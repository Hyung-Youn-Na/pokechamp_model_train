"""Bounded EX-072 optimization with checkpoints only at completed steps.

The runner owns battle admission, original wall-clock limits, immutable
snapshots and atomic checkpoint files. This module never starts a battle or
selects a GPU. ``on_step(policy, optimizer, cursor, metrics)`` is called after
the step and gradient cleanup; returning False requests a graceful stop.
"""
from __future__ import annotations

import copy
import time

import torch

from ..imitation.model import (check_gradients, choice_loss, input_body, json_sha256,
                               restore_rng, rng_state)
from .config import PROTOCOL, SEED
from .model import encode_input
from .objectives import (eligible_decisions, half_brier, ordered_values, policy_kl,
                         ppo_loss, seeded_selection, terminal_target, validate_decision)


class _InterruptedBatch(Exception):
    pass


def _stop_reason(deadline, should_stop):
    if should_stop is not None and should_stop():
        return "interrupted"
    if deadline is not None and time.time() >= deadline:
        return "deadline"
    return None


def _require_time(deadline, should_stop):
    if _stop_reason(deadline, should_stop):
        raise _InterruptedBatch()


def make_optimizer(policy, calibration=False):
    policy.set_stage("calibration" if calibration else "policy")
    config = PROTOCOL["optimizer"]
    return torch.optim.AdamW([p for p in policy.parameters() if p.requires_grad],
                            lr=PROTOCOL["calibration"]["lr"] if calibration else config["lr"],
                            betas=tuple(config["betas"]), weight_decay=config["weight_decay"])


def _validate_optimizer(policy, optimizer, *, calibration=False):
    expected = {id(p) for p in policy.parameters() if p.requires_grad}
    actual = [id(p) for group in optimizer.param_groups for p in group["params"]]
    config = PROTOCOL["optimizer"]
    rate = PROTOCOL["calibration"]["lr"] if calibration else config["lr"]
    if not isinstance(optimizer, torch.optim.AdamW) or set(actual) != expected or len(actual) != len(expected):
        raise ValueError("optimizer does not cover exactly the trainable parameters")
    for group in optimizer.param_groups:
        if (group["lr"] != rate or tuple(group["betas"]) != tuple(config["betas"])
                or group["weight_decay"] != config["weight_decay"]):
            raise ValueError("optimizer differs from the frozen EX-072 settings")


def training_state(policy, optimizer, cursor):
    """Complete optimizer-boundary payload for the runner's atomic checkpoint."""
    if any(p.grad is not None for p in policy.parameters()):
        raise ValueError("checkpoint requested inside an unfinished optimizer step")
    return dict(version="ex072-training-v1", optimizer=copy.deepcopy(optimizer.state_dict()),
                rng=rng_state(), cursor=copy.deepcopy(cursor),
                sampling_rng=copy.deepcopy(policy.sampling_generator.getstate()),
                parameter_fingerprints=policy.trainable_fingerprints(),
                protocol_sha256=json_sha256(PROTOCOL))


def restore_training_state(policy, optimizer, saved):
    if (saved.get("version") != "ex072-training-v1"
            or saved.get("protocol_sha256") != json_sha256(PROTOCOL)
            or saved["parameter_fingerprints"] != policy.trainable_fingerprints()):
        raise ValueError("resume weights or protocol differ from the completed checkpoint")
    cursor = copy.deepcopy(saved["cursor"])
    if cursor.get("stage") not in ("policy", "calibration"):
        raise ValueError("checkpoint has an unknown optimization stage")
    policy.set_stage(cursor["stage"])
    optimizer.load_state_dict(saved["optimizer"])
    _validate_optimizer(policy, optimizer, calibration=cursor["stage"] == "calibration")
    optimizer.zero_grad(set_to_none=True)
    restore_rng(saved["rng"])
    policy.sampling_generator.setstate(saved["sampling_rng"])
    return cursor


def _encoded(policy, record):
    value = encode_input(record["input"], policy.tokenizer)
    if "action_ids" in record and tuple(record["action_ids"]) != value.action_ids:
        raise ValueError("encoder changed the frozen rollout candidate order")
    if record.get("input_sha256", value.input_sha256) != value.input_sha256:
        raise ValueError("encoder input digest differs from the rollout")
    return value


def _bc_records(records, *, round_id):
    if not records:
        raise ValueError("EX-071 train split is required for BC retention")
    for record in records:
        ids = tuple(input_body(record["input"])["questions"]["action"]["criteria"])
        if (record.get("split") != "train" or not record.get("sample_id")
                or len(ids) < 2 or record.get("label") not in ids):
            raise ValueError("BC requires valid EX-071 train-only labels")
    return seeded_selection(records, len(records), namespace=f"bc-round-{round_id}", id_key="sample_id")


