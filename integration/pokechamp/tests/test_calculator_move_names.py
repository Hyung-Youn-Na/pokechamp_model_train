"""Dynamic move types from ID inputs, compared with pinned simulator damage rolls."""

import copy
import json
from pathlib import Path

import pytest

from integration.pokechamp.improved_io.calculator import CalculationError, Calculator
from integration.pokechamp.tests.test_calculator_input_audit import damage_oracle
from integration.pokechamp.tests.test_improved_io import mon, scenario

HERE = Path(__file__).parent


def cases():
    rows = []

    def add(label, move, kind, *, attacker=None, field=None, defender=None):
        rows.append(
            (
                scenario(
                    scenario_id=label,
                    move=move,
                    attacker=attacker or mon("Ninetales"),
                    defender=defender or mon("Blissey"),
                    field=field or {},
                ),
                kind,
            )
        )

    for weather, kind in [(None, "Normal"), ("Sun", "Fire"), ("Rain", "Water"),
                          ("Sand", "Rock"), ("Snow", "Ice")]:
        add(f"weather-{weather}", "weatherball", kind,
            field={"weather": weather} if weather else {})
    for weather in ("Sun", "Rain"):
        add(f"umbrella-{weather}", "weatherball", "Normal",
            attacker=mon("Ninetales", item="Utility Umbrella"), field={"weather": weather})
    add("suppressed-sun", "weatherball", "Normal", field={"weather": "Sun"},
        defender=mon("Golduck", ability="Cloud Nine"))
    for item, kind in [("", "Normal"), ("Burn Drive", "Fire"), ("Douse Drive", "Water"),
                       ("Shock Drive", "Electric"), ("Chill Drive", "Ice")]:
        add(f"drive-{kind}", "technoblast", kind, attacker=mon("Genesect", item=item))
    for item, kind in [("", "Normal"), ("Fire Memory", "Fire"), ("Water Memory", "Water")]:
        add(f"memory-{kind}", "multiattack", kind, attacker=mon("Silvally", item=item))
    for terrain, kind in [(None, "Normal"), ("Electric", "Electric"), ("Grassy", "Grass"),
                          ("Misty", "Fairy"), ("Psychic", "Psychic")]:
        add(f"terrain-{terrain}", "terrainpulse", kind,
            field={"terrain": terrain} if terrain else {})
    add("terrain-flying", "terrainpulse", "Normal", attacker=mon("Charizard"),
        field={"terrain": "Electric"})
    add("terrain-levitate", "terrainpulse", "Normal", attacker=mon("Flygon", ability="Levitate"),
        field={"terrain": "Psychic"})
    for species, kind in [("Oricorio", "Fire"), ("Oricorio-Pom-Pom", "Electric"),
                          ("Oricorio-Sensu", "Ghost")]:
        add(f"dance-{kind}", "revelationdance", kind, attacker=mon(species))
    add("dance-tera", "revelationdance", "Water", attacker=mon("Oricorio", teraType="Water"))
    add("ordinary", "flamethrower", "Fire")
    return rows


CASES = cases()


@pytest.fixture(scope="module")
def independent_rolls():
    records = damage_oracle([case for case, _ in CASES])
    return {
        case["scenario_id"]: [
            r["total"] for r in records if r["scenario_id"] == case["scenario_id"]
        ]
        for case, _ in CASES
    }


@pytest.mark.parametrize("modern", [False, True], ids=["legacy", "v2"])
@pytest.mark.parametrize("case,kind", CASES, ids=[case["scenario_id"] for case, _ in CASES])
def test_id_input_dynamic_type_and_independent_rolls(case, kind, modern, independent_rolls):
    identity = {"input_version": "calculator-input-v2"} if modern else {}
    original = copy.deepcopy(case)
    with Calculator() as calc:
        entry = calc.calculate(identity, [case])["entries"][0]
        assert entry["move"]["type"] == kind
        rolls = entry["damage_rolls"]
        if isinstance(rolls, int):
            rolls = [rolls] * 16  # Calc encodes immunity/fixed damage as a scalar.
        assert rolls == independent_rolls[case["scenario_id"]]
        # Names, IDs and caller casing resolve to the same Gen9 move semantics.
        for spelling in (entry["move"]["name"], entry["move"]["name"].upper()):
            named = copy.deepcopy(case)
            named["move"] = spelling
            assert calc.calculate(identity, [named])["entries"][0] == entry
    assert case == original


@pytest.mark.parametrize("modern", [False, True], ids=["legacy", "v2"])
def test_ex031_weather_ball_regression(modern):
    case = json.loads((HERE / "weather_ball_ex031.json").read_text())
    identity = {"input_version": "calculator-input-v2"} if modern else {}
    with Calculator() as calc:
        entry = calc.calculate(identity, [case])["entries"][0]
    assert case["field"]["weather"] == "Sun" and case["move"] == "weatherball"
    assert entry["move"]["type"] == "Fire"
    assert entry["damage_rolls"] == [
        156, 157, 160, 162, 163, 165, 166, 169,
        171, 172, 174, 177, 178, 180, 181, 184,
    ]
    assert entry["damage_range_hp"] == [156, 184]


@pytest.mark.parametrize("modern", [False, True], ids=["legacy", "v2"])
def test_unknown_move_still_fails_closed(modern):
    identity = {"input_version": "calculator-input-v2"} if modern else {}
    with Calculator() as calc:
        with pytest.raises(CalculationError, match="unknown scenario/move"):
            calc.calculate(identity, [scenario(move="not-a-real-move")])
        assert calc.process.poll() is not None
