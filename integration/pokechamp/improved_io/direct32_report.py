"""Postcollection direct32 metrics and 32-slot viewer; never changes raw evidence."""

from __future__ import annotations

import html
import json
import os
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from .. import benchmark as b
from ..concurrency_metrics import request_metrics
from ..observability.issues import DIMENSIONS, counts, decorate, load_annotations
from ..observability.render import _group_decisions, rebuild_experiment
from . import experiment_policy as policy


def extend(manifest, attempts, review_calls, review, output, batches):
    seen = {a["slot_id"]: a for a in attempts}
    audit = b.read_sealed(review) if review else None
    dimensions = Counter()
    normal = Counter(A=0, B=0)
    resolutions = Counter(model_output=0, extracted_action=0, first_legal_fallback=0)
    sent_sources = resolutions.copy()
    condition_calls = {"A": [], "B": []}
    rows, annotations, experiments = [], {}, set()
    for slot in manifest["compare_schedule"]:
        attempt = seen.get(slot["slot_id"])
        row = dict(
            slot_id=slot["slot_id"],
            condition=slot["condition_id"],
            status="unexecuted",
            category=next(
                (v["stop_category"] for v in batches if v["stop_category"]),
                "not_dispatched",
            ),
            problem_turns=0,
            problem_decisions=0,
            viewers=[],
        )
        if attempt:
            row.update(
                status="completed" if attempt["eligible"] else "failed",
                category=attempt["category"],
            )
            output_errors = False
            for role, actor in attempt["actors"].items():
                if not actor.get("bundle"):
                    continue
                bundle = Path(actor["bundle"])
                actor_manifest = (
                    b.read_sealed(bundle / "manifest.json")
                    if (bundle / "manifest.json.sha256").exists()
                    else json.loads((bundle / "manifest.json").read_text())
                )
                policy.same(manifest, actor_manifest["metadata"])
                if policy.is_v2_repeat(manifest):
                    from .inputfix32 import verify_runtime

                    verify_runtime(
                        actor_manifest["metadata"],
                        prompt_identity=manifest["battle_prompt_identity"],
                    )
                events = list(
                    map(json.loads, (bundle / "events.jsonl").read_text().splitlines())
                )
                output_errors |= any(
                    d.get("kind") == "io_output_error"
                    for d in actor.get("diagnostics", [])
                )
                origins = {
                    e["decision_seq"]: e.get("validation", {}).get(
                        "action_origin", "unknown"
                    )
                    for e in events
                    if e["event_type"] == "decision_result"
                }
                output_errors |= any(
                    "fallback" in origin for origin in origins.values()
                )
                if (
                    slot["condition_id"] == "B"
                    and slot["methods"][int(role[-1]) - 1] == "io"
                ):
                    for event in events:
                        if (
                            event["event_type"] == "wire_action"
                            and event.get("send_status") == "sent"
                            and event.get("action", "").startswith("/choose ")
                        ):
                            sent_sources[
                                origins.get(event["decision_seq"], "unknown")
                            ] += 1
                reviewed = {}
                for e in events:
                    if e["event_type"] != "llm_call":
                        continue
                    policy.same(manifest, e["request"])
                    condition_calls[slot["condition_id"]].append(e)
                    val = e.get("validation", {})
                    if val.get("output_contract_valid") is False:
                        output_errors = True
                    resolution = val.get("action_resolution")
                    if resolution:
                        resolutions[resolution["selection_source"]] += 1
                    key = str(bundle) + ":" + str(e["event_seq"])
                    if audit and key in review_calls:
                        reviewed[str(e["event_seq"])] = dict(
                            audit["calls"][key], status="reviewed"
                        )
                        for dim in DIMENSIONS:
                            dimensions[dim] += not audit["calls"][key][dim]
                if audit and reviewed:
                    path = bundle.parent.parent / "annotations" / f"{bundle.name}.json"
                    path.parent.mkdir(exist_ok=True)
                    annotation = dict(
                        **policy.selected(manifest),
                        battle_id=actor_manifest["battle_id"],
                        actor_id=role,
                        events_sha256=b.digest(bundle / "events.jsonl"),
                        review_sha256=b.digest(review),
                        calls=reviewed,
                    )
                    if path.exists():
                        if b.read_sealed(path) != annotation:
                            raise ValueError("immutable annotation already differs")
                    else:
                        b.seal_json(path, annotation)
                    annotations[str(path)] = b.digest(path)
                decisions, _ = _group_decisions(events)
                decorate(
                    decisions, actor_manifest, load_annotations(bundle, actor_manifest)
                )
                if slot["methods"][int(role[-1]) - 1] == "io":
                    row.update(counts(decisions))
                row["viewers"].append(
                    dict(actor=role, path=str(bundle / "report.html"))
                )
                experiments.add(bundle.parent.parent)
            if attempt["eligible"] and not output_errors:
                normal[slot["condition_id"]] += 1
        rows.append(row)
    for experiment in experiments:
        rebuild_experiment(experiment.parent.parent, experiment.name)
    e = html.escape
    body = []
    for row in rows:
        links = " · ".join(
            f'<a href="{e(quote(os.path.relpath(v["path"], output), safe="/"))}">'
            f"{e(v['actor'])}</a>"
            for v in row["viewers"]
        )
        status = {"completed": "완료", "failed": "실패", "unexecuted": "미실행"}[
            row["status"]
        ]
        body.append(
            f"<tr><td>{e(row['slot_id'])}</td><td>{e(status)}</td>"
            f"<td>{row['problem_turns']}턴 / {row['problem_decisions']}결정</td>"
            f"<td>{e(row['category'] or '')}</td><td>{links}</td></tr>"
        )
    (output / "matches.html").write_text(
        (
            """<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'">
<title>EX-028 32경기 목록</title><style>
body{font:16px system-ui;margin:2rem;background:#f3f6fa;color:#182638}
table{border-collapse:collapse;background:white}
td,th{padding:.7rem;border:1px solid #ccd6e0;text-align:left}
a{color:#174e91}</style>
<h1>EX-028 32경기 목록</h1><p>오류 처리 정책을 포함한 전체 구성의 탐색 비교.
문제 수는 IO actor 관점이며 설명 검토 전에는 미검토다.</p>
<table><thead><tr><th>Slot</th><th>상태</th><th>문제 턴 / 결정</th>
<th>실패·미실행 사유</th><th>Actor viewer</th></tr></thead><tbody>"""
            + "".join(body)
            + "</tbody></table></html>"
        ).replace("EX-028", e(manifest["experiment_policy_identity"]["experiment_id"]))
    )
    return dict(
        slots_processed=len(attempts),
        natural_completions=sum(a["eligible"] for a in attempts),
        slot_results=rows,
        normal_output_completed_games=dict(normal),
        b_action_sources=dict(resolutions),
        explanation_error_dimensions=dict(dimensions),
        b_sent_action_sources=dict(sent_sources),
        condition_request_metrics={
            condition: dict(
                calls=len(calls),
                responses=sum(e.get("raw_content") is not None for e in calls),
                prompt_tokens=sum(
                    e["response"].get("prompt_tokens") or 0 for e in calls
                ),
                completion_tokens=sum(
                    e["response"].get("completion_tokens") or 0 for e in calls
                ),
                cumulative_http_seconds=sum(
                    e["response"].get("http_elapsed_ms") or 0 for e in calls
                )
                / 1000,
                **request_metrics(calls),
            )
            for condition, calls in condition_calls.items()
        },
        annotations=annotations,
        recollection_attempts=0,
        interpretation="오류 처리 정책을 포함한 전체 구성의 개발 대진 탐색 비교",
    )
