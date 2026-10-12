"""EX-079 continuation with audited development stopping and an immutable test lock."""
from pathlib import Path
import math
import os
import statistics
import time

from . import artifacts
from .prepare import verify_identity
from .reporting import score
from .runner import run_group
from .runtime import Clock, own_gpu, own_run
from .stopping import PROTOCOL, SETTING, schedule, stopping_decision
from .storage import atomic, digest, read, seed, sha


def _normal_rows(directory, jobs, model_files, clock, *, collect=None):
    """Never start a remaining slot if this group already contains a failed reservation."""
    from .finalize import audit_game
    rows, pending = artifacts.existing(directory, jobs)
    if any(row["status"] != "completed" for row in rows):
        raise RuntimeError("incomplete reserved group; automatic retry/replacement forbidden")
    if pending:
        if collect is None:
            raise ValueError("required completed group is missing slots")
        rows = collect()
    if (len(rows) != len(jobs) or any(row["status"] != "completed" for row in rows)
            or {row["job"]["slot_id"] for row in rows} != {job["slot_id"] for job in jobs}):
        raise RuntimeError("all scheduled games must complete normally before dependent work")
    expected_jobs = {job["slot_id"]: job for job in jobs}
    if any(row["job"] != expected_jobs[row["job"]["slot_id"]] for row in rows):
        raise ValueError("collected game identity disagrees with frozen schedule")
    hashes = {key: sha(Path(directory) / name) for key, name in model_files.items()}
    for row in rows:
        clock.check()
        if row.get("model_hashes") != hashes:
            raise ValueError("group used a different model snapshot")
        audit_game(Path(directory) / "games" / row["job"]["slot_id"])
    return rows


def _dev_record(directory, manifest, jobs, rows, round_id):
    name = f"models/round-{round_id:03d}.pt"
    evidence = [dict(slot_id=row["job"]["slot_id"],
                     result_sha256=sha(directory / "games" / row["job"]["slot_id"] / "result.json"))
                for row in sorted(rows, key=lambda row: row["job"]["slot_id"])]
    return dict(round=round_id, score=statistics.mean(score(row) for row in rows),
                file=name, sha256=sha(directory / name), identity=manifest["identity"],
                schedule_sha256=digest(jobs), results_sha256=digest(evidence))


