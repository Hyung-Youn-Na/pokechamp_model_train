"""EX-140 (D-197, EP-220): the EX-124 v2+Tera checkpoint on `v2fix` inputs, three zero-shot serving changes for Tera,
GPU1 / port 8109, no retraining (`tera_decision`).

`laya-v2t-fix-tp1` / `-tp3` (Tera-pooled decision, k = 1 / 3) and `laya-v2t-fix-tdef` (Tera defence text, argmax) play
the sealed EX-120 schedule against Abyssal in one run. The same-slot baseline is EX-139 `laya-v2t-fix` (same checkpoint,
same input, plain argmax, deterministic path); EX-125 `laya-v2t` is a reference row. The frozen verdict is per condition:
same-slot score difference condition - EX-139 fix, matchup-cluster bootstrap. tp3 - tp1 is reported only. A tp slot
whose rule never overrode argmax must replay the EX-139 fix game (result and turns): that is the reproduction check.
"""
from __future__ import annotations
import json
import time

from . import config as c
from . import comparison as cmp
from . import variant_battle as vb
from .comparison import Study, _run, failed_moves, tera_usage
from .battle import summarize
from .generalization import SCORE, summarize_generalization
from .reporting import _score
from .storage import atomic, jsonl, read, seal, sha, source_identity, verify_seal

BASELINE = ('EX-139', c.RUN_COMPARE8, 'laya-v2t-fix')
TP = ('laya-v2t-fix-tp1', 'laya-v2t-fix-tp3')

EX140 = Study(
    experiment='EX-140', plan='EP-220', seed=20261040, models=TP + ('laya-v2t-fix-tdef',), out=c.RUN_COMPARE9,
    viewer=c.VIEWER_COMPARE9, gpu=(c.GPU1_INDEX, c.GPU1_UUID), port=c.PORT2, hours=c.COMPARE_HOURS,
    runs={m: ('EX-124', c.RUN_TERA_TRAINING) for m in TP + ('laya-v2t-fix-tdef',)},
    mock_model='laya-v2t-fix-tp3-initial', replicate=None,
    verdicts=('배틀 성적을 개선', '악화', '구별되지 않음'),
    meta=dict(experiment='EX-140', plan='EP-220', slug='ex140', pairs=128, title='EX-140 · laya v2+테라 테라 결정·방어 문구 384경기',
              heading='EX-140 · laya v2+테라(EX-124) fix 입력 테라 합산 결정(k=1·3)과 테라 방어 문구 · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 같은 EX-124 체크포인트가 세 서빙으로 번갈아 진행했습니다. 재학습은 없고 '
                    '입력은 EX-139 fix(v2 형식, 아이템 상태로 보정한 값)입니다. tp1·tp3은 테라 선택지 확률을 합쳐 k배(1·3)로 '
                    '가장 높은 테라 선택지에 몰아 준 결정 분포의 1순위를 고르고, tdef는 테라 선택지에 테라 후 받는 상성 '
                    '(교체 후보와 같은 takes·worst 문구)을 더해 1순위를 고릅니다. 기준은 EX-139 fix의 같은 슬롯입니다. '
                    'tp 경기의 확률 탭은 결정 분포이며 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex140-laya-v1'))


# ----------------------------------------------------------------------------- baseline and comparisons

def baseline_rows():
    name, run, model = BASELINE
    rows = [r for r in read(run / 'manifest.json')['schedule'] if r['model'] == model]
    outcomes = [o for o in read(run / 'result.json')['outcomes'] if o['model'] == model]
    return rows, outcomes


def scores(rows, outcomes, model=None):
    """{EX-120 slot: score} of completed games (of `model` when given)."""
    by_slot = {o['slot_id']: o for o in outcomes}
    return {r['base_slot_id']: SCORE[by_slot[r['slot_id']]['result']] for r in rows
            if (model is None or r['model'] == model) and r['slot_id'] in by_slot
            and by_slot[r['slot_id']]['status'] == 'completed'}


