"""Delayed slot inference from public identity evidence, including fainted targets."""

import json
import subprocess
from pathlib import Path

import pytest

from integration.pokechamp.improved_io.protocol import observed_state


def events(raw):
    return [dict(event_seq=7, protocol=raw)]


def cast(target="p2: Target", spelling="move: Future Sight"):
    move = spelling.removeprefix("move: ")
    return f"|turn|4\n|move|p1a: Caster|{move}|{target}\n|-start|p1a: Caster|{spelling}"


@pytest.mark.parametrize("kind", ["switch", "drag", "replace", "faint"])
@pytest.mark.parametrize("slot", ["p2a", "p2b"])
@pytest.mark.parametrize("spelling", ["move: Future Sight", "move: Doom Desire", "Doom Desire"])
def test_public_identity_evidence(kind, slot, spelling):
    prefix = f"|{kind}|{slot}: Target|Mew|100/100\n"
    state = observed_state(events(prefix + cast(spelling=spelling)))
    (effect,) = state["pending_effects"]
    assert effect["target_slot"] == slot
    assert effect["observed_start_turn"] == 4
    assert effect["move_ref"] == dict(event=7, line=3)
    assert effect["start_ref"] == dict(event=7, line=4)
    assert effect["immediate_damage"] is False


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        "|switch|p1a: Target|Mew|100/100\n",
        "|switch|p2a: Other|Mew|100/100\n",
        "|faint|p2: Target\n",
        "|switch|p2a: Target|Mew|100/100\n|drag|p2b: Target|Mew|100/100\n",
    ],
)
def test_missing_or_ambiguous_evidence_remains_error(prefix):
    with pytest.raises(ValueError, match="unsupported delayed effect destination"):
        observed_state(events(prefix + cast()))


def test_explicit_slot_wins_and_future_evidence_cannot_resolve_past_move():
    prefix = "|switch|p2a: Target|Mew|100/100\n|replace|p2b: Target|Mew|100/100\n"
    assert (
        observed_state(events(prefix + cast("p2c: Target")))["pending_effects"][0]["target_slot"]
        == "p2c"
    )
    with pytest.raises(ValueError, match="unsupported delayed effect destination"):
        observed_state(events(cast() + "\n|faint|p2a: Target"))
    with pytest.raises(ValueError, match="unsupported delayed effect destination"):
        observed_state(
            events(
                "|turn|4\n|move|p1a: Caster|Future Sight|p2: Target\n"
                "|faint|p2a: Target\n|-start|p1a: Caster|move: Future Sight"
            )
        )


@pytest.mark.parametrize("spelling", ["move: Future Sight", "move: Doom Desire", "Doom Desire"])
def test_unlinked_duplicate_recast_expiry_and_end(spelling):
    start = f"|-start|p1a: Caster|{spelling}"
    unknown = observed_state(events(start))["pending_effects"][0]
    assert unknown["target_slot"] is None and unknown["move_ref"] is None
    assert unknown["observed_start_turn"] is None
    raw = cast("p2a: Target", spelling)
    with pytest.raises(ValueError, match="duplicate successful"):
        observed_state(events(raw + "\n" + start))
    failed = (
        raw
        + f"\n|turn|5\n|move|p1a: Caster|{spelling.removeprefix('move: ')}|p2a: Target"
        + "\n|-fail|p1a: Caster"
    )
    (pending,) = observed_state(events(failed))["pending_effects"]
    assert pending["observed_start_turn"] == 4
    assert observed_state(events(failed + "\n|turn|6"))["pending_effects"]
    expired = observed_state(events(failed + "\n|turn|7"))
    assert not expired["pending_effects"]
    assert expired["delayed_history"][0]["status"] == "expired_without_public_resolution"
    for end in ("|win|one", "|tie"):
        state = observed_state(events(raw + "\n" + end))
        assert not state["pending_effects"]
        assert state["delayed_history"][0]["status"] == "battle_ended"


def test_packet_boundaries_faint_and_replacement_keep_slot():
    packets = events("|switch|p2b: Target|Mew|100/100\n|faint|p2b: Target")
    packets += [dict(event_seq=20, protocol=cast())]
    state = observed_state(packets)
    assert state["pending_effects"][0]["current_occupant"] == "p2: Target"
    packets += [dict(event_seq=30, protocol="|switch|p2b: New|Blissey|100/100")]
    state = observed_state(packets)
    assert state["pending_effects"][0]["current_occupant"] == "p2: New"
    packets += [
        dict(event_seq=40, protocol="|turn|6\n|-end|p2b: New|move: Future Sight\n|-immune|p2b: New")
    ]
    state = observed_state(packets)
    assert not state["pending_effects"]
    assert state["delayed_history"][0]["resolution_target"] == "p2: New"
    assert state["delayed_history"][0]["resolution_turn"] == 6


def test_pinned_healing_wish_both_moves_both_sides():
    fixtures = json.loads(
        subprocess.check_output(
            ["node", str(Path(__file__).with_name("delayed_target.cjs"))], text=True
        )
    )
    assert len(fixtures) == 4
    for fixture in fixtures:
        target = fixture["target"]
        rows = fixture["rows"]
        assert f"|{fixture['move']}|{target}: Mew" in rows[0]["protocol"]
        for row in rows:
            state = observed_state(events(row["protocol"]))
            assert bool(state["pending_effects"]) == ("futuremove" in row["pending"])
            if state["pending_effects"]:
                (effect,) = state["pending_effects"]
                assert effect["target_slot"] == target + "a"
                assert effect["observed_start_turn"] == 1
                assert effect["current_occupant"] == target + ": " + row["occupant"]
            else:
                (effect,) = state["delayed_history"]
                assert effect["status"] == "resolution_observed"
                assert effect["resolution_turn"] == 3
                assert effect["resolution_target"] == target + ": Blissey"
        assert rows[-1]["hp"] < rows[-2]["hp"]
