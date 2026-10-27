"""EX-121 locked test (v2 initial/selected once each) and the paired comparison with EX-118 v1 selected.

v1 values come from EX-118's stored `evaluation/test-selected.jsonl`; nothing is re-inferred. Differences are
per test row (same sample_id), with a replay-cluster bootstrap (frozen in the EX-121 protocol).
"""
from __future__ import annotations
import json
import os
import random
import time

from . import config as c
from .evaluation import GROUPS, evaluate
from .resources import gpu0
from .storage import atomic, jsonl, read, seal, verify_seal

SEED = 20261024
DRAWS = 10000
MODELS = {'initial': c.MODEL_DIR, 'selected': c.RUN_V2_TRAINING / 'checkpoints/selected'}


def cluster_interval(pairs, key, seed=SEED, draws=DRAWS):
    """95% percentile interval of the mean per-row difference, resampling replays (clusters)."""
    clusters = {}
    for p in pairs:
        clusters.setdefault(p['replay_id'], []).append(p[key])
    groups = list(clusters.values())
    if not groups:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(draws):
        sample = [rng.choice(groups) for _ in groups]
        means.append(sum(map(sum, sample)) / sum(map(len, sample)))
    means.sort()
    return [means[int(.025 * draws)], means[int(.975 * draws) - 1]]


def paired(v2_rows, v1_rows, replay_of):
    v1 = {r['sample_id']: r for r in v1_rows}
    pairs = []
    for r in v2_rows:
        o = v1.get(r['sample_id'])
        if o is None:
            continue
        pairs.append(dict(sample_id=r['sample_id'], replay_id=replay_of[r['sample_id']],
                          nll=r['nll'] - o['nll'], correct=float(r['correct']) - float(o['correct']),
                          **{g: r[g] for g in GROUPS}))
    return pairs


def compare(pairs):
    def block(rows):
        n = len(rows)
        return dict(n=n, replays=len({r['replay_id'] for r in rows}),
                    nll_diff=sum(r['nll'] for r in rows) / n if n else None,
                    nll_diff_95=cluster_interval(rows, 'nll'),
                    match_diff=sum(r['correct'] for r in rows) / n if n else None,
                    match_diff_95=cluster_interval(rows, 'correct'))
    out = dict(all=block(pairs))
    for g in GROUPS:
        out['by_' + g] = {k: block([r for r in pairs if str(r[g]) == k]) for k in sorted({str(r[g]) for r in pairs})}
    return out


def verdict(result):
    low, high = result['all']['nll_diff_95']
    if high < 0:
        return 'v2가 사람 선택 재현을 개선'
    if low > 0:
        return 'v2가 악화'
    return '구별되지 않음'


def run():
    out = c.RUN_V2_TRAINING
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-121 is not ready for the locked test: %r' % status)
    if verify_seal(c.RUN_TRAINING):
        raise RuntimeError('EX-118 seal failed; its stored v1 predictions cannot be used')
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu0() as (env, _):
        os.environ.update(env)
        metrics = {}
        for name, path in MODELS.items():
            done = out / ('evaluation/completed-%s.json' % name)
            if done.exists():
                metrics[name] = read(done)['metrics']
            elif (out / ('evaluation/reservation-%s.json' % name)).exists():
                raise RuntimeError('test for %s was started but not completed; it is not re-run' % name)
            else:
                metrics[name] = evaluate(name, path, out, dataset=c.V2_DATASET, head_limit=c.V2_HEAD_LIMIT)
    replay_of = {r['sample_id']: r['replay_id'] for r in jsonl(c.EX071_PREPARED / 'test.jsonl')}
    v2_rows = list(jsonl(out / 'evaluation/test-selected.jsonl'))
    v1_rows = list(jsonl(c.RUN_TRAINING / 'evaluation/test-selected.jsonl'))
    comparison = compare(paired(v2_rows, v1_rows, replay_of))
    v1 = read(c.RUN_TRAINING / 'evaluation/report.json')['metrics']
    report = dict(at=time.time(), metrics=metrics, v1_reference={k: v1[k]['all'] for k in v1},
                  comparison=comparison, verdict=verdict(comparison),
                  excluded_test_rows=1024 - len(v2_rows),
                  interpretation='사람 선택 재현 지표다. 렌더러 외 조건(시작 모델·설정·분할)은 EX-118과 같다.')
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    return report