def versus(rows, outcomes, model, base, label, seed=EX140.seed):
    block = vb.versus_baseline(rows, outcomes, model, base, seed)
    block['baseline'] = label
    return block


# ----------------------------------------------------------------------------- per-decision metrics

def _decisions(directory, slot_id):
    """(input body, response body, selection) per model-side decision, in order."""
    inputs, responses = {}, {}
    for e in jsonl(directory / 'games' / slot_id / 'events.jsonl'):
        if e['type'] == 'input':
            inputs[e['decision']] = e['body_json']
        elif e['type'] == 'response':
            responses[e['decision']] = e['body']
        elif e['type'] == 'selection':
            yield inputs.get(e['decision']), responses.get(e['decision']), e


def rule_effect(directory, rows, outcomes, base_rows, base_outcomes):
    """Per model: slots where the served choice ever differed from the policy argmax (`fired`), and how many slots
    replay the baseline game (same result and turns), split by fired / not fired."""
    by_slot = {o['slot_id']: o for o in outcomes}
    base = {r['base_slot_id']: o for r in base_rows for o in base_outcomes if o['slot_id'] == r['slot_id']}
    out = {}
    for r in rows:
        o = by_slot.get(r['slot_id'])
        if o is None or not (directory / 'games' / r['slot_id'] / 'events.jsonl').exists():
            continue
        fired = False
        for _, response, _ in _decisions(directory, r['slot_id']):
            if response and 'model_probabilities' in response:
                p = response['model_probabilities']
                fired |= response['choice'] != max(response['action_ids'], key=lambda k: p[k])
        b = base.get(r['base_slot_id'])
        same = b is not None and b['result'] == o.get('result') and b.get('turns') == o.get('turns')
        m = out.setdefault(r['model'], dict(slots=0, fired=0, fired_same=0, not_fired=0, not_fired_same=0))
        m['slots'] += 1
        key = 'fired' if fired else 'not_fired'
        m[key] += 1
        m[key + '_same'] += same
    return out


def tera_choices(directory, rows, outcomes, renderer, label=None):
    """Per model: each Tera the model side chose, with its defensive change (worst revealed foe attack, else the foe's
    types) and whether the Tera option's v2fix text differs from its normal twin beyond the tag (offence)."""
    import re
    from integration.pokechamp.imitation.schema import ImitationInput
    from . import compact, dex_v2, features
    from .features_v5 import resolved
    by_slot = {o['slot_id']: o for o in outcomes}
    out = {}
    for r in rows:
        o = by_slot.get(r['slot_id'])
        if o is None or not (directory / 'games' / r['slot_id'] / 'events.jsonl').exists():
            continue
        m = out.setdefault(label or r['model'], dict(teras=0, wins=0, by_rule=0, improved=0, same=0, worse=0,
                                                     unknown=0, offence=0, examples=[]))
        for body, response, selection in _decisions(directory, r['slot_id']):
            if not selection['choice'].endswith(':tera') or body is None:
                continue
            value = ImitationInput(body)
            _, view = resolved(value)
            me = {x['slot']: x for x in view['own_team']}[view['own_active_slot']]
            foe = {x['slot']: x for x in view['opponent_team']}.get(view['opponent_active_slot'])
            tera = dex_v2.to_id(me['original_set'].get('teraType', me['tera_type']))
            after = dict(me, terastallized=True, tera_type=tera)
            grade = 'unknown'
            if foe is not None and tera != 'stellar':
                w0, w1 = features._worst_seen(foe, me, view), features._worst_seen(foe, after, view)
                if w0 and w1:
                    a, b = w0['mult'], w1['mult']
                else:
                    a = max(compact.dex.multiplier(t, compact._types(me)) or 0 for t in compact._types(foe))
                    b = max(compact.dex.multiplier(t, [tera]) or 0 for t in compact._types(foe))
                grade = 'improved' if b < a else 'worse' if b > a else 'same'
            criteria = renderer(value)[1]['criteria']
            choice = selection['choice']
            offence = re.sub(r'; terastallize \w+', '', criteria[choice]) != criteria.get(choice[:-5] + ':normal')
            p = (response or {}).get('model_probabilities')
            by_rule = bool(p) and max(response['action_ids'], key=lambda k: p[k]) != choice
            m['teras'] += 1
            m['wins'] += o.get('result') == 'win'
            m['by_rule'] += by_rule
            m[grade] += 1
            m['offence'] += offence
            if len(m['examples']) < 40:
                m['examples'].append(dict(slot=r['slot_id'], turn=json.loads(value.body['state'])['snapshot'].get('turn'),
                                          choice=choice, tera=tera, defence=grade, offence=offence, by_rule=by_rule,
                                          result=o.get('result')))
    return out


