"""One row per scenario; share prose and duplicate top/variant damage copies only."""

from __future__ import annotations

import copy
import re
from collections import Counter

from .history import same_json

DAMAGE_FIELDS = ("damage_range_hp", "damage_rolls")
COVERAGE_FIELDS = {
    "scenario_id",
    "direction",
    "action",
    "target",
    "move",
    "target_mode",
    "execution",
}


def _texts(value):
    if isinstance(value, str) and len(value) >= 80:
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _texts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _texts(child)


def _map(value, transform):
    replacement = transform(value)
    if replacement is not value:
        return replacement
    if isinstance(value, dict):
        return {key: _map(child, transform) for key, child in value.items()}
    if isinstance(value, list):
        return [_map(child, transform) for child in value]
    return value


def encode(bundle, observation, hypotheses):
    entries, coverage = bundle["entries"], bundle["coverage"]
    if [e["scenario_id"] for e in entries] != [c["scenario_id"] for c in coverage] or len(
        {e["scenario_id"] for e in entries}
    ) != len(entries):
        raise ValueError("scenario join is not one-to-one and ordered")
    opponent = next((p for p in observation["opponent_confirmed"] if p["active"]), None)
    rows = []
    for entry, cov in zip(entries, coverage, strict=True):
        if not cov.keys() <= COVERAGE_FIELDS:
            raise ValueError("unclassified coverage field")
        result = copy.deepcopy({k: v for k, v in entry.items() if k != "scenario_id"})
        for key in DAMAGE_FIELDS:
            if key not in result:
                continue
            for index, variant in enumerate(result.get("damage_variants", [])):
                if key in variant and same_json(result[key], variant[key]):
                    result[key] = {"same_as_variant": index}
                    break
        match = re.search(r"-h(\d+)-hp(\d+)$", entry["scenario_id"])
        if match:
            hypothesis, hp = map(int, match.groups())
            if hypothesis >= len(hypotheses):
                raise ValueError("missing opponent hypothesis reference")
            condition = dict(hypothesis_index=hypothesis, hp=hp)
        elif entry["scenario_id"].endswith("-unknown-opponent"):
            condition = "UNKNOWN: replacement not revealed"
        else:
            raise ValueError("unrecognized scenario hypothesis/HP convention")
        target = (
            cov.get("target") or cov.get("action", {}).get("switch")
            if cov["direction"] == "incoming"
            else opponent["species"]
            if opponent is not None
            else None
        )
        rows.append(
            {
                **copy.deepcopy(cov),
                "calculation_target": target,
                "opponent_condition": condition,
                "result": result,
            }
        )
    compact = {
        **{k: copy.deepcopy(v) for k, v in bundle.items() if k not in ("entries", "coverage")},
        "scenarios": rows,
    }
    counts = Counter(_texts(compact))
    table = {f"c{i}": text for i, text in enumerate(sorted(t for t, n in counts.items() if n > 1))}
    ids = {text: key for key, text in table.items()}
    compact = _map(
        compact, lambda v: {"shared_text": ids[v]} if isinstance(v, str) and v in ids else v
    )
    compact["shared_text"] = table
    return compact


def decode(bundle):
    table = bundle.get("shared_text")
    if not isinstance(table, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in table.items()
    ):
        raise ValueError("common conditions must be one-level text values")
    used = set()

    def expand(value):
        if isinstance(value, dict) and "shared_text" in value:
            if set(value) != {"shared_text"} or not isinstance(value["shared_text"], str):
                raise ValueError("invalid common condition reference")
            key = value["shared_text"]
            if key not in table:
                raise ValueError("missing common condition reference")
            used.add(key)
            return table[key]
        return value

    compact = _map({k: v for k, v in bundle.items() if k != "shared_text"}, expand)
    if used != set(table):
        raise ValueError("unused common conditions")
    rows = compact.pop("scenarios")
    entries, coverage, seen = [], [], set()
    for row in rows:
        if set(row) - COVERAGE_FIELDS != {"calculation_target", "opponent_condition", "result"}:
            raise ValueError("unclassified compact scenario fields")
        scenario = row["scenario_id"]
        if scenario in seen:
            raise ValueError("duplicate compact scenario")
        seen.add(scenario)
        result = copy.deepcopy(row["result"])
        for key in DAMAGE_FIELDS:
            ref = result.get(key)
            if isinstance(ref, dict):
                if set(ref) != {"same_as_variant"} or type(ref["same_as_variant"]) is not int:
                    raise ValueError("invalid damage copy reference")
                index = ref["same_as_variant"]
                variants = result.get("damage_variants", [])
                if index < 0 or index >= len(variants) or key not in variants[index]:
                    raise ValueError("missing damage variant reference")
                target = variants[index][key]
                if isinstance(target, dict):
                    raise ValueError("nested damage copy reference")
                result[key] = copy.deepcopy(target)
        entries.append({"scenario_id": scenario, **result})
        coverage.append({k: v for k, v in row.items() if k in COVERAGE_FIELDS})
    return {**compact, "entries": entries, "coverage": coverage}
