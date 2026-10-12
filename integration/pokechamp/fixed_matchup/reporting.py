"""Independent paired-block estimates; incomplete schedules cannot pass efficacy gates."""
from __future__ import annotations

from collections import Counter
import random
import statistics

from .config import PROTOCOL
from .storage import seed


def score(result):
    if result["status"] != "completed":
        return None
    winner = result["winner"]
    if winner not in ("", "p1", "p2"):
        raise ValueError("invalid winner")
    return 0.5 if not winner else float(winner == result["job"]["model_side"])


def validate_results(schedule, results):
    planned = {row["slot_id"]: row for row in schedule}
    if len(planned) != len(schedule):
        raise ValueError("duplicate scheduled slot")
    found = {}
    for row in results:
        identity = row["job"]["slot_id"]
        if identity in found or identity not in planned or row["job"] != planned[identity]:
            raise ValueError("changed/duplicate/unplanned slot")
        if row["status"] not in ("completed", "incomplete", "failed", "invalid", "unattempted"):
            raise ValueError("unknown result status")
        if row["status"] != "completed" and row.get("winner") is not None:
            raise ValueError("failure cannot acquire a winner")
        score(row)
        found[identity] = row
    return [found.get(row["slot_id"], dict(job=row, status="unattempted", winner=None, metrics={}))
            for row in schedule]


def counts(rows):
    statuses = Counter(row["status"] for row in rows)
    values = [score(row) for row in rows if row["status"] == "completed"]
    return dict(planned=len(rows), statuses=dict(statuses), wins=values.count(1),
                draws=values.count(0.5), losses=values.count(0),
                mean=statistics.mean(values) if values else None,
                seconds=sum(row.get("metrics", {}).get("seconds", 0) for row in rows))


def bootstrap(values, *, draws=10000, namespace="primary"):
    if not values:
        raise ValueError("no independent blocks")
    rng = random.Random(seed("bootstrap", namespace))
    sampled = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(draws))
    def quantile(q):
        pos = q * (len(sampled) - 1)
        lower = int(pos)
        upper = min(lower + 1, len(sampled) - 1)
        return sampled[lower] + (sampled[upper] - sampled[lower]) * (pos - lower)
    return dict(mean=statistics.mean(values), ci95=[quantile(0.025), quantile(0.975)],
                blocks=len(values), draws=draws)


def contrast(rows, treatment, baseline, *, draws=10000):
    groups = {}
    for label in (treatment, baseline):
        groups[label] = {(r["job"]["block"], r["job"]["model_team"], r["job"]["model_side"]): score(r)
                         for r in rows if r["job"]["condition"] == label}
    if groups[treatment].keys() != groups[baseline].keys() or not groups[treatment]:
        return dict(estimable=False, reason="unmatched cells")
    if any(v is None for group in groups.values() for v in group.values()):
        return dict(estimable=False, reason="incomplete fixed denominator")
    blocks = sorted({key[0] for key in groups[treatment]})
    differences = []
    for block in blocks:
        keys = [(block, team, side) for team in ("A", "B") for side in ("p1", "p2")]
        if any(k not in groups[treatment] for k in keys):
            return dict(estimable=False, reason="missing orientation")
        differences.append(statistics.mean(groups[treatment][k] - groups[baseline][k] for k in keys))
    return dict(estimable=True, **bootstrap(differences, draws=draws, namespace=treatment + "-" + baseline))


def report(schedule, results, *, draws=None):
    rows = validate_results(schedule, results)
    draws = PROTOCOL["bootstrap"] if draws is None else draws
    labels = sorted({row["condition"] for row in schedule})
    summaries = {}
    for label in labels:
        selected = [row for row in rows if row["job"]["condition"] == label]
        summaries[label] = dict(overall=counts(selected), cells={
            f"{team}-{side}": counts([r for r in selected if r["job"]["model_team"] == team
                                     and r["job"]["model_side"] == side])
            for team in ("A", "B") for side in ("p1", "p2")})
    contrasts = {a + "-" + b: contrast(rows, a, b, draws=draws) for a, b in
                 [("P1", "P0"), ("P1+S", "P1"), ("P0+S", "P0"), ("P1+S", "P0+S")]}
    primary = contrasts["P1-P0"]
    complete = len(rows) == 640 and all(row["status"] == "completed" for row in rows)
    success = complete and primary["estimable"] and primary["mean"] > 0 and primary["ci95"][0] > 0
    return dict(complete=complete, policy_improved=bool(success), summaries=summaries, contrasts=contrasts,
                total=counts(rows), interpretation="고정 공개 상태·한 학습 seed; 일반 비공개 Gen9 OU 효능 아님")


def pilot_gate(rows, *, projected_test_seconds):
    reasons = []
    for label in ("uniform", "P0"):
        group = [r for r in rows if r["job"]["condition"] == label]
        completed = [r for r in group if r["status"] == "completed"]
        if len(group) != 32 or any(r["status"] not in ("completed", "incomplete") for r in group):
            reasons.append(label + ":missing_or_failed")
        if any(r["status"] == "incomplete" and r.get("reason") != "turn_limit" for r in group):
            reasons.append(label + ":interrupted")
        censored = sum(r["status"] == "incomplete" for r in group)
        if not group or censored / len(group) > 0.05:
            reasons.append(label + ":censoring")
        points = []
        for row in completed:
            side_a = next(side for side, team in row["job"]["teams"].items() if team == "A")
            points.append(0.5 if not row["winner"] else float(row["winner"] == side_a))
        if not points or not 0.1 <= statistics.mean(points) <= 0.9:
            reasons.append(label + ":extreme_team_score")
    if not 0 < projected_test_seconds <= PROTOCOL["stage_seconds"]["test"]:
        reasons.append("evaluation_budget")
    return dict(passed=not reasons, reasons=reasons, projected_test_seconds=projected_test_seconds)
