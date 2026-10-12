"""Court Change execution notices, public side history, and pinned Gen9 oracle."""

import copy
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from poke_env.environment.effect import Effect
from poke_env.environment.side_condition import SideCondition

from integration.pokechamp.improved_io.calculations import check_effects, compute
from integration.pokechamp.improved_io.calculator import CalculationError, Calculator
from integration.pokechamp.improved_io.gate import validate_input
from integration.pokechamp.improved_io.live_delivery import build, validate
from integration.pokechamp.improved_io.protocol import (
    court_change_notifications,
    live_effects,
    observed_state,
)
from integration.pokechamp.tests.test_calculator_input_audit import observed


def events(text):
    return [dict(event_seq=7, protocol=text)]


def effect(text, key="p1: Court"):
    mon = SimpleNamespace(effects={Effect.COURT_CHANGE: 0}, fainted=False)
    result = live_effects(
        mon, key, {}, court_change=court_change_notifications(events(text))
    )
    assert mon.effects == {Effect.COURT_CHANGE: 0}
    return result


def test_execution_notice_only_and_no_allowlist_expansion():
    success = "|-activate|p1a: Court|move: Court Change"
    assert effect(success) == {}
    for prefix in (
        "",
        "|move|p1a: Court|Court Change|p1a: Court",
        "|-activate|p2a: Court|move: Court Change",
        "|-activate|p1a: Other|move: Court Change",
        "|-start|p1a: Court|move: Court Change",
    ):
        with pytest.raises(CalculationError, match="COURT_CHANGE"):
            check_effects({"effects": effect(prefix)})
    with pytest.raises(CalculationError, match="PROTECT"):
        check_effects({"effects": {"PROTECT": 0}})
    assert effect(success + "\n|replace|p1a: Other|Zoroark|100/100") == {
        "COURT_CHANGE": 0
    }


def test_swaps_preserve_original_installation_and_only_pinned_conditions():
    start = "|start\n|turn|1\n|-sidestart|p1: One|Spikes\n|-sidestart|p1: One|Spikes\n|-sidestart|p2: Two|Spikes\n|-sidestart|p1: One|Reflect\n|-sidestart|p1: One|Future Sight"
    old = observed_state(events(start))["sides"]
    new = observed_state(events(start + "\n|turn|9\n|-swapsideconditions"))["sides"]
    assert new["p2"]["Spikes"] == old["p1"]["Spikes"]
    assert new["p1"]["Spikes"] == old["p2"]["Spikes"]
    assert new["p2"]["Reflect"] == old["p1"]["Reflect"]
    assert new["p1"]["Future Sight"] == old["p1"]["Future Sight"]
    assert (
        observed_state(events(start + "\n|-swapsideconditions\n|-swapsideconditions"))[
            "sides"
        ]
        == old
    )
    ended = observed_state(
        events(start + "\n|-swapsideconditions\n|-sideend|p2: Two|Spikes")
    )
    assert "Spikes" not in ended["sides"]["p2"]
    assert observed_state(events("|turn|19\n|-swapsideconditions"))["sides"] == {
        "p1": {},
        "p2": {},
    }
    assert (
        observed_state(events("|-sidestart|p1: One|Reflect\n|-swapsideconditions"))[
            "sides"
        ]["p2"]["Reflect"]["observed_start_turn"]
        is None
    )


def test_packet_splits_and_full_prefix_outside_recent_window():
    text = "|start\n|turn|1\n|-sidestart|p1: One|Stealth Rock\n|-swapsideconditions\n|-activate|p1a: Court|move: Court Change\n|turn|30"
    packets = [
        dict(event_seq=i, protocol=line) for i, line in enumerate(text.splitlines(), 1)
    ]
    timing = observed_state(packets)
    assert timing["sides"]["p2"]["Stealth Rock"]["start_ref"] == {"event": 3, "line": 1}
    assert court_change_notifications(packets) == {"p1: Court": {"event": 5, "line": 1}}
    # Callers own cutoff selection; future changes never enter this prefix.
    for future in ("|-swapsideconditions", "|-sideend|p2: Two|Stealth Rock"):
        all_events = packets + [dict(event_seq=99, protocol=future)]
        assert observed_state([e for e in all_events if e["event_seq"] < 7]) == timing


@pytest.fixture(scope="module")
def simulator():
    return json.loads(
        subprocess.run(
            ["node", str(Path(__file__).with_name("court_change.cjs"))],
            text=True,
            capture_output=True,
            check=True,
        ).stdout
    )


