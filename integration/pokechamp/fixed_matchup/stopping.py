"""Frozen EX-079 schedule and deterministic, evidence-independent stopping rule."""
from copy import deepcopy
import math

from .config import PROTOCOL as BASE_PROTOCOL, ROOT
from .schedule import development, test_schedule, training
from .storage import showdown_seed

PROTOCOL = deepcopy(BASE_PROTOCOL)
PROTOCOL.update(experiment="EX-079", pilot_games=0, max_rounds=32,
                total_seconds=None, game_seconds=None,
                stage_seconds=dict(verify=None, pilot=None, train=None, test=None, finalize=None),
                stopping=dict(min_rounds=12, max_rounds=32, target_score=0.65,
                              target_evaluations=3, min_improvement=0.02, patience=3,
                              baseline_round=1, evaluation_rounds=[1, *range(4, 33, 4)]))
SETTING = dict(workers=16, batch_size=32)
DEFAULT_OUTPUT = ROOT / ".pokechamp-data/experiments/ex079-fixed-matchup-stopping"


def schedule():
    dev = {str(round_id): development(round_id) for round_id in PROTOCOL["stopping"]["evaluation_rounds"]}
    test = test_schedule()
    for jobs in [*dev.values(), test]:
        for job in jobs:
            # Round/condition remain in slot identity, but not in common random numbers.
            split = "dev" if job["stage"] == "dev" else "test"
            job["seed_key"] = ["EX-079", split, job["block"], job["model_team"], job["model_side"]]
            job["simulator_seed"] = showdown_seed("game", job["seed_key"])
    return dict(pilot=[], train=[training(r) for r in range(1, 33)], dev=dev, test=test)


def stopping_decision(history):
    """Reconstruct state from a contiguous prefix of completed development evaluations.

    Round 1 initializes the improvement anchor, but never contributes to target streak.
    No observation after a latched stopping decision is permitted.
    """
    config = PROTOCOL["stopping"]
    rounds = config["evaluation_rounds"]
    if not isinstance(history, list) or len(history) > len(rounds):
        raise ValueError("development history must be an ordered prefix")
    state = dict(stop=False, reason=None, reasons=[], round=None, best_round=None,
                 best_score=None, anchor=None, stale=0, target_streak=0)
    for index, row in enumerate(history):
        if state["stop"]:
            raise ValueError("development history continued after latched stopping condition")
        if not isinstance(row, dict) or any(key not in row for key in ("round", "score", "file", "sha256")):
            raise ValueError("incomplete development record")
        value = row["score"]
        if (type(row["round"]) is not int or row["round"] != rounds[index]
                or isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0 <= value <= 1
                or not isinstance(row["file"], str) or not row["file"]
                or not isinstance(row["sha256"], str) or not row["sha256"]):
            raise ValueError("invalid, missing or out-of-order development evaluation")
        state["round"] = row["round"]
        if state["best_score"] is None or value > state["best_score"]:
            state.update(best_score=value, best_round=row["round"])
        if index == 0:
            state["anchor"] = value
            continue
        if value >= state["anchor"] + config["min_improvement"] - 1e-12:
            state.update(anchor=value, stale=0)
        else:
            state["stale"] += 1
        state["target_streak"] = state["target_streak"] + 1 if value >= config["target_score"] else 0
        if row["round"] >= config["min_rounds"]:
            reasons = []
            if state["target_streak"] >= config["target_evaluations"]:
                reasons.append("target")
            if state["stale"] >= config["patience"]:
                reasons.append("plateau")
            if row["round"] >= config["max_rounds"]:
                reasons.append("max_rounds")
            state.update(stop=bool(reasons), reasons=reasons, reason=reasons[0] if reasons else None)
    return state
