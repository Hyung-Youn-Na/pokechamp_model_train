"""Independent execution controls for the diagnostic, not production damage corrections."""

import copy
import json
import subprocess

import pytest

from integration.pokechamp.diagnostics.special_moves import (
    classify,
    comparable,
    node,
    per_hit_comparison,
    run,
    verify_build_sources,
    verify_source,
)
from integration.pokechamp.improved_io.calculator import Calculator


@pytest.fixture(scope="module")
def catalog():
    return node(
        {
            "op": "catalog",
            "prior": {"data": {}},
            "teams": {"control": "- Weather Ball\n- Bullet Seed\n- Tackle"},
        }
    )


def fixture(catalog, name):
    return copy.deepcopy(next(f for f in catalog["fixtures"] if f["scenario_id"] == name))


def execute(catalog, name):
    return node({"op": "execute", "fixture": fixture(catalog, name)})


def wrapper(f, result):
    with Calculator() as calculator:
        return [
            calculator.calculate(
                {"test": i},
                [
                    {
                        k: o["effective"][k]
                        for k in ("scenario_id", "move", "attacker", "defender", "field")
                    }
                ],
            )
            for i, o in enumerate(result["observations"])
        ]


@pytest.mark.parametrize(
    "name,damage",
    [
        ("superfang/base", 100),
        ("endeavor/user-hp-100", 101),
        ("ruination/base", 100),
        ("ruination/target-hp-1", 1),
        ("superfang/ghost", 0),
        ("ruination/protect", 0),
        ("nightshade/normal-neutral", 100),
        ("nightshade/base", 0),
    ],
)
def test_real_discrepancy_versus_normal_zero(catalog, name, damage):
    f = fixture(catalog, name)
    result = node({"op": "execute", "fixture": f})
    assert {o["direct_before_cap"] for o in result["observations"]} == {damage}
    verdict = classify(f, result, wrapper(f, result))
    expected = (
        "numerical_mismatch" if name in ("superfang/base", "endeavor/user-hp-100") else "match"
    )
    assert verdict["status"] == expected
    if damage == 0:
        assert verdict["normal_zero"]


@pytest.mark.parametrize(
    "name,success",
    [
        ("fissure/base", True),
        ("fissure/lower-level", False),
        ("fissure/flying", False),
        ("fissure/sturdy", False),
        ("sheercold/ice", False),
        ("guillotine/ghost", False),
    ],
)
def test_conditional_ohko_preserves_failure_rules(catalog, name, success):
    obs = execute(catalog, name)["observations"][0]
    assert bool(obs["direct_applied"]) == success
    if success:
        assert obs["direct_before_cap"] == 651
        assert obs["direct_applied"] == 201


def test_cap_and_non_damage_hp_redistribution(catalog):
    obs = execute(catalog, "painsplit/user-hp-100")["observations"][0]
    assert obs["hits"] == []
    assert obs["after"] == {"attacker": 150, "defender": 150}
    obs = execute(catalog, "finalgambit/user-hp-341")["observations"][0]
    assert obs["direct_before_cap"] == 341
    assert obs["direct_applied"] == 201
    assert obs["after"]["attacker"] == 0  # self KO is not added to direct target damage


def test_history_paths_and_missing_input(catalog):
    for name, positive in [
        ("counter/base", False),
        ("counter/received-tackle", True),
        ("counter/received-swift", False),
        ("mirrorcoat/received-swift", True),
        ("comeuppance/previous-turn-hit", False),
    ]:
        f = fixture(catalog, name)
        result = node({"op": "execute", "fixture": f})
        assert bool(result["observations"][0]["direct_before_cap"]) == positive
        verdict = classify(f, result, wrapper(f, result))
        assert verdict["status"] == "input_insufficient"
        assert verdict["silent_zero_with_missing_input"]
    single = execute(catalog, "counter/received-doublehit")["observations"][0]
    # Counter returns twice the last hit, not twice total damage received.
    assert single["direct_before_cap"] == 2 * single["history_hits"][-1]["applied"]


def test_multihit_counts_and_early_faint(catalog):
    for name, count in [
        ("bulletseed/hits-2", 2),
        ("bulletseed/hits-5", 5),
        ("bulletseed/early-ko", 1),
    ]:
        result = execute(catalog, name)
        obs = result["observations"][0]
        assert per_hit_comparison(fixture(catalog, name), result)["status"] == "match"
        assert len(obs["hits"]) == count
        assert obs["direct_applied"] == sum(h["applied"] for h in obs["hits"])


def test_weather_mapping_and_sixteen_rolls(catalog):
    f = fixture(catalog, "weatherball/weather-Snow")
    result = node({"op": "execute", "fixture": f})
    assert len(result["observations"]) == 16
    assert all(o["state"]["weather"] == "snowscape" for o in result["observations"])
    assert classify(f, result, wrapper(f, result))["status"] == "match"
    f["field"]["weather"] = "invalid-weather"
    with pytest.raises(subprocess.CalledProcessError):
        node({"op": "execute", "fixture": f})


def test_unknown_move_is_fatal_and_placeholder_visible():
    with pytest.raises(subprocess.CalledProcessError):
        node({"op": "catalog", "prior": {"data": {}}, "teams": {"1": "- MadeUpMove"}})
    data = node(
        {
            "op": "catalog",
            "prior": {"data": {"ditto": {"moves": [{"name": "Nothing"}]}}},
            "teams": {},
        }
    )
    candidate = next(c for c in data["candidates"] if c["id"] == "nothing")
    assert candidate["excluded"]
    assert candidate["origins"] == ["prior-all:ditto", "prior-default-no-observed:ditto"]


def test_provenance_and_evidence_not_overwritten(catalog, tmp_path):
    assert verify_build_sources(catalog["loaded_sources"])
    with pytest.raises(ValueError, match="source identity drift"):
        verify_source({"integration/pokechamp/diagnostics/special_moves.cjs": "wrong"})
    path = tmp_path / "existing"
    path.mkdir()
    (path / "original.json").write_text('{"preserved": true}')
    with pytest.raises(FileExistsError):
        run(path)
    assert sorted(p.name for p in path.iterdir()) == ["original.json"]
    assert json.loads((path / "original.json").read_text())["preserved"]


def test_replay_ignores_only_clock_annotations():
    first = {"observations": [{"log": ["|t:|10", "|-damage|x|1/10"], "direct_applied": 5}]}
    second = copy.deepcopy(first)
    second["observations"][0]["log"][0] = "|t:|20"
    assert comparable(first) == comparable(second)
    second["observations"][0]["direct_applied"] = 4
    assert comparable(first) != comparable(second)
