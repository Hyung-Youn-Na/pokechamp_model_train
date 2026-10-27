"""EX-124 evaluation on GPU1: knowledge held-out (initial / EX-121 / EX-124), locked test once, Tera metrics vs EX-121.

EX-121 test values come from its stored `evaluation/test-selected.jsonl`; only the knowledge held-out rows are run
through EX-121 selected (once). Frozen judgement in the EX-124 protocol.
"""
from __future__ import annotations
import json
import os
import time

from . import config as c
from .evaluation import evaluate
from .evaluation_v2 import _interval, cluster_interval
from .resources import gpu
from .storage import atomic, jsonl, read, seal, verify_seal

SEED = 20261025
NLL_MARGIN = 0.02
CHECKPOINTS = {'initial': c.MODEL_DIR, 'ex121': c.RUN_V2_TRAINING / 'checkpoints/selected',
               'ex124': c.RUN_TERA_TRAINING / 'checkpoints/selected'}


def knowledge(name, path, out, dataset=c.TERA_KNOWLEDGE, parts=('heldout-A', 'heldout-B'), prefix='knowledge'):
    """Held-out knowledge accuracy by `meta.kind`, once per checkpoint (reservation file, no re-run)."""
    from .policy import Policy
    done = out / ('evaluation/%s-%s.json' % (prefix, name))
    if done.exists():
        return read(done)
    if (out / ('evaluation/%s-reservation-%s.json' % (prefix, name))).exists():
        raise RuntimeError('knowledge evaluation of %s was started but not completed; not re-run' % name)
    atomic(out / ('evaluation/%s-reservation-%s.json' % (prefix, name)), dict(at=time.time()), immutable=True)
    policy = Policy(path, head_limit=c.V2_HEAD_LIMIT)
    result = {}
    for part in parts:
        rows = list(jsonl(dataset / (part + '.jsonl')))
        logits = policy.logits([policy.item(r['state'], r['questions']['action']) for r in rows])
        by = {}
        for r, z in zip(rows, logits):
            ids = list(r['questions']['action']['criteria'])
            ok = ids[max(range(len(ids)), key=lambda i: z[i])] == r['expected']['action']
            k = by.setdefault(r['meta']['kind'], [0, 0])
            k[0] += ok
            k[1] += 1
        result[part] = {k: dict(correct=v[0], n=v[1], accuracy=v[0] / v[1]) for k, v in sorted(by.items())}
        result[part]['all'] = dict(correct=sum(v[0] for v in by.values()), n=sum(v[1] for v in by.values()))
        result[part]['all']['accuracy'] = result[part]['all']['correct'] / result[part]['all']['n']
    atomic(done, result, immutable=True)
    return result


def tera_mass(row):
    return sum(v for k, v in row['probabilities'].items() if k.endswith(':tera'))


def tera_metrics(new_rows, old_rows, replay_of):
    old = {r['sample_id']: r for r in old_rows}
    pairs, available = [], []
    for r in new_rows:
        o = old.get(r['sample_id'])
        if o is None:
            continue
        pairs.append(dict(replay_id=replay_of[r['sample_id']], nll=r['nll'] - o['nll']))
        if any(k.endswith(':tera') for k in r['probabilities']):
            human = r['label'].endswith(':tera')
            available.append(dict(replay_id=replay_of[r['sample_id']], human=human, new=tera_mass(r), old=tera_mass(o),
                                  new_top=r['choice'].endswith(':tera'), old_top=o['choice'].endswith(':tera'),
                                  d=tera_mass(r) - tera_mass(o)))
    human = [a for a in available if a['human']]
    other = [a for a in available if not a['human']]
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    return dict(
        nll_diff=mean([p['nll'] for p in pairs]), nll_diff_95=cluster_interval(pairs, 'nll', seed=SEED), paired_rows=len(pairs),
        tera_available=len(available), human_tera=len(human),
        tera_mass_human=dict(new=mean([a['new'] for a in human]), old=mean([a['old'] for a in human]),
                             diff=mean([a['d'] for a in human]), diff_95=cluster_interval(human, 'd', seed=SEED)),
        tera_mass_other=dict(new=mean([a['new'] for a in other]), old=mean([a['old'] for a in other])),
        tera_top=dict(new_on_human=sum(a['new_top'] for a in human), old_on_human=sum(a['old_top'] for a in human),
                      new_rate=mean([float(a['new_top']) for a in available]),
                      old_rate=mean([float(a['old_top']) for a in available]),
                      human_rate=len(human) / len(available) if available else None))


def verdict(m):
    low = m['tera_mass_human']['diff_95'][0]
    ok = m['nll_diff_95'][1] <= NLL_MARGIN
    if low > 0:
        return '테라 재현 개선, 일반 재현 유지' if ok else '테라 재현 개선, 일반 재현 저하'
    return '테라 재현 차이 불분명, 일반 재현 유지' if ok else '개선 없음'


