"""Lossless request deltas and strictly observed annotations; no evaluation truth imports."""

from __future__ import annotations

import copy
import json

from ..improved_io.protocol import annotate, hp, ident  # noqa: F401


def delta(before, after, path=()):
    """Typed paths avoid escaping collisions; equal-length arrays use index paths."""
    if isinstance(before, dict) and isinstance(after, dict):
        result = [{"op": "delete", "path": list(path + (k,))} for k in before if k not in after]
        for key, value in after.items():
            if key not in before:
                result.append({"op": "set", "path": list(path + (key,)), "value": value})
            else:
                result.extend(delta(before[key], value, path + (key,)))
        return result
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [
            op for i, (a, b) in enumerate(zip(before, after)) for op in delta(a, b, path + (i,))
        ]
    if type(before) is type(after) and before == after:
        return []
    return [{"op": "set", "path": list(path), "value": after}]


def apply_delta(before, operations):
    value = copy.deepcopy(before)
    for operation in operations:
        path = operation["path"]
        if not path:
            if operation["op"] != "set":
                raise ValueError("cannot delete root")
            value = copy.deepcopy(operation["value"])
            continue
        parent = value
        for key in path[:-1]:
            parent = parent[key]
        if operation["op"] == "delete":
            del parent[path[-1]]
        elif operation["op"] == "set":
            parent[path[-1]] = copy.deepcopy(operation["value"])
        else:
            raise ValueError("invalid delta operation")
    return value


def request_values(events, actor):
    values = []
    for event in events:
        for line in event["protocol"].splitlines():
            if line.startswith("|request|") and line[9:]:
                value = json.loads(line[9:])
                if value.get("side", {}).get("id", actor) != actor:
                    raise ValueError("foreign actor request")
                values.append(value)
    return values


def reduce_requests(events, actor):
    result = copy.deepcopy(events)
    previous = None
    index = 0
    for event in result:
        lines = []
        for line in event["protocol"].splitlines(keepends=True):
            body = line.rstrip("\r\n")
            ending = line[len(body) :]
            if body.startswith("|request|") and body[9:]:
                value = json.loads(body[9:])
                if value.get("side", {}).get("id", actor) != actor:
                    raise ValueError("foreign actor request")
                encoded = {"actor": actor, "index": index}
                if index == 0:
                    encoded["initial"] = value
                else:
                    encoded["changes"] = delta(previous, value)
                line = "|request_delta|" + json.dumps(encoded, separators=(",", ":")) + ending
                previous = value
                index += 1
            lines.append(line)
        event["protocol"] = "".join(lines)
    return result


def restore_requests(events, actor):
    result = copy.deepcopy(events)
    previous = None
    index = 0
    for event in result:
        lines = []
        for line in event["protocol"].splitlines(keepends=True):
            body = line.rstrip("\r\n")
            ending = line[len(body) :]
            if body.startswith("|request_delta|"):
                encoded = json.loads(body[len("|request_delta|") :])
                if encoded["actor"] != actor or encoded["index"] != index:
                    raise ValueError("request delta actor/order mismatch")
                value = (
                    encoded["initial"] if index == 0 else apply_delta(previous, encoded["changes"])
                )
                line = "|request|" + json.dumps(value, separators=(",", ":")) + ending
                previous = value
                index += 1
            lines.append(line)
        event["protocol"] = "".join(lines)
    return result


def canonical_events(events, actor):
    """Only JSON lexical whitespace is ignored; every other protocol byte is checked."""
    result = copy.deepcopy(events)
    request_values(events, actor)
    for event in result:
        lines = []
        for line in event["protocol"].splitlines(keepends=True):
            body = line.rstrip("\r\n")
            if body.startswith("|request|") and body[9:]:
                line = (
                    "|request|"
                    + json.dumps(json.loads(body[9:]), sort_keys=True)
                    + line[len(body) :]
                )
            lines.append(line)
        event["protocol"] = "".join(lines)
    return result


DELTA_FORMAT = {
    "protocol": "request_delta",
    "scope": "same actor only, in original protocol order",
    "initial": "first original request JSON value",
    "changes": (
        "apply to previous request; set replaces value, delete removes key; "
        "equal-length arrays use index changes; other arrays replace whole"
    ),
    "path": (
        "JSON object keys or array indices as a list; empty path replaces root; "
        "empty changes retain previous value"
    ),
}


def transform(context, condition):
    if condition not in ("H0", "H1", "H2", "H3"):
        raise ValueError("unknown condition")
    value = copy.deepcopy(context)
    if condition in ("H1", "H3"):
        value["harness_annotations"] = annotate(context)
    if condition in ("H2", "H3"):
        value["source_events"] = reduce_requests(
            context["source_events"], context["identity"]["actor_id"]
        )
        value["request_delta_format"] = DELTA_FORMAT
    return value


def verify_equivalence(original, value, condition):
    restored = copy.deepcopy(value)
    if condition in ("H1", "H3"):
        if restored.pop("harness_annotations") != annotate(original):
            raise ValueError("annotation mismatch")
    if condition in ("H2", "H3"):
        if restored.pop("request_delta_format") != DELTA_FORMAT:
            raise ValueError("delta format mismatch")
        restored["source_events"] = restore_requests(
            restored["source_events"], original["identity"]["actor_id"]
        )
    actor = original["identity"]["actor_id"]
    expected = copy.deepcopy(original)
    for value in (expected, restored):
        value["source_events"] = canonical_events(value["source_events"], actor)
    if restored != expected:
        raise ValueError("condition information mismatch")
