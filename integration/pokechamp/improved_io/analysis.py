"""Separate condition denominators and completed paired contrasts."""

from __future__ import annotations

import itertools
import json
import statistics
from collections import defaultdict
from pathlib import Path

from .. import benchmark as b
from .conditions import CONDITIONS


def analyze_conditions(directory, value, attempts):
    report = {
        "experiment_id": value["experiment_id"],
        "exploratory": True,
        "conditions": {},
        "paired_contrasts": {},
        "execution": value["execution"],
    }
    scores = {}
    conditions = value.get("conditions", CONDITIONS)
    for condition in conditions:
        scheduled = [s for s in value["schedule"] if s["condition_id"] == condition]
        observed = [a for a in attempts if a["slot"]["condition_id"] == condition]
        summary = b.summarize_attempts(observed, len(scheduled))
        attempted = {a["slot_id"] for a in observed}
        summary["unexecuted"] = [s["slot_id"] for s in scheduled if s["slot_id"] not in attempted]
        summary["failed_slots"] = sum(not a["eligible"] for a in observed)
        roles = defaultdict(
            lambda: dict(
                calls=0, failed=0, prompt_tokens=0, completion_tokens=0, http_ms=0, permit_wait_ms=0
            )
        )
        for attempt in observed:
            for actor_role, actor in attempt["actors"].items():
                if not actor.get("bundle"):
                    continue
                events = Path(actor["bundle"]) / "events.jsonl"
                for line in events.read_text().splitlines():
                    event = json.loads(line)
                    if event["event_type"] != "llm_call":
                        continue
                    key = actor_role + ":" + event["request"].get("call_role", "unknown")
                    row = roles[key]
                    row["calls"] += 1
                    row["failed"] += event.get("status") != "success"
                    response = event.get("response", {})
                    for name in ("prompt_tokens", "completion_tokens", "permit_wait_ms"):
                        row[name] += response.get(name) or 0
                    row["http_ms"] += response.get("http_elapsed_ms") or 0
        summary["roles"] = dict(roles)
        summary["transport"] = value["execution"]["evidence"].get("io_transport")
        report["conditions"][condition] = summary
        for attempt in observed:
            if attempt["eligible"]:
                slot = attempt["slot"]
                role = f"p{slot['methods'].index('io') + 1}"
                scores[condition, slot["paired_slot_id"]] = {
                    "player_won": 1,
                    "player_lost": 0,
                    "tied": 0.5,
                }[attempt["actors"][role]["outcome"]]
    keys = sorted({s["paired_slot_id"] for s in value["schedule"]})
    for first, second in itertools.combinations(conditions, 2):
        paired = {
            key: scores[second, key] - scores[first, key]
            for key in keys
            if (first, key) in scores and (second, key) in scores
        }
        report["paired_contrasts"][f"{second}-{first}"] = {
            "paired_slot_differences": paired,
            "mean": statistics.mean(paired.values()) if paired else None,
            "missing_pairs": [key for key in keys if key not in paired],
        }
    report["batches"] = [b.read_sealed(p) for p in sorted((directory / "batches").glob("*.json"))]
    report["batch_elapsed_seconds"] = sum(x["elapsed_seconds"] for x in report["batches"])
    report["attempt_resource_seconds"] = sum(a["duration_seconds"] for a in attempts)
    b.write_json(directory / "analysis" / "conditions.json", report, exclusive=False)
    return report
