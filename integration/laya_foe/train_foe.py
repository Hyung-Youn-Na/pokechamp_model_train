"""EX-196 (EP-238, D-216): one epoch from EX-192 selected on fresh imitation rows + opponent-action rows + Tera knowledge.

    python -m integration.laya_foe.train_foe measure|train        (laya env, GPU 0-3)

`laya_v11.train_v11` unchanged (EX-172's continuation loop: one epoch, validation at 25/50/75/100%, the lowest
validation NLL point selected and its temperature refitted); this wrapper registers EX-196, fixes the arguments and
starts the workers on this module with all four GPUs (micro 8 x accumulation 2 x 4 = EX-167's batch of 64).
- dataset: `v12-fresh` (EX-195: v12-ladder rows of the ladder games EX-192 did not use, minus the held-out games;
  validation = v12-ladder-merged validation, the same as EX-192's);
- extra: EX-195 `foe-train.jsonl` (opponent-action rows) and the Tera knowledge rows (as EX-167 / EX-192).
"""
from __future__ import annotations

from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import sys

from integration.laya_imitation import config as c
from integration.laya_imitation.resources import gpu
from integration.laya_ladder.train_ddp import UUIDS
from integration.laya_v11 import train_v11 as T

RUN = c.SHARED / 'runs/model-training/EX-196'
INIT = c.SHARED / 'runs/model-training/EX-192/checkpoints/selected'
FRESH = c.SHARED / 'datasets/generated/laya-compact-imitation/v12-fresh'
FOE = c.SHARED / 'datasets/generated/laya-foe/v1/foe-train.jsonl'
GPUS = '0,1,2,3'
T.RUNS['EX-196'] = RUN


def arguments(mode):
    return [mode, '--experiment', 'EX-196', '--gpus', GPUS, '--dataset', str(FRESH), '--init', str(INIT),
            '--out', str(RUN), '--extra', str(FOE), str(c.TERA_KNOWLEDGE / 'train.jsonl')]


def launch(mode):
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
        worker = ['--worker', mode, '--experiment', 'EX-196', '--gpus', args.gpus, '--dataset', args.dataset,
                  '--init', args.init, '--out', args.out, '--head', str(args.head), '--max-len', str(args.max_len),
                  '--warmup', str(args.warmup), '--updates', str(args.updates), '--memory-rows', str(args.memory_rows),
                  '--extra', *args.extra]
        cmd = [sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc_per_node', str(len(indices)),
               '-m', 'integration.laya_foe.train_foe', *worker]
        return subprocess.call(cmd, env=env, cwd=str(c.ROOT))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        T._worker_main(sys.argv[2:])
    else:
        sys.exit(launch(sys.argv[1]))
