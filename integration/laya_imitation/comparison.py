"""Same-run model comparisons on the sealed EX-120 schedule.

EX-122: v1 (EX-118) vs v2 (EX-121) on GPU0/8107. EX-125: v2 (EX-121) vs v2+Tera knowledge (EX-124) on GPU1/8109.
EX-129: v2+Tera (EX-124) vs v3+Tera (EX-128) on GPU0/8107, judged for non-inferiority (`margin`).
EX-131: v2+Tera (EX-124) vs v4+Tera (EX-130) on GPU1/8109, same judgement (no offline gate, D-191).
EX-133: v2+Tera (EX-124) vs v2+Tera with outcome-weighted imitation (EX-132) on GPU0/8107 (D-193, no offline gate).
EX-137: v4+Tera (EX-130) vs v5+Tera (EX-136, opponent item state and counters) on GPU0/8107 (D-195, no offline gate).
EX-143 / EX-144: v5+Tera (EX-136) vs v6s (EX-141, GPU0/8107) / v6h (EX-142, 2048 tokens, GPU1/8109) (D-198).
Each EX-120 swapped pair is played twice back to back (one pair per model, digest-ordered), with both servings alive.
Per-game play, ledger, no replay of claimed slots and audits are `battle`'s, unchanged.
"""
from __future__ import annotations
import json
import random
import time

from . import config as c
from .battle import BATTLE_SECONDS, CLEANUP_SECONDS, Serving, play_slot, summarize
from .generalization import COLLECTION, SCORE, summarize_generalization
from .storage import append_jsonl, atomic, digest, jsonl, read, seal, source_identity, verify_seal

DRAWS = 10000
RENDER = {'laya-v1': 'v1', 'laya-v2': 'v2', 'laya-v2-initial': 'v2', 'laya-v2t': 'v2', 'laya-v2t-initial': 'v2',
          'laya-v2te': 'v2', 'laya-v2te-initial': 'v2', 'laya-v3t': 'v3', 'laya-v3t-initial': 'v3',
          'laya-v4t': 'v4', 'laya-v4t-initial': 'v4', 'laya-v2tw': 'v2', 'laya-v2tw-initial': 'v2',
          'laya-v5t': 'v5', 'laya-v5t-initial': 'v5',
          'laya-v2t-fix': 'v2fix', 'laya-v2t-info': 'v2info', 'laya-v2t-info-initial': 'v2info',
          'laya-v2t-fix-tp1': 'v2fix', 'laya-v2t-fix-tp3': 'v2fix', 'laya-v2t-fix-tp3-initial': 'v2fix',
          'laya-v2t-fix-tdef': 'v2fixtd',
          'laya-v6st': 'v6s', 'laya-v6st-initial': 'v6s', 'laya-v6ht': 'v6h', 'laya-v6ht-initial': 'v6h'}


class Study:
    def __init__(self, **kw):
        self.__dict__.update(kw)


EX122 = Study(
    experiment='EX-122', plan='EP-210', seed=20261024, models=('laya-v1', 'laya-v2'), out=c.RUN_COMPARE,
    viewer=c.VIEWER_COMPARE, gpu=(c.GPU_INDEX, c.GPU_UUID), port=c.PORT, hours=c.COMPARE_HOURS,
    runs={'laya-v1': ('EX-118', c.RUN_TRAINING), 'laya-v2': ('EX-121', c.RUN_V2_TRAINING)},
    mock_model='laya-v2-initial', replicate='laya-v1',
    verdicts=('v2가 배틀 성적을 개선', 'v2가 악화', '구별되지 않음'),
    meta=dict(experiment='EX-122', plan='EP-210', slug='ex122', pairs=128, title='EX-122 · laya v1·v2 256경기',
              heading='EX-122 · laya v1(EX-118)과 v2(EX-121) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. v2 경기의 압축 입력 탭은 '
                    'v2 렌더러(기술 변형·속도·교체·피해량)로 복원합니다. 확률은 행동 선택 확률이며 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex122-laya-v1'))

