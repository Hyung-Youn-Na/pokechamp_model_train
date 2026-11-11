"""EX-155 evaluation: Tera knowledge held-out, locked test once, paired with EX-149 (v7) and EX-152 (v8).

Report only (D-191). Same blocks as `evaluation_v8` (replay-cluster bootstrap, failure-mark groups, mass on confirmed
marks) plus the `likely` group: test rows whose v8l text has `; likely fails`, with the mass and argmax on those options
for EX-155, EX-152 and EX-149 (the latter two never saw the mark).
"""
from __future__ import annotations
import json
import os
import time

from integration.laya_imitation import config as c
from integration.laya_imitation.evaluation import evaluate
from integration.laya_imitation.evaluation_tera import knowledge, tera_metrics
from integration.laya_imitation.evaluation_v2 import _interval, cluster_interval
from integration.laya_imitation.evaluation_v3 import paired
from integration.laya_imitation.resources import gpu
from integration.laya_imitation.storage import atomic, jsonl, read, seal, verify_seal

from . import evaluation_v8 as e8
from .render_v8l import LIKELY_TEXT

SEED = 20261049


def likely_rows():
    return {r['sample_id']: {a for a, t in r['questions']['action']['criteria'].items() if t.endswith(LIKELY_TEXT)}
            for r in jsonl(c.V8L_DATASET / 'test.jsonl')}


def likely_mass(new_rows, others, likely):
    out = dict(rows=0, human_likely=0, ex155_mass=None, ex155_argmax=0)
    rows = [r for r in new_rows if likely.get(r['sample_id'])]
    mass = lambda row, m: sum(v for k, v in row['probabilities'].items() if k in m)
    out.update(rows=len(rows), human_likely=sum(r['label'] in likely[r['sample_id']] for r in rows),
               ex155_argmax=sum(r['choice'] in likely[r['sample_id']] for r in rows))
    if rows:
        out['ex155_mass'] = sum(mass(r, likely[r['sample_id']]) for r in rows) / len(rows)
    for name, base_rows in others.items():
        base = {r['sample_id']: r for r in base_rows}
        both = [(r, base[r['sample_id']]) for r in rows if r['sample_id'] in base]
        pairs = [dict(replay_id=r['sample_id'].rsplit(':', 3)[0],
                      d=mass(r, likely[r['sample_id']]) - mass(o, likely[r['sample_id']])) for r, o in both]
        out[name] = dict(n=len(both), mass=sum(mass(o, likely[r['sample_id']]) for r, o in both) / len(both)
                         if both else None, argmax=sum(o['choice'] in likely[r['sample_id']] for r, o in both),
                         diff_95=cluster_interval(pairs, 'd', seed=SEED) if pairs else None)
    return out


