"""EX-148 (D-200, EP-223): the stalled-loop serving rule (`loop_decision`) on the v6st / v6ht checkpoints, no retraining.

`laya-v6st-lp` and `laya-v6ht-lp` play the sealed EX-120 schedule against Abyssal in one run on GPU2 / port 8108,
EX-139-style. Their same-slot baselines are the deterministic games of the same checkpoints with plain argmax:
EX-143 `laya-v6st` and EX-144 `laya-v6ht`. The frozen verdict is per rule model: same-slot score difference rule -
baseline, matchup-cluster bootstrap. A rule game in which the rule never fired must replay its baseline game (result and
turns): that is the reproduction check. Loop counts (runs of >= LONG same-move turns by the model side) are reported for
both sides of each comparison. The laya-vs-laya part of EX-148 is `headtohead` (EX-148-H1 / -H2, GPU3 / 8106).
"""
from __future__ import annotations
import json
import time

from . import config as c
from . import comparison as cmp
from .comparison import RENDER, Study, _run, failed_moves, summarize_compare, tera_usage
from .battle import summarize
from .generalization import SCORE, _bootstrap
from .reporting import _score
from .storage import atomic, jsonl, read, seal, sha, source_identity, verify_seal

DRAWS = 10000
LONG = 5
BASELINES = {'laya-v6st-lp': ('EX-143', c.RUN_COMPARE10, 'laya-v6st'),
             'laya-v6ht-lp': ('EX-144', c.RUN_COMPARE11, 'laya-v6ht')}

EX148 = Study(
    experiment='EX-148', plan='EP-223', seed=20261038, models=('laya-v6st-lp', 'laya-v6ht-lp'), out=c.RUN_LOOP_RULE,
    viewer=c.VIEWER_LOOP_RULE, gpu=(c.GPU2_INDEX, c.GPU2_UUID), port=c.PORT3, hours=c.COMPARE_HOURS,
    runs={'laya-v6st-lp': ('EX-141', c.RUN_V6S_TRAINING), 'laya-v6ht-lp': ('EX-142', c.RUN_V6H_TRAINING)},
    mock_model='laya-v6st-lp-initial', replicate=None,
    verdicts=('규칙이 배틀 성적을 개선', '악화', '구별되지 않음'),
    meta=dict(experiment='EX-148', plan='EP-223', slug='ex148', pairs=128, title='EX-148 · laya 루프 결정 규칙 256경기',
              heading='EX-148 · laya v6st(EX-141)·v6ht(EX-142) 정체 루프 결정 규칙 · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 v6st·v6ht 체크포인트가 루프 결정 규칙을 켠 채 번갈아 진행했습니다. '
                    '재학습은 없습니다. 내 활성이 직전 2턴 이상 같은 기술을 썼는데 상대 HP가 10%p 이상 줄지 않았으면 그 기술을 '
                    '빼고, 확률 0.10 이상인 차선이 있으면 그것을 고릅니다. 기준은 EX-143 v6st·EX-144 v6ht의 같은 슬롯입니다. '
                    '규칙이 작동한 결정의 확률 탭은 결정 분포이며 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex148-laya-v1'))


# ----------------------------------------------------------------------------- baselines

def baseline_rows(model):
    name, run, base_model = BASELINES[model]
    rows = [r for r in read(run / 'manifest.json')['schedule'] if r['model'] == base_model]
    outcomes = [o for o in read(run / 'result.json')['outcomes'] if o['model'] == base_model]
    return rows, outcomes


def scores(rows, outcomes):
    by_slot = {o['slot_id']: o for o in outcomes}
    return {r['base_slot_id']: SCORE[by_slot[r['slot_id']]['result']] for r in rows
            if r['slot_id'] in by_slot and by_slot[r['slot_id']]['status'] == 'completed'}


def versus(rows, outcomes, model, base, seed):
    by_slot = {o['slot_id']: o for o in outcomes}
    clusters, mine, theirs = {}, [], []
    for r in rows:
        o = by_slot.get(r['slot_id'])
        if r['model'] != model or o is None or o['status'] != 'completed' or r['base_slot_id'] not in base:
            continue
        mine.append(SCORE[o['result']])
        theirs.append(base[r['base_slot_id']])
        clusters.setdefault(r['matchup_id'], []).append(mine[-1] - theirs[-1])
    diffs = [d for v in clusters.values() for d in v]
    return dict(baseline='%s %s' % (BASELINES[model][0], BASELINES[model][2]), model=model, slots=len(diffs),
                score=sum(mine) / len(mine) if mine else None, baseline_score=sum(theirs) / len(theirs) if theirs else None,
                mean_diff=sum(diffs) / len(diffs) if diffs else None,
                matchup_bootstrap_95=_bootstrap(list(clusters.values()), seed=seed, draws=DRAWS),
                rule_better=sum(d > 0 for d in diffs), baseline_better=sum(d < 0 for d in diffs),
                same=sum(d == 0 for d in diffs))


