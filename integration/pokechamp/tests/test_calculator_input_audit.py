"""Independent Gen9 public-history and final-input regressions for EX-030."""

from __future__ import annotations

import copy
import json
import logging
import subprocess
from pathlib import Path

import pytest

from integration.pokechamp.battle_adapter import install_identity_adapter
from integration.pokechamp.improved_io.calculations import own_spec
from integration.pokechamp.improved_io.calculator import CalculationError, Calculator
from integration.pokechamp.improved_io.lifecycle import ability_histories, for_pokemon
from integration.pokechamp.improved_io.state import normalize
from integration.pokechamp.tests.test_improved_io import mon, scenario

HERE = Path(__file__).parent


def simulate(cases):
    return json.loads(
        subprocess.run(
            ["node", str(HERE / "input_lifecycle.cjs")],
            input=json.dumps(cases),
            text=True,
            capture_output=True,
            check=True,
        ).stdout
    )


def observed(snapshot, *, battle_id="test-battle", rolling_only=False):
    from poke_env.environment.battle import Battle
    from poke_env.player.player import Player

    install_identity_adapter()
    actor = snapshot["actor"]
    request = actor["request"]
    battle = Battle(
        "battle-gen9ou-audit", "observer", logging.getLogger("audit"), gen=9
    )
    battle._format = "gen9ou"
    battle._player_role = request["side"]["id"]
    battle.parse_request(request)
    for line in actor["protocol"].splitlines():
        fields = line.split("|")
        if len(fields) > 1 and fields[1] not in Player.MESSAGES_TO_IGNORE:
            battle.parse_message(fields)
    battle.parse_request(request)
    prefix = [
        {"event_seq": 1, "protocol": actor["protocol"]},
        {"event_seq": 2, "protocol": "|request|" + json.dumps(request)},
    ]
    return normalize(
        battle,
        request,
        actor["own_team"],
        prefix[-1:] if rolling_only else prefix,
        observed_protocol=prefix,
        battle_id=battle_id,
        actor_id=request["side"]["id"],
        decision_seq=request["rqid"],
    )[0]


@pytest.fixture(scope="module")
def lifecycle():
    return simulate(
        [
            {
                "name": "reentry",
                "steps": [
                    ["switch 2", "move 1", "bench"],
                    ["switch 2", "move 1", "reentry"],
                    ["move 2", "move 1", "close-combat"],
                    ["move 1", "move 2", "suppressed"],
                    ["switch 2", "move 1", "leave-suppression"],
                    ["switch 2", "move 1", "restored"],
                ],
            }
        ]
    )[0]["snapshots"]


def test_once_per_pokemon_consumption_survives_reentry_and_suppression(lifecycle):
    # Literal expectations, independently verified by actual simulator lifecycle.
    assert [s["oracle"][0]["boosts"]["def"] for s in lifecycle] == [
        1,
        0,
        0,
        -1,
        -1,
        0,
        0,
    ]
    for snap in lifecycle:
        value = observed(snap)
        normalized = {p["ident"]: p for p in value["current_observation"]["self_team"]}
        for truth in snap["oracle"]:
            actual = normalized[truth["ident"]]
            assert actual["boosts"] == {"hp": 0, **truth["boosts"]}
            history = actual.get("ability_history")
            assert history is not None
            assert history["battle_id"] == "test-battle"
            assert history["pokemon_ident"] == truth["ident"]
            assert (
                bool(history["activations"].get("dauntlessshield"))
                == truth["shieldBoost"]
            )
        shield = normalized["p1: Shield"]
        spec = own_spec(shield)
        assert spec["entry_effects_observed"] is True
        with Calculator() as calc:
            # Compare damage into the future reentry (zero stages) or current state.
            entry = calc.calculate(
                {}, [scenario(attacker=mon("Mew"), defender=spec, move="Tackle")]
            )["entries"][0]
        expected = (
            next(s["damage"] for s in lifecycle if s["label"] == "reentry")
            if not shield["active"]
            else snap["damage"]
        )
        assert entry["damage_rolls"] == expected