def run():
    out = c.RUN_V8L_TRAINING
    checkpoint = out / 'checkpoints/selected'
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-155 is not ready for evaluation: %r' % status)
    if read(c.RUN_V7_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_V7_TRAINING):
        raise RuntimeError('EX-149 must be completed and sealed first')
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(c.GPU2_INDEX, c.GPU2_UUID) as (env, _):
        os.environ.update(env)
        know = knowledge('ex155', checkpoint, out)
        done = out / 'evaluation/completed-selected.json'
        if done.exists():
            test = read(done)['metrics']
        elif (out / 'evaluation/reservation-selected.json').exists():
            raise RuntimeError('locked test was started but not completed; it is not re-run')
        else:
            test = evaluate('selected', checkpoint, out, dataset=c.V8L_DATASET, head_limit=c.V2_HEAD_LIMIT)
    info = e8.row_info()
    likely = likely_rows()
    for sid, v in info.items():
        v['likely'] = 'likely' if likely.get(sid) else 'none'
    replay_of = {k: v['replay_id'] for k, v in info.items()}
    new_rows = list(jsonl(out / 'evaluation/test-selected.jsonl'))
    others = {'EX-149': list(jsonl(c.RUN_V7_TRAINING / 'evaluation/test-selected.jsonl'))}
    v8_done = read(c.RUN_V8_TRAINING / 'status.json')['stage'] == 'completed' if \
        (c.RUN_V8_TRAINING / 'status.json').exists() else False
    if v8_done:
        others['EX-152'] = list(jsonl(c.RUN_V8_TRAINING / 'evaluation/test-selected.jsonl'))
    pair_info = {k: dict(replay_id=v['replay_id'], marks=v['marks'], likely=v['likely']) for k, v in info.items()}
    e8.GROUPS = e8.GROUPS + ('likely',) if 'likely' not in e8.GROUPS else e8.GROUPS
    e8.SEED = SEED
    report = dict(at=time.time(), seed=SEED, test=test, knowledge=dict(new=know),
                  vs={name: e8.compare(paired(new_rows, rows, pair_info)) for name, rows in others.items()},
                  fail_mass={name: e8.fail_mass(new_rows, rows, info) for name, rows in others.items()},
                  likely_mass=likely_mass(new_rows, others, likely),
                  tera={name: tera_metrics(new_rows, rows, replay_of) for name, rows in others.items()},
                  marks={s: v['marks'] for s, v in read(c.V8L_DATASET / 'coverage.json')['coverage'].items()},
                  baselines={'EX-149': read(c.RUN_V7_TRAINING / 'evaluation/report.json')['test']['all']})
    if v8_done:
        report['baselines']['EX-152'] = read(c.RUN_V8_TRAINING / 'evaluation/report.json')['test']['all']
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    print(json.dumps(dict(vs={k: v['all'] for k, v in report['vs'].items()}, likely=report['likely_mass']),
                     ensure_ascii=False))
    return report


def write_report(out, report):
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel = read(out / 'selection.json')
    lines = ['# EX-155 laya v8l(v8 + likely fails 표시) 학습 보고', '',
             'EX-152(v8)와 같은 설정에서 엔진 판정기의 확률 실패를 `; likely fails`로 더 표시했다. 사람 선택 재현이며 '
             '승률이 아니다(D-191).', '', '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|']
    for name, m in list(report['baselines'].items()) + [('EX-155 v8l', report['test']['all'])]:
        lines.append('| %s | %.4f | %.2f%% | %.4f |' % (name, m['nll'], 100 * m['action_match_rate'], m['ece']))
    for name, cmp_ in report['vs'].items():
        lines += ['', '## 같은 행 차이 (EX-155 − %s, replay 클러스터 95%%, 시드 %d)' % (name, report['seed']), '',
                  '| 구분 | n | NLL 차이 | 95% | 일치율 차이 |', '|---|---:|---:|---|---:|',
                  e8._row('전체', cmp_['all']), e8._row('교체 행', cmp_['switch'])]
        for group, title in (('by_likely', 'likely 표시'), ('by_marks', '실패 표시'), ('by_decision_kind', '결정')):
            for key, b in cmp_[group].items():
                lines.append(e8._row('%s %s' % (title, key), b))
    lm = report['likely_mass']
    lines += ['', '## likely fails 표시 행(test)', '',
              '- 행 %d, 사람이 표시된 수를 고른 행 %d, EX-155 확률 합 %s, argmax %d' % (
                  lm['rows'], lm['human_likely'], '%.4f' % lm['ex155_mass'] if lm['ex155_mass'] is not None else '-',
                  lm['ex155_argmax'])]
    for name in report['vs']:
        b = lm.get(name)
        if b and b['n']:
            lines.append('- %s: 확률 합 %.4f, argmax %d, 차이(EX-155 − %s) 95%% %s' % (
                name, b['mass'], b['argmax'], name, _interval(b['diff_95'])))
    lines += ['', '## 학습', '', '| epoch | validation NLL(원 logit) | 일치율 | 경과(초) |', '|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %.4f | %.2f%% | %s |' % (r['epoch'], r['raw']['loss'], 100 * r['raw']['accuracy'],
                                                    r.get('seconds', '-')))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '', '## 해석 한계', '',
              '- 단일 시드 학습이다. test의 likely 표시 행은 적다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
