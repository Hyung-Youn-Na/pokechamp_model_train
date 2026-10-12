"""Frozen game schedules. Every seed is namespaced (qmcts-v1) and stage-keyed; dev/rr seeds are common across
evaluations and the five test conditions share seeds block by block (common random numbers)."""
from __future__ import annotations

from .config import ASSIGNMENTS, PROTOCOL
from .storage import showdown_seed

ORDER = ("A-p1", "B-p1")
TEAMS = ("A", "B")


def job(stage, slot_id, assignment, seed_key, players, **extra):
    return dict(stage=stage, slot_id=slot_id, assignment=assignment, seed_key=list(seed_key),
                game_seed=showdown_seed("game", *seed_key), players=players, **extra)


def side_of(assignment, team):
    return next(side for side, label in ASSIGNMENTS[assignment].items() if label == team)


def other(side):
    return "p2" if side == "p1" else "p1"


def search(tag):
    return dict(mode="search", tag=tag)


def policy(tag):
    return dict(mode="policy", tag=tag)


def self_play(round_id, tag="current"):
    return [job("train", f"train-{round_id:03d}-{block:02d}-{assignment}", assignment, ["train", round_id, block, assignment],
                {"p1": search(tag), "p2": search(tag)}, round=round_id)
            for block in range(PROTOCOL["train"]["blocks"]) for assignment in ORDER]


def match(stage, label, key, blocks, first, second, **extra):
    """`first` plays team A and team B, from p1 and from p2, in every seed block."""
    jobs = []
    for block in range(blocks):
        for assignment in ORDER:
            for team in TEAMS:
                side = side_of(assignment, team)
                jobs.append(job(stage, f"{label}-{block:02d}-{assignment}-{team}", assignment, [*key, block, assignment, team],
                                {side: first, other(side): second}, first_side=side, first_team=team, **extra))
    return jobs


def dev(eval_round, previous_tag):
    e = PROTOCOL["evaluation"]
    return match("dev", f"dev-{eval_round:03d}", ["dev"], e["previous_blocks"], policy("current"), policy(previous_tag),
                 round=eval_round, opponent_tag=previous_tag)


def p0_reference(eval_round):
    e = PROTOCOL["evaluation"]
    return match("p0ref", f"p0ref-{eval_round:03d}", ["p0ref"], e["p0_blocks"], policy("current"), policy("P0"),
                 round=eval_round, opponent_tag="P0")


def round_robin(pairs):
    e = PROTOCOL["evaluation"]
    return [j for x, y in pairs for j in match("rr", f"rr-{x}-{y}", ["rr"], e["round_robin_blocks"], policy(x), policy(y),
                                               pair=[x, y])]


TEST_PLAYERS = {"P0": policy("P0"), "P0+S": search("P0"), "P1": policy("P1"), "P1+S": search("P1")}


def test():
    jobs = []
    for block in range(PROTOCOL["test"]["blocks"]):
        for team in TEAMS:
            for side in ("p1", "p2"):
                assignment = f"{team}-p1" if side == "p1" else f"{'B' if team == 'A' else 'A'}-p1"
                key = ["test", block, team, side]
                for condition in PROTOCOL["test"]["conditions"]:
                    if condition == "P1-vs-P0":
                        players = {side: policy("P1"), other(side): policy("P0")}
                    else:
                        players = {side: TEST_PLAYERS[condition], other(side): dict(mode="opponent")}
                    jobs.append(job("test", f"test-{condition}-{block:02d}-{team}-{side}", assignment, key, players,
                                    condition=condition, block=block, model_team=team, model_side=side))
    return jobs


def smoke():
    return [job("smoke", f"smoke-{block:02d}-{assignment}", assignment, ["smoke", block, assignment],
                {"p1": search("current"), "p2": search("current")})
            for block in range(PROTOCOL["smoke_games"] // 2) for assignment in ORDER]


def bench(label, count):
    return [job("bench", f"bench-{label}-{i:03d}-{assignment}", assignment, ["bench", label, i, assignment],
                {"p1": search("current"), "p2": search("current")})
            for i in range(count) for assignment in ORDER]


def frozen():
    """Everything whose seeds are frozen at prepare (training rounds up to the cap, dev, p0ref, test)."""
    e = PROTOCOL["evaluation"]
    return dict(train={str(r): self_play(r) for r in range(1, e["max_rounds"] + 1)},
                dev=dev(0, "previous"), p0ref=p0_reference(0), rr=round_robin([("x", "y")]), test=test(), smoke=smoke())