def test_consumption_is_not_shared_by_species_ability_actor_or_battle():
    events = [
        {
            "event_seq": 1,
            "protocol": "|start\n|switch|p1a: First|Zamazenta|325/325\n"
            "|-ability|p1a: First|Dauntless Shield|boost\n|turn|1\n"
            "|switch|p1a: Other|Mew|341/341\n|turn|30",
        }
    ]
    histories, complete = ability_histories(events, battle_id="one", actor_id="p1")
    assert complete
    for key in ("p1: Second", "p2: First"):
        assert (
            for_pokemon(
                histories, complete, battle_id="one", actor_id="p1", pokemon_ident=key
            )["activations"]
            == {}
        )
    fresh, _ = ability_histories(
        [{"event_seq": 1, "protocol": "|start"}], battle_id="two", actor_id="p1"
    )
    assert fresh == {}
    assert histories["p1: First"]["activations"]["dauntlessshield"] == [
        {"event": 1, "line": 3}
    ]


def test_unknown_history_never_assumes_unused(lifecycle):
    value = observed(lifecycle[1])
    shield = next(
        p
        for p in value["current_observation"]["self_team"]
        if p["ident"] == "p1: Shield"
    )
    shield["ability_history"] = dict(history_complete=False, activations={})
    with pytest.raises(CalculationError, match="unknown.*consumption"):
        own_spec(shield)


def damage_oracle(cases):
    return json.loads(
        subprocess.run(
            ["node", str(HERE / "input_damage_oracle.cjs")],
            input=json.dumps(cases),
            text=True,
            capture_output=True,
            check=True,
        ).stdout
    )


def modern_case(case):
    for role in ("attacker", "defender"):
        case[role]["projected_entry"] = False
        case[role]["entry_effects_observed"] = True
    return case


@pytest.mark.parametrize(
    "move,hp_a,hp_d,target",
    [
        ("Super Fang", 100, 201, "Blissey"),
        ("Super Fang", 100, 1, "Blissey"),
        ("Super Fang", 100, 201, "Gengar"),
        ("Endeavor", 100, 201, "Blissey"),
        ("Endeavor", 201, 100, "Blissey"),
        ("Endeavor", 100, 201, "Gengar"),
        ("Ruination", 100, 201, "Blissey"),
        ("Seismic Toss", 100, 201, "Blissey"),
        ("Night Shade", 100, 201, "Mew"),
        ("Night Shade", 100, 201, "Blissey"),
        ("Fissure", 100, 201, "Blissey"),
        ("Fissure", 100, 201, "Dragonite"),
        ("Sheer Cold", 100, 201, "Glaceon"),
        ("Guillotine", 100, 201, "Gengar"),
    ],
)
def test_fixed_damage_against_independent_actual_execution(move, hp_a, hp_d, target):
    case = modern_case(
        scenario(
            attacker=mon("Mew", curHP=hp_a), defender=mon(target, curHP=hp_d), move=move
        )
    )
    expected = damage_oracle([case])
    with Calculator() as calc:
        result = calc.calculate({"input_version": "calculator-input-v2"}, [case])[
            "entries"
        ][0]
    assert result["damage_range_hp"] == [
        min(r["total"] for r in expected),
        max(r["total"] for r in expected),
    ]
    assert len(set(r["total"] for r in expected)) == 1


@pytest.mark.parametrize(
    "item,ability,counts",
    [("", "", [2, 3, 4, 5]), ("Loaded Dice", "", [4, 5]), ("", "Skill Link", [5])],
)
def test_icicle_spear_explicit_hit_support_and_sixteen_independent_rolls(
    item, ability, counts
):
    case = modern_case(
        scenario(
            attacker=mon("Kyurem", ability=ability, item=item, curHP=300),
            defender=mon("Mew", curHP=341),
            move="Icicle Spear",
        )
    )
    expected = damage_oracle(
        [{**case, "hits": n, "scenario_id": f"hits-{n}"} for n in counts]
    )
    with Calculator() as calc:
        result = calc.calculate({"input_version": "calculator-input-v2"}, [case])[
            "entries"
        ][0]
    assert [v["hits"] for v in result["damage_variants"]] == counts
    for variant in result["damage_variants"]:
        rows = [r for r in expected if r["scenario_id"] == f"hits-{variant['hits']}"]
        for i, row in enumerate(rows):
            assert [rolls[i] for rolls in variant["damage_rolls"]] == row["hits"]
        assert variant["damage_range_hp"] == [
            min(r["total"] for r in rows),
            max(r["total"] for r in rows),
        ]


