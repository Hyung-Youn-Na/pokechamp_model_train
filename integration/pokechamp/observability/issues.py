"""Derived issue labels and immutable explanation annotations linked to source."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

LABELS = {
    "output_format": "출력 형식 오류",
    "extracted_action": "행동 추출",
    "fallback": "대체 행동",
    "explanation": "설명 오류",
    "execution": "실행 실패",
}
DIMENSIONS = ("facts", "identity", "timing", "calculation")


def load_annotations(bundle, manifest):
    bundle = Path(bundle)
    path = bundle.parent.parent / "annotations" / f"{bundle.name}.json"
    if not path.exists():
        return {}
    from ..benchmark import read_sealed

    value = read_sealed(path)
    if (
        value.get("battle_id") != manifest.get("battle_id")
        or value.get("actor_id") != manifest.get("metadata", {}).get("actor_id")
        or value.get("events_sha256")
        != hashlib.sha256((bundle / "events.jsonl").read_bytes()).hexdigest()
    ):
        raise ValueError("explanation annotation source/identity mismatch")
    events = {
        str(e["event_seq"]): e
        for e in map(json.loads, (bundle / "events.jsonl").read_text().splitlines())
        if e["event_type"] == "llm_call"
    }
    for key, row in value["calls"].items():
        if key not in events or row.get("status") != "reviewed":
            raise ValueError("unknown annotation event or incomplete review")
        if not all(type(row.get(d)) is bool for d in DIMENSIONS) or not row.get(
            "evidence"
        ):
            raise ValueError("annotation dimensions/evidence missing")
    return value["calls"]


def decorate(decisions, manifest, annotations):
    actor = manifest.get("metadata", {}).get("actor_id", "unknown")
    for decision in decisions:
        start = decision["start"]
        decision["issue_anchor"] = (
            f"battle-{manifest.get('battle_id', 'unknown')}-"
            f"actor-{actor}-decision-{start.get('decision_seq')}"
        )
        labels, reviews = set(), []
        for call in decision["calls"]:
            validation = call.get("validation", {})
            resolution = validation.get("action_resolution", {})
            if (
                validation.get("output_contract_valid") is False
                and call.get("raw_content") is not None
            ):
                labels.add("output_format")
            if resolution.get("selection_source") == "extracted_action":
                labels.add("extracted_action")
            if resolution.get("selection_source") == "first_legal_fallback":
                labels.add("fallback")
            if (
                call.get("status") == "failure"
                and not resolution
                and validation.get("category")
            ):
                labels.add("execution")
            if manifest.get("metadata", {}).get("condition_id") == "B":
                row = annotations.get(str(call.get("event_seq")))
                reviews.append(row or {"status": "unreviewed", "label": "미검토"})
                if row and not all(row[d] for d in DIMENSIONS):
                    labels.add("explanation")
        for result in decision["results"]:
            validation = result.get("validation", {})
            if "fallback" in str(validation.get("action_origin", "")):
                labels.add("fallback")
            if result.get("error") or result.get("status") in ("error", "failure"):
                labels.add("execution")
        if any(w.get("send_status") not in (None, "sent") for w in decision["wires"]):
            labels.add("execution")
        decision["issues"] = [k for k in LABELS if k in labels]
        decision["explanation_reviews"] = reviews
    if decisions and manifest.get("result", {}).get("outcome") not in (
        "player_won",
        "player_lost",
        "tied",
    ):
        if "execution" not in decisions[-1]["issues"]:
            decisions[-1]["issues"].append("execution")
    return decisions


def counts(decisions):
    problematic = [d for d in decisions if d.get("issues")]
    turns = {
        d["start"].get("showdown_turn")
        if d["start"].get("showdown_turn") is not None
        else f"decision-{d['start'].get('decision_seq')}"
        for d in problematic
    }
    return dict(problem_decisions=len(problematic), problem_turns=len(turns))
