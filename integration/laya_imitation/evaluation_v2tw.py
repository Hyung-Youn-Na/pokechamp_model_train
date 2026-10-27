"""EX-132 evaluation on GPU0: Tera knowledge held-out (EX-132 once), locked test once, paired with EX-124 selected.

Report only (D-191): nothing here decides whether EX-133 runs. EX-124 test rows and knowledge results are read from
its sealed run. Reported: overall / switch-row NLL differences and the same split by the replay outcome of the row's
side (win / loss / tie) -- the weighting should move the winners' rows more than the losers' (a defect check, not a
verdict), plus failing-option mass and Tera metrics with the EX-130 rules.
"""
from __future__ import annotations
import json
import os
import time

from integration.pokechamp.imitation.schema import ImitationInput

from . import config as c
from .evaluation import evaluate
from .evaluation_effects import fail_metrics
from .evaluation_tera import knowledge, tera_metrics
from .evaluation_v2 import _interval
from .evaluation_v3 import SWITCH_LABELS, block, paired
from .features_v4 import known_failures
from .outcome_weights import sides
from .resources import gpu
from .storage import atomic, jsonl, read, seal, verify_seal

SEED = 20261029
CHECKPOINT = c.RUN_WEIGHTED_TRAINING / 'checkpoints/selected'


def compare(pairs):
    out = dict(all=block(pairs), switch=block([p for p in pairs if p['label_kind'] in SWITCH_LABELS]))
    for group in ('label_kind', 'decision_kind', 'side'):
        keys = sorted({p[group] for p in pairs})
        out['by_' + group] = {k: block([p for p in pairs if p[group] == k]) for k in keys}
    return out


def run():
    out = c.RUN_WEIGHTED_TRAINING
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-132 is not ready for evaluation: %r' % status)
    if read(c.RUN_TERA_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_TERA_TRAINING):
        raise RuntimeError('EX-124 must be completed and sealed first')
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(c.GPU_INDEX, c.GPU_UUID) as (env, _):
        os.environ.update(env)
        know = knowledge('ex132', CHECKPOINT, out)
        done = out / 'evaluation/completed-selected.json'
        if done.exists():
            test = read(done)['metrics']
        elif (out / 'evaluation/reservation-selected.json').exists():
            raise RuntimeError('locked test was started but not completed; it is not re-run')
        else:
            test = evaluate('selected', CHECKPOINT, out, dataset=c.V2_DATASET, head_limit=c.V2_HEAD_LIMIT)
    side_of = sides()
    info, failing = {}, {}
    for r in jsonl(c.EX071_PREPARED / 'test.jsonl'):
        info[r['sample_id']] = dict(replay_id=r['replay_id'], side=side_of.get(r['sample_id']) or 'unmatched')
        bad = known_failures(ImitationInput.from_body(r['input']))
        if bad:
            failing[r['sample_id']] = sorted(bad)
    replay_of = {k: v['replay_id'] for k, v in info.items()}
    new_rows = list(jsonl(out / 'evaluation/test-selected.jsonl'))
    old_rows = list(jsonl(c.RUN_TERA_TRAINING / 'evaluation/test-selected.jsonl'))
    report = dict(at=time.time(), test=test, ex124_test=read(c.RUN_TERA_TRAINING / 'evaluation/report.json')['test'],
                  knowledge=dict(ex124=read(c.RUN_TERA_TRAINING / 'evaluation/knowledge-ex124.json'), ex132=know),
                  comparison=compare(paired(new_rows, old_rows, info)),
                  failing=fail_metrics(new_rows, old_rows, failing, replay_of),
                  tera=tera_metrics(new_rows, old_rows, replay_of))
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    cmp_ = report['comparison']
    print(json.dumps(dict(all=cmp_['all'], by_side=cmp_['by_side'], failing=report['failing']['fail_mass']),
                     ensure_ascii=False))
    return report


def _row(name, b):
    return '| %s | %d | %+.4f | %s | %+.2f%%p |' % (name, b['n'], b['nll_diff'], _interval(b['nll_diff_95']),
                                                  100 * b['match_diff'])


