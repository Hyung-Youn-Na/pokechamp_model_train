"""EX-072 mathematical, boundary, and completed-step resume checks (CPU only)."""
from __future__ import annotations

import copy
import math
import random
from types import SimpleNamespace

import pytest
import torch
from torch import nn

from integration.pokechamp.imitation import model as imitation
from integration.pokechamp.selfplay import model, objectives as obj, trainer
from integration.pokechamp.tests.test_imitation_learning import public_input


class TinyPolicy(nn.Module):
    """A differentiable frozen-base model with independent policy and W/D/L heads."""
    def __init__(self):
        super().__init__()
        self.base = nn.Parameter(torch.tensor([.5, 1., -.2], dtype=torch.bfloat16), requires_grad=False)
        self.lora = nn.Parameter(torch.tensor([.02, -.01, .03]))
        self.action_head = nn.Parameter(torch.tensor([.1, -.1, .0]))
        self.wdl_head = model.make_wdl_head(1)
        self.tokenizer = None
        self.sampling_generator = random.Random(20261002)
        self.stage = "policy"
        self._weight_names = {n for n, p in self.named_parameters() if p.requires_grad}

    def set_stage(self, stage):
        self.stage = stage
        for name, parameter in self.named_parameters():
            parameter.requires_grad_(name in self._weight_names and
                                     (stage == "policy" or stage == "calibration" and name.startswith("wdl_head.")))
        self.train(stage != "inference")

    def scores(self, encoded):
        h = self.base.float() + self.lora
        features = torch.stack((h.mean().expand(3), h), -1)
        return model.Scores(h + self.action_head, self.wdl_head(features), features)

    def trainable_fingerprints(self):
        return imitation.tensor_fingerprints(self, lambda n, p: n in self._weight_names)

    def policy_fingerprints(self):
        return imitation.tensor_fingerprints(self, lambda n, p: n in self._weight_names and not n.startswith("wdl_head."))

    def base_fingerprints(self):
        return imitation.tensor_fingerprints(self, lambda n, p: n not in self._weight_names)

    def snapshot_weights(self):
        return {n: p.detach().clone() for n, p in self.named_parameters() if n in self._weight_names}

    def load_weights(self, weights):
        with torch.no_grad():
            for name, parameter in self.named_parameters():
                if name in weights:
                    parameter.copy_(weights[name])


def fake_encode(value, tokenizer=None):
    body = imitation.input_body(value)
    ids = tuple(body["questions"]["action"]["criteria"])
    return model.EncodedChoice({}, ids, 100, 80, imitation.json_sha256(body))


@pytest.fixture
def tiny(monkeypatch):
    torch.manual_seed(23)
    monkeypatch.setattr(trainer, "encode_input", fake_encode)
    return TinyPolicy()


def bc_records(count=5):
    body = public_input().body
    return [dict(sample_id=f"bc-{i}", split="train", input=body,
                 label=list(body["questions"]["action"]["criteria"])[i % 3]) for i in range(count)]


def rollout(policy, count=17, *, round_id=1):
    body = public_input().body
    encoded = fake_encode(body)
    with torch.no_grad():
        scores = policy.scores(encoded)
        logp = scores.log_probabilities.tolist()
        wdl = scores.wdl_probabilities.tolist()
        baseline = float(obj.old_baseline(scores.log_probabilities, scores.wdl_probabilities))
    return [dict(decision_id=f"round-{round_id}-{i}", slot_id=f"game-{i // 3}", round_id=round_id,
                 input=copy.deepcopy(body), input_sha256=encoded.input_sha256,
                 action_ids=list(encoded.action_ids), choice=encoded.action_ids[i % 3],
                 log_probabilities=list(logp), wdl_probabilities=copy.deepcopy(wdl), baseline=baseline,
                 terminal_status="completed", outcome=("W", "D", "L")[i % 3], submitted=True)
            for i in range(count)]


