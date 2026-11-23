"""EX-183 (D-215): v11rtc (EX-172 selected) + foul-play search distillation, one epoch on GPU 0-3 (laya env).

    python -m integration.laya_distill.train_distill {measure,train}

`laya_v11.train_v11` unchanged (soft-CE, one epoch, 4 validation points, cosine lr, `act_head` frozen, temperature
refit on EX-167's calibration lines); this module only fixes its arguments and registers EX-183:
- `--dataset` laya-distill/v1: `train.jsonl` is `v11-ladder-merged` train (a link), `validation.jsonl` the EX-182
  teacher validation rows (gold targets), so the selected point is the one closest to the teacher;
- `--weights` laya-distill/v1/human-weights: EX-172's weights on a random HUMAN_SHARE of the rows, 0 elsewhere
  (and 0 on the teacher validation games);
- `--extra`: the Tera knowledge rows, EX-172's correction rows repeated to about 2% of the training rows, and the
  EX-182 teacher train rows TEACHER_REPEAT times;
- `--init` EX-172 `checkpoints/selected`, GPUs 0-3 (micro 8 x accumulation 2 x 4 = 64).
The workers run this module (`--worker`), so the registration applies in every rank.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

from integration.laya_distill import paths as P
from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic, sha
from integration.laya_ladder import train_ddp as D
from integration.laya_v11 import train_v11 as V
from integration.laya_v11 import policy as V11P

EXPERIMENT = 'EX-183'
V.RUNS[EXPERIMENT] = P.TRAIN_RUN
_freeze = V._freeze


def _freeze_distill(args, out, files, config, world, accum, split):
    _freeze(args, out, files, config, world, accum, split)
    here = Path(__file__).parent
    atomic(out / 'source/laya_distill.json', {p.name: sha(p) for p in sorted(here.glob('*.py'))}, immutable=True)


V._freeze = _freeze_distill


def arguments(mode):
    tera = str(c.TERA_KNOWLEDGE / 'train.jsonl')
    teacher = P.DATA / 'teacher-train.jsonl'
    corrections = V11P.OUT_CORRECTIONS / 'train.jsonl'
    weights = [json.loads(line)['weight'] for line in open(P.DATA / 'human-weights/weights.jsonl')]
    kept = sum(1 for w in weights if w > 0)
    base = kept + D._count(tera) + P.TEACHER_REPEAT * D._count(teacher)
    times = max(1, round(V.CORRECTION_SHARE * base / D._count(corrections)))
    extra = [tera] + [str(corrections)] * times + [str(teacher)] * P.TEACHER_REPEAT
    return [mode, '--experiment', EXPERIMENT, '--gpus', '0,1,2,3', '--dataset', str(P.DATA),
            '--init', str(P.EX172 / 'checkpoints/selected'), '--out', str(P.TRAIN_RUN),
            '--weights', str(P.DATA / 'human-weights'), '--extra', *extra]


def launch(mode):
    args = V.defaults(V._parser().parse_args(arguments(mode)))
    import os
    import subprocess
    from contextlib import ExitStack
    from integration.laya_imitation.resources import gpu
    indices = [int(x) for x in args.gpus.split(',')]
    status = Path(args.out) / 'status.json'
    if args.mode == 'train' and status.exists():
        raise SystemExit('%s already started (%s); no automatic re-run' % (args.out, status.read_text()))
    with ExitStack() as stack:
        for index in indices:
            stack.enter_context(gpu(index, D.UUIDS[index]))
        env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID',
                   CUDA_VISIBLE_DEVICES=','.join(D.UUIDS[i] for i in indices), OMP_NUM_THREADS='8',
                   TOKENIZERS_PARALLELISM='false')
        Path(args.out).mkdir(parents=True, exist_ok=True)
        worker = ['--worker', args.mode, '--experiment', args.experiment, '--gpus', args.gpus, '--dataset', args.dataset,
                  '--init', args.init, '--out', args.out, '--head', str(args.head), '--max-len', str(args.max_len),
                  '--warmup', str(args.warmup), '--updates', str(args.updates), '--memory-rows', str(args.memory_rows),
                  '--weights', args.weights, '--extra', *args.extra]
        cmd = [sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc_per_node', str(len(indices)),
               '-m', 'integration.laya_distill.train_distill', *worker]
        return subprocess.call(cmd, env=env, cwd=str(c.ROOT))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        V._worker_main(sys.argv[2:])
    else:
        sys.exit(launch(sys.argv[1]))