EX125 = Study(
    experiment='EX-125', plan='EP-212', seed=20261025, models=('laya-v2', 'laya-v2t'), out=c.RUN_COMPARE2,
    viewer=c.VIEWER_COMPARE2, gpu=(c.GPU1_INDEX, c.GPU1_UUID), port=c.PORT2, hours=c.COMPARE_HOURS,
    runs={'laya-v2': ('EX-121', c.RUN_V2_TRAINING), 'laya-v2t': ('EX-124', c.RUN_TERA_TRAINING)},
    mock_model='laya-v2t-initial', replicate=None,
    verdicts=('v2+테라가 배틀 성적을 개선', '악화', '구별되지 않음'),
    meta=dict(experiment='EX-125', plan='EP-212', slug='ex125', pairs=128, title='EX-125 · laya v2·v2+테라 256경기',
              heading='EX-125 · laya v2(EX-121)와 v2+테라 지식(EX-124) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. 두 모델 모두 v2 렌더러 입력이며 '
                    '차이는 학습에 더한 테라 기본 지식 행입니다. 확률은 행동 선택 확률이며 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex125-laya-v1'))


EX127 = Study(
    experiment='EX-127', plan='EP-213', seed=20261026, models=('laya-v2t', 'laya-v2te'), out=c.RUN_COMPARE3,
    viewer=c.VIEWER_COMPARE3, gpu=(c.GPU2_INDEX, c.GPU2_UUID), port=c.PORT3, hours=c.COMPARE_HOURS,
    runs={'laya-v2t': ('EX-124', c.RUN_TERA_TRAINING), 'laya-v2te': ('EX-126', c.RUN_EFFECT_TRAINING)},
    mock_model='laya-v2te-initial', replicate=None,
    verdicts=('효과 지식이 배틀 성적을 개선', '악화', '구별되지 않음'),
    meta=dict(experiment='EX-127', plan='EP-213', slug='ex127', pairs=128, title='EX-127 · laya v2+테라·+효과 256경기',
              heading='EX-127 · laya v2+테라(EX-124)와 v2+테라+효과 지식(EX-126) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. 두 모델 모두 v2 렌더러 입력이며 '
                    '차이는 학습에 더한 기술·도구·특성 효과 지식 행입니다. 확률은 행동 선택 확률이며 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex127-laya-v1'))

EX129 = Study(
    experiment='EX-129', plan='EP-214', seed=20261027, models=('laya-v2t', 'laya-v3t'), out=c.RUN_COMPARE4,
    viewer=c.VIEWER_COMPARE4, gpu=(c.GPU_INDEX, c.GPU_UUID), port=c.PORT, hours=c.COMPARE_HOURS,
    runs={'laya-v2t': ('EX-124', c.RUN_TERA_TRAINING), 'laya-v3t': ('EX-128', c.RUN_V3_TRAINING)},
    mock_model='laya-v3t-initial', replicate=None, margin=0.05,
    verdicts=('v3+테라가 배틀 성적을 개선', '퇴보를 배제하지 못함', '비퇴보'),
    meta=dict(experiment='EX-129', plan='EP-214', slug='ex129', pairs=128, title='EX-129 · laya v2+테라·v3+테라 256경기',
              heading='EX-129 · laya v2+테라(EX-124)와 v3+테라(EX-128) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. 두 모델 모두 테라 지식 행을 함께 학습했고 '
                    '차이는 행동 입력 렌더러(v2 대 v3 상대 세트 추론)입니다. 비퇴보 확인용이며 확률은 행동 선택 확률이고 '
                    '승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex129-laya-v1'))

EX131 = Study(
    experiment='EX-131', plan='EP-215', seed=20261028, models=('laya-v2t', 'laya-v4t'), out=c.RUN_COMPARE5,
    viewer=c.VIEWER_COMPARE5, gpu=(c.GPU1_INDEX, c.GPU1_UUID), port=c.PORT2, hours=c.COMPARE_HOURS,
    runs={'laya-v2t': ('EX-124', c.RUN_TERA_TRAINING), 'laya-v4t': ('EX-130', c.RUN_V4_TRAINING)},
    mock_model='laya-v4t-initial', replicate=None, margin=0.05,
    verdicts=('v4+테라가 배틀 성적을 개선', '퇴보를 배제하지 못함', '비퇴보'),
    meta=dict(experiment='EX-131', plan='EP-215', slug='ex131', pairs=128, title='EX-131 · laya v2+테라·v4+테라 256경기',
              heading='EX-131 · laya v2+테라(EX-124)와 v4+테라(EX-130) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. 두 모델 모두 테라 지식 행을 함께 학습했고 '
                    '차이는 행동 입력 렌더러(v2 대 v4 확정 실패 표시·교체 후보 공격 피해)입니다. 확률은 행동 선택 확률이고 '
                    '승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex131-laya-v1'))

