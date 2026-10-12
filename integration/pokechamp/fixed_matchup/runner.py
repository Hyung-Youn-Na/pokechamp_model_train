"""The explicit experiment command. Importing this module does not start work."""
from __future__ import annotations

import copy
import gzip
import json
import os
from pathlib import Path
import random
import statistics
import time

from . import artifacts
from .battle import BudgetExpired
from .config import PROTOCOL, SEED
from .pool import Pool
from .prepare import verify_identity
from .reporting import pilot_gate, score
from .runtime import Clock, own_gpu, own_run
from .storage import atomic, digest, read, seed, sha


def run_group(directory, schedule, teams, models, clock, setting, model_files):
    directory = Path(directory)
    found, pending = artifacts.existing(directory, schedule)
    hashes = {name: sha(directory / file) for name, file in model_files.items()}
    for row in found:
        if row["status"] == "invalid":
            raise RuntimeError("reserved slot has a shared pipeline failure; recovery judgment required")
        if row["status"] == "completed" and row.get("model_hashes") != hashes:
            raise ValueError("completed slot used a different model snapshot")
    if not pending:
        return found
    jobs = [dict(job, deadline=clock.stage_end) for job in pending]
    started = time.monotonic()
    def receive(result):
        result["model_hashes"] = hashes
        # Pool-level failures have no game body but retain a reserved slot.
        result.setdefault("winner", None)
        result.setdefault("records", [])
        result.setdefault("evidence", None)
        row = artifacts.save_result(directory, result)
        found.append(row)
    with Pool(teams, models, game_seconds=clock.protocol["game_seconds"], **setting) as pool:
        pool.collect(jobs, on_submit=lambda job: artifacts.claim(directory, job),
                     on_result=receive, check=clock.check, retain=False)
        metrics = dict(pool.metrics)
    atomic(directory / "measurements" / f"group-{time.time_ns()}.json",
           dict(slots=[r["slot_id"] for r in pending], seconds=time.monotonic() - started,
                settings=setting, inference=metrics), exclusive=True)
    return found


def benchmark_group(directory, label, jobs, teams, p0, clock, setting):
    """Resume completed probes, but never replay an unfinished reserved probe."""
    directory = Path(directory)
    start_path = directory / "benchmarks" / f"{label}-start.json"
    if not start_path.exists():
        atomic(start_path, dict(start=time.time(), settings=setting), exclusive=True)
    started = read(start_path)
    if started["settings"] != setting:
        raise ValueError("benchmark settings changed")
    results, pending = [], []
    for job in jobs:
        identity = {k: v for k, v in job.items() if k not in ("deadline", "root")}
        claim = directory / "benchmarks/claims" / f"{job['slot_id']}.json"
        path = directory / "benchmarks/results" / f"{job['slot_id']}.json"
        if path.exists():
            row = read(path)
            if (row["job"] != identity or row["status"] != "completed"
                    or read(claim)["root_hash"] != digest(job["root"])):
                raise ValueError("benchmark result/identity changed or failed")
            results.append(row)
        elif claim.exists():
            raise RuntimeError("unfinished reserved benchmark probe; no automatic replay")
        else:
            pending.append(job)
    metric = {}
    if pending:
        def receive(row):
            atomic(directory / "benchmarks/results" / f"{row['job']['slot_id']}.json", row, exclusive=True)
            results.append(row)
        with Pool(teams, {"P0": p0}, **setting) as pool:
            pool.collect(pending, on_submit=lambda job: atomic(
                directory / "benchmarks/claims" / f"{job['slot_id']}.json",
                dict(job={k: v for k, v in job.items() if k not in ("deadline", "root")},
                     root_hash=digest(job["root"])), exclusive=True),
                on_result=receive, check=clock.check, retain=False)
            metric = dict(pool.metrics)
    seconds = time.time() - started["start"]
    transitions = sum(r["metrics"]["transitions"] for r in results)
    return dict(**setting, seconds=seconds, transitions=transitions,
                transitions_per_second=transitions / seconds, inference_this_invocation=metric)


