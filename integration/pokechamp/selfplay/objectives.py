"""The frozen EX-072 objectives and rollout admission rules.

Candidate order is a part of the observation. Outcomes supervise only the
action actually submitted; an unsuccessful trajectory never acquires a label.
"""
from __future__ import annotations

import hashlib
import json
import math

import torch
import torch.nn.functional as F


SEED = 20261002
OUTCOMES = ("W", "D", "L")
REWARDS = (1.0, 0.5, 0.0)


def terminal_target(outcome, terminal_status="completed"):
    if terminal_status != "completed":
        raise ValueError("only a normal terminal battle has a W/D/L target")
    aliases = {"win": "W", "draw": "D", "loss": "L"}
    value = aliases.get(outcome, outcome)
    if value not in OUTCOMES:
        raise ValueError("terminal outcome must be W, D, or L")
    index = OUTCOMES.index(value)
    return index, REWARDS[index]


def _distribution(probabilities, *, classes=None):
    p = probabilities.float()
    if (p.ndim < 1 or classes is not None and p.shape[-1] != classes
            or not bool(torch.isfinite(p).all()) or bool((p < 0).any())
            or not torch.allclose(p.sum(-1), torch.ones_like(p.sum(-1)),
                                  atol=1e-5, rtol=0)):
        raise ValueError("invalid normalized probability distribution")
    return p


def half_brier(probabilities, targets):
    """One half the three-class squared error, without a batch reduction."""
    p = _distribution(probabilities, classes=3)
    target = torch.as_tensor(targets, device=p.device, dtype=torch.long)
    if bool(((target < 0) | (target > 2)).any()):
        raise ValueError("W/D/L target is outside [0, 2]")
    y = F.one_hot(target, num_classes=3).float()
    return 0.5 * (p - y).square().sum(-1)


def old_baseline(old_log_probabilities, old_wdl_probabilities):
    """E_pi_old[P_old(W|s,a) + .5 P_old(D|s,a)], always detached."""
    logp = old_log_probabilities.detach().float()
    wdl = _distribution(old_wdl_probabilities.detach(), classes=3)
    p = _distribution(logp.exp())
    if wdl.shape[:-1] != p.shape:
        raise ValueError("policy and W/D/L candidate dimensions differ")
    return (p * (wdl[..., 0] + 0.5 * wdl[..., 1])).sum(-1).detach()


def ppo_loss(new_log_probability, old_log_probability, advantage, clip=0.2):
    """Negative clipped surrogate. Neither old probabilities nor A has a gradient."""
    new = new_log_probability.float()
    old = old_log_probability.detach().float()
    a = torch.as_tensor(advantage, device=new.device, dtype=torch.float32).detach()
    ratio = (new - old).exp()
    if not bool(torch.isfinite(ratio).all()) or not bool(torch.isfinite(a).all()):
        raise FloatingPointError("nonfinite PPO ratio or advantage")
    return -torch.minimum(ratio * a, ratio.clamp(1 - clip, 1 + clip) * a)


def policy_kl(old_log_probabilities, new_log_probabilities):
    """Forward KL over the full candidate distribution, without a batch mean."""
    old = old_log_probabilities.detach().float()
    new = new_log_probabilities.float()
    if old.shape != new.shape or not bool(torch.isfinite(new).all()):
        raise ValueError("unaligned or nonfinite policy distributions")
    _distribution(new.exp())
    p = _distribution(old.exp())
    return (p * (old - new)).sum(-1)


def ordered_values(value, action_ids, *, name):
    if isinstance(value, dict):
        if tuple(value) != tuple(action_ids):
            raise ValueError(name + " changed candidate insertion order")
        return list(value.values())
    if not isinstance(value, (tuple, list)) or len(value) != len(action_ids):
        raise ValueError(name + " has a different candidate count")
    return list(value)


def validate_decision(record, *, round_id=None):
    """Validate a trainable, normal-terminal, actually chosen decision."""
    from ..imitation.model import input_body, json_sha256

    terminal_target(record.get("outcome"), record.get("terminal_status"))
    if not isinstance(record.get("decision_id"), str) or not record["decision_id"]:
        raise ValueError("rollout decision lacks a stable identity")
    if round_id is not None and record.get("round_id") != round_id:
        raise ValueError("PPO cannot reuse another round's decisions")
    body = input_body(record["input"])
    ids = tuple(body["questions"]["action"]["criteria"])
    if tuple(record.get("action_ids", ())) != ids:
        raise ValueError("rollout candidate order differs from the exact input")
    if len(ids) < 2:
        raise ValueError("automatic decisions are outside the learning denominator")
    if record.get("choice") not in ids or record.get("submitted") is False:
        raise ValueError("rollout is not an actually submitted legal choice")
    if record.get("input_sha256", json_sha256(body)) != json_sha256(body):
        raise ValueError("rollout input hash changed")
    old = torch.tensor(ordered_values(record["log_probabilities"], ids,
                                     name="old log probabilities"), dtype=torch.float32)
    wdl = torch.tensor(ordered_values(record["wdl_probabilities"], ids,
                                     name="old W/D/L probabilities"), dtype=torch.float32)
    if old.shape != (len(ids),) or not bool(torch.isfinite(old).all()):
        raise ValueError("invalid old policy log probabilities")
    if wdl.shape != (len(ids), 3):
        raise ValueError("invalid old W/D/L dimensions")
    baseline = float(old_baseline(old, wdl))
    if (not isinstance(record.get("baseline"), (int, float))
            or not math.isfinite(record["baseline"])
            or abs(record["baseline"] - baseline) > 1e-5):
        raise ValueError("recorded baseline differs from the frozen full distributions")
    return ids, old, wdl, baseline


def eligible_decisions(records, *, round_id=None):
    """Failures and automatic choices contribute no supervised decision."""
    result, seen = [], set()
    for record in records:
        if record.get("terminal_status") != "completed":
            continue
        if len(record.get("action_ids", ())) == 1:
            from ..imitation.model import input_body
            actual = tuple(input_body(record["input"])["questions"]["action"]["criteria"])
            if tuple(record["action_ids"]) != actual:
                raise ValueError("automatic action candidate order differs from its input")
            continue
        validate_decision(record, round_id=round_id)
        if record["decision_id"] in seen:
            raise ValueError("duplicate rollout decision identity")
        seen.add(record["decision_id"])
        result.append(record)
    return result


def seeded_selection(records, limit, *, namespace, seed=SEED, id_key="decision_id"):
    """Outcome-independent selection, stable under input-file reordering."""
    if limit < 0:
        raise ValueError("negative decision cap")
    identifiers = [r[id_key] for r in records]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate selection identity")
    def key(record):
        raw = json.dumps([seed, namespace, record[id_key]], separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest(), record[id_key]
    return sorted(records, key=key)[:limit]
