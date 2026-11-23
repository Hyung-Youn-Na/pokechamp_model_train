"""EX-183 evaluation (D-215, report only, D-191): teacher validation and both locked tests, EX-183 vs EX-172.

    python -m integration.laya_distill.evaluation_distill      (laya env; GPU 0)

- teacher validation (EX-182, 80 held-out train games): cross-entropy to the teacher distribution, argmax = teacher
  best, argmax = human label, switch / tera share of the argmax vs the teacher's, for EX-172 and EX-183;
- locked tests (v11-all / v11-ladder, the same 1,024 + 1,024 rows EX-172 was scored on): `laya_imitation.evaluate`
  for EX-183 once; paired with EX-172's stored rows (NLL, match), replay-cluster bootstrap 95% (10,000, SEED).
"""
from __future__ import annotations

import json
import math
import os
import random
import time

from integration.laya_distill import paths as P
from integration.laya_imitation.resources import gpu
from integration.laya_imitation.storage import atomic, jsonl, read, seal
from integration.laya_ladder import paths as LP
from integration.laya_ladder.train_ddp import UUIDS

SEED = 20261183
TESTS = dict(tour=('selected', LP.GENERATED / 'laya-compact-imitation/v11-all'),
             ladder=('selected-ladder', LP.GENERATED / 'laya-compact-imitation/v11-ladder'))


def _kind(aid):
    return 'switch' if aid.startswith('switch') else ('tera' if aid.endswith(':tera') else 'move')


def teacher_metrics(policy, rows):
    items = [policy.item(r['state'], r['questions']['action']) for r in rows]
    logits = policy.logits(items)
    out = dict(rows=len(rows), ce=0.0, teacher_best=0, human=0, argmax_kind={}, teacher_kind={})
    per = []
    for r, z in zip(rows, logits):
        ids = list(r['questions']['action']['criteria'])
        probs, _ = policy.distribution(z, len(ids))
        gold = r['gold']['action']['probabilities']
        ce = -sum(gold.get(k, 0.0) * math.log(max(p, 1e-12)) for k, p in zip(ids, probs))
        top = ids[max(range(len(ids)), key=lambda i: probs[i])]
        best = max(gold, key=lambda k: (gold[k], k))
        out['ce'] += ce
        out['teacher_best'] += top == best
        out['human'] += top == r['meta']['human_label']
        out['argmax_kind'][_kind(top)] = out['argmax_kind'].get(_kind(top), 0) + 1
        for k, v in gold.items():
            out['teacher_kind'][_kind(k)] = out['teacher_kind'].get(_kind(k), 0) + v
        per.append(dict(sample_id=r['sample_id'], ce=ce, teacher_best=top == best))
    n = max(1, len(rows))
    out.update(ce=out['ce'] / n, teacher_best=out['teacher_best'] / n, human=out['human'] / n,
               argmax_kind={k: v / n for k, v in out['argmax_kind'].items()},
               teacher_kind={k: v / n for k, v in out['teacher_kind'].items()})
    return out, per


def paired(new, base, key, seed=SEED, reps=10000):
    b = {r['sample_id']: r for r in base}
    pairs = [(r['sample_id'].split(':')[0], float(r[key]) - float(b[r['sample_id']][key])) for r in new
             if r['sample_id'] in b]
    by = {}
    for g, d in pairs:
        by.setdefault(g, []).append(d)
    groups = list(by.values())
    mean = sum(d for _, d in pairs) / len(pairs)
    rng = random.Random(seed)
    boots = []
    for _ in range(reps):
        pick = [groups[rng.randrange(len(groups))] for _ in groups]
        flat = [d for g in pick for d in g]
        boots.append(sum(flat) / len(flat))
    boots.sort()
    return dict(n=len(pairs), replays=len(groups), diff=mean, ci95=[boots[int(0.025 * reps)], boots[int(0.975 * reps)]])


