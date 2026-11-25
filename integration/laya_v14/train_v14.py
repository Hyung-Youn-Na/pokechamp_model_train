"""EP-244 / D-220 (EX-213): One-epoch DDP training of v14 recovery/absorb-aware model on GPU 0 & 1 ONLY.

    python -m integration.laya_v14.train_v14 train     (laya env, physical GPU 0 & 1 ONLY)
    python -m integration.laya_v14.train_v14 eval      (laya env, physical GPU 0 ONLY)

Strictly pins physical GPU 0 & GPU 1 (`0,1`, UUIDs `GPU-4f27dd5a-...` and `GPU-c7e2d577-...`). GPUs 2 and 3 are
NEVER touched. Uses `EX-196` selected init (controlled comparison vs EX-209) + `v14` MCTS-5k Q gold (x2) +
`v14` human anchor (150k) + `v14` clean-PP foe anchor (100k) + Tera knowledge rows.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time

from integration.laya_imitation import config as c
from integration.laya_search import search_core as SC

RUN = c.SHARED / 'runs/model-training/EX-213'
INIT = c.SHARED / 'runs/model-training/EX-196/checkpoints/selected'
V14_DATA = c.SHARED / 'datasets/generated/laya-v14-mcts5k-q/v1'
ANCHOR = V14_DATA / 'anchor'
FOE = V14_DATA / 'foe-anchor.jsonl'
GOLD_REPEAT = 2
GPUS = '0,1'


def arguments(mode: str) -> list[str]:
    gold_files = [str(V14_DATA / 'train.jsonl')] * GOLD_REPEAT
    return [
        mode, '--experiment', 'EX-213', '--gpus', GPUS, '--dataset', str(ANCHOR),
        '--init', str(INIT), '--out', str(RUN),
        '--extra', *gold_files, str(FOE), str(c.TERA_KNOWLEDGE / 'train.jsonl'),
    ]


def launch(mode: str) -> int:
    from integration.laya_imitation.resources import gpu
    from integration.laya_v11 import train_v11 as T

    T.RUNS['EX-213'] = RUN
    args = T.defaults(T._parser().parse_args(arguments(mode)))
    indices = [int(x) for x in args.gpus.split(',')]
    if indices != [0, 1]:
        raise RuntimeError('EP-244 strictly restricts training to GPU 0 & 1 only; got %r' % (indices,))
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
            '--worker', mode, '--experiment', 'EX-213', '--gpus', args.gpus, '--dataset', args.dataset,
            '--init', args.init, '--out', args.out, '--head', str(args.head), '--max-len', str(args.max_len),
            '--warmup', str(args.warmup), '--updates', str(args.updates), '--memory-rows', str(args.memory_rows),
            '--extra', *args.extra,
        ]
        cmd = [
            sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc_per_node', '2',
            '-m', 'integration.laya_v14.train_v14', *worker,
        ]
        return subprocess.call(cmd, env=env, cwd=str(c.ROOT))


def evaluate_heldout():
    """Offline report-only evaluation (D-191) on GPU 0 ONLY: v14 held-out MCTS-5k Q + Tera knowledge."""
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
    held_path = V14_DATA / 'heldout.jsonl'
    lines = held_path.read_text().splitlines()
    rng = random.Random(20261213)
    idxs = sorted(rng.sample(range(len(lines)), min(2000, len(lines))))
    rows = [json.loads(lines[i]) for i in idxs]

    def score_model(ckpt, label):
        pol = training_v10.Policy10(ckpt, head_limit=ladder.HEAD_LIMIT)
        ce_sum = kl_sum = 0.0
        m_gold = m_human = m_laya = fs_n = fs_gold = changed_n = changed_gold = 0
        for start in range(0, len(rows), 512):
            chunk = rows[start:start + 512]
            items = [pol.item(r['state'], r['questions']['action']) for r in chunk]
            logits = pol.logits(items, batch_size=32)
            for r, z in zip(chunk, logits):
                ids = list(r['questions']['action']['criteria'])
                p_list, _ = pol.distribution(z, len(ids))
                probs = dict(zip(ids, p_list))
                g = r['gold']['action']['probabilities']
                meta = r.get('meta', {}).get('ex209', {})
                gold_top = max(g, key=g.get)
                pred_top = max(probs, key=probs.get)
                ce = -sum(v * math.log(max(1e-12, probs.get(k, 0.0))) for k, v in g.items() if v > 0)
                ht = -sum(v * math.log(max(1e-12, v)) for v in g.values() if v > 0)
                ce_sum += ce
                kl_sum += (ce - ht)
                m_gold += int(pred_top == gold_top)
                if meta.get('label') is not None:
                    m_human += int(pred_top == meta['label'])
                if meta.get('laya_argmax') is not None:
                    m_laya += int(pred_top == meta['laya_argmax'])
                    if gold_top != meta['laya_argmax']:
                        changed_n += 1
                        changed_gold += int(pred_top == gold_top)
                if ':forced_switch' in r.get('sample_id', ''):
                    fs_n += 1
                    fs_gold += int(pred_top == gold_top)
        n = len(rows)
        res = dict(
            label=label, n=n,
            gold_ce=round(ce_sum / n, 4),
            gold_kl=round(kl_sum / n, 4),
            match_gold_argmax=round(m_gold / n, 4),
            match_human=round(m_human / n, 4),
            match_laya_argmax=round(m_laya / n, 4),
            changed_n=changed_n,
            changed_match_gold=round(changed_gold / max(changed_n, 1), 4),
            fs_n=fs_n,
            fs_match_gold=round(fs_gold / max(fs_n, 1), 4),
        )
        print('[ex213-eval] %s: %s' % (label, json.dumps(res)), flush=True)
        del pol
        torch.cuda.empty_cache()
        return res

    with gpu(0, SC.ALLOWED_GPU_UUIDS[0]) as (env, _):
        os.environ.update(env)
        (RUN / 'evaluation').mkdir(exist_ok=True)
        summary = dict(
            at=time.time(),
            seed=20261213,
            heldout_sample=len(rows),
            heldout_total=len(lines),
            models={
                'ex196_on_v14': score_model(RUNS / 'EX-196/checkpoints/selected', 'EX-196 on v14'),
                'ex209_on_v14': score_model(RUNS / 'EX-209/checkpoints/selected', 'EX-209 on v14'),
                'ex213_v14': score_model(RUN / 'checkpoints/selected', 'EX-213 (v14 MCTS-5k Q)'),
            },
        )
        know = knowledge('ex213', RUN / 'checkpoints/selected', RUN)
        summary['tera_knowledge'] = {k: round(know[k]['all']['accuracy'], 4) for k in ('heldout-A', 'heldout-B') if k in know}
        print('[ex213-eval] Tera knowledge:', summary['tera_knowledge'], flush=True)
        atomic(RUN / 'evaluation/summary.json', summary)
        atomic(RUN / 'status.json', dict(stage='completed', at=time.time()))
    return summary


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        from integration.laya_v11 import train_v11 as T
        T.RUNS['EX-213'] = RUN
        T._worker_main(sys.argv[2:])
    elif sys.argv[1] == 'eval':
        evaluate_heldout()
    else:
        sys.exit(launch(sys.argv[1]))