def test_ppo_ratio_clip_handles_positive_and_negative_advantages():
    old = torch.zeros(4, requires_grad=True)
    new = torch.log(torch.tensor([1.5, .5, 1.5, .5])).requires_grad_()
    advantage = torch.tensor([1., 1., -1., -1.], requires_grad=True)
    loss = obj.ppo_loss(new, old, advantage)
    assert loss.tolist() == pytest.approx([-1.2, -.5, 1.5, .8])
    loss.sum().backward()
    assert old.grad is None and advantage.grad is None
    assert new.grad.tolist() == pytest.approx([0., -.5, 1.5, 0.])


def test_baseline_uses_entire_old_policy_wdl_and_detaches():
    logp = torch.tensor([.25, .75]).log().requires_grad_()
    wdl = torch.tensor([[.8, .1, .1], [.2, .4, .4]], requires_grad=True)
    baseline = obj.old_baseline(logp, wdl)
    assert float(baseline) == pytest.approx(.25 * .85 + .75 * .4)
    assert not baseline.requires_grad


def test_half_brier_and_wdl_normalization():
    assert float(obj.half_brier(torch.tensor([1., 0., 0.]), 0)) == 0
    assert float(obj.half_brier(torch.tensor([1., 0., 0.]), 2)) == 1
    assert float(obj.half_brier(torch.ones(3) / 3, 1)) == pytest.approx(1 / 3)
    with pytest.raises(ValueError):
        obj.half_brier(torch.tensor([.3, .3, .3]), 0)
    with pytest.raises(ValueError):
        obj.half_brier(torch.tensor([1., 0., 0.]), 3)


def test_full_distribution_kl_is_not_selected_action_kl():
    old = torch.tensor([.5, .25, .25]).log()
    new = torch.tensor([.5, .49, .01]).log()
    assert float(obj.policy_kl(old, new)) == pytest.approx(.25 * math.log(.25 / .49) + .25 * math.log(25))
    assert float(obj.policy_kl(old, new)) > .02


@pytest.mark.parametrize("outcome,reward,target", [("W", 1., 0), ("D", .5, 1), ("L", 0., 2)])
def test_only_normal_terminal_games_have_reward(outcome, reward, target):
    assert obj.terminal_target(outcome) == (target, reward)
    for status in ("timeout", "error", "interrupted", None):
        with pytest.raises(ValueError):
            obj.terminal_target(outcome, status)


def test_failed_and_automatic_decisions_do_not_enter_learning(tiny):
    records = rollout(tiny, 3)
    records[0]["terminal_status"] = "timeout"
    records[1]["action_ids"] = [records[1]["choice"]]
    criteria = records[1]["input"]["questions"]["action"]["criteria"]
    records[1]["input"]["questions"]["action"]["criteria"] = {records[1]["choice"]: criteria[records[1]["choice"]]}
    assert [r["decision_id"] for r in obj.eligible_decisions(records)] == [records[2]["decision_id"]]
    # Explicitly submitted flinched/paralyzed choices remain supervised.
    records[2]["executed"] = False
    assert len(obj.eligible_decisions(records)) == 1


def test_corrupt_candidate_count_cannot_masquerade_as_automatic(tiny):
    record = rollout(tiny, 1)[0]
    record["action_ids"] = [record["choice"]]
    with pytest.raises(ValueError, match="candidate order"):
        obj.eligible_decisions([record])


def test_candidate_order_baseline_and_round_integrity(tiny):
    record = rollout(tiny, 1)[0]
    obj.validate_decision(record, round_id=1)
    bad = copy.deepcopy(record)
    bad["action_ids"].reverse()
    with pytest.raises(ValueError, match="order"):
        obj.validate_decision(bad)
    bad = copy.deepcopy(record)
    bad["baseline"] += .1
    with pytest.raises(ValueError, match="baseline"):
        obj.validate_decision(bad)
    with pytest.raises(ValueError, match="another round"):
        obj.validate_decision(record, round_id=2)
    bad = copy.deepcopy(record)
    bad["log_probabilities"] = dict(reversed(list(zip(bad["action_ids"], bad["log_probabilities"]))))
    with pytest.raises(ValueError, match="insertion order"):
        obj.validate_decision(bad)


