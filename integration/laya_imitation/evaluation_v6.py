"""EX-141 / EX-142 evaluation (D-198): Tera knowledge held-out, locked test once, paired with EX-136 (v5+Tera).

Report only (D-191): nothing here decides whether EX-143 / EX-144 run. EX-136 test rows and knowledge results are read
from its sealed run. Paired differences use the replay-cluster bootstrap (seed 20261036), broken down by decision and
label kind, by whether the v6s text shows a streak on the own active Pokemon, and (both variants) by how many history
turns the v6h text carries. The repetition metric: on test rows whose own active Pokemon used the same move in the
last n >= 2 turns, the probability each model puts on that move again, split by whether the human repeated it.
"""
from __future__ import annotations
import json
import os
import re
import time

from . import config as c
from .evaluation import evaluate
from .evaluation_tera import knowledge, tera_metrics
from .evaluation_v2 import _interval, cluster_interval
from .evaluation_v3 import SWITCH_LABELS, paired
from .resources import gpu
from .storage import atomic, jsonl, read, seal, verify_seal

SEED = 20261036
VARIANTS = {
    'v6s': dict(experiment='EX-141', key='ex141', run=c.RUN_V6S_TRAINING, dataset=c.V6S_DATASET,
                gpu=(c.GPU_INDEX, c.GPU_UUID), title='v6s 반복 표시(streak)'),
    'v6h': dict(experiment='EX-142', key='ex142', run=c.RUN_V6H_TRAINING, dataset=c.V6H_DATASET,
                gpu=(c.GPU1_INDEX, c.GPU1_UUID), title='v6h 긴 기록(2048토큰)'),
}
GROUPS = ('label_kind', 'decision_kind', 'streak', 'history')
STREAK = re.compile(r'^ME .* \| streak ([a-z0-9]+) x(\d+)(\+?)')


def history_bucket(n):
    return '0-2' if n <= 2 else '3-8' if n <= 8 else '9-20' if n <= 20 else '21+'


def row_groups():
    """Per test row: the v6s own streak (move, n) and the v6h history-turn bucket, from the sealed datasets."""
    info = {}
    for row in jsonl(c.V6S_DATASET / 'test.jsonl'):
        found = next((STREAK.match(x) for x in row['state'].split('\n') if STREAK.match(x)), None)
        info[row['sample_id']] = dict(replay_id=row['sample_id'].rsplit(':', 3)[0],
                                      streak='none' if found is None else 'x%s%s' % (min(int(found.group(2)), 4),
                                                                                     found.group(3)),
                                      streak_move=found.group(1) if found else None, history='excluded')
    for row in jsonl(c.V6H_DATASET / 'test.jsonl'):
        if row['sample_id'] in info:
            turns = sum(1 for x in row['state'].split('\n') if re.match(r'^T\d+: ', x))
            info[row['sample_id']]['history'] = history_bucket(turns)
    return info


def block(rows, key='nll'):
    n = len(rows)
    return dict(n=n, replays=len({r['replay_id'] for r in rows}),
                nll_diff=sum(r[key] for r in rows) / n if n else None,
                nll_diff_95=cluster_interval(rows, key, seed=SEED),
                match_diff=sum(r['correct'] for r in rows) / n if n else None,
                match_diff_95=cluster_interval(rows, 'correct', seed=SEED))


def compare(pairs):
    out = dict(all=block(pairs), switch=block([p for p in pairs if p['label_kind'] in SWITCH_LABELS]))
    for group in GROUPS:
        keys = sorted({p[group] for p in pairs})
        out['by_' + group] = {k: block([p for p in pairs if p[group] == k]) for k in keys}
    return out


def repeat_metrics(new_rows, old_rows, info):
    """Mean probability on repeating the streak move (normal + Tera), by whether the human repeated it."""
    old = {r['sample_id']: r for r in old_rows}
    out = {}
    for r in new_rows:
        g = info.get(r['sample_id'])
        o = old.get(r['sample_id'])
        if not g or not g['streak_move'] or o is None:
            continue
        ids = ('move:%s:normal' % g['streak_move'], 'move:%s:tera' % g['streak_move'])
        if not any(i in r['probabilities'] for i in ids):
            continue
        human = 'human_repeated' if r['label'] in ids else 'human_changed'
        mass = lambda p: sum(p.get(i, 0.0) for i in ids)
        top = lambda row: row['choice'] in ids
        b = out.setdefault(human, dict(n=0, new_mass=0.0, old_mass=0.0, new_top=0, old_top=0))
        b['n'] += 1
        b['new_mass'] += mass(r['probabilities'])
        b['old_mass'] += mass(o['probabilities'])
        b['new_top'] += top(r)
        b['old_top'] += top(o)
    for b in out.values():
        b['new_mass'] /= b['n']
        b['old_mass'] /= b['n']
    return out


