"""EP-246 / D-222 (EX-218, Way C-1): Wait for GPU 0 idle -> GPU 0·1 DDP 1-epoch train -> GPU 0 offline eval.

    python -m integration.laya_v14.train_way_c1 wait-gpu0
    python -m integration.laya_v14.train_way_c1 train     (physical GPU 0 & GPU 1 ONLY)
    python -m integration.laya_v14.train_way_c1 eval      (physical GPU 0 ONLY)

Strictly pins physical GPU 0 & GPU 1 (`0,1`). Physical GPUs 2 & 3 are NEVER touched.
Training mix (~540k rows from EX-196):
- `hard_train.jsonl` (~25k Hard-Example MCTS 50k + EX-216 V_phi v2) x 3 repeats
- `general_train.jsonl` (~100k general MCTS 5k on v14+walled_duel) x 2 repeats
- `anchor/train.jsonl` (150k human high-Elo anchor on v14+walled_duel)
- `foe-anchor.jsonl` (100k clean-PP opponent anchor on v14+walled_duel)
- `tera-knowledge/train.jsonl`
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

RUN = c.SHARED / 'runs/model-training/EX-218'
INIT = c.SHARED / 'runs/model-training/EX-196/checkpoints/selected'
DATA = c.SHARED / 'datasets/generated/laya-v14w-c1/v1'
ANCHOR = DATA / 'anchor'
FOE = DATA / 'foe-anchor.jsonl'
HARD_REPEAT = 3
GENERAL_REPEAT = 2
GPUS = '0,1'


def wait_gpu0(poll_seconds: int = 30) -> None:
    """Block cleanly until physical GPU 0 is completely idle (< 100 MiB and no compute apps, i.e., EX-217 finished)."""
    from integration.laya_imitation.resources import gpu_processes, gpus

    started = time.time()
    while True:
        dev = next(g for g in gpus() if g['index'] == 0)
        procs = [p for p, u in gpu_processes() if u == SC.GPU0_UUID]
        if dev['uuid'] != SC.GPU0_UUID:
            raise RuntimeError('GPU 0 UUID mismatch: %s' % dev['uuid'])
        if dev['memory_mib'] < 100 and not procs:
            print(f'[ex218-wait] GPU 0 is idle ({dev["memory_mib"]} MiB) after {(time.time()-started)/60:.1f} min -> starting DDP!', flush=True)
            return
        print(f'[ex218-wait] {time.strftime("%H:%M:%SZ", time.gmtime())} waiting for GPU 0 (EX-217): {dev["memory_mib"]} MiB, procs={len(procs)}', flush=True)
        time.sleep(poll_seconds)


def arguments(mode: str) -> list[str]:
    extras = (
        [str(DATA / 'hard_train.jsonl')] * HARD_REPEAT
        + [str(DATA / 'general_train.jsonl')] * GENERAL_REPEAT
        + [str(FOE), str(c.TERA_KNOWLEDGE / 'train.jsonl')]
    )
    return [
        mode, '--experiment', 'EX-218', '--gpus', GPUS, '--dataset', str(ANCHOR),
        '--init', str(INIT), '--out', str(RUN),
        '--extra', *extras,
    ]


def launch(mode: str) -> int:
    from integration.laya_imitation.resources import gpu
    from integration.laya_v11 import train_v11 as T

    T.RUNS['EX-218'] = RUN
    args = T.defaults(T._parser().parse_args(arguments(mode)))
    indices = [int(x) for x in args.gpus.split(',')]
    if indices != [0, 1]:
        raise RuntimeError('EP-246 strictly restricts training to GPU 0 & 1 only; got %r' % (indices,))
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
            '--worker', mode, '--experiment', 'EX-218', '--gpus', args.gpus, '--dataset', args.dataset,
            '--init', args.init, '--out', args.out, '--head', str(args.head), '--max-len', str(args.max_len),
            '--warmup', str(args.warmup), '--updates', str(args.updates), '--memory-rows', str(args.memory_rows),
            '--extra', *args.extra,
        ]
        cmd = [
            sys.executable, '-m', 'torch.distributed.run', '--standalone', '--nproc_per_node', '2',
            '-m', 'integration.laya_v14.train_way_c1', *worker,
        ]
        return subprocess.call(cmd, env=env, cwd=str(c.ROOT))


def evaluate_heldout() -> dict:
    """Offline report-only evaluation (D-191) on physical GPU 0 ONLY:
    1. General held-out MCTS-5k Q (2,000 rows),
    2. Hard-Example held-out MCTS 50k + EX-216 V_phi v2 (all ~3,000 rows, plus `walled` subset),
    3. Tera knowledge `heldout-A` & `heldout-B`.
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
    gen_lines = (DATA / 'heldout.jsonl').read_text().splitlines()
    rng = random.Random(20261218)
    gen_rows = [json.loads(gen_lines[i]) for i in sorted(rng.sample(range(len(gen_lines)), min(2000, len(gen_lines))))]
    hard_rows = [json.loads(l) for l in (DATA / 'hard_heldout.jsonl').read_text().splitlines() if l.strip()]

    def _score_rows(pol, rows, meta_key):
        ce_sum = kl_sum = 0.0
        m_gold = m_human = chg_n = chg_gold = wall_n = wall_gold = 0
        for start in range(0, len(rows), 512):
            chunk = rows[start:start + 512]
            items = [pol.item(r['state'], r['questions']['action']) for r in chunk]
            logits = pol.logits(items, batch_size=32)
            for r, z in zip(chunk, logits):
                ids = list(r['questions']['action']['criteria'])
                p_list, _ = pol.distribution(z, len(ids))
                probs = dict(zip(ids, p_list))
                g = r['gold']['action']['probabilities']
                meta = (r.get('meta') or {}).get(meta_key) or (r.get('meta') or {}).get('ex209') or {}
                gold_top = max(g, key=g.get)
                pred_top = max(probs, key=probs.get)
                ce = -sum(v * math.log(max(1e-12, probs.get(k, 0.0))) for k, v in g.items() if v > 0)
                ht = -sum(v * math.log(max(1e-12, v)) for v in g.values() if v > 0)
                ce_sum += ce
                kl_sum += (ce - ht)
                m_gold += int(pred_top == gold_top)
                if meta.get('label') is not None:
                    m_human += int(pred_top == meta['label'])
                if meta.get('laya_argmax') is not None and gold_top != meta['laya_argmax']:
                    chg_n += 1
                    chg_gold += int(pred_top == gold_top)
                if meta.get('walled'):
                    wall_n += 1
                    wall_gold += int(pred_top == gold_top)
        n = max(1, len(rows))
        return dict(
            n=len(rows),
            gold_ce=round(ce_sum / n, 4),
            gold_kl=round(kl_sum / n, 4),
            match_gold_argmax=round(m_gold / n, 4),
            match_human=round(m_human / n, 4),
            changed_n=chg_n,
            changed_match_gold=round(chg_gold / max(1, chg_n), 4),
            walled_n=wall_n,
            walled_match_gold=round(wall_gold / max(1, wall_n), 4) if wall_n else None,
        )

    with gpu(0, SC.GPU0_UUID) as (env, _):
        os.environ.update(env)
        (RUN / 'evaluation').mkdir(exist_ok=True)
        models_out = {}
        for key, ckpt in (
            ('ex196', RUNS / 'EX-196/checkpoints/selected'),
            ('ex200', RUNS / 'EX-200/checkpoints/selected'),
            ('ex209', RUNS / 'EX-209/checkpoints/selected'),
            ('ex218_way_c1', RUN / 'checkpoints/selected'),
        ):
            pol = training_v10.Policy10(ckpt, head_limit=ladder.HEAD_LIMIT)
            models_out[key] = dict(
                general_2k=_score_rows(pol, gen_rows, 'ex209'),
                hard_50k_vphi2=_score_rows(pol, hard_rows, 'ex218'),
            )
            print(f'[ex218-eval] {key}: {json.dumps(models_out[key])}', flush=True)
            del pol
            torch.cuda.empty_cache()

        know = knowledge('ex218', RUN / 'checkpoints/selected', RUN)
        tera = {k: round(know[k]['all']['accuracy'], 4) for k in ('heldout-A', 'heldout-B') if k in know}
        print('[ex218-eval] Tera knowledge:', tera, flush=True)
        summary = dict(experiment='EX-218', decision='D-222', at=time.time(), models=models_out, tera_knowledge=tera)
        atomic(RUN / 'evaluation/summary.json', summary)
        atomic(RUN / 'status.json', dict(stage='completed', at=time.time()))
    return summary


if __name__ == '__main__':
    if sys.argv[1:2] == ['--worker']:
        from integration.laya_v11 import train_v11 as T
        T.RUNS['EX-218'] = RUN
        T._worker_main(sys.argv[2:])
    elif sys.argv[1] == 'wait-gpu0':
        wait_gpu0()
    elif sys.argv[1] == 'eval':
        evaluate_heldout()
    else:
        sys.exit(launch(sys.argv[1]))
