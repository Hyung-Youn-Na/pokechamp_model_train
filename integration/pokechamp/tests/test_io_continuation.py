"""Continuation retains summary interval semantics and prior sealed evidence."""

import copy
import json
import logging
import subprocess
from pathlib import Path

import pytest

from integration.pokechamp.improved_io.memory import summary_context, summary_window
from integration.pokechamp.summary_diagnostics.oracle import verify_annotations


def test_later_summary_keeps_boundary_turn_hp_and_only_current_rows():
    events = [
        {
            "event_seq": 1,
            "protocol": "|start\n|turn|9\n"
            "|switch|p2a: Fox|Ninetales, M|349/349\n"
            "|move|p1a: King|Kowtow Cleave|p2a: Fox\n"
            "|-damage|p2a: Fox|64/349\n|turn|10",
        },
        {
            "event_seq": 4,
            "showdown_turn": 999,
            "protocol": "|move|p1a: King|Kowtow Cleave|p2a: Fox\n"
            "|-damage|p2a: Fox|0 fnt\n|faint|p2a: Fox",
        },
    ]
    value = dict(
        identity=dict(battle_id="b", actor_id="p2"),
        current_observation=dict(protocol_state=dict(weather={})),
    )
    template = summary_context(value, events)
    before = copy.deepcopy(template)
    replay = summary_window(template, 3, previous="earlier summary [event:1]")
    live = summary_context(
        value,
        events[1:],
        source_event_ids=[1, 4],
        previous="earlier summary [event:1]",
        observed_protocol=events,
    )
    assert replay == live
    assert template == before
    assert replay["source_events"] == events[1:]
    assert replay["source_event_ids"] == [1, 4]
    rows = replay["harness_annotations"]["event_annotations"]
    assert {r["ref"]["event"] for r in rows} == {4}
    assert {r["turn"] for r in rows} == {10}
    damage = next(r for r in rows if r["kind"] == "-damage")
    assert damage["hp_before"]["current"] == 64
    assert damage["hp_after"]["maximum"] == 349
    assert damage["observed_hp_decrease"] == 64
    assert damage["hp_before_ref"] == {"event": 1, "line": 5}
    assert damage["observed_details"] == "Ninetales, M"
    reference = dict(identity=value["identity"], source_events=events)
    assert verify_annotations(replay, reference)
    damage["turn"] = 999
    with pytest.raises(ValueError, match="occurrence turn"):
        verify_annotations(replay, reference)


def test_first_summary_unchanged_and_future_prefix_is_not_reused():
    value = dict(identity=dict(battle_id="b", actor_id="p1"), current_observation={})
    events = [{"event_seq": 1, "protocol": "|start\n|turn|1"}]
    template = summary_context(value, events)
    assert summary_window(template, 0) == template
    assert summary_window(template, 2)["harness_annotations"]["event_annotations"] == []


def test_orb_activation_removal_and_switch_against_pinned_showdown():
    from poke_env.environment.battle import Battle

    from integration.pokechamp.battle_adapter import install_identity_adapter
    from integration.pokechamp.improved_io.state import public_mon, public_revelations
    from integration.pokechamp.summary_diagnostics.oracle import raw_index, verify_public_items

    rows = json.loads(
        subprocess.check_output(
            ["node", str(Path(__file__).with_name("public_items.cjs"))],
            text=True,
        )
    )
    install_identity_adapter()
    for row in rows:
        for phase in ("activated", "afterRemovalAndSwitch"):
            battle = Battle("battle-gen9ou-orb", "observer", logging.getLogger("test"), gen=9)
            battle._format = "gen9ou"
            for line in row[phase].splitlines():
                parts = line.split("|")
                if len(parts) > 1 and parts[1] not in ("", "t:", "split"):
                    battle.parse_message(parts)
            events = [{"event_seq": 1, "protocol": row[phase]}]
            ident = "p2: " + row["species"]
            raw_item = battle.opponent_active_pokemon.item
            mon = public_mon(battle.opponent_active_pokemon, public_revelations(events)[ident])
            mon["ident"] = ident
            if phase == "activated":
                assert raw_item == "unknown_item"
                assert mon["item"] == (row["itemAfterActivation"] or "unknown_item")
            elif row["item"]:
                assert mon["item"] is None
                assert row["itemAfterRemoval"] == ""
            else:
                assert mon["item"] == "unknown_item"
            context = dict(current_observation=dict(opponent_confirmed=[mon]))
            reference = dict(identity=dict(battle_id="b", actor_id="p1"), source_events=events)
            verify_public_items(context, raw_index(reference))
            if row["item"] and phase == "activated":
                mon["item"] = "unknown_item"
                with pytest.raises(ValueError, match="public item"):
                    verify_public_items(context, raw_index(reference))


def test_public_orb_does_not_override_transfer_or_foreign_attribution():
    from integration.pokechamp.improved_io.state import public_revelations

    def reveal(text):
        return public_revelations([{"event_seq": 1, "protocol": text}])["p2: Gliscor"]

    base = "|-status|p2a: Gliscor|tox|[from] item: Toxic Orb"
    assert "item" not in reveal(base + "|[of] p1a: Mew")
    assert "item" not in reveal("|-status|p2a: Gliscor|tox")
    assert reveal(base + "\n|-item|p2a: Gliscor|Choice Scarf|[from] move: Trick")["item"] == (
        "choicescarf"
    )
    assert reveal(base + "\n|-enditem|p2a: Gliscor|Toxic Orb")["item"] is None
