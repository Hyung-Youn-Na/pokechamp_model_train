"""EX-181 (EP-235) report: v10rt choices against foul-play's search from the same seat (stdlib only).

Reads `decisions.jsonl`, the metadata of `samples.jsonl` and `results.jsonl`; writes `result.json` and `report.md`.
Q(a) is the sample-chance x visit weighted mean MCTS score of root option a; V = Q(search best) is the searched
value of the position. Game-cluster bootstrap (2,000 resamples, seed fixed) for the main splits.
"""
from __future__ import annotations

import json
import random
import statistics
from collections import Counter, defaultdict

from integration.laya_regret import paths as P
from integration.laya_regret import search as S

GAPS = (0.05, 0.1, 0.2)
BOOT = 2000


def load():
    decisions = [json.loads(l) for l in open(P.RUN / 'decisions.jsonl')]
    meta = {}
    for line in open(P.RUN / 'samples.jsonl'):
        row = json.loads(line)
        meta[row['id']] = (row['slot'], row['rqid'], row['round'], row['chance'])
    results = {}
    for line in open(P.RUN / 'results.jsonl'):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        results[row['id']] = row
    grouped = defaultdict(list)
    missing = Counter()
    for sid, (slot, rqid, round_, chance) in meta.items():
        if sid in results:
            grouped[(slot, rqid, round_)].append((chance, results[sid]))
        else:
            missing[round_] += 1
    expected = Counter((m[0], m[1], m[2]) for m in meta.values())
    return decisions, grouped, expected, results, missing


def kind_of(row):
    if row['lead']:
        return 'lead'
    if row['forced']:
        return 'forced'
    choice = row.get('laya_choice', '')
    return 'switch' if choice.startswith('switch ') else 'move'


def action_type(choice):
    if choice is None:
        return None
    if choice.startswith('switch '):
        return 'switch'
    return 'tera' if choice.endswith('-tera') else 'move'


def turn_bin(row):
    if row['lead']:
        return 'lead'
    t = int(row['turn'] or 0)
    return '1-10' if t <= 10 else '11-20' if t <= 20 else '21-40' if t <= 40 else '41+'


def analysed(decisions, grouped, expected):
    rows = []
    for d in decisions:
        if d['status'] != 'ready':
            continue
        key = (d['slot'], d['rqid'], 0)
        if len(grouped.get(key, [])) != expected.get(key, -1):
            continue                                          # incomplete search for this decision
        agg = S.aggregate(grouped[key])
        if agg is None:
            continue
        laya = d['laya_choice']
        probs = d['laya_probs']
        order = sorted(probs, key=lambda c: -probs[c])
        best = agg['best']
        row = dict(slot=d['slot'], rqid=d['rqid'], turn=d['turn'], result=d['result'], archetype=d['archetype'],
                   kind=kind_of(d), bin=turn_bin(d), laya=laya, laya_p=probs.get(laya), best=best,
                   best_type=action_type(best), laya_type=action_type(laya),
                   agree=laya == best, considered=laya in agg['considered'], share_laya=agg['share'].get(laya, 0.0),
                   share_best=agg['share'][best], v=agg['q'][best], root=agg['root'],
                   gap=(agg['q'][best] - agg['q'][laya]) if laya in agg['q'] else None,
                   p_best=probs.get(best, 0.0), rank_best=(order.index(best) + 1) if best in order else None,
                   options=len(agg['share']), repeat=d.get('repeat', False))
        key1 = (d['slot'], d['rqid'], 1)
        if row['repeat'] and len(grouped.get(key1, [])) == expected.get(key1, -1):
            agg1 = S.aggregate(grouped[key1])
            if agg1:
                b1 = agg1['best']
                row.update(best1=b1, agree01=b1 == best, best1_in_considered0=b1 in agg['considered'],
                           gap01=(agg['q'][best] - agg['q'][b1]) if b1 in agg['q'] else None,
                           laya_agree1=laya == b1, v1=agg1['q'][b1])
        rows.append(row)
    return rows


def frac(values):
    values = list(values)
    return (sum(1 for v in values if v) / len(values)) if values else None


def summary(rows):
    gaps = [r['gap'] for r in rows if r['gap'] is not None]
    out = dict(n=len(rows), agree=frac(r['agree'] for r in rows), considered=frac(r['considered'] for r in rows),
               share_laya=statistics.mean(r['share_laya'] for r in rows) if rows else None,
               low_visit=frac(r['share_laya'] < 0.01 for r in rows),
               gap_mean=statistics.mean(gaps) if gaps else None,
               gap_median=statistics.median(gaps) if gaps else None)
    for g in GAPS:
        out['gap>=%g' % g] = frac(x >= g for x in gaps)
    return out


