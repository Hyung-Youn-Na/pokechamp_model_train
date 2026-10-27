"""EX-128 evaluation on GPU0: Tera knowledge held-out (EX-128 once), locked test once, paired with EX-124 selected.

EX-124 test rows and knowledge results are read from its sealed run; nothing of EX-124 is re-inferred. The primary
judgement is the switch-row NLL difference (human label voluntary/forced/pivot switch); the secondary is overall
NLL non-inferiority (+0.02). Both are frozen in the EX-128 protocol, as is the EX-129 battle gate.
"""
from __future__ import annotations
import json
import os
import time

from integration.pokechamp.imitation.schema import ImitationInput

from . import config as c
from .evaluation import evaluate
from .evaluation_tera import knowledge, tera_metrics
from .evaluation_v2 import _interval, cluster_interval
from .resources import gpu
from .storage import atomic, jsonl, read, seal, verify_seal

SEED = 20261027
NLL_MARGIN = 0.02
SWITCH_LABELS = ('voluntary_switch', 'forced_switch', 'pivot_switch')
CHECKPOINT = c.RUN_V3_TRAINING / 'checkpoints/selected'


def hidden_bucket(record):
    """Revealed moves of the opponent's active Pokemon in the input: 0-1 / 2-3 / 4, or no_foe."""
    snapshot = json.loads(ImitationInput.from_body(record['input']).body['state'])['snapshot']
    slot = snapshot['opponent_active_slot']
    if not slot:
        return 'no_foe'
    n = len({m['slot']: m for m in snapshot['opponent_team']}[slot]['moves'])
    return '0-1' if n <= 1 else '2-3' if n <= 3 else '4'


def block(rows, key='nll'):
    n = len(rows)
    return dict(n=n, replays=len({r['replay_id'] for r in rows}),
                nll_diff=sum(r[key] for r in rows) / n if n else None,
                nll_diff_95=cluster_interval(rows, key, seed=SEED),
                match_diff=sum(r['correct'] for r in rows) / n if n else None,
                match_diff_95=cluster_interval(rows, 'correct', seed=SEED))


def paired(new_rows, old_rows, info):
    old = {r['sample_id']: r for r in old_rows}
    pairs = []
    for r in new_rows:
        o = old.get(r['sample_id'])
        if o is not None:
            pairs.append(dict(sample_id=r['sample_id'], nll=r['nll'] - o['nll'],
                              correct=float(r['correct']) - float(o['correct']), label_kind=r['label_kind'],
                              decision_kind=r['decision_kind'], **info[r['sample_id']]))
    return pairs


def compare(pairs):
    out = dict(all=block(pairs), switch=block([p for p in pairs if p['label_kind'] in SWITCH_LABELS]))
    for group in ('label_kind', 'decision_kind', 'hidden'):
        keys = sorted({p[group] for p in pairs})
        out['by_' + group] = {k: block([p for p in pairs if p[group] == k]) for k in keys}
    return out


def verdict(cmp_):
    improved = cmp_['switch']['nll_diff_95'][1] < 0
    kept = cmp_['all']['nll_diff_95'][1] <= NLL_MARGIN
    text = ('교체 판단 개선' if improved else '교체 차이 불분명') + (', 전체 비열등' if kept else ', 전체 저하')
    return text, improved or kept


def run():
    out = c.RUN_V3_TRAINING
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-128 is not ready for evaluation: %r' % status)
    if read(c.RUN_TERA_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_TERA_TRAINING):
        raise RuntimeError('EX-124 must be completed and sealed first')
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(c.GPU_INDEX, c.GPU_UUID) as (env, _):
        os.environ.update(env)
        know = knowledge('ex128', CHECKPOINT, out)
        done = out / 'evaluation/completed-selected.json'
        if done.exists():
            test = read(done)['metrics']
        elif (out / 'evaluation/reservation-selected.json').exists():
            raise RuntimeError('locked test was started but not completed; it is not re-run')
        else:
            test = evaluate('selected', CHECKPOINT, out, dataset=c.V3_DATASET, head_limit=c.V2_HEAD_LIMIT)
    info = {r['sample_id']: dict(replay_id=r['replay_id'], hidden=hidden_bucket(r))
            for r in jsonl(c.EX071_PREPARED / 'test.jsonl')}
    new_rows = list(jsonl(out / 'evaluation/test-selected.jsonl'))
    old_rows = list(jsonl(c.RUN_TERA_TRAINING / 'evaluation/test-selected.jsonl'))
    cmp_ = compare(paired(new_rows, old_rows, info))
    text, gate = verdict(cmp_)
    report = dict(at=time.time(), test=test, ex124_test=read(c.RUN_TERA_TRAINING / 'evaluation/report.json')['test'],
                  knowledge=dict(ex124=read(c.RUN_TERA_TRAINING / 'evaluation/knowledge-ex124.json'), ex128=know),
                  comparison=cmp_, tera=tera_metrics(new_rows, old_rows, {k: v['replay_id'] for k, v in info.items()}),
                  verdict=text, battle_gate=gate)
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(), verdict=text, battle_gate=gate))
    seal(out)
    print(json.dumps(dict(verdict=text, battle_gate=gate, switch=cmp_['switch'], all=cmp_['all']), ensure_ascii=False))
    return report


