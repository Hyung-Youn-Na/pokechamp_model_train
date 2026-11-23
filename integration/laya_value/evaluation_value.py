"""EX-200 evaluation (EP-239): engine-target agreement, held-out imitation and opponent prediction, locked tests, Tera.

    python -m integration.laya_value.evaluation_value sample        (any python 3: the target sample, once)
    python -m integration.laya_value.evaluation_value score [--gpu 0]
    python -m integration.laya_value.evaluation_value report

Report only (D-191). EX-200 against EX-196 on the same rows:
- `target`: SAMPLE gold rows of EX-199 `heldout.jsonl` (games kept out of EX-200), with the gold argmax as the
  expected answer; the report also scores the same probabilities against the human label and laya's (EX-196) argmax;
- `foe` / `fresh`: the EX-196 evaluation samples (EX-195 held-out 400 games), EX-196 rows reused;
- the v12 locked tests and the Tera knowledge held-out, EX-196 rows reused.
Paired differences: `laya_v11.evaluation_v11._paired` (game-cluster bootstrap).
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic, jsonl, read
from integration.laya_ladder import paths as ladder
from integration.laya_v11.evaluation_v11 import TESTS, _ci, _paired

from .train_value import RUN, VALUE

SEED = 20261200
SAMPLE = 6000
EX196 = c.SHARED / 'runs/model-training/EX-196'
FOE = c.SHARED / 'datasets/generated/laya-foe/v1'
TARGET = VALUE / 'eval-target'
MODELS = {'ex196': EX196 / 'checkpoints/selected', 'ex200': RUN / 'checkpoints/selected'}


def sample():
    if (TARGET / 'test.jsonl').exists():
        return
    TARGET.mkdir(parents=True, exist_ok=True)
    lines = open(VALUE / 'heldout.jsonl').readlines()
    keep = sorted(random.Random(SEED).sample(range(len(lines)), min(SAMPLE, len(lines))))
    with open(TARGET / 'test.jsonl', 'w') as f:
        for i in keep:
            r = json.loads(lines[i])
            g = r.pop('gold')['action']['probabilities']
            r['expected'] = dict(action=max(g, key=g.get))
            r['meta'] = dict(r['meta'], gold=g)
            f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
    (TARGET / 'manifest.json').write_text(json.dumps(dict(source=str(VALUE / 'heldout.jsonl'), rows=len(keep),
                                                          of=len(lines), seed=SEED)))


def score(gpu_index=0):
    from integration.laya_imitation.evaluation import evaluate
    from integration.laya_imitation.evaluation_tera import knowledge
    from integration.laya_imitation.resources import gpu
    from integration.laya_ladder.train_ddp import UUIDS
    from integration.laya_v10 import training_v10
    from integration.laya_v12 import data_v12
    if read(RUN / 'status.json')['stage'] != 'trained':
        raise RuntimeError('EX-200 is not trained: %r' % read(RUN / 'status.json'))
    (RUN / 'evaluation').mkdir(exist_ok=True)
    training_v10.install(ladder.OPTION_LIMIT)

    def once(name, checkpoint, dataset):
        if (RUN / ('evaluation/completed-%s.json' % name)).exists():
            return
        if (RUN / ('evaluation/reservation-%s.json' % name)).exists():
            raise RuntimeError('test %s was started but not completed; it is not re-run' % name)
        evaluate(name, checkpoint, RUN, dataset=dataset, head_limit=ladder.HEAD_LIMIT)

    with gpu(gpu_index, UUIDS[gpu_index]) as (env, _):
        os.environ.update(env)
        for key, checkpoint in MODELS.items():
            once('target-' + key, checkpoint, TARGET)
        for name in ('foe', 'fresh'):
            once('%s-ex200' % name, MODELS['ex200'], FOE / ('eval-' + name))
        for name, source, _ in TESTS.values():
            once(name, MODELS['ex200'], data_v12.SOURCES[source]['rows'])
        knowledge('ex200', MODELS['ex200'], RUN)
    atomic(RUN / 'status.json', dict(stage='scored', at=time.time()))


def _rows(path):
    return list(jsonl(path))


def _target_metrics(rows, meta):
    n = len(rows)
    out = dict(n=n)
    for key in ('gold_argmax', 'label', 'laya_argmax'):
        hit = 0
        for r in rows:
            want = r['label'] if key == 'gold_argmax' else meta[r['sample_id']][key]
            hit += max(r['probabilities'], key=r['probabilities'].get) == want
        out['match_' + key] = hit / n
    ce = 0.0
    import math
    for r in rows:
        g = meta[r['sample_id']]['gold']
        ce -= sum(v * math.log(max(1e-12, r['probabilities'].get(k, 0.0))) for k, v in g.items() if v > 0)
    out['gold_cross_entropy'] = ce / n
    return out


def report():
    meta = {}
    for r in jsonl(TARGET / 'test.jsonl'):
        e = r['meta']['ex199']
        meta[r['sample_id']] = dict(label=e['label'], laya_argmax=e['laya_argmax'], gold=r['meta']['gold'])
    ev = RUN / 'evaluation'
    a, b = _rows(ev / 'test-target-ex196.jsonl'), _rows(ev / 'test-target-ex200.jsonl')
    target = dict(ex196=_target_metrics(a, meta), ex200=_target_metrics(b, meta), vs=_paired(b, a, set(), SEED))
    heldout = {}
    for name in ('foe', 'fresh'):
        x, y = _rows(EX196 / ('evaluation/test-%s-ex196.jsonl' % name)), _rows(ev / ('test-%s-ex200.jsonl' % name))
        heldout[name] = dict(ex196=read(EX196 / ('evaluation/completed-%s-ex196.json' % name))['metrics']['all'],
                             ex200=read(ev / ('completed-%s-ex200.json' % name))['metrics']['all'],
                             vs=_paired(y, x, set(), SEED))
    tests = {}
    for label, (name, _, _) in TESTS.items():
        tests[label] = dict(metrics=read(ev / ('completed-%s.json' % name))['metrics']['all'],
                            vs_ex196=_paired(_rows(ev / ('test-%s.jsonl' % name)),
                                             _rows(EX196 / ('evaluation/test-%s.jsonl' % name)), set(), SEED))
    result = dict(experiment='EX-200', at=time.time(), seed=SEED, selection=read(RUN / 'selection.json'),
                  split=read(RUN / 'split.json'),
                  curve=[json.loads(line) for line in (RUN / 'validation-curve.jsonl').read_text().splitlines()],
                  target=target, heldout=heldout, tests=tests,
                  knowledge=dict(ex196=read(EX196 / 'evaluation/knowledge-ex196.json'),
                                 ex200=read(ev / 'knowledge-ex200.json')))
    atomic(ev / 'report.json', result)
    write(result)
    atomic(RUN / 'status.json', dict(stage='completed', at=time.time()))
    return result


def write(r):
    pct = lambda v: '%.2f%%' % (100 * v)
    lines = ['# EX-200 laya 엔진 가치 target 이어 학습 보고', '',
             'EX-196 selected에서 1 epoch 이어 학습했다(EX-199 target 행 + 모방 anchor 행 + 상대 예측 행 + 테라 지식). '
             '보고 전용(D-191).', '',
             '## 학습', '', '| 지점 | train loss | validation NLL | 일치율 |', '|---:|---:|---:|---:|']
    for p in r['curve']:
        lines.append('| %s | %s | %.4f | %s |' % (p['point'], '%.4f' % p['train_loss'] if 'train_loss' in p else '-',
                                                  p['raw']['loss'], pct(p['raw']['accuracy'])))
    lines += ['', '선택 지점 %s, 온도 %s. split %s' % (r['selection']['selected_point'], r['selection']['temperature'],
                                                  json.dumps(r['split'])), '',
              '## 엔진 target held-out(EX-199 held-out 경기, 후보 2개 이상 결정)', '',
              '| 모델 | n | target 1순위 일치 | 사람 선택 일치 | EX-196 1순위 일치 | target 교차 엔트로피 |',
              '|---|---:|---:|---:|---:|---:|']
    for key in ('ex196', 'ex200'):
        t = r['target'][key]
        lines.append('| %s | %d | %s | %s | %s | %.4f |' % (key.upper().replace('EX', 'EX-'), t['n'],
                                                            pct(t['match_gold_argmax']), pct(t['match_label']),
                                                            pct(t['match_laya_argmax']), t['gold_cross_entropy']))
    d = r['target']['vs']['all']
    lines += ['', 'target 1순위 일치율 차이 %s(경기 클러스터 95%%).' % _ci(d['match_diff']), '']
    for name, title in (('foe', '상대 행동 예측(EX-195 held-out 400경기)'), ('fresh', '사람 모방(같은 held-out 경기)')):
        h = r['heldout'][name]
        a, b, d = h['ex196'], h['ex200'], h['vs']['all']
        lines += ['## ' + title, '', '| 모델 | NLL | 1순위 일치 |', '|---|---:|---:|',
                  '| EX-196 | %.4f | %s |' % (a['nll'], pct(a['action_match_rate'])),
                  '| EX-200 | %.4f | %s |' % (b['nll'], pct(b['action_match_rate'])),
                  '', 'NLL 차이 %s, 일치율 차이 %s(경기 클러스터 95%%).' % (_ci(d['nll_diff']), _ci(d['match_diff'])), '']
    lines += ['## 잠긴 test(v12, EX-196 대비 같은 행)', '', '| test | n | EX-196 NLL | EX-200 NLL | 차이 | 일치율 |',
              '|---|---:|---:|---:|---|---|']
    for label, title in (('tour', 'EX-071(대회)'), ('ladder', 'EX-166(래더)')):
        d = r['tests'][label]['vs_ex196']['all']
        lines.append('| %s | %d | %.4f | %.4f | %s | %s → %s |' % (title, d['n'], d['base_nll'], d['new_nll'],
                                                                 _ci(d['nll_diff']), pct(d['base_match']), pct(d['new_match'])))
    lines += ['', '## 테라 지식 held-out', '', '| 묶음 | EX-196 | EX-200 |', '|---|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        lines.append('| %s | %s | %s |' % (part, pct(r['knowledge']['ex196'][part]['all']['accuracy']),
                                           pct(r['knowledge']['ex200'][part]['all']['accuracy'])))
    (RUN / 'evaluation/report.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'sample':
        sample()
    elif cmd == 'score':
        score(int(sys.argv[sys.argv.index('--gpu') + 1]) if '--gpu' in sys.argv else 0)
    else:
        report()
