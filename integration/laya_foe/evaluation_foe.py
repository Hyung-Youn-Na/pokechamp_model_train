"""EX-196 evaluation (EP-238): opponent prediction on the held-out games, fresh-game imitation, locked tests, Tera.

    python -m integration.laya_foe.evaluation_foe sample        (CPU: fixed evaluation samples, once)
    python -m integration.laya_foe.evaluation_foe score [--gpu 0]
    python -m integration.laya_foe.evaluation_foe report

Report only (D-191). EX-192 (before) and EX-196 (after) are scored on the same rows:
- `foe`: SAMPLE rows of EX-195 `foe-heldout.jsonl` (400 ladder games no model trained on), seeded;
- `fresh`: SAMPLE rows of EX-195 `imitation-heldout.jsonl` (the same games, the human's own choice);
- EX-196 alone on the v12 locked tests and the Tera knowledge held-out; paired with EX-192's stored rows.
Paired differences: `laya_v11.evaluation_v11._paired` (game-cluster bootstrap).
"""
from __future__ import annotations

from collections import Counter
import json
import os
import random
import sys
import time

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic, jsonl, read
from integration.laya_ladder import paths as ladder
from integration.laya_v11.evaluation_v11 import TESTS, _ci, _paired
from integration.laya_v12 import data_v12

from .train_foe import RUN

SEED = 20261196
SAMPLE = 6000
FOE = c.SHARED / 'datasets/generated/laya-foe/v1'
SETS = {'foe': FOE / 'foe-heldout.jsonl', 'fresh': FOE / 'imitation-heldout.jsonl'}
MODELS = {'ex192': c.SHARED / 'runs/model-training/EX-192/checkpoints/selected', 'ex196': RUN / 'checkpoints/selected'}
EX192 = c.SHARED / 'runs/model-training/EX-192/evaluation'


def sample():
    for name, path in SETS.items():
        d = FOE / ('eval-' + name)
        if (d / 'test.jsonl').exists():
            continue
        d.mkdir(parents=True, exist_ok=True)
        lines = open(path).readlines()
        keep = sorted(random.Random(SEED).sample(range(len(lines)), min(SAMPLE, len(lines))))
        with open(d / 'test.jsonl', 'w') as f:
            f.writelines(lines[i] for i in keep)
        (d / 'manifest.json').write_text(json.dumps(dict(source=str(path), rows=len(keep), of=len(lines), seed=SEED)))


def score(gpu_index=0):
    from integration.laya_imitation.evaluation import evaluate
    from integration.laya_imitation.evaluation_tera import knowledge
    from integration.laya_imitation.resources import gpu
    from integration.laya_ladder.train_ddp import UUIDS
    from integration.laya_v10 import training_v10
    if read(RUN / 'status.json')['stage'] != 'trained':
        raise RuntimeError('EX-196 is not trained: %r' % read(RUN / 'status.json'))
    out = RUN
    (out / 'evaluation').mkdir(exist_ok=True)
    training_v10.install(ladder.OPTION_LIMIT)

    def once(name, checkpoint, dataset):
        if (out / ('evaluation/completed-%s.json' % name)).exists():
            return
        if (out / ('evaluation/reservation-%s.json' % name)).exists():
            raise RuntimeError('test %s was started but not completed; it is not re-run' % name)
        evaluate(name, checkpoint, out, dataset=dataset, head_limit=ladder.HEAD_LIMIT)

    with gpu(gpu_index, UUIDS[gpu_index]) as (env, _):
        os.environ.update(env)
        for key, checkpoint in MODELS.items():
            for name in SETS:
                once('%s-%s' % (name, key), checkpoint, FOE / ('eval-' + name))
        for name, source, _ in TESTS.values():
            once(name, MODELS['ex196'], data_v12.SOURCES[source]['rows'])
        knowledge('ex196', MODELS['ex196'], out)
    atomic(out / 'status.json', dict(stage='scored', at=time.time()))


def _rows(name):
    return list(jsonl(RUN / ('evaluation/test-%s.jsonl' % name)))


def _top(rows, n=3):
    hit = 0
    for r in rows:
        ranked = sorted(r['probabilities'], key=r['probabilities'].get, reverse=True)
        hit += r['label'] in ranked[:n]
    return hit / len(rows)


