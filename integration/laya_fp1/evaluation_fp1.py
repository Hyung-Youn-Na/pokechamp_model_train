"""EX-178 evaluation (D-213): both locked tests once on the fp1 rows, paired with EX-167 (v10 input) on the same rows.

    python -m integration.laya_fp1.evaluation_fp1      (laya env; GPU 0)

Report only (D-191). The fp1 tests (`fp1-test/{tour,ladder}`) are the same 1,024 + 1,024 sample ids as EX-167's
stored test rows (`EX-167/evaluation/test-selected{,-ladder}.jsonl`). Paired differences (replay-cluster bootstrap)
and the probability-mass checks are `laya_ladder.evaluation._side`'s, with the decision groups and the fails /
danger / repeat option sets read from the v10 test rows of the same sample ids (option ids are identical, EX-177).
No Tera knowledge evaluation: EX-178 has no knowledge rows (D-213 decision 4).
"""
from __future__ import annotations

import json
import os
import time

from integration.laya_imitation.evaluation_v2 import _interval
from integration.laya_imitation.resources import gpu
from integration.laya_imitation.storage import atomic, jsonl, read, seal
from integration.laya_ladder import evaluation as L, paths as LP
from integration.laya_ladder.train_ddp import UUIDS
from integration.laya_v10 import training_v10

from .train_fp1 import RUN

TESTS = LP.GENERATED / 'laya-compact-imitation/fp1-test'
EX167 = LP.RUN_TRAINING


def run():
    out = RUN
    checkpoint = out / 'checkpoints/selected'
    if read(out / 'status.json')['stage'] != 'trained':
        raise RuntimeError('EX-178 is not ready for evaluation: %r' % read(out / 'status.json'))
    if read(EX167 / 'status.json')['stage'] != 'completed':
        raise RuntimeError('EX-167 must be completed first')
    training_v10.install(LP.OPTION_LIMIT)
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(0, UUIDS[0]) as (env, _):
        os.environ.update(env)
        tests = dict(tour=L._once('selected', checkpoint, out, TESTS / 'tour'),
                     ladder=L._once('selected-ladder', checkpoint, out, TESTS / 'ladder'))
    tour = L._side(LP.V10_DATASET, list(jsonl(out / 'evaluation/test-selected.jsonl')),
                   list(jsonl(EX167 / 'evaluation/test-selected.jsonl')))
    ladder = L._side(LP.LADDER_ROWS, list(jsonl(out / 'evaluation/test-selected-ladder.jsonl')),
                     list(jsonl(EX167 / 'evaluation/test-selected-ladder.jsonl')))
    ex167 = read(EX167 / 'evaluation/report.json')
    report = dict(at=time.time(), seed=L.SEED, tests=tests,
                  ex167_tests=dict(tour=ex167['tests']['ex071'], ladder=ex167['tests']['ladder']),
                  tour=tour, ladder=ladder)
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    print(json.dumps(dict(tour=tour['vs_ex161']['all'], ladder=ladder['vs_ex161']['all']), ensure_ascii=False))
    return report


def write_report(out, report):
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel = read(out / 'selection.json')
    t, b = report['tests'], report['ex167_tests']
    lines = ['# EX-178 laya fp1(foul-play 기반 입력) 처음부터 학습 보고', '',
             'EX-167과 같은 시작 모델·설정에서 입력만 fp1(foul-play 추적·세트 표본·poke-engine 계산, 기록 문장 없음)으로 '
             '바꿨다(D-213). 사람 선택 재현이며 승률이 아니다. 이 보고는 배틀 진행 여부를 정하지 않는다(D-191).', '',
             '## validation', '', '| epoch | train loss | NLL | 일치율 | ECE |', '|---:|---:|---:|---:|---:|']
    for row in curve:
        r = row['raw']
        lines.append('| %d | %s | %.4f | %.4f | %.4f |' % (row['epoch'], '%.4f' % row['train_loss'] if 'train_loss' in row
                                                         else '-', r['loss'], r['accuracy'], r['ece']))
    lines += ['', '선택 epoch %d, 온도 %s.' % (sel['selected_epoch'], sel['temperature']), '',
              '## 잠긴 test', '', '| test | 모델 | NLL | 일치율 | ECE |', '|---|---|---:|---:|---:|']
    for test, key in (('EX-071(대회)', 'tour'), ('EX-166(래더)', 'ladder')):
        for name, m in (('EX-167 v10', b[key]['all']), ('EX-178 fp1', t[key]['all'])):
            lines.append('| %s | %s | %.4f | %.4f | %.4f |' % (test, name, m['nll'], m['action_match_rate'], m['ece']))
    lines += ['', '## 같은 행 차이(EX-178 − EX-167, replay 클러스터 bootstrap 95%)', '',
              '| test | 묶음 | 행 | NLL 차이 | 일치율 차이 |', '|---|---|---:|---:|---:|']
    for test, key in (('EX-071', 'tour'), ('EX-166', 'ladder')):
        v = report[key]['vs_ex161']
        groups = [('all', v['all'])] + [('%s=%s' % (g[3:], k), d) for g in ('by_decision_kind', 'by_label_kind')
                                        for k, d in sorted(v.get(g, {}).items())]
        for group, d in groups:
            lines.append('| %s | %s | %d | %+.4f %s | %+.4f %s |' % (
                test, group, d['n'], d['nll_diff'], _interval(d['nll_diff_95']), d['match_diff'],
                _interval(d['match_diff_95'])))
    lines += ['', '## 선택지 확률 합(같은 행, EX-178 − EX-167)', '',
              '| test | 묶음 | 행 | 사람 선택 | EX-178 | EX-167 | 차이 95% | argmax EX-178 | argmax EX-167 |',
              '|---|---|---:|---:|---:|---:|---|---:|---:|']
    for test, key in (('EX-071', 'tour'), ('EX-166', 'ladder')):
        for name in ('fails', 'danger', 'repeat'):
            d = report[key][name]
            if d['rows']:
                lines.append('| %s | %s | %d | %d | %.4f | %.4f | %s | %d | %d |' % (
                    test, name, d['rows'], d['human_picked'], d['ex161_mass'], d['ex149_mass'],
                    _interval(d['diff_95']), d['ex161_argmax'], d['ex149_argmax']))
    (out / 'evaluation/report.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    run()