def write_report(out, report):
    cmp_, f, t, k = report['comparison'], report['failing'], report['tera'], report['knowledge']
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    w = read(c.OUTCOME_WEIGHTS / 'manifest.json')
    lines = ['# EX-132 laya v2+테라 승패 가중 모방 학습 보고', '',
             'EX-124(v2+테라)와 같은 시작 모델, 설정, 자료, 분할에서 모방 학습 행에만 리플레이 승패 가중치를 줬다'
             '(이긴 쪽 %.2f, 진 쪽 %.2f, 무승부 %.2f, 평균 1로 정규화, GPU0). '
             '사람 선택 재현이며 승률이 아니다. 이 보고는 EX-133 배틀 진행 여부를 정하지 않는다(D-191).' % (
                 w['raw']['win'], w['raw']['loss'], w['raw']['tie']), '',
             '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|']
    for name, m in (('EX-124 v2+테라', report['ex124_test']['all']), ('EX-132 v2+테라+승패 가중', report['test']['all'])):
        lines.append('| %s | %.4f | %.2f%% | %.4f |' % (name, m['nll'], 100 * m['action_match_rate'], m['ece']))
    lines += ['', '## 같은 행 차이 (EX-132 − EX-124, replay 클러스터 95%)', '',
              '| 구분 | n | NLL 차이 | 95% | 일치율 차이 |', '|---|---:|---:|---|---:|',
              _row('전체', cmp_['all']), _row('교체 행', cmp_['switch'])]
    for group, title in (('by_side', '그 시점의 승패'), ('by_label_kind', '라벨'), ('by_decision_kind', '결정')):
        for key, b in cmp_[group].items():
            lines.append(_row('%s %s' % (title, key), b))
    m = f['fail_mass']
    lines += ['', '가중이 의도대로 작동하면 이긴 쪽 행의 NLL이 진 쪽 행보다 더 낮아진다(결함 점검, 판정 아님).', '',
              '## 실패로 정해진 선택지 (보고 지표)', '',
              '- 해당 test 행 %d(사람이 그 선택지를 고른 행 %d)' % (f['rows_with_failing'], f['human_chose_failing']),
              '- 그 선택지들의 확률 합 평균: EX-124 %.4f → EX-132 %.4f, 차이 %+.4f, 95%% %s' % (
                  m['old'], m['new'], m['diff'], _interval(m['diff_95'])),
              '- 그 선택지가 1위인 행: EX-124 %d → EX-132 %d' % (f['fail_top']['old'], f['fail_top']['new']), '',
              '## 테라 (보고 지표)', '',
              '- 사람이 테라를 고른 test %d행의 테라 확률 합: EX-124 %.4f → EX-132 %.4f' % (
                  t['human_tera'], t['tera_mass_human']['old'], t['tera_mass_human']['new']), '',
              '## 테라 지식 held-out 정답률', '', '| 유형 | n | EX-124 | EX-132 |', '|---|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind in k['ex132'][part]:
            a, b = k['ex124'][part][kind], k['ex132'][part][kind]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% |' % (part, kind, b['n'], 100 * a['accuracy'],
                                                             100 * b['accuracy']))
    ow = split['outcome_weights']
    lines += ['', '## 자료와 학습', '',
              '- 가중치: 학습 행 승 %d · 패 %d · 무 %d, 정규화 배율 %.4f, 학습 분할 평균 %.4f' % (
                  w['counts']['win'], w['counts']['loss'], w['counts']['tie'], w['counts']['scale'], ow['mean']),
              '- 학습 행 %d(모방 %d + 테라 지식 %d), 보정 %d(모방만, 가중 없음), validation %d(가중 없음)' % (
                  split['train'], split['train'] - split['extra_train'], split['extra_train'], split['calibration'],
                  split['validation']), '',
              '| epoch | train loss(가중) | validation NLL(원 logit) | 일치율 |', '|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% |' % (r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-',
                                                    r['raw']['loss'], 100 * r['raw']['accuracy']))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '',
              '## 해석 한계', '',
              '- 승패는 경기 전체의 결과다. 진 쪽의 좋은 수와 이긴 쪽의 실수를 구분하지 않는다.',
              '- 사람 선택 재현 지표는 사람 전체(승·패) 기준이라, 가중의 목적과 어긋날 수 있다.',
              '- 단일 시드 학습이다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
