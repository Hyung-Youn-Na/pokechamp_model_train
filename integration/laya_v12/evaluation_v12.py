"""EX-192 evaluation (EP-237): both locked tests in their v12 rendering, paired with EX-167 (v10rt) and EX-172 (v11rtc).

    python -m integration.laya_v12.evaluation_v12 score  [--gpu 0]   # GPU: Tera knowledge + both tests, once each
    python -m integration.laya_v12.evaluation_v12 report             # CPU: evaluation/report.{json,md}

Report only (D-191). The v12 tests (`v12-all` / `v12-ladder` test) are the same 1,024 + 1,024 sample ids as the stored
EX-167 and EX-172 test rows; the baselines were scored on their own renderings (v10 / v11). Paired differences are
`laya_v11.evaluation_v11._paired` (replay-cluster bootstrap); "input changed" means the v12 row differs from the v11
row of the same sample id.
"""
from __future__ import annotations

import json
import os
import sys
import time

from integration.laya_imitation.storage import atomic, jsonl, read
from integration.laya_ladder import paths as ladder
from integration.laya_v11 import data_v11
from integration.laya_v11.evaluation_v11 import TESTS, _ci, _paired
from integration.laya_v11.train_v11 import RUNS as V11_RUNS

from . import data_v12
from .train_v12 import RUN

SEED = 20261192
BASES = {'EX-167': ladder.RUN_TRAINING / 'evaluation', 'EX-172': V11_RUNS['EX-172'] / 'evaluation'}
KNOWLEDGE = {'EX-167': 'knowledge-ex167.json', 'EX-172': 'knowledge-ex172.json'}


def score(gpu_index=0):
    from integration.laya_imitation.evaluation import evaluate
    from integration.laya_imitation.evaluation_tera import knowledge
    from integration.laya_imitation.resources import gpu
    from integration.laya_ladder.train_ddp import UUIDS
    from integration.laya_v10 import training_v10
    out = RUN
    if read(out / 'status.json')['stage'] != 'trained':
        raise RuntimeError('EX-192 is not trained: %r' % read(out / 'status.json'))
    checkpoint = out / 'checkpoints/selected'
    (out / 'evaluation').mkdir(exist_ok=True)
    training_v10.install(ladder.OPTION_LIMIT)
    with gpu(gpu_index, UUIDS[gpu_index]) as (env, _):
        os.environ.update(env)
        knowledge('ex192', checkpoint, out)
        for name, source, _ in TESTS.values():
            if (out / ('evaluation/completed-%s.json' % name)).exists():
                continue
            if (out / ('evaluation/reservation-%s.json' % name)).exists():
                raise RuntimeError('test %s was started but not completed; it is not re-run' % name)
            evaluate(name, checkpoint, out, dataset=data_v12.SOURCES[source]['rows'], head_limit=ladder.HEAD_LIMIT)
    atomic(out / 'status.json', dict(stage='scored', at=time.time()))


def _changed(source):
    out = set()
    with open(data_v12.SOURCES[source]['rows'] / 'test.jsonl') as a, \
            open(data_v11.SOURCES[source]['rows'] / 'test.jsonl') as b:
        for x, y in zip(a, b, strict=True):
            x, y = json.loads(x), json.loads(y)
            if x['sample_id'] != y['sample_id']:
                raise ValueError('test order differs: %s / %s' % (x['sample_id'], y['sample_id']))
            if x['state'] != y['state'] or x['questions'] != y['questions']:
                out.add(x['sample_id'])
    return out