def _checkpoint_valid(directory, manifest, policy, checkpoint, clock):
    """Check complete restored learner state, replay membership and published predictions."""
    import torch
    from .model import Policy
    def finite(value):
        if torch.is_tensor(value):
            return bool(torch.isfinite(value).all())
        if isinstance(value, dict):
            return all(finite(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return all(finite(item) for item in value)
        return not isinstance(value, float) or math.isfinite(value)
    if (not 1 <= checkpoint["round"] <= 32 or checkpoint["updates"] < 44
            or not checkpoint["optimizer"]["state"] or not finite(checkpoint)
            or checkpoint["identity"] != manifest["identity"]
            or checkpoint["clock"] != read(directory / "clock.json")):
        raise ValueError("invalid complete learner checkpoint")
    replay = artifacts.replay_rows(directory, checkpoint["round"])
    ids = [row["id"] for row in replay]
    if not replay or checkpoint["replay_ids"] != ids or len(set(ids)) != len(ids):
        raise ValueError("checkpoint replay membership changed")
    name = artifacts.publish_round(directory, checkpoint)
    fresh = Policy.load(directory / name, policy.device)
    maximum = 0.0
    # Exact model tensor matching is enforced by publish_round. These observations
    # independently exercise encoder and inference after loading the exported file.
    sample = replay[:32] + replay[-32:]
    for offset in range(0, len(sample), 32):
        clock.check()
        observations = [row["observation"] for row in sample[offset:offset + 32]]
        for left, right in zip(policy.evaluate_batch(observations), fresh.evaluate_batch(observations)):
            if not all(math.isfinite(value) for result in (left, right)
                       for value in [result["value"], *result["policy"]]):
                raise ValueError("nonfinite checkpoint prediction")
            maximum = max(maximum, abs(left["value"] - right["value"]),
                          *(abs(a - b) for a, b in zip(left["policy"], right["policy"])))
    if not math.isfinite(maximum) or maximum > 1e-5:
        raise ValueError("checkpoint reload predictions disagree")
    record = dict(identity=manifest["identity"], round=checkpoint["round"],
                  updates=checkpoint["updates"], model_sha256=sha(directory / name),
                  replay_ids_sha256=digest(ids), finite=True, passed=True,
                  prediction_max_absolute_error=maximum, tolerance=1e-5,
                  observations_checked=len(sample))
    path = directory / "checkpoint-validation" / f"round-{checkpoint['round']:03d}.json"
    if path.exists():
        if read(path) != record:
            raise ValueError("checkpoint validation evidence changed")
    else:
        atomic(path, record, exclusive=True)
    return replay


def policy_phase(directory, manifest, teams, schedules, p0, clock, setting, *, device="cuda:0"):
    """Continue a complete inherited round 1 and return only a normally stopped selection."""
    import torch
    from .model import Policy, learn
    directory = Path(directory)
    if schedules != schedule() or setting != SETTING:
        raise ValueError("EX-079 schedule/settings changed")
    if not (directory / "inheritance.json").exists():
        raise ValueError("missing complete round1 inheritance")
    clock.enter("train")
    policy = Policy.load(directory / "models/P0.pt", device)
    optimizer = torch.optim.AdamW(policy.parameters(), lr=PROTOCOL["lr"], weight_decay=PROTOCOL["weight_decay"])
    generator = torch.Generator().manual_seed(seed("optimizer-shuffle"))
    checkpoint = artifacts.restore_checkpoint(directory, policy, optimizer, generator, identity=manifest["identity"])
    current = checkpoint["round"]
    if not 1 <= current <= 32:
        raise ValueError("EX-079 requires a complete round1 or later checkpoint")
    for path in (directory / "claims").glob("*.json"):
        job = read(path)["job"]
        if job["stage"].startswith("test") and not (directory / "evaluation-lock.json").exists():
            raise ValueError("test reservations exist without a selection lock")
        if ((job["stage"] == "train" and job["round_id"] > current + 1)
                or (job["stage"] == "dev" and job["round_id"] > current)):
            raise ValueError("reservations advanced beyond complete learner checkpoint")
    previous_updates = 0
    for round_id in range(current + 1):
        pointer = read(directory / "checkpoints" / f"round-{round_id:03d}.json")
        expected_file = f"checkpoints/round-{round_id:03d}.pt"
        if (pointer["round"] != round_id or pointer["file"] != expected_file
                or sha(directory / expected_file) != pointer["sha256"]):
            raise ValueError("checkpoint lineage checksum changed")
        prior = torch.load(directory / expected_file, map_location="cpu", weights_only=True)
        if (prior["round"] != round_id or prior["identity"] != manifest["identity"]
                or prior["clock"] != read(directory / "clock.json")):
            raise ValueError("checkpoint lineage identity/clock changed")
        if round_id == 0:
            if prior["updates"] != 0:
                raise ValueError("initial checkpoint has training updates")
        elif (prior["updates"] != previous_updates + prior["learning"]["steps"]
                or not 0 < prior["learning"]["steps"] <= PROTOCOL["max_steps"]
                or (round_id == 1 and prior["updates"] != 44)):
            raise ValueError("checkpoint lineage update count changed")
        previous_updates = prior["updates"]
        artifacts.publish_round(directory, prior)
    # Every completed training round is a prerequisite; re-audit evidence on resume.
    for round_id in range(1, current + 1):
        parent = "models/P0.pt" if round_id == 1 else f"models/round-{round_id - 1:03d}.pt"
        _normal_rows(directory, schedules["train"][round_id - 1], {"current": parent}, clock)
    _checkpoint_valid(directory, manifest, policy, checkpoint, clock)
    history = []
    paths = sorted((directory / "dev").glob("round-*.json"))
    for path in paths:
        record = read(path)
        round_id = record.get("round")
        if str(round_id) not in schedules["dev"] or round_id > current:
            raise ValueError("development evidence is ahead of completed checkpoint")
        jobs = schedules["dev"][str(round_id)]
        name = f"models/round-{round_id:03d}.pt"
        rows = _normal_rows(directory, jobs, {"current": name, "P0": "models/P0.pt"}, clock)
        expected = _dev_record(directory, manifest, jobs, rows, round_id)
        if record != expected or path.name != f"round-{round_id:03d}.json":
            raise ValueError("persisted development record disagrees with authoritative games")
        history.append(record)
    state = stopping_decision(history)
    required = [r for r in PROTOCOL["stopping"]["evaluation_rounds"] if r < current]
    if [record["round"] for record in history if record["round"] < current] != required:
        raise ValueError("checkpoint advanced without required development evaluation")
    stop_path, selected_path = directory / "training-stop.json", directory / "selection.json"
    lock_path = directory / "evaluation-lock.json"
    if (stop_path.exists() or selected_path.exists() or lock_path.exists()) and not state["stop"]:
        raise ValueError("selection/test lock exists without a normal stopping decision")
    if state["stop"] and current != state["round"]:
        raise ValueError("learner advanced beyond latched stopping decision")

    def finish_dev(round_id):
        nonlocal state
        if str(round_id) not in schedules["dev"] or any(row["round"] == round_id for row in history):
            return
        if stop_path.exists() or selected_path.exists() or lock_path.exists():
            raise ValueError("cannot evaluate another checkpoint after stop/selection/test lock")
        name = f"models/round-{round_id:03d}.pt"
        jobs = schedules["dev"][str(round_id)]
        model_files = {"current": name, "P0": "models/P0.pt"}
        rows = _normal_rows(directory, jobs, model_files, clock,
                           collect=lambda: run_group(directory, jobs, teams,
                               {"current": policy, "P0": p0}, clock, setting, model_files))
        record = _dev_record(directory, manifest, jobs, rows, round_id)
        atomic(directory / "dev" / f"round-{round_id:03d}.json", record, exclusive=True)
        history.append(record)
        state = stopping_decision(history)

    finish_dev(current)
    while not state["stop"] and current < PROTOCOL["max_rounds"]:
        if any(path.exists() for path in (stop_path, selected_path, lock_path)):
            raise ValueError("training forbidden after stop/selection/test lock")
        clock.check()
        round_id = current + 1
        parent = f"models/round-{current:03d}.pt"
        jobs = schedules["train"][round_id - 1]
        rows = _normal_rows(directory, jobs, {"current": parent}, clock,
                           collect=lambda: run_group(directory, jobs, teams, {"current": policy},
                               clock, setting, {"current": parent}))
        # Evaluation/export construction must not perturb the learner RNG stream.
        checkpoint = artifacts.restore_checkpoint(directory, policy, optimizer, generator, identity=manifest["identity"])
        replay = artifacts.replay_rows(directory, round_id)
        if not replay:
            raise ValueError("empty training replay")
        learning = learn(policy, optimizer, replay, generator=generator, check=clock.check,
                         batch_size=PROTOCOL["batch"], epochs=PROTOCOL["epochs"], max_steps=PROTOCOL["max_steps"])
        if not 0 < learning["steps"] <= PROTOCOL["max_steps"]:
            raise ValueError("training update count outside fixed protocol")
        artifacts.save_checkpoint(directory, round_id, policy, optimizer, generator,
            identity=manifest["identity"], replay_ids=[row["id"] for row in replay],
            updates=checkpoint["updates"] + learning["steps"], learning=learning)
        checkpoint = artifacts.restore_checkpoint(directory, policy, optimizer, generator, identity=manifest["identity"])
        _checkpoint_valid(directory, manifest, policy, checkpoint, clock)
        current = round_id
        finish_dev(current)
    if not state["stop"] or state["round"] != current:
        raise ValueError("no normal stopping decision; test remains locked")
    stop = dict(identity=manifest["identity"], history_sha256=digest(history), state=state)
    if stop_path.exists():
        if read(stop_path) != stop:
            raise ValueError("persisted stopping decision changed")
    else:
        atomic(stop_path, stop, exclusive=True)
    # A pre-existing later slot is evidence of advancement beyond the frozen stop.
    for path in (directory / "claims").glob("*.json"):
        job = read(path)["job"]
        if job["stage"] == "train" and job["round_id"] > current:
            raise ValueError("training reservations exist after stopped round")
    selected = next(row for row in history if row["round"] == state["best_round"])
    if selected_path.exists():
        if read(selected_path) != selected:
            raise ValueError("selected checkpoint changed after normal stopping")
    else:
        atomic(selected_path, selected, exclusive=True)
    return selected


def run_stopping(directory):
    directory = Path(directory)
    manifest = verify_identity(directory, protocol=PROTOCOL)
    if any((directory / name).exists() for name in ("completed.json", "incomplete.json")):
        raise RuntimeError("experiment already closed; no automatic additional cycle")
    schedules = read(directory / "schedule.json")
    if schedules != schedule() or read(directory / "settings.json") != SETTING:
        raise ValueError("EX-079 schedule/settings changed")
    teams = {key: (directory / "teams" / row["file"]).read_text() for key, row in manifest["teams"].items()}
    with own_run(directory), own_gpu(directory):
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
        import torch
        from .model import Policy
        from .verification import verify
        from .finalize import finalize
        if torch.cuda.is_initialized():
            raise RuntimeError("CUDA initialized before owned resource binding")
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.cuda.set_per_process_memory_fraction(PROTOCOL["gpu_bytes"] / torch.cuda.get_device_properties(0).total_memory)
        clock = Clock(directory, protocol=PROTOCOL)
        start_path = directory / "execution-start.json"
        if not start_path.exists():
            atomic(start_path, dict(identity=manifest["identity"], at=time.time(),
                                   inherited_first=clock.first), exclusive=True)
        execution_start = read(start_path)
        if (execution_start.get("identity") != manifest["identity"]
                or execution_start.get("inherited_first") != clock.first
                or not isinstance(execution_start.get("at"), (int, float))
                or not math.isfinite(execution_start["at"])
                or execution_start["at"] < clock.first):
            raise ValueError("execution start identity/original clock changed")
        with clock.signals():
            try:
                if not (directory / "verification.json").exists():
                    clock.enter("verify")
                    verification = verify(device="cuda:0")
                    clock.check()
                    atomic(directory / "verification.json", dict(verification, identity=manifest["identity"]), exclusive=True)
                verification = read(directory / "verification.json")
                if not verification.get("passed") or verification.get("identity") != manifest["identity"]:
                    raise ValueError("invalid GPU verification receipt")
                p0 = artifacts.initial_model(directory, read(directory / "catalog.json")["vocabulary"],
                                             manifest["identity"], "cuda:0")
                selection = policy_phase(directory, manifest, teams, schedules, p0, clock, SETTING)
                lock = dict(identity=manifest["identity"], P0=sha(directory / "models/P0.pt"),
                            P1=selection["sha256"], selected_file=selection["file"], settings=SETTING,
                            schedule_sha256=sha(directory / "schedule.json"), simulations=64, temperature=1.0,
                            training_stop_sha256=sha(directory / "training-stop.json"),
                            selection_sha256=sha(directory / "selection.json"))
                path = directory / "evaluation-lock.json"
                if path.exists():
                    if read(path) != lock:
                        raise ValueError("independent test lock changed")
                else:
                    atomic(path, lock, exclusive=True)
                p1 = Policy.load(directory / selection["file"], "cuda:0")
                clock.enter("test")
                files = {"P0": "models/P0.pt", "P1": selection["file"]}
                _normal_rows(directory, schedules["test"], files, clock,
                             collect=lambda: run_group(directory, schedules["test"], teams,
                                 {"P0": p0, "P1": p1}, clock, SETTING, files))
                clock.enter("finalize")
                result = finalize(directory, check=clock.check, protocol=PROTOCOL)
                clock.check()
                name = "completed.json" if result["procedure_complete"] else "incomplete.json"
                atomic(directory / name, dict(result, identity=manifest["identity"], at=time.time(),
                       elapsed=time.time() - clock.first,
                       additional_elapsed=time.time() - execution_start["at"],
                       peak_rss=clock.peak_rss), exclusive=True)
                return result
            except BaseException as error:
                failure = dict(stage=clock.stage, reason=f"{type(error).__name__}: {error}",
                               at=time.time(), first=clock.first, elapsed=time.time() - clock.first,
                               additional_elapsed=time.time() - execution_start["at"])
                atomic(directory / "stops" / f"{time.time_ns()}.json", failure, exclusive=True)
                try:
                    for group in [*schedules["train"], *schedules["dev"].values(), schedules["test"]]:
                        artifacts.existing(directory, group)
                    if (directory / "games").exists() and not clock.cancelled:
                        clock.enter("finalize")
                        finalize(directory, check=clock.check, protocol=PROTOCOL)
                except Exception as cleanup_error:
                    atomic(directory / "stops" / f"{time.time_ns()}-finalization.json",
                           dict(reason=f"{type(cleanup_error).__name__}: {cleanup_error}"), exclusive=True)
                # No automatic re-entry from a technical stop. Complete-unit recovery
                # requires deliberate inspection, retaining the failure and original clock.
                atomic(directory / "incomplete.json", dict(failure, identity=manifest["identity"],
                       status="incomplete", technical_stop=True, procedure_complete=False,
                       elapsed=time.time() - clock.first,
                       additional_elapsed=time.time() - execution_start["at"],
                       efficacy_success=False), exclusive=True)
                raise
