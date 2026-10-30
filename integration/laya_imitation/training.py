"""EX-118 (v1) / EX-121 (v2) / EX-124 / EX-126 / EX-128 (v3) / EX-130 (v4) / EX-132 (outcome weights) / EX-136 (v5) /
EX-141 (v6s) / EX-142 (v6h, 2048 tokens) training: preflight, 3 epochs with per-epoch validation, selection,
calibration.

Reuses laya 0.4.13's own loop (`train_model`), item building, checkpoint IO and temperature fit.
No resume: a failure keeps its records and needs a new approval to run again.
"""
from __future__ import annotations
import json
import os
import shutil
import sys
import time
import traceback

from . import config as c
from .resources import gpu
from .storage import append_jsonl, atomic, digest, read, sha, source_identity, verify_seal


class BudgetExceeded(RuntimeError):
    pass


class Spec:
    """Which experiment a run belongs to. EX-118 (v1) is the default; EX-121 (v2) differs only here."""

    def __init__(self, experiment, dataset, out, head, key, max_exclusion_rate=0.0, extra_train=None,
                 gpu=(c.GPU_INDEX, c.GPU_UUID), hours=c.TRAINING_HOURS, weights=None, same_split_as=None,
                 max_len=c.TOKEN_LIMIT):
        # `hours=None`: no training time limit (EX-141/142, user instruction 2026-10-29).
        self.experiment, self.dataset, self.out, self.head, self.key = experiment, dataset, out, head, key
        self.max_exclusion_rate, self.extra_train, self.gpu, self.hours = max_exclusion_rate, extra_train, gpu, hours
        self.weights, self.same_split_as, self.max_len = weights, same_split_as, max_len


EX118 = Spec('EX-118', c.DATASET, c.RUN_TRAINING, c.HEAD_LIMIT, 'ex118')
EX121 = Spec('EX-121', c.V2_DATASET, c.RUN_V2_TRAINING, c.V2_HEAD_LIMIT, 'ex121', max_exclusion_rate=0.005)
# EX-124: EX-121's data plus the Tera knowledge rows (training only), on GPU1.
EX124 = Spec('EX-124', c.V2_DATASET, c.RUN_TERA_TRAINING, c.V2_HEAD_LIMIT, 'ex124', max_exclusion_rate=0.005,
             extra_train=c.TERA_KNOWLEDGE / 'train.jsonl', gpu=(c.GPU1_INDEX, c.GPU1_UUID), hours=c.TERA_TRAINING_HOURS)
# EX-126: EX-124's rows plus the effect knowledge rows (training only), on GPU2.
EX126 = Spec('EX-126', c.V2_DATASET, c.RUN_EFFECT_TRAINING, c.V2_HEAD_LIMIT, 'ex126', max_exclusion_rate=0.005,
             extra_train=(c.TERA_KNOWLEDGE / 'train.jsonl', c.EFFECT_KNOWLEDGE / 'train.jsonl'),
             gpu=(c.GPU2_INDEX, c.GPU2_UUID), hours=c.EFFECT_TRAINING_HOURS)

# EX-128: EX-124's rows and settings with the action rows rendered by v3, on GPU0.
EX128 = Spec('EX-128', c.V3_DATASET, c.RUN_V3_TRAINING, c.V2_HEAD_LIMIT, 'ex128', max_exclusion_rate=0.005,
             extra_train=c.TERA_KNOWLEDGE / 'train.jsonl', hours=c.V3_TRAINING_HOURS)
EX130 = Spec('EX-130', c.V4_DATASET, c.RUN_V4_TRAINING, c.V2_HEAD_LIMIT, 'ex130', max_exclusion_rate=0.005,
             extra_train=c.TERA_KNOWLEDGE / 'train.jsonl', gpu=(c.GPU1_INDEX, c.GPU1_UUID), hours=c.V4_TRAINING_HOURS)
# EX-136 (D-195): EX-130's settings with the action rows rendered by v5 (opponent item state, counters), on GPU0.
EX136 = Spec('EX-136', c.V5_DATASET, c.RUN_V5_TRAINING, c.V2_HEAD_LIMIT, 'ex136', max_exclusion_rate=0.005,
             extra_train=c.TERA_KNOWLEDGE / 'train.jsonl', hours=c.V5_TRAINING_HOURS)
# EX-141 / EX-142 (D-198): EX-136's settings with the action rows rendered by v6s (GPU0) / v6h at 2048 tokens (GPU1),
# trained at the same time, no time limit.
EX141 = Spec('EX-141', c.V6S_DATASET, c.RUN_V6S_TRAINING, c.V2_HEAD_LIMIT, 'ex141', max_exclusion_rate=0.005,
             extra_train=c.TERA_KNOWLEDGE / 'train.jsonl', hours=None)
