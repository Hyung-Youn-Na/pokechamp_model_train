"""Persistent slot admission, compressed observations and atomic completed-round checkpoints."""
from __future__ import annotations

import gzip
import io
import json
import os
from pathlib import Path
import random
import time
from collections import deque

from .config import PROTOCOL
from .storage import atomic, atomic_bytes, digest, encoded, read, sha


def initial_model(directory, vocabulary, identity, device):
    """Initial policy creation is recoverable without accepting an unverified P0."""
    import torch
    from .config import SEED
    from .model import Policy
    directory = Path(directory)
    path, receipt = directory / "models/P0.pt", directory / "models/P0.identity.json"
    if receipt.exists():
        record = read(receipt)
        if record != dict(identity=identity, sha256=sha(path)):
            raise ValueError("initial model identity changed")
    else:
        torch.manual_seed(SEED)
        random.seed(SEED)
        policy = Policy(vocabulary)
        if path.exists():
            loaded = Policy.load(path)
            if any(not torch.equal(tensor, loaded.state_dict()[key]) for key, tensor in policy.state_dict().items()):
                raise ValueError("uncommitted P0 differs from deterministic initialization")
        else:
            policy.save(path)
        atomic(receipt, dict(identity=identity, sha256=sha(path)), exclusive=True)
    return Policy.load(path, device)


def save_result(directory, result):
    base = Path(directory) / "games" / result["job"]["slot_id"]
    records = result["records"]
    raw = b"".join(encoded(row) + b"\n" for row in records)
    atomic_bytes(base / "decisions.jsonl.gz", gzip.compress(raw, mtime=0), exclusive=True)
    atomic_bytes(base / "private-evidence.json.gz", gzip.compress(encoded(result["evidence"]), mtime=0), exclusive=True)
    atomic_bytes(base / "public-roots.json.gz", gzip.compress(encoded(result.get("roots", [])), mtime=0), exclusive=True)
    row = {k: v for k, v in result.items() if k not in ("records", "evidence", "roots")}
    row["files"] = {name: sha(base / name) for name in ("decisions.jsonl.gz", "private-evidence.json.gz", "public-roots.json.gz")}
    row["decisions"] = len(records)
    atomic(base / "result.json", row, exclusive=True)
    return row


def load_result(path, *, records=False):
    path = Path(path)
    row = read(path / "result.json")
    for name, checksum in row["files"].items():
        if sha(path / name) != checksum:
            raise ValueError("game artifact checksum mismatch")
    if records:
        with gzip.open(path / "decisions.jsonl.gz", "rt") as stream:
            row["records"] = [json.loads(line) for line in stream]
    return row


def claim(directory, job):
    identity = {k: v for k, v in job.items() if k != "deadline"}
    atomic(Path(directory) / "claims" / f"{job['slot_id']}.json",
           dict(job=identity, claimed_at=time.time()), exclusive=True)


def existing(directory, schedule):
    """Unfinished reservations are never replayed or quietly replaced."""
    found, remaining = [], []
    for job in schedule:
        base = Path(directory) / "games" / job["slot_id"]
        if (base / "result.json").exists():
            row = load_result(base)
            if row["job"] != job:
                raise ValueError("scheduled identity changed")
            found.append(row)
        elif (Path(directory) / "claims" / f"{job['slot_id']}.json").exists():
            row = dict(job=job, status="incomplete", winner=None, reason="interrupted_reserved_slot",
                       turns=None, records=[], evidence=None, metrics={})
            # Partial files are immutable evidence. Preserve them before writing a derived result.
            if base.exists():
                raise RuntimeError("partial artifact requires recovery audit; no overwrite")
            found.append(save_result(directory, row))
        else:
            remaining.append(job)
    return found, remaining


def replay_rows(directory, through_round):
    low = max(1, through_round - PROTOCOL["replay_rounds"] + 1)
    results = []
    for path in (Path(directory) / "games").glob("*/result.json"):
        row = read(path)
        if row["job"]["stage"] != "train" or not low <= row["job"]["round_id"] <= through_round:
            continue
        if row["status"] == "completed":
            results.append((row["job"]["round_id"], row["job"]["slot_id"], path.parent))
    rows = deque(maxlen=PROTOCOL["replay_capacity"])
    for _, _, path in sorted(results):
        game = load_result(path, records=True)
        for record in game["records"]:
            if (record.get("submitted") and record["mode"] == "search"
                    and record["terminal_status"] == "completed"):
                rows.append(record)
    return list(rows)


