"""A decision inventory and descriptive denominators; strategic review is explicit."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import benchmark as b


def read_events(bundle):
    events, errors = [], []
    raw = (Path(bundle) / "events.jsonl").read_bytes()
    for number, line in enumerate(
        raw.decode("utf-8", errors="replace").splitlines(), 1
    ):
        try:
            event = json.loads(line)
            if (
                not isinstance(event, dict)
                or "event_type" not in event
                or "event_seq" not in event
            ):
                raise ValueError("incomplete event")
            events.append(event)
        except (ValueError, TypeError):
            errors.append(number)
    return events, errors


def inventory(slot, actor):
    bundle = Path(actor["bundle"])
    events, parse_errors = read_events(bundle)
    checksum = b.digest(bundle / "events.jsonl")
    bundle_valid = b.verify_bundle(bundle)["valid"]
    rows = []
    grouped = defaultdict(list)
    for event in events:
        if event.get("decision_seq") is not None:
            grouped[event["decision_seq"]].append(event)
    for start in events:
        if start["event_type"] != "decision_start":
            continue
        seq = start["decision_seq"]
        related = grouped[seq]
        calls = [e for e in related if e["event_type"] == "llm_call"]
        results = [e for e in related if e["event_type"] == "decision_result"]
        wires = [e for e in related if e["event_type"] == "wire_action"]
        prefix = [
            e
            for e in events
            if e["event_type"] == "protocol_in" and e["event_seq"] < start["event_seq"]
        ]
        subsequent = [
            e["event_seq"]
            for e in events
            if e["event_type"] == "protocol_in" and e["event_seq"] > start["event_seq"]
        ]
        rows.append(
            dict(
                key=slot["slot_id"] + ":" + str(seq),
                slot_id=slot["slot_id"],
                attempt=1,
                actor=slot["A_role"],
                decision_seq=seq,
                showdown_turn=start["showdown_turn"],
                task=slot["task"],
                team_assignment=slot["team_assignment"],
                bundle=str(bundle),
                events_sha256=checksum,
                bundle_valid=bundle_valid,
                unparsed_event_lines=parse_errors,
                decision_start=start,
                calls=calls,
                input_snapshots=[e for e in related if e["event_type"] == "input_snapshot"],
                call_status=(
                    "not_dispatched"
                    if calls
                    and all(
                        c.get("response", {}).get("network_called") is False
                        for c in calls
                    )
                    else "called"
                    if calls
                    else "not_called"
                ),
                results=results,
                wires=wires,
                prefix_last_event_seq=prefix[-1]["event_seq"] if prefix else None,
                subsequent_public_event_seqs=subsequent,
                review_status="unreviewed",
            )
        )
    return rows


def summarize(matches):
    counts = Counter(m["status"] for m in matches)
    n = counts["valid_completed"]
    wins = sum(
        m.get("outcome") == "player_won"
        for m in matches
        if m["status"] == "valid_completed"
    )
    draws = sum(
        m.get("outcome") == "tied" for m in matches if m["status"] == "valid_completed"
    )
    return dict(
        planned=len(matches),
        attempted=len(matches) - counts["not_run"],
        valid_completed=n,
        failed=counts["failed"],
        invalid=counts["invalid"],
        not_run=counts["not_run"],
        wins=wins,
        losses=n - wins - draws,
        draws=draws,
        win_rate=wins / n if n else None,
        draw_adjusted_score=(wins + 0.5 * draws) / n if n else None,
    )


def observed_attempts(directory, value):
    """Report interrupted slots conservatively, retaining orphan actor event streams."""
    attempts = []
    claim_path = directory / "run-claim.json"
    claim = b.read_sealed(claim_path) if claim_path.exists() else {}
    for slot in value["schedule"]:
        target = directory / "attempts" / (slot["slot_id"] + "-a1")
        if not target.exists():
            continue
        errors = []
        result_path = target / "result.json"
        if result_path.exists():
            try:
                attempt = b.read_sealed(result_path)
                if attempt.get("slot") != slot or attempt.get("number") != 1:
                    errors.append("attempt_identity_mismatch")
                for name, checksum in attempt.get("source_checksums", {}).items():
                    if b.digest(target / name) != checksum:
                        errors.append("attempt_source_mismatch:" + name)
            except (OSError, ValueError, RuntimeError, KeyError):
                attempt = {}
                errors.append("attempt_result_integrity")
        else:
            attempt = {}
        complete = bool(attempt)
        try:
            request = b.read_sealed(target / "request.json")
            if request["slot"] != slot:
                errors.append("request_slot_mismatch")
        except (OSError, ValueError, RuntimeError, KeyError):
            request = {}
            errors.append("request_unavailable")
        actors = dict(attempt.get("actors", {}))
        data_root = request.get("data_root") or claim.get("data_root")
        for role in ("p1", "p2"):
            actor = dict(actors.get(role, {}))
            if not actor.get("bundle") and data_root:
                bundle = (
                    Path(data_root)
                    / "experiments"
                    / value["experiment_id"]
                    / "battles"
                    / (target.name + "-" + role)
                )
                if (bundle / "events.jsonl").exists():
                    actor["bundle"] = str(bundle)
                    actor["partial_evidence"] = True
            if actor.get("bundle"):
                actor["bundle_valid"] = b.verify_bundle(actor["bundle"])["valid"]
                if attempt.get("eligible") and not actor["bundle_valid"]:
                    errors.append("eligible_actor_bundle_integrity:" + role)
            elif attempt.get("eligible"):
                errors.append("eligible_actor_missing:" + role)
            actors[role] = actor
        attempts.append(
            dict(
                attempt,
                slot=slot,
                slot_id=slot["slot_id"],
                attempt_id=target.name,
                number=1,
                actors=actors,
                duration_seconds=attempt.get("duration_seconds"),
                eligible=bool(attempt.get("eligible")) and not errors,
                category=attempt.get("category") if complete else "outcome_unconfirmed",
                report_status="invalid"
                if errors
                else "valid_completed"
                if attempt.get("eligible")
                else "failed",
                integrity_errors=errors,
            )
        )
    return attempts


def attach_journal(directory, value, decisions):
    """Link committed requests even when an actor died before emitting llm_call."""
    import sqlite3
    from datetime import datetime

    by_actor = defaultdict(list)
    for decision in decisions:
        actor = "/".join(
            (value["experiment_id"], decision["slot_id"] + "-a1", decision["actor"])
        )
        decision["journal_references"] = []
        decision["journal_only_requests"] = []
        by_actor[actor].append(decision)
    unlinked = []
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        reservations = db.execute(
            "SELECT number,actor,reserved_at,payload FROM reservations ORDER BY number"
        ).fetchall()
    for number, actor, at, encoded in reservations:
        intent_path = directory / "requests" / f"intent-{number:06}.json"
        response_path = directory / "requests" / f"response-{number:06}.json"
        reference = dict(
            number=number,
            reserved_at=at,
            actor=actor,
            intent=str(intent_path) if intent_path.exists() else None,
            intent_sha256=b.digest(intent_path) if intent_path.exists() else None,
            response=str(response_path) if response_path.exists() else None,
            response_sha256=b.digest(response_path) if response_path.exists() else None,
        )
        candidates = by_actor.get(actor, [])
        exact = next(
            (
                d
                for d in candidates
                if any(
                    (c.get("request", {}).get("request_intent") == str(intent_path)
                     or any(a.get("request_intent") == str(intent_path)
                            for a in c.get("request", {}).get("http_attempts", [])))
                    for c in d["calls"]
                )
            ),
            None,
        )
        if exact is not None:
            exact["journal_references"].append(
                dict(reference, link_basis="exact_intent_reference")
            )
            continue
        earlier = []
        for decision in candidates:
            stamp = decision["decision_start"].get("timestamp_utc")
            if (
                stamp
                and datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
                <= at
            ):
                earlier.append(decision)
        payload = json.loads(encoded)
        recovered = dict(
            reference,
            payload=payload,
            raw_response=b.read_sealed(response_path)["response"]
            if response_path.exists()
            else None,
            dispatch_status="response_received"
            if response_path.exists()
            else "unconfirmed",
        )
        if earlier:
            decision = max(earlier, key=lambda d: d["decision_start"]["event_seq"])
            decision["journal_references"].append(
                dict(reference, link_basis="actor_and_decision_time_interval")
            )
            decision["journal_only_requests"].append(recovered)
            if not decision["calls"]:
                decision["call_status"] = (
                    "called" if response_path.exists() else "dispatch_unconfirmed"
                )
        else:
            unlinked.append(recovered)
    return unlinked


def build_report(directory):
    directory = Path(directory).resolve()
    from .a_diagnostic import usage, verify_prepared

    value = verify_prepared(directory, current=False)
    attempts = observed_attempts(directory, value)
    by_slot = {a["slot_id"]: a for a in attempts}
    invalidations = (
        b.read_sealed(directory / "invalidations.json")
        if (directory / "invalidations.json").exists()
        else {}
    )
    if set(invalidations) - set(by_slot):
        raise ValueError("invalidation must identify an attempted slot")
    matches, decisions = [], []
    stop = (
        b.read_sealed(directory / "halt.json")["category"]
        if (directory / "halt.json").exists()
        else None
    )
    for slot in value["schedule"]:
        attempt = by_slot.get(slot["slot_id"])
        row = dict(
            slot,
            status="not_run",
            reason=stop or "not_dispatched",
            outcome=None,
            viewer=None,
            duration_seconds=None,
            turns=None,
            original_terminal_category=None,
            source_directory=None,
            integrity_errors=[],
        )
        if attempt:
            actor = attempt["actors"].get(slot["A_role"], {})
            row.update(
                status=attempt["report_status"],
                reason=attempt["category"],
                outcome=actor.get("outcome"),
                duration_seconds=attempt["duration_seconds"],
                turns=actor.get("turns"),
            )
            row["original_terminal_category"] = attempt["category"]
            row["integrity_errors"] = attempt["integrity_errors"]
            if slot["slot_id"] in invalidations:
                row.update(status="invalid", reason=invalidations[slot["slot_id"]])
            if actor.get("bundle"):
                from .observability.render import rebuild_battle

                row["source_directory"] = actor["bundle"]
                if actor.get("bundle_valid"):
                    rebuild_battle(actor["bundle"])
                    row["viewer"] = str(Path(actor["bundle"]) / "report.html")
                decisions.extend(inventory(slot, actor))
        matches.append(row)
    grouped = defaultdict(list)
    for row in matches:
        grouped[(row["opponent_policy"], row["team_assignment"], row["task"])].append(
            row
        )
    stream_errors = {
        row["source_directory"]: read_events(row["source_directory"])[1]
        for row in matches
        if row["source_directory"]
    }
    unlinked_requests = attach_journal(directory, value, decisions)
    annotations = {}
    review_path = directory / "review.json"
    if review_path.exists():
        annotations = b.read_sealed(review_path)
        if set(annotations) - {d["key"] for d in decisions}:
            raise ValueError("review refers to unknown decision")
    for decision in decisions:
        if decision["key"] in annotations:
            annotation = annotations[decision["key"]]
            if annotation.get("events_sha256") != decision[
                "events_sha256"
            ] or not annotation.get("rationale"):
                raise ValueError("review evidence/rationale missing")
            decision["review"] = annotation
            decision["review_status"] = "reviewed"
    result = dict(
        **summarize(matches),
        collection_complete=sum(m["status"] == "valid_completed" for m in matches)
        == 64,
        usage=usage(directory),
        decisions=len(decisions),
        unlinked_requests=len(unlinked_requests),
        journal_only_requests=sum(len(d["journal_only_requests"]) for d in decisions),
        unparsed_event_lines=sum(len(lines) for lines in stream_errors.values()),
        source_parse_errors={
            path: lines for path, lines in stream_errors.items() if lines
        },
        dispatch_unconfirmed_decisions=sum(
            d["call_status"] == "dispatch_unconfirmed" for d in decisions
        ),
        reviewed=sum(d["review_status"] == "reviewed" for d in decisions),
        cells=[
            dict(opponent_policy=k[0], team_assignment=k[1], task=k[2], **summarize(v))
            for k, v in sorted(grouped.items())
        ],
        call_decisions=sum(d["call_status"] == "called" for d in decisions),
        no_call_decisions=sum(
            d["call_status"] in ("not_called", "not_dispatched") for d in decisions
        ),
        multiple_call_decisions=sum(len(d["calls"]) > 1 for d in decisions),
        transmitted_decisions=sum(
            any(w["send_status"] == "sent" for w in d["wires"]) for d in decisions
        ),
    )
    output = directory / "reports" / f"report-{__import__('time').time_ns()}"
    output.mkdir(parents=True)
    b.seal_json(output / "summary.json", result)
    b.seal_json(output / "matches.json", matches)
    b.seal_json(output / "unlinked-requests.json", unlinked_requests)
    with (output / "decisions.jsonl").open("w") as stream:
        for row in decisions:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output / "decisions.jsonl.sha256").write_text(
        b.digest(output / "decisions.jsonl") + "\n"
    )
    with (output / "matches.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(matches[0]))
        writer.writeheader()
        writer.writerows(matches)
    table = "".join(
        "<tr>"
        + "".join(
            "<td>" + html.escape(str(row[k])) + "</td>"
            for k in ("submission_order", "slot_id", "status", "reason", "outcome")
        )
        + "<td>"
        + (
            '<a href="' + html.escape(row["viewer"], quote=True) + '">viewer</a>'
            if row["viewer"]
            else ""
        )
        + "</td></tr>"
        for row in matches
    )
    (output / "matches.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>EX-035 64경기</title><h1>EX-035 64경기 상태</h1><table><tr><th>순서</th><th>경기</th><th>상태</th><th>사유</th><th>결과</th><th>기록</th></tr>'
        + table
        + "</table>"
    )
    (output / "report.md").write_text(
        "# EX-035 원본 A64 진단\n\n"
        + f"예정64·시도{result['attempted']}·유효완료{result['valid_completed']}·실패{result['failed']}·무효{result['invalid']}·미실행{result['not_run']}.\n\n"
        + f"A 결정{len(decisions)}개, 검토{result['reviewed']}개. 미검토는 정상 판단의 증거가 아니다.\n\n"
        + f"요청{result['usage']['reserved_calls']}·응답{result['usage']['responses']}·미확정{result['usage']['uncertain']}.\n\n"
        + "실제 입력·전체 원응답·선택 출처·전송·공개prefix 연결은 decisions.jsonl, 대진은 matches.html을 참조한다.\n"
    )
    result["report_directory"] = str(output)
    return result