EX142 = Spec('EX-142', c.V6H_DATASET, c.RUN_V6H_TRAINING, c.V2_HEAD_LIMIT, 'ex142', max_exclusion_rate=0.005,
             extra_train=c.TERA_KNOWLEDGE / 'train.jsonl', gpu=(c.GPU1_INDEX, c.GPU1_UUID), hours=None,
             max_len=c.V6H_TOKEN_LIMIT)
# EX-132: EX-124's rows, split and settings; imitation train rows weighted by the replay outcome (D-193), on GPU0.
EX132 = Spec('EX-132', c.V2_DATASET, c.RUN_WEIGHTED_TRAINING, c.V2_HEAD_LIMIT, 'ex132', max_exclusion_rate=0.005,
             extra_train=c.TERA_KNOWLEDGE / 'train.jsonl', hours=c.WEIGHTED_TRAINING_HOURS,
             weights=c.OUTCOME_WEIGHTS, same_split_as=c.RUN_TERA_TRAINING)


def extras(spec):
    """`extra_train` as a tuple: one path (EX-124) or several knowledge sets (EX-126)."""
    if spec.extra_train is None:
        return ()
    return tuple(spec.extra_train) if isinstance(spec.extra_train, (tuple, list)) else (spec.extra_train,)


def weigh_items(rows, items, weights):
    """Scale each item's target by its row weight; soft-CE is linear in the target, so the row's loss scales too."""
    missing = [r['sample_id'] for r in rows if r['sample_id'] not in weights]
    if missing:
        raise ValueError('%d rows have no outcome weight (first %r)' % (len(missing), missing[:5]))
    for row, item in zip(rows, items):
        item['target'] = [weights[row['sample_id']] * v for v in item['target']]
    return items


def _items(tok, path, max_len, head):
    from laya.train import items_from_rows, read_jsonl
    rows = read_jsonl(str(path))
    items, skipped = items_from_rows(tok, rows, max_len, head)
    if skipped or len(items) != len(rows):
        raise ValueError('rows not usable by laya: %s %r' % (path.name, skipped))
    return rows, items


def _metrics(records, temperature=None, by_options=None):
    from laya.train import evaluate_records
    m = evaluate_records(records, temperature, by_options)
    return {k: m[k] for k in ('items', 'loss', 'accuracy', 'mean_confidence', 'ece', 'brier')}


def _check_inputs(spec=EX118):
    bad = verify_seal(spec.dataset)
    validation = read(spec.dataset / 'validation.json')
    if spec is EX118:
        failed = not validation['ex089_disjoint'] or validation['token_budget_exclusions']
    else:
        failed = validation['exclusion_rate'] > spec.max_exclusion_rate
    for path in extras(spec):
        if verify_seal(path.parent):
            raise ValueError('extra training rows seal failed: %s' % path.parent)
    if spec.weights is not None and verify_seal(spec.weights):
        raise ValueError('outcome weights seal failed: %s' % spec.weights)
    if bad or failed:
        raise ValueError('dataset seal/validation failed: %r %r' % (bad, validation))
    expected = dict(line.split()[::-1] for line in (c.MODEL_DIR / 'checksums.sha256').read_text().splitlines())
    if any(sha(c.MODEL_DIR / name) != digest for name, digest in expected.items()):
        raise ValueError('base checkpoint hash mismatch')


def _freeze(out, spec=EX118):
    from integration.project_context.registry import freeze_document, resolve_record
    protocol = out / 'protocol'
    freeze_document(resolve_record(spec.experiment), protocol / (spec.experiment + '.md'))
    atomic(out / 'source/identity.json', source_identity(), immutable=True)
    atomic(out / 'source/dataset-manifest.json', read(spec.dataset / 'manifest.json'), immutable=True)
    paths = extras(spec)
    for path in paths:
        name = 'extra-train-manifest.json' if len(paths) == 1 else 'extra-train-manifest-%s.json' % path.parent.parent.name
        atomic(out / 'source' / name, read(path.parent / 'manifest.json'), immutable=True)
    if spec.weights is not None:
        atomic(out / 'source/outcome-weights-manifest.json', read(spec.weights / 'manifest.json'), immutable=True)
    extra_train = str(spec.extra_train) if len(paths) <= 1 else [str(p) for p in paths]
    atomic(protocol / 'train-config.json', dict(_train(spec), base=str(c.MODEL_DIR), revision=c.MODEL_REVISION,
                                               hours=spec.hours, extra_train=extra_train,
                                               weights=str(spec.weights) if spec.weights else None), immutable=True)


def _train(spec):
    return dict(c.TRAIN, head_max_len=spec.head, max_len=spec.max_len)