def run(variant):
    spec = VARIANTS[variant]
    out = spec['run']
    checkpoint = out / 'checkpoints/selected'
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('%s is not ready for evaluation: %r' % (spec['experiment'], status))
    if read(c.RUN_V5_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_V5_TRAINING):
        raise RuntimeError('EX-136 must be completed and sealed first')
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(*spec['gpu']) as (env, _):
        os.environ.update(env)
        know = knowledge(spec['key'], checkpoint, out)
        done = out / 'evaluation/completed-selected.json'
        if done.exists():
            test = read(done)['metrics']
        elif (out / 'evaluation/reservation-selected.json').exists():
            raise RuntimeError('locked test was started but not completed; it is not re-run')
        else:
            test = evaluate('selected', checkpoint, out, dataset=spec['dataset'], head_limit=c.V2_HEAD_LIMIT)
    info = row_groups()
    replay_of = {k: v['replay_id'] for k, v in info.items()}
    new_rows = list(jsonl(out / 'evaluation/test-selected.jsonl'))
    v5_rows = list(jsonl(c.RUN_V5_TRAINING / 'evaluation/test-selected.jsonl'))
    pair_info = {k: {g: v[g] for g in ('replay_id', 'streak', 'history')} for k, v in info.items()}
    report = dict(at=time.time(), seed=SEED, variant=variant, test=test,
                  ex136_test=read(c.RUN_V5_TRAINING / 'evaluation/report.json')['test'],
                  knowledge=dict(ex136=read(c.RUN_V5_TRAINING / 'evaluation/knowledge-ex136.json'), new=know),
                  vs_ex136=compare(paired(new_rows, v5_rows, pair_info)),
                  repeat=repeat_metrics(new_rows, v5_rows, info),
                  tera=tera_metrics(new_rows, v5_rows, replay_of))
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report, spec)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    print(json.dumps(dict(variant=variant, vs_ex136=report['vs_ex136']['all'], repeat=report['repeat']),
                     ensure_ascii=False))
    return report


def _row(name, b):
    if not b['n']:
        return '| %s | 0 | - | - | - |' % name
    return '| %s | %d | %+.4f | %s | %+.2f%%p |' % (name, b['n'], b['nll_diff'], _interval(b['nll_diff_95']),
                                                  100 * b['match_diff'])


def write_report(out, report, spec):
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    data = read(spec['dataset'] / 'validation.json')
    lines = ['# %s laya %s + 테라 지식 학습 보고' % (spec['experiment'], spec['title']), '',
             'EX-136(v5+테라)과 같은 시작 모델, 설정, 테라 지식 행에서 행동 행의 렌더러만 바꿨다(D-198). '
             '사람 선택 재현이며 승률이 아니다. 이 보고는 배틀 진행 여부를 정하지 않는다(D-191).', '',
             '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|']
    for name, m in (('EX-136 v5+테라', report['ex136_test']['all']), (spec['experiment'], report['test']['all'])):
        lines.append('| %s | %.4f | %.2f%% | %.4f |' % (name, m['nll'], 100 * m['action_match_rate'], m['ece']))
    cmp_ = report['vs_ex136']
    lines += ['', '## 같은 행 차이 (%s − EX-136, replay 클러스터 95%%, 시드 %d)' % (spec['experiment'], report['seed']), '',
              '| 구분 | n | NLL 차이 | 95% | 일치율 차이 |', '|---|---:|---:|---|---:|',
              _row('전체', cmp_['all']), _row('교체 행', cmp_['switch'])]
    for group, title in (('by_streak', '내 활성 반복'), ('by_history', 'v6h 기록 턴 수'), ('by_label_kind', '라벨'),
                         ('by_decision_kind', '결정')):
        for name, b in cmp_[group].items():
            lines.append(_row('%s %s' % (title, name), b))
    lines += ['', '## 같은 기술 반복 확률 (내 활성이 직전 2턴 이상 같은 기술을 쓴 test 행)', '',
              '| 사람 선택 | n | EX-136 반복 확률 | %s 반복 확률 | EX-136 반복 1위 | %s 반복 1위 |' % (
                  spec['experiment'], spec['experiment']), '|---|---:|---:|---:|---:|---:|']
    for human, b in sorted(report['repeat'].items()):
        lines.append('| %s | %d | %.4f | %.4f | %d | %d |' % ({'human_changed': '다른 수', 'human_repeated': '또 사용'}[human],
                                                            b['n'], b['old_mass'], b['new_mass'], b['old_top'],
                                                            b['new_top']))
    k = report['knowledge']
    lines += ['', '## 테라 지식 held-out 정답률', '', '| 유형 | n | EX-136 | %s |' % spec['experiment'],
              '|---|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind in k['new'][part]:
            a, d = k['ex136'][part][kind], k['new'][part][kind]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% |' % (part, kind, d['n'], 100 * a['accuracy'],
                                                              100 * d['accuracy']))
    lines += ['', '## 자료와 학습', '',
              '- 길이 제외 %d행(비율 %.4f)' % (data['token_budget_exclusions'], data['exclusion_rate']),
              '- 학습 행 %d(모방 %d + 테라 지식 %d), 보정 %d(모방만), validation %d' % (
                  split['train'], split['train'] - split['extra_train'], split['extra_train'], split['calibration'],
                  split['validation']), '',
              '| epoch | train loss | validation NLL(원 logit) | 일치율 | 경과(초) |', '|---:|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% | %s |' % (
            r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-', r['raw']['loss'],
            100 * r['raw']['accuracy'], r.get('seconds', '-')))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '', '## 해석 한계', '',
              '- 반복 표시는 4턴 기록에서 센 값이라 그보다 긴 연속은 `x4+`로만 보인다.',
              '- v6h는 입력 길이 한도(1024→2048)와 기록 창을 함께 바꿨다. 기록이 짧은 행은 한도만 다르다.',
              '- 단일 시드 학습이다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