def run():
    from integration.laya_imitation.evaluation import evaluate
    from integration.laya_imitation.policy import Policy
    from integration.laya_v10 import training_v10
    out = P.TRAIN_RUN
    if read(out / 'status.json')['stage'] != 'trained':
        raise RuntimeError('EX-183 is not trained: %r' % read(out / 'status.json'))
    training_v10.install(LP.OPTION_LIMIT)
    (out / 'evaluation').mkdir(exist_ok=True)
    rows = list(jsonl(P.DATA / 'teacher-validation.jsonl'))
    teacher = {}
    with gpu(0, UUIDS[0]) as (env, _):
        os.environ.update(env)
        for name, ckpt in (('ex172', P.EX172 / 'checkpoints/selected'), ('ex183', out / 'checkpoints/selected')):
            m, per = teacher_metrics(Policy(ckpt, head_limit=LP.HEAD_LIMIT), rows)
            teacher[name] = m
            with open(out / ('evaluation/teacher-%s.jsonl' % name), 'w') as f:
                for r in per:
                    f.write(json.dumps(r) + '\n')
        tests = {}
        for key, (name, dataset) in TESTS.items():
            if (out / ('evaluation/completed-%s.json' % name)).exists():
                tests[key] = read(out / ('evaluation/completed-%s.json' % name))['metrics']
            else:
                tests[key] = evaluate(name, ckpt, out, dataset=dataset, head_limit=LP.HEAD_LIMIT)
    t172 = [json.loads(l) for l in open(out / 'evaluation/teacher-ex172.jsonl')]
    t183 = [json.loads(l) for l in open(out / 'evaluation/teacher-ex183.jsonl')]
    for r in t172 + t183:
        r['teacher_best'] = float(r['teacher_best'])
    vs = dict(teacher_ce=paired(t183, t172, 'ce'), teacher_best=paired(t183, t172, 'teacher_best'))
    for key, (name, _) in TESTS.items():
        new = [dict(r, correct=float(r['correct'])) for r in jsonl(out / ('evaluation/test-%s.jsonl' % name))]
        base = [dict(r, correct=float(r['correct'])) for r in jsonl(P.EX172 / ('evaluation/test-%s.jsonl' % name))]
        vs[key] = dict(nll=paired(new, base, 'nll'), match=paired(new, base, 'correct'))
    ex172 = read(P.EX172 / 'evaluation/report.json')
    report = dict(at=time.time(), seed=SEED, teacher=teacher, tests=tests, vs_ex172=vs,
                  ex172_tests={k: (ex172.get('tests') or {}).get(k) for k in TESTS})
    atomic(out / 'evaluation/report.json', report, immutable=True)
    lines = ['# EX-183 v11rtc + foul-play 탐색 증류 학습 보고', '', '사람 선택 재현과 교사 분포 근접도이며 승률이 아니다(D-191).', '',
             '## 교사 validation (%d행)' % len(rows), '', '| 모델 | CE | 교사 1순위 일치 | 사람 일치 | argmax 교체 | argmax 테라 | 교사 교체 몫 | 교사 테라 몫 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for name in ('ex172', 'ex183'):
        m = teacher[name]
        lines.append('| %s | %.4f | %.3f | %.3f | %.3f | %.3f | %.3f | %.3f |' % (
            name.upper(), m['ce'], m['teacher_best'], m['human'], m['argmax_kind'].get('switch', 0),
            m['argmax_kind'].get('tera', 0), m['teacher_kind'].get('switch', 0), m['teacher_kind'].get('tera', 0)))
    lines += ['', '## 같은 행 차이(EX-183 − EX-172, replay 클러스터 bootstrap 95%)', '', '| 항목 | 행 | 차이 | 95% |', '|---|---:|---:|---|']
    for label, d in (('교사 CE', vs['teacher_ce']), ('교사 1순위 일치', vs['teacher_best']),
                     ('대회 test NLL', vs['tour']['nll']), ('대회 test 일치', vs['tour']['match']),
                     ('래더 test NLL', vs['ladder']['nll']), ('래더 test 일치', vs['ladder']['match'])):
        lines.append('| %s | %d | %+.4f | [%+.4f, %+.4f] |' % (label, d['n'], d['diff'], d['ci95'][0], d['ci95'][1]))
    (out / 'evaluation/report.md').write_text('\n'.join(lines) + '\n')
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    print(json.dumps(dict(teacher={k: dict(ce=v['ce'], best=v['teacher_best']) for k, v in teacher.items()},
                          vs=vs), ensure_ascii=False))
    return report


if __name__ == '__main__':
    run()
