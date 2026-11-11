"""EX-146 / EX-149 evaluation (D-200): Tera knowledge held-out, locked test once, paired with EX-141 (v6s+Tera).

Report only (D-191): nothing here decides whether EX-147 / EX-150 run. EX-141 test rows and knowledge results are read
from its sealed run. Paired differences use the replay-cluster bootstrap, broken down as in EX-141 (own streak) plus a
per-variant group: the loop kind of the row (`loop_weights.classify`) for v6sl, and the active foe's hidden slots and
`opp watch` line for v7. The repetition metric is EX-141's, also restricted to stalled-loop rows.
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
from .evaluation_v6 import STREAK, repeat_metrics
from .loop_weights import classify
from .resources import gpu
from .storage import atomic, jsonl, read, seal, verify_seal

VARIANTS = {
    'v6sl': dict(experiment='EX-146', key='ex146', run=c.RUN_V6SL_TRAINING, dataset=c.V6S_DATASET,
                 gpu=(c.GPU1_INDEX, c.GPU1_UUID), seed=20261037, title='v6s + 루프 탈출 행 가중'),
    'v7': dict(experiment='EX-149', key='ex149', run=c.RUN_V7_TRAINING, dataset=c.V7_DATASET,
               gpu=(c.GPU_INDEX, c.GPU_UUID), seed=20261040, title='v7 상대 세트 추정'),
}
GROUPS = ('label_kind', 'decision_kind', 'streak', 'extra')
OPPSET = re.compile(r'^opp set: (.*)$', re.M)


def _extra_v7(state):
    """'item?+moves<k>' style bucket of the active foe's hidden slots from the v7 text, plus '+watch'."""
    found = OPPSET.search(state)
    if found is None:
        return 'no-set-line'
    text = found.group(1)
    item = 'item?' if text.startswith('item ') or '; item ' in text else 'item-known'
    moves = len(re.findall(r'(?:likely moves |, )([a-z0-9]+) [.0-9]+', text))
    bucket = 'moves0' if moves == 0 else 'moves1-3' if moves <= 3 else 'moves4+'
    return '%s+%s%s' % (item, bucket, '+watch' if '\nopp watch: ' in state else '')


def row_groups(variant):
    info = {}
    for row in jsonl(VARIANTS[variant]['dataset'] / 'test.jsonl'):
        found = next((STREAK.match(x) for x in row['state'].split('\n') if STREAK.match(x)), None)
        extra = classify(row['state'], row['expected']['action']) if variant == 'v6sl' else _extra_v7(row['state'])
        info[row['sample_id']] = dict(replay_id=row['sample_id'].rsplit(':', 3)[0],
                                      streak='none' if found is None else 'x%s%s' % (min(int(found.group(2)), 4),
                                                                                     found.group(3)),
                                      streak_move=found.group(1) if found else None, extra=extra,
                                      loop=classify(row['state'], row['expected']['action']))
    return info


def block(rows, seed, key='nll'):
    n = len(rows)
    return dict(n=n, replays=len({r['replay_id'] for r in rows}),
                nll_diff=sum(r[key] for r in rows) / n if n else None,
                nll_diff_95=cluster_interval(rows, key, seed=seed),
                match_diff=sum(r['correct'] for r in rows) / n if n else None,
                match_diff_95=cluster_interval(rows, 'correct', seed=seed))


def compare(pairs, seed):
    out = dict(all=block(pairs, seed), switch=block([p for p in pairs if p['label_kind'] in SWITCH_LABELS], seed))
    for group in GROUPS:
        keys = sorted({p[group] for p in pairs})
        out['by_' + group] = {k: block([p for p in pairs if p[group] == k], seed) for k in keys}
    return out


def run(variant):
    spec = VARIANTS[variant]
    out = spec['run']
    checkpoint = out / 'checkpoints/selected'
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('%s is not ready for evaluation: %r' % (spec['experiment'], status))
    if read(c.RUN_V6S_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_V6S_TRAINING):
        raise RuntimeError('EX-141 must be completed and sealed first')
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
    info = row_groups(variant)
    replay_of = {k: v['replay_id'] for k, v in info.items()}
    new_rows = list(jsonl(out / 'evaluation/test-selected.jsonl'))
    base_rows = list(jsonl(c.RUN_V6S_TRAINING / 'evaluation/test-selected.jsonl'))
    pair_info = {k: {g: v[g] for g in ('replay_id', 'streak', 'extra')} for k, v in info.items()}
    stalled = {k: v for k, v in info.items() if v['loop'].startswith('stall')}
    report = dict(at=time.time(), seed=spec['seed'], variant=variant, test=test,
                  ex141_test=read(c.RUN_V6S_TRAINING / 'evaluation/report.json')['test'],
                  knowledge=dict(ex141=read(c.RUN_V6S_TRAINING / 'evaluation/knowledge-ex141.json'), new=know),
                  vs_ex141=compare(paired(new_rows, base_rows, pair_info), spec['seed']),
                  repeat=repeat_metrics(new_rows, base_rows, info),
                  repeat_stalled=repeat_metrics(new_rows, base_rows, stalled),
                  tera=tera_metrics(new_rows, base_rows, replay_of))
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report, spec)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    print(json.dumps(dict(variant=variant, vs_ex141=report['vs_ex141']['all'], repeat=report['repeat'],
                          repeat_stalled=report['repeat_stalled']), ensure_ascii=False))
    return report