def preflight(out, device, spec=EX118):
    """256 rows x 2 epochs: loss must fall; save -> reload must reproduce the logits."""
    import torch
    from laya.train import TrainConfig, calibration_records, load_checkpoint, save_checkpoint, train_model
    model, tok, cfg = load_checkpoint(str(c.MODEL_DIR))
    model.to(device)
    from laya.train import items_from_rows
    head = spec.head
    with open(spec.dataset / 'train.jsonl') as f:
        rows = [json.loads(next(f)) for _ in range(256)]
    small, skipped = items_from_rows(tok, rows, spec.max_len, head)
    if skipped or len(small) != 256:
        raise ValueError('preflight rows not usable: %r' % skipped)
    if spec.weights is not None:
        from .outcome_weights import load
        small = weigh_items(rows, small, load(spec.weights))
    config = TrainConfig(**dict(_train(spec), epochs=2, log_every=0))
    started = time.time()
    history = train_model(model, tok, small, config, device, spec.max_len, head)
    path = out / 'preflight/checkpoint'
    save_checkpoint(model, tok, dict(cfg, max_len=spec.max_len, head_max_len=head), str(path))
    # Round only the persistent tensors the checkpoint stores (fp16); `.half()` on the module would
    # also round non-persistent RoPE buffers that a reload recomputes in fp32 (diagnostics/preflight-v1).
    model.load_state_dict({k: v.half().float() for k, v in model.state_dict().items()})
    a = calibration_records(model, tok, small[:32], device, spec.max_len, head)
    again, _, _ = load_checkpoint(str(path))
    again.to(device)
    b = calibration_records(again, tok, small[:32], device, spec.max_len, head)
    diff = max(float(abs(x[1] - y[1]).max()) for x, y in zip(a, b))
    result = dict(history=history, loss_fell=history[-1] < history[0], reload_max_abs_logit_diff=diff,
                  reload_ok=diff < 1e-3, seconds=round(time.time() - started, 1),
                  peak_allocated_gib=round(torch.cuda.max_memory_allocated() / 2**30, 3))
    atomic(out / 'preflight/result.json', result, immutable=True)
    shutil.rmtree(path)
    del model, again
    torch.cuda.empty_cache()
    if not (result['loss_fell'] and result['reload_ok']):
        raise RuntimeError('preflight failed: %r' % result)
    return result