def test_fickle_beam_preserves_both_power_branches():
    case = modern_case(
        scenario(
            attacker=mon("Hydrapple", curHP=300),
            defender=mon("Blissey", curHP=650),
            move="Fickle Beam",
        )
    )
    expected = damage_oracle(
        [
            {**case, "fickle_all_out": flag, "scenario_id": str(flag)}
            for flag in (False, True)
        ]
    )
    with Calculator() as calc:
        result = calc.calculate({"input_version": "calculator-input-v2"}, [case])[
            "entries"
        ][0]
    assert len(result["damage_variants"]) == 2
    for variant, flag in zip(result["damage_variants"], (False, True), strict=True):
        assert variant["damage_rolls"] == [
            r["total"] for r in expected if r["scenario_id"] == str(flag)
        ]


def test_final_input_detects_damage_tampering_and_required_history_removal(lifecycle):
    from integration.pokechamp.improved_io.calculations import compute
    from integration.pokechamp.improved_io.gate import validate_input
    from integration.pokechamp.improved_io.state import stable_id

    value = observed(lifecycle[1])
    with Calculator() as calc:
        value["calculation_bundle"] = compute(value, calc)
    validate_input(value)
    changed = copy.deepcopy(value)
    changed["calculation_bundle"]["entries"][0]["defender_max_hp"] = 999
    with pytest.raises(ValueError, match="bundle content"):
        validate_input(changed)
    changed = copy.deepcopy(value)
    del changed["current_observation"]["self_team"][0]["ability_history"]
    core = {
        k: changed[k]
        for k in (
            "request",
            "current_observation",
            "opponent_hypotheses",
            "recent_events",
            "lesson_memory",
            "unknowns",
            "battle_summary",
        )
    }
    changed["identity"]["state_id"] = stable_id(core)
    changed["calculation_bundle"]["identity"] = changed["identity"]
    changed["calculation_bundle"]["bundle_sha256"] = stable_id(
        {
            k: v
            for k, v in changed["calculation_bundle"].items()
            if k not in ("elapsed_ms", "bundle_sha256")
        }
    )
    with pytest.raises(ValueError, match="history"):
        validate_input(changed)


@pytest.mark.parametrize(
    "species,ability,item,damage_move",
    [
        ("Ninetales", "Drought", "", "Hurricane"),
        ("Ninetales", "Drought", "Heavy-Duty Boots", "Hurricane"),
        ("Latios", "Levitate", "", "Tackle"),
        ("Zapdos", "Static", "", "Tackle"),
        ("Clefable", "Magic Guard", "", "Tackle"),
        ("Zamazenta", "Dauntless Shield", "", "Tackle"),
        ("Landorus-Therian", "Intimidate", "", "Tackle"),
        ("Iron Valiant", "Quark Drive", "Booster Energy", "Tackle"),
    ],
)
def test_selected_switch_uses_actual_hazards_weather_and_entry_state(
    species, ability, item, damage_move
):
    from integration.pokechamp.improved_io.calculations import field_for

    fixture = {
        "name": "switch",
        "own": [
            {"species": "Mew", "ability": "Synchronize", "moves": ["Splash"]},
            {"species": species, "ability": ability, "item": item, "moves": ["Splash"]},
        ],
        "other": [
            {
                "species": "Mew",
                "ability": "Synchronize",
                "moves": ["Stealth Rock", "Spikes", "Splash", damage_move],
            }
        ],
        "damage_move": damage_move,
        "steps": [
            ["move 1", "move 1", "rocks"],
            ["move 1", "move 2", "before"],
            ["switch 2", "move 3", "after"],
        ],
    }
    snapshots = simulate([fixture])[0]["snapshots"]
    before = observed(snapshots[-2])
    after = snapshots[-1]
    target = next(
        p for p in before["current_observation"]["self_team"] if not p["active"]
    )
    field = field_for(before["current_observation"])
    field = {
        **field,
        "attackerSide": field["defenderSide"],
        "defenderSide": field["attackerSide"],
    }
    case = scenario(
        attacker={
            **mon("Mew", ability="Synchronize", curHP=341),
            "projected_entry": False,
            "entry_effects_observed": True,
        },
        defender=own_spec(target),
        move=damage_move,
        field=field,
    )
    with Calculator() as calc:
        result = calc.calculate(before["identity"], [case])["entries"][0]
    assert result["damage_rolls"] == after["damage"]
    assert (
        result["scenario_state"]["entry"][0]["hp_after_hazards"]
        == after["oracle"][0]["hp"]
    )