def boot(rows, fn, seed=P.SEED):
    """Game-cluster bootstrap 95% interval of fn(rows)."""
    by_game = defaultdict(list)
    for r in rows:
        by_game[r['slot']].append(r)
    games = sorted(by_game)
    rng = random.Random(seed)
    values = []
    for _ in range(BOOT):
        sample = [r for g in (rng.choice(games) for _ in games) for r in by_game[g]]
        v = fn(sample)
        if v is not None:
            values.append(v)
    values.sort()
    if not values:
        return None
    return [values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]]


def diff_boot(rows, fn, seed=P.SEED):
    """Loss minus win difference of fn, game-cluster bootstrap within each outcome."""
    wins = defaultdict(list)
    losses = defaultdict(list)
    for r in rows:
        (wins if r['result'] == 'win' else losses)[r['slot']].append(r)
    if not wins or not losses:
        return dict(point=None, ci=None)
    rng = random.Random(seed)
    values = []
    for _ in range(BOOT):
        w = [r for g in (rng.choice(sorted(wins)) for _ in wins) for r in wins[g]]
        l = [r for g in (rng.choice(sorted(losses)) for _ in losses) for r in losses[g]]
        a, b = fn(l), fn(w)
        if a is not None and b is not None:
            values.append(a - b)
    values.sort()
    point = (fn([r for rs in losses.values() for r in rs]) or 0) - (fn([r for rs in wins.values() for r in rs]) or 0)
    return dict(point=point, ci=[values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]])


def auc(rows):
    """P(V of a decision in a won game > V of a decision in a lost game)."""
    pos = sorted(r['v'] for r in rows if r['result'] == 'win')
    neg = sorted(r['v'] for r in rows if r['result'] != 'win')
    if not pos or not neg:
        return None
    import bisect
    total = 0.0
    for v in pos:
        lo = bisect.bisect_left(neg, v)
        hi = bisect.bisect_right(neg, v)
        total += lo + 0.5 * (hi - lo)
    return total / (len(pos) * len(neg))


def grouped_summary(rows, key):
    groups = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    return {k: summary(v) for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}


def build(rows, decisions, results, missing):
    out = {}
    counts = Counter(d['status'] for d in decisions)
    out['decisions'] = dict(counts)
    out['analysed'] = len(rows)
    out['games'] = len({r['slot'] for r in rows})
    out['missing_samples'] = dict(missing)
    secs = [r['seconds'] for r in results.values()]
    visits = Counter(r['total_visits'] for r in results.values())
    out['search'] = dict(samples=len(results), iterations=dict(visits.most_common(3)),
                         seconds_p50=statistics.median(secs) if secs else None,
                         seconds_p95=sorted(secs)[int(0.95 * len(secs))] if secs else None)
    out['all'] = summary(rows)
    out['all']['agree_ci'] = boot(rows, lambda rs: frac(r['agree'] for r in rs))
    out['all']['gap>=0.1_ci'] = boot(rows, lambda rs: frac(r['gap'] >= 0.1 for r in rs if r['gap'] is not None))
    out['by_result'] = grouped_summary(rows, 'result')
    out['loss_minus_win'] = dict(
        agree=diff_boot(rows, lambda rs: frac(r['agree'] for r in rs)),
        gap_ge_01=diff_boot(rows, lambda rs: frac(r['gap'] >= 0.1 for r in rs if r['gap'] is not None)),
        gap_mean=diff_boot(rows, lambda rs: statistics.mean([r['gap'] for r in rs if r['gap'] is not None] or [0])))
    out['by_kind'] = grouped_summary(rows, 'kind')
    out['by_laya_type'] = grouped_summary(rows, 'laya_type')
    out['by_archetype'] = grouped_summary(rows, 'archetype')
    out['by_turn'] = grouped_summary(rows, 'bin')
    # what laya chose vs what search chose (move / switch / tera), non-lead non-forced decisions
    free = [r for r in rows if r['kind'] in ('move', 'switch')]
    out['type_matrix'] = {'%s->%s' % k: v for k, v in sorted(Counter((r['laya_type'], r['best_type']) for r in free).items())}
    out['type_rates'] = dict(laya_switch=frac(r['laya_type'] == 'switch' for r in free),
                             search_switch=frac(r['best_type'] == 'switch' for r in free),
                             laya_tera=frac(r['laya_type'] == 'tera' for r in free),
                             search_tera=frac(r['best_type'] == 'tera' for r in free))
    # reachability of the search's best through laya's distribution (disagreements only)
    dis = [r for r in rows if not r['agree']]
    ranks = Counter(min(r['rank_best'] or 99, 4) for r in dis)
    out['disagreement_best_rank_in_laya'] = {('4+' if k == 4 else str(k)): v for k, v in sorted(ranks.items())}
    out['disagreement_p_best'] = dict(median=statistics.median(r['p_best'] for r in dis) if dis else None,
                                      ge_0_1=frac(r['p_best'] >= 0.1 for r in dis))
    # value validity
    out['value'] = dict(auc=auc(rows), by_turn={})
    for b, rs in sorted(defaultdict(list, {k: [r for r in rows if r['bin'] == k] for k in {r['bin'] for r in rows}}).items()):
        w = [r['v'] for r in rs if r['result'] == 'win']
        l = [r['v'] for r in rs if r['result'] != 'win']
        out['value']['by_turn'][b] = dict(auc=auc(rs), v_win=statistics.mean(w) if w else None,
                                          v_loss=statistics.mean(l) if l else None, n=len(rs))
    # repeat (search noise floor)
    rep = [r for r in rows if 'agree01' in r]
    gaps01 = [r['gap01'] for r in rep if r['gap01'] is not None]
    out['repeat'] = dict(n=len(rep), best_agree=frac(r['agree01'] for r in rep),
                         best1_in_considered0=frac(r['best1_in_considered0'] for r in rep),
                         laya_agree_round0=frac(r['agree'] for r in rep), laya_agree_round1=frac(r['laya_agree1'] for r in rep),
                         gap01_mean=statistics.mean(gaps01) if gaps01 else None,
                         **{'gap01>=%g' % g: frac(x >= g for x in gaps01) for g in GAPS},
                         v_abs_diff_median=statistics.median(abs(r['v'] - r['v1']) for r in rep) if rep else None)
    # big-gap decisions in lost games while the position was still open
    lost = [r for r in rows if r['result'] != 'win']
    big = [r for r in lost if r['gap'] is not None and r['gap'] >= 0.2 and r['v'] >= 0.4]
    out['loss_big_gap'] = dict(n=len(big), games=len({r['slot'] for r in big}),
                               lost_games=len({r['slot'] for r in lost}))
    first = {}
    for r in sorted(big, key=lambda r: (r['slot'], r['rqid'])):
        first.setdefault(r['slot'], r)
    turns = [int(r['turn'] or 0) for r in first.values()]
    out['loss_big_gap']['first_turn_median'] = statistics.median(turns) if turns else None
    out['loss_big_gap']['top'] = [{k: r[k] for k in ('slot', 'turn', 'kind', 'laya', 'laya_p', 'best', 'share_best',
                                                     'share_laya', 'v', 'gap', 'p_best', 'archetype')}
                                  for r in sorted(big, key=lambda r: -r['gap'])[:25]]
    return out


