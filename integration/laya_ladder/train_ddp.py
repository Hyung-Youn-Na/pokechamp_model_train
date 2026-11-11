"""EX-167 (D-208): EX-161's v10 training on GPU0-3 with DDP, laya 0.4.13's encoding, loss and checkpoint IO.

`python -m integration.laya_ladder.train_ddp {check,measure,train} ...` holds the four pinned GPUs (idle, UUID) and
starts `torchrun --nproc_per_node 4` on this module's `worker`:
- `check`: one global batch of 64 items through DDP (8 x 2 x 4) and through one process (8 x 8): loss and gradient
  must agree. Both stay in train mode (DDP does not sync gradients in eval mode) with every dropout set to 0 (the
  head's two Transformer layers have dropout 0.1, so train-mode passes otherwise differ even within one process);
  save -> reload must reproduce the logits.
- `measure`: optimizer steps on the training rows, seconds per row after warm-up, with gradient checkpointing on
  (EX-161) and off.
- `train`: three epochs; rank 0 validates and checkpoints every epoch, then selects the epoch and fits the
  temperature as `laya_imitation.training.train` does.

Each rank reads and tokenizes only its shard (positions rank, rank + 4, ... of a fixed permutation of the training
rows), so the four processes hold one copy of the data between them; token ids are kept as `array('i')`. A rank
reshuffles its shard every epoch; gradients sync on the last micro-batch of each window (`no_sync` before it), and the
per-window loss scaling is laya's, so the averaged gradient equals EX-161's micro 8 x accum 8 mean.
"""
from __future__ import annotations
import argparse
from array import array
from contextlib import ExitStack, nullcontext
from datetime import timedelta
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time

from integration.laya_imitation import config as c
from integration.laya_imitation.resources import gpu
from integration.laya_imitation.storage import append_jsonl, atomic, sha

from . import paths

UUIDS = {0: c.GPU_UUID, 1: c.GPU1_UUID, 2: c.GPU2_UUID, 3: c.GPU3_UUID}
CHECK_ITEMS = 64
# Choice questions never reach the value head, so on one GPU its gradients stay None and AdamW skips it. DDP reduces
# buckets in order and waits for every parameter, so a parameter that never gets a gradient blocks the reduction of
# the whole model; it is frozen instead, which leaves the same parameters untouched as on one GPU.
UNUSED_PREFIX = 'act_head.'


def _train_cfg(head, max_len):
    return dict(c.TRAIN, head_max_len=head, max_len=max_len, option_max_len=paths.OPTION_LIMIT)


def _count(path):
    with open(path) as f:
        return sum(1 for _ in f)


