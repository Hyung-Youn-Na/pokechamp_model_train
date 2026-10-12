import copy
from pathlib import Path

import pytest

from integration.pokechamp.improved_io.calculator import CalculationError, Calculator
from integration.pokechamp.improved_io.output import parse_action


def mon(name, **changes):
    options = dict(
        level=100,
        ability="",
        item="",
        nature="Hardy",
        ivs=dict.fromkeys(("hp", "atk", "def", "spa", "spd", "spe"), 31),
        evs=dict.fromkeys(("hp", "atk", "def", "spa", "spd", "spe"), 0),
        boosts={},
        curHP=100,
        status="",
    )
    options.update(changes)
    return {"name": name, "options": options}


def scenario(**changes):
    value = {
        "scenario_id": "out-1",
        "attacker": mon("Garchomp"),
        "defender": mon("Tinkaton", item="airballoon"),
        "move": "earthquake",
        "field": {},
    }
    value.update(changes)
    return value


def test_calc_air_balloon_is_immunity_not_type_multiplier():
    with Calculator() as calc:
        balloon = calc.calculate({"state_id": "s1"}, [scenario()])
        popped = scenario(defender=mon("Tinkaton"))
        damaged = calc.calculate({"state_id": "s2"}, [popped])
    assert balloon["entries"][0]["damage_range_hp"] == [0, 0]
    assert damaged["entries"][0]["damage_range_hp"][0] > 0
    assert balloon["identity"]["state_id"] == "s1"


def test_spa_minus_two_and_status_non_application():
    with Calculator() as calc:
        move = scenario(
            attacker=mon("Latios"), defender=mon("Blissey"), move="dracometeor"
        )
        full = calc.calculate({"state_id": "s1"}, [move])["entries"][0][
            "damage_range_hp"
        ]
        lowered = copy.deepcopy(move)
        lowered["attacker"]["options"]["boosts"] = {"spa": -2}
        reduced = calc.calculate({"state_id": "s2"}, [lowered])["entries"][0][
            "damage_range_hp"
        ]
        status = calc.calculate({"state_id": "s3"}, [scenario(move="Thunder Wave")])
    assert reduced[1] < full[0]
    assert "excluded_with_reason" in status["entries"][0]
    assert "damage_range_hp" not in status["entries"][0]


def test_calculator_fault_closes_owned_process():
    calc = Calculator()
    calc.process.kill()
    calc.process.wait()
    with pytest.raises(CalculationError):
        calc.calculate({"state_id": "s1"}, [scenario()])
    assert calc.process.poll() is not None


def test_unrecognized_effect_and_self_stat_mismatch_fail_closed():
    for bad in (
        scenario(field={"inventedEffect": True}),
        scenario(attacker={**mon("Garchomp"), "expectedStats": {"atk": 1}}),
    ):
        with Calculator() as calc:
            with pytest.raises(CalculationError):
                calc.calculate({"state_id": "s"}, [bad])
            assert calc.process.poll() is not None


@pytest.mark.parametrize(
    "response",
    [
        'Use it.\n{"move":"surf","move":"surf"}',
        'Use {"move":"surf"}.\n{"move":"surf"}',
        'Use it.\n{"move":"Surf"}',
        'Use it.\n{"move":"surf"} {"move":"surf"}',
        'Use it.\n{"move":"surf","reason":"ok"}',
        '{"move":"surf"}',
        'One. Two. Three.\n{"move":"surf"}',
    ],
)
def test_bad_text_actions_are_rejected(response):
    with pytest.raises(ValueError):
        parse_action(
            response, [{"move": "surf"}], request_kind="turn_action", can_tera=False
        )


def test_exact_candidate_and_tera_boundary():
    response = parse_action(
        'Surf deals 12.5 percent damage.\n{"move":"surf"}',
        [{"move": "surf"}],
        request_kind="turn_action",
        can_tera=False,
    )
    assert response.action == {"move": "surf"}
    with pytest.raises(ValueError):
        parse_action(
            'Use tera.\n{"terastallize":"surf"}',
            [{"terastallize": "surf"}],
            request_kind="turn_action",
            can_tera=False,
        )


def test_source_seal_includes_runtime_assets_but_no_dependencies():
    from integration.pokechamp.benchmark import source_files

    names = {str(p) for p in source_files()}
    assert any(p.endswith("calculator/package-lock.json") for p in names)
    assert any(p.endswith("improved_io/prior.json") for p in names)
    assert not any("/node_modules/" in p for p in names)
    prompts = Path(__file__).parents[1] / "improved_io/prompts"
    assert (prompts / "battle_fixed.txt").read_text() == (
        (prompts / "battle_common.txt").read_text().rstrip()
        + "\n\n"
        + "---"
        + "\n\n"
        + (prompts / "profiles/fixed.txt").read_text().strip()
        + "\n"
    )


