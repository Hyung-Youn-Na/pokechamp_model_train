"""EX-020 stage execution, denominators, and restart-stable budget management."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .. import benchmark as b
from ..execution import DEFAULT_CONCURRENCY, concurrency_evidence, concurrency_fields
from ..parallel_server import check_ports
from .receipts import read_stage, seal_stage


def execution(
    offline, *, fake, previous=None, clock=None, clock_path=None, summary_prompt_version=None,
    concurrency=DEFAULT_CONCURRENCY,
):
    evidence = {
        **concurrency_evidence(),
        "decision": "D-022",
        "io_offline_gate": str(Path(offline).resolve()),
        "io_transport": "fake" if fake else "cloud",
    }
    if not fake:
        evidence.update(
            io_stage_gate=str(Path(previous).resolve()),
            io_cloud_clock=str(Path(clock_path).resolve()),
        )
    if summary_prompt_version is not None:
        from .prompt_versions import identity

        evidence.update(
            decision="D-027",
            io_summary_prompt_version=summary_prompt_version,
            io_summary_prompt_identity=identity(summary_prompt_version),
        )
    return dict(
        version=1,
        **concurrency_fields(concurrency),
        retry_transient=0,
        evidence=evidence,
        stop_new_work_at=None if fake else clock["stop_new_work_at"],
    )


def battle_checks(directory, *, planned, expected_concurrency=None):
    value = b.verify_plan(directory)
    configured = value["execution"]["battle_concurrency"]
    declared = min(configured, planned)
    if expected_concurrency is not None and expected_concurrency != declared:
        raise ValueError("expected concurrency differs from sealed execution")
    expected_concurrency = declared
    attempts = b.load_attempts(directory)
    b.validate_attempts(value, attempts)
    runtimes, identities, calculator_pids = [], [], []
    errors = []
    spans = []
    from .battle_prompts import assemble
    from .battle_prompts import selected as select_battle_prompt
    from .prompt_versions import asset, selected

    battle_only = value["config"].get("profile") == "io-battle-only-v1"
    prompt_identity = None if battle_only else selected(value.get("execution"))
    battle_identity = (
        select_battle_prompt(value.get("execution", {}).get("evidence", {}))
        if battle_only else None
    )
    for attempt in attempts:
        interval = []
        for role, actor in attempt["actors"].items():
            if actor.get("bundle"):
                valid = b.verify_bundle(Path(actor["bundle"]))["valid"]
                if not valid:
                    errors.append("actor seal")
                if "io_summary_prompt_version" in value.get("execution", {}).get("evidence", {}):
                    for line in (Path(actor["bundle"]) / "events.jsonl").read_text().splitlines():
                        event = json.loads(line)
                        request = event.get("request", {})
                        call_role = request.get("call_role")
                        if event["event_type"] == "llm_call" and call_role in (
                            "summary",
                            "summary_rollup",
                        ):
                            if (
                                event["system_prompt"]
                                != asset(call_role, prompt_identity["version"])[0]
                                or request.get("summary_prompt_identity") != prompt_identity
                            ):
                                errors.append("actual summary prompt mismatch")
                if battle_only:
                    from .battle_only_protocol import validate_context

                    for line in (Path(actor["bundle"]) / "events.jsonl").read_text().splitlines():
                        event = json.loads(line)
                        if event["event_type"] != "llm_call":
                            continue
                        call_role = event.get("request", {}).get("call_role")
                        if call_role in ("summary", "summary_rollup"):
                            errors.append("battle-only summary call")
                        if attempt["slot"]["condition_id"] == "B":
                            context = json.loads(event["user_prompt"])
                            validate_context(context, role=call_role)
                            expected = assemble(context, version=battle_identity["version"],
                                                declared=battle_identity)
                            # Historical v1.0.0 calls predate explicit battle identity metadata.
                            legacy = (battle_identity
                                      if battle_identity["version"] == "v1.0.0" else None)
                            declared = event.get("request", {}).get(
                                "battle_prompt_identity", legacy
                            )
                            if event["system_prompt"] != expected or declared != battle_identity:
                                errors.append("battle-only action prompt drift")
                if role == "p1":
                    events = [
                        json.loads(line)
                        for line in (Path(actor["bundle"]) / "events.jsonl")
                        .read_text()
                        .splitlines()
                    ]
                    starts = [
                        e
                        for e in events
                        if e["event_type"] == "protocol_in"
                        and "|start" in e["protocol"].splitlines()
                    ]
                    if starts:
                        interval = [
                            datetime.fromisoformat(e["timestamp_utc"]).timestamp()
                            for e in (starts[0], events[-1])
                        ]
            runtime = actor.get("io_runtime")
            if runtime:
                if runtime.get("summary_prompt_identity", prompt_identity) != prompt_identity:
                    errors.append("summary prompt identity")
                runtimes.append(runtime)
                identities.append((runtime["battle_id"], runtime["actor_id"]))
                if runtime["calculator_pid"] is not None:
                    calculator_pids.append(runtime["calculator_pid"])
                if not runtime["calculator_closed"] or runtime["actor_id"] != role:
                    errors.append("actor/calculator isolation")
                archive = runtime["memory_archive"]
                if attempt["slot"]["condition_id"] == "B" and archive:
                    errors.append("B memory leak")
                summaries = sum(a["role"] == "summary" for a in archive)
                rollups = sum(a["role"] == "summary_rollup" for a in archive)
                if attempt["slot"]["condition_id"] == "C" and attempt["eligible"]:
                    if summaries != max(0, (runtime["decisions"] - 1) // 10):
                        errors.append("summary cadence")
                    if rollups != summaries // 3:
                        errors.append("rollup cadence")
        if interval:
            spans.append(interval)
    if len(identities) != len(set(identities)):
        errors.append("duplicate actor identity")
    if len(calculator_pids) != len(set(calculator_pids)):
        errors.append("shared calculator process")
    batches = [b.read_sealed(p) for p in (directory / "batches").glob("*.json")]
    maximum = max((x["maximum_battles"] for x in batches), default=0)
    active = actual_maximum = 0
    for _, delta in sorted([(s, 1) for s, _ in spans] + [(e, -1) for _, e in spans]):
        active += delta
        actual_maximum = max(active, actual_maximum)
    check_ports(list(range(8100, 8100 + configured)))
    eligible = sum(a["eligible"] for a in attempts)
    passed = (
        len(attempts) == planned
        and eligible == planned
        and not errors
        and maximum == expected_concurrency
        and actual_maximum == expected_concurrency
    )
    return dict(
        passed=passed,
        planned=planned,
        attempted=len(attempts),
        completed=eligible,
        failed=sum(not a["eligible"] for a in attempts),
        unexecuted=planned - len(attempts),
        maximum_battles=maximum,
        maximum_observed_battles=actual_maximum,
        isolation_errors=errors,
        runtime_actors=len(runtimes),
        summary_calls=sum(
            sum(a["role"] == "summary" for a in r["memory_archive"]) for r in runtimes
        ),
        rollup_calls=sum(
            sum(a["role"] == "summary_rollup" for a in r["memory_archive"]) for r in runtimes
        ),
        ports_released=True,
        benchmark_path=str(directory.resolve()),
        benchmark_plan_sha256=b.digest(directory / "plan.json"),
        summary_prompt_identity=prompt_identity,
    )


def battle_stage(
    root,
    directory,
    offline,
    previous,
    *,
    stage,
    clock=None,
    clock_path=None,
    budget=None,
    experiment_id=None,
    summary_prompt_version=None,
    concurrency=DEFAULT_CONCURRENCY,
):
    read_stage(
        previous, {"fake12": "offline", "smoke12": "cloud_gate", "compare48": "smoke12"}[stage]
    )
    directory.mkdir(parents=True, exist_ok=False)
    extra_outputs = []
    if stage == "fake12":
        from .memory_fixture import run as cadence

        result = cadence(summary_prompt_version or "v1.0.0")
        b.seal_json(directory / "cadence.json", result)
        if not result["passed"]:
            raise ValueError("local cadence gate failed")
        extra_outputs.append(directory / "cadence.json")
    if budget is not None:
        b.seal_json(directory / "budget.json", budget)
        extra_outputs.append(directory / "budget.json")
    config = b.IO_COMPARE_CONFIG if stage == "compare48" else b.IO_SMOKE_CONFIG
    b.seal_json(directory / "config.json", config)
    b.seal_json(
        directory / "execution.json",
        execution(
            offline,
            fake=stage == "fake12",
            previous=previous,
            clock=clock,
            clock_path=clock_path,
            summary_prompt_version=summary_prompt_version,
            concurrency=concurrency,
        ),
    )
    experiment_id = experiment_id or "ex020-" + directory.name
    b.plan(root, experiment_id, directory / "config.json", directory / "execution.json")
    target = root / "benchmarks" / experiment_id
    report = b.run(root, target)
    b.seal_json(directory / "battle-report.json", report)
    checks = battle_checks(target, planned=48 if stage == "compare48" else 12)
    b.seal_json(directory / "checks.json", checks)
    return seal_stage(
        directory / "result.json",
        stage,
        previous,
        checks,
        [directory / "checks.json", directory / "battle-report.json", *extra_outputs],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stage", choices=["fake12", "cloud_gate", "finish_cloud", "smoke12", "compare48"]
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--study-root", type=Path)
    parser.add_argument("--battle-root", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--summary-prompt-version")
    parser.add_argument("--concurrency", type=int, choices=range(1, 11), default=DEFAULT_CONCURRENCY)
    parser.add_argument(
        "--experiment-id", help="New benchmark identity; legacy default is preserved"
    )
    args = parser.parse_args()
    if args.stage == "cloud_gate":
        import fcntl

        from .cloud_gate import collect

        cli_root = b.cli.ARTIFACT_ROOT
        cli_root.mkdir(parents=True, exist_ok=True)
        with (cli_root / "benchmark-runtime.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = collect(
                args.root.resolve(),
                args.output.resolve(),
                args.offline.resolve(),
                args.previous.resolve(),
                args.study_root.resolve(),
                args.battle_root.resolve(),
                concurrency=args.concurrency,
            )
    elif args.stage == "finish_cloud":
        from .cloud_gate import finish

        result = finish(args.output.resolve(), args.previous.resolve(), args.review.resolve())
    elif args.stage in ("smoke12", "compare48"):
        from ..action_study import parallel_budget
        from .receipts import cloud_clock, require_budget

        clock = cloud_clock(args.study_root.resolve())
        require_budget(clock)
        budget = None
        if args.stage == "compare48":
            smoke = read_stage(args.previous.resolve(), "smoke12")
            attempts = b.load_attempts(Path(smoke["benchmark_path"]))
            schedule = b.make_schedule(b.IO_COMPARE_CONFIG, {})["schedule"]
            budget = parallel_budget(attempts, schedule, workers=args.concurrency)
            require_budget(clock, budget["with_margin_seconds"])
        result = battle_stage(
            args.root.resolve(),
            args.output.resolve(),
            args.offline.resolve(),
            args.previous.resolve(),
            stage=args.stage,
            clock=clock,
            clock_path=args.study_root.resolve() / "cloud-clock.json",
            budget=budget,
            experiment_id=args.experiment_id,
            summary_prompt_version=args.summary_prompt_version,
            concurrency=args.concurrency,
        )
    else:
        result = battle_stage(
            args.root.resolve(),
            args.output.resolve(),
            args.offline.resolve(),
            args.offline.resolve(),
            stage=args.stage,
            experiment_id=args.experiment_id,
            summary_prompt_version=args.summary_prompt_version,
            concurrency=args.concurrency,
        )
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