def benchmark(directory, teams, p0, pilot_rows, clock):
    directory = Path(directory)
    saved = directory / "settings.json"
    if saved.exists():
        return read(saved)
    roots = []
    for row in sorted(pilot_rows, key=lambda r: r["job"]["slot_id"]):
        path = directory / "games" / row["job"]["slot_id"] / "public-roots.json.gz"
        with gzip.open(path, "rt") as stream:
            choices = json.load(stream)
        roots.extend(choices[1:4])
    if not roots:
        raise ValueError("no non-preview pilot roots")
    measurements = []
    for workers in PROTOCOL["workers"]:
        for batch in PROTOCOL["inference_batches"]:
            clock.check()
            label = f"w{workers}-b{batch}-n64"
            path = directory / "benchmarks" / f"{label}.json"
            if path.exists():
                measurements.append(read(path))
                continue
            jobs = [dict(kind="probe", slot_id=f"{label}-{i}", root=roots[i % len(roots)],
                         seed=seed("benchmark", i), simulations=64, deadline=clock.stage_end) for i in range(16)]
            row = benchmark_group(directory, label, jobs, teams, p0, clock,
                                  dict(workers=workers, batch_size=batch))
            atomic(path, row, exclusive=True)
            measurements.append(row)
    best = sorted(measurements, key=lambda r: (-r["transitions_per_second"], r["workers"], r["batch_size"]))[0]
    setting = {k: best[k] for k in ("workers", "batch_size")}
    # The selected configuration also measures N=32/128. These do not change the experiment N=64.
    for simulations in (32, 128):
        path = directory / "benchmarks" / f"selected-n{simulations}.json"
        if path.exists():
            continue
        jobs = [dict(kind="probe", slot_id=f"selected-n{simulations}-{i}", root=roots[i % len(roots)],
                     seed=seed("benchmark-extra", i), simulations=simulations, deadline=clock.stage_end)
                for i in range(16)]
        result = benchmark_group(directory, f"selected-n{simulations}", jobs, teams, p0, clock, setting)
        atomic(path, dict(simulations=simulations, **result), exclusive=True)
    atomic(saved, setting, exclusive=True)
    return setting


