"""Scores, the slowdown stopping rule, Bradley-Terry selection and the locked test statistics."""
from __future__ import annotations

import random

from .config import PROTOCOL


def score(result, side):
    """Score of `side`: win 1, draw 0.5, loss 0; a 300-turn censored game counts 0.5. None = technical failure."""
    if result["status"] == "censored":
        return PROTOCOL["evaluation"]["censored_score"]
    if result["status"] != "completed":
        return None
    if not result["winner"]:
        return 0.5
    return 1.0 if result["winner"] == side else 0.0


def evaluation_score(results):
    """Mean score of the job's first player; any technical failure makes the evaluation unjudgeable."""
    scores = [score(r, r["job"]["first_side"]) for r in results]
    if any(s is None for s in scores):
        return None, scores
    return sum(scores) / len(scores), scores


def stop_reasons(history):
    """history: [(round, score)] of completed dev evaluations in order. Reasons the run must stop now."""
    e = PROTOCOL["evaluation"]
    if not history:
        return []
    last_round = history[-1][0]
    streak = 0
    for _, value in reversed(history):
        if value < e["threshold"]:
            streak += 1
        else:
            break
    reasons = []
    if last_round >= e["min_round"] and streak >= e["patience"]:
        reasons.append("slowdown")
    if last_round >= e["max_rounds"]:
        reasons.append("round_cap")
    return reasons


def bradley_terry(players, games, iterations=10000, tolerance=1e-12):
    """players in tie-break order (earlier first); games: (x, y, score_of_x) with draws as half wins.
    -> {player: strength}; a player who scored everything against all opponents gets +inf."""
    wins = {p: 0.0 for p in players}
    played = {(a, b): 0 for a in players for b in players if a != b}
    for x, y, s in games:
        wins[x] += s
        wins[y] += 1 - s
        played[x, y] += 1
        played[y, x] += 1
    total = {p: sum(n for (a, _), n in played.items() if a == p) for p in players}
    perfect = [p for p in players if total[p] and wins[p] == total[p]]
    if perfect:
        return {p: (float("inf") if p in perfect else 0.0) for p in players}
    strength = {p: 1.0 for p in players}
    for _ in range(iterations):
        new = {}
        for p in players:
            denominator = sum(played[p, q] / (strength[p] + strength[q]) for q in players if q != p and played[p, q])
            new[p] = wins[p] / denominator if denominator else 0.0
        norm = sum(new.values()) or 1.0
        new = {p: v * len(players) / norm for p, v in new.items()}
        delta = max(abs(new[p] - strength[p]) for p in players)
        strength = new
        if delta < tolerance:
            break
    return strength


def select(players, games):
    strength = bradley_terry(players, games)
    best = max(strength.values())
    return next(p for p in players if strength[p] == best), strength


def bootstrap(differences, iterations, seed_value):
    """Percentile 95% interval of the mean paired block difference."""
    rng = random.Random(seed_value)
    n = len(differences)
    means = sorted(sum(differences[rng.randrange(n)] for _ in range(n)) / n for _ in range(iterations))
    return means[int(0.025 * iterations)], means[int(0.975 * iterations) - 1]
