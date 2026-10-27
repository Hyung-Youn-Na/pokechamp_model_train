"""EX-136 evaluation on GPU0 (D-195): Tera knowledge held-out, locked test once, paired with EX-130 and EX-124.

Report only (D-191): nothing here decides whether EX-137 / EX-138 run. EX-130 / EX-124 test rows and knowledge results
are read from their sealed runs. Paired differences use the replay-cluster bootstrap (seed 20261032), broken down by
the active foe's item state, the Air Balloon cases and the status/turn counters on the actives. The NHJ human-game
probe re-infers the 132 fixed decisions with v2t / v4t (recorded inputs) and v5t (the same prefixes re-parsed).
"""
from __future__ import annotations
import json
import os
import time

from integration.pokechamp.imitation.schema import ImitationInput

from . import config as c
from .data_v5 import _rows, merged
from .evaluation import evaluate
from .evaluation_effects import fail_metrics
from .evaluation_tera import knowledge, tera_metrics
from .evaluation_v2 import _interval, cluster_interval
from .evaluation_v3 import SWITCH_LABELS, paired
from .features_v4 import known_failures
from .features_v5 import resolved
from .resources import gpu
from .storage import atomic, jsonl, read, seal, verify_seal

SEED = 20261032
CHECKPOINT = c.RUN_V5_TRAINING / 'checkpoints/selected'
PROBE = c.RUN_V5_TRAINING / 'diagnostics/nhj-probe-inputs.json'
GROUND = ('earthquake', 'headlongrush', 'earthpower', 'precipiceblades', 'highhorsepower', 'stompingtantrum',
          'bulldoze', 'scorchingsands', 'drillrun', 'sandsearstorm', 'thousandarrows', 'mudshot')
GROUPS = ('label_kind', 'decision_kind', 'foe_item', 'foe_balloon', 'counter')


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


def row_info(value):
    """Item-state / counter groups of one merged v5 input, its v5-visible failures and its ground options."""
    view_value, view = resolved(value)
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me = own.get(view['own_active_slot']) if view['own_active_slot'] else None
    foe = opp.get(view['opponent_active_slot']) if view['opponent_active_slot'] else None
    held = foe['item_state'] if foe else None
    item = 'no_foe' if held is None else held['state'] + (':' + held['cause'] if held['cause'] else '')
    balloon = 'held' if held and held['state'] == 'held' and held['item'] == 'airballoon' else \
        'removed' if held and held['state'] == 'removed' and held['item'] == 'airballoon' else 'other'
    counters = sorted({m['status'] for m in (me, foe) if m and m.get('status_counter') is not None})
    counter = '+'.join(counters) or ('turns' if view['weather'] or view['field'] or any(
        k in ('reflect', 'light_screen', 'aurora_veil', 'tailwind')
        for side in ('own_side_conditions', 'opponent_side_conditions') for k in view[side]) else 'none')
    ground = [a for a in value.action_ids if a.startswith('move:') and a.split(':')[1] in GROUND]
    return dict(foe_item=item, foe_balloon=balloon, counter=counter), sorted(known_failures(view_value)), ground


def ground_metrics(models, info, ground):
    """Rows whose active foe holds an Air Balloon and that offer ground moves: ground mass and top-1 per model."""
    rows = [s for s in info if info[s]['foe_balloon'] == 'held' and ground.get(s)]
    out = dict(rows=len(rows), human_chose_ground=None)
    for name, preds in models.items():
        have = [s for s in rows if s in preds]
        out[name] = dict(n=len(have), ground_mass=sum(sum(preds[s]['probabilities'].get(a, 0.0) for a in ground[s])
                                                      for s in have) / len(have) if have else None,
                         ground_top=sum(preds[s]['choice'] in ground[s] for s in have))
        if out['human_chose_ground'] is None and have:
            out['human_chose_ground'] = sum(preds[s]['label'] in ground[s] for s in have)
    return out