def verdict(model_summary, block, study=EX148):
    if model_summary['status']['completed'] < 120:
        return '판정 보류(정상 종료 %d/128 < 120)' % model_summary['status']['completed']
    if not block['matchup_bootstrap_95']:
        return '판정 불가'
    low, high = block['matchup_bootstrap_95']
    better, worse, same = study.verdicts
    return better if low > 0 else worse if high < 0 else same


# ----------------------------------------------------------------------------- metrics

def _events(directory, slot_id):
    path = directory / 'games' / slot_id / 'events.jsonl'
    return list(jsonl(path)) if path.exists() else []


def rule_firings(directory, slot_id):
    """(decisions answered, decisions where the rule changed the choice) from the recorded serving bodies."""
    answered = fired = 0
    for e in _events(directory, slot_id):
        if e['type'] != 'http_response' or e.get('status_code') != 200:
            continue
        body = json.loads(e['raw_body'])
        answered += 1
        fired += bool((body.get('loop_rule') or {}).get('fired'))
    return answered, fired


def long_runs(directory, slot_id, side):
    """Runs of >= LONG consecutive turns in which the model side's active used the same move (self-called excluded).

    Each turn contributes the model side's `<mon>:<move>` or None (no move, or it switched); a run is a maximal stretch
    of one non-None value."""
    lines = [line for e in _events(directory, slot_id) if e['type'] == 'protocol' for line in e['protocol'].split('\n')]
    per_turn, current = [], None
    for line in lines:
        parts = line.split('|')
        if len(parts) > 2 and parts[1] == 'turn':
            per_turn.append(current)
            current = None
        elif len(parts) > 3 and parts[1] == 'move' and parts[2].startswith(side) and '[from]' not in line:
            current = parts[2][3:].strip() + ':' + parts[3]
    per_turn.append(current)
    runs, last, count = 0, None, 0
    for key in per_turn + [None]:
        if key is not None and key == last:
            count += 1
            continue
        runs += count >= LONG
        last, count = key, 1 if key is not None else 0
    return runs


def loop_metrics(directory, rows, outcomes, label=lambda r: r['model'], firings=True):
    by_slot = {o['slot_id']: o for o in outcomes}
    out = {}
    for r in rows:
        o = by_slot.get(r['slot_id'])
        if o is None or o['status'] != 'completed':
            continue
        m = out.setdefault(label(r), dict(games=0, long_runs=0, long_run_games=0, answered=0, fired=0, fired_games=0,
                                          fired_wins=0, fired_losses=0))
        m['games'] += 1
        n = long_runs(directory, r['slot_id'], o['model_side'])
        m['long_runs'] += n
        m['long_run_games'] += n > 0
        if firings:
            answered, fired = rule_firings(directory, r['slot_id'])
            m['answered'] += answered
            m['fired'] += fired
            if fired:
                m['fired_games'] += 1
                m['fired_wins'] += o['result'] == 'win'
                m['fired_losses'] += o['result'] == 'loss'
    return out


def reproduction(directory, rows, outcomes, model):
    """Rule games where the rule never fired, against the baseline game of the same slot (result and turns)."""
    base_rows, base_outcomes = baseline_rows(model)
    base = {r['base_slot_id']: o for r in base_rows for o in base_outcomes if o['slot_id'] == r['slot_id']}
    by_slot = {o['slot_id']: o for o in outcomes}
    checked = same = 0
    differ = []
    for r in rows:
        o = by_slot.get(r['slot_id'])
        b = base.get(r['base_slot_id'])
        if r['model'] != model or o is None or b is None or o['status'] != 'completed' or b['status'] != 'completed':
            continue
        if rule_firings(directory, r['slot_id'])[1]:
            continue
        checked += 1
        if (o['result'], o.get('turns')) == (b['result'], b.get('turns')):
            same += 1
        else:
            differ.append(r['slot_id'])
    return dict(checked=checked, same=same, differ=differ[:20])


