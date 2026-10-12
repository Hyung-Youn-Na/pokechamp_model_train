"""Public Protect boundaries and independent pinned simulator volatile truth."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from poke_env.environment.effect import Effect

from integration.pokechamp.improved_io.calculations import check_effects
from integration.pokechamp.improved_io.calculator import CalculationError
from integration.pokechamp.improved_io.protocol import live_effects, protect_lifetimes


def events(text):
    return [dict(event_seq=7, protocol=text, showdown_turn=999)]


def project(text, raw=None, key="p1: Shield"):
    mon = SimpleNamespace(
        effects={Effect.PROTECT: 0} if raw is None else raw, fainted=False
    )
    before = dict(mon.effects)
    result = live_effects(mon, key, {}, protect_lifetimes(events(text)))
    assert mon.effects == before
    return result


@pytest.mark.parametrize("signal", ["-singleturn", "-activate"])
@pytest.mark.parametrize("spelling", ["Protect", "move: Protect"])
@pytest.mark.parametrize(
    "end",
    [
        "|upkeep",
        "|turn|2",
        "|faint|p1a: Shield",
        "|-end|p1a: Shield|Protect",
        "|-end|p1a: Shield|move: Protect",
        "|switch|p1a: Bench|Chansey|100/100",
        "|drag|p1a: Bench|Chansey|100/100",
        "|-activate|p1a: Shield|move: Feint",
        "|-activate|p1a: Shield|move: Hyperspace Fury|[broken]",
    ],
)
def test_expiration_requires_later_evidence(signal, spelling, end):
    prefix = f"|turn|1\n|{signal}|p1a: Shield|{spelling}"
    assert project(prefix) == {"PROTECT": 0}
    assert project(prefix, {}) == {"PROTECT": 0}
    assert project(prefix + "\n" + end) == {}
    life = protect_lifetimes(events(prefix + "\n" + end))["current"]["p1: Shield"]
    assert life["start_ref"] == {"event": 7, "line": 2}
    assert life["end_ref"] == {"event": 7, "line": 3}


@pytest.mark.parametrize(
    "suffix",
    [
        "",
        "|turn|1",
        '|request|{"forceSwitch":[true]}',
        "|switch|p2a: Bench|Chansey|100/100",
        "|faint|p2a: Shield",
        "|-end|p2a: Shield|Protect",
        "|-weather|Snow|[upkeep]",
        "|-damage|p1a: Shield|99/100|[from] psn",
    ],
)
def test_same_turn_keeps_guard(suffix):
    value = project("|turn|1\n|-singleturn|p1a: Shield|Protect\n" + suffix)
    with pytest.raises(CalculationError, match="PROTECT"):
        check_effects({"effects": value})


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        "|turn|25",
        "|upkeep\n|turn|25",
        "|move|p1a: Shield|Protect|p1a: Shield\n|-fail|p1a: Shield\n|upkeep",
        "|-singleturn|p2a: Shield|Protect\n|upkeep",
        "|-singleturn|p1a: Other|Protect\n|turn|2",
    ],
)
def test_missing_occurrence_retains_parser_effect(prefix):
    assert project(prefix) == {"PROTECT": 0}


def test_reactivation_packet_order_and_other_effects():
    prefix = "|turn|2\n|-singleturn|p1a: Shield|Protect\n|upkeep\n|turn|3"
    assert project(prefix) == {}
    prefix += "\n|-singleturn|p1a: Shield|move: Protect"
    assert project(prefix) == {"PROTECT": 0}
    prefix += "\n|-end|p1a: Shield|Protect\n|-singleturn|p1a: Shield|Protect"
    assert project(prefix) == {"PROTECT": 0}
    assert len(protect_lifetimes(events(prefix))["history"]) == 3
    raw = {Effect.PROTECT: 42, Effect.ROOST: 0, Effect.SUBSTITUTE: 1}
    assert project(prefix + "\n|upkeep", raw) == {"ROOST": 0, "SUBSTITUTE": 1}
    assert project("|-activate|p1a: Shield|move: Protect\n|turn|25") == {}


def test_conflicting_identity_and_order():
    prefix = (
        "|switch|p1a: Other|Mew|100/100\n|turn|1\n"
        "|-singleturn|p1a: Shield|Protect\n|upkeep\n|turn|2"
    )
    assert project(prefix) == {"PROTECT": 0}
    with pytest.raises(ValueError, match="backwards"):
        project("|turn|2\n|-singleturn|p1a: Shield|Protect\n|turn|1")
    with pytest.raises(ValueError, match="event order"):
        protect_lifetimes(events("|turn|1") + events("|upkeep"))
    prefix = (
        "|turn|1\n|-singleturn|p1a: Shield|Protect\n"
        "|replace|p1a: Other|Zoroark|100/100\n|upkeep"
    )
    assert project(prefix) == {"PROTECT": 0}


@pytest.fixture(scope="module")
def simulator():
    return json.loads(
        subprocess.check_output(
            ["node", str(Path(__file__).with_name("protect_lifecycle.cjs"))], text=True
        )
    )


@pytest.mark.parametrize(
    "mode", ["success", "no_block", "consecutive", "feint", "pivot", "switch", "faint"]
)
def test_simulator_volatile_truth(simulator, mode):
    fixture = next(f for f in simulator if f["mode"] == mode)
    for snapshot in fixture["rows"]:
        for truth in snapshot["oracle"]:
            projected = project(snapshot["public_protocol"], {}, truth["ident"])
            assert ("PROTECT" in projected) == truth["protect"], (
                mode,
                snapshot["phase"],
            )
    rows = fixture["rows"]
    if mode == "success":
        assert rows[1]["oracle"][0]["hp"] == rows[2]["oracle"][0]["hp"]
        assert rows[-1]["oracle"][0]["hp"] < rows[2]["oracle"][0]["hp"]
    if mode == "consecutive":
        assert "|-fail|p1a: Shield" in rows[-1]["public_protocol"]
        assert [r["oracle"][0]["protect"] for r in rows if r["phase"] == "move"][
            8:12
        ] == [True] * 4
    if mode == "pivot":
        mid = next(r for r in rows if r["phase"] == "midturn_request")
        assert mid["request_state"] == "switch" and mid["oracle"][0]["protect"]
    if mode == "feint":
        assert "|-activate|p1a: Shield|move: Feint" in rows[2]["public_protocol"]
        assert rows[2]["oracle"][0]["hp"] < rows[1]["oracle"][0]["hp"]


def test_separate_packets_and_reentry_do_not_transfer_lifetimes():
    packets = [
        dict(
            event_seq=2,
            protocol="|turn|3\n|-singleturn|p1a: Shield|Protect",
            showdown_turn=99,
        ),
        dict(
            event_seq=8,
            protocol="|upkeep\n|turn|4\n|-singleturn|p2a: Shield|Protect",
            showdown_turn=1,
        ),
    ]
    lifetimes = protect_lifetimes(packets)
    assert lifetimes["current"]["p1: Shield"]["status"] == "expired"
    assert lifetimes["current"]["p2: Shield"]["status"] == "active"
    assert lifetimes["current"]["p1: Shield"]["end_ref"] == {"event": 8, "line": 1}
    assert (
        project(
            "|turn|1\n|-singleturn|p1a: Shield|Protect\n"
            "|switch|p1a: Bench|Chansey|100/100\n"
            "|switch|p1a: Shield|Mew|100/100"
        )
        == {}
    )


def test_unrelated_broken_tag_is_not_protect_removal():
    assert project(
        "|turn|1\n|-singleturn|p1a: Shield|Protect\n"
        "|-activate|p1a: Shield|ability: Other|[broken]"
    ) == {"PROTECT": 0}


@pytest.mark.parametrize(
    "actor,decision,group", [("p1", 30, "self_team"), ("p2", 29, "opponent_confirmed")]
)
def test_ex036_full_prefix_normalizes_both_sides_without_recent_history(
    actor, decision, group
):
    from integration.pokechamp.battle_adapter import install_identity_adapter
    from integration.pokechamp.diagnostics.protect_expiry import BUNDLES, context
    from integration.pokechamp.improved_io.state import normalize

    install_identity_adapter()
    params = context(BUNDLES / ("b01-r2-s0-a1-" + actor), decision)
    params["protocol"] = []
    value, _ = normalize(**params)
    (gliscor,) = [
        m for m in value["current_observation"][group] if m["species"] == "gliscor"
    ]
    assert gliscor["parser_effects"]["PROTECT"] == 0
    assert "PROTECT" not in gliscor["effects"]
    assert "protect" not in value["current_observation"]["protocol_state"]


def test_ex036_fixed_scene_reaches_production_backend_local_transport():
    from integration.pokechamp.battle_adapter import install_identity_adapter
    from integration.pokechamp.diagnostics.protect_expiry import (
        BUNDLES,
        context,
        fake_wire,
    )
    from integration.pokechamp.improved_io.calculations import compute
    from integration.pokechamp.improved_io.calculator import Calculator
    from integration.pokechamp.improved_io.gate import validate_input
    from integration.pokechamp.improved_io.state import normalize

    install_identity_adapter()
    value, _ = normalize(**context(BUNDLES / "b01-r2-s0-a1-p2", 29))
    value["condition_id"] = "B"
    with Calculator() as calc:
        value["calculation_bundle"] = compute(value, calc)
        validate_input(value)
    wire = fake_wire(value)
    assert wire["calls"] == 1 and wire["provider_calls"] == 0
    assert json.loads(wire["messages"][-1]["content"]) == value
