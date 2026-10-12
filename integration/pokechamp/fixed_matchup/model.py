"""Small structured policy/state-value network. No Qwen/legacy heads are loaded."""
from __future__ import annotations

import io
import math
import time

import torch
from torch import nn

from .config import MODEL, SCHEMA
from .storage import atomic_bytes, digest, sha


class Encoder:
    def __init__(self, vocabulary):
        if vocabulary != sorted(set(vocabulary)):
            raise ValueError("vocabulary must be frozen, unique and sorted")
        self.vocabulary = vocabulary
        self.ids = {word: i + 1 for i, word in enumerate(vocabulary)}

    def token(self, token):
        if set(token) != {"categories", "numbers"}:
            raise ValueError("unexpected token field")
        numbers = token["numbers"]
        if len(numbers) != MODEL["numeric"] or any(not math.isfinite(n) for n in numbers):
            raise ValueError("invalid numeric token")
        categories = token["categories"]
        if not categories or len(categories) > 12:
            raise ValueError("invalid category count")
        try:
            ids = [self.ids[word] for word in categories]
        except KeyError as exc:
            raise ValueError(f"unknown category {exc}; no silent UNK") from exc
        return ids + [0] * (12 - len(ids)), numbers

    def collate(self, observations, device):
        if not observations:
            raise ValueError("empty batch")
        max_state = max(len(o["tokens"]) for o in observations)
        max_actions = max(1, max(len(o["actions"]) for o in observations))
        if not 0 < max_state <= MODEL["max_tokens"] or max_actions > 13:
            raise ValueError("observation/action bound exceeded")
        # Pack validated Python rows once per tensor instead of issuing two tiny
        # tensor allocations and indexed writes for every state/action token.
        cat, num, mask, acat, anum, legal = [], [], [], [], [], []
        counts = []
        for obs in observations:
            if set(obs) != {"schema", "tokens", "actions"} or obs["schema"] != SCHEMA:
                raise ValueError("observation schema mismatch/private metadata")
            state = [self.token(row) for row in obs["tokens"]]
            ids = [a["id"] for a in obs["actions"]]
            if len(set(ids)) != len(ids):
                raise ValueError("duplicate action")
            actions = []
            for row in obs["actions"]:
                if set(row) != {"id", "command", "token"}:
                    raise ValueError("unexpected action field")
                actions.append(self.token(row["token"]))
            state_padding, action_padding = max_state - len(state), max_actions - len(actions)
            cat.append([r[0] for r in state] + [[0] * 12] * state_padding)
            num.append([r[1] for r in state] + [[0.] * MODEL["numeric"]] * state_padding)
            mask.append([False] * len(state) + [True] * state_padding)
            acat.append([r[0] for r in actions] + [[0] * 12] * action_padding)
            anum.append([r[1] for r in actions] + [[0.] * MODEL["numeric"]] * action_padding)
            legal.append([True] * len(actions) + [False] * action_padding)
            counts.append(len(ids))
        cat, num, mask, acat, anum, legal = (
            torch.tensor(rows, dtype=dtype) for rows, dtype in zip(
                (cat, num, mask, acat, anum, legal),
                (torch.long, torch.get_default_dtype(), torch.bool,
                 torch.long, torch.get_default_dtype(), torch.bool)))
        return tuple(t.to(device) for t in (cat, num, mask, acat, anum, legal)), counts


