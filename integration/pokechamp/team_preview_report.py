"""EX-039 technical evidence and predeclared matched denominators; no annotation."""

from __future__ import annotations

import html
import json
import math
import sqlite3
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import benchmark as b
from . import team_preview_study as study
from .a_diagnostic_report import (
    attach_journal,
    inventory,
    observed_attempts,
    read_events,
    summarize,
)
from .diagnostics.team_preview import (
    audit,
    check_decision_resolution,
    check_executed_wire,
    check_request_settings,
)
from .improved_io.inputfix32 import verify_runtime
from .improved_io.live_delivery import original_for_call
from .improved_io.output import validate_exact_action
from .observability.render import rebuild_battle


def distribution(values):
    values = sorted(v for v in values if isinstance(v, (int, float)))
    return dict(
        n=len(values),
        median=statistics.median(values) if values else None,
        p95=values[math.ceil(0.95 * len(values)) - 1] if values else None,
        maximum=max(values) if values else None,
        p95_method="nearest_rank",
    )


def paired_scores(matches):
    pairs = defaultdict(list)
    for row in matches:
        pairs[row["paired_slot_id"]].append(row)
    result = []
    for pair, rows in sorted(pairs.items()):
        valid = [r for r in rows if r["status"] == "valid_completed"]
        complete = len(rows) == len(valid) == 2 and {r["swap"] for r in rows} == {0, 1}
        scores = [{"player_won": 1, "tied": 0.5, "player_lost": 0}[r["outcome"]] for r in valid]
        result.append(
            dict(
                paired_slot_id=pair,
                complete=complete,
                valid_games=len(valid),
                llm_score_mean=sum(scores) / 2 if complete else None,
                missing=[
                    dict(slot_id=r["slot_id"], status=r["status"], reason=r["reason"])
                    for r in rows
                    if r["status"] != "valid_completed"
                ],
            )
        )
    return result


def check_lead_input(call, snapshots, expected, selected):
    """Use the sealed lead version; enriched calls also verify their original/wire link."""
    from .team_preview import PROMPT, prompt_identity

    if (
        selected != prompt_identity(selected)
        or call["request"]["team_preview_prompt_identity"] != selected
        or original_for_call(call, snapshots) != expected
        or (selected["version"] == "v1.0.0" and call["system_prompt"] != PROMPT.read_text())
    ):
        raise ValueError("lead_information_boundary")


