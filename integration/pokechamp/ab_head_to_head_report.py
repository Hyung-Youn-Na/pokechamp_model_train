"""Condition/seat outcomes and complete two-actor decision evidence for EX-036."""

from __future__ import annotations

import html
import json
import sqlite3
import statistics
import time
from collections import defaultdict
from pathlib import Path

from . import ab_head_to_head as h
from . import benchmark as b
from .a_diagnostic_report import attach_journal, inventory, observed_attempts, summarize


def paired_scores(matches):
    grouped = defaultdict(list)
    for row in matches:
        grouped[row["paired_slot_id"]].append(row)
    results = []
    for key, rows in sorted(grouped.items()):
        valid = [r for r in rows if r["status"] == "valid_completed"]
        scores = [
            1 if r["outcome"] == "player_won" else 0.5 if r["outcome"] == "tied" else 0
            for r in valid
        ]
        complete = len(valid) == 2 and {
            tuple(r["actor_conditions"]) for r in valid
        } == {("A", "B"), ("B", "A")}
        results.append(
            dict(
                paired_slot_id=key,
                valid_games=len(valid),
                complete=complete,
                B_score_mean=sum(scores) / 2 if complete else None,
                missing_slots=[
                    r["slot_id"] for r in rows if r["status"] != "valid_completed"
                ],
            )
        )
    return results


def condition_usage(directory, value, decisions):
    actors = {
        "/".join(
            (value["experiment_id"], row["slot_id"] + "-a1", role)
        ): b.actor_condition(row, role)
        for row in value["schedule"]
        for role in ("p1", "p2")
    }
    result = {
        c: dict(
            reserved_calls=0,
            responses=0,
            uncertain=0,
            token_usage_unconfirmed=0,
            input_tokens=0,
            output_tokens=0,
            elapsed_ms=0,
            fallback_decisions=0,
            no_call_decisions=0,
            decisions=0,
            system_characters=0,
            user_characters=0,
            system_utf8_bytes=0,
            user_utf8_bytes=0,
            selection_sources={},
        )
        for c in ("A", "B")
    }
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        rows = db.execute(
            "SELECT number,actor FROM reservations ORDER BY number"
        ).fetchall()
    for number, actor in rows:
        item = result[actors[actor]]
        item["reserved_calls"] += 1
        payload = b.read_sealed(directory / "requests" / f"intent-{number:06}.json")["payload"]
        for part in ("system", "user"):
            text = payload[part + "_prompt"]
            item[part + "_characters"] += len(text)
            item[part + "_utf8_bytes"] += len(text.encode("utf-8"))
        response = directory / "requests" / f"response-{number:06}.json"
        if response.exists():
            raw = b.read_sealed(response)["response"]
            item["responses"] += 1
            item["token_usage_unconfirmed"] += (
                raw.get("prompt_eval_count") is None or raw.get("eval_count") is None
            )
            item["input_tokens"] += raw.get("prompt_eval_count") or 0
            item["output_tokens"] += raw.get("eval_count") or 0
        else:
            item["uncertain"] += 1
            item["token_usage_unconfirmed"] += 1
    latencies = defaultdict(list)
    for decision in decisions:
        item = result[decision["condition_id"]]
        latencies[decision["condition_id"]].extend(
            c.get("response", {}).get("elapsed_ms", 0) or 0 for c in decision["calls"]
        )
        item["decisions"] += 1
        item["no_call_decisions"] += decision["call_status"] in (
            "not_called",
            "not_dispatched",
        )
        item["elapsed_ms"] += sum(
            c.get("response", {}).get("elapsed_ms", 0) or 0 for c in decision["calls"]
        )
        sources = {
            r.get("validation", {}).get("action_origin") for r in decision["results"]
        }
        sources.discard(None)
        for source in sources:
            item["selection_sources"][source] = (
                item["selection_sources"].get(source, 0) + 1
            )
        item["fallback_decisions"] += any(
            source.startswith("fallback_") or source == "first_legal_fallback"
            for source in sources
        )
    for condition, item in result.items():
        values = latencies[condition]
        item["mean_request_elapsed_ms"] = statistics.mean(values) if values else None
        item["median_request_elapsed_ms"] = (
            statistics.median(values) if values else None
        )
    return result