def report():
    out = RUN
    res = {}
    for name in SETS:
        a, b = _rows(name + '-ex192'), _rows(name + '-ex196')
        res[name] = dict(n=len(b), ex192=read(out / ('evaluation/completed-%s-ex192.json' % name))['metrics'],
                         ex196=read(out / ('evaluation/completed-%s-ex196.json' % name))['metrics'],
                         top3=dict(ex192=_top(a), ex196=_top(b)),
                         vs=_paired(b, a, set(), SEED))
        if name == 'foe':
            res[name]['labels'] = dict(Counter(r['label_kind'] for r in b))
            res[name]['mean_options'] = sum(r['k'] for r in b) / len(b)
            res[name]['by_label_kind'] = {
                k: dict(n=sum(1 for r in b if r['label_kind'] == k),
                        ex192=sum(r['correct'] for r in a if r['label_kind'] == k) / max(1, sum(1 for r in a if r['label_kind'] == k)),
                        ex196=sum(r['correct'] for r in b if r['label_kind'] == k) / max(1, sum(1 for r in b if r['label_kind'] == k)))
                for k in sorted({r['label_kind'] for r in b})}
    tests = {}
    for label, (name, _, base_file) in TESTS.items():
        tests[label] = dict(metrics=read(out / ('evaluation/completed-%s.json' % name))['metrics']['all'],
                            vs_ex192=_paired(_rows(name), list(jsonl(EX192 / base_file)), set(), SEED))
    result = dict(experiment='EX-196', at=time.time(), seed=SEED, selection=read(out / 'selection.json'),
                  split=read(out / 'split.json'),
                  curve=[json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()],
                  heldout=res, tests=tests,
                  knowledge=dict(ex192=read(EX192 / 'knowledge-ex192.json'),
                                 ex196=read(out / 'evaluation/knowledge-ex196.json')))
    atomic(out / 'evaluation/report.json', result)
    write(out, result)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    return result


def write(out, r):
    pct = lambda v: '%.2f%%' % (100 * v)
    lines = ['# EX-196 laya v12 + 상대 행동 예측 이어 학습 보고', '',
             'EX-192 selected에서 1 epoch 이어 학습했다(새 모방 행 + 상대 예측 행 + 테라 지식). 보고 전용(D-191).', '',
             '## 학습', '', '| 지점 | train loss | validation NLL | 일치율 |', '|---:|---:|---:|---:|']
    for p in r['curve']:
        lines.append('| %s | %s | %.4f | %s |' % (p['point'], '%.4f' % p['train_loss'] if 'train_loss' in p else '-',
                                                  p['raw']['loss'], pct(p['raw']['accuracy'])))
    lines += ['', '선택 지점 %s, 온도 %s. split %s' % (r['selection']['selected_point'], r['selection']['temperature'],
                                                  json.dumps(r['split'])), '']
    for name, title in (('foe', '상대 행동 예측(held-out 400경기)'), ('fresh', '사람 모방(같은 held-out 경기)')):
        h = r['heldout'][name]
        a, b = h['ex192']['all'], h['ex196']['all']
        d = h['vs']['all']
        lines += ['## ' + title, '',
                  '| 모델 | n | NLL | 1순위 일치 | 상위 3 |', '|---|---:|---:|---:|---:|',
                  '| EX-192 | %d | %.4f | %s | %s |' % (h['n'], a['nll'], pct(a['action_match_rate']), pct(h['top3']['ex192'])),
                  '| EX-196 | %d | %.4f | %s | %s |' % (h['n'], b['nll'], pct(b['action_match_rate']), pct(h['top3']['ex196'])),
                  '', 'NLL 차이 %s, 일치율 차이 %s(경기 클러스터 95%%).' % (_ci(d['nll_diff']), _ci(d['match_diff'])), '']
        if name == 'foe':
            lines += ['라벨 분포 %s, 평균 선택지 %.1f개.' % (json.dumps(h['labels']), h['mean_options']), '',
                      '| 라벨 종류 | n | EX-192 일치 | EX-196 일치 |', '|---|---:|---:|---:|']
            for k, v in h['by_label_kind'].items():
                lines.append('| %s | %d | %s | %s |' % (k, v['n'], pct(v['ex192']), pct(v['ex196'])))
            lines.append('')
    lines += ['## 잠긴 test(v12, EX-192 대비 같은 행)', '', '| test | n | EX-192 NLL | EX-196 NLL | 차이 | 일치율 |',
              '|---|---:|---:|---:|---|---|']
    for label, title in (('tour', 'EX-071(대회)'), ('ladder', 'EX-166(래더)')):
        d = r['tests'][label]['vs_ex192']['all']
        lines.append('| %s | %d | %.4f | %.4f | %s | %s → %s |' % (title, d['n'], d['base_nll'], d['new_nll'],
                                                                 _ci(d['nll_diff']), pct(d['base_match']), pct(d['new_match'])))
    lines += ['', '## 테라 지식 held-out', '', '| 묶음 | EX-192 | EX-196 |', '|---|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        lines.append('| %s | %s | %s |' % (part, pct(r['knowledge']['ex192'][part]['all']['accuracy']),
                                           pct(r['knowledge']['ex196'][part]['all']['accuracy'])))
    (out / 'evaluation/report.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'sample':
        sample()
    elif cmd == 'score':
        score(int(sys.argv[sys.argv.index('--gpu') + 1]) if '--gpu' in sys.argv else 0)
    else:
        report()
