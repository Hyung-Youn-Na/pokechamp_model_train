"""EX-071's one Choice readout, shared by training, evaluation and serving.

The pinned Kev encoder and pointer head are reused without changing /ref/kev.
The upstream convenience checkpoint loader casts adapters to the base dtype,
and its probability method uses a prefix cache. Neither path is used here:
LoRA and the pointer head stay FP32 on the frozen BF16 base, and every scored
decision is the same complete causal row in every stage.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import copy
import hashlib
import importlib.metadata
import json
import random
import subprocess
import sys
import time

import numpy as np
import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[3]
KEV_ROOT = Path('/ref/kev')
KEV_COMMIT = 'bb7185cb567e698b3ed0a2a682b0c3863371bf13'
BASE = 'Qwen/Qwen3.5-4B-Base'
REVISION = '1001bb4d826a52d1f399e183466143f4da7b741b'
SNAPSHOT = Path('/root/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B-Base/snapshots') / REVISION
SEED = 20261001
STATE_TOKEN_LIMIT = 8192
# This is the pinned model's actual context window, not a new data-selection
# threshold. The state limit leaves room for the complete Choice branch.
ROW_TOKEN_LIMIT = 262144
PRECISION = dict(base='bfloat16', lora='float32', head='float32', loss='float32',
                 forward='bfloat16', merged=False, cache=False, fused=False,
                 cuda_graphs=False, tf32=False)
MODEL_CONFIG = dict(base=BASE, revision=REVISION, kev_commit=KEV_COMMIT,
                    lora_r=16, lora_alpha=32, lora_dropout=0.05,
                    lora_targets='all', head_dim=256, temperature=1.0,
                    option_isolation=False, special_embeddings=False,
                    state_token_limit=STATE_TOKEN_LIMIT,
                    row_token_limit=ROW_TOKEN_LIMIT, precision=PRECISION)
OFFICIAL_HASHES = {
    'model.safetensors-00001-of-00002.safetensors': 'df547074dce70532a0493e5433152bd17a65efb89088cfabc2e7e2371a93d712',
    'model.safetensors-00002-of-00002.safetensors': '590fbaac095dd31db886c322d9d2f7df47777966391acf306ddddc3e4e3a15ef',
    'tokenizer.json': 'fe000e3ed39ed12b8d2481d527d44f93c65d37e87645d2dcc80d1bf9d50d2927',
}


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def json_bytes(value):
    """Keep candidate insertion order, which is part of the model input."""
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def json_sha256(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def _kev():
    if str(KEV_ROOT) not in sys.path:
        sys.path.insert(0, str(KEV_ROOT))
    from kev import api, model
    if Path(model.__file__).resolve() != KEV_ROOT / 'kev/model.py':
        raise ValueError('an unregistered Kev package shadows the pinned source')
    return api, model


def provenance(*, verify_weights=False):
    commit = subprocess.check_output(
        ['git', '-C', str(KEV_ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != KEV_COMMIT:
        raise ValueError('Kev commit differs from EX-071')
    # A clean commit id alone would miss edits to the imported implementation.
    paths = ['kev/model.py', 'kev/api.py', 'kev/__init__.py']
    for path in paths:
        expected = subprocess.check_output(['git', '-C', str(KEV_ROOT),
                                            'show', KEV_COMMIT + ':' + path])
        if hashlib.sha256(expected).hexdigest() != file_sha256(KEV_ROOT / path):
            raise ValueError('pinned Kev source was modified: ' + path)
    if not SNAPSHOT.is_dir():
        raise FileNotFoundError('pinned Base snapshot is unavailable: ' + str(SNAPSHOT))
    if verify_weights:
        for name, expected in OFFICIAL_HASHES.items():
            if file_sha256(SNAPSHOT / name) != expected:
                raise ValueError('official Base checksum differs: ' + name)
    return dict(kev_commit=commit, kev_source={p: file_sha256(KEV_ROOT / p) for p in paths},
                model=MODEL_CONFIG, base_snapshot=str(SNAPSHOT),
                official_hashes=OFFICIAL_HASHES,
                tokenizer_files={p.name: file_sha256(p) for p in sorted(SNAPSHOT.iterdir())
                                 if p.name in ('config.json', 'tokenizer.json', 'tokenizer_config.json',
                                               'vocab.json', 'merges.txt')},
                packages={p: importlib.metadata.version(p) for p in
                          ('torch', 'transformers', 'peft', 'numpy', 'pydantic',
                           'safetensors', 'huggingface-hub', 'tokenizers')})


def load_tokenizer():
    from transformers import AutoTokenizer
    provenance()
    tok = AutoTokenizer.from_pretrained(SNAPSHOT, local_files_only=True,
                                        trust_remote_code=False)
    if not tok.is_fast:
        raise ValueError('the pinned fast tokenizer is required')
    return tok


def input_body(value):
    body = copy.deepcopy(value if isinstance(value, dict) else value.body)
    if not isinstance(body, dict) or set(body) != {'state', 'questions'}:
        raise ValueError('model input must contain only state and questions')
    if not isinstance(body['state'], str):
        raise ValueError('imitation state must be a serialized JSON string')
    questions = body['questions']
    if not isinstance(questions, dict) or list(questions) != ['action']:
        raise ValueError('exactly one action Choice question is required')
    q = questions['action']
    if (not isinstance(q, dict) or set(q) != {'type', 'instructions', 'criteria'}
            or q['type'] != 'choice' or not isinstance(q['instructions'], str)
            or not isinstance(q['criteria'], dict) or not 1 <= len(q['criteria']) <= 255):
        raise ValueError('invalid Choice question; labels and metadata are not inputs')
    if any(not isinstance(k, str) or not k or not isinstance(v, str)
           for k, v in q['criteria'].items()):
        raise ValueError('every candidate needs an action ID and a description')
    from .schema import ImitationInput
    # One schema owns the public-input allowlist. The learning loader must be
    # just as strict as HTTP serving, including the version and question text.
    ImitationInput.from_body(body)
    return body


@dataclass(frozen=True)
class EncodedChoice:
    encoding: dict
    action_ids: tuple[str, ...]
    tokens: int
    state_tokens: int
    input_sha256: str


def encode_input(value, tok=None):
    body = input_body(value)
    tok = tok if tok is not None else load_tokenizer()
    api, kev = _kev()
    record, meta = api.to_record(api.SystemOneRequest.model_validate(body))
    encoding = kev.encode(tok, record, max_state=STATE_TOKEN_LIMIT,
                          max_branch=ROW_TOKEN_LIMIT, strict=True,
                          option_isolation=False)
    action_ids = tuple(body['questions']['action']['criteria'])
    state_tokens = encoding['seg'].count(0)
    if (encoding['state_truncated'] or state_tokens > STATE_TOKEN_LIMIT
            or len(encoding['ids']) > ROW_TOKEN_LIMIT
            or len(meta) != 1 or tuple(meta[0]['keys']) != action_ids
            or len(encoding['decide_idx']) != 1
            or len(encoding['opt_idx'][0]) != len(action_ids)):
        raise ValueError('Choice encoding clipped or changed the candidate binding')
    # True targets never reach this record: Kev's placeholder label is always 0.
    if encoding['labels'] != [0]:
        raise ValueError('a training target reached the model input')
    return EncodedChoice(encoding, action_ids, len(encoding['ids']), state_tokens,
                         json_sha256(body))


def permute_input(value, *, sample_id, epoch):
    body = input_body(value)
    criteria = body['questions']['action']['criteria']
    keys = list(criteria)
    random.Random(f'{SEED}:candidates:{epoch}:{sample_id}').shuffle(keys)
    body['questions']['action']['criteria'] = {key: criteria[key] for key in keys}
    return body


def seed_all(seed=SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False


def rng_state():
    return dict(python=random.getstate(), numpy=np.random.get_state(),
                torch=torch.get_rng_state(),
                cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else [])


def restore_rng(state):
    random.setstate(state['python'])
    np.random.set_state(state['numpy'])
    torch.set_rng_state(state['torch'])
    if state['cuda']:
        if not torch.cuda.is_available() or len(state['cuda']) != torch.cuda.device_count():
            raise ValueError('checkpoint CUDA RNG device count differs')
        torch.cuda.set_rng_state_all(state['cuda'])


def tensor_fingerprints(module, predicate=lambda name, parameter: True):
    result = {}
    for name, p in module.named_parameters():
        if predicate(name, p):
            data = p.detach().cpu().contiguous().view(torch.uint8).numpy()
            result[name] = hashlib.sha256(data.tobytes()).hexdigest()
    return result


def checkpoint_identity(path):
    """Stable checkpoint identity available to a CPU-only battle controller."""
    return file_sha256(Path(path) / 'files.json')


def verify_checkpoint(path):
    path = Path(path)
    expected = json.loads((path / 'files.json').read_text(encoding='utf-8'))
    actual = {str(p.relative_to(path)): file_sha256(p) for p in sorted(path.rglob('*'))
              if p.is_file() and p != path / 'files.json'}
    if actual != expected:
        raise ValueError('checkpoint file integrity failure: ' + str(path))
    metadata = json.loads((path / 'metadata.json').read_text(encoding='utf-8'))
    if metadata['model_config'] != MODEL_CONFIG:
        raise ValueError('checkpoint model or precision contract differs')
    return metadata


class Policy(nn.Module):
    def __init__(self, device='cuda:0', checkpoint=None, tokenizer=None):
        super().__init__()
        # A fresh serving process must not inherit different backend defaults
        # from a trainer that called seed_all(). These flags are model-path
        # configuration, rather than an initialization-only setting.
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        provenance()
        self.tokenizer = tokenizer if tokenizer is not None else load_tokenizer()
        _, kev = _kev()
        self.model = kev.DecisionModel(str(SNAPSHOT), self.tokenizer, device,
            lora=16, lora_targets='all', dtype=torch.bfloat16,
            attn='sdpa' if str(device).startswith('cuda') else 'eager',
            head_dim=256, option_isolation=False, special_embeddings=False)
        self.device_name = str(device)
        self.model.lm.config.use_cache = False
        self.model.lm.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={'use_reentrant': False})
        self.model.head.float()
        self.model.head.temperature = 1.0
        self.loaded_base_fingerprints = None
        for name, p in self.model.lm.named_parameters():
            if 'lora_' in name:
                p.data = p.data.float()
        if checkpoint is not None:
            from peft import get_peft_model_state_dict, load_peft_weights, set_peft_model_state_dict
            saved = verify_checkpoint(checkpoint)
            weights = load_peft_weights(str(Path(checkpoint) / 'adapter'), device='cpu')
            if set(weights) != set(get_peft_model_state_dict(self.model.lm)):
                raise ValueError('checkpoint does not cover the exact LoRA tensors')
            set_peft_model_state_dict(self.model.lm, weights)
            head = torch.load(Path(checkpoint) / 'head.pt', map_location='cpu', weights_only=True)
            self.model.head.load_state_dict(head)
            if self.trainable_fingerprints() != saved['trainable_fingerprints']:
                raise ValueError('checkpoint parameter reload changed bits')
            self.loaded_base_fingerprints = self.base_fingerprints()
            if self.loaded_base_fingerprints != saved['base_fingerprints']:
                raise ValueError('checkpoint Base reload differs from the frozen weights')
        self.assert_precision()

    @property
    def backbone(self):
        return self.model.lm

    @property
    def head(self):
        return self.model.head

    def assert_precision(self):
        seen = {'base': 0, 'lora': 0, 'head': 0}
        for name, p in self.named_parameters():
            kind = 'lora' if 'lora_' in name else 'head' if name.startswith('model.head.') else 'base'
            seen[kind] += p.numel()
            if p.dtype != (torch.bfloat16 if kind == 'base' else torch.float32):
                raise ValueError('parameter precision differs: ' + name)
            if p.requires_grad != (kind != 'base'):
                raise ValueError('unexpected trainability: ' + name)
        if not all(seen.values()):
            raise ValueError('base, LoRA and pointer head must all exist')
        if any(getattr(m, 'merged', False) for m in self.backbone.modules()):
            raise ValueError('merged LoRA is forbidden')
        return seen

    def base_fingerprints(self):
        return tensor_fingerprints(self, lambda name, p: not p.requires_grad)

    def trainable_fingerprints(self):
        return tensor_fingerprints(self, lambda name, p: p.requires_grad)

    def logits(self, encoded):
        if not isinstance(encoded, EncodedChoice):
            raise TypeError('EncodedChoice is required')
        _, kev = _kev()
        state, positions, rows = kev.rows_of(encoded.encoding)
        if len(rows) != 1:
            raise ValueError('imitation policy accepts exactly one Choice row')
        row = rows[0]
        on_cuda = self.device_name.startswith('cuda')
        with torch.autocast('cuda', dtype=torch.bfloat16, enabled=on_cuda):
            hidden = self.model._rows_hidden([
                (state + row['ids'], positions + row['pos'])])[0]
        # The same Kev PointerHead, evaluated in FP32 (parameters and math).
        with torch.autocast('cuda', enabled=False):
            options = torch.tensor([len(state) + i for i in row['opts']],
                                   device=self.device_name, dtype=torch.long)
            z = self.head(hidden[len(state) + row['decide']].float(),
                          hidden[options].float()).float()
        if z.shape != (len(encoded.action_ids),) or not bool(torch.isfinite(z).all()):
            raise FloatingPointError('nonfinite or misaligned Choice logits')
        return z

    def predict(self, value):
        self.eval()
        start = time.perf_counter()
        encoded = encode_input(value, self.tokenizer)
        if len(encoded.action_ids) == 1:
            ps = [1.0]
            inferred = False
        else:
            with torch.no_grad():
                ps = torch.softmax(self.logits(encoded), dim=-1).cpu().tolist()
            inferred = True
        chosen = max(range(len(ps)), key=ps.__getitem__)
        return dict(action_ids=list(encoded.action_ids),
                    probabilities=dict(zip(encoded.action_ids, ps, strict=True)),
                    choice=encoded.action_ids[chosen], input_sha256=encoded.input_sha256,
                    token_count=encoded.tokens, state_tokens=encoded.state_tokens,
                    elapsed_seconds=time.perf_counter() - start, inferred=inferred)


def choice_loss(logits, action_ids, label):
    if len(set(action_ids)) != len(action_ids) or label not in action_ids:
        raise ValueError('the observed label must identify exactly one candidate')
    if len(action_ids) < 2:
        raise ValueError('single-candidate decisions are excluded from the training denominator')
    if logits.shape != (len(action_ids),) or not bool(torch.isfinite(logits).all()):
        raise FloatingPointError('invalid Choice logits')
    target = torch.tensor([action_ids.index(label)], device=logits.device, dtype=torch.long)
    with torch.autocast('cuda', enabled=False):
        loss = torch.nn.functional.cross_entropy(logits.float()[None], target)
    if not bool(torch.isfinite(loss)):
        raise FloatingPointError('nonfinite imitation loss')
    return loss


def check_gradients(policy):
    squares = 0.0
    for name, p in policy.named_parameters():
        if not p.requires_grad:
            if p.grad is not None:
                raise ValueError('frozen Base received a gradient: ' + name)
            continue
        # Zero is a finite gradient, e.g. the freshly zero-initialized LoRA B
        # makes its paired A gradient zero in the first backward pass.
        if p.grad is None or not bool(torch.isfinite(p.grad).all()):
            raise FloatingPointError('missing or nonfinite trainable gradient: ' + name)
        squares += float(p.grad.detach().double().square().sum())
    norm = squares ** 0.5
    if not np.isfinite(norm):
        raise FloatingPointError('nonfinite total gradient norm')
    return norm