# ----------------------------------------------------------------------------- offline (no inference)

def offline(out=c.RUN_LOOP_RULE):
    """EX-141 locked-test predictions: where the rule fires (stalled streak in the v6s text, argmax on that move, an
    alternative >= FLOOR), the human match of argmax and of the rule's choice, by whether the human repeated the move."""
    from .loop_decision import FLOOR, choose
    from .loop_weights import STREAK, classify
    path = out / 'diagnostics/offline.json'
    if path.exists():
        raise RuntimeError('EX-148 offline metric already computed')
    texts = {r['sample_id']: r for r in jsonl(c.V6S_DATASET / 'test.jsonl')}
    rows = list(jsonl(c.RUN_V6S_TRAINING / 'evaluation/test-selected.jsonl'))
    out_rows, counts = [], dict(test_rows=len(rows), stalled=0, fired=0, argmax_match=0, rule_match=0)
    for r in rows:
        t = texts.get(r['sample_id'])
        if t is None or not classify(t['state'], r['label']).startswith('stall'):
            continue
        counts['stalled'] += 1
        move = STREAK.search(t['state']).group(1)
        ids = list(r['probabilities'])
        choice, _, fired = choose(ids, r['probabilities'], move)
        if not fired:
            continue
        human = 'human_repeated' if r['label'] in ('move:%s:normal' % move, 'move:%s:tera' % move) else 'human_changed'
        counts['fired'] += 1
        counts['argmax_match'] += r['choice'] == r['label']
        counts['rule_match'] += choice == r['label']
        out_rows.append(dict(sample_id=r['sample_id'], move=move, human=human, label=r['label'], argmax=r['choice'],
                             rule=choice, label_probability=r['probabilities'].get(r['label'])))
    by_human = {}
    for x in out_rows:
        b = by_human.setdefault(x['human'], dict(n=0, argmax_match=0, rule_match=0))
        b['n'] += 1
        b['argmax_match'] += x['argmax'] == x['label']
        b['rule_match'] += x['rule'] == x['label']
    doc = dict(source=dict(test=str(c.V6S_DATASET / 'test.jsonl'),
                           predictions=str(c.RUN_V6S_TRAINING / 'evaluation/test-selected.jsonl'),
                           predictions_sha256=sha(c.RUN_V6S_TRAINING / 'evaluation/test-selected.jsonl')),
               floor=FLOOR, counts=counts, by_human=by_human, rows=out_rows, at=time.time())
    atomic(path, doc, immutable=True)
    print(json.dumps(dict(counts=counts, by_human=by_human), ensure_ascii=False))
    return doc


# ----------------------------------------------------------------------------- stages

def mock(study=EX148):
    """CPU, untrained base checkpoint with the rule, v6s path; outside every denominator."""
    cmp.mock(study)


def prepare(study=EX148):
    for model, (name, run, _) in BASELINES.items():
        if read(run / 'status.json')['stage'] != 'completed' or verify_seal(run):
            raise RuntimeError('%s is not completed and sealed' % name)
    cmp.prepare(study)
    atomic(study.out / 'baseline.json', {m: dict(experiment=name, run=str(run), model=base,
                                                 result_sha256=sha(run / 'result.json'),
                                                 manifest_sha256=sha(run / 'manifest.json'),
                                                 slots=len(scores(*baseline_rows(m))))
                                         for m, (name, run, base) in BASELINES.items()}, immutable=True)


