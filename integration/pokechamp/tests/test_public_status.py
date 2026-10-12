"""Independent source-holder and fainted effective-type regressions from EP-051."""

import copy
import json
import subprocess
from pathlib import Path

import pytest

from integration.pokechamp.improved_io.calculations import compute
from integration.pokechamp.improved_io.calculator import Calculator
from integration.pokechamp.improved_io.gate import validate_input
from integration.pokechamp.improved_io.state import public_revelations
from integration.pokechamp.tests.test_calculator_input_audit import observed


@pytest.mark.parametrize("role,other", [("p1", "p2"), ("p2", "p1")])
def test_status_source_uses_explicit_holder_without_inference(role, other):
    prefix = [
        dict(
            event_seq=1,
            protocol=f"|-status|{role}a: Contact|par|[from] ability: Static|[of] {other}a: Holder",
        )
    ]
    facts = public_revelations(prefix)
    assert facts[other + ": Holder"]["ability"] == "static"
    assert "ability" not in facts[role + ": Contact"]
    for suffix in ("", "|[of] p3a: Unknown", "|[of] invalid"):
        value = public_revelations(
            [
                dict(
                    event_seq=1,
                    protocol=f"|-status|{role}a: Contact|par|[from] ability: Static"
                    + suffix,
                )
            ]
        )
        assert not any("ability" in p for p in value.values())
    future = prefix + [
        dict(event_seq=99, protocol=f"|-ability|{other}a: Holder|Pressure")
    ]
    assert public_revelations([e for e in future if e["event_seq"] < 99]) == facts
    switched = prefix + [
        dict(
            event_seq=2,
            protocol=f"|switch|{other}a: Holder|Zapdos|100/100\n|switch|{other}a: Bench|Mew|100/100",
        )
    ]
    assert public_revelations(switched)[other + ": Holder"]["ability"] == "static"


def test_static_and_faint_against_pinned_showdown():
    snapshots = json.loads(
        subprocess.run(
            ["node", str(Path(__file__).with_name("public_status.cjs"))],
            text=True,
            capture_output=True,
            check=True,
        ).stdout
    )
    assert snapshots[0]["oracle"][0][0]["status"] == "par"
    with Calculator() as calc:
        for snap in snapshots:
            for i, actor in enumerate(snap["actors"]):
                value = observed({"actor": copy.deepcopy(actor)}, rolling_only=True)
                value["condition_id"] = "B"
                mons = value["current_observation"]["opponent_confirmed"]
                for mon in mons:
                    truth = next(
                        m for m in snap["oracle"][1 - i] if m["ident"] == mon["ident"]
                    )
                    assert mon["effective_types"] == [s.upper() for s in truth["types"]]
                    if mon["ident"] == "p2: StaticHolder":
                        assert mon["ability"] == "static"
                        assert mon["ability_known"] is True
                if i == 0 and snap["phase"] != "fainted_and_switched":
                    assert {g["ability"] for g in value["opponent_hypotheses"]} == {
                        "static"
                    }
                value["calculation_bundle"] = compute(value, calc)
                validate_input(value)