def _learning_digest(records):
    fields = ("decision_id", "input", "input_sha256", "action_ids", "choice",
              "log_probabilities", "wdl_probabilities", "baseline", "outcome",
              "terminal_status", "round_id", "slot_id")
    return json_sha256([{k: r[k] for k in fields if k in r} for r in records])


def _start_round_state(state, selected, bc, round_id):
    data_sha = _learning_digest(selected)
    bc_sha = json_sha256([{k: r[k] for k in ("sample_id", "split", "input", "label")} for r in bc])
    if state is None:
        state = {}
    if state.get("round_id") != round_id:
        if state and not state.get("complete"):
            raise ValueError("an unfinished PPO round cannot be replaced")
        previous = state.get("round_id")
        if previous is not None and round_id <= previous:
            raise ValueError("PPO rounds must advance without replaying an earlier round")
        updates = state.get("global_updates", 0)
        state.clear()
        state.update(stage="policy", round_id=round_id, epoch=0, index=0,
                     global_updates=updates, round_updates=0, bc_index=0,
                     verify_index=0, old_logprobs_verified=False, max_old_logprob_error=0.0,
                     max_old_wdl_error=0.0,
                     data_sha256=data_sha, bc_sha256=bc_sha,
                     selected_ids=[r["decision_id"] for r in selected], complete=False)
    batches_per_epoch = (len(selected) + PROTOCOL["rl_batch"] - 1) // PROTOCOL["rl_batch"]
    if (state.get("stage") != "policy" or state.get("data_sha256") != data_sha
            or state.get("bc_sha256") != bc_sha
            or state.get("selected_ids") != [r["decision_id"] for r in selected]
            or not 0 <= state.get("epoch", -1) <= PROTOCOL["epochs"]
            or not 0 <= state.get("index", -1) < len(selected)
            or state["index"] % PROTOCOL["rl_batch"] != 0
            or not 0 <= state.get("verify_index", -1) <= len(selected)
            or not 0 <= state.get("global_updates", -1) <= PROTOCOL["max_policy_updates"]
            or state.get("round_updates") != state["epoch"] * batches_per_epoch + state["index"] // PROTOCOL["rl_batch"]
            or state["global_updates"] < state["round_updates"]
            or state.get("bc_index") != state["round_updates"] * PROTOCOL["bc_batch"]
            or state.get("old_logprobs_verified") and state["verify_index"] != len(selected)
            or state["round_updates"] and not state.get("old_logprobs_verified")):
        raise ValueError("resume cursor or immutable replay digest differs")
    return state


def _verify_old_probabilities(policy, selected, state, deadline, should_stop, optimizer, on_boundary):
    """Audit every selected frozen rollout before this round's first update."""
    if state["old_logprobs_verified"]:
        return
    if state["round_updates"]:
        raise ValueError("optimization began before the old-policy audit")
    policy.eval()
    with torch.no_grad():
        for index in range(state["verify_index"], len(selected)):
            _require_time(deadline, should_stop)
            record = selected[index]
            encoded = _encoded(policy, record)
            scored = policy.scores(encoded)
            current = scored.log_probabilities
            old = torch.tensor(ordered_values(record["log_probabilities"], encoded.action_ids,
                                              name="old log probabilities"), device=current.device)
            error = float((current - old).abs().max())
            state["max_old_logprob_error"] = max(state["max_old_logprob_error"], error)
            if error > 1e-5:
                raise ValueError("current policy does not reproduce frozen rollout log probabilities")
            old_wdl = torch.tensor(ordered_values(record["wdl_probabilities"], encoded.action_ids,
                                                  name="old W/D/L probabilities"), device=current.device)
            wdl_error = float((scored.wdl_probabilities - old_wdl).abs().max())
            state["max_old_wdl_error"] = max(state["max_old_wdl_error"], wdl_error)
            if wdl_error > 1e-5:
                raise ValueError("current head does not reproduce frozen rollout W/D/L probabilities")
            state["verify_index"] = index + 1
            if on_boundary is not None and on_boundary(policy, optimizer, state) is False:
                raise _InterruptedBatch()
    state["old_logprobs_verified"] = True


