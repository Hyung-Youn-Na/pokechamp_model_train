"""Training rows from self-play results: both sides' search targets per searched decision."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from .storage import atomic_bytes, encoded

TRAINABLE = ("completed", "censored")


def outcome(result):
    """p1-perspective game value for normally terminated games; None for censored (value loss excluded)."""
    if result["status"] != "completed":
        return None
    return 1 if result["winner"] == "p1" else -1 if result["winner"] == "p2" else 0


def rows(result, tag="current"):
    if result["status"] not in TRAINABLE:
        return []
    z = outcome(result)
    out = []
    for record in result["records"]:
        search = record["search"].get(tag)
        if search is None:
            continue
        counts = [len(record["candidates"]["p1"]), len(record["candidates"]["p2"])]
        pi = [search["pi"][k] if counts[k] >= 2 else None for k in range(2)]
        if pi == [None, None] and z is None:
            continue
        out.append(dict(id=f"{result['job']['slot_id']}:{record['decision']}", prefix=search["row"]["prefix"],
                        ids=search["row"]["ids"], readout=search["row"]["readout"], pi=pi, z=z))
    return out


def write_shard(path, results, tag="current"):
    lines = [encoded(row) for result in results for row in rows(result, tag)]
    atomic_bytes(Path(path), gzip.compress(b"\n".join(lines) + (b"\n" if lines else b""), mtime=0), exclusive=True)
    return len(lines)


def shard_ids(path):
    with gzip.open(path, "rt") as stream:
        return [json.loads(line)["id"] for line in stream if line.strip()]
