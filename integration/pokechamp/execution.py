"""Sealed execution settings and ordered concurrent slot scheduling."""

from __future__ import annotations

import concurrent.futures
import tempfile
import time
from pathlib import Path

from .constants import OLLAMA_MODEL
from .parallel_server import check_ports
from .permits import PermitBroker
from .transport_policy import drain_seconds

DEFAULT_CONCURRENCY = 8
CONCURRENCY_POLICY = "cloud-default8-v1"
ZAI_CONCURRENCY_POLICY = "zai-default4-v1"


def resolve_concurrency(limit=None, *, provider="ollama"):
    """Resolve a new preparation only; sealed executions supply their own limit."""
    if provider not in ("ollama", "zai"):
        raise ValueError("unknown concurrency provider")
    limit = (4 if provider == "zai" else DEFAULT_CONCURRENCY) if limit is None else limit
    concurrency_fields(limit)
    return limit


def sealed_concurrency_provider(value):
    """Retain historical policy selection independently of the current environment."""
    evidence = value["execution"]["evidence"]
    has_concurrency_policy(evidence)
    if evidence.get("concurrency_policy") == ZAI_CONCURRENCY_POLICY:
        if value.get("provider_config", {}).get("provider") != "zai":
            raise ValueError("Z.ai concurrency policy requires sealed Z.ai provider")
        return "zai"
    return "ollama"


def concurrency_fields(limit=DEFAULT_CONCURRENCY):
    """New defaults, or the caller's explicit limit; never clamp a declared value."""
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("concurrency must be 1..10")
    return dict(
        battle_concurrency=limit,
        account_request_limit=limit,
        model_request_limits={OLLAMA_MODEL: limit},
    )


def concurrency_evidence(*, provider="ollama"):
    resolve_concurrency(provider=provider)
    return dict(concurrency_policy=ZAI_CONCURRENCY_POLICY if provider == "zai" else CONCURRENCY_POLICY)


def has_concurrency_policy(evidence):
    if "concurrency_policy" not in evidence:
        return False
    if evidence["concurrency_policy"] not in (CONCURRENCY_POLICY, ZAI_CONCURRENCY_POLICY):
        raise ValueError("unknown concurrency policy")
    return True


def prepared_concurrency(execution):
    """Expected limits for fixed-profile verification, retaining legacy ten."""
    validate_execution(execution)
    if has_concurrency_policy(execution["evidence"]):
        return {key: execution[key] for key in concurrency_fields()}
    return concurrency_fields(10)


def gate_selection(parallel=DEFAULT_CONCURRENCY):
    concurrency_fields(parallel)
    return dict(**concurrency_evidence(), parallel_concurrency=parallel)


def gate_parallel(record):
    """Read the sealed gate declaration; old receipts retain their 1/10 cells."""
    if not has_concurrency_policy(record):
        if "parallel_concurrency" in record:
            raise ValueError("parallel concurrency requires a policy")
        return 10
    return gate_selection(record.get("parallel_concurrency"))["parallel_concurrency"]


def gate_evidence(record):
    parallel = gate_parallel(record)
    return dict(concurrency_policy=record["concurrency_policy"], parallel_concurrency=parallel) if has_concurrency_policy(record) else {}


def validate_execution(value):
    required = {
        "version",
        "battle_concurrency",
        "account_request_limit",
        "model_request_limits",
        "evidence",
        "stop_new_work_at",
    }
    if (
        set(value) - {"retry_transient", "action_policy"} != required
        or value["version"] != 1
    ):
        raise ValueError("invalid execution configuration schema")
    if "retry_transient" in value and (
        type(value["retry_transient"]) is not int
        or value["retry_transient"] not in (0, 1)
    ):
        raise ValueError("retry_transient must be 0 or 1")
    if value.get("action_policy", "strict") not in ("strict", "upstream"):
        raise ValueError("invalid action_policy")
    for key in ("battle_concurrency", "account_request_limit"):
        if type(value[key]) is not int or not 1 <= value[key] <= 10:
            raise ValueError(f"{key} must be 1..10")
    limits = value["model_request_limits"]
    if not isinstance(limits, dict) or set(limits) != {OLLAMA_MODEL}:
        raise ValueError("only the declared model is enabled")
    if type(limits[OLLAMA_MODEL]) is not int or not 1 <= limits[OLLAMA_MODEL] <= 10:
        raise ValueError("invalid model request limit")
    if not isinstance(value["evidence"], dict) or not value["evidence"]:
        raise ValueError("execution evidence is required")
    has_concurrency_policy(value["evidence"])
    deadline = value["stop_new_work_at"]
    if deadline is not None and (
        type(deadline) not in (int, float) or not 0 < deadline < float("inf")
    ):
        raise ValueError("invalid batch deadline")
    return value


