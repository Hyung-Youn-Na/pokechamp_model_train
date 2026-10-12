"""D-030 A/B preparation, collection, review, battle, recovery and reporting CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .. import benchmark as b
from ..execution import (
    DEFAULT_CONCURRENCY,
    concurrency_fields,
    gate_evidence,
    gate_parallel,
)
from . import battle_only_budget as budget
from . import experiment_policy as policy
from .battle_only_protocol import (
    PROFILE,
    read_stage,
    ref,
    restrict_schedule,
    seal_stage,
)
from .receipts import require_budget


def execution(prepared, *, stage, previous, study=None, cohort="c0"):
    from .battle_prompts import selected

    manifest = b.read_sealed(Path(prepared).parent / "manifest.json")
    prompt = selected(manifest)
    fake = stage == "fake32"
    evidence = dict(
        **gate_evidence(manifest),
        **policy.selected(manifest),
        decision="D-031" if prompt["version"] != "v1.0.0" else "D-030",
        battle_prompt_version=prompt["version"],
        battle_prompt_identity=prompt,
        profile=PROFILE,
        io_offline_gate=str(Path(prepared).resolve()),
        io_transport="fake" if fake else "cloud",
    )
    from ..observation import OFFICIAL, selection, validate_selection

    if validate_selection(manifest) == OFFICIAL:
        evidence.update(selection(OFFICIAL))
    if policy.selected(manifest):
        evidence["decision"] = manifest["experiment_policy_identity"]["decision"]
    if policy.is_v2_repeat(manifest):
        from .inputfix32 import verify_runtime

        evidence.update(verify_runtime(manifest))
    deadline = None
    if not fake:
        current = budget.require_cohort(study, cohort)
        evidence.update(
            io_stage_gate=str(Path(previous).resolve()),
            io_study_root=str(Path(study).resolve()),
            io_cohort=cohort,
            io_stage=stage,
        )
        if cohort == "c1":
            evidence["io_recovery"] = current["recovery"]
        deadline = budget.clock(study)["stop_new_work_at"]
    return dict(
        version=1,
        **concurrency_fields(gate_parallel(manifest)),
        retry_transient=0,
        evidence=evidence,
        stop_new_work_at=deadline,
    )


def battle_stage(
    root,
    prepared,
    previous,
    directory,
    *,
    stage,
    study=None,
    cohort="c0",
    experiment_id=None,
):
    from ..action_study import parallel_budget
    from .memory_fixture import run as cadence
    from .study import battle_checks

    if policy.is_direct(b.read_sealed(prepared)):
        from .direct32 import run

        if stage != "compare32":
            raise ValueError("direct32 permits only the main comparison")
        return run(
            root,
            prepared,
            directory,
            study=study,
            cohort=cohort,
            experiment_id=experiment_id,
        )
    predecessor = {"fake32": "prepare", "smoke8": "cloud_gate", "compare32": "smoke8"}[
        stage
    ]
    receipt = read_stage(previous, predecessor)
    read_stage(prepared, "prepare")
    config = (
        b.BATTLE_ONLY_SMOKE_CONFIG
        if stage == "smoke8"
        else b.BATTLE_ONLY_COMPARE_CONFIG
    )
    ex = execution(prepared, stage=stage, previous=previous, study=study, cohort=cohort)
    slots = restrict_schedule(b.make_schedule(config, {})["schedule"], ex)
    estimate = None
    if stage != "fake32":
        if stage == "compare32":
            attempts = b.load_attempts(Path(receipt["benchmark"]["path"]).parent)
            estimate = parallel_budget(attempts, slots, workers=ex["battle_concurrency"])
            require_budget(budget.clock(study), estimate["with_margin_seconds"])
        else:
            require_budget(budget.clock(study))
    directory.mkdir(parents=True, exist_ok=False)
    outputs = []
    if stage == "fake32":
        check = cadence(
            battle_only=True,
            battle_prompt_version=ex["evidence"]["battle_prompt_version"],
        )
        b.seal_json(directory / "no-memory.json", check)
        if not check["passed"]:
            raise ValueError("B31 action no-memory qualification failed")
        outputs.append(directory / "no-memory.json")
    else:
        budget.claim_stage(
            study, cohort, stage, [s["slot_id"] for s in slots], directory
        )
    if estimate:
        b.seal_json(directory / "budget.json", estimate)
        outputs.append(directory / "budget.json")
    b.seal_json(directory / "config.json", config)
    b.seal_json(directory / "execution.json", ex)
    prefix = "ex027" if policy.selected(ex["evidence"]) else "ex026"
    experiment_id = experiment_id or f"{prefix}-{cohort}-{directory.name}"
    b.plan(root, experiment_id, directory / "config.json", directory / "execution.json")
    target = root / "benchmarks" / experiment_id
    b.seal_json(directory / "benchmark.json", ref(target / "plan.json"))
    try:
        report = b.run(root, target)
    except Exception as exc:
        b.seal_json(
            directory / "failure.json",
            dict(
                stage=stage,
                passed=False,
                error_type=type(exc).__name__,
                benchmark=ref(target / "plan.json"),
            ),
        )
        if stage != "fake32":
            budget.halt(study, cohort, "battle_execution", directory / "failure.json")
        raise
    b.seal_json(directory / "battle-report.json", report)
    try:
        checks = battle_checks(
            target, planned=len(slots)
        )
    except Exception as exc:
        b.seal_json(
            directory / "failure.json",
            dict(
                stage=stage,
                passed=False,
                error_type=type(exc).__name__,
                benchmark=ref(target / "plan.json"),
            ),
        )
        if stage != "fake32":
            budget.halt(study, cohort, "battle_validation", directory / "failure.json")
        raise
    b.seal_json(directory / "checks.json", checks)
    outputs += [directory / "checks.json", directory / "battle-report.json"]
    result = dict(
        checks,
        benchmark=ref(target / "plan.json"),
        cohort=cohort,
        intended_stage=stage,
        prepared=ref(prepared),
        summary_calls=checks["summary_calls"],
        planned=len(slots),
        budget_estimate=estimate,
    )
    result = seal_stage(directory / "result.json", stage, previous, result, outputs)
    if stage != "fake32" and not result["passed"]:
        budget.halt(study, cohort, "battle_gate", directory / "result.json")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "prepare",
            "register",
            "fake32",
            "collect",
            "review",
            "smoke8",
            "compare32",
            "recover",
            "report",
        ),
    )
    parser.add_argument(
        "--root", type=Path, default=b.WORKSPACE_ROOT / ".pokechamp-data"
    )
    parser.add_argument("--study-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--defect", type=Path)
    parser.add_argument("--cohort", choices=("c0", "c1", "e1"), default="c0")
    parser.add_argument("--experiment-id")
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--concurrency", type=int, choices=range(1, 11))
    from .battle_prompts import VERSIONS

    parser.add_argument(
        "--experiment-policy",
        choices=(
            policy.LIVE, policy.DIRECT, policy.CALCFIX, policy.INPUTFIX,
            policy.MOVEFIX, policy.EXTERNAL_REPEAT,
        ),
    )
    parser.add_argument(
        "--battle-prompt-version", choices=VERSIONS, default=None,
        help="new official prepare: v1.4.0; explicit legacy: v1.3.0; historical policy: its frozen version",
    )
    from ..observation import BACKENDS
    parser.add_argument("--observation-backend", choices=BACKENDS, default=None)
    parser.add_argument(
        "--battle-root",
        type=Path,
        default=b.WORKSPACE_ROOT
        / ".pokechamp-data/experiments/glm-upstream-fallback32-v1/battles",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=b.WORKSPACE_ROOT
        / ".pokechamp-data/benchmarks/glm-upstream-fallback32-v1"
        / "analysis/io_evidence.json",
    )
    args = parser.parse_args()
    if args.concurrency is not None and args.command != "prepare":
        parser.error("concurrency is selected only during prepare")
    if args.experiment_policy is not None and args.command != "prepare":
        parser.error("experiment policy is selected only during prepare")
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    if args.command == "prepare":
        from .battle_only_prepare import prepare

        result = prepare(
            args.battle_root,
            args.evidence,
            args.output,
            battle_prompt_version=args.battle_prompt_version,
            experiment_policy=args.experiment_policy,
            verification=args.verification,
            observation_backend=args.observation_backend,
            concurrency=args.concurrency if args.concurrency is not None else DEFAULT_CONCURRENCY,
        )
    elif args.command == "register":
        read_stage(args.prepared, "prepare")
        result = budget.register(args.study_root, args.prepared)
    elif args.command in ("fake32", "smoke8", "compare32"):
        result = battle_stage(
            args.root,
            args.prepared,
            args.previous,
            args.output,
            stage=args.command,
            study=args.study_root,
            cohort=args.cohort,
            experiment_id=args.experiment_id,
        )
    elif args.command == "collect":
        from .battle_only_gate import collect

        result = collect(
            args.study_root,
            args.prepared,
            args.previous,
            args.output,
            cohort=args.cohort,
        )
    elif args.command == "review":
        from .battle_only_gate import finish

        result = finish(args.study_root, args.output, args.review, cohort=args.cohort)
    elif args.command == "recover":
        result = budget.recover(args.study_root, args.defect, args.prepared)
    else:
        from .battle_only_report import report

        result = report(args.study_root, args.output, review=args.review)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ("source_files", "rows", "outputs")
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.get("passed", result.get("technical_passed", True)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