# ----------------------------------------------------------------------------- stages

def mock(study=EX140):
    """CPU, untrained base checkpoint, Tera-pooled k=3 decision on `v2fix`; outside every denominator."""
    cmp.mock(study)


def prepare(study=EX140):
    """`comparison.prepare` plus the sealed EX-139 baseline identity."""
    name, run, model = BASELINE
    if read(run / 'status.json')['stage'] != 'completed' or verify_seal(run):
        raise RuntimeError('%s is not completed and sealed' % name)
    cmp.prepare(study)
    rows, outcomes = baseline_rows()
    atomic(study.out / 'baseline.json', dict(experiment=name, run=str(run), model=model,
                                            result_sha256=sha(run / 'result.json'),
                                            manifest_sha256=sha(run / 'manifest.json'),
                                            slots=len(scores(rows, outcomes))), immutable=True)


def execute(study=EX140):
    out = study.out
    manifest = read(out / 'manifest.json')
    if (out / 'result.json').exists():
        raise RuntimeError('%s already executed' % study.experiment)
    if source_identity()['files'] != read(out / 'source/identity.json')['files']:
        raise RuntimeError('source changed after the %s freeze' % study.experiment)
    if sha(BASELINE[1] / 'result.json') != read(out / 'baseline.json')['result_sha256']:
        raise RuntimeError('the EX-139 baseline changed after the freeze')
    rows = manifest['schedule']
    outcomes, latencies, error = _run(out, rows, manifest['servings'], 'cuda', study.hours, study)
    by_slot = {o['slot_id']: o for o in outcomes}
    models = {}
    for model in study.models:
        sub = [r for r in rows if r['model'] == model]
        models[model] = summarize_generalization(sub, [by_slot[r['slot_id']] for r in sub if r['slot_id'] in by_slot],
                                                 latencies.get(model, []))
    base_rows, base_outcomes = baseline_rows()
    base = scores(base_rows, base_outcomes)
    v2t = vb.baseline_scores(*vb.baseline_rows())
    label = '%s %s' % (BASELINE[0], BASELINE[2])
    blocks, reference = {}, {}
    for model in study.models:
        blocks[model] = versus(rows, outcomes, model, base, label, study.seed)
        blocks[model]['verdict'] = vb.verdict(models[model], blocks[model], study)
        reference[model] = versus(rows, outcomes, model, v2t, 'EX-125 laya-v2t', study.seed)
    paired = versus(rows, outcomes, TP[1], scores(rows, outcomes, TP[0]), TP[0], study.seed)
    overall = summarize(rows, outcomes, [x for v in latencies.values() for x in v], seed=study.seed)
    result = dict(overall, models=models, versus_fix=blocks, versus_v2t=reference, paired_tp3_tp1=paired,
                  verdict=' · '.join('%s: %s' % (m.rsplit('-', 1)[1], v['verdict']) for m, v in blocks.items()),
                  tera=tera_usage(out, rows, outcomes), failed_moves=failed_moves(out, rows, outcomes),
                  rule_effect=rule_effect(out, rows, outcomes, base_rows, base_outcomes),
                  reference=dict(tera={label: v for v in tera_usage(BASELINE[1], base_rows, base_outcomes).values()},
                                 failed_moves=failed_moves(BASELINE[1], base_rows, base_outcomes,
                                                           model_of=lambda r: label)),
                  outcomes=outcomes, phase_error=error, all_slots_attempted=len(outcomes) == len(rows))
    atomic(out / 'result.json', result, immutable=True)
    atomic(out / 'status.json', dict(stage='executed', at=time.time(), verdict=result['verdict'],
                                     versus_fix={k: (v['mean_diff'], v['matchup_bootstrap_95']) for k, v in blocks.items()}))
    print(json.dumps(dict(verdict=result['verdict'], versus_fix=blocks, paired_tp3_tp1=paired,
                          models={k: (v['wins'], v['draws'], v['losses']) for k, v in models.items()},
                          rule_effect=result['rule_effect'], error=error), ensure_ascii=False))