def plan(files, world, seed, calib_max, calib_frac, calib_seed):
    """Global training keys `(file, line)` in a fixed order, cut to a multiple of `world`, and the calibration lines.

    The calibration slice is laya's `split_calibration` over the imitation rows (file 0) only, as in EX-161;
    knowledge rows (later files) only join training."""
    from laya.train import split_calibration
    n = _count(files[0])
    train, calib = split_calibration(list(range(n)), calib_max, calib_frac, calib_seed)
    keys = [(0, i) for i in train] + [(f, i) for f, path in enumerate(files[1:], 1) for i in range(_count(path))]
    random.Random(seed).shuffle(keys)
    return keys[:len(keys) // world * world], calib


def read_rows(files, wanted):
    want = {}
    for f, i in wanted:
        want.setdefault(f, set()).add(i)
    rows = {}
    for f, path in enumerate(files):
        lines = want.get(f)
        if not lines:
            continue
        with open(path) as handle:
            for i, line in enumerate(handle):
                if i in lines:
                    rows[(f, i)] = json.loads(line)
    if len(rows) != len(set(wanted)):
        raise ValueError('missing training rows: %d of %d' % (len(rows), len(set(wanted))))
    return rows


def make_items(tok, rows, max_len, head, pack=True):
    """laya items, one per row (the `action` question); training shards pack token ids as `array('i')`, items
    scored by laya's `calibration_records` (validation, calibration, checks) keep lists."""
    from laya.train import items_from_rows
    items, skipped = items_from_rows(tok, rows, max_len, head)
    if skipped or len(items) != len(rows):
        raise ValueError('rows not usable by laya: %r' % skipped)
    if any(item['q']['t'] != 'choice' for item in items):
        raise ValueError('only choice questions are expected (the value head is frozen)')
    for row, item in zip(rows, items):
        if pack:
            item['state_ids'] = array('i', item['state_ids'])
        item['sample_id'] = row.get('sample_id')
    return items


def encode(tok, item, max_len, head, order=None):
    from laya.train import encode_item
    return encode_item(tok, dict(item, state_ids=list(item['state_ids'])), max_len, head, order)


def optimizer_for(model, config):
    import torch
    groups = [{'params': [p for n, p in model.named_parameters() if n.startswith('encoder.') and p.requires_grad],
               'lr': config.encoder_lr},
              {'params': [p for n, p in model.named_parameters() if not n.startswith('encoder.') and p.requires_grad],
               'lr': config.head_lr}]
    return torch.optim.AdamW(groups, weight_decay=config.weight_decay), [p for g in groups for p in g['params']]


def prepare_model(model, checkpointing):
    for name, param in model.named_parameters():
        if name.startswith(UNUSED_PREFIX):
            param.requires_grad_(False)
    if checkpointing:
        model.encoder.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    else:
        model.encoder.gradient_checkpointing_disable()
    model.head_checkpointing = checkpointing
    return model


def fit(ddp, module, tok, items, config, device, max_len, head, rank, *, epochs=None, accum=paths.GRAD_ACCUM,
        checkpointing=True, on_epoch_end=None, stop_after_updates=None, log=print):
    """laya's `train_model` loop for one rank of a DDP group (soft-CE, fp16 autocast, per-window scaling).

    `stop_after_updates` ends early (measurement); returns per-epoch mean local losses and update timestamps."""
    import torch
    from laya.common import collate_items
    from laya.train import _forward, draw_option_order, optimizer_updates, soft_ce_loss
    epochs = epochs or config.epochs
    prepare_model(module, checkpointing)
    ddp.train()
    optimizer, params = optimizer_for(module, config)
    steps_per_epoch = math.ceil(len(items) / config.micro_batch)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=optimizer_updates(len(items), config.micro_batch, accum, epochs), eta_min=config.min_lr)
    scaler = torch.amp.GradScaler('cuda')
    torch.manual_seed(config.seed)
    order_rng = random.Random(config.seed * 1000 + rank)
    history, stamps, updates = [], [], 0
    for epoch in range(epochs):
        epoch_items = list(items)
        random.Random((config.seed + epoch) * 1000 + rank).shuffle(epoch_items)
        total, n_steps = 0.0, 0
        optimizer.zero_grad(set_to_none=True)
        for start in range(0, len(epoch_items), config.micro_batch):
            chunk = [encode(tok, it, max_len, head, draw_option_order(it, order_rng, config.shuffle_options))
                     for it in epoch_items[start:start + config.micro_batch]]
            batch = collate_items([chunk], tok.pad_token_id)
            last = (n_steps + 1) % accum == 0 or start + config.micro_batch >= len(epoch_items)
            window_start = (n_steps // accum) * accum
            window = min(accum, steps_per_epoch - window_start)
            with (nullcontext() if last else ddp.no_sync()):
                logits = _forward(ddp, batch, device, True, False)
                loss = soft_ce_loss(logits, batch['target'].to(device), batch['marker_mask'].to(device))
                scaler.scale(loss / window).backward()
            n_steps += 1
            if last:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(params, config.grad_clip)
                scaler.step(optimizer)
                scaler.update()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                updates += 1
                stamps.append(time.time())
                if stop_after_updates and updates >= stop_after_updates:
                    return history, stamps
            total += loss.item()
            if rank == 0 and config.log_every and n_steps % config.log_every == 0:
                log('epoch %d/%d step %d/%d loss %.4f' % (epoch + 1, epochs, n_steps, steps_per_epoch, loss.item()))
        mean = total / max(1, n_steps)
        history.append(mean)
        if on_epoch_end is not None:
            on_epoch_end(epoch, mean)
    return history, stamps


# ------------------------------------------------------------------------------------------------ worker side

def _setup():
    import torch
    import torch.distributed as dist
    dist.init_process_group('nccl', timeout=timedelta(hours=3))
    local = int(os.environ['LOCAL_RANK'])
    torch.cuda.set_device(local)
    return dist.get_rank(), dist.get_world_size(), torch.device('cuda', local)


def _load(device):
    from laya.train import load_checkpoint
    model, tok, cfg = load_checkpoint(str(c.MODEL_DIR))
    return model.to(device), tok, cfg


def _wrap(model, device):
    from torch.nn.parallel import DistributedDataParallel
    return DistributedDataParallel(model, device_ids=[device.index], output_device=device.index,
                                   broadcast_buffers=False)


def _no_dropout(model):
    import torch.nn as nn
    for module in model.modules():
        if isinstance(module, nn.Dropout):
            module.p = 0.0
        elif isinstance(getattr(module, 'dropout', None), float):
            module.dropout = 0.0
    return model


def _flat_grad(model):
    """All parameter gradients by name order, zeros where a parameter got none (DDP fills unused buckets)."""
    import torch
    return torch.cat([(p.grad.detach().float() if p.grad is not None else torch.zeros_like(p, dtype=torch.float32))
                      .reshape(-1) for _, p in sorted(model.named_parameters())])


def worker_check(args):
    """DDP (8 x 2 x 4) vs one process (8 x 8) on the same 64 items: fp32, canonical option order, dropout off."""
    import torch
    import torch.distributed as dist
    from laya.common import collate_items
    from laya.train import _forward, calibration_records, load_checkpoint, save_checkpoint, soft_ce_loss
    rank, world, device = _setup()
    files = [str(Path(args.dataset) / 'train.jsonl')]
    with open(files[0]) as f:
        rows = [json.loads(next(f)) for _ in range(CHECK_ITEMS)]
    model, tok, cfg = _load(device)
    _no_dropout(prepare_model(model, True))
    items = make_items(tok, rows, args.max_len, args.head, pack=False)
    per = CHECK_ITEMS // world

    def loss_of(net, chunk, scale):
        batch = collate_items([[encode(tok, it, args.max_len, args.head) for it in chunk]], tok.pad_token_id)
        logits = _forward(net, batch, device, False, False)
        loss = soft_ce_loss(logits, batch['target'].to(device), batch['marker_mask'].to(device))
        (loss / scale).backward()
        return loss.detach()

    ddp = _wrap(model, device)
    ddp.train()
    mine = items[rank * per:(rank + 1) * per]
    micro = [mine[i:i + 8] for i in range(0, len(mine), 8)]
    losses = []
    for k, chunk in enumerate(micro):
        with (nullcontext() if k == len(micro) - 1 else ddp.no_sync()):
            losses.append(loss_of(ddp, chunk, len(micro)))
    mean_loss = torch.stack(losses).mean()
    dist.all_reduce(mean_loss)
    mean_loss /= world
    result = None
    if rank == 0:
        g_ddp = _flat_grad(model)
        single, _, _ = load_checkpoint(str(c.MODEL_DIR))
        single = _no_dropout(prepare_model(single.to(device), True))
        single.train()
        single_losses = [loss_of(single, items[i:i + 8], CHECK_ITEMS // 8) for i in range(0, CHECK_ITEMS, 8)]
        g_one = _flat_grad(single)
        rel = float((g_ddp - g_one).norm() / g_one.norm())
        loss_one = float(torch.stack(single_losses).mean())
        out = Path(args.out) / 'check'
        out.mkdir(parents=True, exist_ok=True)
        path = out / 'checkpoint'
        save_checkpoint(single, tok, dict(cfg, max_len=args.max_len, head_max_len=args.head,
                                          option_max_len=paths.OPTION_LIMIT), str(path))
        single.load_state_dict({k: v.half().float() for k, v in single.state_dict().items()})
        a = calibration_records(single, tok, items[:32], device, args.max_len, args.head)
        again, _, _ = load_checkpoint(str(path))
        b = calibration_records(again.to(device), tok, items[:32], device, args.max_len, args.head)
        reload_diff = max(float(abs(x[1] - y[1]).max()) for x, y in zip(a, b))
        result = dict(items=CHECK_ITEMS, world=world, loss_ddp=float(mean_loss), loss_single=loss_one,
                      loss_abs_diff=abs(float(mean_loss) - loss_one), grad_rel_diff=rel,
                      grad_norm=float(g_one.norm()), reload_max_abs_logit_diff=reload_diff)
        result['passed'] = result['loss_abs_diff'] < 1e-4 and rel < 1e-3 and reload_diff < 1e-3
        atomic(out / 'result.json', result)
        import shutil
        shutil.rmtree(path)
        print(json.dumps(result), flush=True)
    dist.barrier()
    dist.destroy_process_group()


def worker_measure(args):
    """Seconds per training row on `world` GPUs, gradient checkpointing on and off (warm-up updates excluded)."""
    import torch
    import torch.distributed as dist
    from laya.train import TrainConfig
    rank, world, device = _setup()
    files = [str(Path(args.dataset) / 'train.jsonl')]
    config = TrainConfig(**dict(_train_cfg(args.head, args.max_len), log_every=0))
    keys, _ = plan(files, world, config.seed, config.calib_max, config.calib_frac, config.calib_seed)
    per_update = config.micro_batch * paths.GRAD_ACCUM
    need = (args.warmup + args.updates) * per_update
    mine = keys[rank::world][:need]
    model, tok, _ = _load(device)
    rows = read_rows(files, mine)
    items = make_items(tok, [rows[k] for k in mine], args.max_len, args.head)
    results = {}
    for checkpointing in (True, False):
        model, tok, _ = _load(device)
        ddp = _wrap(prepare_model(model, checkpointing), device)
        torch.cuda.reset_peak_memory_stats()
        try:
            _, stamps = fit(ddp, model, tok, items, config, device, args.max_len, args.head, rank, epochs=1,
                            checkpointing=checkpointing, stop_after_updates=args.warmup + args.updates)
            seconds = stamps[-1] - stamps[args.warmup - 1]
            rows_done = args.updates * per_update * world
            peak = torch.tensor(torch.cuda.max_memory_allocated() / 2**30, device=device)
            dist.all_reduce(peak, op=dist.ReduceOp.MAX)
            results['checkpointing' if checkpointing else 'no_checkpointing'] = dict(
                seconds=round(seconds, 2), rows=rows_done, seconds_per_row=seconds / rows_done,
                peak_allocated_gib=round(float(peak), 3))
        except torch.OutOfMemoryError as exc:
            results['checkpointing' if checkpointing else 'no_checkpointing'] = dict(error='oom: %s' % str(exc)[:200])
        del ddp, model
        torch.cuda.empty_cache()
        dist.barrier()
    if rank == 0:
        out = Path(args.out) / 'measure'
        out.mkdir(parents=True, exist_ok=True)
        value = dict(dataset=str(args.dataset), world=world, micro_batch=config.micro_batch, grad_accum=paths.GRAD_ACCUM,
                     warmup_updates=args.warmup, measured_updates=args.updates, results=results, at=time.time())
        atomic(out / ('measure-%d.json' % int(time.time())), value)
        print(json.dumps(value), flush=True)
    dist.barrier()
    dist.destroy_process_group()


def _freeze(out, dataset, files, config):
    """EX-161's run freeze: the EX-167 record, source identity, dataset manifest and the training config."""
    from integration.laya_imitation.storage import source_identity
    from integration.project_context.registry import freeze_document, resolve_record
    if (out / 'protocol/EX-167.md').exists():
        return
    freeze_document(resolve_record('EX-167'), out / 'protocol/EX-167.md')
    atomic(out / 'source/identity.json', dict(source_identity(), laya_ladder={
        p.name: sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))}), immutable=True)
    atomic(out / 'source/dataset-manifest.json', json.loads((dataset / 'manifest.json').read_text()), immutable=True)
    atomic(out / 'protocol/train-config.json', dict(
        {k: list(v) if isinstance(v, tuple) else v for k, v in vars(config).items()},
        base=str(c.MODEL_DIR), revision=c.MODEL_REVISION, files=files, world=paths.WORLD,
        grad_accum_per_gpu=paths.GRAD_ACCUM, frozen=UNUSED_PREFIX), immutable=True)


def worker_train(args):
    import torch
    import torch.distributed as dist
    from laya.calibrate import fit_temperature_map
    from laya.train import TrainConfig, calibration_records, load_checkpoint, save_checkpoint
    from integration.laya_imitation.training import _metrics
    rank, world, device = _setup()
    out = Path(args.out)
    dataset = Path(args.dataset)
    files = [str(dataset / 'train.jsonl')] + list(args.extra)
    config = TrainConfig(**_train_cfg(args.head, args.max_len))
    keys, calib_lines = plan(files, world, config.seed, config.calib_max, config.calib_frac, config.calib_seed)
    mine = keys[rank::world]
    model, tok, cfg = _load(device)
    rows = read_rows(files, mine)
    items = make_items(tok, [rows[k] for k in mine], args.max_len, args.head)
    del rows
    clock = time.time()
    val = calib = None
    base_cfg = dict(cfg, max_len=args.max_len, head_max_len=args.head, option_max_len=paths.OPTION_LIMIT)
    if rank == 0:
        _freeze(out, dataset, files, config)
        atomic(out / 'status.json', dict(stage='training', epoch=0, of=config.epochs, at=time.time()))
        vrows = [json.loads(line) for line in open(dataset / 'validation.jsonl')]
        val = make_items(tok, vrows, args.max_len, args.head, pack=False)
        crows = read_rows(files, [(0, i) for i in calib_lines])
        calib = make_items(tok, [crows[(0, i)] for i in calib_lines], args.max_len, args.head, pack=False)
        imitation = sum(1 for f, _ in keys if f == 0)
        atomic(out / 'split.json', dict(train=len(keys), calibration=len(calib), validation=len(val),
                                        extra_train=len(keys) - imitation, imitation_train=imitation,
                                        dropped_for_equal_shards=_count(files[0]) - len(calib_lines) +
                                        sum(_count(p) for p in files[1:]) - len(keys), world=world,
                                        per_rank=len(mine)), immutable=True)
        records = calibration_records(model, tok, val, device, args.max_len, args.head)
        append_jsonl(out / 'validation-curve.jsonl', dict(epoch=0, raw=_metrics(records, 1.0)))
    dist.barrier()
    ddp = _wrap(prepare_model(model, bool(args.checkpointing)), device)

    def on_epoch_end(epoch, mean_loss):
        loss = torch.tensor(mean_loss, device=device)
        dist.all_reduce(loss)
        if rank == 0:
            path = out / 'checkpoints' / ('epoch-%d' % (epoch + 1))
            save_checkpoint(model, tok, base_cfg, str(path))
            recs = calibration_records(model, tok, val, device, args.max_len, args.head)
            row = dict(epoch=epoch + 1, train_loss=float(loss) / world, raw=_metrics(recs, 1.0),
                       seconds=round(time.time() - clock),
                       peak_allocated_gib=round(torch.cuda.max_memory_allocated() / 2**30, 3))
            append_jsonl(out / 'validation-curve.jsonl', row)
            atomic(out / 'status.json', dict(stage='training', epoch=epoch + 1, of=config.epochs, at=time.time()))
        ddp.train()
        dist.barrier()

    history, _ = fit(ddp, model, tok, items, config, device, args.max_len, args.head, rank,
                     checkpointing=bool(args.checkpointing), on_epoch_end=on_epoch_end,
                     log=lambda s: print('[%s] %s' % (time.strftime('%H:%M:%SZ', time.gmtime()), s), flush=True))
    dist.barrier()
    if rank == 0:
        del ddp, model
        torch.cuda.empty_cache()
        curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
        best = min((r for r in curve if r['epoch'] > 0), key=lambda r: (r['raw']['loss'], r['epoch']))
        model, tok, cfg = load_checkpoint(str(out / 'checkpoints' / ('epoch-%d' % best['epoch'])))
        model.to(device)
        recs = calibration_records(model, tok, calib, device, args.max_len, args.head)
        fitted = fit_temperature_map(recs)
        selected = dict(cfg, fine_tuned=True, temperature=fitted['temperature'])
        selected.pop('temperature_by_options', None)
        if fitted['temperature_by_options']:
            selected['temperature_by_options'] = fitted['temperature_by_options']
        selected['training'] = dict(cfg.get('training') or {}, ex167=dict(
            selected_epoch=best['epoch'], history=history, world=world, grad_accum=paths.GRAD_ACCUM,
            checkpointing=bool(args.checkpointing),
            config={k: list(v) if isinstance(v, tuple) else v for k, v in _train_cfg(args.head, args.max_len).items()}))
        save_checkpoint(model, tok, selected, str(out / 'checkpoints/selected'))
        recs = calibration_records(model, tok, val, device, args.max_len, args.head)
        selection = dict(selected_epoch=best['epoch'], rule='min validation raw NLL, earlier epoch on ties',
                         calibration_items=len(calib), temperature=fitted['temperature'],
                         temperature_by_options=fitted['temperature_by_options'],
                         validation_selected_calibrated=_metrics(recs, fitted['temperature'],
                                                                 fitted['temperature_by_options']),
                         checkpoint_sha256={p.name: sha(p) for p in sorted((out / 'checkpoints/selected').rglob('*'))
                                            if p.is_file()})
        atomic(out / 'selection.json', selection, immutable=True)
        atomic(out / 'status.json', dict(stage='trained', at=time.time()))
    dist.barrier()
    dist.destroy_process_group()


def _worker_main(argv):
    from integration.laya_v10 import training_v10
    training_v10.install(paths.OPTION_LIMIT)
    parser = _parser()
    args = parser.parse_args(argv)
    if args.mode == 'check':
        import faulthandler
        faulthandler.dump_traceback_later(240, repeat=True)
    try:
        dict(check=worker_check, measure=worker_measure, train=worker_train)[args.mode](args)
    except BaseException:
        # One failed rank must not leave the others waiting in a collective until the NCCL timeout.
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(1)


def _parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('check', 'measure', 'train'))
    parser.add_argument('--dataset', default=str(paths.V10_DATASET))
    parser.add_argument('--extra', nargs='*', default=[str(c.TERA_KNOWLEDGE / 'train.jsonl')])
    parser.add_argument('--out', default=str(paths.RUN_TRAINING))
    parser.add_argument('--head', type=int, default=paths.HEAD_LIMIT)
    parser.add_argument('--max-len', type=int, default=paths.TOKEN_LIMIT)
    parser.add_argument('--warmup', type=int, default=5)
    parser.add_argument('--updates', type=int, default=60)
    parser.add_argument('--checkpointing', type=int, default=1)
    return parser


# ------------------------------------------------------------------------------------------------ launcher side

def launch(argv):
    """Hold GPU0-3 (pinned UUID, idle) and run `torchrun` on the four of them."""
    args = _parser().parse_args(argv)
    status = Path(args.out) / 'status.json'
    if args.mode == 'train' and status.exists():
        raise SystemExit('%s already started (%s); no automatic re-run' % (args.out, status.read_text()))
    with ExitStack() as stack:
        for index in paths.GPUS:
            stack.enter_context(gpu(index, UUIDS[index]))
        env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID',
                   CUDA_VISIBLE_DEVICES=','.join(UUIDS[i] for i in paths.GPUS), OMP_NUM_THREADS='8',
                   TOKENIZERS_PARALLELISM='false')
        Path(args.out).mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc_per_node', str(paths.WORLD),
               '-m', 'integration.laya_ladder.train_ddp', '--worker', *argv]
        return subprocess.call(cmd, env=env, cwd=str(c.ROOT))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        _worker_main(sys.argv[2:])
    else:
        sys.exit(launch(sys.argv[1:]))