def policy_phase(directory, manifest, teams, schedules, p0, clock, setting):
    import torch
    from .model import Policy, learn

    directory = Path(directory)
    selected_file = directory / "selection.json"
    if selected_file.exists():
        selection = read(selected_file)
        if sha(directory / selection["file"]) != selection["sha256"]:
            raise ValueError("selected policy changed")
        return selection
    clock.enter("train", check_deadline=False)
    policy = Policy.load(directory / "models/P0.pt", "cuda:0")
    optimizer = torch.optim.AdamW(policy.parameters(), lr=PROTOCOL["lr"], weight_decay=PROTOCOL["weight_decay"])
    generator = torch.Generator().manual_seed(seed("optimizer-shuffle"))
    if artifacts.committed_pointer(directory) is not None:
        checkpoint = artifacts.restore_checkpoint(directory, policy, optimizer, generator, identity=manifest["identity"])
        first_round, updates = checkpoint["round"] + 1, checkpoint["updates"]
        artifacts.publish_round(directory, checkpoint)
    else:
        artifacts.save_checkpoint(directory, 0, policy, optimizer, generator, identity=manifest["identity"],
                                  replay_ids=[], updates=0)
        first_round, updates = 1, 0

    def finish_dev(round_id):
        if not round_id or round_id % PROTOCOL["dev_interval"]:
            return
        path = directory / "dev" / f"round-{round_id:03d}.json"
        if path.exists():
            record = read(path)
            if record["sha256"] != sha(directory / record["file"]):
                raise ValueError("dev model checksum changed")
            return
        clock.check()
        name = f"models/round-{round_id:03d}.pt"
        rows = run_group(directory, schedules["dev"][str(round_id)], teams,
                         {"current": policy, "P0": p0}, clock, setting,
                         {"current": name, "P0": "models/P0.pt"})
        if len(rows) == 64 and all(r["status"] == "completed" for r in rows):
            atomic(path, dict(round=round_id, score=statistics.mean(score(r) for r in rows),
                             file=name, sha256=sha(directory / name)), exclusive=True)

    try:
        finish_dev(first_round - 1)
        for round_id in range(first_round, PROTOCOL["max_rounds"] + 1):
            clock.check()
            parent = "models/P0.pt" if round_id == 1 else f"models/round-{round_id - 1:03d}.pt"
            rows = run_group(directory, schedules["train"][round_id - 1], teams, {"current": policy},
                             clock, setting, {"current": parent})
            if len(rows) != PROTOCOL["round_games"] or any(r["status"] != "completed" for r in rows):
                atomic(directory / "train-stop.json", dict(reason="incomplete_round", round=round_id))
                break
            replay = artifacts.replay_rows(directory, round_id)
            result = learn(policy, optimizer, replay, generator=generator, check=clock.check)
            updates += result["steps"]
            name = f"models/round-{round_id:03d}.pt"
            # Publish the full training checkpoint first; an interrupted model export can be regenerated.
            artifacts.save_checkpoint(directory, round_id, policy, optimizer, generator,
                identity=manifest["identity"], replay_ids=[r["id"] for r in replay], updates=updates, learning=result)
            checkpoint = artifacts.restore_checkpoint(directory, policy, optimizer, generator, identity=manifest["identity"])
            artifacts.publish_round(directory, checkpoint)
            finish_dev(round_id)
    except BudgetExpired:
        if clock.cancelled:
            raise
        atomic(directory / "train-stop.json", dict(reason="stage_deadline", latest=read(directory / "latest.json")))
    candidates = [read(p) for p in (directory / "dev").glob("round-*.json")]
    if not candidates:
        raise RuntimeError("no completed trained dev candidate; test remains locked")
    selected = sorted(candidates, key=lambda r: (-r["score"], r["round"]))[0]
    atomic(selected_file, selected, exclusive=True)
    return selected