def test_download_does_not_reapply_an_observed_boost():
    case = modern_case(
        scenario(
            attacker=mon("Porygon2", ability="Download", boosts={"spa": 1}),
            defender=mon("Mew", curHP=341),
            move="Thunderbolt",
        )
    )
    expected = damage_oracle([case])
    with Calculator() as calc:
        result = calc.calculate({"input_version": "calculator-input-v2"}, [case])[
            "entries"
        ][0]
    assert result["damage_rolls"] == [r["total"] for r in expected]


def ready_value(snapshot):
    from integration.pokechamp.improved_io.calculations import compute

    value = observed(snapshot)
    value["condition_id"] = "B"
    with Calculator() as calc:
        value["calculation_bundle"] = compute(value, calc)
    return value


def test_final_fake_backend_receives_required_state_and_rejects_corruption(
    lifecycle, monkeypatch
):
    from integration.pokechamp.benchmark_player import BenchmarkBackend
    from integration.pokechamp.improved_io.backend import FixedBackend
    from integration.pokechamp.improved_io.battle_prompts import assemble, identity

    value = ready_value(lifecycle[1])
    backend = FixedBackend.__new__(FixedBackend)
    backend.io_profile = "io-battle-only-v1"
    backend.input_context = value
    backend.battle_prompt_identity = identity("v1.2.0")
    backend.summary_prompt_identity = None
    backend.role = "self_action"
    backend.experiment_policy = {}
    delivered = []

    def fake_transport(self, system, user, *args, **kwargs):
        self._request_context()
        delivered.append((system, json.loads(user)))
        return "Local fake response"

    monkeypatch.setattr(BenchmarkBackend, "get_LLM_action", fake_transport)
    system = assemble(value, version="v1.2.0")
    assert backend.get_LLM_action(system, json.dumps(value)) == "Local fake response"
    assert delivered[0][1] == value
    shield = next(
        p
        for p in delivered[0][1]["current_observation"]["self_team"]
        if p["ident"] == "p1: Shield"
    )
    assert shield["ability_history"]["activations"]["dauntlessshield"]
    for mutate in (
        lambda v: v["calculation_bundle"]["entries"].pop(),
        lambda v: v["current_observation"]["self_team"][0].pop("ability_history"),
        lambda v: v["calculation_bundle"]["identity"].update(actor_id="p2"),
    ):
        corrupted = copy.deepcopy(value)
        mutate(corrupted)
        backend.input_context = corrupted
        with pytest.raises(ValueError):
            backend.get_LLM_action(system, json.dumps(corrupted))
        assert len(delivered) == 1


def test_side_swap_repetition_order_and_parallel_calculators(lifecycle):
    from concurrent.futures import ThreadPoolExecutor

    from integration.pokechamp.improved_io.calculations import compute

    original = copy.deepcopy(lifecycle[1])
    swapped = copy.deepcopy(original)
    raw = (
        json.dumps(swapped["actor"])
        .replace("p1", "TEMP_SIDE")
        .replace("p2", "p1")
        .replace("TEMP_SIDE", "p2")
    )
    swapped["actor"] = json.loads(raw)
    values = [observed(original), observed(swapped)]
    with ThreadPoolExecutor(max_workers=2) as pool:

        def run(value):
            with Calculator() as calc:
                first = compute(value, calc)
                before = copy.deepcopy(calc.last_request)
                second = compute(value, calc)
                assert first["entries"] == second["entries"]
                reversed_response = calc.calculate(
                    value["identity"], list(reversed(before["scenarios"]))
                )
                assert reversed_response["entries"] == list(reversed(first["entries"]))
                assert calc.process.poll() is None
            assert calc.process.poll() is not None
            return first

        results = list(pool.map(run, values))
    assert results[0]["entries"] == results[1]["entries"]
    assert [r["identity"]["actor_id"] for r in results] == ["p1", "p2"]


