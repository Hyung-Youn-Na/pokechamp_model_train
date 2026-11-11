"""EX-161 evaluation (D-204): Tera knowledge held-out, locked test once, paired with EX-149 (v7).

Report only (D-191, D-204 user decision 6): nothing here stops training, changes the method or decides whether EX-162
runs. Paired differences use the replay-cluster bootstrap overall, on switch rows, by label / decision kind, and by
which v10 marks the row carries (the per-information check metrics). Probability-mass metrics compare EX-161 with
EX-149 on the same test rows: options marked `fails` / `likely fails`, switch options whose worst plausible hit is at
least DANGER%, and the move a stalled `streak` repeats.
"""
from __future__ import annotations
import json
import os
import re
import time

from integration.laya_imitation import config as c
from integration.laya_imitation.evaluation_tera import knowledge, tera_metrics
from integration.laya_imitation.evaluation_v2 import _interval, cluster_interval
from integration.laya_imitation.evaluation_v3 import SWITCH_LABELS, paired
from integration.laya_imitation.resources import gpu
from integration.laya_imitation.storage import atomic, jsonl, read, seal, verify_seal

from . import data_v10, paths, training_v10

SEED = 20261062
DANGER = 80
RISK = re.compile(r'; risk (\d+)-(\d+)%')
STREAK = re.compile(r' \| streak (\w+) x\d+\+? \(opp hp ([\d>]+)\)')
GROUPS = ('label_kind', 'decision_kind', 'locks', 'locked', 'duel', 'wall', 'heals', 'pp', 'stalled')


def _stalled(state):
    """The repeated move of my active when the foe's HP did not fall over the streak, else None."""
    me = next((x for x in state.split('\n') if x.startswith('ME ')), '')
    m = STREAK.search(me)
    if not m:
        return None
    hp = [int(v) for v in m.group(2).split('>')]
    return m.group(1) if hp[-1] >= hp[0] - 5 else None


def row_info():
    info = {}
    for row in jsonl(paths.V10_DATASET / 'test.jsonl'):
        state, crit = row['state'], row['questions']['action']['criteria']
        lines = state.split('\n')
        duel = next((x for x in lines if x.startswith('duel: ')), None)
        stalled = _stalled(state)
        info[row['sample_id']] = dict(
            replay_id=row['sample_id'].rsplit(':', 3)[0],
            locks='locks' if any('; locks' in t for t in crit.values()) else 'none',
            locked='locked?' if any(' | locked? ' in x for x in lines) else
            'locked' if any(' | locked ' in x for x in lines) else 'none',
            duel=duel.rsplit('-> ', 1)[1] if duel else 'none',
            wall='wall' if any('; opp wall ' in t for t in crit.values()) else 'none',
            heals='heals' if any(x.startswith('opp heals: ') for x in lines) else 'none',
            pp='pp' if any(' used)' in x for x in lines if x.startswith('OPP ')) else 'none',
            stalled='stalled' if stalled else 'none',
            fails=sorted(a for a, t in crit.items() if '; fails' in t or '; likely fails' in t),
            danger=sorted(a for a, t in crit.items() if (m := RISK.search(t)) and int(m.group(2)) >= DANGER),
            repeat=sorted(a for a in crit if stalled and a.startswith('move:%s:' % stalled)))
    return info


def block(rows, key='nll'):
    n = len(rows)
    return dict(n=n, replays=len({r['replay_id'] for r in rows}),
                nll_diff=sum(r[key] for r in rows) / n if n else None,
                nll_diff_95=cluster_interval(rows, key, seed=SEED) if n else None,
                match_diff=sum(r['correct'] for r in rows) / n if n else None,
                match_diff_95=cluster_interval(rows, 'correct', seed=SEED) if n else None)


def compare(pairs):
    out = dict(all=block(pairs), switch=block([p for p in pairs if p['label_kind'] in SWITCH_LABELS]))
    for group in GROUPS:
        out['by_' + group] = {k: block([p for p in pairs if p[group] == k]) for k in sorted({p[group] for p in pairs})}
    return out