def build_report(directory):
    directory = Path(directory).resolve()
    value = h.verify_prepared(directory, current=False)
    attempts = observed_attempts(directory, value)
    by_slot = {a["slot_id"]: a for a in attempts}
    invalidations = (
        b.read_sealed(directory / "invalidations.json")
        if (directory / "invalidations.json").exists()
        else {}
    )
    stop = (
        b.read_sealed(directory / "halt.json")["category"]
        if (directory / "halt.json").exists()
        else None
    )
    matches, decisions = [], []
    for slot in value["schedule"]:
        attempt = by_slot.get(slot["slot_id"])
        row = dict(
            slot,
            status="not_run",
            reason=stop or "not_dispatched",
            outcome=None,
            actors={},
            duration_seconds=None,
            turns=None,
        )
        if attempt:
            row.update(
                status=attempt["report_status"],
                reason=attempt["category"],
                duration_seconds=attempt["duration_seconds"],
                integrity_errors=attempt["integrity_errors"],
            )
            if slot["slot_id"] in invalidations:
                row.update(status="invalid", reason=invalidations[slot["slot_id"]])
            for role in ("p1", "p2"):
                actor = attempt["actors"].get(role, {})
                condition = b.actor_condition(slot, role)
                row["actors"][condition] = dict(
                    role=role,
                    team=slot["teams"][int(role[-1]) - 1],
                    outcome=actor.get("outcome"),
                    turns=actor.get("turns"),
                    bundle=actor.get("bundle"),
                    viewer=None,
                )
                if condition == "B":
                    row["outcome"] = actor.get("outcome")
                    row["turns"] = actor.get("turns")
                if actor.get("bundle"):
                    if actor.get("bundle_valid"):
                        from .observability.render import rebuild_battle

                        rebuild_battle(actor["bundle"])
                        row["actors"][condition]["viewer"] = str(
                            Path(actor["bundle"]) / "report.html"
                        )
                    items = inventory(
                        dict(
                            slot, A_role=role, task="head_to_head", team_assignment=role
                        ),
                        actor,
                    )
                    for item in items:
                        item.update(
                            key=slot["slot_id"]
                            + ":"
                            + role
                            + ":"
                            + str(item["decision_seq"]),
                            condition_id=condition,
                            block_id=slot["block_id"],
                            team=slot["teams"][int(role[-1]) - 1],
                        )
                    decisions.extend(items)
            if row["status"] == "valid_completed":
                outcomes = tuple(row["actors"][c]["outcome"] for c in ("A", "B"))
                if outcomes not in (
                    ("player_won", "player_lost"),
                    ("player_lost", "player_won"),
                    ("tied", "tied"),
                ):
                    row.update(
                        status="invalid", reason="inconsistent_terminal_outcomes"
                    )
        matches.append(row)
    unlinked = attach_journal(directory, value, decisions)
    review = (
        b.read_sealed(directory / "review.json")
        if (directory / "review.json").exists()
        else {}
    )
    if set(review) - {r["key"] for r in decisions}:
        raise ValueError("unknown review decision")
    for item in decisions:
        if item["key"] in review:
            annotation = review[item["key"]]
            if annotation.get("events_sha256") != item[
                "events_sha256"
            ] or not annotation.get("rationale"):
                raise ValueError("review evidence/rationale missing")
            item.update(review=annotation, review_status="reviewed")
    pairs = paired_scores(matches)
    blocks = {
        key: summarize([r for r in matches if r["block_id"] == key]) for key in h.BLOCKS
    }
    seats = {
        role: summarize([r for r in matches if r["B_role"] == role])
        for role in ("p1", "p2")
    }
    teams = {
        key: summarize(
            [r for r in matches if r["teams"][int(r["B_role"][-1]) - 1] == key]
        )
        for key in value["teams"]
    }
    summary = summarize(matches)
    n = summary["valid_completed"]
    summary.update(
        experiment_id=value["experiment_policy_identity"]["experiment_id"],
        experiment_policy=value["experiment_policy"],
        skipped_checks=value.get("skipped_checks", {}),
        outcome_perspective="B",
        B=dict(summary),
        A=dict(
            wins=summary["losses"],
            losses=summary["wins"],
            draws=summary["draws"],
            win_rate=summary["losses"] / n if n else None,
            draw_adjusted_score=(summary["losses"] + 0.5 * summary["draws"]) / n
            if n
            else None,
        ),
        complete_pairs=sum(p["complete"] for p in pairs),
        missing_pairs=sum(not p["complete"] for p in pairs),
        paired_B_mean=(
            sum(p["B_score_mean"] for p in pairs if p["complete"])
            / sum(p["complete"] for p in pairs)
            if any(p["complete"] for p in pairs)
            else None
        ),
        collection_complete=n == 32 and all(p["complete"] for p in pairs),
        blocks=blocks,
        B_seats=seats,
        B_teams=teams,
        usage=h.usage(directory),
        condition_usage=condition_usage(directory, value, decisions),
        decisions=len(decisions),
        reviewed=sum(d["review_status"] == "reviewed" for d in decisions),
        unlinked_requests=len(unlinked),
        journal_only_requests=sum(len(d["journal_only_requests"]) for d in decisions),
        unparsed_event_lines=sum(
            len(v)
            for v in {
                d["bundle"]: d["unparsed_event_lines"] for d in decisions
            }.values()
        ),
        stop_category=stop,
    )
    lengths = [r["turns"] for r in matches if r.get("turns") is not None]
    for condition in ("A", "B"):
        summary["condition_usage"][condition]["battle_turns"] = dict(
            observed=len(lengths),
            mean=statistics.mean(lengths) if lengths else None,
            median=statistics.median(lengths) if lengths else None,
        )
    output = directory / "reports" / f"report-{time.time_ns()}"
    output.mkdir(parents=True)
    for name, obj in (
        ("summary", summary),
        ("matches", matches),
        ("pairs", pairs),
        ("unlinked-requests", unlinked),
    ):
        b.seal_json(output / (name + ".json"), obj)
    with (output / "decisions.jsonl").open("w") as stream:
        for row in decisions:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output / "decisions.jsonl.sha256").write_text(
        b.digest(output / "decisions.jsonl") + "\n"
    )
    table = []
    for row in matches:
        cells = [
            str(row[k])
            for k in (
                "submission_order",
                "slot_id",
                "actor_conditions",
                "teams",
                "status",
                "reason",
                "outcome",
            )
        ]
        links = []
        for condition, actor in row["actors"].items():
            if actor["viewer"]:
                links.append(
                    '<a href="'
                    + html.escape(actor["viewer"], quote=True)
                    + '">'
                    + condition
                    + "/"
                    + actor["role"]
                    + "</a>"
                )
        table.append(
            "<tr>"
            + "".join("<td>" + html.escape(c) + "</td>" for c in cells)
            + "<td>"
            + " ".join(links)
            + "</td></tr>"
        )
    (output / "matches.html").write_text(
        f'<!doctype html><meta charset="utf-8"><title>{summary["experiment_id"]} 32경기</title><h1>A/B 직접대결32</h1><table><tr><th>순서</th><th>경기</th><th>p1/p2 조건</th><th>팀</th><th>상태</th><th>사유</th><th>B 결과</th><th>양측 기록</th></tr>'
        + "".join(table)
        + "</table>"
    )
    (output / "report.md").write_text(
        f"# {summary['experiment_id']} A/B 직접대결32\n\n"
        + f"예정32·시도{summary['attempted']}·유효완료{n}·실패{summary['failed']}·무효{summary['invalid']}·미실행{summary['not_run']}. 완료대응{summary['complete_pairs']}/16.\n\n"
        + f"B {summary['wins']}승 {summary['losses']}패 {summary['draws']}무; 승률 {summary['win_rate']}, 점수 {summary['draw_adjusted_score']}.\n\n"
        + f"양측 결정{len(decisions)}개·검토{summary['reviewed']}개. 요청{summary['usage']['reserved_calls']}·응답{summary['usage']['responses']}·미확정{summary['usage']['uncertain']}.\n\n"
        + "b02/b03은 동일 팀 조합의 방향 반전이다. 등록된 A/B 전체 구성 비교이며 프롬프트 단독 또는 L1–L5 효능으로 해석하지 않는다.\n"
    )
    return dict(summary, report_directory=str(output))