def _row(name, b):
    if not b['n']:
        return '| %s | 0 | - | - | - |' % name
    return '| %s | %d | %+.4f | %s | %+.2f%%p |' % (name, b['n'], b['nll_diff'], _interval(b['nll_diff_95']),
                                                  100 * b['match_diff'])


def _repeat_table(lines, title, block_, experiment):
    lines += ['', '## %s' % title, '',
              '| 사람 선택 | n | EX-141 반복 확률 | %s 반복 확률 | EX-141 반복 1위 | %s 반복 1위 |' % (experiment, experiment),
              '|---|---:|---:|---:|---:|---:|']
    for human, b in sorted(block_.items()):
        lines.append('| %s | %d | %.4f | %.4f | %d | %d |' % ({'human_changed': '다른 수', 'human_repeated': '또 사용'}[human],
                                                            b['n'], b['old_mass'], b['new_mass'], b['old_top'],
                                                            b['new_top']))


def write_report(out, report, spec):
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    lines = ['# %s laya %s 학습 보고' % (spec['experiment'], spec['title']), '',
             'EX-141(v6s+테라)과 같은 시작 모델, 설정, 테라 지식 행에서 D-200의 한 가지만 바꿨다. '
             '사람 선택 재현이며 승률이 아니다. 이 보고는 배틀 진행 여부를 정하지 않는다(D-191).', '',
             '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|']
    for name, m in (('EX-141 v6s+테라', report['ex141_test']['all']), (spec['experiment'], report['test']['all'])):
        lines.append('| %s | %.4f | %.2f%% | %.4f |' % (name, m['nll'], 100 * m['action_match_rate'], m['ece']))
    cmp_ = report['vs_ex141']
    lines += ['', '## 같은 행 차이 (%s − EX-141, replay 클러스터 95%%, 시드 %d)' % (spec['experiment'], report['seed']), '',
              '| 구분 | n | NLL 차이 | 95% | 일치율 차이 |', '|---|---:|---:|---|---:|',
              _row('전체', cmp_['all']), _row('교체 행', cmp_['switch'])]
    extra_title = '루프 종류' if report['variant'] == 'v6sl' else '활성 상대 미공개'
    for group, title in (('by_streak', '내 활성 반복'), ('by_extra', extra_title), ('by_label_kind', '라벨'),
                         ('by_decision_kind', '결정')):
        for name, b in cmp_[group].items():
            lines.append(_row('%s %s' % (title, name), b))
    _repeat_table(lines, '같은 기술 반복 확률 (내 활성이 직전 2턴 이상 같은 기술을 쓴 test 행)', report['repeat'],
                  spec['experiment'])
    _repeat_table(lines, '같은 기술 반복 확률 (그중 상대 HP가 10%p 이상 줄지 않은 정체 행)', report['repeat_stalled'],
                  spec['experiment'])
    k = report['knowledge']
    lines += ['', '## 테라 지식 held-out 정답률', '', '| 유형 | n | EX-141 | %s |' % spec['experiment'],
              '|---|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind in k['new'][part]:
            a, d = k['ex141'][part][kind], k['new'][part][kind]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% |' % (part, kind, d['n'], 100 * a['accuracy'],
                                                              100 * d['accuracy']))
    lines += ['', '## 학습', '',
              '- 학습 행 %d(모방 %d + 테라 지식 %d), 보정 %d(모방만), validation %d' % (
                  split['train'], split['train'] - split['extra_train'], split['extra_train'], split['calibration'],
                  split['validation']), '',
              '| epoch | train loss | validation NLL(원 logit) | 일치율 | 경과(초) |', '|---:|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% | %s |' % (
            r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-', r['raw']['loss'],
            100 * r['raw']['accuracy'], r.get('seconds', '-')))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '', '## 해석 한계', '', '- 단일 시드 학습이다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