def run():
    out = c.RUN_TERA_TRAINING
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-124 is not ready for evaluation: %r' % status)
    if read(c.RUN_V2_TRAINING / 'status.json')['stage'] != 'completed' or verify_seal(c.RUN_V2_TRAINING):
        raise RuntimeError('EX-121 must be completed and sealed first')
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(c.GPU1_INDEX, c.GPU1_UUID) as (env, _):
        os.environ.update(env)
        know = {name: knowledge(name, path, out) for name, path in CHECKPOINTS.items()}
        done = out / 'evaluation/completed-selected.json'
        if done.exists():
            test = read(done)['metrics']
        elif (out / 'evaluation/reservation-selected.json').exists():
            raise RuntimeError('locked test was started but not completed; it is not re-run')
        else:
            test = evaluate('selected', CHECKPOINTS['ex124'], out, dataset=c.V2_DATASET, head_limit=c.V2_HEAD_LIMIT)
    replay_of = {r['sample_id']: r['replay_id'] for r in jsonl(c.EX071_PREPARED / 'test.jsonl')}
    metrics = tera_metrics(list(jsonl(out / 'evaluation/test-selected.jsonl')),
                           list(jsonl(c.RUN_V2_TRAINING / 'evaluation/test-selected.jsonl')), replay_of)
    ex121 = read(c.RUN_V2_TRAINING / 'evaluation/report.json')['metrics']['selected']['all']
    report = dict(at=time.time(), knowledge=know, test=test, ex121_test=ex121, tera=metrics, verdict=verdict(metrics))
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    return report


def write_report(out, report):
    t, k = report['tera'], report['knowledge']
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    lines = ['# EX-124 laya v2 + 테라 기본 지식 학습 보고', '',
             'EX-121(v2)과 같은 시작 모델, 설정, 렌더러에서 학습 행에 테라 지식 행만 더했다(GPU1). '
             '사람 선택 재현과 지식 정답률이며 승률이 아니다.', '',
             '## 판정 (실행 전 동결)', '',
             '- 사람이 테라를 고른 test %d행의 테라 확률 합 차이(EX-124 − EX-121): %+.4f, 95%% %s' % (
                 t['human_tera'], t['tera_mass_human']['diff'], _interval(t['tera_mass_human']['diff_95'])),
             '- 전체 NLL 차이: %+.4f, 95%% %s (비열등 상한 +%.2f)' % (t['nll_diff'], _interval(t['nll_diff_95']), NLL_MARGIN),
             '- **%s**' % report['verdict'], '',
             '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|',
             '| EX-121 v2 | %.4f | %.2f%% | %.4f |' % (report['ex121_test']['nll'], 100 * report['ex121_test']['action_match_rate'],
                                                   report['ex121_test']['ece']),
             '| EX-124 v2+테라 | %.4f | %.2f%% | %.4f |' % (report['test']['all']['nll'],
                                                       100 * report['test']['all']['action_match_rate'],
                                                       report['test']['all']['ece']), '',
             '## 테라 지표 (판정 외 포함)', '',
             '| 지표 | EX-121 | EX-124 |', '|---|---:|---:|',
             '| 사람 테라 행의 테라 확률 합 평균 | %.4f | %.4f |' % (t['tera_mass_human']['old'], t['tera_mass_human']['new']),
             '| 비테라 행의 테라 확률 합 평균 | %.4f | %.4f |' % (t['tera_mass_other']['old'], t['tera_mass_other']['new']),
             '| 사람 테라 %d행 중 테라 1순위 | %d | %d |' % (t['human_tera'], t['tera_top']['old_on_human'],
                                                      t['tera_top']['new_on_human']),
             '| 테라 가능 %d행의 테라 1순위 비율 (사람 %.2f%%) | %.2f%% | %.2f%% |' % (
                 t['tera_available'], 100 * t['tera_top']['human_rate'], 100 * t['tera_top']['old_rate'],
                 100 * t['tera_top']['new_rate']), '',
             '## 지식 held-out 정답률', '', '| 유형 | n | initial | EX-121 | EX-124 |', '|---|---:|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind in k['ex124'][part]:
            row = [k[m][part][kind] for m in ('initial', 'ex121', 'ex124')]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% | %.1f%% |' % (part, kind, row[0]['n'],
                                                                     *[100 * r['accuracy'] for r in row]))
    lines += ['', '## 학습', '',
              '- 학습 행 %d(모방 %d + 지식 %d), 보정 %d(모방만), validation %d' % (
                  split['train'], split['train'] - split['extra_train'], split['extra_train'], split['calibration'],
                  split['validation']),
              '| epoch | train loss | validation NLL(원 logit) | 일치율 |', '|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% |' % (r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-',
                                                    r['raw']['loss'], 100 * r['raw']['accuracy']))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '',
              '## 해석 한계', '', '- 지식 행 추가로 학습량도 늘었다. 지식 효과와 분리하지 않았다.',
              '- 사람 테라 test 행이 적어 구간이 넓다.', '- 지식은 "무엇이 일어나는가"이며 전략 라벨이 없다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
