"""EX-181 post-hoc analyses (outside the registered metrics; added after the main report).

Reads rows.jsonl (report stage) and the EX-174 protocol logs, writes posthoc.json.
  1. calibration: next decision's V minus this V, by value-gap bin (does the search's gap show up?)
  2. gap by root-value bin x game result (is the win/loss gap difference just a V effect?)
  3. robust subset: decisions where laya's move got >= 1% of the visits
  4. gap mass concentration by game
  5. lost games whose search value peaked >= 0.7
  6. laya moves with a state-determinable null effect (all boosts +0, or the move fails), from the protocol
"""
import collections
import json

from integration.laya_regret import paths as P

# moves whose failure depends on the opponent's choice, not on the visible state
PREDICTION = {'Sucker Punch', 'Thunderclap', 'Protect', 'Detect', 'Spiky Shield', 'Baneful Bunker',
              'Silk Trap', 'Burning Bulwark', "King's Shield", 'Endure', 'Upper Hand', 'Focus Punch'}


def mean(x):
    x = list(x)
    return sum(x) / len(x) if x else None


def gap_bin(r):
    if r['agree']:
        return 'agree'
    g = r['gap']
    return '<0.05' if g < 0.05 else '0.05-0.1' if g < 0.1 else '0.1-0.2' if g < 0.2 else '>=0.2'


def protocol_lines(slot):
    ev = [json.loads(line) for line in open(P.SOURCE_RUN / 'games' / slot / 'events.jsonl')]
    ev = sorted((e for e in ev if e.get('type') == 'protocol'), key=lambda e: e['sequence'])
    return [ln for e in ev for ln in e['protocol'].split('\n') if ln and not ln.startswith('|request|')]


def null_moves(slot):
    """laya's own moves whose visible effect is nothing: every boost line +0, or a -fail on laya's mon."""
    lines = protocol_lines(slot)
    me = next(ln.split('|')[2] for ln in lines if ln.startswith('|player|') and ln.split('|')[3].startswith('lay'))
    out, turn, streak = [], 0, 0
    for i, ln in enumerate(lines):
        if ln.startswith('|turn|'):
            turn = int(ln.split('|')[2])
            continue
        if not (ln.startswith('|move|') and ln.split('|')[2].startswith(me + 'a')) or '[from]' in ln:
            continue
        name = ln.split('|')[3]
        if name in PREDICTION:
            streak = 0
            continue
        eff, j = [], i + 1
        while j < len(lines) and lines[j].startswith(('|-', '|c|')):
            eff.append(lines[j])
            j += 1
        boosts = [e for e in eff if e.startswith('|-boost|') and e.split('|')[2].startswith(me + 'a')]
        null = (boosts and all(e.split('|')[4] == '0' for e in boosts)) or any(
            e.startswith('|-fail|') and e.split('|')[2].startswith(me + 'a') for e in eff)
        streak = streak + 1 if null else 0
        if null:
            out.append(dict(turn=turn, move=name, streak=streak))
    return out


def stats(rows):
    return dict(n=len(rows), agree=mean(r['agree'] for r in rows), gap=mean(r['gap'] for r in rows),
                ge01=mean(r['gap'] >= 0.1 for r in rows), ge02=mean(r['gap'] >= 0.2 for r in rows))


