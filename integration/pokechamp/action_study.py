"""D-017: fixed 144-request validation followed by strictly gated battles."""

from __future__ import annotations

import concurrent.futures
import json
import multiprocessing
import os
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from . import benchmark as b
from . import cli
from .benchmark_player import ActionCandidate, ActionCandidates, BenchmarkBackend
from .calibration import Trace
from .concurrency_metrics import request_metrics
from .constants import OLLAMA_MODEL
from .execution import (
    DEFAULT_CONCURRENCY,
    concurrency_evidence,
    concurrency_fields,
    gate_parallel,
    gate_selection,
)
from .permits import PermitBroker


def call_case(item, broker_path, deadline):
    cli._load_cloud_credential()
    env = dict(
        os.environ,
        POKECHAMP_PERMIT_SOCKET=broker_path,
        POKECHAMP_BATCH_DEADLINE=str(deadline),
    )
    env.pop("POKECHAMP_CANCEL_PATH", None)
    trace = Trace()
    env.update(POKECHAMP_TRANSPORT_POLICY="legacy-300-v1", POKECHAMP_PROVIDER="ollama")
    backend = BenchmarkBackend(environ=env, trace_sink=trace)
    request = item["request"]
    backend.role = request["call_role"]
    if item["candidates"] is not None:
        backend.candidates = ActionCandidates(
            [
                ActionCandidate(*next(iter(row["action"].items())), None, row["source"])
                for row in item["candidates"]
            ]
        )
    category = None
    try:
        backend.get_LLM_action(
            item["system_prompt"],
            item["user_prompt"],
            request["requested_model"],
            temperature=request["temperature"],
            json_format=True,
            seed=request["seed"],
            stop=request["stop"],
            battle=SimpleNamespace(turn=item["target_state"]["showdown_turn"]),
        )
    except Exception as error:
        category = getattr(error, "category", "configuration")
    payload = getattr(trace, "payload", {})
    return {
        "category": category,
        "trace": payload,
        "group": item["group"],
        "source": item["source"],
        "source_event_seq": item["event_seq"],
        "valid": category is None
        and payload.get("validation", {}).get("output_contract_valid") is True,
    }


def validation_gate(rows, *, declaration=None):
    limit = gate_parallel(declaration or {})
    sequential = [r["trace"] for r in rows if r["concurrency"] == 1]
    parallel = [r["trace"] for r in rows if r["concurrency"] == limit]
    first, second = request_metrics(sequential), request_metrics(parallel)
    passed = (
        len(rows) == 144
        and limit > 1
        and len(sequential) == len(parallel) == 72
        and all(r["valid"] for r in rows)
        and second["maximum_account_http_overlap"] == limit
        and first["http_p95_ms"] is not None
        and second["http_p95_ms"] is not None
        and second["http_p95_ms"] <= 2 * first["http_p95_ms"]
    )
    return {
        "passed": passed,
        "planned_calls": 144,
        "recorded_calls": len(rows),
        "valid_calls": sum(r["valid"] for r in rows),
        "sequential": first,
        "parallel": second,
    }


def qualify_requests(directory, corpus, deadline, *, concurrency=DEFAULT_CONCURRENCY):
    declaration = gate_selection(concurrency)
    limit = gate_parallel(declaration)
    if limit == 1:
        raise ValueError("request comparison requires concurrency 2..10")
    b.seal_json(directory / "request-concurrency.json", declaration)
    rows = []
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="pc-action-") as temp:
        with PermitBroker(
            Path(temp) / "broker.sock", limit, {OLLAMA_MODEL: limit}, deadline=deadline
        ) as broker:
            for concurrency in (1, limit):
                for repeat in range(3):
                    if time.time() >= deadline:
                        break
                    with concurrent.futures.ProcessPoolExecutor(
                        max_workers=concurrency,
                        mp_context=multiprocessing.get_context("spawn"),
                    ) as pool:
                        futures = {
                            pool.submit(call_case, item, str(broker.path), deadline): i
                            for i, item in enumerate(corpus)
                        }
                        for future in concurrent.futures.as_completed(futures):
                            row = future.result()
                            row.update(
                                concurrency=concurrency,
                                repeat=repeat,
                                corpus_index=futures[future],
                            )
                            rows.append(row)
                            b.seal_json(
                                directory
                                / "calls"
                                / f"c{concurrency}-r{repeat}-p{futures[future]}.json",
                                row,
                            )
                    print(
                        f"REQUEST VALIDATION c={concurrency} repeat={repeat}: "
                        f"{sum(r['valid'] for r in rows)}/{len(rows)} valid",
                        flush=True,
                    )
            snapshot = broker.snapshot()
    result = {
        **declaration,
        **validation_gate(rows, declaration=declaration),
        "elapsed_seconds": time.time() - started,
        "broker": snapshot,
    }
    b.seal_json(directory / "request-result.json", result)
    return result


