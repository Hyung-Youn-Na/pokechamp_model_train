"""Qwen3.5-0.8B text backbone + per-tag LoRA adapters + FP32 pointer/value heads. Server processes only."""
from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
import sys

import torch
from torch import nn

from .config import KEV_COMMIT, KEV_FILES, KEV_ROOT, LORA_TARGETS, PROTOCOL, SNAPSHOT
from .storage import seed, sha

TRAIN = "learner"   # ("train" collides with nn.Module.train in PEFT ModuleDicts)


class Heads(nn.Module):
    """Pointer policy head (shared by both sides) and the p1-perspective state value head."""

    def __init__(self, hidden, pointer, value):
        super().__init__()
        self.q, self.k = nn.Linear(hidden, pointer), nn.Linear(hidden, pointer)
        self.scale = 1 / math.sqrt(pointer)
        self.v1, self.v2 = nn.Linear(hidden, value), nn.Linear(value, 1)

    def zero_init(self):
        # Zero keys -> every logit is exactly 0 (uniform P0); zero last value layer -> v = tanh(0) = 0.
        with torch.no_grad():
            for layer in (self.k, self.v2):
                layer.weight.zero_()
                layer.bias.zero_()

    def logits(self, decide, options):
        return (self.k(options) @ self.q(decide)) * self.scale

    def value(self, hidden):
        return torch.tanh(self.v2(torch.tanh(self.v1(hidden)))).squeeze(-1)


def deterministic_autotune():
    """Make Triton autotuning (fla kernels) choose by config order, not by timing: every config is still executed
    once so failing ones stay excluded, but the first working config wins on every GPU and in every process.
    Timing-based choices differed between GPU2 and GPU3 and broke cross-GPU bitwise parity (gate G2)."""
    import math as _math
    from triton.runtime import autotuner
    if getattr(autotuner.Autotuner, "_ex080_deterministic", False):
        return
    measured = autotuner.Autotuner._bench

    def ordered(self, *args, config, **meta):
        timings = measured(self, *args, config=config, **meta)
        if any(_math.isinf(t) for t in timings):
            return timings
        order = next((i for i, c in enumerate(self.configs) if c is config or str(c) == str(config)), len(self.configs))
        return [float(order)] * len(timings)

    autotuner.Autotuner._bench = ordered
    autotuner.Autotuner._ex080_deterministic = True


def kev_branch_hidden():
    """Import kev.shared_prefix pinned to the recorded commit and file hash (refuse anything else)."""
    import subprocess
    head = subprocess.check_output(["git", "-C", str(KEV_ROOT), "rev-parse", "HEAD"], text=True).strip()
    if head != KEV_COMMIT:
        raise RuntimeError("Kev checkout differs from the pinned commit")
    for name, prefix in KEV_FILES.items():
        if not sha(KEV_ROOT / name).startswith(prefix):
            raise RuntimeError(f"pinned Kev file changed: {name}")
    if str(KEV_ROOT) not in sys.path:
        sys.path.insert(0, str(KEV_ROOT))
    from kev.shared_prefix import branch_hidden
    return branch_hidden


def replicate(cache, rows):
    """A fresh per-row copy of a cached static prefix (Kev model.py:323-336). Transformers updates the conv and
    recurrent states in place during a forward pass, so serving the shared cache directly would corrupt it."""
    from transformers.cache_utils import LinearAttentionCacheLayerMixin
    replica = copy.copy(cache)
    replica.layers = [copy.copy(layer) for layer in cache.layers]
    for source, target in zip(cache.layers, replica.layers):
        if isinstance(source, LinearAttentionCacheLayerMixin):
            target.conv_states = source.conv_states.copy()
            target.recurrent_states = source.recurrent_states.copy()
            target.is_conv_states_initialized = source.is_conv_states_initialized.copy()
            target.is_recurrent_states_initialized = source.is_recurrent_states_initialized.copy()
            target.has_previous_state = source.has_previous_state.copy()
            target.conv_kernel_size = source.conv_kernel_size.copy()
    replica.reorder_cache(torch.zeros(rows, dtype=torch.long, device=_cache_device(cache)))
    return replica