EX133 = Study(
    experiment='EX-133', plan='EP-216', seed=20261029, models=('laya-v2t', 'laya-v2tw'), out=c.RUN_COMPARE6,
    viewer=c.VIEWER_COMPARE6, gpu=(c.GPU_INDEX, c.GPU_UUID), port=c.PORT, hours=c.COMPARE_HOURS,
    runs={'laya-v2t': ('EX-124', c.RUN_TERA_TRAINING), 'laya-v2tw': ('EX-132', c.RUN_WEIGHTED_TRAINING)},
    mock_model='laya-v2tw-initial', replicate=None,
    verdicts=('승패 가중이 배틀 성적을 개선', '악화', '구별되지 않음'),
    meta=dict(experiment='EX-133', plan='EP-216', slug='ex133', pairs=128, title='EX-133 · laya v2+테라·승패 가중 256경기',
              heading='EX-133 · laya v2+테라(EX-124)와 v2+테라 승패 가중 모방(EX-132) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. 두 모델 모두 v2 렌더러 입력과 테라 지식 행을 '
                    '썼고 차이는 모방 학습 행의 리플레이 승패 가중치입니다. 확률은 행동 선택 확률이며 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex133-laya-v1'))

# EX-137 (D-195): v4+Tera (EX-130) vs v5+Tera (EX-136), one variable apart; v2+Tera is compared offline (EX-125 slots).
EX137 = Study(
    experiment='EX-137', plan='EP-218', seed=20261033, models=('laya-v4t', 'laya-v5t'), out=c.RUN_COMPARE7,
    viewer=c.VIEWER_COMPARE7, gpu=(c.GPU_INDEX, c.GPU_UUID), port=c.PORT, hours=c.COMPARE_HOURS,
    runs={'laya-v4t': ('EX-130', c.RUN_V4_TRAINING), 'laya-v5t': ('EX-136', c.RUN_V5_TRAINING)},
    mock_model='laya-v5t-initial', replicate=None, margin=0.05,
    verdicts=('v5+테라가 배틀 성적을 개선', '퇴보를 배제하지 못함', '비퇴보'),
    meta=dict(experiment='EX-137', plan='EP-218', slug='ex137', pairs=128, title='EX-137 · laya v4+테라·v5+테라 256경기',
              heading='EX-137 · laya v4+테라(EX-130)와 v5+테라(EX-136) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. 두 모델 모두 v4 모듈과 테라 지식 행을 썼고 '
                    '차이는 v5 렌더러의 상대 아이템 상태(미공개·들고 있음·제거)와 상태 카운터입니다. 확률은 행동 선택 확률이고 '
                    '승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex137-laya-v1'))


# EX-143 / EX-144 (D-198): v5+Tera (EX-136) against each v6 variant, one variable apart, run at the same time.
EX143 = Study(
    experiment='EX-143', plan='EP-221', seed=20261034, models=('laya-v5t', 'laya-v6st'), out=c.RUN_COMPARE10,
    viewer=c.VIEWER_COMPARE10, gpu=(c.GPU_INDEX, c.GPU_UUID), port=c.PORT, hours=c.COMPARE_HOURS,
    runs={'laya-v5t': ('EX-136', c.RUN_V5_TRAINING), 'laya-v6st': ('EX-141', c.RUN_V6S_TRAINING)},
    mock_model='laya-v6st-initial', replicate=None, margin=0.05,
    verdicts=('v6s가 배틀 성적을 개선', '퇴보를 배제하지 못함', '비퇴보'),
    meta=dict(experiment='EX-143', plan='EP-221', slug='ex143', pairs=128, title='EX-143 · laya v5+테라·v6s 256경기',
              heading='EX-143 · laya v5+테라(EX-136)와 v6s 반복 표시(EX-141) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. 두 모델 모두 v5 모듈과 테라 지식 행을 썼고 '
                    '차이는 v6s의 같은 기술 연속 사용 표시(streak)입니다. 확률은 행동 선택 확률이고 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex143-laya-v1'))

