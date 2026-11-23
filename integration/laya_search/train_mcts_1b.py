"""EP-243 / D-219 (EX-209, 1-B): One-epoch DDP training from EX-196 on MCTS-5k Q soft targets + anchors (GPU 0·1 ONLY).

    python -m integration.laya_search.train_mcts_1b prepare        (any python 3: build anchor files, once)
    python -m integration.laya_search.train_mcts_1b measure|train  (laya env, physical GPU 0 & 1 ONLY)

Strictly pins physical GPU 0 & GPU 1 (`0,1`, UUIDs `GPU-4f27dd5a-...` and `GPU-c7e2d577-...`). GPUs 2 and 3 are
NEVER touched. `train_v11` automatically uses `micro 8 x accum 4 x 2 GPUs = effective batch 64` (identical to EX-200).
Repeats the ~60k MCTS-5k Q gold rows 2x alongside 150k human anchor + 100k foe anchor + Tera knowledge rows so gold
target share (~32%) matches EX-200's successful ratio.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys

from integration.laya_imitation import config as c

from . import search_core as SC

RUN = c.SHARED / 'runs/model-training/EX-209'
INIT = c.SHARED / 'runs/model-training/EX-196/checkpoints/selected'
FRESH = c.SHARED / 'datasets/generated/laya-compact-imitation/v12-fresh'
MCTS_DATA = c.SHARED / 'datasets/generated/laya-mcts5k-q/v1'
ANCHOR = MCTS_DATA / 'anchor'
FOE_SOURCE = c.SHARED / 'datasets/generated/laya-foe/v1/foe-train.jsonl'
FOE = MCTS_DATA / 'foe-anchor.jsonl'
ANCHOR_ROWS = 150000
FOE_ROWS = 100000
GOLD_REPEAT = 2
SEED = 20261209
GPUS = '0,1'


def prepare():
    from .data_mcts_1b import game_of, sample_id_of, selected_games
    if (ANCHOR / 'manifest.json').exists() and FOE.exists():
        return
    held = set(selected_games()['heldout'])
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
        foe=dict(source=str(FOE_SOURCE), rows=len(fpick), of=n, seed=SEED + 1),
        gold_repeat=GOLD_REPEAT), indent=1))


def arguments(mode: str) -> list[str]:
    gold_files = [str(MCTS_DATA / 'train.jsonl')] * GOLD_REPEAT
    return [
        mode, '--experiment', 'EX-209', '--gpus', GPUS, '--dataset', str(ANCHOR),
        '--init', str(INIT), '--out', str(RUN),
        '--extra', *gold_files, str(FOE), str(c.TERA_KNOWLEDGE / 'train.jsonl'),
    ]


def launch(mode: str) -> int:
    from integration.laya_imitation.resources import gpu
    from integration.laya_v11 import train_v11 as T

    T.RUNS['EX-209'] = RUN
    args = T.defaults(T._parser().parse_args(arguments(mode)))
    indices = [int(x) for x in args.gpus.split(',')]
    if indices != [0, 1]:
        raise RuntimeError('EP-243 strictly restricts training to GPU 0 & 1 only; got %r' % (indices,))
    status = Path(args.out) / 'status.json'
    if mode == 'train' and status.exists():
        raise SystemExit('%s already started (%s); no automatic re-run' % (args.out, status.read_text()))
    with ExitStack() as stack:
        for index in indices:
            stack.enter_context(gpu(index, SC.ALLOWED_GPU_UUIDS[index]))
        env = dict(
            os.environ,
            CUDA_DEVICE_ORDER='PCI_BUS_ID',
            CUDA_VISIBLE_DEVICES=','.join(SC.ALLOWED_GPU_UUIDS[i] for i in indices),
            OMP_NUM_THREADS='8',
            TOKENIZERS_PARALLELISM='false',
        )
        Path(args.out).mkdir(parents=True, exist_ok=True)
        worker = [
            '--worker', mode, '--experiment', 'EX-209', '--gpus', args.gpus, '--dataset', args.dataset,
            '--init', args.init, '--out', args.out, '--head', str(args.head), '--max-len', str(args.max_len),
            '--warmup', str(args.warmup), '--updates', str(args.updates), '--memory-rows', str(args.memory_rows),
            '--extra', *args.extra,
        ]
        cmd = [
            sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc_per_node', '2',
            '-m', 'integration.laya_search.train_mcts_1b', *worker,
        ]
        return subprocess.call(cmd, env=env, cwd=str(c.ROOT))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        from integration.laya_v11 import train_v11 as T
        T.RUNS['EX-209'] = RUN
        T._worker_main(sys.argv[2:])
    elif sys.argv[1] == 'prepare':
        prepare()
    else:
        sys.exit(launch(sys.argv[1]))