def _round_step(policy, optimizer, batch, bc_batch, *, deadline, should_stop):
    optimizer.zero_grad(set_to_none=True)
    metrics = dict(ppo=0.0, wdl=0.0, bc=0.0, kl=0.0, rl_examples=len(batch), bc_examples=len(bc_batch))
    policy.train()
    for record in batch:
        _require_time(deadline, should_stop)
        ids, old, _, baseline = validate_decision(record)
        scored = policy.scores(_encoded(policy, record))
        logp = scored.log_probabilities
        old = old.to(logp.device)
        target, reward = terminal_target(record["outcome"], record["terminal_status"])
        chosen = ids.index(record["choice"])
        ppo = ppo_loss(logp[chosen], old[chosen], reward - baseline)
        wdl = half_brier(scored.wdl_probabilities[chosen], target)
        kl = policy_kl(old, logp).detach()
        loss = (ppo + PROTOCOL["losses"]["half_brier"] * wdl) / len(batch)
        if not bool(torch.isfinite(loss)):
            raise FloatingPointError("nonfinite combined PPO/WDL loss")
        loss.backward()
        for name, value in (("ppo", ppo), ("wdl", wdl), ("kl", kl)):
            metrics[name] += float(value.detach()) / len(batch)
    # No optimizer operation, including AdamW weight decay, is allowed above
    # the pre-update full-distribution KL cap.
    if metrics["kl"] > PROTOCOL["max_kl"]:
        optimizer.zero_grad(set_to_none=True)
        return dict(metrics, applied=False, reason="kl_limit")
    for record in bc_batch:
        _require_time(deadline, should_stop)
        encoded = _encoded(policy, record)
        loss = choice_loss(policy.scores(encoded).logits, encoded.action_ids, record["label"])
        (PROTOCOL["losses"]["bc"] * loss / len(bc_batch)).backward()
        metrics["bc"] += float(loss.detach()) / len(bc_batch)
    _require_time(deadline, should_stop)
    metrics["gradient_norm"] = check_gradients(policy)
    torch.nn.utils.clip_grad_norm_([p for p in policy.parameters() if p.requires_grad],
                                  PROTOCOL["optimizer"]["gradient_clip"], error_if_nonfinite=True)
    optimizer.step()
    optimizer.zero_grad(set_to_none=True)
    metrics["loss"] = metrics["ppo"] + .5 * metrics["wdl"] + .1 * metrics["bc"]
    return dict(metrics, applied=True)


def train_round(policy, records, bc_records, *, round_id, optimizer=None, state=None,
                deadline=None, should_stop=None, on_step=None, on_boundary=None):
    """Train two epochs of this round only; the runner enforces the 64-game gate."""
    if type(round_id) is not int or round_id not in range(1, PROTOCOL["rounds"] + 1):
        raise ValueError("round_id must be one of the four registered rounds")
    valid = eligible_decisions(records, round_id=round_id)
    selected = seeded_selection(valid, PROTOCOL["round_samples"], namespace=f"rl-round-{round_id}")
    if not selected:
        raise ValueError("PPO round has no valid selected decisions")
    bc = _bc_records(bc_records, round_id=round_id)
    policy.set_stage("policy")
    optimizer = optimizer if optimizer is not None else make_optimizer(policy)
    _validate_optimizer(policy, optimizer)
    state = _start_round_state(state, selected, bc, round_id)
    metrics = []
    if state["complete"]:
        return dict(status=state.get("status", "complete"), state=state, metrics=metrics)
    try:
        _verify_old_probabilities(policy, selected, state, deadline, should_stop, optimizer, on_boundary)
    except _InterruptedBatch:
        return dict(status=_stop_reason(deadline, should_stop) or "interrupted", state=state, metrics=metrics)
    while state["epoch"] < PROTOCOL["epochs"]:
        if on_boundary is not None and on_boundary(policy, optimizer, state) is False:
            return dict(status="interrupted", state=state, metrics=metrics)
        reason = _stop_reason(deadline, should_stop)
        if reason:
            return dict(status=reason, state=state, metrics=metrics)
        if state["global_updates"] >= PROTOCOL["max_policy_updates"]:
            state.update(complete=True, status="update_limit")
            break
        start = state["index"]
        batch = selected[start:start + PROTOCOL["rl_batch"]]
        if not batch:
            state["epoch"] += 1
            state["index"] = 0
            continue
        bc_batch = [bc[(state["bc_index"] + i) % len(bc)] for i in range(PROTOCOL["bc_batch"])]
        boundary_rng = rng_state()
        try:
            update = _round_step(policy, optimizer, batch, bc_batch, deadline=deadline, should_stop=should_stop)
        except _InterruptedBatch:
            optimizer.zero_grad(set_to_none=True)
            restore_rng(boundary_rng)
            return dict(status=_stop_reason(deadline, should_stop), state=state, metrics=metrics)
        except BaseException:
            optimizer.zero_grad(set_to_none=True)
            restore_rng(boundary_rng)
            raise
        if not update["applied"]:
            state.update(complete=True, status=update["reason"])
            metrics.append(update)
            break
        state["index"] += len(batch)
        state["bc_index"] += len(bc_batch)
        state["global_updates"] += 1
        state["round_updates"] += 1
        if state["index"] == len(selected):
            state["epoch"] += 1
            state["index"] = 0
        if state["epoch"] == PROTOCOL["epochs"]:
            state.update(complete=True, status="complete")
        update.update(global_update=state["global_updates"], round_update=state["round_updates"],
                      epoch=state["epoch"], index=state["index"])
        metrics.append(update)
        if on_step is not None and on_step(policy, optimizer, state, update) is False:
            return dict(status="interrupted", state=state, metrics=metrics)
    if state["epoch"] == PROTOCOL["epochs"]:
        state.update(complete=True, status="complete")
    return dict(status=state.get("status", "complete"), state=state, metrics=metrics)