def technical_inventory(slot, actor, role, prepared):
    """Audit every retained call, including failed matches, without rating explanations."""
    from .distributed_lead import selected
    prepared = selected(prepared, slot)
    bundle = Path(actor["bundle"])
    events, parse_errors = read_events(bundle)
    errors = ["unparsed_event_line:" + str(n) for n in parse_errors]
    if not b.verify_bundle(bundle)["valid"]:
        errors.append("bundle_integrity")
    manifest = json.loads((bundle / "manifest.json").read_text())
    meta = manifest["metadata"]
    if meta.get("actor_id") != role or meta.get("slot_id") != slot["slot_id"]:
        errors.append("actor_slot_identity")
    if meta.get("python_random_seed") != slot["actor_seeds"][int(role[-1]) - 1]:
        errors.append("actor_seed")
    if meta.get("team_preview_policy") != study.actor_policy(slot, role, prepared):
        errors.append("lead_policy_identity")
    snapshots = {e["event_seq"]: e for e in events if e["event_type"] == "input_snapshot"}
    calls = [e for e in events if e["event_type"] == "llm_call"]
    seen = set()
    for call in calls:
        try:
            req = call["request"]
            check_request_settings(req, prepared)
            from .transport_policy import audit_attempts

            audit_attempts(call, actor="/".join(
                (prepared["experiment_id"], slot["slot_id"] + "-a1", role)))
            path = req.get("request_intent")
            if path:
                if path in seen:
                    raise ValueError("duplicate_intent_reference")
                seen.add(path)
                intent = b.read_sealed(path)
                expected_actor = "/".join(
                    (prepared["experiment_id"], slot["slot_id"] + "-a1", role)
                )
                if intent["actor"] != expected_actor:
                    raise ValueError("cross_actor_intent")
                for key in ("system_prompt", "user_prompt"):
                    if intent["payload"][key] != call[key]:
                        raise ValueError("ledger_trace_prompt")
                response = Path(path).with_name(Path(path).name.replace("intent-", "response-"))
                if response.exists():
                    raw = b.read_sealed(response)["response"]
                    if raw["message"]["content"] != call["raw_content"]:
                        raise ValueError("ledger_trace_response")
                    if raw["message"].get("thinking") != call.get("provider_reasoning"):
                        raise ValueError("ledger_trace_reasoning")
                elif call.get("response", {}).get("prompt_tokens") is not None:
                    raise ValueError("missing_preserved_response")
            elif call.get("response", {}).get("network_called") is not False:
                raise ValueError("http_without_intent")
            if req["call_role"] == "self_action":
                full = original_for_call(call, snapshots)
                verify_runtime(req, context=full)
                if full["identity"]["actor_id"] != role or full["condition_id"] != "B":
                    raise ValueError("B2_actor_input")
                resolution = call.get("validation", {}).get("action_resolution")
                if resolution:
                    results = [e for e in events if e["event_type"] == "decision_result"
                               and e["decision_seq"] == call["decision_seq"] and e["success"]]
                    # A failed peer may cancel after a response, before action execution.
                    if results:
                        check_decision_resolution(results, resolution)
                        if full["identity"].get("observation_version") == "official-client-v1":
                            from .observation.normalize import SlotCandidates
                            observed = [e for e in events if e["event_type"] == "observation_snapshot"
                                        and e["decision_seq"] == call["decision_seq"]]
                            if len(observed) != 1 or SlotCandidates(observed[0]["official_state"]["candidates"]).order(
                                    resolution["executed_action"]).message != results[0]["selected_action"]:
                                raise ValueError("official_slot_submission_mismatch")
                        else:
                            check_executed_wire(resolution["executed_action"], results[0]["selected_action"])
                    validate_exact_action(
                        resolution["executed_action"],
                        full["request"]["legal_actions"],
                        request_kind=full["request"]["kind"],
                        can_tera=full["request"]["can_tera"],
                    )
            elif req["call_role"] == "team_preview":
                from .team_preview import (
                    build_input,
                    parse_lead,
                )

                own = next(t["showdown_team"] for t in manifest["teams"] if t["role"] == "player")
                public = [e for e in events if e["event_type"] == "protocol_in"]
                expected = build_input(
                    own,
                    public,
                    battle_id=manifest["battle_id"],
                    actor_id=role,
                    decision_seq=call["decision_seq"],
                )
                check_lead_input(call, snapshots, expected, prepared["team_preview_prompt_identity"])
                if call["validation"].get("output_contract_valid") is True:
                    parse_lead(call["raw_content"], list(range(1, 7)))
            else:
                raise ValueError("unexpected_call_role")
        except Exception as exc:
            errors.append(f"call:{call['event_seq']}:{type(exc).__name__}:{exc}")
    enriched = dict(slot, A_role=role, task="lead_policy_comparison", team_assignment=slot["swap"])
    decisions = inventory(enriched, actor)
    for decision in decisions:
        decision["key"] = slot["slot_id"] + ":" + role + ":" + str(decision["decision_seq"])
        decision["condition_id"] = study.actor_policy(slot, role, prepared)
        for result in decision["results"]:
            if not result.get("success"):
                continue
            wires = [w for w in decision["wires"] if w["send_status"] == "sent"]
            if wires and (len(wires) != 1 or wires[0]["action"] != result["selected_action"]):
                errors.append("selected_wire_mismatch:" + str(decision["decision_seq"]))
    preview_calls = [c for c in calls if c["request"].get("call_role") == "team_preview"]
    preview_wires = [
        e for e in events if e["event_type"] == "wire_action" and e["action"].startswith("/team ")
    ]
    if len(preview_calls) > 1 or len(preview_wires) > 1:
        errors.append("duplicate_lead_call_or_send")
    preview_notifications = sum(
        line.startswith("|teampreview|")
        for e in events
        if e["event_type"] == "protocol_in"
        for line in e["protocol"].splitlines()
    )
    lead = dict(
        policy=study.actor_policy(slot, role, prepared),
        calls=len(preview_calls),
        output_valid=sum(
            c["validation"].get("output_contract_valid") is True for c in preview_calls
        ),
        transmitted=sum(w["send_status"] == "sent" for w in preview_wires),
        send_failed=sum(w["send_status"] != "sent" for w in preview_wires),
        duplicate_preview_notifications=max(0, preview_notifications - 1),
        duplicate_calls=max(0, len(preview_calls) - 1),
        duplicate_sends=max(0, len(preview_wires) - 1),
    )
    return decisions, dict(
        bundle=str(bundle), role=role, errors=errors, calls=len(calls), lead=lead
    )


