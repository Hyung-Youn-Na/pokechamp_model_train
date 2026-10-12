"""Order-preserving durable artifacts and immutable original budget."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ..imitation.storage import atomic as _atomic
from ..imitation.storage import jsonl, read, sha, write_jsonl
from .config import PROTOCOL

__all__ = ["Clock", "append", "atomic", "jsonl", "read", "sha", "write_jsonl"]


def atomic(path, value, *, immutable=False):
    # Candidate insertion order is part of the policy. Never sort nested inputs.
    data = (
        value
        if isinstance(value, bytes)
        else (
            json.dumps(
                value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            )
            + "\n"
        ).encode()
    )
    _atomic(path, data, immutable=immutable)


def append(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(
            json.dumps(
                value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            )
            + "\n"
        )
        stream.flush()
        os.fsync(stream.fileno())


class Clock:
    def __init__(self, directory, *, start=False, now=None):
        self.path = Path(directory) / "clock.json"
        if not self.path.exists():
            if not start:
                raise FileNotFoundError("first GPU preflight clock has not started")
            wall = time.time() if now is None else now
            atomic(
                self.path,
                {
                    "started_at": wall,
                    "deadline_at": wall + PROTOCOL["seconds"]["total"],
                    "limits": PROTOCOL["seconds"],
                },
                immutable=True,
            )
        self.record = read(self.path)
        if (
            self.record["limits"] != PROTOCOL["seconds"]
            or self.record["deadline_at"] != self.record["started_at"] + PROTOCOL["seconds"]["total"]
        ):
            raise ValueError("original experiment deadline or limits changed")

    def deadline(self, stage):
        return self.record["started_at"] + self.record["limits"][stage]

    def remaining(self, stage="total"):
        return self.deadline(stage) - time.time()

    def may_start(self, stage):
        return self.remaining(stage) > 0