def preflight(policy, train_records, *, max_samples=32, deadline=None, should_stop=None):
    """At most 32 EX-071 train decisions, with forward/backward but zero updates."""
    if not 1 <= max_samples <= 32:
        raise ValueError("preflight sample cap must be between 1 and 32")
    ordered = _bc_records(train_records, round_id="preflight")[:max_samples]
    policy.set_stage("policy")
    base_before = policy.base_fingerprints()
    before = policy.trainable_fingerprints()
    measurements, max_forward_difference, max_wdl_uniform_error = [], 0.0, 0.0
    initial_policy_parity = False
    if torch.cuda.is_initialized():
        torch.cuda.reset_peak_memory_stats()
    for index, record in enumerate(ordered):
        if _stop_reason(deadline, should_stop):
            break
        policy.zero_grad(set_to_none=True)
        start = time.perf_counter()
        encoded = _encoded(policy, record)
        if index == 0:
            policy.eval()
            with torch.no_grad():
                reference = policy.scores(encoded).logits.detach().clone()
                # Adding a W/D/L readout alone cannot change EX-071's policy.
                inherited = policy.policy.logits(encoded)
                if not torch.equal(reference, inherited):
                    raise ValueError("adding the W/D/L head changed initial action logits")
                initial_policy_parity = True
        policy.train()
        scored = policy.scores(encoded)
        uniform_error = float((scored.wdl_probabilities.detach() - 1 / 3).abs().max())
        max_wdl_uniform_error = max(max_wdl_uniform_error, uniform_error)
        if uniform_error != 0:
            raise ValueError("initial W/D/L head must predict exactly uniform outcomes")
        if index == 0:
            max_forward_difference = float((reference - scored.logits.detach()).abs().max())
            if max_forward_difference > 1e-5:
                raise ValueError("training and inference have different forward conditions")
        chosen = encoded.action_ids.index(record["label"])
        loss = choice_loss(scored.logits, encoded.action_ids, record["label"])
        loss = loss + .5 * half_brier(scored.wdl_probabilities[chosen], index % 3)
        loss.backward()
        norm = check_gradients(policy)
        policy.zero_grad(set_to_none=True)
        measurements.append(dict(sample_id=record["sample_id"], tokens=encoded.tokens,
                                 loss=float(loss.detach()), gradient_norm=norm,
                                 seconds=time.perf_counter() - start))
    base_unchanged = policy.base_fingerprints() == base_before
    weights_unchanged = policy.trainable_fingerprints() == before
    if not base_unchanged or not weights_unchanged:
        raise ValueError("preflight unexpectedly changed parameters")
    return dict(passed=len(measurements) == len(ordered), optimizer_updates=0,
                samples=len(measurements), planned_samples=len(ordered), measurements=measurements,
                base_unchanged=base_unchanged, trainable_unchanged=weights_unchanged,
                initial_policy_exact_parity=initial_policy_parity,
                max_initial_wdl_uniform_error=max_wdl_uniform_error,
                max_train_inference_logit_difference=max_forward_difference,
                max_allocated_bytes=torch.cuda.max_memory_allocated() if torch.cuda.is_initialized() else 0)


