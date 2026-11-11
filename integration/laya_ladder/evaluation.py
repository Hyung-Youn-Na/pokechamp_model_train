"""EX-167 evaluation (D-208): Tera knowledge held-out, both locked tests once, paired with EX-161 (v10t).

Report only (D-191). The EX-071 test pairs EX-167 with EX-161's own stored test rows; the ladder test (EX-166) has no
EX-161 rows, so EX-161 is scored on it here once (`test-ex161-ladder.jsonl`). Paired differences and the
probability-mass checks are `laya_v10.evaluation_v10`'s, with that module's dataset pointed at each test in turn.
"""
from __future__ import annotations
import json
import os
import time

from integration.laya_imitation.evaluation_tera import knowledge
from integration.laya_imitation.evaluation_v2 import _interval
from integration.laya_imitation.evaluation_v3 import paired
from integration.laya_imitation.resources import gpu
from integration.laya_imitation.storage import atomic, jsonl, read, seal, verify_seal
from integration.laya_v10 import evaluation_v10 as E, paths as p10, training_v10

from . import paths

SEED = 20261067
E.SEED = SEED


def _once(name, checkpoint, out, dataset):
    from integration.laya_imitation.evaluation import evaluate
    done = out / ('evaluation/completed-%s.json' % name)
    if done.exists():
        return read(done)['metrics']
    if (out / ('evaluation/reservation-%s.json' % name)).exists():
        raise RuntimeError('test %s was started but not completed; it is not re-run' % name)
    return evaluate(name, checkpoint, out, dataset=dataset, head_limit=paths.HEAD_LIMIT)


def _side(dataset, new_rows, base_rows):
    saved = p10.V10_DATASET
    p10.V10_DATASET = dataset
    try:
        info = E.row_info()
    finally:
        p10.V10_DATASET = saved
    pair_info = {k: {g: v[g] for g in E.GROUPS if g in v} | dict(replay_id=v['replay_id']) for k, v in info.items()}
    return dict(vs_ex161=E.compare(paired(new_rows, base_rows, pair_info)),
                fails=E.mass(new_rows, base_rows, info, 'fails'), danger=E.mass(new_rows, base_rows, info, 'danger'),
                repeat=E.mass(new_rows, base_rows, info, 'repeat'))


def run():
    out = paths.RUN_TRAINING
    checkpoint = out / 'checkpoints/selected'
    if read(out / 'status.json')['stage'] != 'trained':
        raise RuntimeError('EX-167 is not ready for evaluation: %r' % read(out / 'status.json'))
    if read(paths.V10_RUN / 'status.json')['stage'] != 'completed' or verify_seal(paths.V10_RUN):
        raise RuntimeError('EX-161 must be completed and sealed first')
    training_v10.install(paths.OPTION_LIMIT)
    (out / 'evaluation').mkdir(exist_ok=True)
    from .train_ddp import UUIDS
    with gpu(0, UUIDS[0]) as (env, _):
        os.environ.update(env)
        know = knowledge('ex167', checkpoint, out)
        tests = dict(ex071=_once('selected', checkpoint, out, paths.V10_DATASET),
                     ladder=_once('selected-ladder', checkpoint, out, paths.LADDER_ROWS),
                     ladder_ex161=_once('ex161-ladder', paths.V10_RUN / 'checkpoints/selected', out, paths.LADDER_ROWS))
    ex071 = _side(paths.V10_DATASET, list(jsonl(out / 'evaluation/test-selected.jsonl')),
                  list(jsonl(paths.V10_RUN / 'evaluation/test-selected.jsonl')))
    ladder = _side(paths.LADDER_ROWS, list(jsonl(out / 'evaluation/test-selected-ladder.jsonl')),
                   list(jsonl(out / 'evaluation/test-ex161-ladder.jsonl')))
    report = dict(at=time.time(), seed=SEED, tests=tests, ex161_test=read(paths.V10_RUN / 'evaluation/report.json')['test'],
                  knowledge=dict(ex161=read(paths.V10_RUN / 'evaluation/knowledge-ex161.json'), new=know),
                  ex071=ex071, ladder=ladder)
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    print(json.dumps(dict(ex071=ex071['vs_ex161']['all'], ladder=ladder['vs_ex161']['all']), ensure_ascii=False))
    return report


