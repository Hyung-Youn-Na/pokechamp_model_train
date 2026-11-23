"""EX-200 (EP-239, D-217): one epoch from EX-196 selected on the EX-199 soft targets + anchor rows.

    python -m integration.laya_value.train_value prepare            (any python 3: the anchor files, once)
    python -m integration.laya_value.train_value measure|train      (laya env, GPU 0-3)

`laya_v11.train_v11` unchanged (one epoch, validation at 25/50/75/100%, the lowest validation NLL point selected and
its temperature refitted); this wrapper registers EX-200, fixes the arguments and starts the workers on this module
with all four GPUs (micro 8 x accumulation 2 x 4), as `laya_foe.train_foe` does for EX-196.
- dataset `laya-value/v1/anchor`: train = ANCHOR_ROWS human rows drawn (seed) from `v12-fresh` train outside the
  EX-199 held-out games; validation = `v12-fresh` validation (v12-ladder-merged validation, as EX-192 / EX-196);
- extra: EX-199 `train.jsonl` (gold soft targets, all of them), FOE_ROWS rows drawn from EX-195 `foe-train.jsonl`,
  and the Tera knowledge rows (as EX-196).
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
import random
import shutil
from pathlib import Path
import subprocess
import sys

from integration.laya_imitation import config as c

RUN = c.SHARED / 'runs/model-training/EX-200'
INIT = c.SHARED / 'runs/model-training/EX-196/checkpoints/selected'
FRESH = c.SHARED / 'datasets/generated/laya-compact-imitation/v12-fresh'
VALUE = c.SHARED / 'datasets/generated/laya-value/v1'
ANCHOR = VALUE / 'anchor'
FOE_SOURCE = c.SHARED / 'datasets/generated/laya-foe/v1/foe-train.jsonl'
FOE = VALUE / 'foe-anchor.jsonl'
ANCHOR_ROWS = 150000
FOE_ROWS = 100000
SEED = 20261200
GPUS = '0,1,2,3'


def prepare():
    from .data_value import game_of, heldout_games, sample_id_of
    if (ANCHOR / 'manifest.json').exists() and FOE.exists():
        return
    held = heldout_games()
    ANCHOR.mkdir(parents=True, exist_ok=True)
    keep = [i for i, line in enumerate(open(FRESH / 'train.jsonl')) if game_of(sample_id_of(line)) not in held]
    pick = set(random.Random(SEED).sample(keep, min(ANCHOR_ROWS, len(keep))))
    with open(FRESH / 'train.jsonl') as f, open(ANCHOR / 'train.jsonl', 'w') as out:
        for i, line in enumerate(f):
            if i in pick:
                out.write(line)
    shutil.copyfile(FRESH / 'validation.jsonl', ANCHOR / 'validation.jsonl')
    n = sum(1 for _ in open(FOE_SOURCE))
    fpick = set(random.Random(SEED + 1).sample(range(n), min(FOE_ROWS, n)))
    with open(FOE_SOURCE) as f, open(FOE, 'w') as out:
        for i, line in enumerate(f):
            if i in fpick:
                out.write(line)
    (ANCHOR / 'manifest.json').write_text(json.dumps(dict(
        source=str(FRESH), rows=len(pick), of=len(keep), excluded_heldout_games=len(held), seed=SEED,
        foe=dict(source=str(FOE_SOURCE), rows=len(fpick), of=n, seed=SEED + 1)), indent=1))


def arguments(mode):
    return [mode, '--experiment', 'EX-200', '--gpus', GPUS, '--dataset', str(ANCHOR), '--init', str(INIT),
            '--out', str(RUN), '--extra', str(VALUE / 'train.jsonl'), str(FOE), str(c.TERA_KNOWLEDGE / 'train.jsonl')]


def launch(mode):
    from integration.laya_imitation.resources import gpu
    from integration.laya_ladder.train_ddp import UUIDS
    from integration.laya_v11 import train_v11 as T
    T.RUNS['EX-200'] = RUN
    args = T.defaults(T._parser().parse_args(arguments(mode)))
    indices = [int(x) for x in args.gpus.split(',')]
    status = Path(args.out) / 'status.json'
    if mode == 'train' and status.exists():
        raise SystemExit('%s already started (%s); no automatic re-run' % (args.out, status.read_text()))
    with ExitStack() as stack:
        for index in indices:
            stack.enter_context(gpu(index, UUIDS[index]))
        env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID',
                   CUDA_VISIBLE_DEVICES=','.join(UUIDS[i] for i in indices), OMP_NUM_THREADS='8',
                   TOKENIZERS_PARALLELISM='false')
        Path(args.out).mkdir(parents=True, exist_ok=True)
        worker = ['--worker', mode, '--experiment', 'EX-200', '--gpus', args.gpus, '--dataset', args.dataset,
                  '--init', args.init, '--out', args.out, '--head', str(args.head), '--max-len', str(args.max_len),
                  '--warmup', str(args.warmup), '--updates', str(args.updates), '--memory-rows', str(args.memory_rows),
                  '--extra', *args.extra]
        cmd = [sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc_per_node', str(len(indices)),
               '-m', 'integration.laya_value.train_value', *worker]
        return subprocess.call(cmd, env=env, cwd=str(c.ROOT))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        from integration.laya_v11 import train_v11 as T
        T.RUNS['EX-200'] = RUN
        T._worker_main(sys.argv[2:])
    elif sys.argv[1] == 'prepare':
        prepare()
    else:
        sys.exit(launch(sys.argv[1]))