def smoke_gate(report):
    return (
        report["eligible_slots"] == 8
        and report["attempts"] == 8
        and report["processed_slots"] == 8
        and not report["failures"]
    )


def parallel_budget(attempts, schedule, workers=DEFAULT_CONCURRENCY):
    concurrency_fields(workers)
    durations = {tuple(a["slot"]["pair"]): a["duration_seconds"] for a in attempts}
    for a in attempts:
        key = tuple(a["slot"]["pair"])
        durations[key] = max(durations[key], a["duration_seconds"])
    lanes = [0.0] * workers
    for slot in schedule:
        lane = min(range(workers), key=lanes.__getitem__)
        lanes[lane] += durations[tuple(slot["pair"])]
    return {"estimated_seconds": max(lanes), "with_margin_seconds": max(lanes) * 1.5}


def cloud_stages(root, directory):
    local = b.read_sealed(directory / "local-result.json")
    assert smoke_gate(local), "local gate failed"
    corpus = b.read_sealed(directory / "corpus.json")
    assert len(corpus) == 24
    for item in corpus:
        assert b.digest(item["source"]) == item["source_sha256"]
    start = time.time()
    deadline = start + 3.75 * 3600
    intent = {
        "started_at": start,
        "stop_new_work_at": deadline,
        "cleanup_deadline": start + 4 * 3600,
        "source": {
            str(p.relative_to(b.WORKSPACE_ROOT)): b.digest(p) for p in b.source_files()
        },
        "corpus_sha256": b.digest(directory / "corpus.json"),
        "decision": "D-017",
    }
    b.seal_json(directory / "cloud-intent.json", intent)
    import fcntl

    with (cli.ARTIFACT_ROOT / "benchmark-runtime.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = qualify_requests(directory, corpus, deadline)
    outcome = {"request_gate": result, "smoke_id": None, "repeat_id": None}
    if result["passed"]:
        config = {
            "version": 1,
            **concurrency_fields(),
            "retry_transient": 0,
            "evidence": {
                **concurrency_evidence(),
                "decision": "D-017",
                "request_validation": str(directory / "request-result.json"),
                "sha256": b.digest(directory / "request-result.json"),
            },
            "stop_new_work_at": deadline,
        }
        b.seal_json(directory / "smoke-execution.json", config)
        smoke_id = "identity-candidates-cloud8-v1"
        smoke_config = (
            b.WORKSPACE_ROOT / "integration/pokechamp/configs/core-smoke.json"
        )
        b.plan(root, smoke_id, smoke_config, directory / "smoke-execution.json")
        b.run(root, root / "benchmarks" / smoke_id)
        b.analyze(root / "benchmarks" / smoke_id)
        report = json.loads(
            (root / "benchmarks" / smoke_id / "report.json").read_text()
        )
        outcome["smoke_id"] = smoke_id
        outcome["smoke_gate"] = smoke_gate(report)
        if outcome["smoke_gate"]:
            attempts = b.load_attempts(root / "benchmarks" / smoke_id)
            budget = parallel_budget(
                attempts, b.make_schedule(b.CORE_REPEAT_CONFIG, {})["schedule"]
            )
            outcome["repeat_budget"] = budget
            if time.time() + budget["with_margin_seconds"] <= deadline:
                b.seal_json(directory / "repeat-execution.json", config)
                repeat_id = "identity-candidates-cloud32-v1"
                b.plan(
                    root,
                    repeat_id,
                    b.WORKSPACE_ROOT / "integration/pokechamp/configs/core-repeat.json",
                    directory / "repeat-execution.json",
                )
                b.run(root, root / "benchmarks" / repeat_id)
                b.analyze(root / "benchmarks" / repeat_id)
                outcome["repeat_id"] = repeat_id
    outcome["elapsed_seconds"] = time.time() - start
    b.seal_json(directory / "cloud-result.json", outcome)
    return outcome


if __name__ == "__main__":
    import sys

    cloud_stages(Path(sys.argv[1]), Path(sys.argv[2]))
