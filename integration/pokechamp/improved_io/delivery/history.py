"""Deterministic in-window request codec. No semantic protocol summarization."""

from __future__ import annotations

import copy
import json


def same_json(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same_json(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same_json(a, b) for a, b in zip(left, right))
    return left == right


def delta(previous, current):
    """Objects recurse; arrays/scalars replace atomically; deletion is not null."""
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return {"replace": copy.deepcopy(current)}
    return {
        "delete": [k for k in previous if k not in current],
        "set": {k: copy.deepcopy(v) for k, v in current.items() if k not in previous},
        "patch": {
            k: delta(previous[k], v)
            for k, v in current.items()
            if k in previous and not same_json(previous[k], v)
        },
    }


def apply_delta(previous, change):
    if not isinstance(change, dict):
        raise ValueError("request delta is not an object")
    if set(change) == {"replace"}:
        return copy.deepcopy(change["replace"])
    if set(change) != {"delete", "set", "patch"} or not isinstance(previous, dict):
        raise ValueError("invalid object delta")
    deleted, added, patched = change["delete"], change["set"], change["patch"]
    if (
        not isinstance(deleted, list)
        or not all(isinstance(k, str) for k in deleted)
        or len(deleted) != len(set(deleted))
        or not isinstance(added, dict)
        or not isinstance(patched, dict)
        or not set(deleted) <= previous.keys()
        or added.keys() & previous.keys()
        or not patched.keys() <= previous.keys()
        or set(deleted) & patched.keys()
    ):
        raise ValueError("conflicting or missing delta keys")
    result = {k: copy.deepcopy(v) for k, v in previous.items() if k not in deleted}
    result.update(copy.deepcopy(added))
    for key, patch in patched.items():
        result[key] = apply_delta(previous[key], patch)
    return result


def encode(events):
    output, previous, index = [], None, 0
    for event in events:
        lines = []
        for line in event["protocol"].splitlines(keepends=True):
            if not line.startswith("|request|") or not line[9:].strip():
                lines.append(line)
                continue
            end = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            request = json.loads(line[9:])
            entry = dict(request_index=index, eol=end)
            if index == 0:
                entry["request_base"] = request
            else:
                entry.update(base_request=index - 1, request_delta=delta(previous, request))
            lines.append(entry)
            previous, index = request, index + 1
        output.append({**{k: v for k, v in event.items() if k != "protocol"}, "lines": lines})
    return output


def decode(events):
    output, previous, index = [], None, 0
    for event in events:
        if "protocol" in event or "lines" not in event or not isinstance(event["lines"], list):
            raise ValueError("invalid encoded event")
        lines = []
        for line in event["lines"]:
            if isinstance(line, str):
                if line.startswith("|request|") and line[9:].strip():
                    raise ValueError("unencoded request in delta history")
                lines.append(line)
                continue
            keys = {"request_index", "eol"} | (
                {"request_base"} if index == 0 else {"base_request", "request_delta"}
            )
            if (
                not isinstance(line, dict)
                or set(line) != keys
                or type(line["request_index"]) is not int
                or line["request_index"] != index
                or line["eol"] not in ("", "\n", "\r\n")
            ):
                raise ValueError("invalid request index or history record")
            if index == 0:
                request = copy.deepcopy(line["request_base"])
            else:
                if type(line["base_request"]) is not int or line["base_request"] != index - 1:
                    raise ValueError("missing, forward or foreign request reference")
                request = apply_delta(previous, line["request_delta"])
            lines.append(
                "|request|"
                + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
                + line["eol"]
            )
            previous, index = request, index + 1
        output.append(
            {**{k: v for k, v in event.items() if k != "lines"}, "protocol": "".join(lines)}
        )
    return output


def comparable(value):
    """Only JSON whitespace/key order in request rows is presentation, not evidence."""
    value = copy.deepcopy(value)
    for event in value["recent_events"]:
        lines = []
        for line in event["protocol"].splitlines(keepends=True):
            if line.startswith("|request|") and line[9:].strip():
                end = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                line = (
                    "|request|"
                    + json.dumps(
                        json.loads(line[9:]),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + end
                )
            lines.append(line)
        event["protocol"] = "".join(lines)
    return value