def build():
    rows = [json.loads(line) for line in open(P.RUN / 'rows.jsonl')]
    games = collections.defaultdict(list)
    for r in rows:
        games[r['slot']].append(r)
    for g in games.values():
        g.sort(key=lambda r: r['rqid'])
    result = {s: g[0]['result'] for s, g in games.items()}

    cal = collections.defaultdict(list)
    for g in games.values():
        for a, b in zip(g, g[1:]):
            cal[gap_bin(a)].append((b['v'] - a['v'], a['gap']))
            if not a['agree']:
                cal['robust' if a['share_laya'] >= 0.01 else 'share<1%'].append((b['v'] - a['v'], a['gap']))
    calibration = {k: dict(n=len(x), dv=mean(d for d, _ in x), gap=mean(q for _, q in x)) for k, x in cal.items()}

    vbins = {}
    for lo, hi in [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]:
        for res in ('loss', 'win'):
            vbins[f'{lo:.1f}-{min(hi, 1):.1f} {res}'] = stats([r for r in rows if lo <= r['v'] < hi and r['result'] == res])

    robust = {k: stats([r for r in rows if r['share_laya'] >= 0.01 and (k == 'all' or r['result'] == k)])
              for k in ('all', 'loss', 'win')}

    mass = {s: sum(r['gap'] for r in g) for s, g in games.items()}
    total = sum(mass.values())
    top = sorted(mass.items(), key=lambda t: -t[1])
    concentration = dict(total=total, top5=sum(v for _, v in top[:5]) / total, top10=sum(v for _, v in top[:10]) / total,
                         top=[dict(slot=s, mass=v, result=result[s], decisions=len(games[s])) for s, v in top[:10]],
                         per_game={res: dict(games=sum(1 for s in games if result[s] == res),
                                             mass=mean(mass[s] for s in games if result[s] == res),
                                             ge01=mean(sum(r['gap'] >= 0.1 for r in games[s]) for s in games if result[s] == res))
                                   for res in ('loss', 'win')})

    peaks = []
    for s, g in games.items():
        if result[s] != 'loss':
            continue
        i = max(range(len(g)), key=lambda k: g[k]['v'])
        if g[i]['v'] >= 0.7:
            after = g[i:]
            peaks.append(dict(slot=s, turn=g[i]['turn'], v=g[i]['v'], mass_after=sum(r['gap'] for r in after),
                              robust_ge01_after=sum(r['gap'] >= 0.1 and r['share_laya'] >= 0.01 for r in after)))
    peaks.sort(key=lambda t: -t['mass_after'])

    by_turn = {(r['slot'], r['turn']): r for r in rows if r['kind'] == 'move'}
    nulls, matched = {}, []
    for s in sorted(games):
        nulls[s] = null_moves(s)
        matched += [by_turn[(s, n['turn'])] for n in nulls[s] if (s, n['turn']) in by_turn]
    null = dict(
        moves={res: sum(len(nulls[s]) for s in games if result[s] == res) for res in ('loss', 'win')},
        games_any={res: sum(1 for s in games if result[s] == res and nulls[s]) for res in ('loss', 'win')},
        games_streak3={res: sum(1 for s in games if result[s] == res and any(n['streak'] >= 3 for n in nulls[s]))
                       for res in ('loss', 'win')},
        games={res: sum(1 for s in games if result[s] == res) for res in ('loss', 'win')},
        by_move=collections.Counter(n['move'] for v in nulls.values() for n in v).most_common(),
        worst=sorted(([s, result[s], len(v), max((n['streak'] for n in v), default=0)] for s, v in nulls.items() if v),
                     key=lambda t: -t[2])[:12],
        search=dict(stats(matched), share_laya=mean(r['share_laya'] for r in matched),
                    best=collections.Counter(r['best'] for r in matched).most_common(8)))

    out = dict(note='post-hoc, outside the registered EX-181 metrics', calibration=calibration, v_bins=vbins,
               robust_share_ge_1pct=robust, concentration=concentration,
               lost_peak_ge07=dict(n=len(peaks), with_robust_ge01_after=sum(p['robust_ge01_after'] > 0 for p in peaks),
                                   games=peaks),
               null_moves=null)
    (P.RUN / 'posthoc.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    o = build()
    print(json.dumps({k: o[k] for k in ('calibration', 'robust_share_ge_1pct')}, indent=1))
    print(json.dumps({k: v for k, v in o['null_moves'].items() if k != 'worst'}, ensure_ascii=False))
