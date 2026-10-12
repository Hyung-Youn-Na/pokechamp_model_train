"""Durable complete-step checkpoints and a bounded local process supervisor."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from . import config
from .storage import Clock, append, atomic, read, sha


def source_files():
    suffixes = {".py", ".cjs", ".js", ".json", ".html", ".txt"}
    files = [
        p
        for p in (config.ROOT / "integration/pokechamp").rglob("*")
        if p.is_file()
        and p.suffix in suffixes
        and "__pycache__" not in p.parts
        and "tests" not in p.parts
    ]
    files.append(config.ROOT / "scripts/pokechamp-selfplay")
    return {str(p.relative_to(config.ROOT)): sha(p) for p in sorted(files)}


def freeze(directory):
    directory = Path(directory)
    from .prepare import verify

    verify(directory)
    from ..imitation.model import provenance, verify_checkpoint

    validation = read(directory / "verification/cpu.json")
    if not validation["passed"]:
        raise ValueError("CPU validation must pass before first GPU admission")
    verify_checkpoint(config.INITIAL)
    sources = source_files()
    path = directory / "manifest.json"
    if path.exists():
        manifest = read(path)
        if (
            manifest["source"] != sources
            or manifest["protocol"] != config.PROTOCOL
            or manifest["prepared_sha256"] != sha(directory / "prepared/manifest.json")
            or manifest["resource_sha256"] != sha(directory / "resource.json")
            or manifest["cpu_sha256"] != sha(directory / "verification/cpu.json")
        ):
            raise ValueError(
                "source/protocol/data/resource changed after execution freeze"
            )
        return manifest
    manifest = {
        "experiment_id": "EX-072",
        "protocol": config.PROTOCOL,
        "source": sources,
        "prepared_sha256": sha(directory / "prepared/manifest.json"),
        "cpu_sha256": sha(directory / "verification/cpu.json"),
        "initial_checkpoint_sha256": sha(config.INITIAL / "files.json"),
        "resource_sha256": sha(directory / "resource.json"),
        "environment": provenance(verify_weights=True),
        "frozen_at": time.time(),
    }
    for name, digest in sources.items():
        target = directory / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config.ROOT / name, target)
        if sha(target) != digest:
            raise ValueError("source changed while preserving it")
    for name in (
        "project_context/experiments/EX-072-selfplay-rlcd.md",
        "project_context/decisions/D-114-selfplay-rlcd.md",
    ):
        target = directory / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config.ROOT / name, target)
    atomic(path, manifest, immutable=True)
    return manifest


def assert_frozen(directory):
    manifest = read(Path(directory) / "manifest.json")
    if source_files() != manifest["source"]:
        raise ValueError("runtime source differs from the frozen execution")
    for name, key in [
        ("prepared/manifest.json", "prepared_sha256"),
        ("resource.json", "resource_sha256"),
        ("verification/cpu.json", "cpu_sha256"),
    ]:
        if sha(Path(directory) / name) != manifest[key]:
            raise ValueError("frozen artifact changed: " + name)
    prepared = read(Path(directory) / "prepared/manifest.json")
    for name, digest in prepared["files"].items():
        if sha(Path(directory) / "prepared" / name) != digest:
            raise ValueError("frozen prepared data changed: " + name)


def save_checkpoint(
    directory,
    policy,
    optimizer,
    state,
    clock,
    *,
    weights=None,
    calibration_optimizer=None,
):
    import torch

    from ..imitation.model import rng_state

    directory = Path(directory)
    checkpoints = directory / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    path = checkpoints / f"checkpoint-{time.time_ns()}.pt"
    payload = {
        "weights": policy.snapshot_weights() if weights is None else weights,
        "optimizer": optimizer.state_dict() if optimizer is not None else None,
        "calibration_optimizer": calibration_optimizer.state_dict()
        if calibration_optimizer is not None
        else None,
        "state": state,
        "rng": rng_state(),
        "sampling_rng": policy.sampling_generator.getstate(),
        "clock": clock.record,
        "manifest_sha256": sha(directory / "manifest.json"),
    }
    fd, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=checkpoints)
    try:
        with os.fdopen(fd, "wb") as stream:
            torch.save(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(checkpoints, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    record = {
        "path": str(path),
        "sha256": sha(path),
        "phase": state["phase"],
        "global_updates": (state.get("trainer") or {}).get("global_updates", 0),
        "saved_at": time.time(),
    }
    atomic(directory / "latest.json", record)
    atomic(directory / "state.json", state)
    append(directory / "checkpoint-events.jsonl", record)
    return record


def load_checkpoint(directory, policy, optimizer, clock):
    import torch

    from ..imitation.model import restore_rng

    directory = Path(directory)
    pointer = read(directory / "latest.json")
    path = Path(pointer["path"])
    if sha(path) != pointer["sha256"]:
        raise ValueError("complete-step checkpoint integrity failure")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if payload["clock"] != clock.record or payload["manifest_sha256"] != sha(
        directory / "manifest.json"
    ):
        raise ValueError("checkpoint belongs to a different clock or frozen execution")
    policy.load_weights(payload["weights"])
    if payload["optimizer"] is not None:
        optimizer.load_state_dict(payload["optimizer"])
    restore_rng(payload["rng"])
    policy.sampling_generator.setstate(payload["sampling_rng"])
    return payload


def cleanup_owned(directory):
    """Only kill still-matching processes whose identities this run recorded."""
    from .. import cli

    records = []
    for path in (Path(directory) / "games").glob("*/processes.json"):
        for role, item in read(path).items():
            proc = Path(f"/proc/{item['pid']}/stat")
            if proc.exists() and proc.read_text().split()[21] == item["start_ticks"]:
                try:
                    os.killpg(item["pid"], signal.SIGTERM)
                    records.append(
                        {"role": role, "pid": item["pid"], "action": "SIGTERM"}
                    )
                except ProcessLookupError:
                    pass
        worktree = path.parent / "showdown-worktree"
        if worktree.exists():
            # Normal match cleanup already removes its own worktree. This is
            # limited to interrupted attempts under the current experiment.
            time.sleep(0.5)
            for item in read(path).values():
                proc = Path(f"/proc/{item['pid']}/stat")
                if (
                    proc.exists()
                    and proc.read_text().split()[21] == item["start_ticks"]
                ):
                    try:
                        os.killpg(item["pid"], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            result = subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=cli.SHOWDOWN_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode:
                raise RuntimeError("owned worktree cleanup failed: " + result.stderr)
    return records


def supervisor(directory, resume=False):
    """5-minute durable heartbeat; one requested SIGTERM/restart; original deadline."""
    from ..imitation.resource import own_gpu, own_run

    directory = Path(directory).resolve()
    with own_run(directory):
        if (directory / "completed.json").exists():
            raise ValueError("EX-072 already closed; repeated execution is forbidden")
        if (directory / "manifest.json").exists() and not resume:
            raise ValueError(
                "existing execution requires explicit --resume with the original clock"
            )
        with own_gpu(directory, "selfplay-supervisor") as resource:
            os.environ["CUDA_VISIBLE_DEVICES"] = resource["uuid"]
            freeze(directory)
            attempt = 0
            while True:
                attempt += 1
                stream = (directory / f"worker-{time.time_ns()}.log").open("xb")
                command = [
                    str(config.PYTHON),
                    "-m",
                    "integration.pokechamp.selfplay",
                    "worker",
                    "--output",
                    str(directory),
                ]
                process = subprocess.Popen(
                    command,
                    cwd=config.ROOT,
                    env=os.environ.copy(),
                    stdin=subprocess.DEVNULL,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                append(
                    directory / "process-events.jsonl",
                    {"kind": "worker_start", "pid": process.pid, "at": time.time()},
                )
                last_heartbeat = 0
                sent_term = None
                try:
                    while process.poll() is None:
                        if time.time() - last_heartbeat >= 300:
                            state = (
                                read(directory / "state.json")
                                if (directory / "state.json").exists()
                                else {}
                            )
                            atomic(
                                directory / "supervisor.json",
                                {
                                    "pid": os.getpid(),
                                    "worker_pid": process.pid,
                                    "at": time.time(),
                                    "state": state,
                                    "attempt": attempt,
                                },
                            )
                            last_heartbeat = time.time()
                        if (directory / "clock.json").exists():
                            clock = Clock(directory)
                            if clock.remaining() <= 60 and sent_term is None:
                                os.kill(process.pid, signal.SIGTERM)
                                sent_term = time.time()
                            if clock.remaining() <= 0:
                                os.killpg(process.pid, signal.SIGKILL)
                        time.sleep(0.5)
                finally:
                    if process.poll() is None:
                        os.kill(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    stream.close()
                    cleanup_owned(directory)
                append(
                    directory / "process-events.jsonl",
                    {
                        "kind": "worker_exit",
                        "pid": process.pid,
                        "returncode": process.returncode,
                        "at": time.time(),
                    },
                )
                if process.returncode == 75 and attempt == 1 and sent_term is None:
                    proof = read(directory / "restart-request.json")
                    if proof["pid"] != process.pid or not proof["signal_received"]:
                        raise ValueError(
                            "planned SIGTERM restart lacks its signal receipt"
                        )
                    continue
                atomic(
                    directory / "supervisor-exit.json",
                    {
                        "returncode": process.returncode,
                        "at": time.time(),
                        "attempts": attempt,
                        "reason": "budget" if sent_term is not None else "worker_exit",
                    },
                )
                return process.returncode
