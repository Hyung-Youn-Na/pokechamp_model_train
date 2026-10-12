"""Fail-closed stage receipts and a study-wide, restart-stable Cloud clock."""

from __future__ import annotations

import time
from pathlib import Path

from .. import benchmark as b

STAGES = ("offline", "fake12", "cloud_gate", "smoke12", "compare48")


def source_identity():
    return {str(p.relative_to(b.WORKSPACE_ROOT)): b.digest(p) for p in b.source_files()}


def verify_outputs(path, value):
    outputs = value.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        raise ValueError("missing sealed output references")
    for name, digest in outputs.items():
        target = Path(path).parent / name
        if Path(name).name != name or b.digest(target) != digest:
            raise ValueError("output seal mismatch")
        b.read_sealed(target)


def offline_receipt(path, *, current=True):
    path = Path(path)
    value = b.read_sealed(path)
    if (
        value.get("offline_gate_passed") is not True
        or value.get("structural_replay_passed") is not True
        or value.get("semantic_rubric") != "passed"
        or value.get("posthoc_truth_damage_validation") != "passed"
    ):
        raise ValueError("offline gate did not pass")
    rows = value.get("cases", [])
    if (
        {r["case"] for r in rows} != {f"IO-C{i:02}" for i in range(1, 16)}
        or len(rows) != 15
        or any(r["status"] != "success" for r in rows)
    ):
        raise ValueError("offline scene denominator mismatch")
    verify_outputs(path, value)
    for name, digest in value["source_files"].items():
        if b.digest(path.parent / "source" / name) != digest:
            raise ValueError("offline archive drift")
    semantics = b.read_sealed(path.parent / "semantic.json")
    posthoc = b.read_sealed(path.parent / "posthoc.json")
    if (
        len(semantics) != 15
        or not all(
            r["passed"] and r["checks"] and all(c["passed"] for c in r["checks"]) for r in semantics
        )
        or len(posthoc) != 3
        or not all(r["valid"] for r in posthoc)
    ):
        raise ValueError("offline component gate mismatch")
    if current and value.get("source_files") != source_identity():
        raise ValueError("offline source drift")
    return value


def read_stage(path, stage, *, current=True):
    if stage == "offline":
        return offline_receipt(path, current=current)
    value = b.read_sealed(Path(path))
    if value.get("stage") != stage or value.get("passed") is not True:
        raise ValueError(f"{stage} gate did not pass")
    if current and value.get("source_files") != source_identity():
        raise ValueError("stage source drift")
    previous = value["previous"]
    if b.digest(previous["path"]) != previous["sha256"]:
        raise ValueError("predecessor receipt drift")
    read_stage(previous["path"], STAGES[STAGES.index(stage) - 1], current=current)
    verify_outputs(path, value)
    if stage in ("fake12", "smoke12", "compare48"):
        directory = Path(value["benchmark_path"])
        if b.digest(directory / "plan.json") != value["benchmark_plan_sha256"]:
            raise ValueError("benchmark plan drift")
        plan = b.verify_plan(directory)
        b.validate_attempts(plan, b.load_attempts(directory))
    if stage == "cloud_gate":
        collection = b.read_sealed(Path(path).parent / "collection.json")
        for name, digest in collection["call_outputs"].items():
            if Path(name).name != name or b.digest(Path(path).parent / name) != digest:
                raise ValueError("Cloud call output drift")
            b.read_sealed(Path(path).parent / name)
    if stage == "fake12":
        cadence = b.read_sealed(Path(path).parent / "cadence.json")
        if cadence.get("passed") is not True or (
            cadence.get("actions"),
            cadence.get("summaries"),
            cadence.get("rollups"),
        ) != (31, 3, 1):
            raise ValueError("local cadence evidence missing")
    return value


def seal_stage(path, stage, previous, result, outputs):
    index = STAGES.index(stage)
    read_stage(previous, STAGES[index - 1])
    value = dict(
        result,
        stage=stage,
        source_files=source_identity(),
        previous={"path": str(Path(previous).resolve()), "sha256": b.digest(previous)},
        outputs={Path(p).name: b.digest(p) for p in outputs},
    )
    b.seal_json(Path(path), value)
    return value


def cloud_clock(study_root, *, now=None):
    """Call immediately before the first Cloud dispatch; never reset on source changes."""
    path = Path(study_root) / "cloud-clock.json"
    if not path.exists():
        started = time.time() if now is None else now
        b.seal_json(
            path,
            {
                "first_dispatch_at": started,
                "stop_new_work_at": started + 13500,
                "cleanup_deadline": started + 14400,
                "decision": "D-022",
            },
        )
    value = b.read_sealed(path)
    if (
        value["stop_new_work_at"] != value["first_dispatch_at"] + 13500
        or value["cleanup_deadline"] != value["first_dispatch_at"] + 14400
    ):
        raise ValueError("invalid Cloud clock")
    return value


def require_budget(clock, estimate=0, *, now=None):
    from . import experiment_policy as policy

    if policy.selected(clock):
        from .battle_only_budget import clock as verified_clock

        path = Path(clock["study"]["path"])
        if verified_clock(path.parent) != clock:
            raise ValueError("unverified unlimited clock")
        return
    current = time.time() if now is None else now
    deadline = clock["stop_new_work_at"]
    if type(deadline) not in (int, float) or not 0 < deadline < float("inf"):
        raise ValueError("invalid bounded clock")
    if current + estimate >= deadline:
        raise ValueError("budget_stop")


def halt_study(root, category, evidence):
    path = Path(root) / "halt.json"
    if not path.exists():
        b.seal_json(
            path,
            {
                "category": category,
                "evidence": str(Path(evidence).resolve()),
                "stopped_at": time.time(),
                "decision": "D-022",
            },
        )
    return b.read_sealed(path)


def require_not_halted(root):
    path = Path(root) / "halt.json"
    if path.exists():
        value = b.read_sealed(path)
        raise ValueError("study halted: " + value["category"])


def require_entry_gate(config, execution):
    evidence = execution["evidence"]
    transport = evidence.get("io_transport")
    if transport == "fake":
        if config != b.IO_SMOKE_CONFIG:
            raise ValueError("fake transport only authorizes local smoke")
        return
    if transport != "cloud":
        raise ValueError("explicit IO transport required")
    stage = "smoke12" if config == b.IO_COMPARE_CONFIG else "cloud_gate"
    previous = read_stage(evidence["io_stage_gate"], stage)
    if "io_summary_prompt_version" in evidence:
        from .prompt_versions import selected

        if previous.get("summary_prompt_identity") != selected(execution):
            raise ValueError("battle/Cloud summary prompt version mismatch")
    require_not_halted(Path(evidence["io_cloud_clock"]).parent)
    clock = b.read_sealed(Path(evidence["io_cloud_clock"]))
    if execution["stop_new_work_at"] != clock["stop_new_work_at"]:
        raise ValueError("Cloud deadline must match persistent clock")
    require_budget(clock)
