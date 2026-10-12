import json
import logging
import subprocess
from pathlib import Path

from integration.pokechamp.improved_io.state import public_mon, public_revelations


def test_pinned_showdown_public_revelations():
    from poke_env.environment.battle import Battle

    fixture = Path(__file__).with_name("public_revelations.cjs")
    raw = subprocess.check_output(["node", str(fixture)], text=True)
    event = json.loads(raw)
    assert "|Knock Off|" in event["protocol"]
    assert "[from] ability: Poison Heal" in event["protocol"]
    battle = Battle("battle-gen9ou-fixture", "observer", logging.getLogger("test"), gen=9)
    battle._format = "gen9ou"
    # The independent simulator output is the evidence; the parser drops these facts.
    from integration.pokechamp.battle_adapter import install_identity_adapter

    install_identity_adapter()
    for line in event["protocol"].splitlines():
        fields = line.split("|")
        if len(fields) > 1 and fields[1] not in ("", "t:", "split"):
            battle.parse_message(fields)
    opponent = battle.opponent_active_pokemon
    assert "knockoff" not in opponent.moves
    assert opponent.ability is None
    value = public_mon(opponent, public_revelations([event])["p2: Gliscor"])
    assert "knockoff" in value["moves"]
    assert value["ability"] == "poisonheal"


def test_revelations_exclude_called_moves_and_foreign_healing():
    events = [
        {
            "protocol": "|move|p2a: Gliscor|Knock Off|p1a: Mew|[from] move: Metronome\n"
            "|-heal|p2a: Gliscor|80/100|[from] ability: Water Absorb|[of] p1a: Mew"
        }
    ]
    assert public_revelations(events)["p2: Gliscor"] == {"moves": []}
    assert public_revelations([]) == {}


def test_persistent_cloud_clock_cannot_restart_budget(tmp_path):
    import pytest

    from integration.pokechamp.improved_io.receipts import cloud_clock, require_budget

    first = cloud_clock(tmp_path, now=100)
    assert cloud_clock(tmp_path, now=20000) == first
    require_budget(first, now=101)
    with pytest.raises(ValueError, match="budget_stop"):
        require_budget(first, now=13600)
    with pytest.raises(ValueError, match="budget_stop"):
        require_budget(first, 100, now=13501)


def test_boolean_only_offline_receipt_cannot_admit_battles(tmp_path):
    import pytest

    from integration.pokechamp.benchmark import seal_json
    from integration.pokechamp.improved_io.receipts import offline_receipt

    path = tmp_path / "result.json"
    seal_json(path, {"offline_gate_passed": True})
    with pytest.raises(ValueError, match="offline gate"):
        offline_receipt(path)


def test_missing_or_foreign_stage_cannot_admit_cloud(tmp_path):
    import pytest

    from integration.pokechamp.benchmark import seal_json
    from integration.pokechamp.improved_io.receipts import read_stage

    path = tmp_path / "result.json"
    seal_json(path, {"stage": "fake12", "passed": True})
    with pytest.raises(ValueError, match="cloud_gate gate"):
        read_stage(path, "cloud_gate")


def test_future_sight_is_delayed_and_not_an_immediate_damage_modifier():
    import pytest

    from integration.pokechamp.improved_io.calculations import check_effects
    from integration.pokechamp.improved_io.calculator import CalculationError

    rows = json.loads(
        subprocess.check_output(
            ["node", str(Path(__file__).with_name("future_sight.cjs"))], text=True
        )
    )
    future, control = rows
    assert future["hp"][0] == future["hp"][1] == future["hp"][2] > future["hp"][3]
    assert len(set(control["hp"])) == 1
    check_effects({"effects": {"FUTURE_SIGHT": 1}})
    with pytest.raises(CalculationError, match="unsupported active effects"):
        check_effects({"effects": {"SUBSTITUTE": 1}})


def test_double_faint_switch_preserves_unknown_target():
    import pytest

    from integration.pokechamp.improved_io.calculations import compute
    from integration.pokechamp.improved_io.calculator import (
        CalculationError,
        Calculator,
    )

    result = json.loads(
        subprocess.check_output(
            ["node", str(Path(__file__).with_name("double_faint.cjs"))], text=True
        )
    )
    assert result["fainted"] == [True, True] and result["requestState"] == "switch"
    value = {
        "identity": {"state_id": "double-faint"},
        "request": {"kind": "forced_switch", "legal_actions": [{"switch": "pikachu"}]},
        "current_observation": {
            "weather": {},
            "field": {},
            "self_side_conditions": {},
            "opponent_side_conditions": {},
            "self_team": [],
            "opponent_confirmed": [{"active": True, "fainted": True}],
        },
    }
    with Calculator() as calc:
        response = compute(value, calc)
        assert len(response["entries"]) == 1
        assert "UNKNOWN" in response["entries"][0]["excluded_with_reason"]
        assert "damage_range_hp" not in response["entries"][0]
        value["request"] = {"kind": "turn_action", "legal_actions": [{"move": "surf"}]}
        with pytest.raises(CalculationError, match="opponent active missing"):
            compute(value, calc)