def mass(new_rows, base_rows, info, key):
    """Probability on the options `info[...][key]` lists, EX-161 vs EX-149 on the same rows."""
    base = {r['sample_id']: r for r in base_rows}
    rows = [(r, base[r['sample_id']], set(info[r['sample_id']][key])) for r in new_rows
            if r['sample_id'] in base and info.get(r['sample_id'], {}).get(key)]
    total = lambda row, m: sum(v for k, v in row['probabilities'].items() if k in m)
    pairs = [dict(replay_id=info[r['sample_id']]['replay_id'], d=total(r, m) - total(o, m)) for r, o, m in rows]
    return dict(rows=len(rows), human_picked=sum(r['label'] in m for r, _, m in rows),
                ex161_mass=sum(total(r, m) for r, _, m in rows) / len(rows) if rows else None,
                ex149_mass=sum(total(o, m) for _, o, m in rows) / len(rows) if rows else None,
                diff_95=cluster_interval(pairs, 'd', seed=SEED) if pairs else None,
                ex161_argmax=sum(r['choice'] in m for r, _, m in rows),
                ex149_argmax=sum(o['choice'] in m for _, o, m in rows))


def run():
    out = paths.RUN_V10_TRAINING
    checkpoint = out / 'checkpoints/selected'
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-161 is not ready for evaluation: %r' % status)
    if read(c.RUN_V7_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_V7_TRAINING):
        raise RuntimeError('EX-149 must be completed and sealed first')
    budget = data_v10.budget()
    training_v10.install(budget['option'])
    from integration.laya_imitation.evaluation import evaluate
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(*paths.GPU) as (env, _):
        os.environ.update(env)
        know = knowledge('ex161', checkpoint, out)
        done = out / 'evaluation/completed-selected.json'
        if done.exists():
            test = read(done)['metrics']
        elif (out / 'evaluation/reservation-selected.json').exists():
            raise RuntimeError('locked test was started but not completed; it is not re-run')
        else:
            test = evaluate('selected', checkpoint, out, dataset=paths.V10_DATASET, head_limit=budget['head'])
    info = row_info()
    replay_of = {k: v['replay_id'] for k, v in info.items()}
    new_rows = list(jsonl(out / 'evaluation/test-selected.jsonl'))
    base_rows = list(jsonl(c.RUN_V7_TRAINING / 'evaluation/test-selected.jsonl'))
    pair_info = {k: {g: v[g] for g in GROUPS if g in v} | dict(replay_id=v['replay_id']) for k, v in info.items()}
    data = read(paths.V10_DATASET / 'coverage.json')['coverage']
    report = dict(at=time.time(), seed=SEED, budget=budget, test=test,
                  ex149_test=read(c.RUN_V7_TRAINING / 'evaluation/report.json')['test'],
                  knowledge=dict(ex149=read(c.RUN_V7_TRAINING / 'evaluation/knowledge-ex149.json'), new=know),
                  vs_ex149=compare(paired(new_rows, base_rows, pair_info)),
                  fails=mass(new_rows, base_rows, info, 'fails'),
                  danger=mass(new_rows, base_rows, info, 'danger'),
                  repeat=mass(new_rows, base_rows, info, 'repeat'),
                  tera=tera_metrics(new_rows, base_rows, replay_of),
                  marks={s: data[s]['marks'] for s in data})
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    print(json.dumps(dict(vs_ex149=report['vs_ex149']['all'], fails=report['fails'], danger=report['danger'],
                          repeat=report['repeat']), ensure_ascii=False))
    return report


def _row(name, b):
    if not b['n']:
        return '| %s | 0 | - | - | - |' % name
    return '| %s | %d | %+.4f | %s | %+.2f%%p |' % (name, b['n'], b['nll_diff'], _interval(b['nll_diff_95']),
                                                  100 * b['match_diff'])


def _mass_row(name, d):
    if not d['rows']:
        return '| %s | 0 | - | - | - | - | - | - |' % name
    return '| %s | %d | %d | %.4f | %.4f | %s | %d | %d |' % (name, d['rows'], d['human_picked'], d['ex161_mass'],
                                                            d['ex149_mass'], _interval(d['diff_95']),
                                                            d['ex161_argmax'], d['ex149_argmax'])


