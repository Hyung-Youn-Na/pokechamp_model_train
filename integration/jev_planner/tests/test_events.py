import json

import pytest

from integration.jev_planner.events import bounded_prefix, public_events, trigger_events


def test_exact_midframe_cutoff_excludes_private_control_and_future():
    lines = ["|init|battle", "|turn|1", "|faint|p2a: A", "|-terastallize|p1a: B|Fire",
             '|request|{"rqid":1,"side":{"id":"p1"}}', "|c|name|private",
             "|sentchoice|move 1", "|turn|2", "|faint|future"]
    prefix = [dict(event_seq=1, protocol="\n".join(lines)), dict(event_seq=2, protocol="|faint|further")]
    boundary = dict(protocol_event_seq=1, line_index=6)
    rows = public_events(prefix, boundary, actor="p1", battle="battle-test")
    assert [r["line_index"] for r in rows] == [0, 1, 2, 3]
    assert all(r["sequence"] == 1 for r in rows)
    assert "future" not in json.dumps(rows) and "private" not in json.dumps(rows)
    assert [e["kind"] for e in trigger_events(rows, decision_kind="forced_switch", rqid=1)] == ["faint", "tera", "forced_switch"]
    later = public_events(prefix, boundary, actor="p1", battle="battle-test",
                          since=dict(protocol_event_seq=1, line_index=2))
    assert [r["line_index"] for r in later] == [3]


@pytest.mark.parametrize("line,match", [
    ('|request|{"side":{"id":"p2"}}', "foreign private"),
    ("|split|p1", "unresolved split"), (">battle-other", "foreign battle"),
    ("|request|bad", "invalid private"),
])
def test_ambiguous_source_is_rejected(line, match):
    with pytest.raises(ValueError, match=match):
        public_events([dict(event_seq=1, protocol=line)],
                      dict(protocol_event_seq=1, line_index=0), actor="p1", battle="battle-test")


def test_same_event_coordinates_and_same_turn_request_events_have_distinct_identity():
    from integration.jev_planner.events import event_identity
    row = dict(sequence=2, line_index=3, turn=5, protocol="|faint|p2a: A")
    events = trigger_events([row], decision_kind="forced_switch", rqid=5)
    assert event_identity(events[0]) == ("faint", 2, 3)
    assert event_identity(events[1]) == ("forced_switch", 5)
    assert event_identity(trigger_events([], decision_kind="forced_switch", rqid=6)[0]) != event_identity(events[1])


@pytest.mark.parametrize("prefix,boundary", [
    ([], {"protocol_event_seq": 1, "line_index": 0}),
    ([{"event_seq": 1, "protocol": "|init|battle"}], {"protocol_event_seq": 1, "line_index": 1}),
    ([{"event_seq": 2, "protocol": "|init|battle"}], {"protocol_event_seq": 1, "line_index": 0}),
    ([{"event_seq": 1, "protocol": "|init|battle", "direction": "sent"}], {"protocol_event_seq": 1, "line_index": 0}),
    ([{"event_seq": 1, "protocol": "|init|battle", "actor": "p2"}], {"protocol_event_seq": 1, "line_index": 0}),
])
def test_missing_or_foreign_cutoff_fails(prefix, boundary):
    with pytest.raises(ValueError):
        bounded_prefix(prefix, boundary, actor="p1", battle="battle-test")
