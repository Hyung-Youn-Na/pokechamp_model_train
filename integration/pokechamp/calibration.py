"""Preregistered development-prompt concurrency calibration (no battle outcomes)."""

from __future__ import annotations

import concurrent.futures
import contextlib
import fcntl
import json
import multiprocessing
import random
import statistics
import tempfile
import time
from collections import defaultdict
from pathlib import Path

from . import benchmark as b
from . import cli
from .cloud import OllamaCloudBackend
from .constants import OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, WORKSPACE_ROOT
from .permits import PermitBroker

CORPUS_SOURCE = "core-smoke-128k-300s-v1"
GROUPS = (
    ("io", "self_action"),
    ("minimax", "self_action"),
    ("minimax", "opponent_action"),
    ("minimax", "tool_choice"),
    ("minimax", "state_value"),
)


def extract_corpus(root):
    directory = root / "benchmarks" / CORPUS_SOURCE
    source = b.verify_plan(directory)
    attempts = b.load_attempts(directory)
    b.validate_attempts(source, attempts)
    groups = defaultdict(list)
    for attempt in sorted(attempts, key=lambda a: a["attempt_id"]):
        if not set(attempt["slot"]["teams"]) <= set(source["development_teams"]):
            raise RuntimeError("integrity: non-development corpus")
        for role, actor in sorted(attempt["actors"].items()):
            path = Path(actor["bundle"]) / "events.jsonl"
            method = attempt["slot"]["methods"][int(role[-1]) - 1]
            for line in path.read_text().splitlines():
                event = json.loads(line)
                if event["event_type"] != "llm_call" or event["status"] != "success":
                    continue
                key = method, event["request"].get("call_role")
                if key not in GROUPS or len(groups[key]) >= 4:
                    continue
                request = event["request"]
                if (
                    request["model"] != OLLAMA_MODEL
                    or request["thinking_effort"] != "low"
                    or request["requested_output_tokens"] != 131072
                    or request["context_window"] is not None
                ):
                    raise RuntimeError("configuration: corpus request conditions differ")
                groups[key].append(
                    {
                        "group": list(key),
                        "source": str(path),
                        "source_sha256": b.digest(path),
                        "event_seq": event["event_seq"],
                        "system_prompt": event["system_prompt"],
                        "user_prompt": event["user_prompt"],
                        "request": {k: v for k, v in request.items() if k != "target_state"},
                    }
                )
    if any(len(groups[key]) != 4 for key in GROUPS):
        raise RuntimeError("integrity: insufficient successful corpus roles")
    return [item for key in GROUPS for item in groups[key]]


class Trace:
    def record_llm_call(self, **payload):
        self.payload = payload


def call_prompt(item, broker_path, deadline):
    cli._load_cloud_credential()
    import os

    env = dict(
        os.environ, POKECHAMP_PERMIT_SOCKET=broker_path, POKECHAMP_BATCH_DEADLINE=str(deadline)
    )
    env.pop("POKECHAMP_CANCEL_PATH", None)
    trace = Trace()
    env.update(POKECHAMP_TRANSPORT_POLICY="legacy-300-v1", POKECHAMP_PROVIDER="ollama")
    backend = OllamaCloudBackend(environ=env, trace_sink=trace)
    request = item["request"]
    category = None
    try:
        backend.get_LLM_action(
            item["system_prompt"],
            item["user_prompt"],
            request["requested_model"],
            temperature=request["temperature"],
            json_format=request["json_format"],
            seed=request["seed"],
            stop=request["stop"],
        )
    except Exception as exc:
        category = getattr(exc, "category", "configuration")
    payload = getattr(trace, "payload", {})
    record = backend.call_records[-1] if backend.call_records else {}
    if payload.get("response", {}).get("reported_model", OLLAMA_MODEL) != OLLAMA_MODEL:
        category = "model"
    complete = False
    try:
        complete = isinstance(json.loads(payload.get("raw_content") or ""), dict)
    except (ValueError, TypeError):
        pass
    complete = complete and payload.get("response", {}).get("done_reason") == "stop"
    return {
        "category": category,
        "complete_json": complete,
        "record": record,
        "trace": payload,
        "source_event_seq": item["event_seq"],
        "group": item["group"],
    }