TITLES = (('by_locks', 'lock 선택지'), ('by_locked', '고정 표시'), ('by_duel', '결투'), ('by_wall', '예상 교체'),
          ('by_heals', '상대 회복'), ('by_pp', '상대 PP'), ('by_stalled', '멈춘 반복'), ('by_label_kind', '라벨'),
          ('by_decision_kind', '결정'))


def write_report(out, report):
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    b = report['budget']
    lines = ['# EX-161 laya v10(정보 전부 + lock + 전략) 학습 보고', '',
             'EX-149(v7)과 같은 시작 모델, 설정, 테라 지식 행에서 입력만 v10으로 바꿨다(D-204: 전체 %d, head %d, '
             '선택지 %d토큰). 사람 선택 재현이며 승률이 아니다. 이 보고는 학습 중단, 방법 변경, 배틀 진행 여부를 '
             '정하지 않는다(D-191, D-204).' % (paths.TOKEN_LIMIT, b['head'], b['option']), '',
             '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|']
    for name, m in (('EX-149 v7', report['ex149_test']['all']), ('EX-161 v10', report['test']['all'])):
        lines.append('| %s | %.4f | %.2f%% | %.4f |' % (name, m['nll'], 100 * m['action_match_rate'], m['ece']))
    cmp_ = report['vs_ex149']
    lines += ['', '## 같은 행 차이 (EX-161 − EX-149, replay 클러스터 95%%, 시드 %d)' % report['seed'], '',
              '| 구분 | n | NLL 차이 | 95% | 일치율 차이 |', '|---|---:|---:|---|---:|',
              _row('전체', cmp_['all']), _row('교체 행', cmp_['switch'])]
    for group, title in TITLES:
        for name, blk in cmp_[group].items():
            lines.append(_row('%s %s' % (title, name), blk))
    lines += ['', '## 표시된 선택지의 확률 합(test, 보고 전용)', '',
              '| 선택지 | 행 | 사람이 고름 | EX-161 | EX-149 | 차이 95% | EX-161 argmax | EX-149 argmax |',
              '|---|---:|---:|---:|---:|---|---:|---:|',
              _mass_row('fails·likely fails', report['fails']),
              _mass_row('최악 %d%% 이상 교체' % DANGER, report['danger']),
              _mass_row('멈춘 streak의 같은 수', report['repeat'])]
    lines += ['', '## 자료의 표시(분할별)', '']
    keys = data_v10.MARKS + ('human_locks',)
    lines += ['| 분할 | ' + ' | '.join(keys) + ' |', '|---|' + '---:|' * len(keys)]
    for s, m in report['marks'].items():
        lines.append('| %s | %s |' % (s, ' | '.join(str(m[k]) for k in keys)))
    k = report['knowledge']
    lines += ['', '## 테라 지식 held-out 정답률', '', '| 유형 | n | EX-149 | EX-161 |', '|---|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind in k['new'][part]:
            a, n = k['ex149'][part][kind], k['new'][part][kind]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% |' % (part, kind, n['n'], 100 * a['accuracy'],
                                                              100 * n['accuracy']))
    lines += ['', '## 학습', '',
              '- 학습 행 %d(모방 %d + 테라 지식 %d), 보정 %d(모방만), validation %d' % (
                  split['train'], split['train'] - split['extra_train'], split['extra_train'], split['calibration'],
                  split['validation']), '',
              '| epoch | train loss | validation NLL(원 logit) | 일치율 | 경과(초) |', '|---:|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% | %s |' % (
            r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-', r['raw']['loss'],
            100 * r['raw']['accuracy'], r.get('seconds', '-')))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '', '## 해석 한계', '',
              '- 단일 시드 학습이다. 정보를 한꺼번에 넣었으므로 어떤 정보가 효과를 냈는지 나눌 수 없다.',
              '- 표시별 묶음은 그 표시가 있는 행이라는 뜻이며, 표시가 원인이라는 뜻이 아니다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