def test_history_older_than_rolling_window_is_retained(lifecycle):
    value = observed(lifecycle[-2], rolling_only=True)
    assert (
        len(value["recent_events"]) == 1
        and "|Dauntless Shield|" not in value["recent_events"][0]["protocol"]
    )
    shield = next(
        p
        for p in value["current_observation"]["self_team"]
        if p["ident"] == "p1: Shield"
    )
    assert own_spec(shield)["entry_effects_observed"] is True
    assert shield["ability_history"]["activations"]["dauntlessshield"]


@pytest.mark.parametrize(
    "species,ability,item,tera,boost",
    [
        ("Ogerpon", "Defiant", "", "Grass", "spe"),
        ("Ogerpon-Hearthflame", "Mold Breaker", "Hearthflame Mask", "Fire", "atk"),
        ("Ogerpon-Wellspring", "Water Absorb", "Wellspring Mask", "Water", "spd"),
        ("Ogerpon-Cornerstone", "Sturdy", "Cornerstone Mask", "Rock", "def"),
    ],
)
def test_tera_form_and_repeat_embody_aspect_follow_real_actions(
    species, ability, item, tera, boost
):
    from integration.pokechamp.improved_io.calculations import compute, tera_spec

    fixture = {
        "name": "embody",
        "own": [
            {
                "species": species,
                "ability": ability,
                "item": item,
                "teraType": tera,
                "moves": ["Tackle", "Splash"],
            },
            {"species": "Mew", "ability": "Synchronize", "moves": ["Splash"]},
        ],
        "steps": [
            ["move 2 terastallize", "move 1", "tera"],
            ["switch 2", "move 1", "bench"],
            ["switch 2", "move 1", "reentry"],
        ],
    }
    snapshots = simulate([fixture])[0]["snapshots"]
    before = observed(snapshots[0])
    tera_state = observed(snapshots[1])
    bench = observed(snapshots[2])
    reentry = observed(snapshots[3])
    assert snapshots[1]["oracle"][0]["boosts"][boost] == 1
    assert snapshots[3]["oracle"][0]["boosts"][boost] == 1
    assert tera_state["current_observation"]["self_team"][0]["boosts"][boost] == 1
    assert reentry["current_observation"]["self_team"][0]["boosts"][boost] == 1
    current = before["current_observation"]["self_team"][0]
    projected = tera_spec(current, own_spec(current))
    outgoing = scenario(
        attacker=projected,
        defender={
            **mon("Mew", ability="Synchronize", curHP=341),
            "projected_entry": False,
        },
        move="Tackle",
    )
    with Calculator() as calc:
        result = calc.calculate(before["identity"], [outgoing])["entries"][0]
        assert result["damage_rolls"] == snapshots[1]["outgoingDamage"]
        assert result["scenario_state"]["phase"] == "after_selected_terastallization"
        bundle = compute(before, calc)
        assert any(c["scenario_id"].startswith("in-tera-") for c in bundle["coverage"])
        target = next(
            p for p in bench["current_observation"]["self_team"] if not p["active"]
        )
        incoming = scenario(
            attacker={
                **mon("Mew", ability="Synchronize", curHP=341),
                "projected_entry": False,
            },
            defender=own_spec(target),
            move="Tackle",
        )
        result = calc.calculate(bench["identity"], [incoming])["entries"][0]
        assert result["damage_rolls"] == snapshots[3]["damage"]


