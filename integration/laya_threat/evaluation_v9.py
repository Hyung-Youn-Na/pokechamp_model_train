"""EX-157 evaluation (D-202): Tera knowledge held-out, locked test once, paired with EX-149 (v7).

Report only (D-191): nothing here decides whether EX-158 runs. Paired differences use the replay-cluster bootstrap,
by label / decision kind, by how v9 changed the row (`change`: spread fix, threat marks, both, none) and by whether the
human's choice carries a risk mark. The danger metric: on test rows whose v9 switch options include one marked with a
worst case of at least DANGER% (a plausible one-hit KO), the probability mass and argmax on those options for EX-157
and EX-149, and how often the human picked one.
"""
from __future__ import annotations
import json
import os
import re
import time

from integration.laya_imitation import config as c
from integration.laya_imitation.evaluation import evaluate
from integration.laya_imitation.evaluation_tera import knowledge, tera_metrics
from integration.laya_imitation.evaluation_v2 import _interval, cluster_interval
from integration.laya_imitation.evaluation_v3 import SWITCH_LABELS, paired
from integration.laya_imitation.resources import gpu
from integration.laya_imitation.storage import atomic, jsonl, read, seal, verify_seal

from . import paths

SEED = 20261052
GROUPS = ('label_kind', 'decision_kind', 'change', 'human_risk')
DANGER = 100
RISK = re.compile(r'; risk (\d+)-(\d+)%')


def strip(row):
    """The v9 row text without threat marks (state, criteria)."""
    state = '\n'.join(x for x in row['state'].split('\n') if not x.startswith('opp threat: '))
    crit = {a: re.sub(r'; risk [^;]*$', '', t) for a, t in row['questions']['action']['criteria'].items()}
    return state, crit


def danger(row):
    return {a for a, t in row['questions']['action']['criteria'].items()
            if (m := RISK.search(t)) and int(m.group(2)) >= DANGER}


def row_info():
    v9 = {r['sample_id']: r for r in jsonl(paths.V9_DATASET / 'test.jsonl')}
    v7 = {r['sample_id']: r for r in jsonl(c.V7_DATASET / 'test.jsonl')}
    info = {}
    for sid, row in v9.items():
        state, crit = strip(row)
        base = v7.get(sid)
        fixed = base is not None and (state, crit) != (base['state'], base['questions']['action']['criteria'])
        marked = state != row['state'] or crit != row['questions']['action']['criteria']
        change = 'both' if fixed and marked else 'spread fix' if fixed else 'threat' if marked else 'none'
        label = row['expected']['action']
        info[sid] = dict(replay_id=sid.rsplit(':', 3)[0], change=change,
                         human_risk='risk' if '; risk ' in row['questions']['action']['criteria'][label] else 'no risk',
                         danger=sorted(danger(row)))
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
        out['by_' + group] = {k: block([p for p in pairs if p[group] == k]) for k in sorted({p[group] for p in pairs})}
    return out


def danger_mass(new_rows, base_rows, info):
    base = {r['sample_id']: r for r in base_rows}
    rows = [(r, base[r['sample_id']], set(info[r['sample_id']]['danger'])) for r in new_rows
            if r['sample_id'] in base and info[r['sample_id']]['danger']]
    mass = lambda row, m: sum(v for k, v in row['probabilities'].items() if k in m)
    pairs = [dict(replay_id=info[r['sample_id']]['replay_id'], d=mass(r, m) - mass(o, m)) for r, o, m in rows]
    return dict(rows=len(rows), human_picked=sum(r['label'] in m for r, _, m in rows),
                ex157_mass=sum(mass(r, m) for r, _, m in rows) / len(rows) if rows else None,
                ex149_mass=sum(mass(o, m) for _, o, m in rows) / len(rows) if rows else None,
                diff_95=cluster_interval(pairs, 'd', seed=SEED) if pairs else None,
                ex157_argmax=sum(r['choice'] in m for r, _, m in rows),
                ex149_argmax=sum(o['choice'] in m for _, o, m in rows))