def execute(study=EX148):
    out = study.out
    manifest = read(out / 'manifest.json')
    if (out / 'result.json').exists():
        raise RuntimeError('%s already executed' % study.experiment)
    if source_identity()['files'] != read(out / 'source/identity.json')['files']:
        raise RuntimeError('source changed after the %s freeze' % study.experiment)
    frozen = read(out / 'baseline.json')
    if any(sha(run / 'result.json') != frozen[m]['result_sha256'] for m, (_, run, _) in BASELINES.items()):
        raise RuntimeError('a baseline changed after the freeze')
    outcomes, latencies, error = _run(out, manifest['schedule'], manifest['servings'], 'cuda', study.hours, study)
    schedule = manifest['schedule']
    summary = summarize_compare(schedule, outcomes, latencies, None, study)
    vs, reference, reference_failed = {}, {}, {}
    for model in study.models:
        base_rows, base_outcomes = baseline_rows(model)
        vs[model] = versus(schedule, outcomes, model, scores(base_rows, base_outcomes), study.seed)
        vs[model]['verdict'] = verdict(summary['models'][model], vs[model], study)
        vs[model]['reproduction'] = reproduction(out, schedule, outcomes, model)
        name, run, base_model = BASELINES[model]
        label = lambda r, n=name, b=base_model: '%s %s' % (n, b)
        reference.update(loop_metrics(run, base_rows, base_outcomes, label=label, firings=False))
        reference_failed.update(failed_moves(run, base_rows, base_outcomes, model_of=label))
    overall = summarize(schedule, outcomes, [x for v in latencies.values() for x in v], seed=study.seed)
    result = dict(overall, **summary, versus_baseline=vs,
                  verdict=' · '.join('%s: %s' % (m, v['verdict']) for m, v in vs.items()),
                  loops=loop_metrics(out, schedule, outcomes), reference_loops=reference,
                  reference_failed=reference_failed,
                  tera=tera_usage(out, schedule, outcomes), failed_moves=failed_moves(out, schedule, outcomes),
                  outcomes=outcomes, phase_error=error, all_slots_attempted=len(outcomes) == len(schedule))
    atomic(out / 'result.json', result, immutable=True)
    atomic(out / 'status.json', dict(stage='executed', at=time.time(), verdict=result['verdict'],
                                     versus_baseline={k: (v['mean_diff'], v['matchup_bootstrap_95']) for k, v in vs.items()}))
    print(json.dumps(dict(verdict=result['verdict'], versus_baseline=vs, loops=result['loops'],
                          models={k: (v['wins'], v['draws'], v['losses']) for k, v in summary['models'].items()},
                          error=error), ensure_ascii=False))


def export(study=EX148):
    from .features import Calc
    from .serving import v6_renderer
    from .viewer import export as export_viewer
    out = study.out
    result = read(out / 'result.json')
    counts = ' · '.join('%s %d승 %d무 %d패' % (k, v['wins'], v['draws'], v['losses']) for k, v in result['models'].items())
    meta = dict(study.meta, intro=study.meta['intro'] + ' 모델별: ' + counts + '. 판정: ' + result['verdict'] + '.')
    with Calc() as calc:
        renderers = {m: v6_renderer(RENDER[m])(calc) for m in study.models}
        viewer = export_viewer(out, study.viewer, meta=meta, columns=cmp._columns,
                               renderer_for=lambda row: renderers[row['model']])
    write_report(out, result, viewer, study)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(), verdict=result['verdict']))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(study.viewer / 'index.html'), verdict=result['verdict']), ensure_ascii=False))


# ----------------------------------------------------------------------------- report

def _interval(v):
    return '[%+.4f, %+.4f]' % tuple(v) if v else '—'


