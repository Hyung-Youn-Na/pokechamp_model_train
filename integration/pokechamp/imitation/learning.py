"""Bounded, resumable EX-071 LoRA training and one-read test evaluation.

Public entry points accept the experiment output directory. Data preparation
owns prepared/{train,validation,test}.jsonl and its manifest. The controller
owns resource.json and the physical GPU lock. This module checks that identity
but never selects a different GPU or touches EX-066's execution.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import signal
import tempfile
import time

import numpy as np
import torch

from .model import (MODEL_CONFIG, PRECISION, ROOT, SEED, Policy, check_gradients,
                    checkpoint_identity, choice_loss, encode_input, file_sha256,
                    input_body, json_bytes, json_sha256, load_tokenizer,
                    permute_input, provenance, restore_rng, rng_state,
                    seed_all, verify_checkpoint)


CONFIG = dict(experiment='EX-071', seed=SEED, epochs=3, microbatch=1,
              accumulation=16, learning_rate=5e-5, betas=[0.9, 0.999],
              weight_decay=0.01, gradient_clip=1.0,
              scheduler='linear_warmup_10_percent_then_cosine',
              maximum_seconds=24 * 3600, validation_reserve_seconds=4 * 3600,
              resume_interval_seconds=15 * 60, preflight_samples=32,
              preflight_p95_margin=1.2, validation_samples=512, test_samples=1024,
              checkpoint_fractions=[0.25, 0.5, 0.75, 1.0],
              model=MODEL_CONFIG)


class BudgetExpired(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_json(path, value, *, immutable=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json_bytes(value) + b'\n'
    if immutable and path.exists():
        if path.read_bytes() == payload:
            return
        raise FileExistsError('immutable evidence already exists: ' + str(path))
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        if immutable:
            # Hard-link admission is atomic and cannot overwrite an existing
            # reservation even when two controller processes race.
            try:
                os.link(temp, path)
            except FileExistsError:
                if path.read_bytes() != payload:
                    raise
        else:
            os.replace(temp, path)
        dirfd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(json_bytes(value).decode('utf-8') + '\n')
        f.flush()
        os.fsync(f.fileno())


def append_jsonl(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json_bytes(value).decode('utf-8') + '\n')
        f.flush()
        os.fsync(f.fileno())


def rows(path):
    result = []
    with Path(path).open(encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                raise ValueError(f'empty prepared record at {path}:{i}')
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f'non-object prepared record at {path}:{i}')
            result.append(value)
    return result


def source_hashes():
    sources = list(Path(__file__).parent.glob('*.py'))
    script = ROOT / 'scripts/pokechamp-imitation'
    if script.exists():
        sources.append(script)
    return {str(path.relative_to(ROOT)): file_sha256(path)
            for path in sorted(sources)}


def prepared_records(output):
    result = {}
    for split, cap in [('train', None), ('validation', CONFIG['validation_samples']),
                       ('test', CONFIG['test_samples'])]:
        records = rows(Path(output) / 'prepared' / (split + '.jsonl'))
        if not records or cap is not None and len(records) > cap:
            raise ValueError(f'{split} has no samples or exceeds its frozen cap')
        seen = set()
        for r in records:
            if r.get('split') != split or not isinstance(r.get('sample_id'), str):
                raise ValueError('prepared split/sample identity differs')
            if r['sample_id'] in seen:
                raise ValueError('duplicate sample in ' + split)
            seen.add(r['sample_id'])
            body = input_body(r['input'])
            candidates = body['questions']['action']['criteria']
            if len(candidates) < 2 or r.get('label') not in candidates:
                raise ValueError('masked or single-candidate record entered ' + split)
            if not r.get('group_id') or not r.get('replay_id'):
                raise ValueError('prepared sample lacks its replay/group identity')
            if not isinstance(r.get('tera_used'), bool):
                raise ValueError('prepared sample lacks historical Tera status')
        result[split] = records
    for field in ('group_id', 'replay_id', 'sample_id'):
        sets = {split: {r[field] for r in records} for split, records in result.items()}
        for a, b in [('train', 'validation'), ('train', 'test'), ('validation', 'test')]:
            if sets[a] & sets[b]:
                raise ValueError(f'{field} crosses {a}/{b} partitions')
    return result


def freeze(output):
    output = Path(output)
    destination = output / 'learning-manifest.json'
    if destination.exists():
        return assert_frozen(output)
    records = prepared_records(output)
    resource = read_json(output / 'resource.json')
    if resource.get('physical_gpu') not in (3, 2, 0):
        raise ValueError('EX-071 may only own one of physical GPUs 3, 2, 0')
    evidence = dict(version='pokemon-imitation-learning-v1', at=now(), config=CONFIG,
                    prepared_manifest_sha256=file_sha256(output / 'prepared/manifest.json'),
                    data_files={split + '.jsonl': file_sha256(output / 'prepared' / (split + '.jsonl'))
                                for split in records},
                    denominators={split: len(value) for split, value in records.items()},
                    resource=resource, resource_sha256=file_sha256(output / 'resource.json'),
                    sources=source_hashes(), environment=provenance(verify_weights=True))
    # Preserve the actual executed source alongside the hashes; later working
    # tree edits must not make the training implementation unrecoverable.
    for name, expected in evidence['sources'].items():
        destination_path = output / 'learning-source' / name
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        payload = (ROOT / name).read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError('source changed during learning freeze: ' + name)
        if destination_path.exists() and destination_path.read_bytes() != payload:
            raise FileExistsError('different preserved learning source exists: ' + name)
        if not destination_path.exists():
            with destination_path.open('xb') as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
    atomic_json(destination, evidence, immutable=True)
    return evidence


def assert_frozen(output):
    output = Path(output)
    frozen = read_json(output / 'learning-manifest.json')
    if frozen['config'] != CONFIG or frozen['sources'] != source_hashes():
        raise ValueError('learning source/configuration changed after freezing')
    for name, expected in frozen['sources'].items():
        if file_sha256(output / 'learning-source' / name) != expected:
            raise ValueError('preserved learning source changed: ' + name)
    if frozen['environment'] != provenance():
        raise ValueError('pinned model source/tokenizer/environment changed')
    for path, expected in frozen['data_files'].items():
        if file_sha256(output / 'prepared' / path) != expected:
            raise ValueError('prepared data changed: ' + path)
    if (frozen['prepared_manifest_sha256'] != file_sha256(output / 'prepared/manifest.json')
            or frozen['resource_sha256'] != file_sha256(output / 'resource.json')):
        raise ValueError('prepared manifest or GPU identity changed')
    return frozen


def validate_gpu(output):
    physical = read_json(Path(output) / 'resource.json')['physical_gpu']
    if physical not in (3, 2, 0) or os.environ.get('CUDA_VISIBLE_DEVICES') != str(physical):
        raise ValueError('EX-071 requires exactly its fixed physical GPU; GPU1 is forbidden')
    if torch.cuda.device_count() != 1:
        raise ValueError('exactly one CUDA device must be visible')
    return dict(physical_gpu=physical, visible_devices=os.environ['CUDA_VISIBLE_DEVICES'],
                device_count=1, device_name=torch.cuda.get_device_name(0))


class TrainingClock:
    def __init__(self, output, *, start=False, time_fn=time.time):
        self.path = Path(output) / 'training-clock.json'
        self.time_fn = time_fn
        if not self.path.exists():
            if not start:
                raise FileNotFoundError('GPU preflight must establish the original clock')
            exclusive_json(self.path, dict(started_at=time_fn(), at=now(),
                maximum_seconds=CONFIG['maximum_seconds'], experiment='EX-071'))
        self.original = read_json(self.path)
        if self.original.get('maximum_seconds') != CONFIG['maximum_seconds']:
            raise ValueError('original training time limit changed')
        if self.original['started_at'] > time_fn() + 1:
            raise ValueError('training clock is in the future')
        self.identity = file_sha256(self.path)

    def elapsed(self):
        if file_sha256(self.path) != self.identity:
            raise ValueError('original training clock was modified')
        return max(0.0, self.time_fn() - self.original['started_at'])

    def remaining(self):
        return max(0.0, self.original['maximum_seconds'] - self.elapsed())

    def require(self, seconds=0):
        if self.remaining() <= seconds:
            raise BudgetExpired('the original 24-hour training clock has no time for this operation')


def update_budget(sample_seconds, n_train, elapsed_seconds):
    if (not sample_seconds or not all(math.isfinite(v) and v > 0 for v in sample_seconds)
            or n_train < 1 or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0):
        raise ValueError('invalid preflight timing or denominator')
    p95 = float(np.quantile(sample_seconds, 0.95, method='linear'))
    update_seconds = p95 * CONFIG['preflight_p95_margin'] * CONFIG['accumulation']
    available = max(0.0, CONFIG['maximum_seconds'] - elapsed_seconds
                    - CONFIG['validation_reserve_seconds'])
    epoch_limit = math.ceil(n_train / CONFIG['accumulation']) * CONFIG['epochs']
    updates = min(epoch_limit, math.floor(available / update_seconds))
    return dict(p95_sample_seconds=p95, estimated_update_seconds=update_seconds,
                timing_margin=CONFIG['preflight_p95_margin'], available_training_seconds=available,
                reserved_validation_seconds=CONFIG['validation_reserve_seconds'],
                maximum_epoch_updates=epoch_limit, planned_updates=updates,
                quarter_updates=sorted({math.ceil(updates * q)
                                        for q in CONFIG['checkpoint_fractions']}) if updates else [])


def representative_samples(records):
    """Deterministic extremes plus length quantiles for at most 32 samples."""
    for r in records:
        if (not isinstance(r.get('token_count'), int) or r['token_count'] <= 0
                or not isinstance(r.get('state_tokens'), int) or r['state_tokens'] <= 0):
            raise ValueError('prepare must retain strict encoder token_count/state_tokens')
    selected = {}
    def add(r):
        if len(selected) < CONFIG['preflight_samples']:
            selected.setdefault(r['sample_id'], r)
    by_id = lambda r: json_sha256([SEED, 'preflight', r['sample_id']])
    by_length = sorted(records, key=lambda r: (r['token_count'], by_id(r)))
    add(by_length[-1]); add(by_length[0])
    by_options = sorted(records, key=lambda r: (len(r['input']['questions']['action']['criteria']), by_id(r)))
    add(by_options[0]); add(by_options[-1])
    kinds = defaultdict(list)
    for r in records:
        kinds[r['decision_kind']].append(r)
    for kind in sorted(kinds):
        ordered = sorted(kinds[kind], key=lambda r: (r['token_count'], by_id(r)))
        add(ordered[-1]); add(ordered[0])
    for i in range(CONFIG['preflight_samples']):
        index = round(i * (len(by_length) - 1) / (CONFIG['preflight_samples'] - 1))
        add(by_length[index])
    for r in sorted(records, key=by_id):
        add(r)
        if len(selected) == min(len(records), CONFIG['preflight_samples']):
            break
    return list(selected.values())


def initial_cursor():
    return dict(epoch=0, index=0, updates=0, examples_seen=0, accumulation_count=0,
                accumulation_size=0, accumulated_loss=0.0)


def make_optimizer(policy):
    return torch.optim.AdamW([p for p in policy.parameters() if p.requires_grad],
        lr=CONFIG['learning_rate'], betas=tuple(CONFIG['betas']),
        weight_decay=CONFIG['weight_decay'])


def learning_rate_factor(completed, planned):
    if planned < 1:
        raise ValueError('scheduler needs a positive fixed update count')
    warmup = max(1, math.ceil(planned * 0.1))
    if completed < warmup:
        return (completed + 1) / warmup
    if planned == warmup:
        return 0.0
    progress = min(1.0, (completed - warmup) / (planned - warmup))
    return 0.5 * (1.0 + math.cos(math.pi * progress))


def make_scheduler(optimizer, planned):
    return torch.optim.lr_scheduler.LambdaLR(optimizer,
        lr_lambda=lambda completed: learning_rate_factor(completed, planned))


def _files(directory):
    return {str(p.relative_to(directory)): file_sha256(p)
            for p in sorted(Path(directory).rglob('*')) if p.is_file()}


def _same_state(a, b):
    """Exact checkpoint state comparison, including NumPy and tensor RNG."""
    if isinstance(a, torch.Tensor) and isinstance(b, torch.Tensor):
        return a.dtype == b.dtype and a.shape == b.shape and torch.equal(a.detach().cpu(), b.detach().cpu())
    if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
        return a.dtype == b.dtype and np.array_equal(a, b)
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_same_state(a[k], b[k]) for k in a)
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        return type(a) is type(b) and len(a) == len(b) and all(_same_state(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def save_checkpoint(policy, optimizer, scheduler, destination, *, cursor, frozen,
                    clock, base_fingerprints, stage):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    trainable = policy.trainable_fingerprints()
    if cursor['accumulation_count']:
        check_gradients(policy)
    # Captured before any serialization; saving is observational and must not
    # consume dropout RNG or silently reuse different partial gradients.
    gradients = {name: p.grad.detach().cpu().clone() for name, p in policy.named_parameters()
                 if p.requires_grad and p.grad is not None} if cursor['accumulation_count'] else {}
    state = dict(optimizer=optimizer.state_dict(), scheduler=scheduler.state_dict(),
                 rng=rng_state(), cursor=dict(cursor), gradients=gradients,
                 original_clock=clock.original, clock_sha256=clock.identity,
                 elapsed_seconds=clock.elapsed())
    if destination.exists():
        previous = verify_checkpoint(destination)
        if (previous['cursor'] != cursor or previous['trainable_fingerprints'] != trainable
                or previous['frozen_sha256'] != json_sha256(frozen)):
            raise FileExistsError('different complete checkpoint exists: ' + str(destination))
        existing_state = torch.load(destination / 'state.pt', map_location='cpu', weights_only=False)
        for key in state.keys() - {'elapsed_seconds'}:
            if not _same_state(state[key], existing_state[key]):
                raise FileExistsError('different checkpoint training state exists: ' + key)
        return destination
    temporary = Path(tempfile.mkdtemp(prefix='.' + destination.name + '-',
                                      dir=destination.parent))
    try:
        policy.backbone.save_pretrained(temporary / 'adapter', safe_serialization=True)
        torch.save({k: v.detach().cpu() for k, v in policy.head.state_dict().items()},
                   temporary / 'head.pt')
        # Store partial accumulated gradients so even a >15-minute optimizer
        # batch can checkpoint without replaying dropout or losing contributions.
        torch.save(state, temporary / 'state.pt')
        metadata = dict(at=now(), stage=stage, model_config=MODEL_CONFIG, config=CONFIG,
                        cursor=dict(cursor), original_clock=clock.original,
                        clock_sha256=clock.identity, elapsed_seconds=clock.elapsed(),
                        frozen_sha256=json_sha256(frozen), base_fingerprints=base_fingerprints,
                        trainable_fingerprints=trainable, partial_gradients=len(gradients))
        atomic_json(temporary / 'metadata.json', metadata)
        atomic_json(temporary / 'files.json', _files(temporary))
        for p in temporary.rglob('*'):
            if p.is_file():
                with p.open('rb') as f:
                    os.fsync(f.fileno())
        os.rename(temporary, destination)
        dirfd = os.open(destination.parent, os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination


def restore_training_state(policy, optimizer, scheduler, checkpoint, *, clock, frozen):
    metadata = verify_checkpoint(checkpoint)
    if (metadata['config'] != CONFIG or metadata['frozen_sha256'] != json_sha256(frozen)
            or metadata['clock_sha256'] != clock.identity
            or metadata['original_clock'] != clock.original):
        raise ValueError('resume configuration, data, or original clock changed')
    state = torch.load(Path(checkpoint) / 'state.pt', map_location='cpu', weights_only=False)
    if state['cursor'] != metadata['cursor'] or state['original_clock'] != clock.original:
        raise ValueError('checkpoint cursor or original clock evidence differs')
    optimizer.load_state_dict(state['optimizer'])
    scheduler.load_state_dict(state['scheduler'])
    gradients = state['gradients']
    expected = {name for name, p in policy.named_parameters() if p.requires_grad}
    if state['cursor']['accumulation_count'] and set(gradients) != expected:
        raise ValueError('partial optimizer batch lacks complete trainable gradients')
    if not state['cursor']['accumulation_count'] and gradients:
        raise ValueError('complete optimizer boundary carries partial gradients')
    for name, p in policy.named_parameters():
        if p.requires_grad:
            p.grad = gradients[name].to(p.device, dtype=p.dtype) if name in gradients else None
    restore_rng(state['rng'])
    return dict(state['cursor'])


def set_latest(output, checkpoint):
    path = Path(checkpoint).resolve()
    verify_checkpoint(path)
    atomic_json(Path(output) / 'training/latest.json',
                dict(path=str(path), checkpoint_sha256=checkpoint_identity(path)))


def latest(output):
    pointer = read_json(Path(output) / 'training/latest.json')
    path = Path(pointer['path'])
    if checkpoint_identity(path) != pointer['checkpoint_sha256']:
        raise ValueError('latest checkpoint pointer changed')
    verify_checkpoint(path)
    return path


def progress(output, stage, **values):
    memory = dict(max_allocated_bytes=0, max_reserved_bytes=0)
    if torch.cuda.is_initialized():
        memory = dict(max_allocated_bytes=torch.cuda.max_memory_allocated(),
                      max_reserved_bytes=torch.cuda.max_memory_reserved())
    atomic_json(Path(output) / stage / 'progress.json',
                dict(at=now(), pid=os.getpid(), stage=stage, **memory, **values))


def preflight(output):
    output = Path(output)
    frozen = freeze(output)
    if (output / 'preflight/report.json').exists():
        raise FileExistsError('GPU preflight already completed; implicit repetition is forbidden')
    if (output / 'preflight/attempt.json').exists():
        raise FileExistsError('GPU preflight was already attempted; preserve and resolve its failure first')
    records = prepared_records(output)['train']
    chosen = representative_samples(records)
    gpu = validate_gpu(output)
    clock = TrainingClock(output, start=True)
    exclusive_json(output / 'preflight/attempt.json', dict(at=now(), gpu=gpu,
                   sample_ids=[r['sample_id'] for r in chosen],
                   frozen_sha256=json_sha256(frozen), clock_sha256=clock.identity))
    seed_all()
    policy = Policy()
    base_before = policy.base_fingerprints()
    trainable_before = policy.trainable_fingerprints()
    checks = []
    policy.train()
    for r in chosen:
        clock.require(60)
        encoded = encode_input(r['input'], policy.tokenizer)
        if encoded.tokens != r['token_count'] or encoded.state_tokens != r['state_tokens']:
            raise ValueError('prepared length differs from the frozen encoder')
        policy.zero_grad(set_to_none=True)
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        started = time.perf_counter()
        loss = choice_loss(policy.logits(encoded), encoded.action_ids, r['label'])
        loss.backward()
        norm = check_gradients(policy)
        torch.cuda.synchronize()
        row = dict(sample_id=r['sample_id'], decision_kind=r['decision_kind'],
                   token_count=encoded.tokens, state_tokens=encoded.state_tokens,
                   candidates=len(encoded.action_ids), loss=float(loss.detach()),
                   gradient_norm=norm, seconds=time.perf_counter() - started,
                   allocated_bytes=torch.cuda.max_memory_allocated(),
                   reserved_bytes=torch.cuda.max_memory_reserved())
        checks.append(row)
        append_jsonl(output / 'preflight/samples.jsonl', row)
        progress(output, 'preflight', completed=len(checks), planned=len(chosen),
                 elapsed_seconds=clock.elapsed(), last_sample=row)
    policy.zero_grad(set_to_none=True)
    if base_before != policy.base_fingerprints() or trainable_before != policy.trainable_fingerprints():
        raise ValueError('forward/backward preflight unexpectedly changed weights')
    # Reset the initialization RNG after the dropout-only preflight. This is a
    # reproducible initial policy, not a warm start or an optimization update.
    budget = update_budget([r['seconds'] for r in checks], len(records), clock.elapsed())
    report = dict(passed=True, at=now(), gpu=gpu, samples=checks, optimizer_updates=0,
                  base_unchanged=True, trainable_unchanged=True,
                  initial_base_fingerprints=base_before,
                  initial_trainable_fingerprints=trainable_before,
                  original_clock=clock.original, clock_sha256=clock.identity,
                  frozen_sha256=json_sha256(frozen), elapsed_seconds=clock.elapsed(), **budget)
    atomic_json(output / 'preflight/report.json', report, immutable=True)
    progress(output, 'preflight', phase='complete', elapsed_seconds=clock.elapsed(),
             planned_updates=budget['planned_updates'])
    return report


def epoch_order(records, epoch):
    ordered = list(records)
    random.Random(f'{SEED}:records:{epoch}').shuffle(ordered)
    return ordered


def one_microbatch(policy, record, cursor):
    """Accumulate exactly one labelled observation; cursor points to the next."""
    body = permute_input(record['input'], sample_id=record['sample_id'], epoch=cursor['epoch'] + 1)
    encoded = encode_input(body, policy.tokenizer)
    value = choice_loss(policy.logits(encoded), encoded.action_ids, record['label'])
    (value / cursor['accumulation_size']).backward()
    cursor['index'] += 1
    cursor['examples_seen'] += 1
    cursor['accumulation_count'] += 1
    cursor['accumulated_loss'] += float(value.detach()) / cursor['accumulation_size']
    return encoded, float(value.detach())


def optimizer_step(policy, optimizer, scheduler, cursor):
    if cursor['accumulation_count'] != cursor['accumulation_size'] or not cursor['accumulation_count']:
        raise ValueError('optimizer update needs the complete accumulated batch')
    norm = check_gradients(policy)
    torch.nn.utils.clip_grad_norm_([p for p in policy.parameters() if p.requires_grad],
                                  CONFIG['gradient_clip'], error_if_nonfinite=True)
    used_lr = optimizer.param_groups[0]['lr']
    optimizer.step()
    scheduler.step()
    if any(not bool(torch.isfinite(p).all()) for p in policy.parameters() if p.requires_grad):
        raise FloatingPointError('nonfinite parameter after optimizer update')
    result = dict(loss=cursor['accumulated_loss'], observations=cursor['accumulation_count'],
                  gradient_norm=norm, learning_rate=used_lr)
    cursor['updates'] += 1
    cursor['accumulation_count'] = 0
    cursor['accumulation_size'] = 0
    cursor['accumulated_loss'] = 0.0
    optimizer.zero_grad(set_to_none=True)
    return result


@contextmanager
def stop_requested():
    state = {'signal': None}
    previous = {}
    def handler(number, frame):
        state['signal'] = number
    for number in (signal.SIGINT, signal.SIGTERM):
        previous[number] = signal.signal(number, handler)
    try:
        yield state
    finally:
        for number, value in previous.items():
            signal.signal(number, value)


def prediction_row(policy, record):
    encoded = encode_input(record['input'], policy.tokenizer)
    start = time.perf_counter()
    with torch.no_grad():
        logits = policy.logits(encoded)
        value = choice_loss(logits, encoded.action_ids, record['label'])
        probabilities = torch.softmax(logits, -1).cpu().tolist()
    chosen = encoded.action_ids[max(range(len(probabilities)), key=probabilities.__getitem__)]
    return dict(sample_id=record['sample_id'], replay_id=record['replay_id'],
                group_id=record['group_id'], decision_kind=record['decision_kind'],
                label_kind=record.get('label_kind', record['decision_kind']),
                tera_used=record['tera_used'], label=record['label'],
                label_tera=record['label'].endswith(':tera'),
                action_ids=list(encoded.action_ids), probabilities=probabilities,
                choice=chosen, nll=float(value.detach()), matched=chosen == record['label'],
                input_sha256=encoded.input_sha256, token_count=encoded.tokens,
                state_tokens=encoded.state_tokens, elapsed_seconds=time.perf_counter() - start)


def metrics(predictions):
    if not predictions:
        raise ValueError('cannot report metrics without evaluated observations')
    def summarize(values):
        return dict(observations=len(values), nll=float(np.mean([r['nll'] for r in values])),
                    action_match_rate=float(np.mean([r['matched'] for r in values])))
    report = {'all': summarize(predictions)}
    for field in ('decision_kind', 'label_kind', 'tera_used', 'label_tera'):
        groups = defaultdict(list)
        for r in predictions:
            value = r.get(field, r.get('label', '').endswith(':tera')) if field == 'label_tera' else r[field]
            groups[str(value).lower() if isinstance(value, bool) else str(value)].append(r)
        report['by_' + field] = {key: summarize(value) for key, value in sorted(groups.items())}
    return report


def validation(policy, records, path, *, clock, minimum_seconds=60, output=None):
    path = Path(path)
    complete = path.with_suffix('.complete.json')
    if complete.exists():
        receipt = read_json(complete)
        if file_sha256(path) != receipt['predictions_sha256']:
            raise ValueError('saved validation predictions changed')
        saved = rows(path)
        if [r['sample_id'] for r in saved] != [r['sample_id'] for r in records]:
            raise ValueError('saved validation sample identities differ')
        return receipt['metrics']
    if path.exists():
        # Validation is allowed to resume from its completed rows: no partial
        # result is used for selection, and the checkpoint identity is fixed.
        result = rows(path)
        if [r['sample_id'] for r in result] != [r['sample_id'] for r in records[:len(result)]]:
            raise ValueError('partial validation order differs')
    else:
        result = []
    policy.eval()
    for r in records[len(result):]:
        clock.require(minimum_seconds)
        prediction = prediction_row(policy, r)
        append_jsonl(path, prediction)
        result.append(prediction)
        if output is not None:
            progress(output, 'training', phase='validation', validation_file=path.name,
                     completed=len(result), planned=len(records), elapsed_seconds=clock.elapsed())
    report = metrics(result)
    atomic_json(complete, dict(at=now(), observations=len(result), metrics=report,
                              predictions_sha256=file_sha256(path)), immutable=True)
    return report


def _trainable_changed(initial, final):
    lora = [name for name in initial if 'lora_' in name]
    head = [name for name in initial if name.startswith('model.head.')]
    return dict(lora_changed=bool(lora) and any(initial[k] != final[k] for k in lora),
                head_changed=bool(head) and any(initial[k] != final[k] for k in head))


def _selection(output, report, *, stopped_reason=None):
    output = Path(output)
    candidates = []
    for update in report['quarter_updates']:
        cp = output / 'training' / f'checkpoint-{update:07d}'
        complete = output / 'training' / f'validation-{update:07d}.complete.json'
        if cp.exists() and complete.exists():
            metadata = verify_checkpoint(cp)
            receipt = read_json(complete)
            predictions = complete.with_name(complete.name.replace('.complete.json', '.jsonl'))
            if receipt['predictions_sha256'] != file_sha256(predictions):
                raise ValueError('checkpoint selection validation changed')
            candidates.append((receipt['metrics']['all']['nll'], update, cp, metadata))
    if not candidates:
        raise BudgetExpired('no registered trained checkpoint has a complete validation result')
    nll, update, cp, metadata = min(candidates, key=lambda item: (item[0], item[1]))
    initial = verify_checkpoint(output / 'training/initial')
    changes = _trainable_changed(initial['trainable_fingerprints'], metadata['trainable_fingerprints'])
    if not all(changes.values()):
        raise ValueError('selected checkpoint must update both LoRA and pointer head')
    result = dict(at=now(), checkpoint=str(cp.resolve()), selected_update=update,
                  selected_validation_nll=nll, planned_updates=report['planned_updates'],
                  completed_checkpoint_updates=[value[1] for value in candidates],
                  completed_planned_training=report['planned_updates'] in [value[1] for value in candidates],
                  stopped_reason=stopped_reason, validation_nll_by_update={str(u): n for n, u, _, _ in candidates},
                  base_unchanged=True, **changes)
    atomic_json(output / 'training/selection.json', result, immutable=True)
    return result


def train(output, resume=False):
    output = Path(output)
    frozen = assert_frozen(output)
    if (output / 'training/selection.json').exists():
        return read_json(output / 'training/selection.json')
    report = read_json(output / 'preflight/report.json')
    if not report['passed'] or report['frozen_sha256'] != json_sha256(frozen):
        raise ValueError('successful frozen preflight is required')
    if report['planned_updates'] < 1:
        raise BudgetExpired('preflight predicts zero updates inside the approved budget')
    validate_gpu(output)
    clock = TrainingClock(output)
    clock.require(60)
    records = prepared_records(output)
    training, heldout = records['train'], records['validation']
    seed_all()
    checkpoint = latest(output) if resume else None
    if not resume and (output / 'training/latest.json').exists():
        raise FileExistsError('a training checkpoint exists; use the explicit resume path')
    policy = Policy(checkpoint=checkpoint)
    optimizer = make_optimizer(policy)
    scheduler = make_scheduler(optimizer, report['planned_updates'])
    base = policy.loaded_base_fingerprints or policy.base_fingerprints()
    if base != report['initial_base_fingerprints']:
        raise ValueError('training Base differs from preflight')
    if resume:
        cursor = restore_training_state(policy, optimizer, scheduler, checkpoint,
                                        clock=clock, frozen=frozen)
    else:
        if policy.trainable_fingerprints() != report['initial_trainable_fingerprints']:
            raise ValueError('fresh LoRA/head initialization is not reproducible')
        cursor = initial_cursor()
        checkpoint = save_checkpoint(policy, optimizer, scheduler, output / 'training/initial',
            cursor=cursor, frozen=frozen, clock=clock, base_fingerprints=base, stage='initial')
        set_latest(output, checkpoint)
    # A resume at a quarter checkpoint first finishes that checkpoint's
    # validation. Otherwise it might pass a missing model-selection result.
    if cursor['updates'] == 0:
        if cursor['examples_seen'] != 0 and not (output / 'training/validation-initial.complete.json').exists():
            raise ValueError('initial validation is missing after training has begun')
        validation(policy, heldout, output / 'training/validation-initial.jsonl',
                   clock=clock, output=output)
    elif cursor['updates'] in report['quarter_updates'] and not cursor['accumulation_count']:
        validation(policy, heldout, output / 'training' / f'validation-{cursor["updates"]:07d}.jsonl',
                   clock=clock, output=output)
    last_save = time.time()
    ordered = epoch_order(training, cursor['epoch'])
    stopped = None
    with stop_requested() as requested:
        try:
            while cursor['updates'] < report['planned_updates']:
                clock.require(max(60.0, report['p95_sample_seconds'] * CONFIG['preflight_p95_margin']))
                if requested['signal'] is not None:
                    stopped = 'signal:' + str(requested['signal'])
                    break
                if cursor['index'] >= len(ordered):
                    if cursor['accumulation_count']:
                        raise ValueError('partial gradient batch crossed an epoch boundary')
                    cursor['epoch'] += 1
                    cursor['index'] = 0
                    ordered = epoch_order(training, cursor['epoch'])
                if cursor['epoch'] >= CONFIG['epochs']:
                    raise ValueError('frozen update count would exceed the three-epoch bound')
                if not cursor['accumulation_count']:
                    cursor['accumulation_size'] = min(CONFIG['accumulation'], len(ordered) - cursor['index'])
                    optimizer.zero_grad(set_to_none=True)
                policy.train()
                record = ordered[cursor['index']]
                started = time.perf_counter()
                encoded, sample_loss = one_microbatch(policy, record, cursor)
                progress(output, 'training', phase='accumulation', cursor=cursor,
                         sample_id=record['sample_id'], token_count=encoded.tokens,
                         sample_loss=sample_loss, elapsed_seconds=clock.elapsed(),
                         planned_updates=report['planned_updates'])
                if cursor['accumulation_count'] == cursor['accumulation_size']:
                    update = optimizer_step(policy, optimizer, scheduler, cursor)
                    append_jsonl(output / 'training/updates.jsonl',
                        dict(at=now(), cursor=dict(cursor), elapsed_seconds=clock.elapsed(), **update))
                    if cursor['updates'] in report['quarter_updates']:
                        if policy.base_fingerprints() != base:
                            raise ValueError('frozen Base changed during training')
                        checkpoint = save_checkpoint(policy, optimizer, scheduler,
                            output / 'training' / f'checkpoint-{cursor["updates"]:07d}',
                            cursor=cursor, frozen=frozen, clock=clock,
                            base_fingerprints=base, stage='quarter')
                        set_latest(output, checkpoint)
                        last_save = time.time()
                        validation(policy, heldout, output / 'training' / f'validation-{cursor["updates"]:07d}.jsonl',
                                   clock=clock, output=output)
                if time.time() - last_save >= CONFIG['resume_interval_seconds']:
                    checkpoint = save_checkpoint(policy, optimizer, scheduler,
                        output / 'training' / f'resume-{cursor["updates"]:07d}-{cursor["examples_seen"]:09d}',
                        cursor=cursor, frozen=frozen, clock=clock,
                        base_fingerprints=base, stage='periodic_resume')
                    set_latest(output, checkpoint)
                    last_save = time.time()
                progress(output, 'training', phase='train', cursor=cursor,
                         elapsed_seconds=clock.elapsed(), planned_updates=report['planned_updates'],
                         last_sample_seconds=time.perf_counter() - started)
        except BudgetExpired as exc:
            stopped = str(exc)
        finally:
            if stopped is not None or requested['signal'] is not None:
                checkpoint = save_checkpoint(policy, optimizer, scheduler,
                    output / 'training' / f'interrupted-{cursor["updates"]:07d}-{cursor["examples_seen"]:09d}',
                    cursor=cursor, frozen=frozen, clock=clock,
                    base_fingerprints=base, stage='interrupted')
                set_latest(output, checkpoint)
                atomic_json(output / 'training' / f'interruption-{time.time_ns()}.json',
                    dict(at=now(), reason=stopped, cursor=cursor, checkpoint=str(checkpoint),
                         elapsed_seconds=clock.elapsed()), immutable=True)
    if stopped and stopped.startswith('signal:'):
        return dict(status='interrupted', reason=stopped, cursor=cursor,
                    checkpoint=str(checkpoint), original_clock=clock.original)
    if policy.base_fingerprints() != base:
        raise ValueError('frozen Base changed during training')
    result = _selection(output, report, stopped_reason=stopped)
    progress(output, 'training', phase='complete' if result['completed_planned_training'] else 'budget_exhausted',
             cursor=cursor, selection=result, elapsed_seconds=clock.elapsed())
    return result


def evaluation_lock(output):
    output = Path(output)
    frozen = assert_frozen(output)
    lock = read_json(output / 'evaluation-lock.json')
    if (lock['frozen_sha256'] != json_sha256(frozen)
            or lock['selection_sha256'] != file_sha256(output / 'training/selection.json')
            or lock['serving_parity_sha256'] != file_sha256(output / 'reload/serving-parity.json')):
        raise ValueError('model selection, serving parity or frozen input changed after test lock')
    for name, path in lock['model_checkpoints'].items():
        verify_checkpoint(path)
        if checkpoint_identity(path) != lock['checkpoint_sha256'][name]:
            raise ValueError('locked checkpoint changed: ' + name)
    return lock


def reload_and_lock(output):
    """Reload both models and compare saved validation through actual HTTP."""
    from .serving import verify_saved_probabilities
    output = Path(output)
    frozen = assert_frozen(output)
    if (output / 'evaluation-lock.json').exists():
        return evaluation_lock(output)
    selection = read_json(output / 'training/selection.json')
    clock = TrainingClock(output)
    validate_gpu(output)
    samples = {r['sample_id']: r for r in prepared_records(output)['validation']}
    checkpoints = {'initial': str((output / 'training/initial').resolve()),
                   'selected': selection['checkpoint']}
    prediction_paths = {'initial': output / 'training/validation-initial.jsonl',
                        'selected': output / 'training' / f'validation-{selection["selected_update"]:07d}.jsonl'}
    parity = {}
    for name, checkpoint in checkpoints.items():
        reference = rows(prediction_paths[name])
        # The saved order is already balanced by group. Pick its first eight;
        # never consult test examples for loading or serving qualification.
        reference = reference[:8]
        receipt_path = output / 'reload' / f'parity-{name}.json'
        if receipt_path.exists():
            previous = read_json(receipt_path)
            if (previous.get('passed') is not True
                    or previous['checkpoint_sha256'] != checkpoint_identity(checkpoint)
                    or [r['sample_id'] for r in previous['samples']] != [r['sample_id'] for r in reference]
                    or [r['input_sha256'] for r in previous['samples']] != [r['input_sha256'] for r in reference]
                    or [r['saved_probabilities'] for r in previous['samples']] != [r['probabilities'] for r in reference]):
                raise ValueError('saved serving parity identity changed')
            parity[name] = previous
            continue
        clock.require(60)
        policy = Policy(checkpoint=checkpoint)
        saved = verify_checkpoint(checkpoint)
        policy.eval()
        if policy.loaded_base_fingerprints != saved['base_fingerprints']:
            raise ValueError('reloaded frozen Base differs from the saved checkpoint')
        parity[name] = verify_saved_probabilities(policy, name, checkpoint,
            [samples[r['sample_id']] for r in reference], reference, clock=clock)
        if policy.trainable_fingerprints() != saved['trainable_fingerprints']:
            raise ValueError('serving verification changed trainable weights')
        atomic_json(receipt_path, parity[name], immutable=True)
        del policy
        gc.collect()
        torch.cuda.empty_cache()
    receipt = dict(at=now(), passed=True, models=parity, precision=PRECISION,
                   source_sha256=json_sha256(frozen['sources']),
                   checkpoint_sha256={name: checkpoint_identity(cp) for name, cp in checkpoints.items()})
    atomic_json(output / 'reload/serving-parity.json', receipt, immutable=True)
    lock = dict(at=now(), frozen_sha256=json_sha256(frozen),
                selection_sha256=file_sha256(output / 'training/selection.json'),
                serving_parity_sha256=file_sha256(output / 'reload/serving-parity.json'),
                model_checkpoints=checkpoints,
                checkpoint_sha256={name: checkpoint_identity(cp) for name, cp in checkpoints.items()},
                test_sha256=frozen['data_files']['test.jsonl'], test_model_evaluations=1,
                planned_test_observations=frozen['denominators']['test'])
    atomic_json(output / 'evaluation-lock.json', lock, immutable=True)
    return lock


def evaluate(output):
    output = Path(output)
    validate_gpu(output)
    lock = reload_and_lock(output)
    records = prepared_records(output)['test']
    if (output / 'evaluation/report.json').exists():
        existing = read_json(output / 'evaluation/report.json')
        for name in lock['model_checkpoints']:
            complete = read_json(output / 'evaluation' / f'completed-{name}.json')
            if complete['predictions_sha256'] != file_sha256(output / 'evaluation' / f'test-{name}.jsonl'):
                raise ValueError('completed test predictions changed')
        return existing
    reports = {}
    for name, checkpoint in lock['model_checkpoints'].items():
        reservation = output / 'evaluation' / f'reservation-{name}.json'
        complete = output / 'evaluation' / f'completed-{name}.json'
        prediction_path = output / 'evaluation' / f'test-{name}.jsonl'
        if complete.exists():
            receipt = read_json(complete)
            if receipt['predictions_sha256'] != file_sha256(prediction_path):
                raise ValueError('completed test predictions changed')
            reports[name] = receipt['metrics']
            continue
        if reservation.exists():
            raise RuntimeError('this model already attempted its one test pass: ' + name)
        exclusive_json(reservation, dict(at=now(), model=name, model_evaluation_number=1,
            checkpoint=checkpoint, checkpoint_sha256=lock['checkpoint_sha256'][name],
            evaluation_lock_sha256=file_sha256(output / 'evaluation-lock.json')))
        policy = Policy(checkpoint=checkpoint)
        policy.eval()
        saved = verify_checkpoint(checkpoint)
        before = policy.trainable_fingerprints()
        predictions = []
        for r in records:
            prediction = prediction_row(policy, r)
            append_jsonl(prediction_path, prediction)
            predictions.append(prediction)
            progress(output, 'evaluation', phase='test', model=name,
                     completed=len(predictions), planned=len(records))
        if (policy.trainable_fingerprints() != before
                or policy.base_fingerprints() != saved['base_fingerprints']):
            raise ValueError('test evaluation changed model parameters')
        report = metrics(predictions)
        atomic_json(complete, dict(at=now(), model=name, observations=len(records),
                    metrics=report, predictions_sha256=file_sha256(prediction_path),
                    base_unchanged=True, trainable_unchanged=True), immutable=True)
        reports[name] = report
        del policy
        gc.collect()
        torch.cuda.empty_cache()
    result = dict(at=now(), metrics=reports, observations_per_model=len(records),
                  interpretation='인간 선택 재현 지표이며 실배틀 승률 또는 행동가치가 아님',
                  nll_difference=reports['selected']['all']['nll'] - reports['initial']['all']['nll'],
                  action_match_rate_difference=reports['selected']['all']['action_match_rate']
                    - reports['initial']['all']['action_match_rate'])
    atomic_json(output / 'evaluation/report.json', result, immutable=True)
    progress(output, 'evaluation', phase='complete', models=list(reports), observations_per_model=len(records))
    return result
