"""One scoring path for EX-118/121 evaluation and EX-119/120/122 serving: raw logits -> clamped temperature -> probs.

laya's `Agent` rounds published probabilities to 4 decimals, so twelve of them can miss 1.0 by
more than the EX-071 player's tolerance and the NLL of a near-zero option is undefined. This path
reuses laya's own encoding (`build_sequence` via `encode_item`) and forward, in fp32, and applies the
checkpoint temperature the way `Agent` does (`clamp_temperature`, `temp_bucket`).
"""
from __future__ import annotations
import math

import torch
from laya.common import QTYPES, clamp_temperature, collate_items, temp_bucket
from laya.train import _forward, encode_item, encode_state, load_checkpoint, to_internal

from . import config as c
from .compact import render


class Policy:
    """`head_limit`/`renderer` default to v1 (EX-118); EX-121 passes the v2 budget and a v2 renderer."""

    def __init__(self, checkpoint, device='cuda', head_limit=c.HEAD_LIMIT, renderer=render, token_limit=None):
        self.model, self.tok, self.cfg = load_checkpoint(str(checkpoint))
        self.device = torch.device(device)
        self.model.to(self.device).eval()
        trained = (self.cfg.get('training') or {})
        if token_limit is None:   # D-198: an EX-142 checkpoint is scored at the 2048 tokens it was trained with
            token_limit = c.V6H_TOKEN_LIMIT if trained.get('ex142') else c.TOKEN_LIMIT
        # The experiment budgets, not the base checkpoint's own head_max_len (192), which would cut questions.
        self.max_len, self.head_max_len = token_limit, head_limit
        self.renderer = renderer
        if any(trained.get(k) for k in ('ex118', 'ex121', 'ex128', 'ex130', 'ex141', 'ex142')) and \
                (self.cfg['max_len'], self.cfg['head_max_len']) != (token_limit, head_limit):
            raise ValueError('checkpoint was trained with other token budgets')

    def temperature(self, k):
        qtype = QTYPES['choice']
        by_options = self.cfg.get('temperature_by_options') or {}
        bucket = temp_bucket(qtype, k)
        raw = by_options[bucket] if bucket in by_options else self.cfg.get('temperature', [1.0, 1.0, 1.0])[qtype]
        return clamp_temperature(float(raw))

    def item(self, state, question):
        q = to_internal('action', question)
        k = len(question['criteria'])
        return {'q': q, 'state_ids': encode_state(self.tok, state, self.max_len), 'target': [0.0] * k,
                'qtype': QTYPES['choice'], 'k': k}

    @torch.no_grad()
    def logits(self, items, batch_size=16):
        out = []
        for start in range(0, len(items), batch_size):
            chunk = items[start:start + batch_size]
            batch = collate_items([[encode_item(self.tok, it, self.max_len, self.head_max_len) for it in chunk]],
                                  self.tok.pad_token_id)
            # collate_items raises when a target has more entries than surviving option markers.
            rows = _forward(self.model, batch, self.device, amp=False, detach_encoder=False).cpu().double()
            out.extend(row[:it['k']].tolist() for row, it in zip(rows, chunk))
        return out

    def distribution(self, logits, k, temperature=None):
        t = self.temperature(k) if temperature is None else temperature
        z = [v / t for v in logits]
        m = max(z)
        e = [math.exp(v - m) for v in z]
        s = sum(e)
        return [v / s for v in e], [v - m - math.log(s) for v in z]

    def predict(self, value):
        """EX-071 serving contract body for a validated `ImitationInput`."""
        state, question = self.renderer(value)
        ids = list(question['criteria'])
        [row] = self.logits([self.item(state, question)])
        probs, _ = self.distribution(row, len(ids))
        probabilities = dict(zip(ids, probs))
        return dict(input_sha256=value.sha256, action_ids=ids, probabilities=probabilities,
                    choice=max(ids, key=lambda key: probabilities[key]))