def _row(name, b):
    return '| %s | %d | %+.4f | %s | %+.2f%%p |' % (name, b['n'], b['nll_diff'], _interval(b['nll_diff_95']),
                                                  100 * b['match_diff'])


def write_report(out, report):
    cmp_, t, k = report['comparison'], report['tera'], report['knowledge']
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    data = read(c.V3_DATASET / 'validation.json')
    lines = ['# EX-128 laya v3 렌더러(상대 세트 추론) + 테라 지식 학습 보고', '',
             'EX-124(v2+테라)와 같은 시작 모델, 설정, 테라 지식 행에서 행동 행의 렌더러만 v3로 바꿨다(GPU0). '
             '사람 선택 재현이며 승률이 아니다.', '',
             '## 판정 (실행 전 동결)', '',
             '- 주 지표: 교체 행(사람 라벨 voluntary/forced/pivot switch) NLL 차이(EX-128 − EX-124) %+.4f, 95%% %s' % (
                 cmp_['switch']['nll_diff'], _interval(cmp_['switch']['nll_diff_95'])),
             '- 보조 지표: 전체 NLL 차이 %+.4f, 95%% %s (비열등 상한 +%.2f)' % (
                 cmp_['all']['nll_diff'], _interval(cmp_['all']['nll_diff_95']), NLL_MARGIN),
             '- **%s**. EX-129 배틀 진행 조건(주 지표 개선 또는 전체 비열등): %s' % (
                 report['verdict'], '충족' if report['battle_gate'] else '미충족'), '',
             '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|']
    for name, m in (('EX-124 v2+테라', report['ex124_test']['all']), ('EX-128 v3+테라', report['test']['all'])):
        lines.append('| %s | %.4f | %.2f%% | %.4f |' % (name, m['nll'], 100 * m['action_match_rate'], m['ece']))
    lines += ['', '## 같은 행 차이 (EX-128 − EX-124, replay 클러스터 95%)', '',
              '| 구분 | n | NLL 차이 | 95% | 일치율 차이 |', '|---|---:|---:|---|---:|',
              _row('전체', cmp_['all']), _row('교체 행', cmp_['switch'])]
    for group, title in (('by_label_kind', '라벨'), ('by_hidden', '상대 공개 기술 수'), ('by_decision_kind', '결정')):
        for key, b in cmp_[group].items():
            lines.append(_row('%s %s' % (title, key), b))
    lines += ['', '## 테라 (보고 지표)', '',
              '- 사람이 테라를 고른 test %d행의 테라 확률 합: EX-124 %.4f → EX-128 %.4f' % (
                  t['human_tera'], t['tera_mass_human']['old'], t['tera_mass_human']['new']), '',
              '## 테라 지식 held-out 정답률', '', '| 유형 | n | EX-124 | EX-128 |', '|---|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind in k['ex128'][part]:
            a, b = k['ex124'][part][kind], k['ex128'][part][kind]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% |' % (part, kind, b['n'], 100 * a['accuracy'],
                                                             100 * b['accuracy']))
    lines += ['', '## 자료와 학습', '',
              '- v3 자료 길이 제외 %d행(비율 %.4f)' % (data['token_budget_exclusions'], data['exclusion_rate']),
              '- 학습 행 %d(모방 %d + 테라 지식 %d), 보정 %d(모방만), validation %d' % (
                  split['train'], split['train'] - split['extra_train'], split['extra_train'], split['calibration'],
                  split['validation']), '',
              '| epoch | train loss | validation NLL(원 logit) | 일치율 |', '|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% |' % (r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-',
                                                    r['raw']['loss'], 100 * r['raw']['accuracy']))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '',
              '## 해석 한계', '',
              '- 상대 세트는 2026-08 래더(1695) 집계 marginal이며 기술 포함 확률을 독립으로 다뤘다. 리플레이 시기(2023~2026)와 메타가 다르다.',
              '- 소모·제거된 도구는 공개 상태에서 "모름"과 구별되지 않는다(스냅숏 한계).',
              '- 테라 B 지식 행은 EX-124와 같은 v2 상태 텍스트다.',
              '- 단일 시드 학습이다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
