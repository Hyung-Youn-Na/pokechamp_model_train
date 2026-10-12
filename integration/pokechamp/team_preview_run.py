"""D-053 one-shot first-pair gate and EX-039 collection on the C-033 workers."""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import fcntl
import json
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path

from . import a_diagnostic as shared
from . import benchmark as b
from . import team_preview_study as study
from .diagnostics.team_preview import audit
from .execution import validate_execution
from .parallel_server import check_ports
from .permits import PermitBroker
from .transport_policy import drain_seconds


def staged_schedule(rows):
    """The first submitted slot selects the pair; preserve all other relative order."""
    if rows and "provider_id" in rows[0]:
        pairs = {}
        for row in rows:
            pairs.setdefault(row["provider_id"], row["paired_slot_id"])
        gate = [r for r in rows if r["paired_slot_id"] == pairs[r["provider_id"]]]
        if len(rows) != 32 or len(gate) != 4:
            raise ValueError("EX-042 first four schedule")
        return gate, [r for r in rows if r not in gate]
    pair = rows[0]["paired_slot_id"]
    gate = [r for r in rows if r["paired_slot_id"] == pair]
    remaining = [r for r in rows if r["paired_slot_id"] != pair]
    if len(rows) != 32 or len(gate) != 2 or {r["swap"] for r in gate} != {0, 1}:
        raise ValueError("EX-039 first pair schedule")
    return gate, remaining


def local_eight_rows(rows):
    """The actual next dispatch wave: first four queued rows per provider."""
    remaining = staged_schedule(rows)[1]
    counts = {p: 0 for p in ('ollama', 'zai')}
    selected = []
    for row in remaining:
        provider = row['provider_id']
        if counts[provider] < 4:
            counts[provider] += 1
            selected.append(row)
    if len(selected) != 8 or set(counts.values()) != {4}:
        raise ValueError('local eight requires follow-up provider allocation 4+4')
    return selected


def verify_entry(directory, verification):
    value = study.verify_prepared(directory)
    receipt = b.read_sealed(verification)
    skipped = (
        value.get("registered_experiment") == "EX-044"
        and study.execution_protocol(value).get("preflight_status") == "skipped_by_user"
        and receipt.get("preflight_status") == "skipped_by_user"
        and receipt.get("local_passed") is False
        and receipt.get("wire_passed") is False
    )
    qualified = receipt.get("local_passed") is True and receipt.get("wire_passed") is True
    if (
        receipt.get("source_files") != value["parent_files"]
        or not (skipped or qualified)
        or receipt.get("execution_protocol") != study.execution_protocol(value)
    ):
        raise ValueError("current EX-039 local/source qualification required")
    for evidence in receipt.get("evidence", []):
        if b.digest(evidence["path"]) != evidence["sha256"]:
            raise ValueError("local verification evidence drift")
    if not receipt.get("evidence"):
        raise ValueError("local verification evidence missing")
    study.require_execution_registration(directory, value)
    return value


def inspect_pair(directory, attempts, prepared, snapshot):
    errors, technical = [], None
    expected = 4 if prepared.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046") else 2
    if len(attempts) != expected or any(not a["eligible"] for a in attempts):
        errors.append("first_pair_not_two_valid_terminations")
    try:
        valid = [a for a in attempts if a["eligible"]]
        if valid:
            technical = audit(valid, prepared, directory)
    except Exception as exc:
        errors.append("technical_integrity:" + type(exc).__name__ + ":" + str(exc))
    if sum(snapshot["active_at_close"].values()) or any(
        event["event"] == "orphan" for event in snapshot["events"]
    ):
        errors.append("permit_not_returned")
    if prepared.get("registered_experiment") in ("EX-043", "EX-044", "EX-045", "EX-046"):
        from .diagnostics.corrected_lead import read_receipt
        for attempt in attempts:
            try:
                if not read_receipt(directory, attempt["attempt_id"])["passed"]:
                    errors.append("first_four_input_audit_failed")
            except Exception as exc:
                errors.append("first_four_input_audit_missing:" + str(exc))
    calls = shared.usage(directory)
    if not errors and calls["uncertain"] > calls.get("known_retryable_failures", calls.get("known_connection_failures", 0)):
        errors.append("gate_uncertain_request")
    if technical and technical["ledger_intents"] != calls["reserved_calls"]:
        # A failed member may have requests that are outside the valid member's
        # audit; preserve them without misclassifying that provider failure.
        if all(a["eligible"] for a in attempts):
            errors.append("gate_ledger_trace_mismatch")
    return dict(
        passed=not errors,
        errors=errors,
        technical=technical,
        usage=calls,
        permits=snapshot,
        strategic_judgment_evaluated=False,
        explanation_accuracy_evaluated=False,
        checked_at=time.time(),
    )