EX144 = Study(
    experiment='EX-144', plan='EP-221', seed=20261035, models=('laya-v5t', 'laya-v6ht'), out=c.RUN_COMPARE11,
    viewer=c.VIEWER_COMPARE11, gpu=(c.GPU1_INDEX, c.GPU1_UUID), port=c.PORT2, hours=c.COMPARE_HOURS,
    runs={'laya-v5t': ('EX-136', c.RUN_V5_TRAINING), 'laya-v6ht': ('EX-142', c.RUN_V6H_TRAINING)},
    mock_model='laya-v6ht-initial', replicate=None, margin=0.05,
    verdicts=('v6h가 배틀 성적을 개선', '퇴보를 배제하지 못함', '비퇴보'),
    meta=dict(experiment='EX-144', plan='EP-221', slug='ex144', pairs=128, title='EX-144 · laya v5+테라·v6h 256경기',
              heading='EX-144 · laya v5+테라(EX-136)와 v6h 긴 기록·2048토큰(EX-142) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. 두 모델 모두 v5 모듈과 테라 지식 행을 썼고 '
                    '차이는 v6h의 과거 턴 기록(2048토큰 안에서 4턴 이전까지)입니다. 확률은 행동 선택 확률이고 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex144-laya-v1'))


def make_schedule(base, study=EX122):
    """EX-120 rows -> 256 rows; per EX-120 pair, both models' pairs consecutively, first model by digest."""
    pairs = []
    for row in base:
        if not pairs or pairs[-1][0]['pair_id'] != row['pair_id']:
            pairs.append([])
        pairs[-1].append(row)
    out = []
    name = study.experiment.lower().replace('-', '') + '_first'
    for pair in pairs:
        first = int(digest([study.seed, name, pair[0]['pair_id']])[0], 16) % 2
        for model in (study.models if first == 0 else study.models[::-1]):
            prefix = model.split('-', 1)[1]
            for row in pair:
                out.append(dict(row, slot_id='%s-%s' % (prefix, row['slot_id']), pair_id='%s-%s' % (prefix, row['pair_id']),
                                base_slot_id=row['slot_id'], base_pair_id=row['pair_id'], model=model))
    for order, row in enumerate(out, 1):
        row['submission_order'] = order
    return out


def summarize_compare(rows, outcomes, latencies, ex120=None, study=EX122):
    old, new = study.models
    by_slot = {o['slot_id']: o for o in outcomes}
    per_model = {}
    for model in study.models:
        sub = [r for r in rows if r['model'] == model]
        outs = [by_slot[r['slot_id']] for r in sub if r['slot_id'] in by_slot]
        per_model[model] = summarize_generalization(sub, outs, latencies.get(model, []))
    base = {}
    for r in rows:
        o = by_slot.get(r['slot_id'])
        if o and o['status'] == 'completed':
            base.setdefault(r['base_slot_id'], dict(matchup=r['matchup_id']))[r['model']] = SCORE[o['result']]
    diffs = [dict(matchup=v['matchup'], d=v[new] - v[old]) for v in base.values() if old in v and new in v]
    clusters = {}
    for d in diffs:
        clusters.setdefault(d['matchup'], []).append(d['d'])
    groups = list(clusters.values())
    interval = None
    if groups:
        rng = random.Random(study.seed)
        means = []
        for _ in range(DRAWS):
            sample = [rng.choice(groups) for _ in groups]
            means.append(sum(map(sum, sample)) / sum(map(len, sample)))
        means.sort()
        interval = [means[int(.025 * DRAWS)], means[int(.975 * DRAWS) - 1]]
    replication = None
    if ex120 is not None and study.replicate:
        ex = {o['slot_id']: o for o in ex120}
        kept = [(r['base_slot_id'], by_slot[r['slot_id']]) for r in rows if r['model'] == study.replicate
                and r['slot_id'] in by_slot and by_slot[r['slot_id']]['status'] == 'completed']
        compared = [(ex[b], o) for b, o in kept if b in ex and ex[b]['status'] == 'completed']
        replication = dict(compared=len(compared), same_result=sum(a['result'] == o['result'] for a, o in compared),
                           same_result_and_turns=sum(a['result'] == o['result'] and a.get('turns') == o.get('turns')
                                                     for a, o in compared))
    return dict(models=per_model, paired=dict(
        slots=len(diffs), mean_diff=sum(d['d'] for d in diffs) / len(diffs) if diffs else None,
        matchup_bootstrap_95=interval, new_better=sum(d['d'] > 0 for d in diffs), old_better=sum(d['d'] < 0 for d in diffs),
        same=sum(d['d'] == 0 for d in diffs), old=old, new=new), v1_replication=replication)