def test_balanced_schedule_preserves_ex016_pairs_and_execution_requirement():
    from collections import Counter

    from integration.pokechamp.benchmark import CORE_REPEAT_CONFIG, make_schedule
    from integration.pokechamp.improved_io.conditions import require_parallel, schedule

    reference = make_schedule(CORE_REPEAT_CONFIG, {})
    for smoke, count in ((True, 12), (False, 48)):
        slots = schedule(reference, smoke=smoke)
        assert len(slots) == count
        assert schedule(reference, smoke=smoke) == slots
        for start in range(0, count, 3):
            assert {s["condition_id"] for s in slots[start : start + 3]} == {
                "A",
                "B",
                "C",
            }
        assert Counter(s["condition_id"] for s in slots) == dict.fromkeys(
            "ABC", count // 3
        )
        for slot in slots:
            original = next(
                s
                for s in reference["schedule"]
                if s["slot_id"] == slot["paired_slot_id"]
            )
            assert all(slot[k] == original[k] for k in original if k != "slot_id")
    with pytest.raises(ValueError):
        require_parallel(None)


def summary(battle="b1", actor="p1", event=1):
    from integration.pokechamp.improved_io.memory import HEADINGS

    return (
        "<summary>\n# Battle Summary\n"
        + "\n".join(f"## {h}\nUNKNOWN" for h in HEADINGS)
        + f"\nbattle_id: {battle}\nactor_id: {actor}\n[event:{event}]\n</summary>"
    )


def test_summary_isolation_future_reference_and_three_new_summary_cadence():
    from integration.pokechamp.improved_io.memory import BattleMemory, validate_summary

    for text in (summary(actor="p2"), summary(battle="other"), summary(event=2)):
        with pytest.raises(ValueError):
            validate_summary(text, battle_id="b1", actor_id="p1", event_ids=[1])
    first, second = BattleMemory("b1", "p1", True), BattleMemory("b2", "p1", True)
    for n in (10, 20, 30):
        first.decisions = n
        first.accept(summary(), [1])
    first.accept(summary(), [1], rollup=True)
    assert not first.summaries and first.consolidated
    first.decisions = 40
    first.accept(summary(), [1])
    assert len(first.summaries) == 1
    assert second.archive == [] and second.decisions == 0


def test_fixed_backend_rejects_text_before_success_trace():
    from types import SimpleNamespace

    from integration.pokechamp.cloud import CloudRequestError
    from integration.pokechamp.improved_io.backend import FixedBackend

    backend = FixedBackend(
        environ={"OLLAMA_API_KEY": "fixture"},
        client_factory=lambda **_: SimpleNamespace(
            chat=lambda **_: {
                "model": "glm-5.3-flash",
                "message": {"content": 'Use it.\n{"move":"surf","move":"surf"}'},
                "done_reason": "stop",
            }
        ),
    )
    backend.input_context = {
        "condition_id": "B",
        "identity": {"battle_id": "b"},
        "request": {
            "legal_actions": [{"move": "surf"}],
            "kind": "turn_action",
            "can_tera": False,
        },
    }
    with pytest.raises(CloudRequestError) as error:
        backend.get_LLM_action("fixed", "input", backend.model, json_format=False)
    assert error.value.category == "output_contract"
    assert backend.failure_event.is_set()
    assert backend.response_error == "duplicate JSON key"


def test_observed_dauntless_shield_is_not_applied_twice():
    target = mon("Zamazenta", ability="Dauntless Shield", boosts={"def": 1})
    target["entry_effects_observed"] = True
    with Calculator() as calc:
        actual = calc.calculate({"state_id": "s"}, [scenario(defender=target)])
    # Pinned Showdown independent 85..100 rolls; never derive expected via this worker.
    assert actual["entries"][0]["damage_rolls"] == [
        81,
        82,
        82,
        84,
        84,
        85,
        87,
        87,
        88,
        90,
        90,
        91,
        93,
        93,
        94,
        96,
    ]


def test_low_hp_damage_never_invents_survival_probability():
    with Calculator() as calc:
        result = calc.calculate(
            {"state_id": "s"},
            [scenario(defender=mon("Blissey", curHP=1), move="Dragon Claw")],
        )
    entry = result["entries"][0]
    assert entry["damage_range_hp"][0] > 1
    assert entry["survival_given_hit"] is None and entry["ko_chance_given_hit"] is None


def test_thunder_wave_immunity_and_tie_are_explicit():
    with Calculator() as calc:
        status = calc.calculate(
            {"state_id": "s"},
            [
                scenario(
                    move="Thunder Wave",
                    attacker=mon("Tinkaton"),
                    defender=mon("Ting-Lu"),
                )
            ],
        )
        tie = calc.calculate(
            {"state_id": "s2"},
            [scenario(attacker=mon("Garchomp"), defender=mon("Garchomp"))],
        )
    assert status["entries"][0]["effect_assessment"].startswith("immune:")
    assert (
        tie["entries"][0]["conditional_order"]["equal_priority_speed_relation"]
        == "tie_possible"
    )


def test_failed_gate_prevents_new_battle_plan(tmp_path):
    from integration.pokechamp.benchmark import seal_json
    from integration.pokechamp.improved_io.conditions import require_offline_gate

    path = tmp_path / "gate.json"
    seal_json(path, {"offline_gate_passed": False})
    execution = dict(
        version=1,
        battle_concurrency=10,
        account_request_limit=10,
        model_request_limits={"glm-5.3-flash": 10},
        retry_transient=0,
        evidence={"io_offline_gate": str(path)},
        stop_new_work_at=None,
    )
    with pytest.raises(ValueError, match="did not pass"):
        require_offline_gate(execution)
    execution["evidence"] = {"note": "unqualified"}
    with pytest.raises(ValueError, match="receipt"):
        require_offline_gate(execution)