def _mass_row(name, d):
    if not d['rows']:
        return '| %s | 0 | - | - | - | - | - | - |' % name
    return '| %s | %d | %d | %.4f | %.4f | %s | %d | %d |' % (name, d['rows'], d['human_picked'], d['ex161_mass'],
                                                            d['ex149_mass'], _interval(d['diff_95']),
                                                            d['ex161_argmax'], d['ex149_argmax'])


def write_report(out, report):
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    merged = read(paths.MERGED / 'manifest.json')
    t = report['tests']
    lines = ['# EX-167 laya v10 + 최근 래더 자료 학습 보고', '',
             'EX-161(v10t)과 같은 시작 모델, 설정, 렌더러(v10)에서 학습 자료에 최근 래더 경기를 더했다(D-208). GPU 4장 '
             'DDP(장당 8 × 누적 2 × 4장 = 전체 배치 64). 사람 선택 재현이며 승률이 아니다. 이 보고는 배틀 진행 여부를 '
             '정하지 않는다(D-191).', '',
             '## 잠긴 test', '', '| test | 모델 | NLL | 일치율 | ECE |', '|---|---|---:|---:|---:|']
    for test, name, m in (('EX-071(대회)', 'EX-161 v10t', report['ex161_test']['all']),
                          ('EX-071(대회)', 'EX-167', t['ex071']['all']),
                          ('EX-166(래더)', 'EX-161 v10t', t['ladder_ex161']['all']),
                          ('EX-166(래더)', 'EX-167', t['ladder']['all'])):
        lines.append('| %s | %s | %.4f | %.2f%% | %.4f |' % (test, name, m['nll'], 100 * m['action_match_rate'], m['ece']))
    for key, title in (('ex071', 'EX-071 test(대회)'), ('ladder', 'EX-166 test(래더)')):
        cmp_ = report[key]['vs_ex161']
        lines += ['', '## 같은 행 차이: %s (EX-167 − EX-161, replay 클러스터 95%%, 시드 %d)' % (title, report['seed']), '',
                  '| 구분 | n | NLL 차이 | 95% | 일치율 차이 |', '|---|---:|---:|---|---:|',
                  E._row('전체', cmp_['all']), E._row('교체 행', cmp_['switch'])]
        for group, name in E.TITLES:
            for k, blk in cmp_[group].items():
                lines.append(E._row('%s %s' % (name, k), blk))
        lines += ['', '표시된 선택지의 확률 합(보고 전용):', '',
                  '| 선택지 | 행 | 사람이 고름 | EX-167 | EX-161 | 차이 95% | EX-167 argmax | EX-161 argmax |',
                  '|---|---:|---:|---:|---:|---|---:|---:|',
                  _mass_row('fails·likely fails', report[key]['fails']),
                  _mass_row('최악 %d%% 이상 교체' % E.DANGER, report[key]['danger']),
                  _mass_row('멈춘 streak의 같은 수', report[key]['repeat'])]
    k = report['knowledge']
    lines += ['', '## 테라 지식 held-out 정답률', '', '| 유형 | n | EX-161 | EX-167 |', '|---|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind in k['new'][part]:
            a, n = k['ex161'][part][kind], k['new'][part][kind]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% |' % (part, kind, n['n'], 100 * a['accuracy'], 100 * n['accuracy']))
    b = merged['budget']
    lines += ['', '## 학습', '',
              '- 학습 행 %d(EX-071 %d + 래더 %d + 테라 지식 %d), 보정 %d(합친 모방 행에서), validation %d(EX-071 512 + 래더 512)'
              % (split['train'], b['own_train'], b['ladder_rows'], split['extra_train'], split['calibration'],
                 split['validation']),
              '- 래더: 최신 %d경기(가장 오래된 업로드 %s), 예산 %d행(측정 %.4f초/행 × 길이 비 %.3f)' % (
                  b['ladder_games'], b['ladder_oldest_upload'], b['ladder_budget'], b['seconds_per_row_measured'],
                  b['length_ratio']), '',
              '| epoch | train loss | validation NLL(원 logit) | 일치율 | 경과(초) |', '|---:|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% | %s |' % (
            r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-', r['raw']['loss'],
            100 * r['raw']['accuracy'], r.get('seconds', '-')))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '', '## 해석 한계', '',
              '- 단일 시드 학습이다. 자료 양과 출처(래더)가 함께 바뀌었으므로 둘의 효과를 나눌 수 없다.',
              '- 래더 행의 미공개 세트는 추정값이다(D-208 결정 3).', '']
    (out / 'report.md').write_text('\n'.join(lines))
