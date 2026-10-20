"""Actor-local public rows and replan events at an exact request cutoff."""
from __future__ import annotations

import copy
import json
import re

from integration.jev_eval.turn_logs import public_rows


def coordinates(boundary):
    if not isinstance(boundary, dict):
        raise ValueError("a public protocol boundary is required")
    sequence, line = boundary.get("protocol_event_seq"), boundary.get("line_index")
    if type(sequence) is not int or sequence < 1 or type(line) is not int or line < 0:
        raise ValueError("invalid public protocol boundary")
    return sequence, line


def bounded_prefix(prefix, boundary, *, actor, battle):
    """Copy and clip the received stream, rejecting ambiguous/foreign sources."""
    cutoff_sequence, cutoff_line = coordinates(boundary)
    if not isinstance(prefix, list) or not prefix:
        raise ValueError("the actor's received protocol prefix is required")
    result, previous = [], 0
    for event in prefix:
        if not isinstance(event, dict):
            raise ValueError("invalid protocol frame")
        sequence = event.get("event_seq", event.get("sequence"))
        if type(sequence) is not int or sequence <= previous:
            raise ValueError("unordered protocol prefix")
        previous = sequence
        if sequence > cutoff_sequence:
            continue
        if event.get("line_offset", 0):
            raise ValueError("incomplete protocol prefix")
        if event.get("actor", actor) != actor or event.get("battle", battle) != battle:
            raise ValueError("foreign actor or battle in protocol prefix")
        if event.get("direction", "received") not in ("received", "receive", "inbound", "incoming", "recv"):
            raise ValueError("protocol prefix must contain received frames")
        protocol = event.get("protocol")
        if not isinstance(protocol, str):
            raise ValueError("invalid protocol text")
        lines = protocol.splitlines()
        if sequence == cutoff_sequence:
            if cutoff_line >= len(lines):
                raise ValueError("missing protocol cutoff row")
            lines = lines[:cutoff_line + 1]
        for line in lines:
            if line.startswith(">") and line[1:] != battle:
                raise ValueError("foreign battle room in protocol prefix")
            if line.startswith("|split|"):
                raise ValueError("unresolved split in protocol prefix")
            if line.startswith("|request|") and line[len("|request|"):]:
                try:
                    request = json.loads(line[len("|request|"):])
                except ValueError as error:
                    raise ValueError("invalid private request in protocol prefix") from error
                if (not isinstance(request, dict)
                        or request.get("side", {}).get("id", actor) != actor):
                    raise ValueError("foreign private request in protocol prefix")
        result.append(dict(event_seq=sequence, protocol="\n".join(lines)))
    if not result or result[-1]["event_seq"] != cutoff_sequence:
        raise ValueError("missing protocol cutoff frame")
    return result


def public_events(prefix, boundary, *, actor, battle, since=None):
    """Private request/chat/control rows never enter planner messages."""
    frozen = bounded_prefix(prefix, boundary, actor=actor, battle=battle)
    frames = [dict(type="protocol", username=actor, sequence=e["event_seq"],
                   event_seq=e["event_seq"], protocol=e["protocol"]) for e in frozen]
    rows, _, _, _ = public_rows(frames, actor)
    cutoff = coordinates(since) if since is not None else None
    return [copy.deepcopy(row) for row in rows
            if cutoff is None or (row["sequence"], row["line_index"]) > cutoff]


def trigger_events(rows, *, decision_kind, rqid,
                   enabled=('faint', 'tera', 'forced_switch')):
    result = []
    for row in rows:
        parts = row["protocol"].split("|")
        command = parts[1]
        kind = {"faint": "faint", "-terastallize": "tera"}.get(command)
        # Protocol identifiers carry a position letter only while active.
        # Use the event target, never a final-state matchup comparison: a
        # switch out and back in between decisions must remain observable.
        active_target = len(parts) > 2 and re.match(r"^p[1-4][a-c]: ", parts[2])
        if active_target and command in ("switch", "drag", "replace"):
            if "active_change" in enabled:
                kind = "active_change"
        if active_target and command in ("detailschange", "-formechange", "-transform"):
            if "form_change" in enabled:
                kind = "form_change"
        if kind is not None:
            result.append(dict(kind=kind, sequence=row["sequence"],
                               line_index=row["line_index"], turn=row["turn"]))
    if decision_kind == "forced_switch":
        result.append(dict(kind="forced_switch", rqid=rqid))
    return result


def event_identity(event):
    if event["kind"] == "forced_switch":
        return ("forced_switch", event["rqid"])
    return event["kind"], event["sequence"], event["line_index"]
