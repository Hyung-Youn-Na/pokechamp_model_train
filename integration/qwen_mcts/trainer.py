"""One training round of the learner adapter/heads (runs inside the train GPU server)."""
from __future__ import annotations

import random
import time

import numpy as np
import torch

from .config import PROTOCOL
from .network import TRAIN
from .storage import seed


def optimizer_for(net):
    t = PROTOCOL["train"]
    groups = [{"params": net.adapter_parameters(TRAIN), "lr": t["lr_lora"]},
              {"params": list(net.heads[TRAIN].parameters()), "lr": t["lr_head"]}]
    for group in groups:
        group["initial_lr"] = group["lr"]
    return torch.optim.AdamW(groups, betas=tuple(t["betas"]), weight_decay=t["weight_decay"])


def lr_factor(step):
    return min(1.0, (step + 1) / PROTOCOL["train"]["warmup"])


def batch_loss(net, static_ids, rows, *, branch_hidden, pad_id):
    """rows: dict(prefix, ids, readout, pi=[pi1|None, pi2|None], z|None). Policy CE only for sides with >=2
    candidates; value MSE only for rows of normally terminated games."""
    groups = {}
    for row in rows:
        groups.setdefault(row["prefix"], []).append(row)
    outputs = net.branch_rows(TRAIN, static_ids, {k: [(r["ids"], r["readout"]) for r in v] for k, v in groups.items()},
                              pad_id=pad_id, branch_hidden=branch_hidden, probabilities=False)
    policy_terms, value_terms = [], []
    for prefix, members in groups.items():
        values, logits = outputs[prefix]
        for k, row in enumerate(members):
            for side, target in enumerate(row["pi"]):
                if target is None or len(target) < 2:
                    continue
                side_logits = logits[k][side]
                if side_logits.shape[0] != len(target):
                    raise ValueError("policy target/candidate misalignment")
                t = torch.tensor(target, dtype=torch.float32, device=side_logits.device)
                policy_terms.append(-(t * torch.log_softmax(side_logits.float(), -1)).sum())
            if row["z"] is not None:
                value_terms.append((values[k].float() - float(row["z"])) ** 2)
    zero = torch.zeros((), device=net.device)
    policy = torch.stack(policy_terms).mean() if policy_terms else zero
    value = torch.stack(value_terms).mean() if value_terms else zero
    loss = policy + PROTOCOL["train"]["value_weight"] * value
    return loss, policy, value, len(policy_terms), len(value_terms)


def train_round(net, optimizer, rows, *, round_id, global_step, static_ids, branch_hidden, pad_id, steps=None,
                check=lambda: None):
    t = PROTOCOL["train"]
    steps = t["steps"] if steps is None else steps
    if not rows:
        raise ValueError("empty replay")
    generator = torch.Generator().manual_seed(seed("replay-order", round_id))
    parameters = net.adapter_parameters(TRAIN) + list(net.heads[TRAIN].parameters())
    net.use(TRAIN)
    net.lm.train()
    net.heads[TRAIN].train()
    order, metrics, started = [], [], time.monotonic()
    try:
        for _ in range(steps):
            check()
            if len(order) < t["batch"]:
                order += torch.randperm(len(rows), generator=generator).tolist()
            batch, order = [rows[i] for i in order[:t["batch"]]], order[t["batch"]:]
            for group in optimizer.param_groups:
                group["lr"] = group["initial_lr"] * lr_factor(global_step)
            optimizer.zero_grad(set_to_none=True)
            loss, policy, value, n_policy, n_value = batch_loss(net, static_ids, batch, branch_hidden=branch_hidden, pad_id=pad_id)
            if not torch.isfinite(loss):
                raise FloatingPointError("nonfinite loss")
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(parameters, t["clip"], error_if_nonfinite=True)
            optimizer.step()
            global_step += 1
            metrics.append(dict(step=global_step, loss=float(loss.detach()), policy=float(policy.detach()),
                                value=float(value.detach()), policy_terms=n_policy, value_terms=n_value,
                                gradient_norm=float(norm), lr_lora=optimizer.param_groups[0]["lr"]))
    finally:
        net.lm.eval()
        net.heads[TRAIN].eval()
    return dict(metrics=metrics, global_step=global_step, seconds=time.monotonic() - started, rows=len(rows))


def rng_state():
    return dict(python=random.getstate(), numpy=np.random.get_state(), torch=torch.get_rng_state(),
                cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None)


def set_rng_state(state):
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    # map_location may have moved the saved ByteTensors to the GPU; RNG setters need CPU ByteTensors.
    torch.set_rng_state(state["torch"].cpu())
    if state["cuda"] is not None:
        torch.cuda.set_rng_state_all([s.cpu() for s in state["cuda"]])