def execute_schedule(directory, data_root, value, broker, *, worker=None, gate_check=None, local_first_four=False, local_eight=False):
    """Persist dispatch before spawning; a failed gate never releases the second stage."""
    worker = worker or b.run_attempt
    gate_check = gate_check or inspect_pair
    first, remaining = staged_schedule(value["schedule"])
    if local_first_four:
        if value.get("registered_experiment") != "EX-045" or value["transport"] != "fake":
            raise ValueError("local four requires EX-045 fake transport")
        remaining = []
    if local_eight:
        if local_first_four or value.get("registered_experiment") != "EX-045" or value["transport"] != "fake" or value.get("local_identity") != "ep058-local-eight":
            raise ValueError("local eight requires EX-045 fake transport exclusively")
        first, remaining = local_eight_rows(value["schedule"]), []
        if len(first) != 8 or any(sum(r['provider_id'] == p for r in first) != 4 for p in ('ollama', 'zai')):
            raise ValueError("local eight requires follow-up provider allocation 4+4")
    claim = directory / "run-claim.json"
    local_started = b.read_sealed(claim)["started_at"] if local_eight and claim.exists() else time.time()
    local_deadline = local_started + 1740 if local_eight else None
    configured = validate_execution(value["execution"])
    ports = list(range(8100, 8100 + configured["battle_concurrency"]))
    attempts, active, events, stop = [], {}, [], None
    pending, gate_done = list(first), local_eight

    def persist_stop(category):
        nonlocal stop
        stop = stop or category
        with shared.locked(directory):
            if not (directory / "halt.json").exists():
                b.seal_json(directory / "halt.json", dict(category=stop, at=time.time()))
        broker.stop()
        for slot, _ in active.values():
            target = directory / "attempts" / (slot["slot_id"] + "-a1")
            if target.exists():
                b.signal_cancel(target, stop)

    with futures.ThreadPoolExecutor(max_workers=len(ports)) as pool:
        try:
            while pending or active or not gate_done:
                if study.execution_protocol(value).get("first_429_halt") and (directory / "halt.json").exists():
                    persist_stop(b.read_sealed(directory / "halt.json")["category"])
                deadline = local_deadline if local_eight else study.collection_deadline(directory)
                if deadline is not None and time.time() >= deadline:
                    persist_stop("budget_stop")
                for slot, _ in active.values():
                    cancel = directory / "attempts" / (slot["slot_id"] + "-a1") / "cancel.json"
                    if cancel.exists():
                        category = json.loads(cancel.read_text())["category"]
                        if category in shared.SHARED:
                            persist_stop(category)
                if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046") and any(
                    e["event"] == "orphan" for e in broker.snapshot()["events"]):
                    persist_stop("permit_integrity")
                if stop:
                    persist_stop(stop)
                while pending and ports and not stop:
                    if study.execution_protocol(value).get("first_429_halt"):
                        study.check_admission(directory)
                    study.verify_prepared(directory)
                    if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
                        deadline = local_deadline if local_eight else study.collection_deadline(directory)
                        if deadline is not None and time.time() >= deadline:
                            persist_stop("budget_stop")
                            break
                    if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
                        available = [(i, p) for i, r in enumerate(pending) for p in ports
                                     if (p < 8104) == (r["provider_id"] == "ollama")]
                        if not available:
                            break
                        index, port = available[0]
                        slot = pending.pop(index)
                        ports.remove(port)
                    else:
                        slot, port = pending.pop(0), ports.pop(0)
                    event = dict(
                        slot_id=slot["slot_id"],
                        event="dispatch",
                        time=time.time(),
                        port=port,
                        **({"provider_id": slot["provider_id"]} if "provider_id" in slot else {}),
                        stage="main" if gate_done else "first_pair",
                    )
                    b.seal_json(directory / "dispatch" / (slot["slot_id"] + ".json"), event)
                    events.append(event)
                    job = pool.submit(
                        worker,
                        data_root,
                        directory,
                        value,
                        slot,
                        1,
                        port=port,
                        broker_path=str(broker.path_for(slot) if hasattr(broker, "path_for") else broker.path),
                        deadline=deadline,
                        **({"hard_timeout_seconds": 1200, "cleanup_deadline": local_deadline} if local_eight else
                           {"hard_timeout_seconds": 600} if local_first_four else {}),
                    )
                    active[job] = (slot, port)
                if not active:
                    if not gate_done:
                        gate_done = True
                        check = gate_check(directory, attempts, value, broker.snapshot())
                        b.seal_json(directory / "first-pair-check.json", check)
                        if not check["passed"]:
                            persist_stop("first_pair_failed")
                        if check["passed"] and not stop:
                            pending = list(remaining)
                            continue
                    break
                done, _ = futures.wait(active, timeout=0.2, return_when=futures.FIRST_COMPLETED)
                for job in sorted(done, key=lambda f: active[f][1]):
                    slot, port = active.pop(job)
                    ports.append(port)
                    result = job.result()
                    attempts.append(result)
                    if value.get("registered_experiment") in ("EX-043", "EX-044", "EX-045", "EX-046"):
                        from .diagnostics.corrected_lead import before_reuse
                        input_check = before_reuse(directory, result)
                        if not input_check["passed"]:
                            persist_stop("input_contract")
                    print(
                        f"{study.execution_protocol(value)['experiment']} {len(attempts)}/32 {slot['slot_id']}: "
                        f"{result['category'] or 'completed'}",
                        flush=True,
                    )
                    if result["category"] in shared.SHARED:
                        persist_stop(result["category"])
                    elif value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046") and not gate_done and not result["eligible"]:
                        persist_stop("first_pair_failed")
        except BaseException as exc:
            persist_stop(getattr(exc, "category", None) or "integrity")
            b.seal_json(
                directory / "failure.json",
                dict(error_type=type(exc).__name__, category=stop, message=b.cli._safe_error(exc)),
            )
        finally:
            # Live HTTP remains owned by the worker and drains under its timeout.
            # Collect every completed future even after coordinator failure.
            futures.wait(active)
            for job in active:
                try:
                    attempts.append(job.result())
                except Exception:
                    pass  # observed_attempts reports the persisted orphan as unconfirmed.
            b.seal_json(
                directory / "batch.json",
                dict(
                    events=events,
                    stop_category=stop,
                    broker=broker.snapshot(),
                    finished_at=time.time(),
                ),
            )
    return attempts