def select_concurrency(levels):
    grouped = defaultdict(list)
    for level in levels:
        grouped[level["concurrency"]].append(level)
    baseline = grouped.get(1, [])
    if len(baseline) != 3 or any(x["calls"] != 20 or x["transport_errors"] for x in baseline):
        return None
    baseline_p95 = b.percentile([v for x in baseline for v in x["http_latencies_ms"]], 0.95)
    candidates = {}
    for c, rows in grouped.items():
        if len(rows) != 3 or any(x["calls"] != 20 or x["transport_errors"] for x in rows):
            continue
        p95 = b.percentile([v for x in rows for v in x["http_latencies_ms"]], 0.95)
        if p95 is not None and p95 <= 2 * baseline_p95:
            candidates[c] = statistics.median(x["json_per_second"] for x in rows)
    if not candidates or max(candidates.values()) <= 0:
        return None
    best = max(candidates.values())
    return min(c for c, throughput in candidates.items() if throughput >= 0.95 * best)


def measure_level(directory, corpus, concurrency, repeat, deadline, shared_broker=None):
    calls = []
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="pc-cal-") as temp:
        manager = (
            contextlib.nullcontext(shared_broker)
            if shared_broker is not None
            else PermitBroker(
                Path(temp) / "broker.sock", 10, {OLLAMA_MODEL: concurrency}, deadline=deadline
            )
        )
        with manager as broker:
            with broker.condition:
                broker.stopped = False
                broker.model_limits[OLLAMA_MODEL] = concurrency
                broker.deadline = deadline
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=concurrency, mp_context=multiprocessing.get_context("spawn")
            ) as pool:
                todo = list(enumerate(corpus))
                active = {}
                stop = False
                while todo or active:
                    while (
                        todo and len(active) < concurrency and not stop and time.time() < deadline
                    ):
                        index, item = todo.pop(0)
                        active[pool.submit(call_prompt, item, str(broker.path), deadline)] = index
                    if not active:
                        break
                    done, _ = concurrent.futures.wait(
                        active, timeout=0.1, return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    for future in done:
                        index = active.pop(future)
                        result = future.result()
                        result["corpus_index"] = index
                        calls.append(result)
                        b.seal_json(
                            directory / "calls" / f"r{repeat}-c{concurrency:02d}-p{index:02d}.json",
                            result,
                        )
                        if result["category"] not in (None, "output_contract"):
                            stop = True
                            broker.stop()
                snapshot = broker.snapshot()
    elapsed = time.time() - started
    latencies = [x["record"]["http_elapsed_ms"] for x in calls if "http_elapsed_ms" in x["record"]]
    errors = [x["category"] for x in calls if x["category"] not in (None, "output_contract")]
    completed = sum(x["complete_json"] for x in calls)
    network = [x for x in calls if x["record"].get("network_called")]
    from .concurrency_metrics import request_metrics

    row = {
        "request_concurrency": request_metrics([x["trace"] for x in calls]),
        "concurrency": concurrency,
        "repeat": repeat,
        "elapsed_seconds": elapsed,
        "calls": len(network),
        "planned_calls": 20,
        "transport_errors": errors,
        "complete_json": completed,
        "json_per_second": completed / elapsed,
        "http_success_rate": sum(x["record"].get("http_status") == 200 for x in network)
        / len(network)
        if network
        else None,
        "json_completion_rate": completed / len(network) if network else None,
        "tokens_per_second": sum(
            x["record"].get("prompt_tokens", 0) + x["record"].get("completion_tokens", 0)
            for x in calls
        )
        / elapsed,
        "http_latencies_ms": latencies,
        "http_p50_ms": b.percentile(latencies, 0.5),
        "http_p95_ms": b.percentile(latencies, 0.95),
        "broker": snapshot,
    }
    b.seal_json(directory / f"r{repeat}-c{concurrency:02d}.json", row)
    return row


def calibrate(root, experiment_id):
    cli.ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    with (
        (cli.ARTIFACT_ROOT / "benchmark-runtime.lock").open("a") as lock,
        tempfile.TemporaryDirectory(prefix="pc-cal-study-") as temp,
        PermitBroker(Path(temp) / "broker.sock", 10, {OLLAMA_MODEL: 10}) as broker,
    ):
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cli._assert_submodule_pins(require_clean=True)
        corpus = extract_corpus(root)
        directory = root / "calibrations" / experiment_id
        directory.mkdir(parents=True, exist_ok=False, mode=0o700)
        b.seal_json(directory / "corpus.json", corpus)
        rng = random.Random(20260907)
        order = [list(range(1, 11))]
        for _ in range(2):
            row = list(range(1, 11))
            rng.shuffle(row)
            order.append(row)
        comparison = ["sequential", "parallel"]
        rng.shuffle(comparison)
        started = time.time()
        protocol = {
            "experiment_id": experiment_id,
            "source_experiment": CORPUS_SOURCE,
            "corpus_sha256": b.digest(directory / "corpus.json"),
            "selection_rule": (
                "sorted attempt_id, actor role, event_seq; first four successes per group"
            ),
            "order": order,
            "comparison_order": comparison,
            "seed": 20260907,
            "measurement_started_at": started,
            "calibration_stop_at": started + 1800,
            "stop_new_work_at": started + 13500,
            "cleanup_deadline": started + 14400,
            "request_timeout_seconds": OLLAMA_TIMEOUT_SECONDS,
            "official_account_limit": 10,
            "official_model_limit": "unknown",
            "official_checked_date": "2026-09-07",
            "official_sources": [
                "https://ollama.com/pricing",
                "https://ollama.com/library/glm-5.3-flash",
            ],
            "parent_files": {
                str(p.relative_to(WORKSPACE_ROOT)): b.digest(p) for p in b.source_files()
            },
            "selection": (
                "three complete repeats; no transport error; pooled p95 <= 2x C1; "
                "lowest C at >=95% best median JSON/s"
            ),
        }
        protocol["source"] = cli._research_source_snapshot()
        protocol["environment"] = cli._toolchain_snapshot()
        for relative in protocol["parent_files"]:
            target = directory / "source" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((WORKSPACE_ROOT / relative).read_bytes())
        b.seal_json(directory / "protocol.json", protocol)
        levels, cutoff, hard_stop = [], 11, None
        for repeat, sequence in enumerate(order, 1):
            for concurrency in sequence:
                if concurrency >= cutoff or time.time() >= protocol["calibration_stop_at"]:
                    continue
                for relative, wanted in protocol["parent_files"].items():
                    if b.digest(WORKSPACE_ROOT / relative) != wanted:
                        raise RuntimeError("integrity: calibration source changed")
                if b.digest(directory / "corpus.json") != protocol["corpus_sha256"]:
                    raise RuntimeError("integrity: calibration corpus changed")
                # Reserve the full timeout inside the 30-minute calibration allowance.
                if time.time() + OLLAMA_TIMEOUT_SECONDS + 10 >= protocol["calibration_stop_at"]:
                    continue
                row = measure_level(
                    directory,
                    corpus,
                    concurrency,
                    repeat,
                    protocol["calibration_stop_at"] - OLLAMA_TIMEOUT_SECONDS - 5,
                    shared_broker=broker,
                )
                levels.append(row)
                print(
                    f"CALIBRATION repeat={repeat} C={concurrency} calls={row['calls']} "
                    f"JSON/s={row['json_per_second']:.3f} errors={row['transport_errors']}",
                    flush=True,
                )
                if row["transport_errors"]:
                    cutoff = min(cutoff, concurrency)
                if any(x in b.HARD_STOP for x in row["transport_errors"]):
                    hard_stop = row["transport_errors"]
                    break
            if hard_stop:
                break
        selected = (
            select_concurrency([x for x in levels if x["concurrency"] < cutoff])
            if not hard_stop
            else None
        )
        report = {
            "experiment_id": experiment_id,
            "selected_concurrency": selected,
            "hard_stop": hard_stop,
            "levels": levels,
            "elapsed_seconds": time.time() - started,
            "scope": (
                "This account/model/request corpus only; observed HTTP overlap "
                "does not prove provider execution parallelism."
            ),
            "protocol_sha256": b.digest(directory / "protocol.json"),
            "cutoff": cutoff,
            "account_cooldown_until": time.time() + max(0, broker.cooldown - time.monotonic()),
        }
        b.seal_json(directory / "report.json", report)
        print(f"Calibration selected C*={selected}; evidence: {directory}", flush=True)
        return report