def _cache_device(cache):
    for layer in cache.layers:
        for name in ("keys", "conv_states", "recurrent_states"):
            value = getattr(layer, name, None)
            if isinstance(value, dict):
                value = next((v for v in value.values() if torch.is_tensor(v)), None)
            if torch.is_tensor(value):
                return value.device
    raise ValueError("empty cache")


def cache_fingerprint(cache):
    h = hashlib.sha256()
    for layer in cache.layers:
        for name in ("keys", "values", "conv_states", "recurrent_states"):
            value = getattr(layer, name, None)
            values = value.values() if isinstance(value, dict) else [value]
            for tensor in values:
                if torch.is_tensor(tensor):
                    h.update(tensor.detach().float().cpu().numpy().tobytes())
    return h.hexdigest()


def bucket(length, buckets):
    for width in buckets:
        if length <= width:
            return width
    raise ValueError(f"row of {length} tokens exceeds the largest serving bucket {buckets[-1]}; no truncation")


def plan_passes(lengths, rows_per_pass, buckets):
    """Fixed-shape passes (D-128): rows grouped by their own length bucket, `rows_per_pass` rows per pass, input order
    kept. Every pass has the same [rows_per_pass, bucket] shape, so a row's result depends only on the row itself."""
    groups = {}
    for index, length in enumerate(lengths):
        groups.setdefault(bucket(length, buckets), []).append(index)
    return [(width, groups[width][start:start + rows_per_pass])
            for width in sorted(groups) for start in range(0, len(groups[width]), rows_per_pass)]