def _interval(v):
    return '[%+.4f, %+.4f]' % tuple(v) if v else '—'


def write_report(out, report):
    sel = read(out / 'selection.json')
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    pre = read(out / 'preflight/result.json')
    split = read(out / 'split.json')
    m, cmp_ = report['metrics'], report['comparison']
    fmt = lambda x: '%.4f | %.2f%% | %.4f' % (x['nll'], 100 * x['action_match_rate'], x['ece'])
    lines = ['# EX-121 laya 렌더러 v2(4종) 학습과 v1 쌍비교 보고', '',
             '렌더러 `laya-compact-v2[damage,moves,speed,switch]`로 EX-118과 같은 시작 모델·설정·분할에서 학습했다. '
             '사람 선택 재현 지표이며 승률이 아니다. 배틀은 EX-122에서 본다.', '',
             '## 판정 (실행 전 동결)', '',
             '- 행별 NLL 차이(v2 selected − v1 selected) 리플레이 클러스터 95%%: %s → **%s**' % (
                 _interval(cmp_['all']['nll_diff_95']), report['verdict']),
             '- 쌍비교 행 %d (리플레이 %d), v2 길이 제외 test 행 %d' % (cmp_['all']['n'], cmp_['all']['replays'],
                                                            report['excluded_test_rows']), '',
             '## 잠긴 test', '', '| 모델 | NLL(보정) | 일치율 | ECE |', '|---|---:|---:|---:|',
             '| v1 selected (EX-118) | %s |' % fmt(report['v1_reference']['selected']),
             '| v2 initial | %s |' % fmt(m['initial']['all']), '| v2 selected | %s |' % fmt(m['selected']['all']), '',
             '평균 차이: NLL %+.4f, 일치율 %+.2f%%p (95%% %s).' % (
                 cmp_['all']['nll_diff'], 100 * cmp_['all']['match_diff'],
                 '[%+.2f, %+.2f]%%p' % tuple(100 * x for x in cmp_['all']['match_diff_95'])), '',
             '## 라벨 종류별 차이 (v2 − v1, 판정 외)', '',
             '| 종류 | n | NLL 차이 | 95% | 일치율 차이 | 95% |', '|---|---:|---:|---|---:|---|']
    for k, v in cmp_['by_label_kind'].items():
        lines.append('| %s | %d | %+.4f | %s | %+.2f%%p | %s |' % (
            k, v['n'], v['nll_diff'], _interval(v['nll_diff_95']), 100 * v['match_diff'],
            '[%+.1f, %+.1f]' % tuple(100 * x for x in v['match_diff_95'])))
    lines += ['', '## 학습', '',
              '- 자료: `%s` (train %d, 보정 %d, validation %d), head_max_len %d' % (
                  c.V2_DATASET, split['train'] + split['calibration'], split['calibration'], split['validation'],
                  c.V2_HEAD_LIMIT),
              '- 사전검사: loss %s, 재로딩 logit 최대 차이 %.2e' % (' → '.join('%.4f' % h for h in pre['history']),
                                                         pre['reload_max_abs_logit_diff']),
              '- 학습 시간: %.2f시간' % (read(out / 'status.json').get('seconds', 0) / 3600), '',
              '| epoch | train loss | validation NLL(원 logit) | validation 일치율 |', '|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% |' % (r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-',
                                                    r['raw']['loss'], 100 * r['raw']['accuracy']))
    lines += ['', '선택 epoch %d, 보정 온도 `%s`.' % (sel['selected_epoch'],
                                              json.dumps(sel['temperature_by_options'] or sel['temperature'])), '',
              '## 해석 한계', '',
              '- 네 모듈을 함께 넣어 개별 기여는 분리하지 않았다.',
              '- 상대 미공개 정보는 EX-071 corpus 최빈 세트 가정에 의존한다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