def extract_features(policy, records, *, max_samples=2048, deadline=None, should_stop=None):
    """Cache only selected-action representations from the final frozen policy."""
    if not 1 <= max_samples <= PROTOCOL["calibration"]["samples"]:
        raise ValueError("calibration representation cap exceeds the frozen limit")
    selected = seeded_selection(eligible_decisions(records), max_samples, namespace="calibration-features")
    policy.set_stage("inference")
    result = []
    with torch.no_grad():
        for record in selected:
            if _stop_reason(deadline, should_stop):
                # An incomplete representation set must never be silently
                # treated as a shorter completed calibration dataset.
                raise TimeoutError("calibration feature extraction did not finish")
            encoded = _encoded(policy, record)
            scored = policy.scores(encoded)
            chosen = encoded.action_ids.index(record["choice"])
            result.append(dict(decision_id=record["decision_id"], outcome=record["outcome"],
                               features=scored.features[chosen].detach().cpu().clone(),
                               input_sha256=encoded.input_sha256, choice=record["choice"]))
    return result


def _feature_digest(records):
    import hashlib
    digest = hashlib.sha256()
    for record in records:
        digest.update(json_sha256([record["decision_id"], record["outcome"]]).encode())
        features = record["features"]
        if (not isinstance(features, torch.Tensor) or features.dtype != torch.float32
                or features.ndim != 1 or not bool(torch.isfinite(features).all())):
            raise ValueError("invalid cached calibration representation")
        digest.update(features.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def train_head(policy, feature_records, *, optimizer=None, state=None, deadline=None,
               should_stop=None, on_step=None):
    """Fit only W/D/L; policy parameters are checked for bitwise invariance."""
    records = seeded_selection(feature_records, PROTOCOL["calibration"]["samples"],
                               namespace="calibration-features")
    if not records:
        raise ValueError("calibration has no chosen-action representations")
    data_sha = _feature_digest(records)
    if state is None:
        state = dict(stage="calibration", epoch=0, index=0, updates=0,
                     data_sha256=data_sha, selected_ids=[r["decision_id"] for r in records],
                     policy_fingerprints=policy.policy_fingerprints(), complete=False)
    if (state.get("stage") != "calibration" or state.get("data_sha256") != data_sha
            or state.get("selected_ids") != [r["decision_id"] for r in records]
            or state.get("policy_fingerprints") != policy.policy_fingerprints()
            or not 0 <= state.get("epoch", -1) <= PROTOCOL["calibration"]["epochs"]
            or not 0 <= state.get("index", -1) <= len(records)):
        raise ValueError("calibration resume cursor, data, or frozen policy changed")
    policy.set_stage("calibration")
    optimizer = optimizer if optimizer is not None else make_optimizer(policy, calibration=True)
    _validate_optimizer(policy, optimizer, calibration=True)
    metrics = []
    while state["epoch"] < PROTOCOL["calibration"]["epochs"] and not state["complete"]:
        reason = _stop_reason(deadline, should_stop)
        if reason:
            return dict(status=reason, state=state, metrics=metrics)
        batch = records[state["index"]:state["index"] + PROTOCOL["calibration"]["batch"]]
        if not batch:
            state["epoch"] += 1
            state["index"] = 0
            continue
        features = torch.stack([r["features"] for r in batch]).to(next(policy.wdl_head.parameters()).device)
        targets = torch.tensor([terminal_target(r["outcome"])[0] for r in batch], device=features.device)
        optimizer.zero_grad(set_to_none=True)
        probability = policy.wdl_head(features).float().softmax(-1)
        loss = half_brier(probability, targets).mean()
        loss.backward()
        norm = check_gradients(policy)
        reason = _stop_reason(deadline, should_stop)
        if reason:
            optimizer.zero_grad(set_to_none=True)
            return dict(status=reason, state=state, metrics=metrics)
        torch.nn.utils.clip_grad_norm_(policy.wdl_head.parameters(),
                                      PROTOCOL["optimizer"]["gradient_clip"], error_if_nonfinite=True)
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        state["index"] += len(batch)
        state["updates"] += 1
        if state["index"] == len(records):
            state["epoch"] += 1
            state["index"] = 0
        if state["epoch"] == PROTOCOL["calibration"]["epochs"]:
            state["complete"] = True
        update = dict(update=state["updates"], loss=float(loss.detach()), gradient_norm=norm,
                      examples=len(batch), epoch=state["epoch"], index=state["index"])
        metrics.append(update)
        if on_step is not None and on_step(policy, optimizer, state, update) is False:
            return dict(status="interrupted", state=state, metrics=metrics)
    if policy.policy_fingerprints() != state["policy_fingerprints"]:
        raise ValueError("head calibration changed the action policy")
    state.update(complete=True, status="complete")
    return dict(status="complete", state=state, metrics=metrics, policy_unchanged=True)