class Network:
    def __init__(self, device, *, attn=None, gradient_checkpointing=False, snapshot=SNAPSHOT, dtype=torch.bfloat16):
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM
        self.device = torch.device(device)
        self.autocast_dtype = torch.bfloat16 if dtype == torch.bfloat16 else None   # fp32 tiny models: exact path
        attn = attn or ("sdpa" if self.device.type == "cuda" else "eager")
        full = AutoModelForCausalLM.from_pretrained(str(snapshot), dtype=dtype, attn_implementation=attn)
        backbone = full.model
        del full
        backbone.config.use_cache = False
        lora = PROTOCOL["lora"]
        self.lora_config = LoraConfig(task_type="FEATURE_EXTRACTION", r=lora["r"], lora_alpha=lora["alpha"],
                                      lora_dropout=lora["dropout"], target_modules=list(LORA_TARGETS))
        torch.manual_seed(seed("lora-init"))
        self.lm = get_peft_model(backbone, self.lora_config, adapter_name=TRAIN)
        self._lora_fp32(TRAIN)
        if gradient_checkpointing:
            self.lm.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        self.lm.to(self.device)
        self.hidden = self.lm.get_base_model().config.hidden_size
        self.heads = {TRAIN: self.new_heads(seed("heads-init"))}
        self.static = {}
        self.active = TRAIN
        self.lm.eval()

    def _autocast(self):
        import contextlib
        if self.autocast_dtype is None:
            return contextlib.nullcontext()
        return torch.autocast(self.device.type, dtype=self.autocast_dtype)

    @property
    def base(self):
        return self.lm.get_base_model()

    def new_heads(self, init_seed):
        heads = PROTOCOL["heads"]
        torch.manual_seed(init_seed)
        module = Heads(self.hidden, heads["pointer_dim"], heads["value_hidden"])
        module.zero_init()
        return module.float().to(self.device)

    def _lora_fp32(self, tag):
        for name, parameter in self.lm.named_parameters():
            if "lora_" in name and f".{tag}." in name:
                parameter.data = parameter.data.float()

    def adapter_state(self, tag):
        from peft import get_peft_model_state_dict
        return {k: v.detach().float().cpu().contiguous() for k, v in get_peft_model_state_dict(self.lm, adapter_name=tag).items()}

    def heads_state(self, tag):
        return {k: v.detach().float().cpu().contiguous() for k, v in self.heads[tag].state_dict().items()}

    def save(self, tag, directory):
        from safetensors.torch import save_file
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        save_file(self.adapter_state(tag), str(directory / "adapter.safetensors"))
        save_file(self.heads_state(tag), str(directory / "heads.safetensors"))
        return {name: sha(directory / name) for name in ("adapter.safetensors", "heads.safetensors")}

    def load(self, tag, directory, static_ids=None):
        """Load saved adapter/head weights under `tag` (TRAIN replaces the trainable copy in place)."""
        from peft import set_peft_model_state_dict
        from safetensors.torch import load_file
        directory = Path(directory)
        if tag not in self.lm.peft_config:
            torch.manual_seed(seed("lora-slot", tag))
            self.lm.add_adapter(tag, self.lora_config)
            self._lora_fp32(tag)
            self.lm.to(self.device)
        adapter = load_file(str(directory / "adapter.safetensors"))
        if tag != TRAIN:
            self._lora_fp32(tag)   # load the saved fp32 values exactly before any serving cast
        result = set_peft_model_state_dict(self.lm, adapter, adapter_name=tag)
        if getattr(result, "unexpected_keys", None):
            raise ValueError("unexpected adapter keys")
        if tag != TRAIN and self.autocast_dtype is not None:
            # Serving copies keep LoRA in the autocast dtype: autocast rounds fp32 LoRA weights to the same bf16
            # values before every matmul, so outputs are bitwise identical while the per-layer fp32 copies vanish.
            for name, parameter in self.lm.named_parameters():
                if "lora_" in name and f".{tag}." in name:
                    parameter.data = parameter.data.to(self.autocast_dtype)
        heads = self.heads.get(tag) or self.new_heads(seed("heads-slot", tag))
        heads.load_state_dict(load_file(str(directory / "heads.safetensors")), strict=True)
        self.heads[tag] = heads
        for parameter in list(self.adapter_parameters(tag)) + list(heads.parameters()):
            if not torch.isfinite(parameter.float()).all():
                raise FloatingPointError("nonfinite checkpoint")
        self.static = {key: value for key, value in self.static.items() if key[0] != tag}
        if static_ids is not None:
            for prefix_id, ids in static_ids.items():
                self.static[tag, prefix_id] = self._static(tag, ids)
        return {name: sha(directory / name) for name in ("adapter.safetensors", "heads.safetensors")}

    def drop(self, tag):
        if tag == TRAIN:
            raise ValueError("the trainable adapter is never dropped")
        if tag in self.lm.peft_config:
            self.use(TRAIN)
            self.lm.delete_adapter(tag)
        self.heads.pop(tag, None)
        self.static = {key: value for key, value in self.static.items() if key[0] != tag}

    def adapter_parameters(self, tag):
        return [p for name, p in self.lm.named_parameters() if "lora_" in name and f".{tag}." in name]

    def use(self, tag):
        if self.active != tag:
            self.lm.set_adapter(tag)
            self.active = tag

    @torch.no_grad()
    def _static(self, tag, ids):
        from transformers import DynamicCache
        self.use(tag)
        self.lm.eval()
        tensor = torch.tensor([ids], device=self.device)
        positions = torch.arange(len(ids), device=self.device)[None]
        with self._autocast():
            out = self.lm(input_ids=tensor, position_ids=positions, past_key_values=DynamicCache(config=self.base.config),
                          use_cache=True)
        return len(ids), out.past_key_values

    def _pad(self, rows, offset, pad_id, width=None):
        width = width or max(len(ids) for ids in rows)
        ids = torch.full((len(rows), width), pad_id, dtype=torch.long)
        positions = torch.zeros((len(rows), width), dtype=torch.long)
        mask = torch.zeros((len(rows), width), dtype=torch.long)
        for i, row in enumerate(rows):
            ids[i, :len(row)] = torch.tensor(row)
            positions[i, :len(row)] = torch.arange(offset, offset + len(row))
            mask[i, :len(row)] = 1
        return ids.to(self.device), positions.to(self.device), mask.to(self.device)

    def _readout(self, tag, hidden, readouts, *, probabilities=True):
        """hidden: per row [L_i, d] fp32. -> values (p1 perspective), per-side policies (None if no readout);
        probabilities=False returns raw logits for the loss."""
        heads = self.heads[tag]
        last = torch.stack([h[(r.value if r is not None else len(h) - 1)] for h, r in zip(hidden, readouts)])
        values = heads.value(last)
        policies = []
        for h, r in zip(hidden, readouts):
            if r is None:
                policies.append(None)
                continue
            sides = []
            for decide, closes in zip(r.decide, r.closes):
                if not closes:
                    sides.append([])
                else:
                    logits = heads.logits(h[decide], h[list(closes)])
                    sides.append(torch.softmax(logits, -1) if probabilities else logits)
            policies.append(sides)
        return values, policies

    @torch.no_grad()
    def evaluate(self, tag, prefix_id, rows, readouts, *, pad_id, rows_per_pass=None, buckets=None, with_hidden=False):
        """Cached-prefix inference in fixed-shape passes (D-128): rows continue the static prefix of `prefix_id` under
        adapter `tag`; each pass holds exactly `rows_per_pass` rows (filled with copies of its first row) padded to the
        rows' own length bucket, and the value head always runs on the full pass."""
        serving = PROTOCOL["serving"]
        rows_per_pass = rows_per_pass or serving["rows_per_pass"]
        buckets = buckets or serving["buckets"]
        self.use(tag)
        self.lm.eval()
        heads = self.heads[tag]
        length, cache = self.static[tag, prefix_id]
        values, policies, hiddens = [None] * len(rows), [None] * len(rows), [None] * len(rows)
        passes = plan_passes([len(r) for r in rows], rows_per_pass, buckets)
        for width, indices in passes:
            part = [rows[i] for i in indices]
            filled = part + [part[0]] * (rows_per_pass - len(part))
            ids, positions, mask = self._pad(filled, length, pad_id, width=width)
            mask = torch.cat([torch.ones((rows_per_pass, length), dtype=torch.long, device=self.device), mask], 1)
            with self._autocast():
                out = self.lm(input_ids=ids, position_ids=positions, attention_mask=mask,
                              past_key_values=replicate(cache, rows_per_pass), use_cache=True).last_hidden_state.float()
            first = readouts[indices[0]]
            spots = [(readouts[i].value if readouts[i] is not None else len(rows[i]) - 1) for i in indices]
            spots += [first.value if first is not None else len(part[0]) - 1] * (rows_per_pass - len(part))
            last = out[torch.arange(rows_per_pass, device=self.device), torch.tensor(spots, device=self.device)]
            v = heads.value(last).cpu().tolist()
            for k, i in enumerate(indices):
                values[i] = v[k]
                if with_hidden:
                    hiddens[i] = last[k].cpu()
                r = readouts[i]
                if r is None:
                    continue
                sides = []
                for decide, closes in zip(r.decide, r.closes):
                    if not closes:
                        sides.append([])
                    else:
                        logits = heads.logits(out[k, decide], out[k, list(closes)])
                        sides.append(torch.softmax(logits, -1).cpu().tolist())
                policies[i] = sides
        if any(not math.isfinite(v) for v in values):
            raise FloatingPointError("nonfinite value")
        if with_hidden:
            return values, policies, len(passes), hiddens
        return values, policies, len(passes)

    @torch.no_grad()
    def full_rows(self, tag, static_ids, rows, readouts, *, pad_id):
        """Reference path without any cache: each row is static + suffix as one causal row (gates only)."""
        self.use(tag)
        hidden = []
        for ids in rows:
            sequence = [*static_ids, *ids]
            tensor = torch.tensor([sequence], device=self.device)
            positions = torch.arange(len(sequence), device=self.device)[None]
            with self._autocast():
                out = self.lm(input_ids=tensor, position_ids=positions).last_hidden_state.float()
            hidden.append(out[0, len(static_ids):])
        return self._readout(tag, hidden, readouts)

    def branch_rows(self, tag, static_ids, groups, *, pad_id, branch_hidden, probabilities=True):
        """Shared-prefix path (Kev branch_hidden): groups = {prefix_id: [(ids, readout), ...]}. Gradients flow
        through the static prefix (LoRA changes it), so training never reuses a cache."""
        self.use(tag)
        splits, order = [], []
        for prefix_id in sorted(groups):
            static = static_ids[prefix_id]
            length = len(static)
            branches = [{"ids": list(ids), "pos": list(range(length, length + len(ids)))} for ids, _ in groups[prefix_id]]
            splits.append((list(static), list(range(length)), branches))
            order.append(prefix_id)
        with self._autocast():
            hidden = branch_hidden(self.lm, splits, pad_id, self.device)
        outputs = {}
        for prefix_id, per_branch in zip(order, hidden):
            readouts = [r for _, r in groups[prefix_id]]
            outputs[prefix_id] = self._readout(tag, [h.float() for h in per_branch], readouts, probabilities=probabilities)
        return outputs
