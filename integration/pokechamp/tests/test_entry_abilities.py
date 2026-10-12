"""Clone regression with pinned simulator rolls and literal expectations."""

import copy
import json
import subprocess
from pathlib import Path

import pytest

from integration.pokechamp.improved_io.calculator import Calculator
from integration.pokechamp.tests.test_improved_io import mon, scenario

HERE = Path(__file__).parent


def oracle(scenarios):
    return json.loads(
        subprocess.run(
            ["node", str(HERE / "entry_abilities.cjs")],
            input=json.dumps(scenarios),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )


def entry_cases():
    cases = []
    for stage in (1, 0, -1, -2):
        target = mon("Zamazenta", ability="Dauntless Shield", boosts={"def": stage})
        target["entry_effects_observed"] = True
        cases.append(scenario(scenario_id=f"shield-{stage}", defender=target))
    for observed, ability in (
        (False, "Dauntless Shield"),
        (False, ""),
        (True, ""),
        (True, "Fur Coat"),
    ):
        target = mon("Zamazenta", ability=ability)
        target["entry_effects_observed"] = observed
        cases.append(
            scenario(scenario_id=f"shield-{observed}-{ability}", defender=target)
        )
    for name, ability, stat in (
        ("Zacian", "Intrepid Sword", "atk"),
        ("Ogerpon", "Embody Aspect (Teal)", "spe"),
        ("Ogerpon-Hearthflame", "Embody Aspect (Hearthflame)", "atk"),
        ("Ogerpon-Wellspring", "Embody Aspect (Wellspring)", "spd"),
        ("Ogerpon-Cornerstone", "Embody Aspect (Cornerstone)", "def"),
    ):
        for role in ("attacker", "defender"):
            p = mon(name, ability=ability, boosts={stat: 1})
            p["entry_effects_observed"] = True
            parts = {"defender": mon("Mew"), role: p}
            cases.append(scenario(scenario_id=f"{ability}-{role}", **parts))
    return cases


def test_entry_abilities_match_all_sixteen_showdown_rolls():
    cases = entry_cases()
    rows = oracle(cases)
    before = copy.deepcopy(cases)
    with Calculator() as calc:
        result = calc.calculate({}, cases)
        assert result == calc.calculate({}, cases)
    assert cases == before
    for index, entry in enumerate(result["entries"]):
        independent = rows[index * 16 : (index + 1) * 16]
        assert entry["damage_rolls"] == [r["damage"] for r in independent]
        assert (
            entry["conditional_order"]["attacker_speed"]
            == independent[0]["attacker_speed"]
        )
        assert (
            entry["conditional_order"]["defender_speed"]
            == independent[0]["defender_speed"]
        )


def test_worker_clone_input_and_generation_invariants():
    result = subprocess.run(
        ["node", str(HERE / "entry_worker_invariants.cjs")],
        input=json.dumps(entry_cases()),
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["passed"] is True


@pytest.mark.parametrize("drops,stage", [(0, 1), (1, 0), (2, -1)])
def test_showdown_actual_entry_and_close_combat_transitions(drops, stage):
    target = mon(
        "Zamazenta", ability="Dauntless Shield", boosts={"def": stage, "spd": -drops}
    )
    target["entry_effects_observed"] = True
    case = scenario(defender=target)
    rows = oracle([{**case, "close_combats": drops}])
    assert {r["initial_defense"] for r in rows} == {1}
    assert {r["after_close_combat"] for r in rows} == {stage}
    with Calculator() as calc:
        assert calc.calculate({}, [case])["entries"][0]["damage_rolls"] == [
            r["damage"] for r in rows
        ]


def test_turn4_original_input_exact_rolls_and_actual_132_damage():
    cases = json.loads((HERE / "entry_turn4.json").read_text())["scenarios"]
    rows = oracle(cases)
    expected = [
        120,
        121,
        123,
        124,
        126,
        127,
        129,
        130,
        132,
        133,
        135,
        136,
        138,
        139,
        141,
        142,
    ]
    with Calculator() as calc:
        result = calc.calculate({}, cases)
    assert rows[0]["attacker_stats"]["atk"] == 186
    for index, entry in enumerate(result["entries"]):
        assert entry["damage_rolls"] == [
            r["damage"] for r in rows[index * 16 : (index + 1) * 16]
        ]
        assert entry["damage_range_hp"] == ([120, 142] if index < 2 else [126, 148])
    assert result["entries"][0]["damage_rolls"] == expected
    assert 132 in expected


def test_legacy_scene06_expectations_have_independent_rolls():
    fixture = json.loads((HERE / "entry_scene06_expected.json").read_text())
    rows = oracle(fixture["scenarios"])
    for index, case in enumerate(fixture["scenarios"]):
        entry = fixture["entries"][case["scenario_id"]]
        assert entry["damage_rolls"] == [
            r["damage"] for r in rows[index * 16 : (index + 1) * 16]
        ]