@pytest.mark.parametrize(
    "name",
    ["one_side", "layers", "screens", "empty", "repeat", "removal", "unsupported"],
)
def test_independent_side_truth_and_both_actor_inputs(simulator, name):
    case = next(c for c in simulator if c["name"] == name)
    with Calculator() as calc:
        for snap in case["snapshots"]:
            for actor_index, actor in enumerate(snap["actors"]):
                # Mid-switch request is intentionally stale; only protocol history
                # is checked there. Stable requests below drive full B normalization.
                state = observed_state(events(actor["protocol"]))
                for i, side in enumerate(("p1", "p2")):
                    public = {
                        re.sub("[^a-z0-9]", "", k.lower()): v
                        for k, v in state["sides"].get(side, {}).items()
                    }
                    assert set(public) == set(snap["sides"][i])
                    for k, v in public.items():
                        assert v.get("layers", 1) == snap["sides"][i][k]["layers"]
                if snap["phase"].startswith("entry_"):
                    continue
                fixture = {"actor": copy.deepcopy(actor)}
                value = observed(fixture, rolling_only=True)
                value["condition_id"] = "B"
                obs = value["current_observation"]
                for i, field in (
                    (actor_index, "self_side_conditions"),
                    (1 - actor_index, "opponent_side_conditions"),
                ):
                    expected = {
                        SideCondition.from_showdown_message(k).name
                        for k in state["sides"].get("p" + str(i + 1), {})
                    }
                    assert set(obs[field]) == expected
                for p in obs["self_team"] + obs["opponent_confirmed"]:
                    assert "COURT_CHANGE" not in p["effects"]
                if name == "unsupported":
                    with pytest.raises(
                        CalculationError, match="unsupported side effect"
                    ):
                        compute(value, calc)
                    continue
                value["calculation_bundle"] = compute(value, calc)
                validate_input(value)
                delivery = build(value, version="v1.3.0")
                validate(
                    value,
                    delivery,
                    delivery.system_prompt,
                    delivery.user_json,
                    version="v1.3.0",
                )


def test_independent_damage_screens_and_entry_hazard_hp_status(simulator):
    from integration.pokechamp.improved_io.calculations import field_for, own_spec
    from integration.pokechamp.tests.test_improved_io import scenario

    with Calculator() as calc:
        for case in simulator:
            if case["name"] == "unsupported":
                continue
            for snap in case["snapshots"]:
                if snap["phase"].startswith("entry_"):
                    continue
                values = [observed({"actor": copy.deepcopy(a)}) for a in snap["actors"]]
                active = [
                    next(
                        m for m in v["current_observation"]["self_team"] if m["active"]
                    )
                    for v in values
                ]
                for i in range(2):
                    request = scenario(
                        attacker=own_spec(active[i]),
                        defender=own_spec(active[1 - i]),
                        move="Tackle",
                        field=field_for(values[i]["current_observation"]),
                    )
                    actual = calc.calculate(values[i]["identity"], [request])[
                        "entries"
                    ][0]
                    assert actual["damage_rolls"] == snap["damage"][i]
            before = next(
                s
                for s in reversed(case["snapshots"])
                if s["phase"] in ("swapped", "swapped_twice")
            )
            for i, side in enumerate(("p1", "p2")):
                entry = next(
                    (s for s in case["snapshots"] if s["phase"] == "entry_" + side),
                    None,
                )
                if entry is None:
                    continue
                value = observed({"actor": copy.deepcopy(before["actors"][i])})
                other = observed({"actor": copy.deepcopy(before["actors"][1 - i])})
                bench = next(
                    m
                    for m in value["current_observation"]["self_team"]
                    if not m["active"]
                )
                attacker = next(
                    m for m in other["current_observation"]["self_team"] if m["active"]
                )
                request = scenario(
                    attacker=own_spec(attacker),
                    defender=own_spec(bench),
                    move="Tackle",
                    field=field_for(other["current_observation"]),
                )
                actual = calc.calculate(value["identity"], [request])["entries"][0]
                projected = actual["scenario_state"]["entry"][0]
                assert projected["hp_after_hazards"] == entry["oracle"][i]["hp"]
                assert projected["status_after_hazards"] == entry["oracle"][i]["status"]
                assert actual["conditional_order"]["defender_speed"] == entry["oracle"][i]["speed"]
                # Blissey enters after the other side's switch in some phases;
                # only compare damage when the same attacker is still active.
                if entry["oracle"][1 - i]["active"] == attacker["ident"].split(": ")[1]:
                    assert actual["damage_rolls"] == entry["damage"][1 - i]
