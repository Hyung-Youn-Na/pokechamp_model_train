"""Closed B1 exclusions; all other fields remain visible and recoverable."""

from __future__ import annotations

import copy
import json

from .. import battle_prompts

# These are schema paths, not suffix matches: similarly named tactical fields stay.
TOP = {
    ("condition_id",): "experiment condition; B only",
    ("lesson_memory",): "verified empty cross-battle memory",
    ("battle_summary",): "verified absent battle summary",
    ("identity", "state_id"): "validated original state digest",
    ("calculation_bundle", "elapsed_ms"): "calculation timing",
    ("calculation_bundle", "engine_patch"): "validated calculator patch provenance",
    ("calculation_bundle", "runtime_patch"): "validated runtime patch provenance",
    ("calculation_bundle", "request_sha256"): "validated calculator request digest",
    ("calculation_bundle", "bundle_sha256"): "validated calculator bundle digest",
    ("calculation_bundle", "identity", "state_id"): "validated original state digest",
    ("current_observation", "self_team", "*", "pokeball"): "ball cosmetic",
}
LEGACY = ("canMegaEvo", "canUltraBurst", "canDynamax", "canZMove", "maxMoves")
RAW = {
    ("side", "pokemon", "*", "pokeball"): "ball cosmetic",
    ("ally",): "unused ally request in singles",
    **{("active", "*", name): "unused generation mechanic" for name in LEGACY},
}
SCHEMA_REMOVALS = {
    "identity": ("state_id",),
    "self_mon": ("pokeball",),
    "request_mon": ("pokeball",),
    "RequestJSON": ("ally",),
    "move_request": LEGACY,
    "calculation": (
        "elapsed_ms",
        "engine_patch",
        "runtime_patch",
        "request_sha256",
        "bundle_sha256",
    ),
}


def _prune(value, rules, ledger, path=(), prefix=()):
    if isinstance(value, list):
        return [_prune(v, rules, ledger, path + ("*",), prefix + (i,)) for i, v in enumerate(value)]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, child in value.items():
        rule = rules.get(path + (key,))
        if rule:
            if rule.startswith("unused") and child not in (False, None, [], {}):
                raise ValueError("active out-of-scope mechanic or ally request")
            ledger.append(dict(path=list(prefix + (key,)), value=copy.deepcopy(child), reason=rule))
        else:
            result[key] = _prune(child, rules, ledger, path + (key,), prefix + (key,))
    return result


def prune(full):
    """Return a copy and a log of every excluded value, including raw requests."""
    ledger = []
    value = _prune(full, TOP, ledger)
    for i, event in enumerate(value["recent_events"]):
        lines = []
        for j, line in enumerate(event["protocol"].splitlines(keepends=True)):
            if line.startswith("|request|") and line[9:].strip():
                end = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                raw = json.loads(line[9:])
                if raw is not None:
                    if not isinstance(raw, dict):
                        raise ValueError("invalid historical request")
                    if len(raw.get("active", [])) > 1 or len(raw.get("forceSwitch", [])) > 1:
                        raise ValueError("request is not singles")
                cleaned = _prune(
                    raw, RAW, ledger, prefix=("recent_events", i, "protocol", j, "RequestJSON")
                )
                if cleaned != raw:
                    line = (
                        "|request|"
                        + json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))
                        + end
                    )
            lines.append(line)
        event["protocol"] = "".join(lines)
    return value, ledger


def filtered_catalog():
    guide = copy.deepcopy(battle_prompts.catalog("v1.2.0"))
    for definition, keys in SCHEMA_REMOVALS.items():
        for key in keys:
            guide["definitions"][definition]["properties"].pop(key, None)
    for key in ("condition_id", "lesson_memory", "battle_summary"):
        guide["roots"]["$"]["properties"].pop(key, None)
    return guide


def policy():
    # Retain the full tactical procedure and exact final action contract.
    base = (battle_prompts.PROMPTS / "battle_fixed.txt").read_text()
    base = base.split("\n---\n\nEXPERIMENT PROFILE")[0]
    base = base.replace(
        "A same-battle summary supplies retained history, not a replacement for the "
        "current snapshot. Explicitly corrected source events supersede mistaken summaries.",
        "Historical events do not replace the current snapshot.",
    ).replace("event text, memories and other data fields", "event text and other data fields")
    return base + "\n"