def verdict(summary, study=EX122):
    for model, s in summary['models'].items():
        if s['status']['completed'] < 120:
            return '판정 보류(%s 정상 종료 %d/128 < 120)' % (model, s['status']['completed'])
    low, high = summary['paired']['matchup_bootstrap_95']
    better, worse, same = study.verdicts
    margin = getattr(study, 'margin', None)
    if margin is not None:
        # Non-inferiority (EX-129): `same` means the lower bound clears -margin.
        return better if low > 0 else same if low > -margin else worse
    return better if low > 0 else worse if high < 0 else same


def tera_usage(directory, rows, outcomes):
    """Per model: games with a `-terastallize` by the model side, decisions with a Tera option and Tera choices."""
    by_slot = {o['slot_id']: o for o in outcomes}
    out = {}
    for r in rows:
        o = by_slot.get(r['slot_id'])
        events = directory / 'games' / r['slot_id'] / 'events.jsonl'
        if o is None or not events.exists():
            continue
        m = out.setdefault(r['model'], dict(games=0, tera_games=0, tera_wins=0, tera_losses=0, available=0, chosen=0,
                                            turns=[]))
        m['games'] += 1
        used, turn = False, 0
        for e in jsonl(events):
            if e['type'] == 'selection' and e.get('probabilities'):
                if any(k.endswith(':tera') for k in e['probabilities']):
                    m['available'] += 1
                    m['chosen'] += e['choice'].endswith(':tera')
            elif e['type'] == 'protocol':
                for line in e['protocol'].split('\n'):
                    if line.startswith('|turn|'):
                        turn = int(line.split('|')[2])
                    elif line.startswith('|-terastallize|') and line.split('|')[2].startswith(r['model_side']) and not used:
                        used = True
                        m['turns'].append(turn)
        if used:
            m['tera_games'] += 1
            m['tera_wins'] += o.get('result') == 'win'
            m['tera_losses'] += o.get('result') == 'loss'
    for m in out.values():
        m['choice_rate'] = m['chosen'] / m['available'] if m['available'] else None
        m['turns'].sort()
    return out


def _failed_after(lines, i):
    """Lines after a `|move|` up to the next move or turn boundary: did it fail or hit an immunity?"""
    for line in lines[i + 1:]:
        if line.startswith(('|move|', '|turn|', '|upkeep')):
            return False
        if line.startswith(('|-fail|', '|-immune|', '|-block|')):
            return True
    return False


LOOP = 3   # the same move failing this many times in a row counts as a loop