def probe(calc):
    """NHJ decisions: v2t / v4t on the recorded inputs, v5t on the re-parsed ones (GPU env already set)."""
    from .policy import Policy
    from .serving import v2_renderer, v4_renderer, v5_renderer
    doc = read(PROBE)
    models = {'v2t': (c.RUN_TERA_TRAINING, v2_renderer(calc), 'recorded'),
              'v4t': (c.RUN_V4_TRAINING, v4_renderer(calc), 'recorded'),
              'v5t': (c.RUN_V5_TRAINING, v5_renderer(calc), 'reparsed')}
    rows = [dict(game=d['game'], turn=d['turn'], decision=d['decision']) for d in doc['decisions']]
    for name, (run, renderer, field) in models.items():
        policy = Policy(run / 'checkpoints/selected', device='cuda', head_limit=c.V2_HEAD_LIMIT, renderer=renderer)
        for row, d in zip(rows, doc['decisions']):
            out = policy.predict(ImitationInput.from_body(d[field]))
            row[name] = dict(choice=max(out['probabilities'], key=out['probabilities'].get),
                             probabilities=out['probabilities'])
        del policy
    balloon = []
    for row, d in zip(rows, doc['decisions']):
        snapshot = json.loads(d['reparsed']['state'])['snapshot']
        foe = {m['slot']: m for m in snapshot['opponent_team']}.get(snapshot['opponent_active_slot'])
        ground = [a for a in row['v2t']['probabilities'] if a.startswith('move:') and a.split(':')[1] in GROUND]
        if foe and foe['item_state'] == dict(state='held', item='airballoon', cause=None) and ground \
                and snapshot['decision_kind'] == 'turn_action':
            balloon.append(dict(game=row['game'], turn=row['turn'], **{
                m: dict(choice=row[m]['choice'], ground_mass=sum(row[m]['probabilities'].get(a, 0.0) for a in ground),
                        icespinner=row[m]['probabilities'].get('move:icespinner:normal'))
                for m in models}))
    summary = dict(decisions=len(rows), balloon_ground_decisions=len(balloon),
                   ground_top={m: sum(b[m]['choice'].split(':')[1] in GROUND for b in balloon
                                      if b[m]['choice'].startswith('move:')) for m in models},
                   changed_vs_v2t={m: sum(r[m]['choice'] != r['v2t']['choice'] for r in rows) for m in ('v4t', 'v5t')})
    return dict(summary=summary, balloon=balloon, rows=rows)


def run():
    out = c.RUN_V5_TRAINING
    status = read(out / 'status.json')
    if status['stage'] != 'trained':
        raise RuntimeError('EX-136 is not ready for evaluation: %r' % status)
    for name, run_ in (('EX-130', c.RUN_V4_TRAINING), ('EX-124', c.RUN_TERA_TRAINING)):
        if read(run_ / 'status.json')['stage'] != 'completed' or verify_seal(run_):
            raise RuntimeError('%s must be completed and sealed first' % name)
    (out / 'evaluation').mkdir(exist_ok=True)
    with gpu(c.GPU_INDEX, c.GPU_UUID) as (env, _):
        os.environ.update(env)
        know = knowledge('ex136', CHECKPOINT, out)
        done = out / 'evaluation/completed-selected.json'
        if done.exists():
            test = read(done)['metrics']
        elif (out / 'evaluation/reservation-selected.json').exists():
            raise RuntimeError('locked test was started but not completed; it is not re-run')
        else:
            test = evaluate('selected', CHECKPOINT, out, dataset=c.V5_DATASET, head_limit=c.V2_HEAD_LIMIT)
        probe_path = out / 'evaluation/nhj-probe.json'
        if not probe_path.exists():
            from .features import Calc
            with Calc() as calc:
                atomic(probe_path, probe(calc), immutable=True)
        nhj = read(probe_path)
    info, failing, ground = {}, {}, {}
    for record, extra in _rows('test'):
        groups, bad, grd = row_info(merged(record, extra))
        info[record['sample_id']] = dict(replay_id=record['replay_id'], **groups)
        if bad:
            failing[record['sample_id']] = bad
        if grd:
            ground[record['sample_id']] = grd
    replay_of = {k: v['replay_id'] for k, v in info.items()}
    new_rows = list(jsonl(out / 'evaluation/test-selected.jsonl'))
    v4_rows = list(jsonl(c.RUN_V4_TRAINING / 'evaluation/test-selected.jsonl'))
    v2_rows = list(jsonl(c.RUN_TERA_TRAINING / 'evaluation/test-selected.jsonl'))
    preds = {name: {r['sample_id']: r for r in rows} for name, rows in
             (('ex136', new_rows), ('ex130', v4_rows), ('ex124', v2_rows))}
    report = dict(at=time.time(), seed=SEED, test=test,
                  ex130_test=read(c.RUN_V4_TRAINING / 'evaluation/report.json')['test'],
                  ex124_test=read(c.RUN_TERA_TRAINING / 'evaluation/report.json')['test'],
                  knowledge=dict(ex124=read(c.RUN_TERA_TRAINING / 'evaluation/knowledge-ex124.json'),
                                 ex130=read(c.RUN_V4_TRAINING / 'evaluation/knowledge-ex130.json'), ex136=know),
                  vs_ex130=compare(paired(new_rows, v4_rows, info)), vs_ex124=compare(paired(new_rows, v2_rows, info)),
                  failing=dict(vs_ex130=fail_metrics(new_rows, v4_rows, failing, replay_of),
                               vs_ex124=fail_metrics(new_rows, v2_rows, failing, replay_of)),
                  ground=ground_metrics(preds, info, ground),
                  tera=dict(vs_ex130=tera_metrics(new_rows, v4_rows, replay_of),
                            vs_ex124=tera_metrics(new_rows, v2_rows, replay_of)),
                  nhj=nhj['summary'], nhj_balloon=nhj['balloon'])
    atomic(out / 'evaluation/report.json', report, immutable=True)
    write_report(out, report)
    atomic(out / 'status.json', dict(stage='completed', at=time.time()))
    seal(out)
    print(json.dumps(dict(vs_ex130=report['vs_ex130']['all'], vs_ex124=report['vs_ex124']['all'],
                          ground=report['ground'], nhj=report['nhj']), ensure_ascii=False))
    return report