def pct(x):
    return '—' if x is None else '%.1f%%' % (100 * x)


def num(x, digits=3):
    return '—' if x is None else ('%.*f' % (digits, x))


def table(groups):
    lines = ['| 묶음 | 결정 | 1순위 일치 | 고려 집합 안 | laya 수 방문 몫 | 값 차이 평균 | ≥0.05 | ≥0.1 | ≥0.2 | laya 수 방문 1% 미만 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for k, s in groups.items():
        lines.append('| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            k, s['n'], pct(s['agree']), pct(s['considered']), pct(s['share_laya']), num(s['gap_mean']),
            pct(s['gap>=0.05']), pct(s['gap>=0.1']), pct(s['gap>=0.2']), pct(s['low_visit'])))
    return '\n'.join(lines)


def markdown(o):
    a = o['all']
    r = o['repeat']
    lw = o['loss_minus_win']
    lines = ['# EX-181 보고 — EX-174 v10rt 결정 대 foul-play 탐색', '',
             '- 대상: %d경기, 분석 결정 %d개 (결정 상태 %s, 빠진 표본 %s)' % (o['games'], o['analysed'], o['decisions'], o['missing_samples']),
             '- 탐색: 표본 %d개, 표본당 반복 %s, 소요 p50 %s초·p95 %s초' % (
                 o['search']['samples'], o['search']['iterations'], num(o['search']['seconds_p50'], 2), num(o['search']['seconds_p95'], 2)),
             '', '## 전체', '',
             table({'전체': a}), '',
             '- 1순위 일치 95%% %s, 값 차이 ≥0.1 비율 95%% %s(경기 클러스터 bootstrap)' % (
                 [pct(x) for x in a['agree_ci']] if a['agree_ci'] else '—',
                 [pct(x) for x in a['gap>=0.1_ci']] if a['gap>=0.1_ci'] else '—'),
             '', '## 탐색 잡음 기준(반복 탐색, 새 표본)', '',
             '- 결정 %d개: 두 탐색의 1순위 일치 %s, 회차 1 1순위가 회차 0 고려 집합 안 %s' % (r['n'], pct(r['best_agree']), pct(r['best1_in_considered0'])),
             '- 같은 결정에서 laya 일치: 회차 0 %s, 회차 1 %s' % (pct(r['laya_agree_round0']), pct(r['laya_agree_round1'])),
             '- 회차 1 1순위를 회차 0 Q로 잰 값 차이: 평균 %s, ≥0.05 %s, ≥0.1 %s, ≥0.2 %s; |V0−V1| 중앙값 %s' % (
                 num(r['gap01_mean']), pct(r['gap01>=0.05']), pct(r['gap01>=0.1']), pct(r['gap01>=0.2']), num(r['v_abs_diff_median'])),
             '', '## 탐색 값의 타당성', '',
             '- 결정 단위 AUC(이긴 경기 결정의 V > 진 경기 결정의 V): %s' % num(o['value']['auc']), '',
             '| 턴 구간 | 결정 | AUC | 이긴 경기 V 평균 | 진 경기 V 평균 |', '|---|---:|---:|---:|---:|']
    for b, v in o['value']['by_turn'].items():
        lines.append('| %s | %d | %s | %s | %s |' % (b, v['n'], num(v['auc']), num(v['v_win']), num(v['v_loss'])))
    lines += ['', '## 경기 결과별', '', table(o['by_result']), '',
              '- 진 경기 − 이긴 경기: 1순위 일치 %s %s, 값 차이 ≥0.1 비율 %s %s, 값 차이 평균 %s %s' % (
                  pct(lw['agree']['point']), [pct(x) for x in lw['agree']['ci'] or []],
                  pct(lw['gap_ge_01']['point']), [pct(x) for x in lw['gap_ge_01']['ci'] or []],
                  num(lw['gap_mean']['point']), [num(x) for x in lw['gap_mean']['ci'] or []]),
              '', '## 결정 종류별', '', table(o['by_kind']),
              '', '## laya 선택 유형별', '', table(o['by_laya_type']),
              '', '## laya 팀 유형별', '', table(o['by_archetype']),
              '', '## 턴 구간별', '', table(o['by_turn']),
              '', '## 무엇을 골랐나(선봉·강제 교체 제외)', '',
              '- laya 교체 %s / 탐색 1순위 교체 %s, laya 테라 %s / 탐색 1순위 테라 %s' % (
                  pct(o['type_rates']['laya_switch']), pct(o['type_rates']['search_switch']),
                  pct(o['type_rates']['laya_tera']), pct(o['type_rates']['search_tera'])),
              '- laya→탐색 유형 표: %s' % o['type_matrix'],
              '', '## 결합 정책으로 닿을 수 있나(불일치 결정)', '',
              '- 탐색 1순위의 laya 확률 순위: %s' % o['disagreement_best_rank_in_laya'],
              '- 탐색 1순위의 laya 확률 중앙값 %s, 0.1 이상 %s' % (
                  num(o['disagreement_p_best']['median']), pct(o['disagreement_p_best']['ge_0_1'])),
              '', '## 진 경기의 큰 차이 결정(V ≥ 0.4, 값 차이 ≥ 0.2)', '',
              '- %d결정, 진 경기 %d개 중 %d개에서 나옴, 경기별 첫 결정의 턴 중앙값 %s' % (
                  o['loss_big_gap']['n'], o['loss_big_gap']['lost_games'], o['loss_big_gap']['games'],
                  o['loss_big_gap']['first_turn_median']), '',
              '| 경기 | 턴 | 종류 | laya 선택(확률) | 탐색 1순위(방문 몫) | laya 수 방문 몫 | V | 값 차이 | 1순위의 laya 확률 |',
              '|---|---:|---|---|---|---:|---:|---:|---:|']
    for t in o['loss_big_gap']['top']:
        lines.append('| %s | %s | %s | %s (%s) | %s (%s) | %s | %s | %s | %s |' % (
            t['slot'], t['turn'], t['kind'], t['laya'], num(t['laya_p'], 2), t['best'], pct(t['share_best']),
            pct(t['share_laya']), num(t['v']), num(t['gap']), num(t['p_best'], 3)))
    return '\n'.join(lines) + '\n'


def main():
    decisions, grouped, expected, results, missing = load()
    rows = analysed(decisions, grouped, expected)
    out = build(rows, decisions, results, missing)
    (P.RUN / 'result.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    with open(P.RUN / 'rows.jsonl', 'w') as handle:
        for r in rows:
            handle.write(json.dumps(r, ensure_ascii=False) + '\n')
    (P.RUN / 'report.md').write_text(markdown(out))
    print(json.dumps(dict(analysed=out['analysed'], all=out['all'], repeat=out['repeat']), ensure_ascii=False, indent=1))
    return 0