def failed_moves(directory, rows, outcomes, model_of=lambda r: r['model']):
    """Per model: the model side's moves (not called ones) answered by `-fail` / `-immune` / `-block`, plus the
    longest run of the same move failing back to back per game (EX-131 loop metrics)."""
    by_slot = {o['slot_id']: o for o in outcomes}
    out = {}
    for r in rows:
        o = by_slot.get(r['slot_id'])
        events = directory / 'games' / r['slot_id'] / 'events.jsonl'
        if o is None or not events.exists():
            continue
        side = o['model_side']
        lines = [line for e in jsonl(events) if e['type'] == 'protocol' for line in e['protocol'].split('\n')]
        m = out.setdefault(model_of(r), dict(games=0, moves=0, failed=0, by_move={}, failed_games=0, loops=[]))
        m['games'] += 1
        streak, longest, last, any_failed = 0, (0, None), None, False
        for i, line in enumerate(lines):
            parts = line.split('|')
            if len(parts) < 4 or parts[1] != 'move' or not parts[2].startswith(side) or '[from]' in line:
                continue
            m['moves'] += 1
            entry = m['by_move'].setdefault(parts[3], [0, 0])
            entry[0] += 1
            if _failed_after(lines, i):
                m['failed'] += 1
                entry[1] += 1
                any_failed = True
                streak = streak + 1 if parts[3] == last else 1
                longest = max(longest, (streak, parts[3]), key=lambda x: x[0])
            else:
                streak = 0
            last = parts[3]
        m['failed_games'] += any_failed
        if longest[0] >= LOOP:
            m['loops'].append(dict(slot_id=r['slot_id'], move=longest[1], streak=longest[0], result=o.get('result')))
    for m in out.values():
        m['rate'] = m['failed'] / m['moves'] if m['moves'] else None
        m['top_failed'] = sorted(([k, v[1], v[0]] for k, v in m['by_move'].items() if v[1]), key=lambda x: (-x[1], x[0]))[:15]
        m['aurora_veil'] = dict(zip(('used', 'failed'), m['by_move'].get('Aurora Veil', [0, 0])))
        del m['by_move']
    return out


def _run(directory, rows, servings, device, hours, study=EX122):
    """`battle._run` with one owned serving per model (same ledger/claim/no-replay rules)."""
    from contextlib import nullcontext
    from .resources import gpu, port
    directory.mkdir(parents=True, exist_ok=True)
    ledger, games = directory / 'ledger.jsonl', directory / 'games'
    outcomes = [read(games / r['slot_id'] / 'outcome.json') for r in rows
                if (games / r['slot_id'] / 'outcome.json').exists()]
    claimed = {r['slot_id'] for r in rows if (games / r['slot_id']).exists()}
    if claimed - {o['slot_id'] for o in outcomes}:
        raise RuntimeError('a claimed slot has no outcome; it is not replayed: %s' % sorted(claimed))
    if not (directory / 'clock.json').exists():
        atomic(directory / 'clock.json', dict(first_started=time.time(), hours=hours), immutable=True)
    deadline = read(directory / 'clock.json')['first_started'] + hours * 3600
    latencies = {}
    for o in outcomes:
        latencies.setdefault(o['model'], []).extend(read(games / o['slot_id'] / 'audit.json')['inference_seconds'])
    error, owned = None, {}
    device_lock = gpu(*study.gpu) if device == 'cuda' else nullcontext((dict(CUDA_VISIBLE_DEVICES=''), None))
    with port(study.port), device_lock as (env, _):
        try:
            identities = {}
            for model, spec in servings.items():
                owned[model] = Serving(directory, spec['checkpoint'], model, device, render=RENDER[model])
                identities[model] = owned[model].start(env)
                if spec.get('sha') and identities[model]['checkpoint_sha256'] != spec['sha']:
                    raise RuntimeError('served checkpoint differs from the frozen one: ' + model)
                append_jsonl(ledger, dict(type='serving_started', identity=identities[model], at=time.time()))
            for row in rows:
                if row['slot_id'] in claimed:
                    continue
                if time.time() > deadline - CLEANUP_SECONDS:
                    append_jsonl(ledger, dict(type='admission_closed', reason='stage_time_limit', at=time.time()))
                    break
                model = row['model']
                append_jsonl(ledger, dict(type='slot_claim', slot_id=row['slot_id'], at=time.time()))
                outcome, audit = play_slot(games / row['slot_id'], row, identities[model],
                                           lambda m=model: owned[m].check(identities[m]['checkpoint_sha256']),
                                           port=study.port)
                outcomes.append(outcome)
                latencies.setdefault(model, []).extend(audit['inference_seconds'])
                append_jsonl(ledger, dict(type='slot_finished', outcome=outcome, at=time.time()))
                atomic(directory / 'status.json', dict(stage='running', done=len(outcomes), of=len(rows), at=time.time()))
                if outcome.get('failure_scope') == 'phase':
                    error = dict(type='phase_halt', slot_id=row['slot_id'], reason=outcome.get('error'))
                    break
        except BaseException as caught:
            error = dict(type=type(caught).__name__, detail=str(caught))
        finally:
            for serving in owned.values():
                serving.stop()
            append_jsonl(ledger, dict(type='closed', error=error, at=time.time()))
    return outcomes, latencies, error