def run(directory):
    directory = Path(directory)
    manifest = verify_identity(directory)
    if any((directory / name).exists() for name in ("completed.json", "incomplete.json")):
        raise RuntimeError("experiment already closed; no automatic additional cycle")
    teams = {label: (directory / "teams" / row["file"]).read_text() for label, row in manifest["teams"].items()}
    schedules = read(directory / "schedule.json")
    # GPU ownership and visibility must precede CUDA initialization/importing model modules.
    with own_run(directory), own_gpu(directory):
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        import torch
        from .model import Policy
        from .verification import verify
        from .finalize import finalize

        if torch.cuda.is_initialized():
            raise RuntimeError("CUDA was initialized before owned resource binding")
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.cuda.set_per_process_memory_fraction(PROTOCOL["gpu_bytes"] / torch.cuda.get_device_properties(0).total_memory)
        clock = Clock(directory)
        with clock.signals():
            try:
                if not (directory / "verification.json").exists():
                    clock.enter("verify")
                    verification = verify(device="cuda:0")
                    clock.check()
                    atomic(directory / "verification.json", dict(verification, identity=manifest["identity"]), exclusive=True)
                verification = read(directory / "verification.json")
                if not verification.get("passed") or verification["identity"] != manifest["identity"]:
                    raise ValueError("verification receipt invalid")
                p0 = artifacts.initial_model(directory, read(directory / "catalog.json")["vocabulary"],
                                             manifest["identity"], "cuda:0")
                if not (directory / "pilot-gate.json").exists():
                    clock.enter("pilot")
                    uniform_jobs = [j for j in schedules["pilot"] if j["condition"] == "uniform"]
                    random_rows = run_group(directory, uniform_jobs, teams, {"P0": p0}, clock,
                                            dict(workers=8, batch_size=16), {"P0": "models/P0.pt"})
                    if (len(random_rows) != 32 or any(r["status"] != "completed" and
                            not (r["status"] == "incomplete" and r.get("reason") == "turn_limit")
                            for r in random_rows)
                            or sum(r["status"] == "incomplete" for r in random_rows) / 32 > 0.05):
                        raise RuntimeError("uniform pilot did not complete; no benchmark/training")
                    setting = benchmark(directory, teams, p0, random_rows, clock)
                    started = time.monotonic()
                    initial_jobs = [j for j in schedules["pilot"] if j["condition"] == "P0"]
                    policy_rows = run_group(directory, initial_jobs, teams, {"P0": p0}, clock,
                                            setting, {"P0": "models/P0.pt"})
                    elapsed = time.monotonic() - started
                    # Conservative bound: twice observed wall/throughput and twice slow-game average.
                    lengths = sorted(r.get("metrics", {}).get("seconds", 0) for r in policy_rows)
                    p95 = lengths[min(len(lengths) - 1, int(0.95 * len(lengths)))] if lengths else float("inf")
                    projection = 2 * 640 * max(elapsed / max(1, len(policy_rows)), p95 / setting["workers"])
                    gate = pilot_gate(random_rows + policy_rows, projected_test_seconds=projection)
                    whole = time.time() - clock.first + PROTOCOL["stage_seconds"]["train"] + projection + PROTOCOL["stage_seconds"]["finalize"]
                    if whole > PROTOCOL["total_seconds"]:
                        gate["reasons"].append("whole_run_budget")
                        gate["passed"] = False
                    atomic(directory / "pilot-gate.json", dict(gate, settings=setting, measured_wall=elapsed,
                           projected_whole_seconds=whole), exclusive=True)
                gate = read(directory / "pilot-gate.json")
                if not gate["passed"]:
                    raise RuntimeError("pilot gate failed; no training: " + str(gate["reasons"]))
                setting = gate["settings"]
                selection = policy_phase(directory, manifest, teams, schedules, p0, clock, setting)
                lock = dict(identity=manifest["identity"], P0=sha(directory / "models/P0.pt"),
                            P1=selection["sha256"], selected_file=selection["file"], settings=setting,
                            schedule_sha256=sha(directory / "schedule.json"), simulations=64, temperature=1.0)
                lock_path = directory / "evaluation-lock.json"
                if lock_path.exists() and read(lock_path) != lock:
                    raise ValueError("evaluation lock changed")
                if not lock_path.exists():
                    atomic(lock_path, lock, exclusive=True)
                p1 = Policy.load(directory / selection["file"], "cuda:0")
                clock.enter("test", check_deadline=False)
                try:
                    clock.check()
                    run_group(directory, schedules["test"], teams, {"P0": p0, "P1": p1}, clock, setting,
                              {"P0": "models/P0.pt", "P1": selection["file"]})
                except BudgetExpired:
                    if clock.cancelled:
                        raise
                    artifacts.existing(directory, schedules["test"])
                clock.enter("finalize")
                result = finalize(directory, check=clock.check)
                clock.check()
                receipt_name = "completed.json" if result["procedure_complete"] else "incomplete.json"
                atomic(directory / receipt_name, dict(result, identity=manifest["identity"],
                       at=time.time(), elapsed=time.time() - clock.first, peak_rss=clock.peak_rss), exclusive=True)
                return result
            except BaseException as error:
                atomic(directory / "stops" / f"{time.time_ns()}.json",
                       dict(stage=clock.stage, reason=f"{type(error).__name__}: {error}",
                            at=time.time(), first=clock.first, elapsed=time.time() - clock.first), exclusive=True)
                # Never collect after a failure. Preserve all reserved slots, then
                # attempt bounded CPU audit/export without renewing the first clock.
                try:
                    for group in [schedules["pilot"], schedules["test"], *schedules["train"], *schedules["dev"].values()]:
                        artifacts.existing(directory, group)
                    if (directory / "games").exists() and not clock.cancelled:
                        clock.enter("finalize")
                        finalize(directory, check=clock.check)
                except Exception as cleanup_error:
                    atomic(directory / "stops" / f"{time.time_ns()}-finalization.json",
                           dict(reason=f"{type(cleanup_error).__name__}: {cleanup_error}", at=time.time()), exclusive=True)
                raise