def export(study=EX140):
    from .features import Calc
    from .input_variants import renderer
    from .tera_decision import renderer as defence_renderer
    from .viewer import export as export_viewer
    out = study.out
    result = read(out / 'result.json')
    manifest = read(out / 'manifest.json')
    counts = ' · '.join('%s %d승 %d무 %d패' % (k, v['wins'], v['draws'], v['losses']) for k, v in result['models'].items())
    meta = dict(study.meta, intro=study.meta['intro'] + ' 모델별: ' + counts + '. 판정: ' + result['verdict'] + '.')
    with Calc() as calc:
        fix, tdef = renderer('v2fix', calc), defence_renderer(calc)
        renderers = {m: tdef if cmp.RENDER[m] == 'v2fixtd' else fix for m in study.models}
        viewer = export_viewer(out, study.viewer, meta=meta, columns=cmp._columns,
                               renderer_for=lambda row: renderers[row['model']])
        choices = tera_choices(out, manifest['schedule'], result['outcomes'], fix)
        base_rows, base_outcomes = baseline_rows()
        choices.update(tera_choices(BASELINE[1], base_rows, base_outcomes, fix, label='%s %s' % (BASELINE[0], BASELINE[2])))
    atomic(out / 'tera-choices.json', choices, immutable=True)
    write_report(out, result, viewer, choices, study)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(), verdict=result['verdict']))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(study.viewer / 'index.html'),
                          tera_choices={k: {x: y for x, y in v.items() if x != 'examples'} for k, v in choices.items()}),
                     ensure_ascii=False))


# ----------------------------------------------------------------------------- report