@pytest.mark.parametrize(
    "case",
    [
        scenario(
            attacker=mon("Mew"),
            defender=mon("Dragonite", ability="Multiscale", curHP=323),
            move="Tackle",
            field={"defenderSide": {"isSR": True}},
        ),
        scenario(
            attacker=mon("Mew"),
            defender=mon("Skarmory", ability="Weak Armor", curHP=271),
            move="Double Kick",
        ),
        scenario(
            attacker=mon("Comfey", ability="Triage"),
            defender=mon("Mew", curHP=341),
            move="Draining Kiss",
        ),
        scenario(
            attacker=mon("Mew", status="brn", boosts={"atk": 2}),
            defender=mon("Mew", curHP=341),
            move="Tackle",
            field={"defenderSide": {"isReflect": True}},
        ),
        scenario(
            attacker=mon("Mew", status="par"),
            defender=mon("Mew", curHP=341),
            move="Surf",
            field={
                "weather": "Sun",
                "defenderSide": {"isLightScreen": True},
                "attackerSide": {"isTailwind": True},
            },
        ),
        scenario(
            attacker=mon("Rillaboom", ability="Overgrow"),
            defender=mon("Mew", curHP=341),
            move="Grassy Glide",
            field={"terrain": "Grassy"},
        ),
        scenario(
            attacker=mon("Mew", teraType="Water"),
            defender=mon("Mew", teraType="Fire", curHP=341),
            move="Surf",
            field={"weather": "Rain"},
        ),
        scenario(
            attacker=mon("Iron Valiant", ability="Quark Drive", item="Booster Energy"),
            defender=mon("Mew", curHP=341),
            move="Acrobatics",
            field={"terrain": "Electric"},
        ),
        scenario(
            attacker=mon("Mew"),
            defender=mon(
                "Iron Valiant", ability="Quark Drive", item="Booster Energy", curHP=289
            ),
            move="Poltergeist",
            field={"terrain": "Electric"},
        ),
        scenario(
            attacker=mon("Mew"),
            defender=mon(
                "Iron Valiant", ability="Quark Drive", item="Booster Energy", curHP=289
            ),
            move="Knock Off",
            field={"terrain": "Electric"},
        ),
    ],
)
def test_ordinary_damage_and_pre_hit_speed_against_simulator(case):
    case = modern_case(copy.deepcopy(case))
    expected = damage_oracle([case])
    with Calculator() as calc:
        result = calc.calculate({"input_version": "calculator-input-v2"}, [case])[
            "entries"
        ][0]
    if isinstance(result["damage_rolls"][0], list):
        for i, row in enumerate(expected):
            assert [roll[i] for roll in result["damage_rolls"]] == row["hits"]
    else:
        assert result["damage_rolls"] == [r["total"] for r in expected]
    assert (
        result["conditional_order"]["attacker_speed"]
        == expected[0]["before"]["attacker_speed"]
    )
    assert (
        result["conditional_order"]["defender_speed"]
        == expected[0]["before"]["defender_speed"]
    )
    if case["move"] == "Draining Kiss":
        assert result["conditional_order"]["move_priority"] == 3
    if case["move"] == "Grassy Glide":
        assert result["conditional_order"]["move_priority"] == 1


@pytest.mark.parametrize(
    "item,terrain",
    [("Booster Energy", False), ("Booster Energy", True), ("Electric Seed", True)],
)
def test_projected_qp_items_follow_actual_terrain_and_consumption(item, terrain):
    from integration.pokechamp.improved_io.calculations import field_for

    snapshots = simulate(
        [
            {
                "name": "qp-item",
                "own": [
                    {"species": "Mew", "ability": "Synchronize", "moves": ["Splash"]},
                    {
                        "species": "Iron Valiant",
                        "ability": "Quark Drive",
                        "item": item,
                        "moves": ["Splash"],
                    },
                ],
                "other": [
                    {
                        "species": "Mew",
                        "ability": "Synchronize",
                        "moves": ["Electric Terrain", "Splash"],
                    }
                ],
                "damage_move": "Knock Off",
                "steps": [
                    ["move 1", "move 1" if terrain else "move 2", "before"],
                    ["switch 2", "move 2", "after"],
                ],
            }
        ]
    )[0]["snapshots"]
    before = observed(snapshots[-2])
    target = next(
        p for p in before["current_observation"]["self_team"] if not p["active"]
    )
    f = field_for(before["current_observation"])
    f = {**f, "attackerSide": f["defenderSide"], "defenderSide": f["attackerSide"]}
    case = scenario(
        attacker={**mon("Mew", ability="Synchronize"), "projected_entry": False},
        defender=own_spec(target),
        move="Knock Off",
        field=f,
    )
    with Calculator() as calc:
        result = calc.calculate(before["identity"], [case])["entries"][0]
    expected = snapshots[-1]["damage"]
    assert result["damage_rolls"] == (0 if all(x == 0 for x in expected) else expected)
    assert snapshots[-1]["oracle"][0]["item"] == (
        "boosterenergy" if terrain and item == "Booster Energy" else ""
    )


