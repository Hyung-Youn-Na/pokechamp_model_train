"""EX-126 evaluation on GPU2: effect knowledge held-out (initial / EX-124 / EX-126), Tera held-out (EX-126 against
EX-124's stored result), locked test once, and the failure-option probability mass against EX-124.

EX-124 test values come from its stored `evaluation/test-selected.jsonl`; only the effect held-out rows are run
through EX-124 selected (once). Frozen judgement in the EX-126 protocol.
"""
from __future__ import annotations
import json
import os
import time

from . import config as c
from .effect_knowledge import option_outcomes
from .evaluation import evaluate
from .evaluation_tera import knowledge
from .evaluation_v2 import _interval, cluster_interval
from .resources import gpu
from .storage import atomic, jsonl, read, seal, verify_seal

SEED = 20261026
NLL_MARGIN = 0.02
FAILING = ('fails', 'immune', 'absorbed', 'reflected')
PARTS = ('heldout-A', 'heldout-B', 'heldout-C')
CHECKPOINTS = {'initial': c.MODEL_DIR, 'ex124': c.RUN_TERA_TRAINING / 'checkpoints/selected',
               'ex126': c.RUN_EFFECT_TRAINING / 'checkpoints/selected'}


def failing_options(records):
    """{sample_id: [action ids whose outcome the visible state decides as not working]}."""
    out = {}
    for record in records:
        bad = [a for a, label in option_outcomes(record).items() if label in FAILING]
        if bad:
            out[record['sample_id']] = bad
    return out


def fail_metrics(new_rows, old_rows, failing, replay_of):
    old = {r['sample_id']: r for r in old_rows}
    pairs, rows = [], []
    for r in new_rows:
        o = old.get(r['sample_id'])
        if o is None:
            continue
        pairs.append(dict(replay_id=replay_of[r['sample_id']], nll=r['nll'] - o['nll']))
        bad = failing.get(r['sample_id'])
        if not bad:
            continue
        new = sum(r['probabilities'].get(a, 0.0) for a in bad)
        was = sum(o['probabilities'].get(a, 0.0) for a in bad)
        rows.append(dict(replay_id=replay_of[r['sample_id']], new=new, old=was, d=new - was, human=r['label'] in bad,
                         new_top=r['choice'] in bad, old_top=o['choice'] in bad))
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    return dict(
        nll_diff=mean([p['nll'] for p in pairs]), nll_diff_95=cluster_interval(pairs, 'nll', seed=SEED),
        paired_rows=len(pairs), rows_with_failing=len(rows), human_chose_failing=sum(x['human'] for x in rows),
        fail_mass=dict(new=mean([x['new'] for x in rows]), old=mean([x['old'] for x in rows]),
                       diff=mean([x['d'] for x in rows]), diff_95=cluster_interval(rows, 'd', seed=SEED) if rows else None),
        fail_top=dict(new=sum(x['new_top'] for x in rows), old=sum(x['old_top'] for x in rows)))


def verdict(m):
    high = m['fail_mass']['diff_95'][1] if m['fail_mass']['diff_95'] else None
    ok = m['nll_diff_95'][1] <= NLL_MARGIN
    if high is not None and high < 0:
        return '실패 선택지 확률 감소, 일반 재현 유지' if ok else '실패 선택지 확률 감소, 일반 재현 저하'
    return '실패 선택지 차이 불분명, 일반 재현 유지' if ok else '개선 없음'


def run():
    out = c.RUN_EFFECT_TRAINING
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-126 is not ready for evaluation: %r' % status)
    if read(c.RUN_TERA_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_TERA_TRAINING):
        raise RuntimeError('EX-124 must be completed and sealed first')
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(c.GPU2_INDEX, c.GPU2_UUID) as (env, _):
        os.environ.update(env)
        effect = {name: knowledge(name, path, out, dataset=c.EFFECT_KNOWLEDGE, parts=PARTS, prefix='effect-knowledge')
                  for name, path in CHECKPOINTS.items()}
        tera = knowledge('ex126', CHECKPOINTS['ex126'], out)
        done = out / 'evaluation/completed-selected.json'
        if done.exists():
            test = read(done)['metrics']
        elif (out / 'evaluation/reservation-selected.json').exists():
            raise RuntimeError('locked test was started but not completed; it is not re-run')
        else:
            test = evaluate('selected', CHECKPOINTS['ex126'], out, dataset=c.V2_DATASET, head_limit=c.V2_HEAD_LIMIT)
    records = list(jsonl(c.EX071_PREPARED / 'test.jsonl'))
    replay_of = {r['sample_id']: r['replay_id'] for r in records}
    metrics = fail_metrics(list(jsonl(out / 'evaluation/test-selected.jsonl')),
                           list(jsonl(c.RUN_TERA_TRAINING / 'evaluation/test-selected.jsonl')), failing_options(records),
                           replay_of)
    ex124 = read(c.RUN_TERA_TRAINING / 'evaluation/report.json')
    report = dict(at=time.time(), effect_knowledge=effect, tera_knowledge=dict(ex126=tera, ex124=ex124['knowledge']['ex124']),
                  test=test, ex124_test=ex124['test']['all'], failing=metrics, verdict=verdict(metrics))
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    return report