def write_report(out, result, viewer, study=EX148):
    models = result['models']
    lines = ['# %s %s 보고' % (study.experiment, study.meta['heading'].split(' · ', 1)[1]), '', study.meta['intro'], '',
             '## 판정 (실행 전 동결: 규칙 모델 − 같은 체크포인트 argmax의 같은 슬롯)', '',
             '| 규칙 모델 | 기준 | 비교 슬롯 | 규칙 점수 | 기준 점수 | 차이 평균 | 조합 클러스터 95% | 규칙 우세/기준 우세/같음 | 판정 |',
             '|---|---|---:|---:|---:|---:|---|---|---|']
    for m, v in result['versus_baseline'].items():
        lines.append('| %s | %s | %d | %s | %s | %s | %s | %d/%d/%d | **%s** |' % (
            m, v['baseline'], v['slots'], _score(v['score']), _score(v['baseline_score']),
            '%+.4f' % v['mean_diff'] if v['mean_diff'] is not None else '—', _interval(v['matchup_bootstrap_95']),
            v['rule_better'], v['baseline_better'], v['same'], v['verdict']))
    lines += ['', '## 재현 검사', '', '규칙이 한 번도 작동하지 않은 경기는 기준 경기와 결과·턴 수가 같아야 한다.', '',
              '| 규칙 모델 | 검사 경기 | 같음 | 다른 슬롯(최대 20) |', '|---|---:|---:|---|']
    for m, v in result['versus_baseline'].items():
        r = v['reproduction']
        lines.append('| %s | %d | %d | %s |' % (m, r['checked'], r['same'], ', '.join(r['differ']) or '—'))
    lines += ['', '## 루프 지표 (보고 지표)', '',
              '긴 반복은 모델 쪽 활성이 %d턴 이상 연속 같은 기술을 쓴 구간이다.' % LONG, '',
              '| 모델 | 경기 | 긴 반복 | 긴 반복 경기 | 응답 결정 | 규칙 작동 결정 | 작동 경기 | 작동 경기 승/패 |',
              '|---|---:|---:|---:|---:|---:|---:|---|']
    for k, v in list(result['loops'].items()) + list(result['reference_loops'].items()):
        lines.append('| %s | %d | %d | %d | %s | %s | %s | %s |' % (
            k, v['games'], v['long_runs'], v['long_run_games'], v['answered'] or '—', v['fired'] or '—',
            v['fired_games'] or '—', '%d/%d' % (v['fired_wins'], v['fired_losses']) if v['fired_games'] else '—'))
    p = result['paired']
    lines += ['', '## v6ht-lp − v6st-lp (보고 전용)', '',
              '- 같은 슬롯 점수 차이 평균 %s, 조합 클러스터 95%% %s' % (
                  '%+.4f' % p['mean_diff'] if p['mean_diff'] is not None else '—', _interval(p['matchup_bootstrap_95'])),
              '', '## 모델별', '', '| 모델 | 정상 | 승/무/패 | 평균 점수 | 조합 클러스터 95% | 지연 p50 |', '|---|---|---|---:|---|---:|']
    for k, s in models.items():
        lines.append('| %s | %d/%d | %d/%d/%d | %s | %s | %s |' % (
            k, s['status']['completed'], s['scheduled'], s['wins'], s['draws'], s['losses'], _score(s['mean_score']),
            '[%.3f, %.3f]' % tuple(s['matchup_bootstrap_95']) if s['matchup_bootstrap_95'] else '—',
            '%.3f초' % s['inference_seconds']['p50'] if s['inference_seconds']['n'] else '—'))
    lines += ['', '## 실패·무효 기술 (보고 지표)', '', '| 모델 | 경기 | 기술 사용 | 실패·무효 | 비율 | 많이 실패한 기술 |',
              '|---|---:|---:|---:|---:|---|']
    fm = list(result['failed_moves'].items()) + list(result['reference_failed'].items())
    for k, f in fm:
        lines.append('| %s | %d | %d | %d | %s | %s |' % (
            k, f['games'], f['moves'], f['failed'], '%.2f%%' % (100 * f['rate']) if f['rate'] is not None else '—',
            ', '.join('%s %d/%d' % tuple(x) for x in f['top_failed'][:6])))
    lines += ['', '## 해석 한계', '',
              '- 재학습 없는 서빙 규칙이다. 기준은 이번 실행이 아니라 EX-143·EX-144 경기다(결정적 경로).',
              '- Abyssal은 회복·Protect 루프를 거의 만들지 않아 규칙 작동이 드물 수 있다. 사람 대전 효과는 이 실험으로 입증되지 않는다.',
              '- 반복 판단은 4턴 기록 창 안에서만 한다. 그 사이 상대가 교체했거나 HP를 모르면 작동하지 않는다.', '']
    if result.get('phase_error'):
        lines += ['## 단계 오류', '', '```', str(result['phase_error']), '```', '']
    lines += ['## 경기별', '', '| 슬롯 | 모델 | 진영 | 상태 | 결과 | 턴 | 감사 |', '|---|---|---|---|---|---|---|']
    for o in result['outcomes']:
        lines.append('| %s | %s | %s | %s | %s | %s | %s |' % (
            o['slot_id'], o['model'], o['model_side'], o['status'], o.get('result') or '—', o.get('turns', '—'),
            '통과' if o.get('audit_passed') else '실패'))
    lines += ['', '## 산출물', '',
              '- 원장 `ledger.jsonl`, 경기별 `games/<slot>/`, 결과 `result.json`, 지표 `metrics.json`, 기준 `baseline.json`',
              '- 뷰어: `%s/index.html` (경기 %d, 결정 %d)' % (study.viewer, viewer['games'], viewer['decisions']),
              '- 동결: `manifest.json`, `protocol/`, `source/identity.json`, 봉인 `checksums.sha256`', '']
    (out / 'report.md').write_text('\n'.join(lines))
    atomic(out / 'metrics.json', {k: v for k, v in result.items() if k != 'outcomes'})