def run():
    out = paths.RUN_V9_TRAINING
    checkpoint = out / 'checkpoints/selected'
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-157 is not ready for evaluation: %r' % status)
    if read(c.RUN_V7_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_V7_TRAINING):
        raise RuntimeError('EX-149 must be completed and sealed first')
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(*paths.GPU) as (env, _):
        os.environ.update(env)
        know = knowledge('ex157', checkpoint, out)
        done = out / 'evaluation/completed-selected.json'
        if done.exists():
            test = read(done)['metrics']
        elif (out / 'evaluation/reservation-selected.json').exists():
            raise RuntimeError('locked test was started but not completed; it is not re-run')
        else:
            test = evaluate('selected', checkpoint, out, dataset=paths.V9_DATASET, head_limit=c.V2_HEAD_LIMIT)
    info = row_info()
    replay_of = {k: v['replay_id'] for k, v in info.items()}
    new_rows = list(jsonl(out / 'evaluation/test-selected.jsonl'))
    base_rows = list(jsonl(c.RUN_V7_TRAINING / 'evaluation/test-selected.jsonl'))
    pair_info = {k: dict(replay_id=v['replay_id'], change=v['change'], human_risk=v['human_risk'])
                 for k, v in info.items()}
    data = read(paths.V9_DATASET / 'coverage.json')['coverage']
    report = dict(at=time.time(), seed=SEED, test=test,
                  ex149_test=read(c.RUN_V7_TRAINING / 'evaluation/report.json')['test'],
                  knowledge=dict(ex149=read(c.RUN_V7_TRAINING / 'evaluation/knowledge-ex149.json'), new=know),
                  vs_ex149=compare(paired(new_rows, base_rows, pair_info)),
                  danger=danger_mass(new_rows, base_rows, info),
                  tera=tera_metrics(new_rows, base_rows, replay_of),
                  marks={s: data[s]['marks'] for s in data})
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    print(json.dumps(dict(vs_ex149=report['vs_ex149']['all'], danger=report['danger']), ensure_ascii=False))
    return report


def _row(name, b):
    if not b['n']:
        return '| %s | 0 | - | - | - |' % name
    return '| %s | %d | %+.4f | %s | %+.2f%%p |' % (name, b['n'], b['nll_diff'], _interval(b['nll_diff_95']),
                                                  100 * b['match_diff'])


def write_report(out, report):
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    lines = ['# EX-157 laya v9 상대 위협 표시 학습 보고', '',
             'EX-149(v7)과 같은 시작 모델, 설정, 테라 지식 행에서 입력만 v9로 바꿨다(D-202: 상대 노력치 보정, '
             '`risk`·`opp threat` 표시). 사람 선택 재현이며 승률이 아니다. 이 보고는 배틀 진행 여부를 정하지 않는다(D-191).', '',
             '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|']
    for name, m in (('EX-149 v7', report['ex149_test']['all']), ('EX-157 v9', report['test']['all'])):
        lines.append('| %s | %.4f | %.2f%% | %.4f |' % (name, m['nll'], 100 * m['action_match_rate'], m['ece']))
    cmp_ = report['vs_ex149']
    lines += ['', '## 같은 행 차이 (EX-157 − EX-149, replay 클러스터 95%%, 시드 %d)' % report['seed'], '',
              '| 구분 | n | NLL 차이 | 95% | 일치율 차이 |', '|---|---:|---:|---|---:|',
              _row('전체', cmp_['all']), _row('교체 행', cmp_['switch'])]
    for group, title in (('by_change', '변화'), ('by_human_risk', '사람 선택'), ('by_label_kind', '라벨'),
                         ('by_decision_kind', '결정')):
        for name, b in cmp_[group].items():
            lines.append(_row('%s %s' % (title, name), b))
    d = report['danger']
    lines += ['', '## 최악 %d%% 이상 교체 선택지(test)' % DANGER, '',
              '| 행 | 사람이 고름 | EX-157 확률 합 | EX-149 확률 합 | 차이 95% | EX-157 argmax | EX-149 argmax |',
              '|---:|---:|---:|---:|---|---:|---:|']
    if d['rows']:
        lines.append('| %d | %d | %.4f | %.4f | %s | %d | %d |' % (d['rows'], d['human_picked'], d['ex157_mass'],
                                                                 d['ex149_mass'], _interval(d['diff_95']),
                                                                 d['ex157_argmax'], d['ex149_argmax']))
    lines += ['', '## 자료의 표시(분할별)', '',
              '| 분할 | 노력치 보정 행 | 보정으로 바뀐 행 | threat 줄 | risk 선택지 | risk 행 | 사람이 risk 선택지 | 바뀐 행 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s, m in report['marks'].items():
        lines.append('| %s | %d | %d | %d | %d | %d | %d | %d |' % (
            s, m['spread_fixed'], m['fix_changed'], m['threat_line'], m['risk_options'], m['risk_row'],
            m['human_risk'], m['changed']))
    k = report['knowledge']
    lines += ['', '## 테라 지식 held-out 정답률', '', '| 유형 | n | EX-149 | EX-157 |', '|---|---:|---:|---:|']
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
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '', '## 해석 한계', '', '- 단일 시드 학습이다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
