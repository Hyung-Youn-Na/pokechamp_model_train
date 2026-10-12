"""Frozen slots. Test labels never participate in training or model selection."""
from .config import PROTOCOL
from .storage import seed, showdown_seed


def players(model, mode):
    return dict(model=model, mode=mode)


def matchup(stage, condition, block, team, side, descriptors, *, round_id=0):
    other = "p2" if side == "p1" else "p1"
    assignment = {side: team, other: "B" if team == "A" else "A"}
    # Conditions share game/actor seed blocks; train/dev/test never share namespaces.
    seed_key = [stage, round_id, block, team, side]
    return dict(slot_id=f"{stage}-{round_id}-{condition}-{block:03d}-{team}-{side}",
                stage=stage, condition=condition, block=block, model_team=team, model_side=side,
                teams=assignment, players={side: descriptors[0], other: descriptors[1]},
                seed_key=seed_key, round_id=round_id, simulator_seed=showdown_seed("game", seed_key))


def paired(stage, condition, blocks, descriptors, *, round_id=0):
    return [matchup(stage, condition, block, team, side, descriptors, round_id=round_id)
            for block in range(blocks) for team in ("A", "B") for side in ("p1", "p2")]


def training(round_id):
    # Eight independent seed blocks, four orientations: 32 games per round.
    return paired("train", "selfplay", 8, [players("current", "search")] * 2, round_id=round_id)


def development(round_id):
    return paired("dev", "candidate", 16, [players("current", "policy"), players("P0", "policy")],
                  round_id=round_id)


def test_schedule():
    result = []
    for label, model, mode in [("P0", "P0", "policy"), ("P0+S", "P0", "search"),
                                ("P1", "P1", "policy"), ("P1+S", "P1", "search")]:
        result.extend(paired("test", label, PROTOCOL["test_blocks"],
                             [players(model, mode), players(None, "opponent")]))
    result.extend(paired("test-direct", "P1-v-P0", PROTOCOL["test_blocks"],
                         [players("P1", "policy"), players("P0", "policy")]))
    # Interleave conditions without using results; guards against deadline/order bias.
    return sorted(result, key=lambda row: seed("evaluation-order", row["slot_id"]))


def pilot_schedule():
    return (paired("pilot", "uniform", 8, [players(None, "uniform")] * 2)
            + paired("pilot", "P0", 8, [players("P0", "search")] * 2))