def test_hash_selection_has_no_outcome_dependence(tiny):
    records = rollout(tiny, 30)
    selected = [r["decision_id"] for r in obj.seeded_selection(records, 8, namespace="round-1")]
    changed = [dict(r, outcome="L", baseline=.123) for r in reversed(records)]
    assert selected == [r["decision_id"] for r in obj.seeded_selection(changed, 8, namespace="round-1")]


def test_sampling_is_reproducible_temperature_one_and_offline_auditable():
    probabilities = torch.tensor([.1, .2, .7])
    outcomes = []
    for seed in range(2000):
        choice, uniform = model.sample_categorical(probabilities, seed=seed, return_uniform=True)
        assert choice == model.sample_categorical(probabilities, seed=seed)
        assert uniform == random.Random(seed).random()
        outcomes.append(choice)
    assert outcomes.count(0) / 2000 == pytest.approx(.1, abs=.025)
    assert outcomes.count(1) / 2000 == pytest.approx(.2, abs=.025)
    assert outcomes.count(2) / 2000 == pytest.approx(.7, abs=.025)


def test_zero_initialized_wdl_and_action_policy_independence():
    head = model.make_wdl_head(4)
    features = torch.randn(5, 8, requires_grad=True)
    probability = head(features).softmax(-1)
    assert torch.equal(probability, torch.full((5, 3), 1 / 3))
    assert all(p.dtype == torch.float32 for p in head.parameters())
    obj.half_brier(probability, torch.tensor([0, 1, 2, 0, 1])).mean().backward()
    assert torch.equal(features.grad, torch.zeros_like(features))
    assert head[-1].weight.grad.abs().sum() > 0


def test_combined_step_means_rl_and_bc_independently(tiny, monkeypatch):
    records, bc = rollout(tiny, 3), bc_records(4)
    reference = copy.deepcopy(tiny)
    losses = []
    for record in records:
        scores = reference.scores(fake_encode(record["input"]))
        target, reward = obj.terminal_target(record["outcome"])
        index = record["action_ids"].index(record["choice"])
        losses.append(obj.ppo_loss(scores.log_probabilities[index], torch.tensor(record["log_probabilities"][index]),
                                   reward - record["baseline"]) + .5 * obj.half_brier(scores.wdl_probabilities[index], target))
    bc_losses = [imitation.choice_loss(reference.scores(fake_encode(r["input"])).logits,
                                      fake_encode(r["input"]).action_ids, r["label"]) for r in bc]
    expected = torch.stack(losses).mean() + .1 * torch.stack(bc_losses).mean()
    expected.backward()
    torch.nn.utils.clip_grad_norm_([p for p in reference.parameters() if p.requires_grad], 1.)
    optimizer = trainer.make_optimizer(tiny)
    gradients = {}
    def inspect_step():
        gradients.update({n: p.grad.clone() for n, p in tiny.named_parameters() if p.requires_grad})
    monkeypatch.setattr(optimizer, "step", inspect_step)
    result = trainer._round_step(tiny, optimizer, records, bc, deadline=None, should_stop=None)
    assert result["applied"] and result["loss"] == pytest.approx(float(expected.detach()), abs=1e-6)
    for name, parameter in reference.named_parameters():
        if parameter.requires_grad:
            assert torch.allclose(gradients[name], parameter.grad, atol=1e-7, rtol=1e-5), name
    assert tiny.base.grad is None


