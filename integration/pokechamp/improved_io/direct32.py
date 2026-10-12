"""D-033 sealed preparation and one-shot main comparison; no qualification receipts."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .. import benchmark as b
from ..execution import DEFAULT_CONCURRENCY, gate_evidence, gate_selection
from . import battle_only_budget as budget
from . import battle_prompts
from . import experiment_policy as policy
from .battle_only_protocol import CONDITIONS_AB, PROFILE, read_ref, ref
from .calculator import expected_patch
from .conditions import schedule
from .receipts import source_identity, verify_outputs

SKIPPED = {
    name: "skipped_by_user"
    for name in (
        "regression",
        "offline15",
        "posthoc3",
        "fake32",
        "cloud_gate",
        "smoke8",
    )
}


def skipped_for(value):
    if policy.is_v2_repeat(value):
        return {
            k: v for k, v in SKIPPED.items() if k in ("fake32", "cloud_gate", "smoke8")
        }
    if policy.is_calcfix(value):
        return {k: v for k, v in SKIPPED.items() if k != "regression"}
    return dict(SKIPPED)


def prepare(
    directory,
    *,
    battle_prompt_version=None,
    experiment_policy=policy.DIRECT,
    verification=None,
    concurrency=DEFAULT_CONCURRENCY,
):
    selection = policy.selection(experiment_policy)
    required_version = policy.required_prompt_version(selection)
    battle_prompt_version = battle_prompt_version or required_version
    if battle_prompt_version != required_version:
        raise ValueError(f"direct32 policy requires battle prompt {required_version}")
    directory = Path(directory)
    reference_path = (
        b.WORKSPACE_ROOT / ".pokechamp-data/benchmarks/glm-upstream-fallback32-v1"
    )
    reference = b.verify_plan(reference_path)
    prompt = battle_prompts.selection(battle_prompt_version)
    system = battle_prompts.assemble(version=battle_prompt_version)
    selection = policy.selection(experiment_policy)
    skipped = skipped_for(selection)
    qualification = {}
    if policy.is_movefix(selection):
        from .movefix32 import preparation_evidence

        qualification = preparation_evidence(verification, selection=selection)
    elif policy.is_inputfix(selection):
        from .inputfix32 import preparation_evidence

        qualification = preparation_evidence(verification)
    elif policy.is_calcfix(selection):
        from .calcfix32 import preparation_evidence

        qualification = preparation_evidence(verification)
    elif verification is not None:
        raise ValueError("qualification is only supported by qualified repeats")
    directory.mkdir(parents=True, exist_ok=False)
    b.seal_json(directory / "battle-prompt.json", dict(**prompt, system_prompt=system))
    b.seal_json(directory / "config.json", b.BATTLE_ONLY_COMPARE_CONFIG)
    sources = source_identity()
    for relative in sources:
        target = directory / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((b.WORKSPACE_ROOT / relative).read_bytes())
    manifest = dict(
        **gate_selection(concurrency),
        **selection,
        **qualification,
        **prompt,
        profile=PROFILE,
        source_files=sources,
        skipped=skipped,
        scenes=[],
        battle_prompt=ref(directory / "battle-prompt.json"),
        reference=ref(reference_path / "plan.json"),
        compare_schedule=schedule(reference, smoke=False, condition_ids=("A", "B")),
        prompt_sha256=prompt["battle_prompt_identity"]["prompt_sha256"],
        prior_sha256=b.digest(Path(__file__).with_name("prior.json")),
        calculation_identity=expected_patch(),
        config=ref(directory / "config.json"),
    )
    if policy.is_movefix(selection):
        from .movefix32 import validate_manifest

        validate_manifest(manifest)
    elif policy.is_inputfix(selection):
        from .inputfix32 import validate_manifest

        validate_manifest(manifest)
    elif policy.is_calcfix(selection):
        from .calcfix32 import validate_manifest

        validate_manifest(manifest)
    b.seal_json(directory / "manifest.json", manifest)
    result = dict(
        **gate_selection(concurrency),
        **selection,
        profile=PROFILE,
        stage="prepare",
        passed=True,
        preparation_only=True,
        conditions=CONDITIONS_AB,
        source_files=sources,
        skipped=skipped,
        outputs={
            name: b.digest(directory / name)
            for name in ("manifest.json", "battle-prompt.json", "config.json")
        },
    )
    b.seal_json(directory / "result.json", result)
    return result


def read_stage(path, stage, *, current=True):
    path = Path(path)
    value = b.read_sealed(path)
    if (
        not policy.is_direct(value)
        or value.get("stage") != stage
        or value.get("profile") != PROFILE
        or value.get("conditions") != CONDITIONS_AB
    ):
        raise ValueError("direct32 preparation identity mismatch")
    if current and value["source_files"] != source_identity():
        raise ValueError("direct32 source drift")
    verify_outputs(path, value)
    if stage != "prepare":
        raise ValueError("direct32 comparison result is an outcome, not a passed gate")
    skipped = skipped_for(value)
    if (
        value.get("passed") is not True
        or value.get("preparation_only") is not True
        or value.get("skipped") != skipped
        or "offline" in value
    ):
        raise ValueError("direct32 cannot fabricate qualification")
    manifest = b.read_sealed(path.parent / "manifest.json")
    policy.same(value, manifest)
    if gate_evidence(value) != gate_evidence(manifest):
        raise ValueError("preparation concurrency declaration mismatch")
    if (
        manifest["source_files"] != value["source_files"]
        or manifest["skipped"] != skipped
        or manifest["scenes"]
    ):
        raise ValueError("direct32 manifest drift")
    for relative, checksum in value["source_files"].items():
        if b.digest(path.parent / "source" / relative) != checksum:
            raise ValueError("direct32 source archive drift")
    prompt = read_ref(manifest["battle_prompt"])
    if (
        prompt["battle_prompt_identity"] != manifest["battle_prompt_identity"]
        or prompt["battle_prompt_version"] != policy.required_prompt_version(value)
        or hashlib.sha256(prompt["system_prompt"].encode()).hexdigest()
        != manifest["prompt_sha256"]
    ):
        raise ValueError("direct32 prompt seal drift")
    if current:
        identity = battle_prompts.selected(manifest)
        if prompt["system_prompt"] != battle_prompts.assemble(
            version=policy.required_prompt_version(value), declared=identity
        ):
            raise ValueError("direct32 prompt source drift")
        if (
            manifest["prior_sha256"] != b.digest(Path(__file__).with_name("prior.json"))
            or manifest["calculation_identity"] != expected_patch()
        ):
            raise ValueError("direct32 prior/calculator drift")
    reference = read_ref(manifest["reference"])
    if (
        manifest["compare_schedule"]
        != schedule(reference, smoke=False, condition_ids=("A", "B"))
        or read_ref(manifest["config"]) != b.BATTLE_ONLY_COMPARE_CONFIG
    ):
        raise ValueError("direct32 schedule/config drift")
    if policy.is_movefix(value):
        from .movefix32 import validate_manifest

        validate_manifest(manifest, current=current)
    elif policy.is_inputfix(value):
        from .inputfix32 import validate_manifest

        validate_manifest(manifest, current=current)
    elif policy.is_calcfix(value):
        from .calcfix32 import validate_manifest

        validate_manifest(manifest, current=current)
    return value


def require_entry(config, execution):
    evidence = execution["evidence"]
    if (
        not policy.is_direct(evidence)
        or config != b.BATTLE_ONLY_COMPARE_CONFIG
        or evidence.get("io_stage") != "compare32"
        or evidence.get("io_cohort") != "c0"
        or evidence.get("io_transport") != "cloud"
        or evidence.get("io_stage_gate") != evidence.get("io_offline_gate")
    ):
        raise ValueError(
            "direct32 requires one original compare32 with preparation predecessor"
        )
    prepared = read_stage(evidence["io_offline_gate"], "prepare")
    cohort = budget.require_cohort(evidence["io_study_root"], "c0")
    if cohort["prepared"] != ref(evidence["io_offline_gate"]):
        raise ValueError("direct32 cohort/preparation mismatch")
    policy.same(evidence, prepared, cohort)
    if policy.is_v2_repeat(evidence):
        from .inputfix32 import verify_runtime

        manifest = b.read_sealed(
            Path(evidence["io_offline_gate"]).parent / "manifest.json"
        )
        verify_runtime(evidence, manifest=manifest)
    clock = budget.clock(evidence["io_study_root"])
    if execution["stop_new_work_at"] != clock["stop_new_work_at"]:
        raise ValueError("direct32 clock mismatch")


def run(root, prepared, directory, *, study, cohort="c0", experiment_id=None):
    from .battle_only import execution
    from .study import battle_checks

    if cohort != "c0":
        raise ValueError("direct32 prohibits recollection")
    read_stage(prepared, "prepare")
    budget.require_cohort(study, cohort)
    # Clock is sealed once at main-stage admission; all HTTP intents reference it.
    budget.clock(study, create=True)
    ex = execution(
        prepared, stage="compare32", previous=prepared, study=study, cohort=cohort
    )
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    manifest = b.read_sealed(Path(prepared).parent / "manifest.json")
    slots = manifest["compare_schedule"]
    budget.claim_stage(
        study, cohort, "compare32", [s["slot_id"] for s in slots], directory
    )
    b.seal_json(directory / "config.json", b.BATTLE_ONLY_COMPARE_CONFIG)
    b.seal_json(directory / "execution.json", ex)
    experiment_id = experiment_id or (
        manifest["experiment_policy_identity"]["experiment_id"].lower().replace("-", "")
        + "-c0-compare32"
    )
    value = b.plan(
        root, experiment_id, directory / "config.json", directory / "execution.json"
    )
    if value["schedule"] != slots:
        raise ValueError("direct32 benchmark schedule differs from prepared schedule")
    target = Path(root) / "benchmarks" / experiment_id
    b.seal_json(directory / "benchmark.json", ref(target / "plan.json"))
    try:
        report = b.run(root, target)
    except Exception as exc:
        b.seal_json(
            directory / "failure.json",
            dict(
                category="battle_execution",
                error_type=type(exc).__name__,
                benchmark=ref(target / "plan.json"),
            ),
        )
        budget.halt(study, cohort, "battle_execution", directory / "failure.json")
        raise
    b.seal_json(directory / "battle-report.json", report)
    checks = battle_checks(target, planned=32)
    b.seal_json(directory / "checks.json", checks)
    attempts = b.load_attempts(target)
    batches = [b.read_sealed(p) for p in (target / "batches").glob("*.json")]
    stop = next((x["stop_category"] for x in batches if x["stop_category"]), None)
    seen = {a["slot_id"] for a in attempts}
    result = dict(
        **gate_evidence(manifest),
        **policy.selected(ex["evidence"]),
        profile=PROFILE,
        stage="compare32",
        conditions=CONDITIONS_AB,
        source_files=source_identity(),
        skipped=skipped_for(manifest),
        benchmark=ref(target / "plan.json"),
        prepared=ref(prepared),
        slots_processed=len(attempts),
        natural_completions=sum(a["eligible"] for a in attempts),
        planned=32,
        checks=checks,
        stop_category=stop,
        unexecuted=[
            dict(slot_id=s["slot_id"], reason=stop or "not_dispatched")
            for s in slots
            if s["slot_id"] not in seen
        ],
        passed=not checks["isolation_errors"] and len(attempts) == 32,
        comparison_complete=sum(a["eligible"] for a in attempts) == 32,
    )
    b.seal_json(directory / "result.json", result)
    if stop or checks["isolation_errors"]:
        budget.halt(study, cohort, stop or "integrity", directory / "result.json")
    return result
