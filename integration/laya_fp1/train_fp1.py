"""EX-178 (D-213): EX-167's training on the fp1 rows, from the same start (`laya-typed-decisions@e929ae5c`).

    python -m integration.laya_fp1.train_fp1 {check,measure,train}      (laya env; GPU0-3, idle, pinned UUIDs)

`laya_ladder.train_ddp` unchanged (laya's encoding, soft-CE, per-window scaling, 3 epochs, micro 8 x accum 2 x 4,
`act_head` frozen, epoch selection and temperature as EX-167). Only these differ:
- `--dataset` fp1-ladder-merged, `--extra` empty (no tera knowledge rows, D-213 decision 4), `--out` EX-178;
- the run freeze records EX-178 (not EX-167) and the `laya_fp1` source hashes next to `laya_ladder`'s.
The workers run this module (`--worker`), so the replaced freeze applies in every rank.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys

from integration.laya_imitation import config as c
from integration.laya_imitation.resources import gpu
from integration.laya_imitation.storage import atomic, sha
from integration.laya_ladder import paths
from integration.laya_ladder import train_ddp as D

RUN = c.SHARED / 'runs/model-training/EX-178'
DATASET = c.SHARED / 'datasets/generated/laya-compact-imitation/fp1-ladder-merged'
FIXED = ['--dataset', str(DATASET), '--extra', '--out', str(RUN)]


def _freeze(out, dataset, files, config):
    from integration.laya_imitation.storage import source_identity
    from integration.project_context.registry import freeze_document, resolve_record
    if (out / 'protocol/EX-178.md').exists():
        return
    freeze_document(resolve_record('EX-178'), out / 'protocol/EX-178.md')
    here = Path(__file__).parent
    atomic(out / 'source/identity.json', dict(
        source_identity(),
        laya_ladder={p.name: sha(p) for p in sorted(Path(D.__file__).parent.glob('*.py'))},
        laya_fp1={p.name: sha(p) for p in sorted(here.glob('*.py'))}), immutable=True)
    atomic(out / 'source/dataset-manifest.json', json.loads((dataset / 'manifest.json').read_text()), immutable=True)
    atomic(out / 'protocol/train-config.json', dict(
        {k: list(v) if isinstance(v, tuple) else v for k, v in vars(config).items()},
        base=str(c.MODEL_DIR), revision=c.MODEL_REVISION, files=files, world=paths.WORLD,
        grad_accum_per_gpu=paths.GRAD_ACCUM, frozen=D.UNUSED_PREFIX), immutable=True)


def launch(argv):
    args = D._parser().parse_args(argv)
    status = Path(args.out) / 'status.json'
    if args.mode == 'train' and status.exists():
        raise SystemExit('%s already started (%s); no automatic re-run' % (args.out, status.read_text()))
    with ExitStack() as stack:
        for index in paths.GPUS:
            stack.enter_context(gpu(index, D.UUIDS[index]))
        env = dict(os.environ, CUDA_DEVICE_ORDER='PCI_BUS_ID',
                   CUDA_VISIBLE_DEVICES=','.join(D.UUIDS[i] for i in paths.GPUS), OMP_NUM_THREADS='8',
                   TOKENIZERS_PARALLELISM='false')
        Path(args.out).mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc_per_node', str(paths.WORLD),
               '-m', 'integration.laya_fp1.train_fp1', '--worker', *argv]
        return subprocess.call(cmd, env=env, cwd=str(c.ROOT))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        D._freeze = _freeze
        D._worker_main(sys.argv[2:])
    else:
        sys.exit(launch(sys.argv[1:2] + FIXED + sys.argv[2:]))