def test_kl_discard_leaves_weights_optimizer_and_cursor_unapplied(tiny):
    records, bc = rollout(tiny), bc_records()
    optimizer = trainer.make_optimizer(tiny)
    def increase_kl(policy, optimizer, state, metrics):
        with torch.no_grad():
            policy.action_head[0].add_(3.)
        return False
    first = trainer.train_round(tiny, records, bc, round_id=1, optimizer=optimizer, on_step=increase_kl)
    before, state_before = tiny.trainable_fingerprints(), copy.deepcopy(optimizer.state_dict())
    result = trainer.train_round(tiny, records, bc, round_id=1, optimizer=optimizer, state=first["state"])
    assert result["status"] == "kl_limit"
    assert result["state"]["global_updates"] == 1
    assert result["metrics"][0]["applied"] is False
    assert tiny.trainable_fingerprints() == before
    for key, value in state_before["state"].items():
        for field in value:
            assert torch.equal(value[field], optimizer.state_dict()["state"][key][field])
    assert all(p.grad is None for p in tiny.parameters())


def test_completed_step_resume_is_bitwise_identical(tiny):
    records, bc = rollout(tiny), bc_records()
    full, resumed = copy.deepcopy(tiny), copy.deepcopy(tiny)
    full_optimizer = trainer.make_optimizer(full)
    full_result = trainer.train_round(full, records, bc, round_id=1, optimizer=full_optimizer)
    assert full_result["state"]["global_updates"] == 4
    optimizer = trainer.make_optimizer(resumed)
    stopped = trainer.train_round(resumed, records, bc, round_id=1, optimizer=optimizer,
                                  on_step=lambda *_: False)
    saved = trainer.training_state(resumed, optimizer, stopped["state"])
    reloaded = copy.deepcopy(tiny)
    reloaded.load_weights(resumed.snapshot_weights())
    reloaded_optimizer = trainer.make_optimizer(reloaded)
    cursor = trainer.restore_training_state(reloaded, reloaded_optimizer, saved)
    final = trainer.train_round(reloaded, records, bc, round_id=1, optimizer=reloaded_optimizer, state=cursor)
    assert final["status"] == "complete"
    assert final["state"] == full_result["state"]
    assert full.trainable_fingerprints() == reloaded.trainable_fingerprints()


def test_old_policy_audit_checkpoint_resumes_without_any_update(tiny):
    records, bc = rollout(tiny), bc_records()
    optimizer = trainer.make_optimizer(tiny)
    saved = []
    def boundary(policy, optimizer, state):
        if state["verify_index"] == 5:
            saved.append(trainer.training_state(policy, optimizer, state))
            return False
    partial = trainer.train_round(tiny, records, bc, round_id=1, optimizer=optimizer, on_boundary=boundary)
    assert partial["status"] == "interrupted" and partial["state"]["global_updates"] == 0
    assert partial["state"]["verify_index"] == 5
    cursor = trainer.restore_training_state(tiny, optimizer, saved[0])
    complete = trainer.train_round(tiny, records, bc, round_id=1, optimizer=optimizer, state=cursor)
    assert complete["status"] == "complete" and complete["state"]["verify_index"] == len(records)


def test_resume_rejects_changed_rollout_bc_or_weights(tiny):
    records, bc = rollout(tiny), bc_records()
    optimizer = trainer.make_optimizer(tiny)
    stopped = trainer.train_round(tiny, records, bc, round_id=1, optimizer=optimizer, on_step=lambda *_: False)
    saved = trainer.training_state(tiny, optimizer, stopped["state"])
    changed = copy.deepcopy(records)
    changed[0]["outcome"] = "L"
    with pytest.raises(ValueError, match="digest"):
        trainer.train_round(tiny, changed, bc, round_id=1, optimizer=optimizer, state=copy.deepcopy(stopped["state"]))
    changed_bc = copy.deepcopy(bc)
    changed_bc[0]["split"] = "test"
    with pytest.raises(ValueError, match="train-only"):
        trainer.train_round(tiny, records, changed_bc, round_id=1, optimizer=optimizer)
    with torch.no_grad():
        tiny.lora.add_(.1)
    with pytest.raises(ValueError, match="weights"):
        trainer.restore_training_state(tiny, optimizer, saved)