def write_report(out, report):
    f, k = report['failing'], report['effect_knowledge']
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    pct = lambda v: '%.2f%%' % (100 * v) if v is not None else '—'
    lines = ['# EX-126 laya v2 + 테라 + 효과 지식 학습 보고', '',
             'EX-124(v2+테라)와 같은 시작 모델, 설정, 렌더러에서 학습 행에 효과 지식 행만 더했다(GPU2). '
             '사람 선택 재현과 지식 정답률이며 승률이 아니다.', '',
             '## 판정 (실행 전 동결)', '',
             '- 실패·무효로 정해진 선택지가 있는 test %d행의 그 선택지 확률 합 차이(EX-126 − EX-124): %+.4f, 95%% %s' % (
                 f['rows_with_failing'], f['fail_mass']['diff'] or 0.0, _interval(f['fail_mass']['diff_95'])
                 if f['fail_mass']['diff_95'] else '—'),
             '- 전체 NLL 차이: %+.4f, 95%% %s (비열등 상한 +%.2f)' % (f['nll_diff'], _interval(f['nll_diff_95']), NLL_MARGIN),
             '- **%s**' % report['verdict'], '',
             '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|',
             '| EX-124 v2+테라 | %.4f | %.2f%% | %.4f |' % (report['ex124_test']['nll'],
                                                       100 * report['ex124_test']['action_match_rate'],
                                                       report['ex124_test']['ece']),
             '| EX-126 v2+테라+효과 | %.4f | %.2f%% | %.4f |' % (report['test']['all']['nll'],
                                                         100 * report['test']['all']['action_match_rate'],
                                                         report['test']['all']['ece']), '',
             '## 실패 선택지 (판정 외 포함)', '',
             '| 지표 | EX-124 | EX-126 |', '|---|---:|---:|',
             '| 실패 선택지 확률 합 평균 | %s | %s |' % (pct(f['fail_mass']['old']), pct(f['fail_mass']['new'])),
             '| 실패 선택지가 1순위인 행 | %d | %d |' % (f['fail_top']['old'], f['fail_top']['new']),
             '', '사람이 실패 선택지를 고른 행: %d/%d.' % (f['human_chose_failing'], f['rows_with_failing']), '',
             '## 효과 지식 held-out 정답률', '', '| 유형 | n | initial | EX-124 | EX-126 |', '|---|---:|---:|---:|---:|']
    for part in PARTS:
        for kind in k['ex126'][part]:
            row = [k[m][part][kind] for m in ('initial', 'ex124', 'ex126')]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% | %.1f%% |' % (part, kind, row[0]['n'],
                                                                     *[100 * r['accuracy'] for r in row]))
    t = report['tera_knowledge']
    lines += ['', '## 테라 지식 held-out (망각 확인)', '', '| 유형 | n | EX-124 | EX-126 |', '|---|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind in t['ex126'][part]:
            a, b = t['ex124'][part][kind], t['ex126'][part][kind]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% |' % (part, kind, b['n'], 100 * a['accuracy'], 100 * b['accuracy']))
    by_source = split.get('extra_train_by_source', {})
    lines += ['', '## 학습', '',
              '- 학습 행 %d(모방 %d + 지식 %d: %s), 보정 %d(모방만), validation %d' % (
                  split['train'], split['train'] - split['extra_train'], split['extra_train'],
                  ', '.join('%s %d' % kv for kv in by_source.items()), split['calibration'], split['validation']),
              '', '| epoch | train loss | validation NLL(원 logit) | 일치율 |', '|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% |' % (r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-',
                                                    r['raw']['loss'], 100 * r['raw']['accuracy']))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '',
              '## 해석 한계', '', '- 지식 행 추가로 학습량도 늘었다. 지식 효과와 분리하지 않았다.',
              '- 실패 선택지는 공개 정보만으로 결과가 정해지는 기술만 센다(기록이 필요한 기술, 미공개 특성 의존 제외).',
              '- 지식은 "무엇이 일어나는가"이며 전략 라벨이 없다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