def train(out, device, clock, spec=EX118):
    import torch
    from laya.calibrate import fit_temperature_map
    from laya.train import (TrainConfig, calibration_records, load_checkpoint, save_checkpoint,
                            split_calibration, train_model)
    head = spec.head
    model, tok, cfg = load_checkpoint(str(c.MODEL_DIR))
    model.to(device)
    rows, items = _items(tok, spec.dataset / 'train.jsonl', spec.max_len, head)
    _, val = _items(tok, spec.dataset / 'validation.jsonl', spec.max_len, head)
    config = TrainConfig(**_train(spec))
    for row, item in zip(rows, items):
        item['sample_id'] = row['sample_id']
    train_items, calib_items = split_calibration(items, config.calib_max, config.calib_frac, config.calib_seed)
    weighted = None
    if spec.weights is not None:
        # After the split: calibration (and validation) keep EX-124's unit targets.
        from .outcome_weights import load
        weights = load(spec.weights)
        train_items = weigh_items([dict(sample_id=it['sample_id']) for it in train_items], train_items, weights)
        weighted = dict(rows=len(train_items), mean=sum(weights[it['sample_id']] for it in train_items) / len(train_items),
                        calibration_ids_sha256=digest([it['sample_id'] for it in calib_items]))
    extra, by_source = [], {}
    for path in extras(spec):
        # Calibration stays imitation-only (same rows as EX-121); knowledge rows only join training.
        _, items_ = _items(tok, path, spec.max_len, head)
        extra += items_
        by_source[path.parent.parent.name] = len(items_)
    train_items = train_items + extra
    split = dict(train=len(train_items), calibration=len(calib_items), validation=len(val), extra_train=len(extra))
    if len(by_source) > 1:
        split['extra_train_by_source'] = by_source
    if weighted is not None:
        split['outcome_weights'] = weighted
    if spec.same_split_as is not None:
        base = read(spec.same_split_as / 'split.json')
        if any(base[k] != split[k] for k in ('train', 'calibration', 'validation', 'extra_train')):
            raise ValueError('split differs from %s: %r vs %r' % (spec.same_split_as.name, split, base))
    atomic(out / 'split.json', split, immutable=True)
    base_cfg = dict(cfg, max_len=spec.max_len, head_max_len=head)
    records = calibration_records(model, tok, val, device, spec.max_len, head)
    append_jsonl(out / 'validation-curve.jsonl', dict(epoch=0, raw=_metrics(records, 1.0),
                                                     shipped=_metrics(records, cfg.get('temperature'),
                                                                      cfg.get('temperature_by_options'))))

    def on_epoch_end(epoch, mean_loss):
        if spec.hours is not None and time.time() - clock > spec.hours * 3600:
            raise BudgetExceeded('training budget exceeded after epoch %d' % (epoch + 1))
        path = out / 'checkpoints' / ('epoch-%d' % (epoch + 1))
        save_checkpoint(model, tok, base_cfg, str(path))
        recs = calibration_records(model, tok, val, device, spec.max_len, head)
        model.train()
        row = dict(epoch=epoch + 1, train_loss=mean_loss, raw=_metrics(recs, 1.0), seconds=round(time.time() - clock),
                   peak_allocated_gib=round(torch.cuda.max_memory_allocated() / 2**30, 3))
        append_jsonl(out / 'validation-curve.jsonl', row)
        atomic(out / 'status.json', dict(stage='training', epoch=epoch + 1, of=config.epochs, at=time.time()))

    history = train_model(model, tok, train_items, config, device, spec.max_len, head,
                          on_epoch_end=on_epoch_end)
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    epochs = [r for r in curve if r['epoch'] > 0]
    best = min(epochs, key=lambda r: (r['raw']['loss'], r['epoch']))
    del model
    torch.cuda.empty_cache()
    model, tok, cfg = load_checkpoint(str(out / 'checkpoints' / ('epoch-%d' % best['epoch'])))
    model.to(device)
    calib = calibration_records(model, tok, calib_items, device, spec.max_len, head)
    fitted = fit_temperature_map(calib)
    selected = dict(cfg, fine_tuned=True, temperature=fitted['temperature'])
    selected.pop('temperature_by_options', None)
    if fitted['temperature_by_options']:
        selected['temperature_by_options'] = fitted['temperature_by_options']
    selected['training'] = dict(cfg.get('training') or {}, **{spec.key: dict(
        selected_epoch=best['epoch'], history=history,
        config={k: list(v) if isinstance(v, tuple) else v for k, v in _train(spec).items()})})
    save_checkpoint(model, tok, selected, str(out / 'checkpoints/selected'))
    recs = calibration_records(model, tok, val, device, spec.max_len, head)
    selection = dict(selected_epoch=best['epoch'], rule='min validation raw NLL, earlier epoch on ties',
                     calibration_items=len(calib), temperature=fitted['temperature'],
                     temperature_by_options=fitted['temperature_by_options'],
                     validation_selected_calibrated=_metrics(recs, fitted['temperature'],
                                                             fitted['temperature_by_options']),
                     checkpoint_sha256={p.name: sha(p) for p in sorted((out / 'checkpoints/selected').rglob('*'))
                                        if p.is_file()})
    atomic(out / 'selection.json', selection, immutable=True)
    return selection


def run(preflight_only=False, spec=EX118):
    out = spec.out
    if (out / 'status.json').exists() and read(out / 'status.json')['stage'] != 'preflight-passed':
        raise RuntimeError('%s run already started (%s); no automatic re-run' % (spec.experiment,
                                                                               read(out / 'status.json')))
    _check_inputs(spec)
    out.mkdir(parents=True, exist_ok=True)
    with gpu(*spec.gpu) as (env, device_info):
        os.environ.update(env)
        import torch
        device = torch.device('cuda')
        if not (out / 'protocol' / (spec.experiment + '.md')).exists():
            _freeze(out, spec)
            atomic(out / 'gpu-identity.json', dict(device_info, visible=torch.cuda.get_device_name(0)), immutable=True)
        try:
            if not (out / 'preflight/result.json').exists():
                atomic(out / 'status.json', dict(stage='preflight', at=time.time()))
                preflight(out, device, spec)
                atomic(out / 'status.json', dict(stage='preflight-passed', at=time.time()))
            if preflight_only:
                return
            clock = time.time()
            atomic(out / 'clock.json', dict(first_started=clock), immutable=True)
            atomic(out / 'status.json', dict(stage='training', epoch=0, at=clock))
            selection = train(out, device, clock, spec)
            atomic(out / 'status.json', dict(stage='trained', selected_epoch=selection['selected_epoch'],
                                             seconds=round(time.time() - clock), at=time.time()))
        except BaseException as error:
            atomic(out / 'status.json', dict(stage='failed', error=type(error).__name__, detail=str(error),
                                             traceback=traceback.format_exc(), at=time.time()))
            raise


if __name__ == '__main__':
    run(preflight_only='--preflight-only' in sys.argv)