def test_policy_updates_carry_across_rounds_without_replaying_data(tiny):
    optimizer = trainer.make_optimizer(tiny)
    first = trainer.train_round(tiny, rollout(tiny), bc_records(), round_id=1, optimizer=optimizer)
    second = trainer.train_round(tiny, rollout(tiny, round_id=2), bc_records(), round_id=2,
                                 optimizer=optimizer, state=first["state"])
    assert second["state"]["global_updates"] == 8
    assert second["state"]["round_updates"] == 4
    with pytest.raises(ValueError, match="advance"):
        trainer.train_round(tiny, rollout(tiny), bc_records(), round_id=1,
                            optimizer=optimizer, state=second["state"])


def test_deadline_and_signal_never_apply_partial_updates(tiny):
    records = rollout(tiny)
    before = tiny.trainable_fingerprints()
    result = trainer.train_round(tiny, records, bc_records(), round_id=1, deadline=0)
    assert result["status"] == "deadline" and result["state"]["global_updates"] == 0
    assert tiny.trainable_fingerprints() == before
    calls = 0
    def stopping():
        nonlocal calls
        calls += 1
        return calls > 21
    result = trainer.train_round(tiny, records, bc_records(), round_id=1, should_stop=stopping)
    assert result["status"] == "interrupted" and result["state"]["global_updates"] == 0
    assert tiny.trainable_fingerprints() == before
    assert all(p.grad is None for p in tiny.parameters())


def test_old_logprobs_must_match_before_first_update(tiny):
    records = rollout(tiny)
    with torch.no_grad():
        tiny.action_head[0].add_(.02)
    before = tiny.trainable_fingerprints()
    with pytest.raises(ValueError, match="reproduce"):
        trainer.train_round(tiny, records, bc_records(), round_id=1)
    assert tiny.trainable_fingerprints() == before


def test_head_calibration_changes_only_wdl_and_resumes(tiny):
    records = rollout(tiny, 17)
    features = trainer.extract_features(tiny, records)
    before_policy, before_base = tiny.policy_fingerprints(), tiny.base_fingerprints()
    before_logits = tiny.scores(fake_encode(records[0]["input"])).logits.detach().clone()
    full = copy.deepcopy(tiny)
    complete = trainer.train_head(full, features)
    optimizer = trainer.make_optimizer(tiny, calibration=True)
    stopped = trainer.train_head(tiny, features, optimizer=optimizer, on_step=lambda *_: False)
    saved = trainer.training_state(tiny, optimizer, stopped["state"])
    cursor = trainer.restore_training_state(tiny, optimizer, saved)
    final = trainer.train_head(tiny, features, optimizer=optimizer, state=cursor)
    assert final["policy_unchanged"] and complete["state"]["updates"] == 4
    assert full.trainable_fingerprints() == tiny.trainable_fingerprints()
    assert tiny.policy_fingerprints() == before_policy and tiny.base_fingerprints() == before_base
    assert torch.equal(before_logits, tiny.scores(fake_encode(records[0]["input"])).logits)
    assert not torch.equal(tiny.wdl_head[-1].weight, torch.zeros_like(tiny.wdl_head[-1].weight))


def test_incomplete_feature_extraction_cannot_be_adopted(tiny):
    with pytest.raises(TimeoutError, match="did not finish"):
        trainer.extract_features(tiny, rollout(tiny), deadline=0)


def test_checkpoint_requires_optimizer_boundary(tiny):
    optimizer = trainer.make_optimizer(tiny)
    tiny.action_head.grad = torch.ones_like(tiny.action_head)
    with pytest.raises(ValueError, match="unfinished"):
        trainer.training_state(tiny, optimizer, {})


