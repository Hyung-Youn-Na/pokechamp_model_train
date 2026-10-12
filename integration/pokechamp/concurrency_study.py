"""Execute D-016's conditional calibration, paired 8-slot runs and 32-slot run."""

from __future__ import annotations

import time

from . import benchmark as b
from .calibration import calibrate
from .constants import OLLAMA_MODEL, WORKSPACE_ROOT
from .execution import estimate_schedule


def comparison_gate(sequential, parallel):
    reasons = []
    if parallel["eligible_slots"] < sequential["eligible_slots"]:
        reasons.append("fewer_valid_completions")
    if parallel["batch_elapsed_seconds"] >= sequential["batch_elapsed_seconds"]:
        reasons.append("not_faster")
    metrics = parallel["request_concurrency"]
    if metrics["http_status_counts"].get("429", 0) or metrics["error_counts"].get("timeout", 0):
        reasons.append("provider_429_or_timeout")
    if any(x.get("stop_category") in b.HARD_STOP for x in parallel["batches"]):
        reasons.append("hard_stop")
    if any(parallel["failures"].get(k, 0) for k in b.HARD_STOP):
        reasons.append("integrity_or_configuration")
    return reasons


def same_comparison_conditions(first, second):
    """Compare sealed conditions without treating free disk observation as a treatment."""
    import copy

    for key in ("source", "parent_files", "schedule", "teams"):
        if first[key] != second[key]:
            return False
    environments = [copy.deepcopy(p["environment"]) for p in (first, second)]
    for environment in environments:
        environment["toolchain"].pop("free_disk_gib", None)
    return environments[0] == environments[1]


def study(root, experiment_id, *, calibration_id=None):
    directory = root / "concurrency-studies" / experiment_id
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    ids = {
        "calibration": calibration_id or experiment_id + "-calibration",
        "sequential": experiment_id + "-sequential8",
        "parallel": experiment_id + "-parallel8",
        "repeat": experiment_id + "-parallel32",
    }
    b.seal_json(
        directory / "intent.json",
        {
            "ids": ids,
            "decision": "D-016",
            "account": "Max; user declared exclusive Cloud use",
            "total_budget_seconds": 14400,
        },
    )
    calibration_dir = root / "calibrations" / ids["calibration"]
    if calibration_id is None:
        calibration = calibrate(root, ids["calibration"])
    else:
        b.validate_identifier(calibration_id, "calibration_id")
        calibration = b.read_sealed(calibration_dir / "report.json")
    protocol = b.read_sealed(calibration_dir / "protocol.json")
    if calibration["protocol_sha256"] != b.digest(calibration_dir / "protocol.json"):
        raise RuntimeError("integrity: calibration protocol reference changed")
    if protocol["corpus_sha256"] != b.digest(calibration_dir / "corpus.json"):
        raise RuntimeError("integrity: calibration corpus changed")
    if calibration_id is not None:
        # Explicit continuation only: preserve the original clock and unchanged request path.
        for name in (
            "cloud.py",
            "constants.py",
            "permits.py",
            "calibration.py",
            "benchmark_player.py",
            "concurrency_metrics.py",
        ):
            relative = "integration/pokechamp/" + name
            if b.digest(WORKSPACE_ROOT / relative) != protocol["parent_files"][relative]:
                raise RuntimeError("configuration: calibration request implementation changed")
        b.cli._assert_submodule_pins(require_clean=True)
    selected = calibration["selected_concurrency"]
    result = {"ids": ids, "selected_concurrency": selected, "stages": {}, "repeat_executed": False}

    def finish(reason):
        result["stop_reason"] = reason
        result["measurement_elapsed_seconds"] = time.time() - protocol["measurement_started_at"]
        result["fits_four_hours"] = time.time() <= protocol["cleanup_deadline"]
        b.seal_json(directory / "result.json", result)
        print(f"STUDY stopped/completed: {reason}; {directory}", flush=True)
        return result

    if selected is None or selected < 2:
        return finish("no_validated_concurrency_at_least_two")
    evidence = {
        "official_account_limit": {
            "value": 10,
            "source": "https://ollama.com/pricing",
            "checked": "2026-09-07",
        },
        "official_model_limit": {
            "value": "unknown",
            "source": "https://ollama.com/library/glm-5.3-flash",
            "checked": "2026-09-07",
        },
        "operational": {
            "model": OLLAMA_MODEL,
            "account": "Max/exclusive",
            "value": selected,
            "calibration_report": str(calibration_dir / "report.json"),
            "report_sha256": b.digest(calibration_dir / "report.json"),
            "protocol_sha256": b.digest(calibration_dir / "protocol.json"),
        },
    }
    while time.time() < calibration.get("account_cooldown_until", 0):
        if time.time() >= protocol["stop_new_work_at"]:
            return finish("budget_during_account_cooldown")
        time.sleep(min(1, calibration["account_cooldown_until"] - time.time()))
    for condition in protocol["comparison_order"]:
        if time.time() >= protocol["stop_new_work_at"]:
            return finish("budget_before_comparison")
        execution = {
            "version": 1,
            "battle_concurrency": 1 if condition == "sequential" else min(selected, 8),
            "account_request_limit": 1 if condition == "sequential" else 10,
            "model_request_limits": {OLLAMA_MODEL: 1 if condition == "sequential" else selected},
            "stop_new_work_at": protocol["stop_new_work_at"],
            "evidence": evidence,
        }
        path = directory / f"{condition}-execution.json"
        b.seal_json(path, execution)
        b.plan(
            root,
            ids[condition],
            WORKSPACE_ROOT / "integration/pokechamp/configs/core-smoke.json",
            path,
        )
        report = b.run(root, root / "benchmarks" / ids[condition])
        result["stages"][condition] = report
        if any(batch["stop_category"] for batch in report["batches"]):
            return finish("comparison_batch_stopped")
    sequential, parallel = result["stages"]["sequential"], result["stages"]["parallel"]
    seqplan = b.verify_plan(root / "benchmarks" / ids["sequential"], current=True)
    parplan = b.verify_plan(root / "benchmarks" / ids["parallel"], current=True)
    if not same_comparison_conditions(seqplan, parplan):
        return finish("comparison_condition_integrity")
    reasons = comparison_gate(sequential, parallel)
    result["comparison_gate_failures"] = reasons
    if reasons:
        return finish("comparison_gate_failed")
    predicted = estimate_schedule(
        b.make_schedule(b.CORE_REPEAT_CONFIG, {})["schedule"],
        {k: row["seconds_per_processed_slot"] for k, row in parallel["pair_runtime"].items()},
        selected,
    )
    result["repeat_estimate_seconds"] = predicted
    result["remaining_at_repeat_gate_seconds"] = protocol["stop_new_work_at"] - time.time()
    if predicted is None or predicted * 1.5 > result["remaining_at_repeat_gate_seconds"]:
        return finish("insufficient_budget_with_50pct_margin")
    execution["battle_concurrency"] = selected
    execution["account_request_limit"] = 10
    execution["model_request_limits"] = {OLLAMA_MODEL: selected}
    path = directory / "repeat-execution.json"
    b.seal_json(path, execution)
    b.plan(
        root, ids["repeat"], WORKSPACE_ROOT / "integration/pokechamp/configs/core-repeat.json", path
    )
    result["repeat_executed"] = True
    result["stages"]["repeat"] = b.run(root, root / "benchmarks" / ids["repeat"])
    return finish("repeat_processed")
