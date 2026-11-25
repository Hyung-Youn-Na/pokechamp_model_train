"""EP-248 / D-224 (EX-226, Way B): GPU 0·1 DDP 1-epoch train -> GPU 0 offline eval (`with_eval` & `no_eval`).

    python -m integration.laya_v14.train_way_b train     (physical GPU 0 & GPU 1 ONLY)
    python -m integration.laya_v14.train_way_b eval      (physical GPU 0 ONLY)
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

from integration.laya_imitation import config as c
from integration.laya_search import search_core as SC
from integration.laya_v14.train_way_c1_v3 import score_policy_rows

RUN = c.SHARED / 'runs/model-training/EX-226'
INIT = c.SHARED / 'runs/model-training/EX-196/checkpoints/selected'
DATA = c.SHARED / 'datasets/generated/laya-v14w-wayb/v1'
ANCHOR = DATA / 'anchor_noduel'
FOE = DATA / 'foe-anchor_noduel.jsonl'
HARD_REPEAT = 3
GENERAL_REPEAT = 2
GPUS = '0,1'


def arguments(mode: str) -> list[str]:
    extras = (
        [str(DATA / 'hard_train.jsonl')] * HARD_REPEAT
        + [str(DATA / 'general_train.jsonl')] * GENERAL_REPEAT
        + [str(FOE), str(c.TERA_KNOWLEDGE / 'train.jsonl')]
    )
    return [
        mode, '--experiment', 'EX-226', '--gpus', GPUS, '--dataset', str(ANCHOR),
        '--init', str(INIT), '--out', str(RUN),
        '--extra', *extras,
    ]


def launch(mode: str) -> int:
    from integration.laya_imitation.resources import gpu
    from integration.laya_v11 import train_v11 as T

    T.RUNS['EX-226'] = RUN
    args = T.defaults(T._parser().parse_args(arguments(mode)))
    indices = [int(x) for x in args.gpus.split(',')]
    if indices != [0, 1]:
        raise RuntimeError('EP-248 strictly restricts training to GPU 0 & 1 only; got %r' % (indices,))
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
            OMP_NUM_THREADS='4',
            MKL_NUM_THREADS='4',
            TOKENIZERS_PARALLELISM='false',
        )
        Path(args.out).mkdir(parents=True, exist_ok=True)
        worker = [
            '--worker', mode, '--experiment', 'EX-226', '--gpus', args.gpus, '--dataset', args.dataset,
            '--init', args.init, '--out', args.out, '--head', str(args.head), '--max-len', str(args.max_len),
            '--warmup', str(args.warmup), '--updates', str(args.updates), '--memory-rows', str(args.memory_rows),
            '--extra', *args.extra,
        ]
        cmd = [
            sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc_per_node', '2',
            '-m', 'integration.laya_v14.train_way_b', *worker,
        ]
        return subprocess.call(cmd, env=env, cwd=str(c.ROOT))


def evaluate_heldout() -> dict:
    """Offline report-only evaluation (D-191) on physical GPU 0 ONLY:
    Measures BOTH `with_eval` (tool-assisted) AND `no_eval` (Tool-Dropout standalone robustness) + Tera + HP-recovery!
    """
    import torch
    from integration.laya_imitation.evaluation_tera import knowledge
    from integration.laya_imitation.resources import gpu
    from integration.laya_imitation.storage import atomic
    from integration.laya_ladder import paths as ladder
    from integration.laya_v10 import training_v10

    training_v10.install(ladder.OPTION_LIMIT)
    import laya.train as LT
    orig_fwd = LT._forward
    LT._forward = lambda m, b, d, amp, detach_encoder: orig_fwd(m, b, d, True, detach_encoder)

    RUNS = c.SHARED / 'runs/model-training'
    rng = random.Random(20261226)
    gen_w_lines = (DATA / 'heldout_with_eval.jsonl').read_text().splitlines()
    gen_n_lines = (DATA / 'heldout_no_eval.jsonl').read_text().splitlines()
    idx_gen = sorted(rng.sample(range(len(gen_w_lines)), min(2000, len(gen_w_lines))))
    gen_w = [json.loads(gen_w_lines[i]) for i in idx_gen]
    gen_n = [json.loads(gen_n_lines[i]) for i in idx_gen]

    hard_w = [json.loads(l) for l in (DATA / 'hard_heldout_with_eval.jsonl').read_text().splitlines() if l.strip()]
    hard_n = [json.loads(l) for l in (DATA / 'hard_heldout_no_eval.jsonl').read_text().splitlines() if l.strip()]

    with gpu(0, SC.GPU0_UUID) as (env, _):
        os.environ.update(env)
        (RUN / 'evaluation').mkdir(exist_ok=True)
        models_out = {}
        cands = [
            ('ex200', RUNS / 'EX-200/checkpoints/selected'),
            ('ex225_way_c1_clean', RUNS / 'EX-225/checkpoints/selected'),
            ('ex226_way_b', RUN / 'checkpoints/selected'),
        ]
        for key, ckpt in cands:
            if not (ckpt / 'rl_agent_config.json').exists() and not (ckpt / 'model.safetensors').exists():
                continue
            pol = training_v10.Policy10(ckpt, head_limit=ladder.HEAD_LIMIT)
            models_out[key] = dict(
                hard_with_eval=score_policy_rows(pol, hard_w, 'ex225'),
                hard_no_eval=score_policy_rows(pol, hard_n, 'ex225'),
                general_2k_with_eval=score_policy_rows(pol, gen_w, 'ex209'),
                general_2k_no_eval=score_policy_rows(pol, gen_n, 'ex209'),
            )
            print(f'[ex226-eval] {key}: {json.dumps(models_out[key])}', flush=True)
            del pol
            torch.cuda.empty_cache()

        know = knowledge('ex226', RUN / 'checkpoints/selected', RUN)
        tera = {k: round(know[k]['all']['accuracy'], 4) for k in ('heldout-A', 'heldout-B') if k in know}
        print('[ex226-eval] Tera knowledge:', tera, flush=True)
        summary = dict(experiment='EX-226', decision='D-224', at=time.time(), models=models_out, tera_knowledge=tera)
        atomic(RUN / 'evaluation/summary.json', summary)
        atomic(RUN / 'status.json', dict(stage='completed', at=time.time()))
    return summary


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        from integration.laya_v11 import train_v11 as T
        T.RUNS['EX-226'] = RUN
        T._worker_main(sys.argv[2:])
    elif sys.argv[1] == 'eval':
        evaluate_heldout()
    else:
        sys.exit(launch(sys.argv[1]))