class FakeInherited(nn.Module):
    """Imitation-shaped module for testing composition without loading a GPU."""
    def __init__(self, device="cpu", checkpoint=None, tokenizer=None):
        super().__init__()
        self.tokenizer = tokenizer
        lm = nn.Module()
        lm.base = nn.Parameter(torch.ones(4, 2, dtype=torch.bfloat16), requires_grad=False)
        lm.lora_A = nn.Parameter(torch.tensor([.25, .5]))
        lm.dropout = nn.Dropout(.05)
        lm.peft_config = {"default": SimpleNamespace(lora_dropout=.05)}
        head = nn.Module()
        head.q, head.k = nn.Linear(2, 2), nn.Linear(2, 2)
        head.forward = lambda decision, candidates: head.k(candidates) @ head.q(decision)
        self.model = nn.Module()
        self.model.lm, self.model.head = lm, head
        self.calls = 0
        def hidden(rows):
            self.calls += 1
            return [lm.base + lm.dropout(lm.lora_A).to(torch.bfloat16)]
        self.model._rows_hidden = hidden

    @property
    def backbone(self):
        return self.model.lm

    @property
    def head(self):
        return self.model.head

    def logits(self, encoded):
        hidden = self.model._rows_hidden([None])[0]
        return self.head(hidden[3].float(), hidden[torch.tensor([0, 1, 2])].float())


@pytest.fixture
def composed(monkeypatch):
    monkeypatch.setattr(imitation, "Policy", FakeInherited)
    monkeypatch.setattr(imitation, "_kev", lambda: (None, SimpleNamespace(
        rows_of=lambda encoding: ([], [], [{"ids": [1, 2, 3, 4], "pos": [0, 1, 2, 3], "opts": [0, 1, 2], "decide": 3}]))))
    monkeypatch.setattr(model, "encode_input", fake_encode)
    monkeypatch.setattr(trainer, "encode_input", fake_encode)
    return model.SelfPlayPolicy(device="cpu", checkpoint=None)


def test_composed_readouts_share_one_forward_and_snapshot_reload(composed, tmp_path):
    encoded = fake_encode(public_input().body)
    composed.eval()
    before_calls = composed.policy.calls
    scores = composed.scores(encoded)
    assert composed.policy.calls == before_calls + 1
    assert torch.equal(scores.logits, composed.policy.logits(encoded))
    assert torch.equal(scores.wdl_probabilities, torch.full((3, 3), 1 / 3))
    composed.assert_precision()
    fingerprints = composed.trainable_fingerprints()
    path = tmp_path / "snapshot.pt"
    composed.save_snapshot(path, {"round": 0})
    with torch.no_grad():
        composed.wdl_head[-1].bias.add_(1)
    assert composed.load_snapshot(path) == {"round": 0}
    assert composed.trainable_fingerprints() == fingerprints


def test_preflight_is_bounded_finite_and_performs_no_optimizer_update(composed):
    report = trainer.preflight(composed, bc_records(33))
    assert report["passed"] and report["samples"] == 32 and report["optimizer_updates"] == 0
    assert report["base_unchanged"] and report["trainable_unchanged"]
    assert report["initial_policy_exact_parity"] and report["max_initial_wdl_uniform_error"] == 0
    assert report["max_train_inference_logit_difference"] == 0
    with pytest.raises(ValueError):
        trainer.preflight(composed, bc_records(), max_samples=33)


def test_predict_keeps_sampling_and_wdl_distinct_and_alternate_head_policy_fixed(composed):
    body = public_input().body
    before = composed.predict(body, seed=100)
    alternate = {k: v.detach().clone() for k, v in composed.wdl_head.state_dict().items()}
    alternate["2.bias"] = torch.tensor([2., 0., -2.])
    after = composed.predict(body, seed=100, alternate_head=alternate)
    assert before["choice"] == after["choice"]
    assert before["probabilities"] == after["probabilities"]
    assert before["wdl_probabilities"] == after["wdl_probabilities"]
    assert after["wdl_probabilities_after"] != after["wdl_probabilities"]
    assert after["sampling_uniform"] == random.Random(100).random()