@pytest.mark.parametrize(
    "hazard,species,ability,item",
    [
        ("Toxic Spikes", "Milotic", "Marvel Scale", ""),
        ("Toxic Spikes", "Milotic", "Marvel Scale", "Heavy-Duty Boots"),
        ("Toxic Spikes", "Gengar", "Cursed Body", ""),
        ("Sticky Web", "Uxie", "Synchronize", ""),
        ("Sticky Web", "Serperior", "Contrary", ""),
        ("Sticky Web", "Bisharp", "Defiant", ""),
    ],
)
def test_entry_hazard_status_and_ranks(hazard, species, ability, item):
    from integration.pokechamp.improved_io.calculations import field_for

    snapshots = simulate(
        [
            {
                "name": "status-hazard",
                "own": [
                    {"species": "Mew", "ability": "Synchronize", "moves": ["Splash"]},
                    {
                        "species": species,
                        "ability": ability,
                        "item": item,
                        "moves": ["Splash"],
                    },
                ],
                "other": [
                    {
                        "species": "Mew",
                        "ability": "Synchronize",
                        "moves": [hazard, "Splash"],
                    }
                ],
                "steps": [
                    ["move 1", "move 1", "before"],
                    ["switch 2", "move 2", "after"],
                ],
            }
        ]
    )[0]["snapshots"]
    before = observed(snapshots[-2])
    target = next(
        p for p in before["current_observation"]["self_team"] if not p["active"]
    )
    f = field_for(before["current_observation"])
    f = {**f, "attackerSide": f["defenderSide"], "defenderSide": f["attackerSide"]}
    case = scenario(
        attacker={**mon("Mew", ability="Synchronize"), "projected_entry": False},
        defender=own_spec(target),
        move="Tackle",
        field=f,
    )
    with Calculator() as calc:
        result = calc.calculate(before["identity"], [case])["entries"][0]
    assert result["damage_rolls"] == (
        0 if all(x == 0 for x in snapshots[-1]["damage"]) else snapshots[-1]["damage"]
    )
    after = observed(snapshots[-1])
    actual = after["current_observation"]["self_team"][0]
    with Calculator() as calc:
        current = calc.calculate(
            after["identity"], [{**case, "defender": own_spec(actual)}]
        )["entries"][0]
    assert current["conditional_order"] == result["conditional_order"]


def test_intrepid_sword_forced_switch_consumption():
    snapshots = simulate(
        [
            {
                "name": "sword",
                "own": [
                    {
                        "name": "Sword",
                        "species": "Zacian",
                        "ability": "Intrepid Sword",
                        "moves": ["Splash"],
                    },
                    {"species": "Mew", "ability": "Synchronize", "moves": ["Splash"]},
                ],
                "steps": [
                    ["move 1", "move 3", "dragged"],
                    ["switch 2", "move 1", "reentry"],
                ],
            }
        ]
    )[0]["snapshots"]
    assert [
        s["oracle"][
            next(i for i, p in enumerate(s["oracle"]) if p["ident"] == "p1: Sword")
        ]["swordBoost"]
        for s in snapshots
    ] == [True] * 3
    for s in snapshots:
        v = observed(s)
        p = next(
            p
            for p in v["current_observation"]["self_team"]
            if p["ident"] == "p1: Sword"
        )
        assert own_spec(p)["entry_effects_observed"]
        assert len(p["ability_history"]["activations"]["intrepidsword"]) == 1


def test_weather_replacement_clears_field_qp_before_damage():
    from integration.pokechamp.improved_io.calculations import field_for

    snapshots = simulate(
        [
            {
                "name": "field-qp",
                "own": [
                    {"species": "Mew", "ability": "Synchronize", "moves": ["Splash"]},
                    {"species": "Pelipper", "ability": "Drizzle", "moves": ["Splash"]},
                ],
                "other": [
                    {
                        "species": "Walking Wake",
                        "ability": "Protosynthesis",
                        "moves": ["Sunny Day", "Splash"],
                    }
                ],
                "damage_move": "Surf",
                "steps": [["move 1", "move 1", "sun"], ["switch 2", "move 2", "rain"]],
            }
        ]
    )[0]["snapshots"]
    before = observed(snapshots[-2])
    target = next(
        p for p in before["current_observation"]["self_team"] if not p["active"]
    )
    f = field_for(before["current_observation"])
    f = {**f, "attackerSide": f["defenderSide"], "defenderSide": f["attackerSide"]}
    case = scenario(
        attacker={
            **mon("Walking Wake", ability="Protosynthesis", boostedStat="spa"),
            "qp_source": "field",
            "projected_entry": False,
        },
        defender=own_spec(target),
        move="Surf",
        field=f,
    )
    with Calculator() as calc:
        result = calc.calculate(before["identity"], [case])["entries"][0]
    assert result["scenario_state"]["weather"] == "Rain"
    assert result["damage_rolls"] == snapshots[-1]["damage"]