def run_parallel(root, directory, value, existing):
    from . import benchmark as b

    config = validate_execution(value["execution"])
    stop_categories = b.HARD_STOP
    if value.get("conditions"):
        stop_categories = stop_categories | {
            "calculation", "input_contract", "output_contract", "environment",
            "transport", "rate_limit", "timeout", "watchdog",
            "algorithm", "worker_exit", "peer_failure", "interrupted", "budget_stop",
        }
    if value.get("config", {}).get("profile") == "io-battle-only-v1":
        stop_categories = stop_categories | {"provider", "action_contract"}
    from .improved_io.experiment_policy import stop_categories as policy_stops

    stop_categories = policy_stops(config["evidence"], stop_categories)
    ports = list(range(8100, 8100 + config["battle_concurrency"]))
    check_ports(ports)
    deadline = config["stop_new_work_at"]
    pending = []
    for slot in value["schedule"]:
        attempts = sorted(
            [a for a in existing if a["slot_id"] == slot["slot_id"]],
            key=lambda a: a["number"],
        )
        if attempts and (
            any(a["eligible"] for a in attempts)
            or attempts[-1]["category"] not in b.TRANSIENT
            or len(attempts) >= 1 + config.get("retry_transient", 1)
        ):
            continue
        pending.append((slot, len(attempts) + 1))
    # Each invocation has its own preserved batch timing, including a resumed invocation.
    batches = directory / "batches"
    batches.mkdir(exist_ok=True)
    batch = batches / f"{time.time_ns()}.json"
    started = time.time()
    events, stopped, max_battles = [], None, 0
    active = {}
    with tempfile.TemporaryDirectory(prefix="pc-permit-") as temp:
        with PermitBroker(
            Path(temp) / "broker.sock",
            config["account_request_limit"],
            config["model_request_limits"],
            deadline=deadline,
            timeout=drain_seconds(value.get("provider_config", {})),
        ) as broker:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(ports)) as pool:
                try:
                    while pending or active:
                        if deadline and time.time() >= deadline:
                            stopped = stopped or "budget_stop"
                        # Fatal actor signals must stop the account before response draining
                        # finishes and before the attempt future returns.
                        for slot, number, _ in active.values():
                            cancel = (
                                directory
                                / "attempts"
                                / f"{slot['slot_id']}-a{number}"
                                / "cancel.json"
                            )
                            if cancel.exists():
                                import json

                                category = json.loads(cancel.read_text())["category"]
                                if category in stop_categories:
                                    stopped = category
                        if stopped:
                            broker.stop()
                            for _, (slot, number, _) in active.items():
                                target = (
                                    directory
                                    / "attempts"
                                    / f"{slot['slot_id']}-a{number}"
                                )
                                if target.exists():
                                    b.signal_cancel(target, stopped)
                        while pending and ports and not stopped:
                            b.verify_plan(directory, current=True)
                            slot, number = pending.pop(0)
                            port = ports.pop(0)
                            events.append(
                                {
                                    "event": "dispatch",
                                    "slot_id": slot["slot_id"],
                                    "number": number,
                                    "port": port,
                                    "time": time.time(),
                                }
                            )
                            future = pool.submit(
                                b.run_attempt,
                                root,
                                directory,
                                value,
                                slot,
                                number,
                                port=port,
                                broker_path=str(broker.path),
                                deadline=deadline,
            timeout=drain_seconds(value.get("provider_config", {})),
                            )
                            active[future] = (slot, number, port)
                            max_battles = max(max_battles, len(active))
                        if not active:
                            break
                        done, _ = concurrent.futures.wait(
                            active,
                            timeout=0.2,
                            return_when=concurrent.futures.FIRST_COMPLETED,
                        )
                        for future in sorted(done, key=lambda f: active[f][2]):
                            slot, number, port = active.pop(future)
                            ports.append(port)
                            result = future.result()
                            existing.append(result)
                            events.append(
                                {
                                    "event": "finish",
                                    "slot_id": slot["slot_id"],
                                    "number": number,
                                    "port": port,
                                    "time": time.time(),
                                }
                            )
                            print(
                                f"BENCHMARK {slot['slot_id']} a{number}: "
                                f"{result['category'] or 'completed'}",
                                flush=True,
                            )
                            if result["category"] in stop_categories:
                                stopped = result["category"]
                            elif result[
                                "category"
                            ] in b.TRANSIENT and number < 1 + config.get(
                                "retry_transient", 1
                            ):
                                pending.insert(0, (slot, number + 1))
                except BaseException:
                    stopped = stopped or "interrupted"
                    broker.stop()
                    for slot, number, _ in active.values():
                        target = directory / "attempts" / f"{slot['slot_id']}-a{number}"
                        if target.exists():
                            b.signal_cancel(target, "interrupted")
                    raise
                finally:
                    # Finish/cleanup futures before sealing the actual elapsed batch time.
                    concurrent.futures.wait(active)
                    b.seal_json(
                        batch,
                        {
                            "started_at": started,
                            "finished_at": time.time(),
                            "elapsed_seconds": time.time() - started,
                            "stop_category": stopped,
                            "maximum_battles": max_battles,
                            "events": events,
                            "not_dispatched_slots": [s["slot_id"] for s, _ in pending],
                            "broker": broker.snapshot(),
                        },
                    )
    return existing


def estimate_schedule(schedule, pair_seconds, concurrency):
    lanes = [0.0] * concurrency
    for slot in schedule:
        key = "-".join(slot["pair"])
        if key not in pair_seconds:
            return None
        index = min(range(concurrency), key=lambda i: (lanes[i], i))
        lanes[index] += pair_seconds[key]
    return max(lanes)