def test_observed_quark_speed_and_supreme_overlord_match_showdown():
    import pytest

    from integration.pokechamp.improved_io.calculations import (
        ability_effects,
        check_effects,
    )
    from integration.pokechamp.improved_io.calculator import (
        CalculationError,
        Calculator,
    )

    rows = json.loads(
        subprocess.check_output(
            ["node", str(Path(__file__).with_name("observed_abilities.cjs"))], text=True
        )
    )
    with Calculator() as calc:
        for kind in ("quark", "overlord"):
            for enabled in (False, True):
                group = [r for r in rows if r["kind"] == kind and r["enabled"] == enabled]
                effects = (
                    (
                        {"QUARK_DRIVE": 0, "QUARKDRIVESPE": 0}
                        if kind == "quark"
                        else {"SUPREME_OVERLORD": 0, "FALLEN2": 0}
                    )
                    if enabled
                    else {}
                )
                check_effects({"effects": effects})
                scenario = group[0]["scenario"]
                options = scenario["attacker"]["options"]
                for key in ("abilityOn", "boostedStat", "alliesFainted"):
                    options.pop(key, None)
                options.update(ability_effects({"effects": effects}))
                response = calc.calculate({"kind": kind, "enabled": enabled}, [scenario])[
                    "entries"
                ][0]
                assert response["damage_rolls"] == [r["damage"] for r in group]
                assert response["conditional_order"]["attacker_speed"] == group[0]["speed"]
    with pytest.raises(CalculationError, match="count"):
        ability_effects({"effects": {"SUPREME_OVERLORD": 0}})


def test_fixed_actor_calculator_and_rollup_cadence():
    from integration.pokechamp.improved_io.memory_fixture import run

    result = run()
    assert result["passed"]
    assert len(result["roles"]) == 35
    assert result["roles"][10] == "summary"
    assert result["roles"][-3:] == ["summary", "summary_rollup", "self_action"]
    assert result["cloud_calls"] == 0


def test_cloud_worker_seals_response_before_coordinator_receives_it(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from integration.pokechamp.benchmark import read_sealed
    from integration.pokechamp.improved_io import cloud_gate
    from integration.pokechamp.improved_io.backend import FixedBackend

    class Local(FixedBackend):
        def __init__(self, **kwargs):
            super().__init__(
                environ={"OLLAMA_API_KEY": "local-fixture"},
                trace_sink=kwargs["trace_sink"],
                client_factory=lambda **_: SimpleNamespace(
                    chat=lambda **_: {
                        "model": "glm-5.3-flash",
                        "message": {
                            "content": 'This is a preservation fixture.\n{"move":"splash"}'
                        },
                        "done": True,
                        "done_reason": "stop",
                    }
                ),
            )

    monkeypatch.setattr(cloud_gate.cli, "_load_cloud_credential", lambda: None)
    monkeypatch.setattr(cloud_gate, "FixedBackend", Local)
    path = tmp_path / "response.json"
    item = {
        "id": "response",
        "role": "self_action",
        "output_path": str(path),
        "metadata": {"denominator": "action180", "concurrency": 1, "repeat": 0},
        "context": {
            "identity": {"battle_id": "fixture", "actor_id": "p1", "showdown_turn": 1},
            "condition_id": "B",
            "request": {
                "kind": "turn_action",
                "can_tera": False,
                "legal_actions": [{"move": "splash"}],
            },
        },
    }
    returned = cloud_gate.call(item, "unused-local-socket", 1)
    assert returned["valid"]
    assert read_sealed(path) == returned


def test_coordinator_signal_sets_stop_and_restores_handler(tmp_path, monkeypatch):
    import signal

    from integration.pokechamp.improved_io import cloud_gate

    original = signal.getsignal(signal.SIGINT)

    def collect(*args, concurrency):
        assert concurrency == 8
        signal.raise_signal(signal.SIGINT)
        assert args[-1].is_set()
        return {"passed": False, "stop_requested": True}

    monkeypatch.setattr(cloud_gate, "_collect", collect)
    result = cloud_gate.collect(tmp_path, tmp_path / "stage", None, None, tmp_path, None)
    assert result["stop_requested"]
    assert signal.getsignal(signal.SIGINT) == original


def test_study_halt_blocks_new_cloud_directory_without_resetting_clock(tmp_path):
    import pytest

    from integration.pokechamp.improved_io.cloud_gate import collect
    from integration.pokechamp.improved_io.receipts import cloud_clock, halt_study

    clock = cloud_clock(tmp_path, now=100)
    halt_study(tmp_path, "summary_semantics", tmp_path / "review.json")
    with pytest.raises(ValueError, match="study halted"):
        collect(tmp_path, tmp_path / "new-stage", None, None, tmp_path, None)
    assert not (tmp_path / "new-stage").exists()
    assert cloud_clock(tmp_path, now=1000) == clock