def test_wind_rider_observed_tailwind_boost_is_not_reapplied():
    from integration.pokechamp.improved_io.calculations import field_for

    snapshots = simulate(
        [
            {
                "name": "wind",
                "own": [
                    {
                        "species": "Brambleghast",
                        "ability": "Wind Rider",
                        "moves": ["Tailwind", "Splash"],
                    },
                ],
                "steps": [["move 1", "move 1", "tailwind"]],
            }
        ]
    )[0]["snapshots"]
    value = observed(snapshots[-1])
    target = value["current_observation"]["self_team"][0]
    assert snapshots[-1]["oracle"][0]["boosts"]["atk"] == 1
    case = scenario(
        attacker=own_spec(target),
        defender={
            **mon("Mew", ability="Synchronize", curHP=341),
            "projected_entry": False,
        },
        move="Tackle",
        field=field_for(value["current_observation"]),
    )
    with Calculator() as calc:
        result = calc.calculate(value["identity"], [case])["entries"][0]
    assert result["damage_rolls"] == snapshots[-1]["outgoingDamage"]


def test_supreme_overlord_candidate_counts_actual_public_faint():
    from integration.pokechamp.improved_io.calculations import field_for

    snapshots = simulate(
        [
            {
                "name": "fallen",
                "own": [
                    {"species": "Mew", "ability": "Synchronize", "moves": ["Memento"]},
                    {
                        "species": "Kingambit",
                        "ability": "Supreme Overlord",
                        "moves": ["Splash"],
                    },
                ],
                "steps": [
                    ["move 1", "move 1", "faint"],
                    ["switch 2", "", "replacement"],
                ],
            }
        ]
    )[0]["snapshots"]
    before = observed(snapshots[-2])
    target = next(
        p
        for p in before["current_observation"]["self_team"]
        if p["species"] == "kingambit"
    )
    candidate = own_spec(target)
    assert candidate["options"]["alliesFainted"] == 1
    case = scenario(
        attacker=candidate,
        defender={
            **mon("Mew", ability="Synchronize", curHP=341),
            "projected_entry": False,
        },
        move="Tackle",
        field=field_for(before["current_observation"]),
    )
    with Calculator() as calc:
        result = calc.calculate(before["identity"], [case])["entries"][0]
    assert result["damage_rolls"] == snapshots[-1]["outgoingDamage"]


def test_cloud_nine_entry_suppresses_field_qp_before_damage():
    from integration.pokechamp.improved_io.calculations import field_for

    snapshots = simulate(
        [
            {
                "name": "suppress-weather",
                "own": [
                    {"species": "Mew", "ability": "Synchronize", "moves": ["Splash"]},
                    {
                        "species": "Golduck",
                        "ability": "Cloud Nine",
                        "moves": ["Splash"],
                    },
                ],
                "other": [
                    {
                        "species": "Walking Wake",
                        "ability": "Protosynthesis",
                        "moves": ["Sunny Day", "Splash"],
                    }
                ],
                "damage_move": "Surf",
                "steps": [
                    ["move 1", "move 1", "sun"],
                    ["switch 2", "move 2", "suppressed"],
                ],
            }
        ]
    )[0]["snapshots"]
    before = observed(snapshots[-2])
    target = next(
        p for p in before["current_observation"]["self_team"] if not p["active"]
    )
    f = field_for(before["current_observation"])
    f = {**f, "attackerSide": f["defenderSide"], "defenderSide": f["attackerSide"]}
    case = scenario(
        attacker={
            **mon("Walking Wake", ability="Protosynthesis", boostedStat="spa"),
            "qp_source": "field",
            "projected_entry": False,
        },
        defender=own_spec(target),
        move="Surf",
        field=f,
    )
    with Calculator() as calc:
        result = calc.calculate(before["identity"], [case])["entries"][0]
    assert result["scenario_state"]["weather"] is None
    assert result["damage_rolls"] == snapshots[-1]["damage"]