# ----------------------------------------------------------------------------- stages

def _base_schedule():
    if verify_seal(COLLECTION):
        raise RuntimeError('EX-120 collection seal failed')
    return read(COLLECTION / 'schedule.json')


def mock(study=EX122):
    """First EX-120 pair with the v2 renderer and the untrained base checkpoint on CPU; outside every denominator."""
    base = _base_schedule()
    prefix = study.mock_model.split('-', 1)[1]
    pair = [dict(r, slot_id='%s-%s' % (prefix, r['slot_id']), model=study.mock_model) for r in base
            if r['pair_id'] == base[0]['pair_id']]
    directory = study.out / 'mock'
    if (directory / 'result.json').exists():
        raise RuntimeError('%s mock already completed' % study.experiment)
    outcomes, latencies, error = _run(directory, pair, {study.mock_model: dict(checkpoint=c.MODEL_DIR)}, 'cpu', 1.0,
                                      study)
    result = dict(outcomes=outcomes, latency=latencies, phase_error=error)
    atomic(directory / 'result.json', result, immutable=True)
    atomic(directory / 'manifest.json', dict(experiment_id=study.experiment + '-mock', schedule=pair), immutable=True)
    print(json.dumps(dict(games=[(o['slot_id'], o['status'], o.get('result'), o.get('audit_passed')) for o in outcomes],
                          error=error), ensure_ascii=False))


def prepare(study=EX122):
    from integration.project_context.registry import freeze_document, resolve_record
    from .serving import checkpoint_identity, renderer_matches_dataset
    out = study.out
    if (out / 'manifest.json').exists():
        raise RuntimeError('%s already prepared' % study.experiment)
    for name, run in study.runs.values():
        if read(run / 'status.json')['stage'] != 'completed' or verify_seal(run):
            raise RuntimeError('%s is not completed and sealed' % name)
    if not all(renderer_matches_dataset(RENDER[m]) for m in study.models):
        raise RuntimeError('a live renderer differs from its dataset generator')
    rows = make_schedule(_base_schedule(), study)
    freeze_document(resolve_record(study.experiment), out / 'protocol' / (study.experiment + '.md'))
    atomic(out / 'source/identity.json', source_identity(), immutable=True)
    collection = read(COLLECTION / 'manifest.json')
    servings = {}
    for model, (_, run) in study.runs.items():
        path = run / 'checkpoints/selected'
        servings[model] = dict(checkpoint=str(path), sha=checkpoint_identity(path), render=RENDER[model])
    manifest = dict(experiment_id=study.experiment, schedule=rows,
                    collection=dict(path=str(COLLECTION), schedule_sha256=collection['schedule_sha256']),
                    servings=servings, opponent='abyssal', port=study.port, gpu_uuid=study.gpu[1],
                    turn_limit=c.TURN_LIMIT, decision_limit=c.DECISION_LIMIT, battle_seconds=BATTLE_SECONDS,
                    stage_hours=study.hours, retries=0, fallback=0, requery=0,
                    probability_meaning='action_selection_probability', created_at=time.time())
    atomic(out / 'manifest.json', manifest, immutable=True)
    atomic(out / 'status.json', dict(stage='prepared', at=time.time()))
    print(json.dumps(dict(prepared=len(rows), servings={k: v['sha'] for k, v in servings.items()})))


