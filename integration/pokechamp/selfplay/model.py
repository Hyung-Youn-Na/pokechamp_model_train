"""EX-072 policy and selected-action W/D/L readouts on one frozen-base forward."""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import os
from pathlib import Path
import random
import tempfile
import time

import torch
from torch import nn

from ..imitation import model as imitation
from .objectives import old_baseline


SEED = 20261002
INITIAL_CHECKPOINT = (imitation.ROOT / ".pokechamp-data/experiments/"
                      "ex071-qwen-replay-imitation/training/checkpoint-0001720")
MODEL_CONFIG = copy.deepcopy(imitation.MODEL_CONFIG)
MODEL_CONFIG.update(lora_dropout=0.0, wdl_head=["2d", 256, "Tanh", 3],
                    wdl_order=["W", "D", "L"], sampling="categorical")
EncodedChoice = imitation.EncodedChoice
encode_input = imitation.encode_input


@dataclass
class Scores:
    logits: torch.Tensor
    wdl_logits: torch.Tensor
    features: torch.Tensor

    @property
    def log_probabilities(self):
        return self.logits.float().log_softmax(-1)

    @property
    def wdl_probabilities(self):
        return self.wdl_logits.float().softmax(-1)


def make_wdl_head(hidden_size, *, device="cpu"):
    head = nn.Sequential(nn.Linear(2 * hidden_size, 256), nn.Tanh(), nn.Linear(256, 3))
    nn.init.zeros_(head[-1].weight)
    nn.init.zeros_(head[-1].bias)
    return head.to(device=device, dtype=torch.float32)


def sample_categorical(probabilities, *, seed=None, generator=None, return_uniform=False):
    if seed is not None and generator is not None:
        raise ValueError("pass a sampling seed or a generator, not both")
    if generator is None:
        if seed is None:
            raise ValueError("categorical sampling needs an explicit RNG identity")
        generator = random.Random(int(seed))
    p = torch.as_tensor(probabilities, dtype=torch.float32, device="cpu")
    if (p.ndim != 1 or not bool(torch.isfinite(p).all()) or bool((p < 0).any())
            or not torch.allclose(p.sum(), torch.tensor(1.0), atol=1e-5, rtol=0)):
        raise ValueError("invalid sampling distribution")
    uniform = (float(torch.rand((), generator=generator)) if isinstance(generator, torch.Generator)
               else generator.random())
    # Normalize the float32 roundoff again in Python for a stable CPU audit.
    values = p.tolist()
    total = sum(values)
    cumulative, choice = 0.0, len(values) - 1
    for index, value in enumerate(values):
        cumulative += value / total
        if uniform < cumulative:
            choice = index
            break
    return (choice, uniform) if return_uniform else choice


def _rng_digest(generator):
    state = (generator.get_state().numpy().tobytes() if isinstance(generator, torch.Generator)
             else repr(generator.getstate()).encode())
    return hashlib.sha256(state).hexdigest()