def write_report(out, result, viewer, choices, study=EX140):
    interval = vb._interval
    label = '%s %s' % (BASELINE[0], BASELINE[2])
    lines = ['# %s %s 보고' % (study.experiment, study.meta['heading'].split(' · ', 1)[1]), '', study.meta['intro'], '',
             '## 판정 (실행 전 동결: 각 조건 − %s 같은 슬롯)' % label, '',
             '| 조건 | 비교 슬롯 | 조건 점수 | 기준 점수 | 차이 평균 | 조합 클러스터 95% | 조건 우세/기준 우세/같음 | 판정 |',
             '|---|---:|---:|---:|---:|---|---|---|']
    for m, v in result['versus_fix'].items():
        lines.append('| %s | %d | %s | %s | %s | %s | %d/%d/%d | **%s** |' % (
            m, v['slots'], _score(v['score']), _score(v['baseline_score']),
            '%+.4f' % v['mean_diff'] if v['mean_diff'] is not None else '—', interval(v['matchup_bootstrap_95']),
            v['variant_better'], v['baseline_better'], v['same'], v['verdict']))
    lines += ['', '## 보고 전용 비교', '', '| 비교 | 슬롯 | 차이 평균 | 조합 클러스터 95% | 앞 우세/뒤 우세/같음 |', '|---|---:|---:|---|---|']
    pairs = [('%s − %s' % (TP[1], TP[0]), result['paired_tp3_tp1'])]
    pairs += [('%s − EX-125 laya-v2t' % m, v) for m, v in result['versus_v2t'].items()]
    for name, v in pairs:
        lines.append('| %s | %d | %s | %s | %d/%d/%d |' % (
            name, v['slots'], '%+.4f' % v['mean_diff'] if v['mean_diff'] is not None else '—',
            interval(v['matchup_bootstrap_95']), v['variant_better'], v['baseline_better'], v['same']))
    lines += ['', '## 모델별', '', '| 모델 | 정상 | 승/무/패 | 평균 점수 | 조합 클러스터 95% | 지연 p50 |', '|---|---|---|---:|---|---:|']
    for k, s in result['models'].items():
        lines.append('| %s | %d/%d | %d/%d/%d | %s | %s | %s |' % (
            k, s['status']['completed'], s['scheduled'], s['wins'], s['draws'], s['losses'], _score(s['mean_score']),
            '[%.3f, %.3f]' % tuple(s['matchup_bootstrap_95']) if s['matchup_bootstrap_95'] else '—',
            '%.3f초' % s['inference_seconds']['p50'] if s['inference_seconds']['n'] else '—'))
    lines += ['', '## 테라 사용 (보고 지표)', '',
              '| 모델 | 경기 | 테라 경기 | 테라 경기 승/패 | 테라 가능 결정 | 테라 선택 | 첫 테라 턴 중앙값 |', '|---|---:|---:|---|---:|---:|---:|']
    for k, v in list(result['tera'].items()) + list(result['reference']['tera'].items()):
        turns = sorted(v['turns'])
        lines.append('| %s | %d | %d | %d/%d | %d | %d | %s |' % (
            k, v['games'], v['tera_games'], v['tera_wins'], v['tera_losses'], v['available'], v['chosen'],
            turns[len(turns) // 2] if turns else '—'))
    lines += ['', '## 테라 선택의 성격 (보고 지표)', '',
              '방어: 테라 순간 상대가 공개한 공격 중 최악 배율(없으면 상대 타입 배율)의 테라 전→후. '
              '공격: 테라 선택지의 v2fix 문구가 같은 기술의 일반 선택지와 태그 밖에서 다름(자속·피해 변화).', '',
              '| 모델 | 테라 | 규칙이 바꾼 선택 | 방어 개선 | 같음 | 악화 | 판단 불가 | 공격 변화 있음 | 그 경기 승 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for k, v in choices.items():
        lines.append('| %s | %d | %d | %d | %d | %d | %d | %d | %d |' % (
            k, v['teras'], v['by_rule'], v['improved'], v['same'], v['worse'], v['unknown'], v['offence'], v['wins']))
    lines += ['', '## 규칙 작동과 재현 (보고 지표)', '',
              '규칙이 1순위를 바꾼 적 없는 tp 슬롯은 EX-139 fix 경기(결과·턴 수)를 재현해야 한다.', '',
              '| 모델 | 슬롯 | 규칙 작동 | 그중 기준과 같음 | 작동 안 함 | 그중 기준과 같음 |', '|---|---:|---:|---:|---:|---:|']
    for k, v in result['rule_effect'].items():
        lines.append('| %s | %d | %d | %d | %d | %d |' % (k, v['slots'], v['fired'], v['fired_same'], v['not_fired'],
                                                         v['not_fired_same']))
    lines += ['', '## 실패·무효 기술 (보고 지표)', '', '| 모델 | 기술 | 실패·무효 | 비율 |', '|---|---:|---:|---:|']
    for k, v in list(result['failed_moves'].items()) + list(result['reference']['failed_moves'].items()):
        lines.append('| %s | %d | %d | %.2f%% |' % (k, v['moves'], v['failed'], 100 * v['failed'] / v['moves'] if v['moves'] else 0))
    lines += ['', '## 산출물', '', '- 결과 `result.json`, 테라 선택 `tera-choices.json`, 뷰어 `%s`' % (study.viewer / 'index.html'),
              '- 분모: 조건별 예정 128, 정상 종료는 위 표', '']
    atomic(out / 'report.md', '\n'.join(lines))
    atomic(out / 'metrics.json', dict(versus_fix=result['versus_fix'], versus_v2t=result['versus_v2t'],
                                      paired_tp3_tp1=result['paired_tp3_tp1'], tera=result['tera'],
                                      tera_choices={k: {x: y for x, y in v.items() if x != 'examples'}
                                                    for k, v in choices.items()},
                                      rule_effect=result['rule_effect'], viewer=viewer))
