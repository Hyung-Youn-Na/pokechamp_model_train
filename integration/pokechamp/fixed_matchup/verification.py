"""Synthetic acceptance checks; never uses the experimental A/B matchup."""
from __future__ import annotations

import copy
import tempfile
from pathlib import Path

from .search import search
from .simulator import Simulator
from .storage import digest

FIXTURE_TEAMS = {
    "p1": "Gholdengo @ Life Orb\nAbility: Good as Gold\nTera Type: Steel\nEVs: 252 SpA / 252 Spe\n"
          "- Make It Rain\n- Nasty Plot\n\nClefable\nAbility: Magic Guard\n- Moonblast",
    "p2": "Clefable\nAbility: Magic Guard\n- Moonblast\n\nBlissey\nAbility: Natural Cure\n- Soft-Boiled",
}


class MatrixGame:
    """Terminal payoff fixture exposes no realized opponent action to selection."""
    def __init__(self, payoffs):
        self.payoffs = payoffs

    def restore(self, root, seed):
        return dict(ended=False, root={"matrix": 1}, observations={s: {
            "actions": [{"id": "0"}, {"id": "1"}]} for s in ("p1", "p2")})

    def advance(self, actions):
        value = self.payoffs[int(actions["p1"])][int(actions["p2"])]
        return dict(ended=True, winner="p1" if value > 0 else "p2" if value < 0 else "")


def uniform(observations):
    return [dict(policy=[1 / len(o["actions"])] * len(o["actions"]) if o["actions"] else [], value=0)
            for o in observations]


def cpu_checks():
    with Simulator("real") as actual, Simulator("search") as branch:
        preview = actual.init(FIXTURE_TEAMS, [1, 2, 3, 4])
        before = digest(preview["root"])
        restored = branch.restore(preview["root"], [9, 8, 7, 6])
        assert restored["observations"] == preview["observations"]
        frame = actual.advance({"p1": "lead:1", "p2": "lead:1"})
        private = actual.evidence()
        current_seed = list(map(int, private["snapshot"]["prng"].split(",")))
        restored = branch.restore(frame["root"], current_seed)
        assert restored["observations"] == frame["observations"]
        actions = {s: o["actions"][0]["id"] for s, o in frame["observations"].items()}
        expected = actual.advance(actions)
        produced = branch.advance(actions)
        assert expected["root"] == produced["root"]
        assert digest(preview["root"]) == before
        # The fixture guarantees a forced switch, with no queued hidden move.
        assert not expected["observations"]["p1"]["actions"]
        assert expected["observations"]["p2"]["actions"][0]["id"] == "switch:2"
        restored = branch.restore(expected["root"], [5, 6, 7, 8])
        assert restored["observations"] == expected["observations"]
        vocabulary = actual.catalog()["vocabulary"]
    match = search({}, MatrixGame([[1, -1], [-1, 1]]), uniform, search_seed=17, simulations=4096)
    assert all(0.3 < info["policy"][0] < 0.7 for info in match["sides"].values())
    dominant = search({}, MatrixGame([[1, 1], [-1, -1]]), uniform, search_seed=18, simulations=512)
    assert dominant["sides"]["p1"]["policy"][0] > 0.85
    return dict(passed=True, roundtrip=True, forced_switch=True, independent_root=True,
                matching_pennies=match["sides"], dominance=dominant["sides"],
                vocabulary=vocabulary, observation=preview["observations"]["p1"],
                forced_observations=list(expected["observations"].values()))


def model_checks(vocabulary, observation, *, device="cpu"):
    import torch
    from .model import Policy, learn

    torch.manual_seed(791)
    model = Policy(vocabulary).to(device).eval()
    original = model.evaluate_batch([observation])[0]
    batched = model.evaluate_batch([observation, observation])[0]
    error = max(abs(a - b) for a, b in zip(original["policy"] + [original["value"]],
                                         batched["policy"] + [batched["value"]]))
    if error > 1e-5:
        raise ValueError("batch prediction tolerance failed")
    longest = copy.deepcopy(observation)
    longest["tokens"] = (longest["tokens"] * 256)[:256]
    longest["actions"] = [dict(copy.deepcopy(observation["actions"][0]), id=f"fixture:{i}") for i in range(13)]
    boundary = model.evaluate_batch([longest])[0]
    if len(boundary["policy"]) != 13 or abs(sum(boundary["policy"]) - 1) > 1e-6:
        raise ValueError("maximum shape inference failed")
    with tempfile.TemporaryDirectory(prefix="fixed-matchup-check-") as folder:
        path = Path(folder) / "model.pt"
        model.save(path)
        loaded = Policy.load(path, device)
        after = loaded.evaluate_batch([observation])[0]
        if max(abs(a - b) for a, b in zip(original["policy"] + [original["value"]],
                                          after["policy"] + [after["value"]])) > 1e-5:
            raise ValueError("reload tolerance failed")
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    rows = [dict(observation=observation, observation_hash=digest(observation),
                 terminal_status="completed", z=1,
                 target=[1.0] + [0.0] * (len(observation["actions"]) - 1))] * 4
    initial = copy.deepcopy(model.state_dict())
    update = learn(model, optimizer, rows, generator=torch.Generator().manual_seed(8), batch_size=4)
    assert any(not torch.equal(initial[k], v) for k, v in model.state_dict().items())
    return dict(passed=True, device=device, batch_error=error, update_steps=update["steps"],
                parameters=sum(p.numel() for p in model.parameters()), max_shape=[256, 13])


def verify(*, device="cpu"):
    checked = cpu_checks()
    vocabulary, forced = checked.pop("vocabulary"), checked.pop("forced_observations")
    result = model_checks(vocabulary, checked.pop("observation"), device=device)
    from .model import Policy
    Policy(vocabulary).to(device).eval().evaluate_batch(forced)
    result["forced_switch_fainted_encoding"] = True
    browser = browser_checks()
    return dict(passed=True, simulator=checked, model=result, browser=browser, synthetic_only=True,
                experimental_games=0, efficacy_evidence=False)


def browser_checks():
    """Fail before collecting experimental games if the offline browser is unavailable."""
    import json
    import os
    import subprocess
    from .config import ROOT
    from .finalize import BROWSER_PYTHON, page
    from .storage import atomic
    with tempfile.TemporaryDirectory(prefix="fixed-matchup-browser-gate-") as folder:
        root = Path(folder)
        (root / "fixture").mkdir()
        (root / "index.html").write_text("<!doctype html><a href='fixture/index.html'>fixture</a>")
        row = dict(job=dict(slot_id="fixture"), status="completed", winner="")
        (root / "fixture/index.html").write_text(page(row, [], "|tie|"))
        (root / "fixture/replay.html").write_text("<!doctype html>fixture")
        atomic(root / "task.json", dict(export=str(root), sample=["fixture"]))
        output = subprocess.check_output([str(BROWSER_PYTHON), "-m",
            "integration.pokechamp.fixed_matchup.browser_check", str(root / "task.json")],
            env=dict(os.environ, PYTHONPATH=str(ROOT)), cwd=ROOT, text=True, timeout=60)
        result = json.loads(output)
        if not result["passed"]:
            raise ValueError("offline browser preflight failed")
        return result
