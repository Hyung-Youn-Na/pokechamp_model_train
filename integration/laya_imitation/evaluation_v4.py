"""EX-130 evaluation on GPU1: Tera knowledge held-out (EX-130 once), locked test once, paired with EX-124 selected.

Report only (D-191): nothing here decides whether EX-131 runs. EX-124 test rows and knowledge results are read from
its sealed run. Reported: overall / switch-row NLL differences, rows with a v4 `fails` marker, and the probability
mass on options the visible state decides as failing (`evaluation_effects.fail_metrics`, same rule source).
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
from .resources import gpu
from .storage import atomic, jsonl, read, seal, verify_seal

SEED = 20261028
CHECKPOINT = c.RUN_V4_TRAINING / 'checkpoints/selected'


def compare(pairs):
    out = dict(all=block(pairs), switch=block([p for p in pairs if p['label_kind'] in SWITCH_LABELS]))
    for group in ('label_kind', 'decision_kind', 'marked'):
        keys = sorted({p[group] for p in pairs})
        out['by_' + group] = {k: block([p for p in pairs if p[group] == k]) for k in keys}
    return out


def run():
    out = c.RUN_V4_TRAINING
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-130 is not ready for evaluation: %r' % status)
    if read(c.RUN_TERA_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_TERA_TRAINING):
        raise RuntimeError('EX-124 must be completed and sealed first')
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(c.GPU1_INDEX, c.GPU1_UUID) as (env, _):
        os.environ.update(env)
        know = knowledge('ex130', CHECKPOINT, out)
        done = out / 'evaluation/completed-selected.json'
        if done.exists():
            test = read(done)['metrics']
        elif (out / 'evaluation/reservation-selected.json').exists():
            raise RuntimeError('locked test was started but not completed; it is not re-run')
        else:
            test = evaluate('selected', CHECKPOINT, out, dataset=c.V4_DATASET, head_limit=c.V2_HEAD_LIMIT)
    info, failing = {}, {}
    for r in jsonl(c.EX071_PREPARED / 'test.jsonl'):
        bad = known_failures(ImitationInput.from_body(r['input']))
        info[r['sample_id']] = dict(replay_id=r['replay_id'], marked='marked' if bad else 'plain')
        if bad:
            failing[r['sample_id']] = sorted(bad)
    replay_of = {k: v['replay_id'] for k, v in info.items()}
    new_rows = list(jsonl(out / 'evaluation/test-selected.jsonl'))
    old_rows = list(jsonl(c.RUN_TERA_TRAINING / 'evaluation/test-selected.jsonl'))
    report = dict(at=time.time(), test=test, ex124_test=read(c.RUN_TERA_TRAINING / 'evaluation/report.json')['test'],
                  knowledge=dict(ex124=read(c.RUN_TERA_TRAINING / 'evaluation/knowledge-ex124.json'), ex130=know),
                  comparison=compare(paired(new_rows, old_rows, info)),
                  failing=fail_metrics(new_rows, old_rows, failing, replay_of),
                  tera=tera_metrics(new_rows, old_rows, replay_of))
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    cmp_ = report['comparison']
    print(json.dumps(dict(switch=cmp_['switch'], all=cmp_['all'], failing=report['failing']['fail_mass']),
                     ensure_ascii=False))
    return report


def _row(name, b):
    return '| %s | %d | %+.4f | %s | %+.2f%%p |' % (name, b['n'], b['nll_diff'], _interval(b['nll_diff_95']),
                                                  100 * b['match_diff'])


def write_report(out, report):
    cmp_, f, t, k = report['comparison'], report['failing'], report['tera'], report['knowledge']
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    data = read(c.V4_DATASET / 'validation.json')
    lines = ['# EX-130 laya v4 렌더러(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습 보고', '',
             'EX-124(v2+테라)와 같은 시작 모델, 설정, 테라 지식 행에서 행동 행의 렌더러만 v4로 바꿨다(GPU1). '
             '사람 선택 재현이며 승률이 아니다. 이 보고는 EX-131 배틀 진행 여부를 정하지 않는다(D-191).', '',
             '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|']
    for name, m in (('EX-124 v2+테라', report['ex124_test']['all']), ('EX-130 v4+테라', report['test']['all'])):
        lines.append('| %s | %.4f | %.2f%% | %.4f |' % (name, m['nll'], 100 * m['action_match_rate'], m['ece']))
    lines += ['', '## 같은 행 차이 (EX-130 − EX-124, replay 클러스터 95%)', '',
              '| 구분 | n | NLL 차이 | 95% | 일치율 차이 |', '|---|---:|---:|---|---:|',
              _row('전체', cmp_['all']), _row('교체 행', cmp_['switch'])]
    for group, title in (('by_label_kind', '라벨'), ('by_marked', '실패 표시'), ('by_decision_kind', '결정')):
        for key, b in cmp_[group].items():
            lines.append(_row('%s %s' % (title, key), b))
    m = f['fail_mass']
    lines += ['', '## 실패로 정해진 선택지 (보고 지표)', '',
              '- 해당 test 행 %d(사람이 그 선택지를 고른 행 %d)' % (f['rows_with_failing'], f['human_chose_failing']),
              '- 그 선택지들의 확률 합 평균: EX-124 %.4f → EX-130 %.4f, 차이 %+.4f, 95%% %s' % (
                  m['old'], m['new'], m['diff'], _interval(m['diff_95'])),
              '- 그 선택지가 1위인 행: EX-124 %d → EX-130 %d' % (f['fail_top']['old'], f['fail_top']['new']), '',
              '## 테라 (보고 지표)', '',
              '- 사람이 테라를 고른 test %d행의 테라 확률 합: EX-124 %.4f → EX-130 %.4f' % (
                  t['human_tera'], t['tera_mass_human']['old'], t['tera_mass_human']['new']), '',
              '## 테라 지식 held-out 정답률', '', '| 유형 | n | EX-124 | EX-130 |', '|---|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind in k['ex130'][part]:
            a, b = k['ex124'][part][kind], k['ex130'][part][kind]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% |' % (part, kind, b['n'], 100 * a['accuracy'],
                                                             100 * b['accuracy']))
    lines += ['', '## 자료와 학습', '',
              '- v4 자료 길이 제외 %d행(비율 %.4f)' % (data['token_budget_exclusions'], data['exclusion_rate']),
              '- 학습 행 %d(모방 %d + 테라 지식 %d), 보정 %d(모방만), validation %d' % (
                  split['train'], split['train'] - split['extra_train'], split['extra_train'], split['calibration'],
                  split['validation']), '',
              '| epoch | train loss | validation NLL(원 logit) | 일치율 |', '|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% |' % (r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-',
                                                    r['raw']['loss'], 100 * r['raw']['accuracy']))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '',
              '## 해석 한계', '',
              '- 실패 표시는 공개 상태로 결과가 정해지는 경우만이다(EX-126 규칙). Whirlwind/Roar의 교체 대상 없음, Wish 중복은 빠진다.',
              '- `out`은 상대 가정 세트(v2 corpus 최빈 세트) 기준 최대값이다.',
              '- 테라 B 지식 행은 EX-124와 같은 v2 상태 텍스트다.',
              '- 단일 시드 학습이다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