def report():
    out = RUN
    tests = {}
    for label, (name, source, base_file) in TESTS.items():
        changed = _changed(source)
        rows = list(jsonl(out / ('evaluation/test-%s.jsonl' % name)))
        tests[label] = dict(metrics=read(out / ('evaluation/completed-%s.json' % name))['metrics']['all'],
                            changed_rows=len(changed),
                            vs={b: _paired(rows, list(jsonl(base / base_file)), changed, SEED)
                                for b, base in BASES.items()})
    result = dict(experiment='EX-192', at=time.time(), seed=SEED, selection=read(out / 'selection.json'),
                  split=read(out / 'split.json'),
                  curve=[json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()],
                  tests=tests, knowledge=dict({b: read(base / KNOWLEDGE[b]) for b, base in BASES.items()},
                                              new=read(out / 'evaluation/knowledge-ex192.json')))
    atomic(out / 'evaluation/report.json', result)
    write(out, result)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    return result


def write(out, r):
    lines = ['# EX-192 laya v12(foul-play 추론 입력) 처음부터 학습 보고', '',
             'EX-167과 같은 시작 모델·설정(3 epoch, 테라 지식 행 포함)에서 입력만 렌더러 v12로 바꿨다(EP-237). 사람 선택 '
             '재현 보고이며 승률이 아니다. 이 보고는 배틀 진행 여부를 정하지 않는다(D-191).', '',
             '## validation', '', '| epoch | train loss | NLL(원 logit) | 일치율 | ECE |', '|---:|---:|---:|---:|---:|']
    for p in r['curve']:
        lines.append('| %d | %s | %.4f | %.2f%% | %.4f |' % (
            p['epoch'], '%.4f' % p['train_loss'] if 'train_loss' in p else '-', p['raw']['loss'],
            100 * p['raw']['accuracy'], p['raw']['ece']))
    lines += ['', '선택 epoch %d, 온도 %s.' % (r['selection']['selected_epoch'], r['selection']['temperature']), '',
              '## 잠긴 test (같은 행 차이, EX-192 − 기준, replay 클러스터 95%%, 시드 %d)' % r['seed'], '',
              '| test | 기준 | 구분 | n | 기준 NLL | EX-192 NLL | NLL 차이 | 일치율 기준 → EX-192 |',
              '|---|---|---|---:|---:|---:|---|---|']
    for label, title in (('tour', 'EX-071(대회)'), ('ladder', 'EX-166(래더)')):
        for base, groups in r['tests'][label]['vs'].items():
            for group, b in sorted(groups.items(), key=lambda kv: (kv[0] != 'all', kv[0])):
                lines.append('| %s | %s | %s | %d | %.4f | %.4f | %s | %.2f%% → %.2f%% |' % (
                    title, base, group, b['n'], b['base_nll'], b['new_nll'], _ci(b['nll_diff']),
                    100 * b['base_match'], 100 * b['new_match']))
    lines += ['', 'EX-167은 v10 입력, EX-172는 v11 입력, EX-192는 v12 입력에서 잰 값이다. "input changed"는 v11 행과 '
              '입력이 다른 행이다(대회 %d행, 래더 %d행).' % (r['tests']['tour']['changed_rows'],
                                                 r['tests']['ladder']['changed_rows']), '',
              '## 테라 지식 held-out 정답률', '', '| 유형 | n | EX-167 | EX-172 | EX-192 |', '|---|---:|---:|---:|---:|']
    k = r['knowledge']
    for part in ('heldout-A', 'heldout-B'):
        for kind, b in k['new'][part].items():
            lines.append('| %s %s | %d | %.1f%% | %.1f%% | %.1f%% |' % (
                part, kind, b['n'], 100 * k['EX-167'][part][kind]['accuracy'],
                100 * k['EX-172'][part][kind]['accuracy'], 100 * b['accuracy']))
    lines += ['', '## 해석 한계', '', '- 단일 시드다. validation은 epoch 2 뒤 다시 올라 epoch 2를 골랐다.',
              '- 입력 판본이 기준마다 달라 차이는 입력과 학습을 함께 반영한다.', '']
    (out / 'evaluation/report.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    if sys.argv[1] == 'score':
        score(int(sys.argv[sys.argv.index('--gpu') + 1]) if '--gpu' in sys.argv else 0)
    else:
        report()
