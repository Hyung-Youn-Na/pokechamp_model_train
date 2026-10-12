"""Check recovery against the complete source, independently of forward pruning."""

from __future__ import annotations

import copy
import json

from . import exclusions, history


def _insert(root, path, value):
    if not path:
        raise ValueError("empty exclusion path")
    node = root
    for key in path[:-1]:
        if isinstance(node, list) and (type(key) is not int or key < 0 or key >= len(node)):
            raise ValueError("invalid excluded array location")
        node = node[key]
    if not isinstance(node, dict) or not isinstance(path[-1], str) or path[-1] in node:
        raise ValueError("excluded value overwrites retained information")
    node[path[-1]] = copy.deepcopy(value)


def restore_source(projection, ledger):
    """Insert only explicitly allowed exclusions; all other data comes from display."""
    value = copy.deepcopy(projection)
    seen = set()
    for record in ledger:
        if set(record) != {"path", "value", "reason"}:
            raise ValueError("invalid exclusion record")
        path = tuple(record["path"])
        if path in seen:
            raise ValueError("duplicate exclusion record")
        seen.add(path)
        raw = (
            len(path) > 5
            and path[0] == "recent_events"
            and type(path[1]) is int
            and path[2] == "protocol"
            and type(path[3]) is int
            and path[4] == "RequestJSON"
        )
        policy_path = tuple("*" if type(k) is int else k for k in (path[5:] if raw else path))
        rule = (exclusions.RAW if raw else exclusions.TOP).get(policy_path)
        if rule is None or rule != record["reason"]:
            raise ValueError("unclassified exclusion")
        if not raw:
            _insert(value, path, record["value"])
            continue
        if path[1] < 0 or path[3] < 0:
            raise ValueError("negative historical exclusion location")
        event = value["recent_events"][path[1]]
        lines = event["protocol"].splitlines(keepends=True)
        line = lines[path[3]]
        if not line.startswith("|request|"):
            raise ValueError("excluded request location is not a request")
        end = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        request = json.loads(line[9:])
        _insert(request, path[5:], record["value"])
        lines[path[3]] = (
            "|request|" + json.dumps(request, ensure_ascii=False, separators=(",", ":")) + end
        )
        event["protocol"] = "".join(lines)
    return value


def check_source(full, projection, ledger):
    restored = restore_source(projection, ledger)
    if not history.same_json(history.comparable(restored), history.comparable(full)):
        raise ValueError("complete original differs beyond explicit exclusions")
    return restored
