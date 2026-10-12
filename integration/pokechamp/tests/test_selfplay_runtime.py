"""EX-072 original-budget, terminal gate and durable checkpoint invariants."""

import copy
import random
from pathlib import Path

import pytest
import torch

from integration.pokechamp.selfplay import execution
from integration.pokechamp.selfplay.runner import outcomes_for, round_gate
from integration.pokechamp.selfplay.storage import Clock, atomic, read, sha


def slot(n=0):
    return {
        "slot_id": f"slot-{n}",
        "stage": "train",
        "round": 1,
        "model": "initial",
        "pair_id": f"pair-{n // 2}",
        "model_side": "p1" if n % 2 == 0 else "p2",
        "opponent": "current",
        "simulator_seed": [1, 2, 3, n],
    }


def test_original_clock_and_each_stage_deadline_survive_restart(tmp_path):
    first = Clock(tmp_path, start=True, now=1000)
    assert first.deadline("policy") == 58600
    assert first.deadline("calibration") == 65800
    assert first.deadline("test") == 86500
    assert first.deadline("total") == 87400
    resumed = Clock(tmp_path, start=True, now=9000)
    assert resumed.record == first.record
    bad = copy.deepcopy(first.record)
    bad["deadline_at"] += 1
    atomic(tmp_path / "clock.json", bad)
    with pytest.raises(ValueError, match="deadline"):
        Clock(tmp_path)


def test_round_gate_counts_attempts_normal_games_and_actual_multi_choices():
    outcomes = [
        dict(
            slot(i),
            status="completed" if i < 48 else "failed",
            result="win" if i < 48 else None,
        )
        for i in range(64)
    ]
    decisions = [
        {
            "slot_id": "slot-0",
            "terminal_status": "completed",
            "action_ids": ["a", "b"],
            "automatic": False,
        }
        for _ in range(512)
    ]
    assert round_gate(outcomes, decisions)["passed"]
    assert not round_gate(outcomes[:-1], decisions)["passed"]
    outcomes[-1]["status"] = "unattempted"
    assert not round_gate(outcomes, decisions)["passed"]
    outcomes[-1]["status"] = "failed"
    outcomes[0]["status"] = "incomplete"
    outcomes[0]["result"] = None
    assert not round_gate(outcomes, decisions)["passed"]
    outcomes[0]["status"] = "completed"
    outcomes[0]["result"] = "win"
    decisions[-1]["automatic"] = True
    assert not round_gate(outcomes, decisions)["passed"]
    decisions[-1]["automatic"] = False
    decisions[-1]["action_ids"] = ["a"]
    assert not round_gate(outcomes, decisions)["passed"]


def test_claimed_interruption_is_consumed_without_replacement(tmp_path):
    rows = [slot(0), slot(1)]
    attempt = tmp_path / "games/slot-0"
    attempt.mkdir(parents=True)
    atomic(attempt / "request.json", {"slot": rows[0]}, immutable=True)
    result = outcomes_for(tmp_path, rows)
    assert [(r["status"], r["result"]) for r in result] == [
        ("incomplete", None),
        ("unattempted", None),
    ]
    assert read(attempt / "outcome.json")["reason"] == "interrupted_claim"
    before = sha(attempt / "outcome.json")
    assert outcomes_for(tmp_path, rows) == result
    assert sha(attempt / "outcome.json") == before


class TinyPolicy(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.tensor([1.0, 2.0]))
        self.sampling_generator = random.Random(42)

    def snapshot_weights(self):
        return {"weight": self.weight.detach().clone()}

    def load_weights(self, weights):
        with torch.no_grad():
            self.weight.copy_(weights["weight"])


def test_complete_checkpoint_restores_optimizer_rng_cursor_and_original_deadline(
    tmp_path,
):
    policy = TinyPolicy()
    optim = torch.optim.AdamW(policy.parameters(), lr=1e-5)
    atomic(tmp_path / "manifest.json", {"frozen": True}, immutable=True)
    clock = Clock(tmp_path, start=True, now=100)
    policy.weight.sum().backward()
    optim.step()
    optim.zero_grad(set_to_none=True)
    state = {
        "phase": "train",
        "trainer": {"global_updates": 1, "epoch": 0, "index": 16},
    }
    record = execution.save_checkpoint(tmp_path, policy, optim, state, clock)
    expected = policy.snapshot_weights()
    expected_rng = torch.get_rng_state().clone()
    policy.weight.data.add_(100)
    random.seed(999)
    torch.manual_seed(999)
    payload = execution.load_checkpoint(tmp_path, policy, optim, Clock(tmp_path))
    assert torch.equal(policy.weight, expected["weight"])
    assert torch.equal(torch.get_rng_state(), expected_rng)
    assert payload["state"] == state and payload["clock"] == clock.record
    assert next(iter(optim.state.values()))["step"] == 1
    assert sha(record["path"]) == record["sha256"]
    atomic(tmp_path / "manifest.json", {"frozen": False})
    with pytest.raises(ValueError, match="different clock or frozen"):
        execution.load_checkpoint(tmp_path, policy, optim, clock)


def test_failed_checkpoint_never_replaces_last_committed_pointer(tmp_path, monkeypatch):
    policy = TinyPolicy()
    optim = torch.optim.AdamW(policy.parameters(), lr=1e-5)
    atomic(tmp_path / "manifest.json", {})
    clock = Clock(tmp_path, start=True, now=100)
    state = {"phase": "collect", "trainer": None}
    first = execution.save_checkpoint(tmp_path, policy, optim, state, clock)
    assert first["global_updates"] == 0

    def fail(payload, stream):
        stream.write(b"partial")
        raise OSError("disk failure")

    monkeypatch.setattr(torch, "save", fail)
    with pytest.raises(OSError):
        execution.save_checkpoint(tmp_path, policy, optim, state, clock)
    assert read(tmp_path / "latest.json") == first
    assert len(list((tmp_path / "checkpoints").glob("*.pt"))) == 1
    assert not list((tmp_path / "checkpoints").glob(".checkpoint-*"))


def test_checkpoint_integrity_precedes_loading_pickle(tmp_path):
    policy = TinyPolicy()
    optim = torch.optim.AdamW(policy.parameters(), lr=1e-5)
    atomic(tmp_path / "manifest.json", {})
    clock = Clock(tmp_path, start=True, now=100)
    record = execution.save_checkpoint(
        tmp_path, policy, optim, {"phase": "train"}, clock
    )
    Path(record["path"]).write_bytes(b"corruption")
    with pytest.raises(ValueError, match="integrity"):
        execution.load_checkpoint(tmp_path, policy, optim, clock)