def run(directory, data_root, *, verification, local_first_four=False, local_eight=False):
    directory, data_root = Path(directory).resolve(), Path(data_root).resolve()
    b.cli._assert_research_root_boundary(data_root)
    value = verify_entry(directory, verification)
    if local_eight and (local_first_four or value.get("registered_experiment") != "EX-045" or value["transport"] != "fake" or value.get("local_identity") != "ep058-local-eight"):
        raise ValueError("local eight requires EX-045 fake transport exclusively")
    configured = validate_execution(value["execution"])
    owned_ports = list(range(8100, 8100 + configured["battle_concurrency"]))
    b.cli.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    with (b.cli.ARTIFACT_ROOT / "benchmark-runtime.lock").open("a") as runtime:
        fcntl.flock(runtime, fcntl.LOCK_EX | fcntl.LOCK_NB)
        check_ports(owned_ports)
        if (directory / "halt.json").exists():
            raise ValueError("EX-039 halted; no resumption")
        b.seal_json(
            directory / "run-claim.json",
            dict(
                started_at=time.time(),
                data_root=str(data_root),
                verification=str(Path(verification).resolve()),
                verification_sha256=b.digest(verification),
                **({"local_eight": True, "hard_timeout_seconds": 1200, "total_seconds": 1800,
                    "cleanup_reserve_seconds": 60} if local_eight else
                   {"local_first_four": True, "hard_timeout_seconds": 600} if local_first_four else {}),
                execution_protocol=study.execution_protocol(value),
            ),
        )
        with tempfile.TemporaryDirectory(prefix="pc-lead-") as temp:
            with ExitStack() as stack:
                if value.get("registered_experiment") in ("EX-042", "EX-043", "EX-044", "EX-045", "EX-046"):
                    from .distributed_lead import Brokers
                    broker = Brokers(stack, temp, value)
                    paths = [b.path for b in broker.providers.values()]
                else:
                    broker = stack.enter_context(PermitBroker(
                        Path(temp) / "b.sock", configured["account_request_limit"],
                        configured["model_request_limits"],
                        timeout=drain_seconds(value.get("provider_config", {}))))
                    paths = [broker.path]
                execute_schedule(directory, data_root, value, broker, local_first_four=local_first_four, local_eight=local_eight)
            snapshot = broker.snapshot()
        check_ports(owned_ports)
        cleanup = dict(
            ports_closed=owned_ports,
            permits=snapshot,
            remaining_permits=sum(snapshot["active_at_close"].values()),
            socket_removed=all(not path.exists() for path in paths),
            completed_at=time.time(),
        )
        clock = directory / "cloud-clock.json"
        if clock.exists():
            cleanup["within_cleanup_deadline"] = (
                cleanup["completed_at"] <= b.read_sealed(clock)["cleanup_deadline"]
            )
        b.seal_json(directory / "cleanup.json", cleanup)
    from .team_preview_report import build_report

    if value.get("registered_experiment") in ("EX-043", "EX-044", "EX-045", "EX-046"):
        from .diagnostics.corrected_lead import audit_attempt
        # Finish coverage after execution resources have been released. This
        # offline stage has no model calls and is outside the six-hour budget.
        for path in sorted((directory / "attempts").glob("*/result.json")):
            attempt = b.read_sealed(path)
            if not (directory / "input-audit-receipts" / (attempt["attempt_id"] + ".json")).exists():
                audit_attempt(directory, attempt, offline=True)
    return build_report(directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("run")
    collect.add_argument("--directory", type=Path, required=True)
    collect.add_argument("--data-root", type=Path, required=True)
    collect.add_argument("--verification", type=Path, required=True)
    report = sub.add_parser("report")
    report.add_argument("--directory", type=Path, required=True)
    viewer = sub.add_parser("viewer")
    viewer.add_argument("--report-directory", type=Path, required=True)
    viewer.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        result = run(args.directory, args.data_root, verification=args.verification)
    elif args.command == "viewer":
        from .completed_viewer import build_viewer
        result = build_viewer(args.report_directory, args.output)
    else:
        from .team_preview_report import build_report

        result = build_report(args.directory)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
