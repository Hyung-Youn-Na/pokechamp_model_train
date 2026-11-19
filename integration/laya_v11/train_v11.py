"""EX-171 / EX-172 (D-209): one more epoch from v10rt (EX-167 selected) on the v11 rows, on GPU2 / GPU3.

    python -m integration.laya_v11.train_v11 measure --experiment EX-171 --gpus 2,3
    python -m integration.laya_v11.train_v11 train   --experiment EX-171 --gpus 2,3
    python -m integration.laya_v11.train_v11 train   --experiment EX-172 --gpus 2,3

EX-167's loop (`laya_ladder.train_ddp`: laya's encoding, soft-CE, per-window scaling, `act_head` frozen, no gradient
checkpointing) with what D-209 adds:
- start: `--init` (EX-167 `checkpoints/selected`), one epoch, cosine from the configured learning rates;
- GPUs: `--gpus` one or two; micro 8 x accumulation (8 / GPUs) x GPUs = EX-167's batch of 64;
- validation and a checkpoint at 25 / 50 / 75 / 100% of the epoch; the point with the lowest validation NLL (earlier on
  ties) is selected and its temperature refitted on EX-167's calibration lines;
- EX-172: `--weights` (rows with weight 0 are left out, the others scale their target) and `--extra` files that may
  repeat (correction rows, `gold` soft targets);
- memory: rows are read and tokenised in chunks and the raw rows dropped; token ids are `array('i')`. `measure` reports
  seconds per row and the loading memory per row, from which the launcher decides one-GPU-per-model or two-GPU
  sequential (D-209 decision 6).
The calibration lines are EX-167's (`plan` over the same file order), so they never enter training.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from contextlib import ExitStack, nullcontext
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
from integration.laya_ladder import paths as ladder
from integration.laya_ladder import train_ddp as D

from . import data_v11, paths, policy

UUIDS = {2: c.GPU2_UUID, 3: c.GPU3_UUID}
RUNS = {'EX-171': c.SHARED / 'runs/model-training/EX-171', 'EX-172': c.SHARED / 'runs/model-training/EX-172'}
POINTS = 4
CHUNK = 20000
CORRECTION_SHARE = 0.02


def rss_gb():
    with open('/proc/self/status') as f:
        for line in f:
            if line.startswith('VmRSS:'):
                return int(line.split()[1]) / 2 ** 20
    return 0.0


def load_weights(path, train):
    """Weights aligned with the lines of `train` (the weights file is written in that order)."""
    if not path:
        return None
    values = []
    with open(Path(path) / 'weights.jsonl') as f:
        for line in f:
            values.append(json.loads(line)['weight'])
    if len(values) != D._count(train):
        raise ValueError('weights do not cover %s' % train)
    return values


def train_keys(files, world, config, weights):
    """EX-167's order and calibration lines; then zero-weight rows are left out and the list is cut to `world`."""
    keys, calib = D.plan(files, 1, config.seed, config.calib_max, config.calib_frac, config.calib_seed)
    if weights is not None:
        keys = [k for k in keys if k[0] != 0 or weights[k[1]] > 0]
    return keys[:len(keys) // world * world], calib


def load_items(tok, files, mine, weights, max_len, head, pack=True, limit=None):
    """Items for the keys `mine`, in that order, read and tokenised `CHUNK` rows at a time."""
    position = {k: i for i, k in enumerate(mine)}
    want = defaultdict(set)
    for f, i in mine:
        want[f].add(i)
    items = [None] * len(mine)
    done = 0

    def flush(keys, rows):
        made = D.make_items(tok, rows, max_len, head, pack=pack)
        for key, row, item in zip(keys, rows, made):
            if key[0] == 0 and weights is not None and weights[key[1]] != 1.0:
                item['target'] = [weights[key[1]] * v for v in item['target']]
            items[position[key]] = item

    for f, path in enumerate(files):
        lines = want.get(f)
        if not lines:
            continue
        keys, rows = [], []
        with open(path) as handle:
            for i, line in enumerate(handle):
                if i in lines:
                    keys.append((f, i))
                    rows.append(json.loads(line))
                    done += 1
                    if len(rows) == CHUNK:
                        flush(keys, rows)
                        keys, rows = [], []
                    if limit and done >= limit:
                        break
        if rows:
            flush(keys, rows)
        if limit and done >= limit:
            break
    if limit:
        return [x for x in items if x is not None]
    if any(x is None for x in items):
        raise ValueError('missing training rows')
    return items


def fit(ddp, module, tok, items, config, device, max_len, head, rank, accum, on_point, stop_after_updates=None,
        log=print):
    """One epoch of `train_ddp.fit` with `on_point(k, mean loss so far)` after the update at k/POINTS of the epoch."""
    import torch
    from laya.common import collate_items
    from laya.train import _forward, draw_option_order, optimizer_updates, soft_ce_loss
    D.prepare_model(module, False)
    ddp.train()
    optimizer, params = D.optimizer_for(module, config)
    steps = math.ceil(len(items) / config.micro_batch)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=optimizer_updates(len(items), config.micro_batch, accum, 1), eta_min=config.min_lr)
    scaler = torch.amp.GradScaler('cuda')
    torch.manual_seed(config.seed)
    order_rng = random.Random(config.seed * 1000 + rank)
    epoch_items = list(items)
    random.Random(config.seed * 1000 + rank).shuffle(epoch_items)
    marks = {min(steps, max(accum, round(k * steps / POINTS) // accum * accum)): k for k in range(1, POINTS)}
    marks[steps] = POINTS
    total, n_steps, updates, stamps, losses = 0.0, 0, 0, [], []
    optimizer.zero_grad(set_to_none=True)
    for start in range(0, len(epoch_items), config.micro_batch):
        chunk = [D.encode(tok, it, max_len, head, draw_option_order(it, order_rng, config.shuffle_options))
                 for it in epoch_items[start:start + config.micro_batch]]
        batch = collate_items([chunk], tok.pad_token_id)
        last = (n_steps + 1) % accum == 0 or start + config.micro_batch >= len(epoch_items)
        window = min(accum, steps - (n_steps // accum) * accum)
        with (nullcontext() if last else ddp.no_sync()):
            logits = _forward(ddp, batch, device, True, False)
            loss = soft_ce_loss(logits, batch['target'].to(device), batch['marker_mask'].to(device))
            scaler.scale(loss / window).backward()
        n_steps += 1
        value = loss.item()
        if not math.isfinite(value):
            raise FloatingPointError('loss is not finite at step %d' % n_steps)
        total += value
        if last:
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(params, config.grad_clip)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)
            updates += 1
            stamps.append(time.time())
            losses.append(value)
            if stop_after_updates and updates >= stop_after_updates:
                return total / n_steps, stamps, losses
        if rank == 0 and config.log_every and n_steps % config.log_every == 0:
            log('step %d/%d loss %.4f' % (n_steps, steps, value))
        if n_steps in marks:
            on_point(marks[n_steps], total / n_steps)
            ddp.train()
    return total / max(1, n_steps), stamps, losses


def _config(args, **extra):
    from laya.train import TrainConfig
    return TrainConfig(**dict(D._train_cfg(args.head, args.max_len), epochs=1, **extra))


def _files(args):
    return [str(Path(args.dataset) / 'train.jsonl')] + list(args.extra)


def worker_measure(args):
    """Seconds per row over `--updates` updates, loading memory per row, and the save -> reload check."""
    import torch
    import torch.distributed as dist
    from laya.train import calibration_records, load_checkpoint, save_checkpoint
    rank, world, device = D._setup()
    accum = 8 // world
    config = _config(args, log_every=0)
    files = _files(args)
    weights = load_weights(args.weights, files[0])
    keys, _ = train_keys(files, world, config, weights)
    per_update = config.micro_batch * accum
    need = (args.warmup + args.updates) * per_update
    c.MODEL_DIR = Path(args.init)
    model, tok, cfg = D._load(device)
    before = rss_gb()
    items = load_items(tok, files, keys[rank::world], weights, args.max_len, args.head, limit=max(need, args.memory_rows))
    per_row = (rss_gb() - before) / len(items)
    ddp = D._wrap(D.prepare_model(model, False), device)
    torch.cuda.reset_peak_memory_stats()
    mean, stamps, losses = fit(ddp, model, tok, items[:need], config, device, args.max_len, args.head, rank, accum,
                               lambda k, loss: None, stop_after_updates=args.warmup + args.updates)
    seconds = stamps[-1] - stamps[args.warmup - 1]
    peak = torch.tensor(torch.cuda.max_memory_allocated() / 2 ** 30, device=device)
    dist.all_reduce(peak, op=dist.ReduceOp.MAX)
    if rank == 0:
        out = Path(args.out) / 'measure'
        out.mkdir(parents=True, exist_ok=True)
        spr = seconds / (args.updates * per_update * world)
        model.load_state_dict({k: v.half().float() for k, v in model.state_dict().items()})
        check = D.make_items(tok, [json.loads(line) for _, line in zip(range(32), open(files[0]))], args.max_len,
                             args.head, pack=False)
        a = calibration_records(model, tok, check, device, args.max_len, args.head)
        path = out / 'checkpoint'
        save_checkpoint(model, tok, dict(cfg, max_len=args.max_len, head_max_len=args.head,
                                         option_max_len=ladder.OPTION_LIMIT), str(path))
        again, _, _ = load_checkpoint(str(path))
        b = calibration_records(again.to(device), tok, check, device, args.max_len, args.head)
        import shutil
        shutil.rmtree(path)
        diff = max(float(abs(x[1] - y[1]).max()) for x, y in zip(a, b))
        rows = len(keys)
        half = max(1, len(losses) // 2)
        value = dict(experiment=args.experiment, world=world, accum=accum, train_rows=rows,
                     seconds_per_row=spr, expected_hours=rows * spr / 3600,
                     peak_gpu_gib=round(float(peak), 2), memory_rows=len(items), memory_gb_per_row=per_row,
                     base_rss_gb=round(before, 2),
                     predicted_host_gb=dict(one_process_per_model=round(before + per_row * rows, 1),
                                            two_processes_per_model=round(2 * (before + per_row * rows / 2), 1)),
                     loss_first_half=sum(losses[:half]) / half, loss_second_half=sum(losses[half:]) / max(1, len(losses) - half),
                     reload_max_abs_logit_diff=diff, reload_ok=diff < 1e-3, at=time.time())
        atomic(out / ('measure-%d.json' % int(time.time())), value)
        print(json.dumps(value), flush=True)
    dist.barrier()
    dist.destroy_process_group()


def _freeze(args, out, files, config, world, accum, split):
    from integration.laya_imitation.storage import source_identity
    from integration.project_context.registry import freeze_document, resolve_record
    freeze_document(resolve_record(args.experiment), out / ('protocol/%s.md' % args.experiment))
    package = {p.name: sha(p) for p in sorted(paths.PACKAGE.glob('*.py'))}
    atomic(out / 'source/identity.json', dict(source_identity(), laya_v11=package), immutable=True)
    atomic(out / 'source/dataset-manifest.json', json.loads((Path(args.dataset) / 'manifest.json').read_text()),
           immutable=True)
    extra = {}
    for path in sorted(set(args.extra)):
        manifest = Path(path).parent / 'manifest.json'
        extra[path] = dict(times=args.extra.count(path), manifest_sha256=sha(manifest) if manifest.exists() else None)
    atomic(out / 'protocol/train-config.json', dict(
        {k: list(v) if isinstance(v, tuple) else v for k, v in vars(config).items()},
        init=str(args.init), init_sha256={p.name: sha(p) for p in sorted(Path(args.init).iterdir()) if p.is_file()},
        files=files, extra=extra, weights=str(args.weights) if args.weights else None,
        weights_manifest_sha256=sha(Path(args.weights) / 'manifest.json') if args.weights else None,
        world=world, grad_accum_per_gpu=accum, frozen=D.UNUSED_PREFIX, points=POINTS, split=split), immutable=True)


def worker_train(args):
    import torch
    import torch.distributed as dist
    from laya.calibrate import fit_temperature_map
    from laya.train import calibration_records, load_checkpoint, save_checkpoint
    from integration.laya_imitation.training import _metrics
    rank, world, device = D._setup()
    accum = 8 // world
    out, dataset = Path(args.out), Path(args.dataset)
    files = _files(args)
    config = _config(args)
    weights = load_weights(args.weights, files[0])
    keys, calib_lines = train_keys(files, world, config, weights)
    c.MODEL_DIR = Path(args.init)
    model, tok, cfg = D._load(device)
    items = load_items(tok, files, keys[rank::world], weights, args.max_len, args.head)
    clock = time.time()
    val = calib = None
    base_cfg = dict(cfg, max_len=args.max_len, head_max_len=args.head, option_max_len=ladder.OPTION_LIMIT)
    key = args.experiment.lower().replace('-', '')
    if rank == 0:
        by_file = defaultdict(int)
        for f, _ in keys:
            by_file[f] += 1
        total_rows = D._count(files[0])
        split = dict(train=len(keys), imitation_train=by_file[0], extra_train=len(keys) - by_file[0],
                     calibration=len(calib_lines), imitation_rows=total_rows,
                     left_out_by_weight=sum(1 for w in weights if w == 0) if weights is not None else 0,
                     validation=D._count(dataset / 'validation.jsonl'), world=world, per_rank=len(items))
        _freeze(args, out, files, config, world, accum, split)
        atomic(out / 'split.json', split, immutable=True)
        atomic(out / 'status.json', dict(stage='training', point=0, of=POINTS, at=time.time()))
        val = D.make_items(tok, [json.loads(line) for line in open(dataset / 'validation.jsonl')], args.max_len,
                           args.head, pack=False)
        calib = load_items(tok, files, [(0, i) for i in calib_lines], None, args.max_len, args.head, pack=False)
        records = calibration_records(model, tok, val, device, args.max_len, args.head)
        append_jsonl(out / 'validation-curve.jsonl', dict(point=0, raw=_metrics(records, 1.0),
                                                         shipped=_metrics(records, cfg.get('temperature'),
                                                                          cfg.get('temperature_by_options'))))
    dist.barrier()
    ddp = D._wrap(D.prepare_model(model, False), device)
    stamp = lambda s: print('[%s] %s' % (time.strftime('%H:%M:%SZ', time.gmtime()), s), flush=True)

    def on_point(k, mean_loss):
        loss = torch.tensor(mean_loss, device=device)
        dist.all_reduce(loss)
        if rank == 0:
            save_checkpoint(model, tok, base_cfg, str(out / 'checkpoints' / ('point-%d' % k)))
            recs = calibration_records(model, tok, val, device, args.max_len, args.head)
            row = dict(point=k, fraction=k / POINTS, train_loss=float(loss) / world, raw=_metrics(recs, 1.0),
                       seconds=round(time.time() - clock),
                       peak_allocated_gib=round(torch.cuda.max_memory_allocated() / 2 ** 30, 3),
                       host_rss_gb=round(rss_gb(), 2))
            append_jsonl(out / 'validation-curve.jsonl', row)
            atomic(out / 'status.json', dict(stage='training', point=k, of=POINTS, at=time.time()))
            stamp('point %d/%d validation NLL %.4f' % (k, POINTS, row['raw']['loss']))
        dist.barrier()

    mean, _, _ = fit(ddp, model, tok, items, config, device, args.max_len, args.head, rank, accum, on_point, log=stamp)
    dist.barrier()
    if rank == 0:
        del ddp, model
        torch.cuda.empty_cache()
        curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
        best = min((r for r in curve if r['point'] > 0), key=lambda r: (r['raw']['loss'], r['point']))
        model, tok, cfg = load_checkpoint(str(out / 'checkpoints' / ('point-%d' % best['point'])))
        model.to(device)
        fitted = fit_temperature_map(calibration_records(model, tok, calib, device, args.max_len, args.head))
        selected = dict(cfg, fine_tuned=True, temperature=fitted['temperature'])
        selected.pop('temperature_by_options', None)
        if fitted['temperature_by_options']:
            selected['temperature_by_options'] = fitted['temperature_by_options']
        selected['training'] = dict(cfg.get('training') or {}, **{key: dict(
            selected_point=best['point'], points=POINTS, world=world, grad_accum=accum, init=str(args.init),
            mean_train_loss=mean,
            config={k: list(v) if isinstance(v, tuple) else v
                    for k, v in dict(D._train_cfg(args.head, args.max_len), epochs=1).items()})})
        save_checkpoint(model, tok, selected, str(out / 'checkpoints/selected'))
        recs = calibration_records(model, tok, val, device, args.max_len, args.head)
        atomic(out / 'selection.json', dict(
            selected_point=best['point'], rule='min validation raw NLL over the %d points, earlier on ties' % POINTS,
            calibration_items=len(calib), temperature=fitted['temperature'],
            temperature_by_options=fitted['temperature_by_options'],
            validation_selected_calibrated=_metrics(recs, fitted['temperature'], fitted['temperature_by_options']),
            checkpoint_sha256={p.name: sha(p) for p in sorted((out / 'checkpoints/selected').rglob('*'))
                               if p.is_file()}), immutable=True)
        atomic(out / 'status.json', dict(stage='trained', selected_point=best['point'],
                                         seconds=round(time.time() - clock), at=time.time()))
    dist.barrier()
    dist.destroy_process_group()


def _parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('measure', 'train'))
    parser.add_argument('--experiment', required=True, choices=sorted(RUNS))
    parser.add_argument('--gpus', default='2,3')
    parser.add_argument('--dataset', default=str(data_v11.MERGED))
    parser.add_argument('--init', default=str(paths.V10RT))
    parser.add_argument('--extra', nargs='*', default=None)
    parser.add_argument('--weights', default=None)
    parser.add_argument('--out', default=None)
    parser.add_argument('--head', type=int, default=ladder.HEAD_LIMIT)
    parser.add_argument('--max-len', type=int, default=ladder.TOKEN_LIMIT)
    parser.add_argument('--warmup', type=int, default=5)
    parser.add_argument('--updates', type=int, default=60)
    parser.add_argument('--memory-rows', type=int, default=8000)
    return parser


def defaults(args):
    """The experiment's files: EX-171 the v11 rows and the Tera knowledge rows; EX-172 adds the weights and the
    correction rows, repeated to about `CORRECTION_SHARE` of the training rows."""
    tera = str(c.TERA_KNOWLEDGE / 'train.jsonl')
    if args.out is None:
        args.out = str(RUNS[args.experiment])
    if args.extra is None:
        args.extra = [tera]
        if args.experiment == 'EX-172':
            corrections = policy.OUT_CORRECTIONS / 'train.jsonl'
            n = D._count(corrections)
            base = D._count(Path(args.dataset) / 'train.jsonl') + D._count(tera)
            times = max(1, round(CORRECTION_SHARE * base / n))
            args.extra += [str(corrections)] * times
    if args.weights is None and args.experiment == 'EX-172':
        args.weights = str(policy.OUT_WEIGHTS)
    return args


def launch(argv):
    args = defaults(_parser().parse_args(argv))
    indices = [int(x) for x in args.gpus.split(',')]
    if 8 % len(indices):
        raise SystemExit('use one or two GPUs')
    status = Path(args.out) / 'status.json'
    if args.mode == 'train' and status.exists():
        raise SystemExit('%s already started (%s); no automatic re-run' % (args.out, status.read_text()))
    with ExitStack() as stack:
        for index in indices:
            stack.enter_context(gpu(index, UUIDS[index]))
        env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID',
                   CUDA_VISIBLE_DEVICES=','.join(UUIDS[i] for i in indices), OMP_NUM_THREADS='8',
                   TOKENIZERS_PARALLELISM='false')
        Path(args.out).mkdir(parents=True, exist_ok=True)
        worker = ['--worker', args.mode, '--experiment', args.experiment, '--gpus', args.gpus, '--dataset', args.dataset,
                  '--init', args.init, '--out', args.out, '--head', str(args.head), '--max-len', str(args.max_len),
                  '--warmup', str(args.warmup), '--updates', str(args.updates), '--memory-rows', str(args.memory_rows),
                  '--extra', *args.extra]
        if args.weights:
            worker += ['--weights', args.weights]
        cmd = [sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc_per_node', str(len(indices)),
               '-m', 'integration.laya_v11.train_v11', *worker]
        return subprocess.call(cmd, env=env, cwd=str(c.ROOT))


def _worker_main(argv):
    from integration.laya_v10 import training_v10
    training_v10.install(ladder.OPTION_LIMIT)
    args = _parser().parse_args(argv)
    try:
        dict(measure=worker_measure, train=worker_train)[args.mode](args)
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        if args.mode == 'train' and os.environ.get('RANK', '0') == '0' and args.out:
            try:
                atomic(Path(args.out) / 'status.json', dict(stage='failed', detail=traceback.format_exc()[-2000:],
                                                            at=time.time()))
            except Exception:
                pass
        os._exit(1)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        _worker_main(sys.argv[2:])
    else:
        sys.exit(launch(sys.argv[1:]))