class SelfPlayPolicy(nn.Module):
    """Composition preserves the EX-071 loader's own precision/reload checks."""

    def __init__(self, device="cuda:0", checkpoint=INITIAL_CHECKPOINT, tokenizer=None):
        super().__init__()
        self.policy = imitation.Policy(device=device, checkpoint=checkpoint, tokenizer=tokenizer)
        self.device_name = str(device)
        self.tokenizer = self.policy.tokenizer
        # EX-071 is loaded and verified before modifying the dropout contract.
        for module in self.policy.modules():
            if isinstance(module, nn.Dropout):
                module.p = 0.0
        for config in self.backbone.peft_config.values():
            config.lora_dropout = 0.0
        self.wdl_head = make_wdl_head(self.policy.head.q.in_features, device=device)
        self._weight_names = frozenset(name for name, p in self.named_parameters() if p.requires_grad)
        self.sampling_generator = random.Random(SEED)
        self.stage = "policy"
        self.assert_precision()

    @property
    def backbone(self):
        return self.policy.backbone

    @property
    def head(self):
        return self.policy.head

    def set_stage(self, stage):
        if stage not in ("policy", "calibration", "inference"):
            raise ValueError("unknown selfplay model stage")
        self.stage = stage
        for name, p in self.named_parameters():
            p.requires_grad_(name in self._weight_names and
                             (stage == "policy" or stage == "calibration" and name.startswith("wdl_head.")))
        self.train(stage != "inference")
        self.assert_precision()

    def assert_precision(self):
        counts = dict(base=0, lora=0, action_head=0, wdl_head=0)
        for name, p in self.named_parameters():
            kind = ("lora" if "lora_" in name else "wdl_head" if name.startswith("wdl_head.")
                    else "action_head" if name.startswith("policy.model.head.") else "base")
            counts[kind] += p.numel()
            if p.dtype != (torch.bfloat16 if kind == "base" else torch.float32):
                raise ValueError("selfplay parameter precision differs: " + name)
            expected = kind != "base" and (self.stage == "policy" or
                       self.stage == "calibration" and kind == "wdl_head")
            if p.requires_grad != expected:
                raise ValueError("selfplay trainability differs: " + name)
        if not all(counts.values()):
            raise ValueError("base, LoRA, action head and W/D/L head are required")
        if any(isinstance(m, nn.Dropout) and m.p != 0 for m in self.modules()):
            raise ValueError("selfplay forward must have zero dropout")
        if any(getattr(m, "merged", False) for m in self.backbone.modules()):
            raise ValueError("merged adapters are forbidden")
        return counts

    def scores(self, encoded):
        if not isinstance(encoded, EncodedChoice):
            raise TypeError("EncodedChoice is required")
        _, kev = imitation._kev()
        state, positions, rows = kev.rows_of(encoded.encoding)
        if len(rows) != 1:
            raise ValueError("selfplay requires exactly one Choice row")
        row = rows[0]
        with torch.autocast("cuda", dtype=torch.bfloat16,
                            enabled=self.device_name.startswith("cuda")):
            hidden = self.policy.model._rows_hidden([
                (state + row["ids"], positions + row["pos"])])[0]
        with torch.autocast("cuda", enabled=False):
            option_indices = torch.tensor([len(state) + i for i in row["opts"]],
                                          device=self.device_name, dtype=torch.long)
            decision = hidden[len(state) + row["decide"]].float()
            candidates = hidden[option_indices].float()
            logits = self.head(decision, candidates).float()
            features = torch.cat((decision.expand(len(candidates), -1), candidates), dim=-1)
            wdl_logits = self.wdl_head(features).float()
        if (logits.shape != (len(encoded.action_ids),)
                or wdl_logits.shape != (len(encoded.action_ids), 3)
                or not bool(torch.isfinite(logits).all())
                or not bool(torch.isfinite(wdl_logits).all())):
            raise FloatingPointError("nonfinite or misaligned selfplay readouts")
        return Scores(logits, wdl_logits, features)

    def logits(self, encoded):
        return self.scores(encoded).logits

    def predict(self, value, *, seed=None, generator=None, alternate_head=None):
        self.eval()
        start = time.perf_counter()
        encoded = encode_input(value, self.tokenizer)
        if seed is not None and generator is not None:
            raise ValueError("pass a sampling seed or a generator, not both")
        if generator is None:
            generator = (random.Random(int(seed)) if seed is not None
                         else self.sampling_generator)
        before = _rng_digest(generator)
        ids = encoded.action_ids
        if len(ids) == 1:
            # C-055 automatic actions have no model forward or learned W/D/L.
            return dict(action_ids=list(ids), probabilities={ids[0]: 1.0},
                        log_probabilities={ids[0]: 0.0}, wdl_probabilities=None,
                        baseline=None, choice=ids[0], input_sha256=encoded.input_sha256,
                        token_count=encoded.tokens, state_tokens=encoded.state_tokens,
                        elapsed_seconds=time.perf_counter() - start, inferred=False,
                        sampling_seed=seed, sampling_uniform=None,
                        rng=dict(seed=seed, state_before=before, state_after=before))
        with torch.no_grad():
            scored = self.scores(encoded)
            logp = scored.log_probabilities
            probabilities = logp.exp().cpu()
            wdl = scored.wdl_probabilities
            baseline = float(old_baseline(logp, wdl))
            after_wdl = None
            if alternate_head is not None:
                if isinstance(alternate_head, dict):
                    from torch.func import functional_call
                    if set(alternate_head) != set(self.wdl_head.state_dict()):
                        raise ValueError("alternate W/D/L head must cover every parameter")
                    params = {k: v.to(device=scored.features.device, dtype=torch.float32)
                              for k, v in alternate_head.items()}
                    after_wdl = functional_call(self.wdl_head, params,
                                               (scored.features,)).float().softmax(-1)
                else:
                    after_wdl = alternate_head(scored.features).float().softmax(-1)
        chosen, uniform = sample_categorical(probabilities, generator=generator, return_uniform=True)
        result = dict(action_ids=list(ids), probabilities=dict(zip(ids, probabilities.tolist())),
                      log_probabilities=dict(zip(ids, logp.cpu().tolist())),
                      wdl_probabilities=dict(zip(ids, wdl.cpu().tolist())), baseline=baseline,
                      choice=ids[chosen], input_sha256=encoded.input_sha256,
                      token_count=encoded.tokens, state_tokens=encoded.state_tokens,
                      elapsed_seconds=time.perf_counter() - start, inferred=True,
                      sampling_seed=seed, sampling_uniform=uniform,
                      rng=dict(seed=seed, state_before=before,
                               state_after=_rng_digest(generator)))
        if after_wdl is not None:
            result["wdl_probabilities_after"] = dict(zip(ids, after_wdl.cpu().tolist()))
        return result

    def snapshot_weights(self):
        return {name: p.detach().cpu().clone() for name, p in self.named_parameters()
                if name in self._weight_names}

    def load_weights(self, weights):
        if set(weights) != self._weight_names:
            raise ValueError("snapshot must cover the exact LoRA and both heads")
        named = dict(self.named_parameters())
        # Validate all tensors before mutating any parameter.
        for name, value in weights.items():
            if (value.shape != named[name].shape or value.dtype != torch.float32
                    or not bool(torch.isfinite(value).all())):
                raise ValueError("invalid snapshot tensor: " + name)
        with torch.no_grad():
            for name, value in weights.items():
                named[name].copy_(value.to(named[name].device))

    def trainable_fingerprints(self):
        return imitation.tensor_fingerprints(self, lambda name, p: name in self._weight_names)

    def policy_fingerprints(self):
        return imitation.tensor_fingerprints(self, lambda name, p: name in self._weight_names
                                             and not name.startswith("wdl_head."))

    def base_fingerprints(self):
        return imitation.tensor_fingerprints(self, lambda name, p: name not in self._weight_names)

    def save_snapshot(self, path, metadata=None):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(model_config=MODEL_CONFIG, weights=self.snapshot_weights(),
                       fingerprints=self.trainable_fingerprints(), metadata=metadata or {})
        fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                torch.save(payload, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory_fd = os.open(path.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return dict(path=str(path), sha256=imitation.file_sha256(path),
                    fingerprints=payload["fingerprints"])

    def load_snapshot(self, path):
        saved = torch.load(path, map_location="cpu", weights_only=True)
        if saved.get("model_config") != MODEL_CONFIG:
            raise ValueError("snapshot model contract changed")
        self.load_weights(saved["weights"])
        if self.trainable_fingerprints() != saved["fingerprints"]:
            raise ValueError("snapshot reload changed tensor bits")
        return saved.get("metadata", {})


Policy = SelfPlayPolicy
