"""Bounded EX-073 optimization with checkpoints only at completed steps.

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
                               )
from .config import PROTOCOL, SEED
from ..selfplay.model import encode_input
from . import distributed as collective
from ..selfplay.objectives import (eligible_decisions, half_brier, ordered_values, policy_kl,
                         ppo_loss, seeded_selection as _selection, terminal_target, validate_decision)


def seeded_selection(records, limit, **kwargs):
    return _selection(records, limit, seed=SEED, **kwargs)


def rng_state():
    import random
    import numpy as np
    return dict(python=random.getstate(), numpy=np.random.get_state(),
                torch=torch.get_rng_state(), cuda=(torch.cuda.get_rng_state()
                if torch.cuda.is_initialized() else None))


def restore_rng(state):
    import random
    import numpy as np
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"])
    if state["cuda"] is not None:
        torch.cuda.set_rng_state(state["cuda"])


class _InterruptedBatch(Exception):
    pass


def _stop_reason(deadline, should_stop):
    if collective.any_rank(should_stop is not None and should_stop()):
        return "interrupted"
    if collective.any_rank(deadline is not None and time.time() >= deadline):
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
            raise ValueError("optimizer differs from the frozen EX-073 settings")


def training_state(policy, optimizer, cursor):
    """Complete optimizer-boundary payload for the runner's atomic checkpoint."""
    if any(p.grad is not None for p in policy.parameters()):
        raise ValueError("checkpoint requested inside an unfinished optimizer step")
    return dict(version="ex073-training-v1", optimizer=copy.deepcopy(optimizer.state_dict()),
                rank_rng=collective.gather(rng_state()), world_size=collective.world_size(), cursor=copy.deepcopy(cursor),
                sampling_rng=collective.gather(copy.deepcopy(policy.sampling_generator.getstate())),
                parameter_fingerprints=policy.trainable_fingerprints(),
                protocol_sha256=json_sha256(PROTOCOL))


