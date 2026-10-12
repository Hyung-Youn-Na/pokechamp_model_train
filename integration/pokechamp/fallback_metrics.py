"""D-018 metrics: IO/search events are distinct from actual wire decisions."""

import json
from collections import Counter, defaultdict
from pathlib import Path


def fallback_metrics(attempts):
    result = {}
    for cohort in ("all_attempts", "eligible_completed"):
        methods = {}
        for method in ("io", "minimax"):
            row = dict(
                actor_games=0,
                games_with_sent_fallback=0,
                sent_decisions=0,
                sent_fallback_decisions=0,
                io_calls=0,
                extra_calls=0,
                recovered_io_calls=0,
                fallback_stages=Counter(),
                io_by_role=defaultdict(Counter),
                output_errors_by_role=defaultdict(Counter),
            )
            for attempt in attempts:
                if cohort == "eligible_completed" and not attempt["eligible"]:
                    continue
                for index, actor_method in enumerate(attempt["slot"]["methods"]):
                    if actor_method != method:
                        continue
                    row["actor_games"] += 1
                    actor = attempt["actors"].get(f"p{index + 1}", {})
                    for d in actor.get("diagnostics", []):
                        context = d.get("io_context", {})
                        if d["kind"] == "io_result":
                            row["io_calls"] += 1
                            role_row = row["io_by_role"][context["role"]]
                            role_row["returned_io_calls"] += 1
                            role_row["recovered_io_calls"] += (
                                context["attempt"] > 1 and not d["fallback"]
                            )
                            row["recovered_io_calls"] += (
                                context["attempt"] > 1 and not d["fallback"]
                            )
                        elif d["kind"] == "fallback_stage":
                            row["fallback_stages"][d["stage"]] += 1
                        elif (
                            d["kind"] == "io_output_error"
                            and d["cause"] == "candidate_connection"
                        ):
                            row["output_errors_by_role"][context["role"]][
                                "candidate_connection"
                            ] += 1
                    if not actor.get("bundle"):
                        continue
                    events = [
                        json.loads(line)
                        for line in (Path(actor["bundle"]) / "events.jsonl")
                        .read_text()
                        .splitlines()
                    ]
                    origins = {
                        e["decision_seq"]: e.get("validation", {}).get(
                            "action_origin", ""
                        )
                        for e in events
                        if e["event_type"] == "decision_result"
                    }
                    sent, fallback = set(), set()
                    io_ids = set()
                    for e in events:
                        if e["event_type"] == "llm_call":
                            req, val = e.get("request", {}), e.get("validation", {})
                            context = req.get("io_context") or {}
                            if context:
                                io_ids.add(context["io_call_id"])
                                row["extra_calls"] += context["attempt"] > 1
                                role_row = row["io_by_role"][context["role"]]
                                role_row["calls"] += 1
                                role_row["extra_calls"] += context["attempt"] > 1
                                role_row["started_io_calls"] += context["attempt"] == 1
                            if (
                                val.get("json_valid") is False
                                and e.get("raw_content") is not None
                            ):
                                row["output_errors_by_role"][
                                    req.get("call_role", "unknown")
                                ]["json_parse"] += 1
                        if (
                            e["event_type"] == "wire_action"
                            and e.get("send_status") == "sent"
                            and e.get("action", "").startswith("/choose ")
                        ):
                            key = e.get("decision_seq")
                            sent.add(key)
                            if origins.get(key, "").startswith("fallback_"):
                                fallback.add(key)
                    # Include interrupted IO calls that never returned.
                    row.setdefault("io_calls_started", 0)
                    row["io_calls_started"] += len(io_ids)
                    row["sent_decisions"] += len(sent)
                    row["sent_fallback_decisions"] += len(fallback)
                    row["games_with_sent_fallback"] += bool(fallback)
            row["sent_fallback_fraction"] = (
                row["sent_fallback_decisions"] / row["sent_decisions"]
                if row["sent_decisions"]
                else None
            )
            row["fallback_game_fraction"] = (
                row["games_with_sent_fallback"] / row["actor_games"]
                if row["actor_games"]
                else None
            )
            methods[method] = row
        result[cohort] = methods
    return result


def markdown_metrics(metrics):
    lines = [
        "",
        "## 원본 fallback: 실제 전송과 검색 분리",
        "",
        "| 집계 | 방법 | fallback 판단/전송 판단 | fallback 경기/경기 | IO 시작/반환 | 추가 호출 | 회복 IO |",
        "|---|---|---|---|---|---|---|",
    ]
    details = []
    for cohort, methods in metrics.items():
        for method, r in methods.items():
            lines.append(
                f"| {cohort} | {method} | {r['sent_fallback_decisions']}/{r['sent_decisions']} | {r['games_with_sent_fallback']}/{r['actor_games']} | {r.get('io_calls_started', 0)}/{r['io_calls']} | {r['extra_calls']} | {r['recovered_io_calls']} |"
            )
            details.extend(
                [
                    "",
                    f"{cohort}/{method} 단계: "
                    + json.dumps(r["fallback_stages"], ensure_ascii=False),
                    f"{cohort}/{method} 역할별 IO: "
                    + json.dumps(r["io_by_role"], ensure_ascii=False),
                    f"{cohort}/{method} 역할별 출력 오류: "
                    + json.dumps(r["output_errors_by_role"], ensure_ascii=False),
                    "",
                ]
            )
    return lines + details