def execute(study=EX122):
    out = study.out
    manifest = read(out / 'manifest.json')
    if (out / 'result.json').exists():
        raise RuntimeError('%s already executed' % study.experiment)
    if source_identity()['files'] != read(out / 'source/identity.json')['files']:
        raise RuntimeError('source changed after the %s freeze' % study.experiment)
    outcomes, latencies, error = _run(out, manifest['schedule'], manifest['servings'], 'cuda', study.hours, study)
    ex120 = read(c.RUN_GENERAL / 'result.json')['outcomes']
    summary = summarize_compare(manifest['schedule'], outcomes, latencies, ex120, study)
    overall = summarize(manifest['schedule'], outcomes, [x for v in latencies.values() for x in v], seed=study.seed)
    result = dict(overall, **summary,
                  verdict=verdict(summary, study) if summary['paired']['matchup_bootstrap_95'] else '판정 불가',
                  tera=tera_usage(out, manifest['schedule'], outcomes),
                  failed_moves=failed_moves(out, manifest['schedule'], outcomes),
                  outcomes=outcomes, phase_error=error,
                  all_slots_attempted=len(outcomes) == len(manifest['schedule']))
    atomic(out / 'result.json', result, immutable=True)
    atomic(out / 'status.json', dict(stage='executed', at=time.time(), verdict=result['verdict'],
                                     paired=summary['paired']))
    print(json.dumps(dict(verdict=result['verdict'], paired=summary['paired'],
                          models={k: (v['wins'], v['draws'], v['losses']) for k, v in summary['models'].items()},
                          tera={k: (v['tera_games'], v['games'], v['chosen'], v['available']) for k, v in result['tera'].items()},
                          replication=summary['v1_replication'], error=error), ensure_ascii=False))


def _columns(row):
    return [('모델', row['model']), ('조합', row['matchup_id']), ('시드', row['seed_index']),
            ('laya 팀 유형', row['archetypes']['model'])]


def export(study=EX122):
    from .compact import render as v1_render
    from .features import Calc
    from .reporting import compare_report
    from .serving import v2_renderer, v3_renderer, v4_renderer, v5_renderer, v6_renderer
    from .viewer import export as export_viewer
    out = study.out
    result = read(out / 'result.json')
    counts = ' · '.join('%s %d승 %d무 %d패' % (k, v['wins'], v['draws'], v['losses']) for k, v in result['models'].items())
    meta = dict(study.meta, intro=study.meta['intro'] + ' 모델별: ' + counts + '. 판정: ' + result['verdict'] + '.')
    with Calc() as calc:
        renderers = dict(v1=v1_render, v2=v2_renderer(calc), v3=v3_renderer(calc), v4=v4_renderer(calc),
                         v5=v5_renderer(calc))
        for name in {RENDER[m] for m in study.models} & {'v6s', 'v6h'}:
            renderers[name] = v6_renderer(name)(calc)
        viewer = export_viewer(out, study.viewer, meta=meta, columns=_columns,
                               renderer_for=lambda row: renderers[RENDER[row['model']]])
    compare_report(out, result, viewer, study)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(), verdict=result['verdict']))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(study.viewer / 'index.html'))))


def baseline_failed_moves():
    """The same failure count on EX-120 (EX-118 v1 model, same schedule) as the reference row."""
    manifest, result = read(c.RUN_GENERAL / 'manifest.json'), read(c.RUN_GENERAL / 'result.json')
    return failed_moves(c.RUN_GENERAL, manifest['schedule'], result['outcomes'], model_of=lambda r: 'EX-120 v1')


def mock2():
    mock(EX125)


def prepare2():
    prepare(EX125)


def execute2():
    execute(EX125)


def export2():
    export(EX125)


def mock3():
    mock(EX127)


def prepare3():
    prepare(EX127)


def execute3():
    execute(EX127)


def export3():
    export(EX127)


def mock4():
    mock(EX129)


def prepare4():
    prepare(EX129)


def execute4():
    execute(EX129)


def export4():
    export(EX129)


def mock5():
    mock(EX131)


def prepare5():
    prepare(EX131)


def execute5():
    execute(EX131)


def export5():
    export(EX131)


def mock6():
    mock(EX133)


def prepare6():
    prepare(EX133)


def execute6():
    execute(EX133)


def export6():
    export(EX133)


def mock7():
    mock(EX137)


def prepare7():
    prepare(EX137)


def execute7():
    execute(EX137)


def export7():
    export(EX137)


def mock10():
    mock(EX143)


def prepare10():
    prepare(EX143)


def execute10():
    execute(EX143)


def export10():
    export(EX143)


def mock11():
    mock(EX144)


def prepare11():
    prepare(EX144)


def execute11():
    execute(EX144)


def export11():
    export(EX144)