def save_checkpoint(directory, round_id, policy, optimizer, generator, *, identity, replay_ids, updates,
                    learning=None):
    import torch
    directory = Path(directory)
    payload = dict(round=round_id, identity=identity, model=policy.payload(), optimizer=optimizer.state_dict(),
        generator=generator.get_state(), torch_rng=torch.get_rng_state(), python_rng=random.getstate(),
        cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else [],
        replay_ids=replay_ids, updates=updates, clock=read(directory / "clock.json"), learning=learning)
    stream = io.BytesIO()
    torch.save(payload, stream)
    name = f"checkpoints/round-{round_id:03d}.pt"
    commit = directory / f"checkpoints/round-{round_id:03d}.json"
    if commit.exists():
        raise FileExistsError("training round already committed")
    if (directory / name).exists():
        # The process died before committing this file. Preserve, never overwrite it.
        orphan = directory / "uncommitted" / str(time.time_ns()) / Path(name).name
        orphan.parent.mkdir(parents=True, exist_ok=False)
        os.rename(directory / name, orphan)
    atomic_bytes(directory / name, stream.getvalue(), exclusive=True)
    pointer = dict(file=name, sha256=sha(directory / name), round=round_id)
    atomic(commit, pointer, exclusive=True)
    atomic(directory / "latest.json", pointer)


def committed_pointer(directory):
    directory = Path(directory)
    commits = [read(p) for p in sorted((directory / "checkpoints").glob("round-*.json"))]
    if not commits:
        return None
    if [c["round"] for c in commits] != list(range(len(commits))):
        raise ValueError("noncontiguous completed-round checkpoints")
    pointer = commits[-1]
    if sha(directory / pointer["file"]) != pointer["sha256"]:
        raise ValueError("committed checkpoint corrupted")
    latest = directory / "latest.json"
    if latest.exists():
        prior = read(latest)
        if prior not in commits:
            raise ValueError("latest pointer is not a committed checkpoint")
    if not latest.exists() or read(latest) != pointer:
        atomic(latest, pointer)
    return pointer


def restore_checkpoint(directory, policy, optimizer, generator, *, identity):
    import torch
    directory = Path(directory)
    pointer = committed_pointer(directory)
    if pointer is None:
        raise ValueError("no committed checkpoint")
    path = directory / pointer["file"]
    if sha(path) != pointer["sha256"]:
        raise ValueError("checkpoint checksum mismatch")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if payload["identity"] != identity or payload["clock"] != read(directory / "clock.json"):
        raise ValueError("checkpoint source/first clock changed")
    from .config import MODEL, SCHEMA
    if (payload["model"]["vocabulary"] != policy.encoder.vocabulary
            or payload["model"]["config"] != MODEL or payload["model"]["schema"] != SCHEMA):
        raise ValueError("checkpoint vocabulary changed")
    policy.load_state_dict(payload["model"]["weights"], strict=True)
    optimizer.load_state_dict(payload["optimizer"])
    generator.set_state(payload["generator"])
    torch.set_rng_state(payload["torch_rng"])
    random.setstate(payload["python_rng"])
    if payload["cuda_rng"]:
        torch.cuda.set_rng_state_all(payload["cuda_rng"])
    return payload


def publish_round(directory, payload):
    """Finish exports after a committed update, including a crash before latest.json."""
    import torch
    directory = Path(directory)
    round_id = payload["round"]
    if not round_id:
        return "models/P0.pt"
    name = f"models/round-{round_id:03d}.pt"
    path = directory / name
    if path.exists():
        actual = torch.load(path, map_location="cpu", weights_only=True)
        expected = payload["model"]
        if (actual.keys() != expected.keys() or actual["config"] != expected["config"]
                or actual["schema"] != expected["schema"] or actual["vocabulary"] != expected["vocabulary"]
                or actual["weights"].keys() != expected["weights"].keys()
                or any(not torch.equal(actual["weights"][key], value) for key, value in expected["weights"].items())):
            raise ValueError("published policy disagrees with committed training state")
    else:
        stream = io.BytesIO()
        torch.save(payload["model"], stream)
        atomic_bytes(path, stream.getvalue(), exclusive=True)
    metrics = directory / "training" / f"round-{round_id:03d}.json"
    if metrics.exists():
        if read(metrics) != payload["learning"]:
            raise ValueError("training metrics disagree with checkpoint")
    else:
        atomic(metrics, payload["learning"], exclusive=True)
    return name
