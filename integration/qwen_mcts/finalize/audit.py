"""All-game audit of an EX-080 run (read-only on the raw artifacts).

For every game: artifact hashes, root digests, candidate/choice alignment, the action RNG redrawn from the recorded
probabilities, and every matrix-search policy re-solved from its recorded payoff matrix and priors (bitwise).
Sampled decisions are re-rendered from their stored public roots and compared with the recorded rendering digest.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import random

from ..config import PROTOCOL
from ..solver import solve
from ..storage import digest, read, seed, sha

SIDES = ("p1", "p2")
NORMAL = ("completed", "censored")


def games(run):
    root = Path(run) / "games"
    for group in sorted(p.name for p in root.iterdir() if p.is_dir()):
        for slot in sorted(p.name for p in (root / group).iterdir() if p.is_dir()):
            yield group, slot


def load(run, group, slot):
    directory = Path(run) / "games" / group / slot
    summary = read(directory / "result.json")
    for name, checksum in summary["files"].items():
        if sha(directory / name) != checksum:
            raise ValueError(f"artifact changed: {group}/{slot}/{name}")
    with gzip.open(directory / "decisions.jsonl.gz", "rt") as stream:
        records = [json.loads(line) for line in stream if line.strip()]
    with gzip.open(directory / "roots.jsonl.gz", "rt") as stream:
        roots = [json.loads(line) for line in stream if line.strip()]
    with gzip.open(directory / "evidence.json.gz", "rt") as stream:
        evidence = json.load(stream)
    return summary, records, roots, evidence


def probabilities(record, job, side):
    count = len(record["candidates"][side])
    player = job["players"][side]
    if count == 1:
        return [1.0]
    if player["mode"] == "search":
        return record["search"][player["tag"]]["pi"][SIDES.index(side)]
    if player["mode"] == "policy":
        return record["policy"][player["tag"]]["rho"][SIDES.index(side)]
    if player["mode"] == "uniform":
        return [1.0 / count] * count
    raise ValueError("no recorded probabilities for " + player["mode"])


def draw(values, rng):
    total, u, cumulative = sum(values), rng.random(), 0.0
    for index, p in enumerate(values):
        cumulative += p / total
        if u < cumulative:
            return index
    return len(values) - 1


def audit_game(run, group, slot, *, describe=None):
    summary, records, roots, evidence = load(run, group, slot)
    job, status = summary["job"], summary["status"]
    out = dict(group=group, slot=slot, status=status, decisions=len(records), searches=0, rerendered=0)
    if status not in NORMAL:
        return out
    if len(roots) != len(records) or any(digest(root) != r["root"] for root, r in zip(roots, records)):
        raise ValueError(f"{slot}: stored roots do not match decision digests")
    if status == "completed" and (not evidence or not evidence["ended"] or (evidence["winner"] or None) != (summary["winner"] or None)):
        raise ValueError(f"{slot}: evidence disagrees with the recorded result")
    rngs = {side: random.Random(seed("action", *job["seed_key"], side)) for side in SIDES}
    config = PROTOCOL["search"]
    for index, record in enumerate(records):
        for side in SIDES:
            candidates = record["candidates"][side]
            if not candidates:
                continue
            choice = record["choices"].get(side)
            if choice not in candidates:
                raise ValueError(f"{slot}:{index}: choice outside candidates")
            if job["players"][side]["mode"] == "opponent":
                continue
            values = probabilities(record, job, side)
            if len(values) != len(candidates) or candidates[draw(values, rngs[side])] != choice:
                raise ValueError(f"{slot}:{index}: action RNG redraw disagrees with the recorded choice")
        for tag, s in record["search"].items():
            pi1, pi2, q, info = solve(s["matrix"], s["rho"][0], s["rho"][1], tau=config["tau"],
                                      iterations=config["iterations"], tolerance=config["gap_tolerance"])
            if pi1.tolist() != s["pi"][0] or pi2.tolist() != s["pi"][1] or q != s["q"]:
                raise ValueError(f"{slot}:{index}: re-solved policy differs from the recorded one")
            out["searches"] += 1
        if describe is not None and index in (0, len(records) - 1):
            frame = describe(roots[index])
            if digest(frame["dynamic"]) != record["dynamic"] or \
                    {s: [c["id"] for c in frame["candidates"][s]] for s in SIDES} != record["candidates"]:
                raise ValueError(f"{slot}:{index}: re-rendered public state differs")
            out["rerendered"] += 1
    return out


def audit_replay(run):
    """Every replay row refers to a searched decision of a trainable self-play game with matching targets."""
    from ..replay import rows as replay_rows
    checked = 0
    for shard in sorted((Path(run) / "replay").glob("round-*.jsonl.gz")):
        round_id = int(shard.name[6:9])
        group = f"train-{round_id:03d}"
        expected = {}
        for _, slot in [(g, s) for g, s in games(run) if g == group]:
            summary, records, _, _ = load(run, group, slot)
            for row in replay_rows(dict(summary, records=records)):
                expected[row["id"]] = row
        with gzip.open(shard, "rt") as stream:
            actual = [json.loads(line) for line in stream if line.strip()]
        if {r["id"]: r for r in actual} != expected:
            raise ValueError(f"replay shard {shard.name} differs from its games")
        checked += len(actual)
    return checked


def audit_run(run):
    from ..sim import Simulator
    totals = dict(games=0, normal=0, decisions=0, searches=0, rerendered=0, by_group={})
    with Simulator("search") as sim:
        for group, slot in games(run):
            row = audit_game(run, group, slot, describe=sim.describe)
            totals["games"] += 1
            totals["normal"] += row["status"] in NORMAL
            for key in ("decisions", "searches", "rerendered"):
                totals[key] += row[key]
            stats = totals["by_group"].setdefault(group, {})
            stats[row["status"]] = stats.get(row["status"], 0) + 1
    totals["replay_rows"] = audit_replay(run)
    totals["passed"] = True
    return totals
