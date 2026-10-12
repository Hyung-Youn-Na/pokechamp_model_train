"""Simultaneous-action Exp3 MCTS with independently sampled chance transitions."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
import time

from .storage import digest, showdown_seed


def distribution(values):
    values = [float(v) for v in values]
    if not values or any(not math.isfinite(v) or v < 0 for v in values) or sum(values) <= 0:
        raise ValueError("invalid probability distribution")
    total = sum(values)
    return [v / total for v in values]


def draw(probabilities, rng):
    probabilities = distribution(probabilities)
    u, cumulative = rng.random(), 0.0
    for index, p in enumerate(probabilities):
        cumulative += p
        if u < cumulative:
            return index
    return len(probabilities) - 1


class Exp3:
    def __init__(self, prior, *, gamma=0.1, eta=0.05):
        if not 0 < gamma <= 1 or not 0 < eta <= 1:
            raise ValueError("invalid Exp3 parameters")
        self.gamma, self.eta = gamma, eta
        self.weights = [math.log(max(p, 1e-8)) for p in distribution(prior)]
        self.visits = [0] * len(self.weights)

    def probabilities(self):
        highest = max(self.weights)
        base = distribution([math.exp(w - highest) for w in self.weights])
        return [(1 - self.gamma) * p + self.gamma / len(base) for p in base]

    def choose(self, rng):
        probabilities = self.probabilities()
        selected = draw(probabilities, rng)
        return selected, probabilities[selected]

    def update(self, selected, probability, reward):
        if not math.isfinite(reward) or not 0 <= reward <= 1 or not 0 < probability <= 1:
            raise ValueError("invalid Exp3 feedback")
        self.visits[selected] += 1
        self.weights[selected] += self.eta * reward / probability
        top = max(self.weights)
        self.weights = [w - top for w in self.weights]


@dataclass
class Node:
    action_ids: dict
    selectors: dict
    value: float


def make_node(frame, evaluate):
    observations = [frame["observations"][s] for s in ("p1", "p2")]
    outputs = evaluate(observations)
    if len(outputs) != 2:
        raise ValueError("expected two perspective outputs")
    values, ids, selectors = [], {}, {}
    for side, observation, result in zip(("p1", "p2"), observations, outputs):
        actions = [a["id"] for a in observation["actions"]]
        if len(set(actions)) != len(actions) or len(result["policy"]) != len(actions):
            raise ValueError("model/action alignment failure")
        value = float(result["value"])
        if not math.isfinite(value) or abs(value) > 1.000001:
            raise ValueError("invalid state value")
        values.append(value)
        ids[side] = actions
        if actions:
            selectors[side] = Exp3(result["policy"])
    return Node(ids, selectors, (values[0] - values[1]) / 2)


def search(root, simulator, evaluate, *, search_seed, simulations=64, depth=32, check=lambda: None):
    if simulations < 1 or depth < 1:
        raise ValueError("positive search budget required")
    start = time.monotonic()
    frame = simulator.restore(root, showdown_seed("search", search_seed, "initialize"))
    if frame["ended"]:
        raise ValueError("terminal root cannot be searched")
    root_key = digest(frame["root"])
    tree = {root_key: make_node(frame, evaluate)}
    rngs = {side: random.Random(digest([search_seed, side])) for side in ("p1", "p2")}
    transitions, returns = 0, []
    for simulation in range(simulations):
        check()
        frame = simulator.restore(root, showdown_seed("search", search_seed, simulation))
        node, path = tree[root_key], []
        value = node.value
        for _ in range(depth):
            check()
            picks, commands = {}, {}
            # Neither selection sees the other's realized action.
            for side, selector in node.selectors.items():
                index, probability = selector.choose(rngs[side])
                picks[side] = index, probability
                commands[side] = node.action_ids[side][index]
            path.append((node, picks))
            frame = simulator.advance(commands)
            transitions += 1
            if frame["ended"]:
                value = 1.0 if frame["winner"] == "p1" else -1.0 if frame["winner"] == "p2" else 0.0
                break
            key = digest(frame["root"])
            if key not in tree:
                tree[key] = make_node(frame, evaluate)
                value = tree[key].value
                break
            node = tree[key]
            value = node.value
        for visited, picks in reversed(path):
            for side, (index, probability) in picks.items():
                own_value = value if side == "p1" else -value
                visited.selectors[side].update(index, probability, (own_value + 1) / 2)
        returns.append(value)
    initial = tree[root_key]
    result = {}
    for side, selector in initial.selectors.items():
        if sum(selector.visits) != simulations:
            raise ValueError("root visit conservation failed")
        result[side] = dict(action_ids=initial.action_ids[side], visits=selector.visits,
                            policy=[n / simulations for n in selector.visits])
    return dict(sides=result, simulations=simulations, transitions=transitions, nodes=len(tree),
                mean_value=sum(returns) / len(returns), seconds=time.monotonic() - start)
