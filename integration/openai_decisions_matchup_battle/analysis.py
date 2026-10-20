"""EX112 사전 동결 판정기. 공개 입력만 판정하며 미래 로그는 사후 검토에만 사용한다."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics

from integration.candidate_matchup.summary import decorate, remove_summaries, FIELD, PROFILE, token
from integration.candidate_matchup.rules import identity
from integration.jev_eval.turn_logs import public_rows

VERSION = 'candidate-matchup-comparison-v1'
METRICS = ('blocked', 'type_zero', 'damage_zero', 'reflected', 'primary_status_blocked',
           'secondary_status_blocked', 'unknown')


def flags(candidate):
    summary = candidate.get(FIELD, {})
    effect = summary.get('public_effects', {}).get('result')
    status = summary.get('status_effect', {})
    return dict(blocked=effect == 'blocked',
        type_zero=summary.get('type_matchup', {}).get('multiplier') == 0,
        damage_zero=summary.get('damage', {}).get('result') == 'calculated_zero',
        reflected=effect == 'reflected',
        primary_status_blocked=status.get('result') == 'blocked' and status.get('component') == 'primary',
        secondary_status_blocked=status.get('result') == 'blocked' and status.get('component') == 'secondary_if_triggered',
        unknown=effect == 'unknown')


def classify(payload, selection):
    """Unknown is not a blocker; alternative means any other available candidate.

    Unknown-only turns never enter the primary denominator. Unknown alternatives
    alongside a definite blocker are identified separately, not silently dropped.
    """
    rebuilt = decorate(remove_summaries(payload))
    criteria = rebuilt['questions']['action']['criteria']
    by_choice = {key: flags(value) for key, value in criteria.items()}
    choice = selection['choice'] if selection else None
    if choice is not None and choice not in criteria:
        raise ValueError('selected choice is absent from input')
    automatic = bool(selection and selection['automatic'])
    model = bool(selection and not automatic)
    counts = {name: sum(row[name] for row in by_choice.values()) for name in METRICS}
    return dict(decision_kind=rebuilt['state']['decision_kind'], turn=rebuilt['state']['turn'],
        choice=choice, automatic=automatic, model=model, candidates=len(criteria),
        candidate_counts=counts, selected=by_choice.get(choice),
        primary_eligible=model and 0 < counts['blocked'] < len(criteria),
        all_blocked=bool(criteria) and counts['blocked'] == len(criteria),
        unknown_present=counts['unknown'] > 0,
        unknown_only_alternatives=0 < counts['blocked'] < len(criteria) and
            counts['blocked'] + counts['unknown'] == len(criteria),
        selected_summary=criteria[choice].get(FIELD) if choice is not None else None)


def review_case(entry, selected_summary, rows):
    """Public evidence between the decision cutoff and next turn, no causal claim."""
    boundary = entry['boundary']
    cutoff = (boundary['protocol_event_seq'], boundary['line_index'])
    window = []
    for row in rows:
        if (row['sequence'], row['line_index']) <= cutoff:
            continue
        if row['protocol'].startswith('|turn|'):
            break
        window.append(row)
    actor = entry['actor']; other = 'p2' if actor == 'p1' else 'p1'
    move_name = token(selected_summary['move'])
    action_index = next((i for i, row in enumerate(window)
        if row['protocol'].startswith('|move|' + actor) and
        token(row['protocol'].split('|')[3]) == move_name), None)
    preceding = window if action_index is None else window[:action_index]
    switches = [r for r in preceding if r['protocol'].startswith(('|switch|' + other, '|drag|' + other, '|replace|' + other))]
    tera = [r for r in preceding if r['protocol'].startswith('|-terastallize|' + other)]
    state_changes = [r for r in preceding if r['protocol'].startswith((
        '|-status|', '|-curestatus|', '|-start|', '|-end|', '|-item|', '|-enditem|',
        '|-ability|', '|-fieldstart|', '|-fieldend|', '|-weather|', '|-sidestart|', '|-sideend|',
        '|-boost|', '|-unboost|', '|-formechange|', '|detailschange|'))]
    effects = []
    if action_index is not None:
        for row in window[action_index + 1:]:
            if row['protocol'].startswith(('|move|', '|cant|', '|upkeep|')):
                break
            effects.append(row)
    markers = Counter(r['protocol'].split('|')[1] for r in effects)
    return dict(cutoff=boundary, selected_move_observed=action_index is not None,
        opponent_before_action='changed' if switches else 'stayed' if action_index is not None else 'not_observed',
        opponent_switches=switches, opponent_tera=tera, preceding_state_changes=state_changes,
        action_row=window[action_index] if action_index is not None else None,
        actual_result_rows=effects, actual_result_markers=dict(markers), public_window=window,
        interpretation='공개 로그의 시간순 사건이다. 상대 행동·상태변화 및 실패 원인의 인과효과를 추정하지 않는다.')


def distribution(values):
    values = sorted(values)
    return dict(n=len(values), total=sum(values), median=statistics.median(values) if values else None,
                p95=values[math.ceil(.95 * len(values)) - 1] if values else None,
                maximum=max(values) if values else None)


def usage_metrics(events):
    attempts = [e for e in events if e['type'] == 'transport']
    responses = {e['request_number']: e for e in events if e['type'] == 'http_response'}
    usage = Counter(); unknown = 0
    for attempt in attempts:
        response = responses.get(attempt['request_number'])
        try:
            value = json.loads(response['raw_body']).get('usage') if response else None
        except (ValueError, TypeError):
            value = None
        if not isinstance(value, dict):
            unknown += 1
        else:
            usage.update({k: v for k, v in value.items() if type(v) in (int, float)})
    return dict(logical_requests=len({e['decision'] for e in attempts}), http_attempts=len(attempts),
        retries=sum(e.get('attempt', 1) > 1 for e in attempts), confirmed_tokens=dict(usage),
        usage_unknown_attempts=unknown, retry_wait_seconds=sum(e['delay_seconds'] for e in events if e['type'] == 'provider_retry'),
        http_latency_seconds=distribution([e['elapsed_seconds'] for e in events if e['type'] in ('http_response', 'attempt_failure') and 'elapsed_seconds' in e]),
        logical_latency_seconds=distribution([e['elapsed_seconds'] for e in events if e['type'] == 'response']),
        decision_latency_seconds=distribution([e['decision_seconds'] for e in events if e['type'] == 'selection' and 'decision_seconds' in e]))


def score(outcome):
    if not outcome or not outcome.get('completed') or not outcome.get('audit_passed'):
        return None
    return {'player_won': 1., 'draw': .5, 'opponent_won': 0., 'player_lost': 0., 'tie': .5, 'tied': .5}.get(outcome.get('outcome'))


def analyze(source, viewer=None):
    source = Path(source)
    manifest = json.loads((source / 'manifest.json').read_text())
    result = json.loads((source / 'result.json').read_text())
    events = [json.loads(line) for line in (source / 'events.jsonl').open()]
    outcomes = {row['username']: row for row in result['outcomes']}
    selections = {e['decision']: e for e in events if e['type'] == 'selection'}
    logs = {name: public_rows(events, name)[0] for name in outcomes}
    counters = Counter(); selected = Counter(); candidate_counts = Counter(); cases = []; decisions = []
    for entry in events:
        if entry['type'] != 'input':
            continue
        row = classify(entry['payload'], selections.get(entry['decision']))
        outcome = outcomes[entry['decision'].split('-')[0]]
        row.update(decision=entry['decision'], slot=outcome['slot'], slot_id=outcome['slot_id'],
                   input_event_seq=entry['event_seq'], valid_game=score(outcome) is not None)
        counters['inputs'] += 1
        for key in ('model', 'automatic', 'primary_eligible', 'all_blocked', 'unknown_present', 'unknown_only_alternatives'):
            counters[key] += bool(row[key])
        counters['unselected'] += row['choice'] is None
        counters['primary_selected_blocked'] += bool(row['primary_eligible'] and row['selected']['blocked'])
        candidate_counts.update(row['candidate_counts'])
        if row['selected']:
            selected.update({('automatic_' if row['automatic'] else 'model_') + k: int(v) for k, v in row['selected'].items()})
        if row['selected'] and row['selected']['blocked']:
            case = dict(row, review=review_case(entry, row['selected_summary'], logs[outcome['username']]),
                raw_events=str(source / 'events.jsonl'),
                viewer=str(Path(viewer) / f"battle-{outcome['slot']}" / 'index.html') if viewer else None,
                replay=str(Path(viewer) / f"battle-{outcome['slot']}" / 'replay.html') if viewer else None)
            cases.append(case)
        decisions.append(row)
    valid = [score(row) for row in result['outcomes'] if score(row) is not None]
    wins = valid.count(1.); draws = valid.count(.5); losses = valid.count(0.)
    return dict(version=VERSION, experiment=manifest['experiment_id'], source=str(source),
        counts=dict(counters), selected_metrics=dict(selected), candidate_metrics=dict(candidate_counts),
        primary=dict(numerator=counters['primary_selected_blocked'], denominator=counters['primary_eligible'],
            rate=counters['primary_selected_blocked'] / counters['primary_eligible'] if counters['primary_eligible'] else None),
        battle=dict(planned=len(manifest['schedule']), attempted=len(result['outcomes']), valid=len(valid),
            wins=wins, draws=draws, losses=losses, score_rate=sum(valid) / len(valid) if valid else None,
            failed=result['failed'], invalid=result['invalid'], unattempted=result['unattempted'], completed_pairs=result['completed_pairs']),
        usage=usage_metrics(events), decisions=decisions, blocked_cases=cases,
        outcomes=result['outcomes'], schedule=manifest['schedule'])


def difference(new, baseline):
    return new - baseline if new is not None and baseline is not None else None


def compare(baseline, new, output, viewer=None):
    """Write a new comparison directory; never overwrite preserved evidence."""
    baseline_viewer = Path('/workspace/exports/battle_viewers/ex110')
    old = analyze(baseline, baseline_viewer if baseline_viewer.exists() else None)
    fresh = analyze(new, viewer)
    if old['schedule'] != fresh['schedule']:
        raise ValueError('comparison schedules differ')
    slots = []; pairs = defaultdict(list)
    old_by_slot = {r['slot_id']: r for r in old['outcomes']}
    new_by_slot = {r['slot_id']: r for r in fresh['outcomes']}
    for row in old['schedule']:
        a = score(old_by_slot.get(row['slot_id'])); b = score(new_by_slot.get(row['slot_id']))
        item = dict(slot_id=row['slot_id'], paired_slot_id=row['paired_slot_id'], baseline=a, new=b, difference=difference(b, a))
        slots.append(item); pairs[row['paired_slot_id']].append(item)
    pair_rows = [dict(paired_slot_id=key, common_complete=len(rows) == 2 and all(r['difference'] is not None for r in rows),
        baseline=sum(r['baseline'] for r in rows) / 2 if len(rows) == 2 and all(r['baseline'] is not None for r in rows) else None,
        new=sum(r['new'] for r in rows) / 2 if len(rows) == 2 and all(r['new'] is not None for r in rows) else None,
        difference=sum(r['difference'] for r in rows) / 2 if len(rows) == 2 and all(r['difference'] is not None for r in rows) else None)
        for key, rows in pairs.items()]
    report = dict(version=VERSION, profile=PROFILE, rules=identity(),
        analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        baseline={k: v for k, v in old.items() if k not in ('decisions', 'blocked_cases', 'outcomes', 'schedule')},
        new={k: v for k, v in fresh.items() if k not in ('decisions', 'blocked_cases', 'outcomes', 'schedule')},
        primary_rate_difference=difference(fresh['primary']['rate'], old['primary']['rate']),
        score_rate_difference=difference(fresh['battle']['score_rate'], old['battle']['score_rate']), slots=slots, pairs=pair_rows,
        primary_definition='모델 선택·blocked와 다른 후보 공존. 교체/unknown도 다른 후보이며 unknown은 차단으로 세지 않는다. 자동/전후보차단/미선택 제외.',
        limitations='과거 기준선 탐색 비교. 실행시점·모델 변동성·선택 이후 경기전개·개발 대진 재사용. 인과효과·일반 승률 개선·문자열 배치 단독효과를 주장하지 않는다.')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    (output / 'comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    case_text = ['# 차단 선택 전사례 공개 로그 검토', '', '요약은 선택 이전 공개입력으로 재생성했다. 아래 미래 로그는 사후 결과 검토에만 사용했다.', '']
    for label, data in (('baseline', old), ('new', fresh)):
        (output / f'{label}-decisions.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in data['decisions']))
        (output / f'{label}-blocked-cases.json').write_text(json.dumps(data['blocked_cases'], ensure_ascii=False, indent=2) + '\n')
        for case in data['blocked_cases']:
            review = case['review']
            case_text += [f"## {data['experiment']} 경기{case['slot']} 턴{case['turn']} · {case['choice']}", '',
                f"결정 `{case['decision']}` · 자동 {case['automatic']} · 유효경기 {case['valid_game']} · 주분모 {case['primary_eligible']}", '',
                f"[원문]({case['raw_events']}) event_seq={case['input_event_seq']}; cutoff={review['cutoff']}", '',
                f"상대 선행 교체 {len(review['opponent_switches'])} · 테라 {len(review['opponent_tera'])} · 선행 상태변화 {len(review['preceding_state_changes'])} · 상대 {review['opponent_before_action']} · 선택 기술 관측 {review['selected_move_observed']}", '',
                f"실제 결과 표지: {review['actual_result_markers']}. 원문 순서에 따른 검토이며 성공/실패 원인의 추가 추론은 하지 않는다.", '']
            if case['viewer']:
                case_text += [f"[입력·선택·리플레이]({case['viewer']}) · [리플레이]({case['replay']})", '']
            case_text += ['```text'] + [f"{r['sequence']}:{r['line_index']} {r['protocol']}" for r in review['public_window']] + ['```', '']
    (output / 'blocked-cases.md').write_text('\n'.join(case_text))
    lines = ['# 후보별 상성 요약 고정32경기 비교', '', report['primary_definition'], '',
        '| 항목 | 기준선 | 요약 추가 |', '|---|---:|---:|']
    for key in ('numerator', 'denominator', 'rate'):
        lines.append(f"| 주지표 {key} | {old['primary'][key]} | {fresh['primary'][key]} |")
    for key in ('valid', 'wins', 'draws', 'losses', 'score_rate', 'failed', 'invalid', 'unattempted', 'completed_pairs'):
        lines.append(f"| 경기 {key} | {old['battle'][key]} | {fresh['battle'][key]} |")
    for key in ('logical_requests', 'http_attempts', 'retries', 'usage_unknown_attempts', 'retry_wait_seconds'):
        lines.append(f"| 사용 {key} | {old['usage'][key]} | {fresh['usage'][key]} |")
    lines += ['', f"주지표 차이(새−기준선) {report['primary_rate_difference']}; 점수율 차이 {report['score_rate_difference']}.", '',
        '타입0·피해0·반사·주요/부가 상태차단·unknown·자동선택은 comparison.json에 별도 집계했다. 부가 상태차단은 전체 기술 차단에 합산하지 않았다.', '',
        '## 동일 슬롯·진영 교환쌍', '', '| 슬롯 | 기준 점수 | 새 점수 | 차이 |', '|---|---:|---:|---:|']
    lines += [f"| {r['slot_id']} | {r['baseline']} | {r['new']} | {r['difference']} |" for r in slots]
    lines += ['', '| 쌍 | 기준 평균 | 새 평균 | 차이 |', '|---|---:|---:|---:|']
    lines += [f"| {r['paired_slot_id']} | {r['baseline']} | {r['new']} | {r['difference']} |" for r in pair_rows]
    lines += ['', '## 사용량·지연', '', '```json', json.dumps({k: d['usage'] for k, d in [('baseline', old), ('new', fresh)]}, ensure_ascii=False, indent=2), '```', '',
        '[차단 선택 전사례](blocked-cases.md) · [기계 판독 지표](comparison.json)', '', report['limitations'], '']
    (output / 'report.md').write_text('\n'.join(lines))
    return report
