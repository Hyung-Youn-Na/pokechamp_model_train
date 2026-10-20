"""Official Quyet inference, one loaded BF16 model explicitly split over GPU0..3."""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time

from .config import (CODE_REVISION, EVIDENCE, MAX_TOKENS, MODEL_DIR, MODEL_ID,
                     QUYET_SOURCE, REVISION, runtime_profile)
from .formatting import prepare
from .storage import read


def fixed_device_map():
    return {'model.embed_tokens': 0,
            **{f'model.layers.{i}': i // 8 for i in range(32)},
            'model.norm': 3, 'model.rotary_emb': 0, 'lm_head': 0}


def check_placement(model):
    placement = fixed_device_map()
    count, dtypes = Counter(), Counter()
    for name, parameter in model.named_parameters(remove_duplicate=False):
        prefixes = [p for p in placement if name == p or name.startswith(p + '.')]
        if not prefixes:
            raise ValueError('unmapped model parameter: ' + name)
        expected = placement[max(prefixes, key=len)]
        if str(parameter.device) != f'cuda:{expected}':
            raise ValueError('device placement mismatch: ' + name)
        count[str(parameter.device)] += parameter.numel()
        dtypes[str(parameter.dtype)] += parameter.numel()
    if model.get_input_embeddings().weight is not model.get_output_embeddings().weight:
        raise ValueError('official tied embedding/head identity lost')
    if set(count) != {'cuda:0', 'cuda:1', 'cuda:2', 'cuda:3'}:
        raise ValueError('four-device coverage missing')
    return dict(parameter_elements_by_device=dict(count), parameter_elements_by_dtype=dict(dtypes),
                tied_embeddings=True, device_map=placement)


def memory_sample():
    import torch
    for i in range(4):
        torch.cuda.synchronize(i)
    return {name: [fn(i) for i in range(4)] for name, fn in (
        ('allocated', torch.cuda.memory_allocated), ('reserved', torch.cuda.memory_reserved),
        ('peak_allocated', torch.cuda.max_memory_allocated), ('peak_reserved', torch.cuda.max_memory_reserved))}


class QuyetModel:
    def __init__(self, model_dir=MODEL_DIR, *, max_tokens=MAX_TOKENS, profile='ex084'):
        if max_tokens != MAX_TOKENS or Path(model_dir).resolve() != MODEL_DIR.resolve():
            raise ValueError('model path/length differs from frozen EX-084')
        self.profile = runtime_profile(profile)
        self.model_dir = Path(model_dir)
        self.runtime = None
        self.identity = None
        self.details = {}

    def load(self):
        import torch
        from quyet.llm.runtime import LLMModel
        from integration.jev27b.config import PINNED
        versions = {name: importlib.metadata.version(name) for name in PINNED}
        if versions != PINNED:
            raise ValueError('reused JEV environment versions changed')
        actual = subprocess.check_output(['git', '-C', str(QUYET_SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', str(QUYET_SOURCE), 'status', '--porcelain'], text=True).strip()
        if actual != CODE_REVISION or dirty:
            raise ValueError('pinned Quyet source differs')
        receipt = read(EVIDENCE / 'download.json')
        if receipt.get('passed') is not True or receipt['revision'] != REVISION or receipt['model'] != MODEL_ID:
            raise ValueError('missing official bundle receipt')
        official = read(self.model_dir / 'quyet_config.json')
        if official['prompt_version'] != 1 or official['temperatures']['choice'] != 1.3313:
            raise ValueError('official prompt or calibration changed')
        started = time.monotonic()
        self.runtime = LLMModel(self.model_dir, official, 'cuda:0', dtype=torch.bfloat16,
                                device_map=fixed_device_map())
        self.runtime.max_state_tokens = self.runtime.max_prompt_tokens = MAX_TOKENS
        # Each decision is independent. Do not retain a KV/recurrent generation cache.
        self.runtime.model.config.use_cache = False
        self.runtime.model.model.config.use_cache = False
        placement = check_placement(self.runtime.model)
        self.details = dict(model=MODEL_ID, revision=REVISION, code_revision=CODE_REVISION,
            official_name=self.runtime.name, prompt_version=1, strict=True,
            limits=dict(state=MAX_TOKENS, prompt=MAX_TOKENS, options=10),
            official_limits=official['limits'], temperatures=self.runtime.temps,
            quantization=None, offload=None, profile=self.profile.name,
            allocator_bytes=self.profile.allocator_bytes, gpu_bytes=self.profile.gpu_bytes,
            use_cache=False, placement=placement,
            versions=versions,
            official_files=receipt['files'])
        self.identity = hashlib.sha256(json.dumps(self.details, sort_keys=True).encode()).hexdigest()
        self.details['load_seconds'] = time.monotonic() - started
        self.details['loaded_memory'] = memory_sample()
        return self

    def metadata(self):
        return dict(self.details, loaded=self.runtime is not None, serving_identity=self.identity)

    def evaluate(self, payload):
        prepared = prepare(self.runtime.tok, payload, strict=True)
        import torch
        before = memory_sample()
        for i in range(4):
            torch.cuda.reset_peak_memory_stats(i)
        started = time.monotonic()
        result = self.runtime.predict(payload['state'], payload['questions'], strict=True)
        after = memory_sample()
        if result['usage']['input_tokens'] != len(prepared.token_ids) or result['warnings']:
            raise ValueError('official formatter count/truncation drift')
        if any(a.get('truncated') for a in result['answers'].values()):
            raise ValueError('truncated inference forbidden')
        if any(v > self.profile.allocator_bytes for values in after.values() for v in values):
            raise ValueError('allocator memory limit exceeded')
        result['model'] = MODEL_ID
        result['metadata'] = dict(revision=REVISION, serving_identity=self.identity,
            formatter=prepared.evidence(), elapsed_seconds=time.monotonic() - started,
            memory_before=before, memory_after=after)
        return result

    def validate_input(self, payload):
        """Reject malformed/overlong requests before the journal consumes an inference."""
        prepare(self.runtime.tok, payload, strict=True)