def _row(name, b):
    if not b['n']:
        return '| %s | 0 | - | - | - |' % name
    return '| %s | %d | %+.4f | %s | %+.2f%%p |' % (name, b['n'], b['nll_diff'], _interval(b['nll_diff_95']),
                                                  100 * b['match_diff'])


GROUP_TITLES = (('by_foe_item', '상대 아이템'), ('by_foe_balloon', '상대 풍선'), ('by_counter', '카운터'),
                ('by_label_kind', '라벨'), ('by_decision_kind', '결정'))


def write_report(out, report):
    curve = [json.loads(line) for line in (out / 'validation-curve.jsonl').read_text().splitlines()]
    sel, split = read(out / 'selection.json'), read(out / 'split.json')
    data = read(c.V5_DATASET / 'validation.json')
    k = report['knowledge']
    lines = ['# EX-136 laya v5 렌더러(상대 아이템 상태·상태 카운터) + 테라 지식 학습 보고', '',
             'EX-130(v4+테라)와 같은 시작 모델, 설정, 테라 지식 행에서 행동 행의 렌더러만 v5로 바꿨다(GPU0, D-195). '
             '사람 선택 재현이며 승률이 아니다. 이 보고는 EX-137·EX-138 배틀 진행 여부를 정하지 않는다(D-191).', '',
             '## 잠긴 test', '', '| 모델 | NLL | 일치율 | ECE |', '|---|---:|---:|---:|']
    for name, m in (('EX-124 v2+테라', report['ex124_test']['all']), ('EX-130 v4+테라', report['ex130_test']['all']),
                    ('EX-136 v5+테라', report['test']['all'])):
        lines.append('| %s | %.4f | %.2f%% | %.4f |' % (name, m['nll'], 100 * m['action_match_rate'], m['ece']))
    for key, other in (('vs_ex130', 'EX-130'), ('vs_ex124', 'EX-124')):
        cmp_ = report[key]
        lines += ['', '## 같은 행 차이 (EX-136 − %s, replay 클러스터 95%%, 시드 %d)' % (other, report['seed']), '',
                  '| 구분 | n | NLL 차이 | 95% | 일치율 차이 |', '|---|---:|---:|---|---:|',
                  _row('전체', cmp_['all']), _row('교체 행', cmp_['switch'])]
        for group, title in GROUP_TITLES:
            for name, b in cmp_[group].items():
                lines.append(_row('%s %s' % (title, name), b))
    g = report['ground']
    lines += ['', '## 공개된 Air Balloon 상대에게 지면 기술 (보고 지표)', '',
              '- 해당 test 행 %d(사람이 지면 기술을 고른 행 %s)' % (g['rows'], g['human_chose_ground']), '',
              '| 모델 | n | 지면 기술 확률 합 평균 | 지면 기술 1위 |', '|---|---:|---:|---:|']
    for name in ('ex124', 'ex130', 'ex136'):
        m = g[name]
        lines.append('| %s | %d | %s | %d |' % (name.upper().replace('EX', 'EX-'), m['n'],
                                              '%.4f' % m['ground_mass'] if m['ground_mass'] is not None else '-',
                                              m['ground_top']))
    for key, other in (('vs_ex130', 'EX-130'), ('vs_ex124', 'EX-124')):
        f = report['failing'][key]
        m = f['fail_mass']
        lines += ['', '## 실패로 정해진 선택지 (v5 입력 기준, EX-136 − %s)' % other, '',
                  '- 해당 test 행 %d(사람이 그 선택지를 고른 행 %d)' % (f['rows_with_failing'], f['human_chose_failing']),
                  '- 확률 합 평균: %s %.4f → EX-136 %.4f, 차이 %+.4f, 95%% %s' % (
                      other, m['old'], m['new'], m['diff'], _interval(m['diff_95'])) if m['diff'] is not None else '- 해당 없음',
                  '- 그 선택지가 1위인 행: %s %d → EX-136 %d' % (other, f['fail_top']['old'], f['fail_top']['new'])]
    n = report['nhj']
    lines += ['', '## 사람 대전 국면 재추론 (NHJ 4경기 %d결정, 보고 지표)' % n['decisions'], '',
              '공개된 풍선 Gholdengo 상대로 지면 기술을 고를 수 있던 결정 %d개:' % n['balloon_ground_decisions'], '',
              '| 경기 | 턴 | v2t 선택(지면 확률) | v4t 선택(지면 확률) | v5t 선택(지면 확률) |', '|---|---:|---|---|---|']
    for b in report['nhj_balloon']:
        cell = lambda m: '%s (%.2f)' % (b[m]['choice'].replace('move:', '').replace(':normal', ''), b[m]['ground_mass'])
        lines.append('| %s | %d | %s | %s | %s |' % (b['game'][-2:], b['turn'], cell('v2t'), cell('v4t'), cell('v5t')))
    lines += ['', '- 지면 기술 1위 횟수: ' + ', '.join('%s %d' % kv for kv in n['ground_top'].items()),
              '- v2t와 선택이 달라진 결정: ' + ', '.join('%s %d' % kv for kv in n['changed_vs_v2t'].items()),
              '- 국면 비교이며 승패를 말하지 않는다. 첫 분기 뒤의 국면은 실제로는 나오지 않았을 수 있다.', '',
              '## 테라 지식 held-out 정답률', '', '| 유형 | n | EX-124 | EX-130 | EX-136 |', '|---|---:|---:|---:|---:|']
    for part in ('heldout-A', 'heldout-B'):
        for kind in k['ex136'][part]:
            a, b, d = k['ex124'][part][kind], k['ex130'][part][kind], k['ex136'][part][kind]
            lines.append('| %s %s | %d | %.1f%% | %.1f%% | %.1f%% |' % (
                part, kind, d['n'], 100 * a['accuracy'], 100 * b['accuracy'], 100 * d['accuracy']))
    lines += ['', '## 자료와 학습', '',
              '- v5 자료 길이 제외 %d행(비율 %.4f)' % (data['token_budget_exclusions'], data['exclusion_rate']),
              '- 학습 행 %d(모방 %d + 테라 지식 %d), 보정 %d(모방만), validation %d' % (
                  split['train'], split['train'] - split['extra_train'], split['extra_train'], split['calibration'],
                  split['validation']), '',
              '| epoch | train loss | validation NLL(원 logit) | 일치율 |', '|---:|---:|---:|---:|']
    for r in curve:
        lines.append('| %d | %s | %.4f | %.2f%% |' % (r['epoch'], '%.4f' % r['train_loss'] if 'train_loss' in r else '-',
                                                    r['raw']['loss'], 100 * r['raw']['accuracy']))
    lines += ['', '선택 epoch %d.' % sel['selected_epoch'], '',
              '## 해석 한계', '',
              '- 미공개 아이템은 Air Balloon을 뺀 가정 세트 기준이다. 상태 카운터는 공개 protocol에서 센 값이다.',
              '- 두 모듈(`items`, `counters`)을 함께 바꿨으므로 차이를 한쪽 효과로 나누지 않는다.',
              '- 테라 B 지식 행은 EX-124와 같은 v2 상태 텍스트다.',
              '- 단일 시드 학습이다.', '']
    (out / 'report.md').write_text('\n'.join(lines))