def usage(directory, prepared, decisions, *, provider_id=None):
    actor_conditions = {
        "/".join((prepared["experiment_id"], row["slot_id"] + "-a1", role)): study.actor_policy(
            row, role, prepared
        )
        for row in prepared["schedule"]
        for role in ("p1", "p2")
    }
    trace = {}
    logical_calls = []
    for decision in decisions:
        for call in decision["calls"]:
            if provider_id and call["request"].get("provider") != provider_id:
                continue
            logical_calls.append((decision["condition_id"], call))
            request = call["request"]
            attempts = request.get("http_attempts")
            if attempts is None:
                if request.get("request_intent"):
                    trace[request["request_intent"]] = call
            else:
                for attempt in attempts:
                    if attempt.get("request_intent"):
                        trace[attempt["request_intent"]] = dict(
                            call, response=attempt, status=attempt["status"],
                            validation={"category": attempt.get("category")},
                        )
    groups, requests = {}, []
    for condition in ("seeded_random", "llm_lead"):
        for role in ("team_preview", "self_action"):
            groups[condition + "/" + role] = dict(
                condition=condition,
                call_role=role,
                reserved=0,
                logical_requests=0,
                logical_reserved=0,
                logical_status_counts=Counter(),
                known_connection_failures=0,
                http_attempted=0,
                dispatch_unconfirmed=0,
                responses=0,
                uncertain_requests=0,
                input_tokens=0,
                output_tokens=0,
                token_usage_unconfirmed=0,
                confirmed_cost=None,
                currency="USD",
                cost_status="provider_billing_not_exposed",
                permit_wait_ms=[],
                http_elapsed_ms=[],
                elapsed_ms=[],
                decision_ms=[],
                errors=Counter(),
            )
    for condition, call in logical_calls:
        group = groups[condition + "/" + call["request"]["call_role"]]
        group["logical_requests"] += 1
        group["logical_status_counts"][call["status"]] += 1
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        rows = db.execute(
            "SELECT number,actor,reserved_at,payload FROM reservations ORDER BY number"
        ).fetchall()
    reserved_logical = set()
    for number, actor, reserved_at, encoded in rows:
        payload = json.loads(encoded)
        if provider_id and payload["request"].get("provider") != provider_id:
            continue
        role = payload["request"]["call_role"]
        item = groups[actor_conditions[actor] + "/" + role]
        item["reserved"] += 1
        logical = (actor, payload["request"].get("logical_request_id", number))
        if logical not in reserved_logical:
            item["logical_reserved"] += 1
            reserved_logical.add(logical)
        path = directory / "requests" / f"intent-{number:06}.json"
        if path.exists():
            intent = b.read_sealed(path)
            if (intent["actor"], intent["reserved_at"], intent["payload"]) != (
                actor,
                reserved_at,
                payload,
            ):
                raise ValueError("ledger_intent_mismatch")
        call = trace.get(str(path))
        response_path = directory / "requests" / f"response-{number:06}.json"
        raw = b.read_sealed(response_path)["response"] if response_path.exists() else None
        if raw is not None:
            item["responses"] += 1
            input_tokens, output_tokens = raw.get("prompt_eval_count"), raw.get("eval_count")
            if type(input_tokens) is int and input_tokens >= 0:
                item["input_tokens"] += input_tokens
            if type(output_tokens) is int and output_tokens >= 0:
                item["output_tokens"] += output_tokens
            if not (type(input_tokens) is int and input_tokens >= 0
                    and type(output_tokens) is int and output_tokens >= 0):
                item["token_usage_unconfirmed"] += 1
        else:
            item["uncertain_requests"] += 1
            item["token_usage_unconfirmed"] += 1
        proof_path = path.with_name(path.name.replace("intent-", "attempt-"))
        proof = b.read_sealed(proof_path) if proof_path.exists() else {}
        observed = (call or {}).get("response", proof)
        if proof.get("connection_retryable"):
            item["known_connection_failures"] += 1
        network = observed.get("network_called")
        if raw is not None or network is True:
            item["http_attempted"] += 1
        elif network is not False:
            item["dispatch_unconfirmed"] += 1
        if call:
            for key in ("permit_wait_ms", "http_elapsed_ms", "elapsed_ms"):
                item[key].append(call.get("response", {}).get(key))
            if call["status"] == "failure":
                item["errors"][call.get("validation", {}).get("category") or "output_contract"] += 1
        requests.append(
            dict(
                number=number,
                provider_id=payload["request"].get("provider", "ollama"),
                actor=actor,
                call_role=role,
                intent=str(path),
                response=str(response_path) if raw is not None else None,
                trace_event_seq=call["event_seq"] if call else None,
                logical_request_id=payload["request"].get("logical_request_id"),
                http_attempt_number=payload["request"].get("http_attempt_number", 1),
                attempt_status=observed.get("status"),
                dispatch_unconfirmed=network is None and raw is None,
            )
        )
    provider_slots = {r["slot_id"] for r in prepared["schedule"] if r.get("provider_id") == provider_id}
    for decision in decisions:
        if provider_id and decision["slot_id"] not in provider_slots:
            continue
        kind = (
            "team_preview"
            if decision["decision_start"]["decision_kind"] == "team_preview"
            else "self_action"
        )
        item = groups[decision["condition_id"] + "/" + kind]
        ends = decision["wires"] or decision["results"]
        if ends:
            item["decision_ms"].append(
                max(e["monotonic_offset_ms"] for e in ends)
                - decision["decision_start"]["monotonic_offset_ms"]
            )
    for item in groups.values():
        for key in ("permit_wait_ms", "http_elapsed_ms", "elapsed_ms", "decision_ms"):
            item[key] = distribution(item[key])
        item["errors"] = dict(item["errors"])
        item["logical_status_counts"] = dict(item["logical_status_counts"])
        # List-price range only. Cache split and actual account debits are absent.
        item["listed_token_cost_usd_range"] = [
            (item["input_tokens"] * rate + item["output_tokens"] * 0.50) / 1_000_000
            for rate in (0.03, 0.15)
        ]
        item["cost_basis"] = "https://ollama.com/pricing; 2026-09-14; received tokens only"
        if (provider_id or prepared.get("provider_config", {}).get("provider", "ollama")) != "ollama" or (prepared.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046") ):
            item["listed_token_cost_usd_range"] = None
            item["cost_basis"] = None
        if prepared["transport"] == "fake":
            item["confirmed_cost"], item["cost_status"] = 0, "local_fake_no_provider_charge"
            item["listed_token_cost_usd_range"] = None
    return list(groups.values()), requests


def build_report(directory):
    directory = Path(directory).resolve()
    prepared = study.verify_prepared(directory, current=False)
    attempts = observed_attempts(directory, prepared)
    by_slot = {a["slot_id"]: a for a in attempts}
    for slot in prepared["schedule"]:
        dispatch = directory / "dispatch" / (slot["slot_id"] + ".json")
        if dispatch.exists() and slot["slot_id"] not in by_slot:
            b.read_sealed(dispatch)
            orphan = dict(
                slot=slot,
                slot_id=slot["slot_id"],
                eligible=False,
                category="outcome_unconfirmed",
                report_status="invalid",
                actors={"p1": {}, "p2": {}},
                duration_seconds=None,
                integrity_errors=["dispatched_attempt_evidence_missing"],
            )
            attempts.append(orphan)
            by_slot[slot["slot_id"]] = orphan
    halt = b.read_sealed(directory / "halt.json") if (directory / "halt.json").exists() else {}
    stop = halt.get("category")
    invalidations = (
        b.read_sealed(directory / "invalidations.json")
        if (directory / "invalidations.json").exists()
        else {}
    )
    if set(invalidations) - set(by_slot):
        raise ValueError("invalidation_of_unattempted_slot")
    matches, decisions, technical = [], [], []
    for slot in prepared["schedule"]:
        attempt = by_slot.get(slot["slot_id"])
        llm_role = next(
            role for role in ("p1", "p2") if study.actor_policy(slot, role, prepared) == "llm_lead"
        )
        row = dict(
            slot,
            llm_role=llm_role,
            status="not_run",
            reason=stop or "not_dispatched",
            outcome=None,
            actors={},
            duration_seconds=None,
            integrity_errors=[],
        )
        if attempt:
            row.update(
                status=attempt["report_status"],
                reason=attempt["category"],
                outcome=attempt["actors"][llm_role].get("outcome"),
                duration_seconds=attempt["duration_seconds"],
                integrity_errors=attempt["integrity_errors"],
            )
            for role, actor in attempt["actors"].items():
                row["actors"][role] = dict(actor)
                if not actor.get("bundle"):
                    continue
                actor_decisions, check = technical_inventory(slot, actor, role, prepared)
                decisions.extend(actor_decisions)
                technical.append(dict(slot_id=slot["slot_id"], **check))
                row["integrity_errors"].extend(check["errors"])
                if actor.get("bundle_valid"):
                    rebuild_battle(actor["bundle"])
                    row["actors"][role]["viewer"] = str(Path(actor["bundle"]) / "report.html")
            if attempt["eligible"]:
                try:
                    row["valid_match_audit"] = audit([attempt], prepared, directory)
                except Exception as exc:
                    row["integrity_errors"].append(
                        "valid_match_audit:" + type(exc).__name__ + ":" + str(exc)
                    )
            if prepared.get("registered_experiment") in ("EX-043", "EX-044", "EX-045", "EX-046"):
                from .diagnostics.corrected_lead import read_receipt
                try:
                    receipt = read_receipt(directory, slot["slot_id"] + "-a1")
                    row["input_audit"] = receipt
                    if not receipt["passed"]:
                        row["integrity_errors"].append("input_audit_failed")
                except Exception as exc:
                    row["integrity_errors"].append("input_audit_missing_or_invalid:" + str(exc))
            if row["integrity_errors"]:
                row.update(status="invalid", reason="technical_integrity")
            if slot["slot_id"] in invalidations:
                row.update(status="invalid", reason=invalidations[slot["slot_id"]])
        matches.append(row)
    unlinked = attach_journal(directory, prepared, decisions)
    condition_usage, requests = usage(directory, prepared, decisions)
    pairs = paired_scores(matches)
    complete = [p["llm_score_mean"] for p in pairs if p["complete"]]
    conditions = {}
    for condition in ("llm_lead", "seeded_random"):
        rows = []
        for row in matches:
            outcome = row["outcome"]
            if condition == "seeded_random":
                outcome = {
                    "player_won": "player_lost",
                    "player_lost": "player_won",
                    "tied": "tied",
                }.get(outcome)
            rows.append(dict(row, outcome=outcome))
        conditions[condition] = summarize(rows)
    cells = []
    for block in sorted({r["block_id"] for r in matches}):
        for role in ("p1", "p2"):
            subset = [r for r in matches if r["block_id"] == block and r["llm_role"] == role]
            cells.append(
                dict(
                    block_id=block,
                    llm_role=role,
                    llm_lead=summarize(subset),
                    seeded_random=summarize(
                        [
                            dict(
                                r,
                                outcome={
                                    "player_won": "player_lost",
                                    "player_lost": "player_won",
                                    "tied": "tied",
                                }.get(r["outcome"]),
                            )
                            for r in subset
                        ]
                    ),
                )
            )
    result = dict(
        experiment=study.execution_protocol(prepared)["experiment"],
        transport=prepared["transport"],
        **summarize(matches),
        conditions=conditions,
        block_seat_cells=cells,
        planned_pairs=16,
        completed_pairs=len(complete),
        completed_pair_llm_score=sum(complete) / len(complete) if complete else None,
        pairs=pairs,
        usage=condition_usage,
        outcome_unconfirmed=sum(a["category"] == "outcome_unconfirmed" for a in attempts),
        unlinked_requests=len(unlinked),
        technical_errors=sum(len(t["errors"]) for t in technical),
        match_duration_seconds=distribution([m["duration_seconds"] for m in matches]),
        error_categories=dict(Counter(a["category"] for a in attempts if a["category"])),
        explanation_accuracy="not_evaluated_C032",
        strategic_optimality="not_evaluated",
        source_files=prepared["parent_files"],
        model=prepared["model"],
        source=prepared["source"],
        policy=prepared["experiment_policy_identity"],
        execution_protocol=study.execution_protocol(prepared),
        schedule_sha256=study.digest(prepared["schedule"]),
        teams=prepared["teams"],
        prompt=prepared["team_preview_prompt_identity"],
    )
    lead_checks = [t["lead"] for t in technical if t["lead"]["policy"] == "llm_lead"]
    lead_usage = next(
        u
        for u in condition_usage
        if u["condition"] == "llm_lead" and u["call_role"] == "team_preview"
    )
    result["lead_funnel"] = dict(
        planned=32,
        reserved=lead_usage["reserved"],
        logical_requests=lead_usage["logical_requests"],
        http_attempted=lead_usage["http_attempted"],
        dispatch_unconfirmed=lead_usage["dispatch_unconfirmed"],
        responses=lead_usage["responses"],
        output_valid=sum(t["output_valid"] for t in lead_checks),
        transmitted=sum(t["transmitted"] for t in lead_checks),
        selection_failed=len(attempts) - sum(t["transmitted"] for t in lead_checks),
        not_run=32 - len(attempts),
        requests_not_reserved=32 - lead_usage["logical_reserved"],
        duplicate_calls=sum(t["duplicate_calls"] for t in lead_checks),
        duplicate_sends=sum(t["duplicate_sends"] for t in lead_checks),
        duplicate_preview_notifications=sum(
            t["duplicate_preview_notifications"] for t in lead_checks
        ),
    )
    result["denominator_invariants"] = (
        result["planned"] == result["attempted"] + result["not_run"]
        and result["attempted"] == result["valid_completed"] + result["failed"] + result["invalid"]
    )
    result["collection_complete"] = (
        result["valid_completed"] == 32
        and len(complete) == 16
        and not result["technical_errors"]
        and not unlinked
    )
    clock = directory / "cloud-clock.json"
    batch = directory / "batch.json"
    if clock.exists():
        result["clock"] = b.read_sealed(clock)
    if batch.exists():
        batch_record = b.read_sealed(batch)
        result["batch_finished_at"] = batch_record["finished_at"]
        if clock.exists():
            result["elapsed_from_first_request_seconds"] = (
                batch_record["finished_at"] - result["clock"]["first_dispatch_at"]
            )
    result["technical_consistency"] = dict(
        valid_match_audits=sum("valid_match_audit" in m for m in matches),
        valid_actor_lead_first_switch_checks=sum(
            len(m.get("valid_match_audit", {}).get("actors", [])) for m in matches
        ),
        actor_bundles=len(technical),
        checked_calls=sum(t["calls"] for t in technical),
        failed_or_invalid_actor_evidence_preserved=True,
    )
    if prepared.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
        from .distributed_lead_report import completion_controls, provider_summary
        result["execution_controls"] = completion_controls(directory)
        result["collection_complete"] = result["collection_complete"] and all(result["execution_controls"].values())
        result["providers"] = provider_summary(directory, prepared, matches, decisions)
        result["budget"] = study.shared.usage(directory)
    if prepared.get("registered_experiment") in ("EX-045", "EX-046"):
        from .diagnostics.official_observation import statistics_for
        trackers = [a.get("io_runtime", {}).get("official_observation")
                    for attempt in attempts for a in attempt["actors"].values()]
        trackers = [t for t in trackers if t]
        operations = [op for t in trackers for op in t["operations"]]
        result["official_observation"] = dict(
            actors=len(trackers), all_closed=all(t["closed"] for t in trackers),
            processing_ms=statistics_for([op["elapsed_ms"] for op in operations]),
            node_rss_bytes=statistics_for([op["rss_bytes"] for op in operations]),
            actor_peak_rss_bytes=statistics_for([t["actor_peak_rss_bytes"] for t in trackers]),
            build_verification_ms=statistics_for([t["build_verification_ms"] for t in trackers]),
        )
    output = directory / "reports" / f"report-{time.time_ns()}"
    output.mkdir(parents=True)
    for name, value in [
        ("summary", result),
        ("matches", matches),
        ("technical", technical),
        ("requests", requests),
        ("unlinked-requests", unlinked),
    ]:
        b.seal_json(output / (name + ".json"), value)
    with (output / "decisions.jsonl").open("w") as stream:
        for decision in decisions:
            stream.write(json.dumps(decision, ensure_ascii=False) + "\n")
    (output / "decisions.jsonl.sha256").write_text(b.digest(output / "decisions.jsonl") + "\n")
    table = []
    for row in matches:
        links = " ".join(
            '<a href="' + html.escape(a["viewer"], quote=True) + '">' + role + "</a>"
            for role, a in row["actors"].items()
            if a.get("viewer")
        )
        table.append(
            "<tr>"
            + "".join(
                "<td>" + html.escape(str(row[k])) + "</td>"
                for k in ("slot_id", "llm_role", "status", "reason", "outcome")
            )
            + "<td>"
            + links
            + "</td></tr>"
        )
    (output / "matches.html").write_text(
        f'<!doctype html><meta charset="utf-8"><title>{result["experiment"]}</title>'
        f"<h1>{result['experiment']} 경기·양쪽 viewer</h1><table>" + "".join(table) + "</table>"
    )
    llm = conditions["llm_lead"]
    (output / "report.md").write_text(
        f"# {result['experiment']} B2 선봉 정책 대응 비교\n\n"
        + ("비교 완료" if result["collection_complete"] else "비교 미완료")
        + ". "
        + f"예정32·시도{result['attempted']}·유효{result['valid_completed']}·실패{result['failed']}"
        + f"·무효{result['invalid']}·미실행{result['not_run']}. 완료 대응쌍{len(complete)}/16.\n\n"
        + f"LLM 선봉 {llm['wins']}승 {llm['draws']}무 {llm['losses']}패, 승률 {llm['win_rate']}, "
        + f"무승부 반영 점수 {llm['draw_adjusted_score']}. "
        + f"완료쌍 동일가중 LLM 점수 {result['completed_pair_llm_score']}.\n\n"
        + f"공급자 {list(prepared['provider_configs']) if 'provider_configs' in prepared else prepared.get('provider_config', {}).get('provider', 'ollama')}. 모델 seed는 각 공급자 봉인 설정을 따른다.\n\n"
        + (f"선봉 전략 {prepared['lead_strategy']} · 규칙 {prepared['lead_rules']}. "
           + "각 구성요소 version/hash와 결합 prompt hash는 summary.json의 prompt를 참조한다.\n\n"
           if "lead_strategy" in prepared else "")
        + "조건·팀 block·진영별 결과와 분모는 summary.json, 누락쌍은 pairs, "
        + "모든 경기·viewer는 matches.html/JSON을 참조한다.\n\n"
        + "선봉·전투별 요청/token·미확정 사용량과 지연 중앙값/p95/최대는 summary.json의 usage다. "
        + "API 원응답에 실제 청구액/캐시별 과금이 없어 확정 비용은 미확정이다. "
        + "공식 단가 기반 구간은 수신 token에 대한 추정이며 미확정 요청을 포함하지 않는다. "
        + ("호출·금액 상한 없음. 남은 호출 수: 상한 없음. 공급자별 지표는 summary.json의 providers다.\n\n" if prepared.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046") else "금액 상한은 제외했고 실패·미확정 요청도8000상한에 포함했다.\n\n")
        + "원문/reasoning·B2 원본/실제 전달·선봉 선택/전송/최초 출전·기술 검사 연결은 "
        + "decisions.jsonl, technical.json, requests.json이다. "
        + "설명 정확성·전략적 최적성은 C-032에 따라 미평가이며 annotation0이다.\n\n"
        + "개발 팀의 탐색적 대응 비교이며 b02/b03은 같은 조합의 방향 반전이다. "
        + "같은 seed도 선봉 이후 전개/난수 소비가 달라진다. "
        + "과거 Ollama/EX-039·EX-038 성적은 합치지 않으며 공급자 자체 효과를 주장하지 않는다. "
        + "B/B2 동등성·압축 효과·일반 Gen9 OU·L1–L5 효능 근거가 아니다.\n\n"
        + "재검증: `PYTHONPATH=/workspace /workspace/pokechamp/.venv/bin/python "
        + f"-m integration.pokechamp.team_preview_run report --directory {directory}`\n"
    )
    return dict(
        report_directory=str(output),
        collection_complete=result["collection_complete"],
        valid_completed=result["valid_completed"],
        completed_pairs=len(complete),
        attempted=result["attempted"],
        technical_errors=result["technical_errors"],
    )