class Policy(nn.Module):
    def __init__(self, vocabulary):
        super().__init__()
        self.encoder = Encoder(vocabulary)
        dim = MODEL["hidden"]
        self.embedding = nn.Embedding(len(vocabulary) + 1, dim, padding_idx=0)
        self.numeric = nn.Linear(MODEL["numeric"], dim)
        layer = nn.TransformerEncoderLayer(dim, MODEL["heads"], MODEL["feedforward"],
                                           dropout=0, batch_first=True, norm_first=True)
        self.transformer = nn.TransformerEncoder(layer, MODEL["layers"], enable_nested_tensor=False)
        self.policy_head = nn.Sequential(nn.Linear(2 * dim, dim), nn.Tanh(), nn.Linear(dim, 1))
        self.value_head = nn.Sequential(nn.Linear(dim, dim), nn.Tanh(), nn.Linear(dim, 1), nn.Tanh())

    @property
    def device(self):
        return next(self.parameters()).device

    def embed(self, categories, numbers):
        denominator = (categories != 0).sum(-1, keepdim=True).clamp_min(1)
        return self.embedding(categories).sum(-2) / denominator + self.numeric(numbers)

    def forward(self, batch):
        cat, num, mask, acat, anum, legal = batch
        state = self.transformer(self.embed(cat, num), src_key_padding_mask=mask)
        valid = (~mask).unsqueeze(-1)
        pooled = (state * valid).sum(1) / valid.sum(1)
        actions = self.embed(acat, anum)
        context = pooled.unsqueeze(1).expand(-1, actions.shape[1], -1)
        logits = self.policy_head(torch.cat((context, actions), -1)).squeeze(-1)
        # Waiting perspectives still require a state value; do not softmax an all-masked row.
        logits = logits.masked_fill(~legal, -1e9)
        return logits, self.value_head(pooled).squeeze(-1)

    @torch.no_grad()
    def evaluate_batch(self, observations):
        self.eval()
        batch, counts = self.encoder.collate(observations, self.device)
        logits, values = self(batch)
        if not torch.isfinite(logits).all() or not torch.isfinite(values).all():
            raise FloatingPointError("nonfinite inference")
        return [dict(policy=logits[i, :count].softmax(-1).cpu().tolist() if count else [],
                     value=float(values[i].cpu())) for i, count in enumerate(counts)]

    def payload(self):
        return dict(schema=SCHEMA, config=MODEL, vocabulary=self.encoder.vocabulary,
                    weights={k: v.detach().cpu().clone() for k, v in self.state_dict().items()})

    def save(self, path):
        stream = io.BytesIO()
        torch.save(self.payload(), stream)
        atomic_bytes(path, stream.getvalue(), exclusive=True)
        return sha(path)

    @classmethod
    def load(cls, path, device="cpu"):
        payload = torch.load(path, map_location="cpu", weights_only=True)
        if payload["schema"] != SCHEMA or payload["config"] != MODEL:
            raise ValueError("checkpoint architecture changed")
        model = cls(payload["vocabulary"])
        model.load_state_dict(payload["weights"], strict=True)
        for parameter in model.parameters():
            if not torch.isfinite(parameter).all():
                raise FloatingPointError("nonfinite checkpoint")
        return model.to(device).eval()


def learn(policy, optimizer, rows, *, generator, check=lambda: None, batch_size=256, epochs=2, max_steps=64):
    """Fresh bounded passes through replay; rollout policies stay frozen elsewhere."""
    if not rows:
        raise ValueError("no normal-terminal training records")
    policy.train()
    metrics, started = [], time.monotonic()
    for _ in range(epochs):
        order = torch.randperm(len(rows), generator=generator).tolist()
        for offset in range(0, len(order), batch_size):
            check()
            selected = [rows[i] for i in order[offset:offset + batch_size]]
            observations = [r["observation"] for r in selected]
            batch, counts = policy.encoder.collate(observations, policy.device)
            targets = torch.zeros_like(batch[-1], dtype=torch.float32)
            z, enabled = [], []
            for i, (row, count) in enumerate(zip(selected, counts)):
                if row["terminal_status"] != "completed" or row["z"] not in (-1, 0, 1):
                    raise ValueError("nonterminal/invalid value label")
                if row["observation_hash"] != digest(row["observation"]):
                    raise ValueError("training observation altered")
                probs = row["target"]
                if (len(probs) != count or not count or any(not math.isfinite(p) or p < 0 for p in probs)
                        or abs(sum(probs) - 1) > 1e-6):
                    raise ValueError("misaligned visit target")
                targets[i, :count] = torch.tensor(probs, device=policy.device)
                z.append(row["z"])
                enabled.append(count > 1)
            optimizer.zero_grad(set_to_none=True)
            logits, values = policy(batch)
            losses = -(targets * logits.log_softmax(-1)).sum(-1)
            chosen = torch.tensor(enabled, device=policy.device)
            policy_loss = losses[chosen].mean() if chosen.any() else logits.sum() * 0
            value_loss = (values - torch.tensor(z, dtype=torch.float32, device=policy.device)).square().mean()
            loss = policy_loss + value_loss
            if not torch.isfinite(loss):
                raise FloatingPointError("nonfinite loss")
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0, error_if_nonfinite=True)
            optimizer.step()
            metrics.append(dict(policy=float(policy_loss.detach()), value=float(value_loss.detach()),
                                gradient_norm=float(norm), samples=len(selected)))
            if len(metrics) >= max_steps:
                break
        if len(metrics) >= max_steps:
            break
    policy.eval()
    return dict(steps=len(metrics), metrics=metrics, seconds=time.monotonic() - started)