def restore_training_state(policy, optimizer, saved):
    if (saved.get("version") != "ex073-training-v1"
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
    if saved["world_size"] != collective.world_size():
        raise ValueError("checkpoint rank count differs")
    restore_rng(saved["rank_rng"][collective.rank()])
    policy.sampling_generator.setstate(saved["sampling_rng"][collective.rank()])
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
    """Audit every admitted decision once across four frozen replicas."""
    if state["old_logprobs_verified"]:
        return
    if state["round_updates"]:
        raise ValueError("optimization began before the old-policy audit")
    policy.eval()
    with torch.no_grad():
        while state["verify_index"] < len(selected):
            _require_time(deadline, should_stop)
            start = state["verify_index"]
            index = start + collective.rank()
            error = None
            logp_error = wdl_error = 0.0
            try:
                if index < len(selected):
                    record = selected[index]
                    encoded = _encoded(policy, record)
                    scored = policy.scores(encoded)
                    old = torch.tensor(ordered_values(record["log_probabilities"], encoded.action_ids,
                        name="old log probabilities"), device=scored.logits.device)
                    logp_error = float((scored.log_probabilities - old).abs().max())
                    old_wdl = torch.tensor(ordered_values(record["wdl_probabilities"], encoded.action_ids,
                        name="old W/D/L probabilities"), device=scored.logits.device)
                    wdl_error = float((scored.wdl_probabilities - old_wdl).abs().max())
                    if logp_error > 1e-5 or wdl_error > 1e-5:
                        raise ValueError("frozen rollout log probability/WDL reproduction failed")
            except Exception as exc:
                error = exc
            collective.raise_if_failed(error)
            errors = collective.gather((logp_error, wdl_error))
            state["max_old_logprob_error"] = max(state["max_old_logprob_error"], *(e[0] for e in errors))
            state["max_old_wdl_error"] = max(state["max_old_wdl_error"], *(e[1] for e in errors))
            state["verify_index"] = min(start + collective.world_size(), len(selected))
            if collective.any_rank(on_boundary is not None and on_boundary(policy, optimizer, state) is False):
                raise _InterruptedBatch()
    state["old_logprobs_verified"] = True


def _apply_step(policy, optimizer):
    torch.nn.utils.clip_grad_norm_([p for p in policy.parameters() if p.requires_grad],
                                  PROTOCOL["optimizer"]["gradient_clip"], error_if_nonfinite=True)
    optimizer.step()
    optimizer.zero_grad(set_to_none=True)


def _numeric_difference(name, actual, reference, *, atol, rtol):
    """Bounded numerical failure evidence; never serialize a full tensor."""
    actual, reference = actual.detach().cpu().flatten(), reference.detach().cpu().flatten()
    difference = (actual - reference).abs()
    violations = ~torch.isclose(actual, reference, atol=atol, rtol=rtol)
    indices = torch.nonzero(violations).flatten()
    return dict(parameter=name, max_absolute_error=float(difference.max()),
                violation_count=int(indices.numel()), elements=actual.numel(), atol=atol, rtol=rtol,
                examples=[dict(flat_index=int(index), actual=float(actual[index]),
                               reference=float(reference[index]),
                               absolute_error=float(difference[index]),
                               allowed_error=float(atol + rtol * reference[index].abs()))
                          for index in indices[:3]])


def _round_step(policy, optimizer, batch, bc_batch, *, deadline, should_stop,
                reduce=True, apply=True):
    optimizer.zero_grad(set_to_none=True)
    metrics = dict(ppo=0.0, wdl=0.0, bc=0.0, kl=0.0,
                   rl_examples=len(batch), bc_examples=len(bc_batch))
    policy.train()
    shard = collective.local_slice if reduce else lambda value: value
    error = None
    try:
        for record in shard(batch):
            if (deadline is not None and time.time() >= deadline) or (should_stop and should_stop()):
                raise _InterruptedBatch()
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
    except Exception as exc:
        error = exc
    if reduce:
        if collective.any_rank(isinstance(error, _InterruptedBatch)):
            optimizer.zero_grad(set_to_none=True)
            raise _InterruptedBatch()
        collective.raise_if_failed(error)
        values = collective.sum_values([metrics[k] for k in ("ppo", "wdl", "kl")])
        metrics.update(zip(("ppo", "wdl", "kl"), values))
    elif error is not None:
        raise error
    if metrics["kl"] >= PROTOCOL["max_kl"]:
        optimizer.zero_grad(set_to_none=True)
        return dict(metrics, applied=False, reason="kl_limit")
    error = None
    try:
        for record in shard(bc_batch):
            encoded = _encoded(policy, record)
            loss = choice_loss(policy.scores(encoded).logits, encoded.action_ids, record["label"])
            (PROTOCOL["losses"]["bc"] * loss / len(bc_batch)).backward()
            metrics["bc"] += float(loss.detach()) / len(bc_batch)
    except Exception as exc:
        error = exc
    if reduce:
        collective.raise_if_failed(error)
        metrics["bc"] = collective.sum_values([metrics["bc"]])[0]
        collective.sum_gradients(p for p in policy.parameters() if p.requires_grad)
        _require_time(deadline, should_stop)
    elif error is not None:
        raise error
    metrics["gradient_norm"] = (collective.checked(check_gradients, policy)
                                if reduce else check_gradients(policy))
    if not apply:
        return dict(metrics, applied=False, reason="gradient_probe")
    if reduce:
        collective.checked(_apply_step, policy, optimizer)
    else:
        _apply_step(policy, optimizer)
    metrics["loss"] = metrics["ppo"] + .5 * metrics["wdl"] + .1 * metrics["bc"]
    return dict(metrics, applied=True)


def train_round(policy, records, bc_records, *, round_id, optimizer=None, state=None,
                deadline=None, should_stop=None, on_step=None, on_boundary=None):
    """Train two epochs of this round only; the runner enforces the 64-game gate."""
    if type(round_id) is not int or round_id not in range(1, PROTOCOL["rounds"] + 1):
        raise ValueError("round_id outside registered rounds")
    valid = eligible_decisions(records, round_id=round_id)
    selected = seeded_selection(valid, PROTOCOL["round_samples"], namespace=f"rl-round-{round_id}")
    if not selected:
        raise ValueError("PPO round has no valid selected decisions")
    bc = _bc_records(bc_records, round_id=round_id)
    policy.set_stage("policy")
    optimizer = optimizer if optimizer is not None else make_optimizer(policy)
    _validate_optimizer(policy, optimizer)
    collective.assert_same(policy.trainable_fingerprints())
    state = _start_round_state(state, selected, bc, round_id)
    collective.assert_same(state, "round cursor")
    metrics = []
    if state["complete"]:
        return dict(status=state.get("status", "complete"), state=state, metrics=metrics)
    try:
        _verify_old_probabilities(policy, selected, state, deadline, should_stop, optimizer, on_boundary)
    except _InterruptedBatch:
        return dict(status=_stop_reason(deadline, should_stop) or "interrupted", state=state, metrics=metrics)
    while state["epoch"] < PROTOCOL["epochs"]:
        if collective.any_rank(on_boundary is not None and on_boundary(policy, optimizer, state) is False):
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
        if collective.any_rank(on_step is not None and on_step(policy, optimizer, state, update) is False):
            return dict(status="interrupted", state=state, metrics=metrics)
    if state["epoch"] == PROTOCOL["epochs"]:
        state.update(complete=True, status="complete")
    return dict(status=state.get("status", "complete"), state=state, metrics=metrics)


def preflight(policy, train_records, *, max_samples=16, deadline=None, should_stop=None):
    """Collective real-input 1-vs-4 numerical gate; restore every original weight/RNG.

    Each rank computes a single-device reference before the same global batch is
    sharded. Probe AdamW steps are discarded and never count as training updates.
    """
    if collective.world_size() != 4:
        raise ValueError("GPU preflight requires four initialized ranks")
    if max_samples != 16:
        raise ValueError("preflight uses the frozen global RL16/BC4 batch")
    policy.set_stage("policy")
    _require_time(deadline, should_stop)
    collective.assert_same(policy.trainable_fingerprints())
    collective.assert_same(policy.base_fingerprints(), "frozen base")
    original = policy.snapshot_weights()
    original_fingerprints = policy.trainable_fingerprints()
    original_rng = rng_state()
    base_before = policy.base_fingerprints()
    bc = _bc_records(train_records, round_id="preflight")[:16]
    if len(bc) != 16:
        raise ValueError("preflight needs sixteen distinct BC train inputs")
    measurements, records = [], []
    max_logp, max_wdl = 0.0, 0.0
    if torch.cuda.is_initialized():
        torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    report = None
    try:
        policy.eval()
        for index, record in enumerate(bc):
            _require_time(deadline, should_stop)
            tick = time.perf_counter()
            def score_replica():
                encoded = _encoded(policy, record)
                with torch.no_grad():
                    score = policy.scores(encoded)
                    return encoded, score.log_probabilities.detach().cpu(), score.wdl_probabilities.detach().cpu()
            encoded, logp, wdl = collective.checked(score_replica)
            replicas = collective.gather((logp.tolist(), wdl.tolist()))
            for other_logp, other_wdl in replicas:
                max_logp = max(max_logp, float((logp - torch.tensor(other_logp)).abs().max()))
                max_wdl = max(max_wdl, float((wdl - torch.tensor(other_wdl)).abs().max()))
            if max_logp > 1e-5 or max_wdl > 1e-5:
                raise ValueError("four replica output mismatch at frozen tolerance 1e-5")
            ids = encoded.action_ids
            records.append(dict(decision_id="preflight-" + str(index), input=record["input"],
                input_sha256=encoded.input_sha256, action_ids=list(ids), choice=record["label"],
                log_probabilities=dict(zip(ids, logp.tolist())),
                wdl_probabilities=dict(zip(ids, wdl.tolist())),
                baseline=float((logp.exp() * (wdl[:, 0] + .5 * wdl[:, 1])).sum()),
                outcome=("W", "D", "L")[index % 3], terminal_status="completed",
                round_id=1, submitted=True))
            measurements.append(dict(sample_id=record["sample_id"], tokens=encoded.tokens,
                                     seconds=time.perf_counter() - tick))
        trainable = [(n, p) for n, p in policy.named_parameters() if p.requires_grad]
        optimizer = make_optimizer(policy)
        collective.checked(_round_step, policy, optimizer, records, bc[:4], deadline=deadline,
                           should_stop=should_stop, reduce=False, apply=False)
        reference_grad = {n: p.grad.detach().cpu().clone() for n, p in trainable}
        collective.checked(_apply_step, policy, optimizer)
        reference_weights = policy.snapshot_weights()
        policy.load_weights(original)
        optimizer = make_optimizer(policy)
        _round_step(policy, optimizer, records, bc[:4], deadline=deadline,
                    should_stop=should_stop, apply=False)
        max_grad_error = 0.0
        error = None
        for name, parameter in trainable:
            actual = parameter.grad.detach().cpu()
            max_grad_error = max(max_grad_error, float((actual-reference_grad[name]).abs().max()))
            if error is None and not torch.allclose(actual, reference_grad[name], atol=1e-5, rtol=1e-4):
                error = ValueError("four-rank gradient differs: " + repr(_numeric_difference(
                    name, actual, reference_grad[name], atol=1e-5, rtol=1e-4)))
        collective.raise_if_failed(error)
        collective.checked(_apply_step, policy, optimizer)
        actual_weights = policy.snapshot_weights()
        max_update_error = 0.0
        error = None
        for name, value in actual_weights.items():
            max_update_error = max(max_update_error, float((value-reference_weights[name]).abs().max()))
            if error is None and not torch.allclose(value, reference_weights[name], atol=1e-6, rtol=1e-5):
                error = ValueError("four-rank AdamW update differs: " + repr(_numeric_difference(
                    name, value, reference_weights[name], atol=1e-6, rtol=1e-5)))
        collective.raise_if_failed(error)
        changes = {kind: any(not torch.equal(value, original[name])
                    for name, value in actual_weights.items() if predicate(name))
                   for kind, predicate in {
                       "lora": lambda n: "lora_" in n,
                       "action_head": lambda n: n.startswith("policy.model.head."),
                       "wdl_head": lambda n: n.startswith("wdl_head.")}.items()}
        error = (ValueError("probe did not update LoRA/heads only")
                 if not all(changes.values()) or policy.base_fingerprints() != base_before else None)
        collective.raise_if_failed(error)
        collective.assert_same(policy.trainable_fingerprints(), "post-update weights")
        report = dict(passed=True, world_size=4, optimizer_updates=0, probe_updates_discarded=2,
                    max_log_probability_error=max_logp, max_wdl_error=max_wdl,
                    max_gradient_error=max_grad_error, max_update_error=max_update_error,
                    base_unchanged=True, changed=changes, measurements=measurements,
                    seconds=time.perf_counter()-start,
                    max_allocated_bytes=torch.cuda.max_memory_allocated() if torch.cuda.is_initialized() else 0,
                    tolerances=dict(logp_wdl_atol=1e-5, gradient_atol=1e-5,
                                    gradient_rtol=1e-4, update_atol=1e-6, update_rtol=1e-5))
        return report
    finally:
        import sys
        import numpy as np
        policy.zero_grad(set_to_none=True)
        policy.load_weights(original)
        restore_rng(original_rng)
        restored = rng_state()
        weights_restored = policy.trainable_fingerprints() == original_fingerprints
        rng_restored = (restored["python"] == original_rng["python"]
            and restored["numpy"][0] == original_rng["numpy"][0]
            and np.array_equal(restored["numpy"][1], original_rng["numpy"][1])
            and restored["numpy"][2:] == original_rng["numpy"][2:]
            and torch.equal(restored["torch"], original_rng["torch"])
            and (restored["cuda"] is None and original_rng["cuda"] is None
                 or restored["cuda"] is not None and original_rng["cuda"] is not None
                 and torch.equal(restored["cuda"], original_rng["cuda"])))
        receipt = dict(weights_restored=weights_restored, rng_restored=rng_restored,
                       restored_fingerprint_sha256=json_sha256(original_fingerprints))
        if report is not None:
            report.update(receipt)
        if sys.exception() is not None:
            sys.exception().add_note("preflight restoration: " + repr(receipt))
        if not weights_restored or not rng_restored:
            raise RuntimeError("preflight restoration verification failed: " + repr(receipt))


def extract_features(policy, records, *, max_samples=2048, deadline=None, should_stop=None):
    """Cache only selected-action representations from the final frozen policy."""
    if not 1 <= max_samples <= PROTOCOL["calibration"]["samples"]:
        raise ValueError("calibration representation cap exceeds the frozen limit")
    selected = seeded_selection(eligible_decisions(records), max_samples, namespace="calibration-features")
    policy.set_stage("inference")
    collective.assert_same([r["decision_id"] for r in selected], "calibration feature selection")
    collective.assert_same(policy.trainable_fingerprints(), "calibration policy")
    result = []
    with torch.no_grad():
        for start in range(0, len(selected), collective.world_size()):
            if _stop_reason(deadline, should_stop):
                raise TimeoutError("calibration feature extraction did not finish")
            def extract_one():
                index = start + collective.rank()
                if index >= len(selected):
                    return None
                record = selected[index]
                encoded = _encoded(policy, record)
                scored = policy.scores(encoded)
                chosen = encoded.action_ids.index(record["choice"])
                return dict(decision_id=record["decision_id"], outcome=record["outcome"],
                            features=scored.features[chosen].detach().cpu().clone(),
                            input_sha256=encoded.input_sha256, choice=record["choice"])
            feature = collective.checked(extract_one)
            result.extend(item for item in collective.gather(feature) if item is not None)

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
    collective.assert_same(state, "calibration cursor")
    collective.assert_same(policy.trainable_fingerprints(), "calibration weights")
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
        optimizer.zero_grad(set_to_none=True)
        def local_backward():
            shard = collective.local_slice(batch)
            if not shard:
                return 0.0
            features = torch.stack([r["features"] for r in shard]).to(next(policy.wdl_head.parameters()).device)
            targets = torch.tensor([terminal_target(r["outcome"])[0] for r in shard], device=features.device)
            probability = policy.wdl_head(features).float().softmax(-1)
            loss = half_brier(probability, targets).sum() / len(batch)
            loss.backward()
            return float(loss.detach())
        local_loss = collective.checked(local_backward)
        collective.sum_gradients(policy.wdl_head.parameters())
        loss_value = collective.sum_values([local_loss])[0]
        norm = collective.checked(check_gradients, policy)
        reason = _stop_reason(deadline, should_stop)
        if reason:
            optimizer.zero_grad(set_to_none=True)
            return dict(status=reason, state=state, metrics=metrics)
        collective.checked(_apply_step, policy, optimizer)
        state["index"] += len(batch)
        state["updates"] += 1
        if state["index"] == len(records):
            state["epoch"] += 1
            state["index"] = 0
        if state["epoch"] == PROTOCOL["calibration"]["epochs"]:
            state["complete"] = True
        update = dict(update=state["updates"], loss=loss_value, gradient_norm=norm,
                      examples=len(batch), epoch=state["epoch"], index=state["index"])
        metrics.append(update)
        if collective.any_rank(on_step is not None and on_step(policy, optimizer, state, update) is False):
            return dict(status="interrupted", state=state, metrics=metrics)
    if policy.policy_fingerprints() != state["policy_fingerprints"]:
        raise ValueError("head calibration changed the action policy")
    state.update(complete=True, status="complete")
    return dict(status="complete", state=state, metrics=metrics, policy_unchanged=True)
