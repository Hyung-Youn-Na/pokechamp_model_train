"""v10 strategy facts (D-204 decisions 1 and 3, #26 likely threat and #33-41), computed on the item-resolved view.

Call `compute` inside `laya_threat.spreads.patched()`, so every foe spec is the item-consistent v9 spread. Damage is
the pinned calculator's % of the defender's max HP. The team matchup (#35/#36) uses bench specs (no boosts) and the
weather / terrain only (no screens or hazards), so it changes with the teams rather than with this turn; its requests
are cached per process (EX-071 rows of one replay are contiguous).
"""
from __future__ import annotations
import json
import math

from integration.laya_imitation import dex_v2, features, features_v3, features_v5, features_v7
from integration.laya_threat import spreads, threat

from . import history

ANSWER_HP = 50          # #36: Y answers X when it takes <= 50% from X and deals >= min(50, X's HP)
WINCON_SHOWN = 2
HEAL_FLOOR = 0.25
WALL_RATIO = 0.5        # #39: shown when the wall takes at most half of what the active foe takes
ENTRY_SHOWN = 12        # #41
REMOVER_FLOOR = 0.25
CACHE = 200_000
RECOVERY = ('recover', 'roost', 'slackoff', 'softboiled', 'milkdrink', 'moonlight', 'morningsun', 'synthesis',
            'shoreup', 'strengthsap', 'rest', 'wish', 'healorder', 'junglehealing', 'lunarblessing', 'painsplit')
HEAL_ITEMS = ('leftovers', 'blacksludge')
HEAL_ABILITIES = ('regenerator', 'poisonheal')
REMOVERS = ('defog', 'rapidspin', 'mortalspin', 'tidyup', 'courtchange')
HAZARDS = ('stealth_rock', 'spikes', 'toxic_spikes', 'sticky_web')

_cache = {}


def _alive(mon):
    return mon['status'] != 'fnt' and (mon['hp_percent'] is None or mon['hp_percent'] > 0)


def _hp(mon):
    return 100.0 if mon['hp_percent'] is None else mon['hp_percent']


def _damaging(move):
    facts = dex_v2.load()['moves'].get(move)
    return facts is not None and facts['category'] != 'status'


def _usage(mon):
    key = features_v3.species_key(mon['species'])
    return None if key is None else features_v3.usage()[key]


def _run(calc, requests):
    """`calc.run` with the per-process cache (keys are the canonical request JSON)."""
    keys = [json.dumps(r, sort_keys=True, separators=(',', ':')) for r in requests]
    if len(_cache) + len(set(keys)) > CACHE:   # clear first: the keys this call finds cached must stay cached
        _cache.clear()
    todo = sorted({k for k in keys if k not in _cache})
    if todo:
        for k, result in zip(todo, calc.run([json.loads(k) for k in todo]), strict=True):
            _cache[k] = result
    return [_cache[k] for k in keys]


def _best(results):
    """(max, min, move) of the strongest successful result, or None."""
    ok = [(r['max'], r['min'], m) for m, r in results if 'error' not in r]
    return max(ok) if ok else None


def _bench_foe(mon):
    spec, _ = features._opp_spec(mon)
    return dict(spec, boosts={})


# ----------------------------------------------------------------------------- #35 / #36 team matchup

def matchup(view, calc):
    """{(my slot, opp slot): dict(out, out_move, takes, takes_move, speed)} over the living Pokemon of both sides."""
    mine = [m for m in view['own_team'] if _alive(m)]
    theirs = [m for m in view['opponent_team'] if _alive(m)]
    neutral = dict(weather=view['weather'], field=view['field'], attacker_side={}, defender_side={})
    requests, slots = [], []
    for x in mine:
        attacker = features._own_spec(x, active=False)
        moves = [m['id'] for m in x['moves'] if _damaging(m['id'])]
        for y in theirs:
            defender = _bench_foe(y)
            for move in moves:
                requests.append(dict(attacker=attacker, defender=defender, move=move, **neutral))
                slots.append(('out', x['slot'], y['slot'], move))
            for move in threat.candidate_moves(y):
                requests.append(dict(attacker=defender, defender=features._own_spec(x, active=False), move=move,
                                     **neutral))
                slots.append(('takes', x['slot'], y['slot'], move))
    best = {}
    for (kind, xs, ys, move), result in zip(slots, _run(calc, requests) if requests else [], strict=True):
        best.setdefault((kind, xs, ys), []).append((move, result))
    trick_room = 'trick_room' in view['field']
    out = {}
    for x in mine:
        mine_speed = features._own_speed(x, view, False)
        for y in theirs:
            o = _best(best.get(('out', x['slot'], y['slot']), []))
            t = _best(best.get(('takes', x['slot'], y['slot']), []))
            foe_speed = features._opp_speed(y, view)
            speed = None
            if mine_speed is not None and foe_speed is not None:
                faster = mine_speed > foe_speed['est']
                speed = 'tie' if mine_speed == foe_speed['est'] else 'faster' if faster != trick_room else 'slower'
            out[(x['slot'], y['slot'])] = dict(out=o[0] if o else 0.0, out_move=o[2] if o else None,
                                               takes=t[0] if t else 0.0, takes_move=t[2] if t else None, speed=speed)
    return out


def answers(view, table):
    """{opp slot: my slot} with the largest (out - takes), faster first on ties."""
    rank = {'faster': 2, 'tie': 1, 'slower': 0, None: 0}
    out = {}
    for y in [m for m in view['opponent_team'] if _alive(m)]:
        cells = [(c['out'] - c['takes'], rank[c['speed']], -xs, xs) for (xs, ys), c in table.items() if ys == y['slot']]
        if cells:
            out[y['slot']] = max(cells)[3]
    return out


def wincons(view, table):
    """(my slots, opp slots) that no living Pokemon of the other side answers (#36)."""
    own = {m['slot']: m for m in view['own_team'] if _alive(m)}
    opp = {m['slot']: m for m in view['opponent_team'] if _alive(m)}
    mine = [xs for xs in own if not any(
        table[(xs, ys)]['out'] <= ANSWER_HP and table[(xs, ys)]['takes'] >= min(ANSWER_HP, _hp(own[xs])) for ys in opp)]
    theirs = [ys for ys in opp if not any(
        table[(xs, ys)]['takes'] <= ANSWER_HP and table[(xs, ys)]['out'] >= min(ANSWER_HP, _hp(opp[ys])) for xs in own)]
    return mine[:WINCON_SHOWN], theirs[:WINCON_SHOWN]


# ----------------------------------------------------------------------------- #26 / #34 active duel

def likely_threat(view, foe, me, calc):
    """The foe's likely attack on my active: the strongest revealed attacking move, else the most likely hidden one."""
    revealed = [m['id'] for m in foe['moves'] if _damaging(m['id'])]
    u = _usage(foe)
    hidden = [(m, p) for m, p in features_v7._moves(foe, u) if _damaging(m)] if u else []
    candidates = [(m, 1.0) for m in revealed] or hidden[:1]
    if not candidates:
        return None
    attacker = features._opp_spec(foe)[0]
    side = dict(weather=view['weather'], field=view['field'], attacker_side=view['opponent_side_conditions'],
                defender_side=view['own_side_conditions'])
    defender = features._own_spec(me, active=True)
    results = _run(calc, [dict(attacker=attacker, defender=defender, move=m, **side) for m, _ in candidates])
    ok = [(r['max'], r['min'], m, p) for (m, p), r in zip(candidates, results, strict=True) if 'error' not in r]
    if not ok:
        return None
    mx, mn, move, p = max(ok)
    return dict(move=move, p=p, min=mn, max=mx)


def _hits(hp, damage):
    return None if damage <= 0 else max(1, math.ceil(hp / damage - 1e-9))


def duel(view, facts, shown_fails, likely, first):
    """#34 from the shown `dmg` (non-Tera, not failing) and the likely threat; None if either side has no attack."""
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me, foe = own[view['own_active_slot']], opp[view['opponent_active_slot']]
    best = None
    for action_id, d in facts['damage'].items():
        parts = action_id.split(':')
        if parts[0] != 'move' or parts[2] != 'normal' or action_id in shown_fails or 'error' in d:
            continue
        if best is None or d['min'] > best[0]:
            best = (d['min'], parts[1], facts['moves'][action_id]['priority'])
    if best is None or likely is None:
        return None
    mine, theirs = _hits(_hp(foe), best[0]), _hits(_hp(me), likely['min'])
    if mine is None or theirs is None:
        return None
    foe_priority = dex_v2.load()['moves'].get(likely['move'], {}).get('priority', 0)
    if best[2] != foe_priority:
        me_first = best[2] > foe_priority
    elif first is not None:
        me_first = first >= 0.5
    else:
        me_first = 'first' in (facts['speed']['order'] or '') and 'second' not in (facts['speed']['order'] or '')
    win = mine <= theirs if me_first else mine < theirs
    return dict(me_hits=mine, me_move=best[1], opp_hits=theirs, opp_move=likely['move'], me_first=me_first,
                result='win' if win else 'lose')


# ----------------------------------------------------------------------------- #38 / #41 / #39 / #40

def heals(foe, pp_used):
    out = []
    used = pp_used.get(foe['species'], {})
    for m in foe['moves']:
        if m['id'] in RECOVERY:
            top = history.max_pp(m['id'])
            left = None if top is None or m['id'] not in used else max(0, top - used[m['id']])
            out.append(('move', m['id'], 'seen', left))
    u = _usage(foe)
    if u:
        for move, p in features_v7._moves(foe, u):
            if move in RECOVERY and p >= HEAL_FLOOR:
                out.append(('move', move, round(p, 4), None))
    state = (foe.get('item_state') or {}).get('state')
    if state == 'held' and foe['item_state']['item'] in HEAL_ITEMS:
        out.append(('item', foe['item_state']['item'], 'seen', None))
    elif state == 'unknown' and u:
        for item, p in features_v3._norm(features_v3._top(u['items'])):
            if item in HEAL_ITEMS and p >= HEAL_FLOOR:
                out.append(('item', item, round(p, 4), None))
    if foe['ability'] in HEAL_ABILITIES:
        out.append(('ability', foe['ability'], 'seen', None))
    elif not foe['ability'] and u:
        for ability, p in features_v3._norm(features_v3._top(u['abilities'])):
            if ability in HEAL_ABILITIES and p >= HEAL_FLOOR:
                out.append(('ability', ability, round(p, 4), None))
    return out


def _opp_entry(mon, side):
    """Entry damage of an opponent bench Pokemon on its own side (`features._hazards` reads `original_set`)."""
    state = (mon.get('item_state') or {}).get('state')
    item = mon['item_state']['item'] if state == 'held' else None
    probe = dict(mon, original_set={'ability': mon['ability'] or ''}, item=item)
    return features._hazards(probe, side)['pct'], state == 'unknown'


def hazards(view):
    """#41 on any side with hazards: opponent bench entry costs, and both sides' hazard removers."""
    if not any(k in HAZARDS for k in view['own_side_conditions']) and \
            not any(k in HAZARDS for k in view['opponent_side_conditions']):
        return None
    foe_slot = view['opponent_active_slot']
    entry = []
    if any(k in HAZARDS for k in view['opponent_side_conditions']):
        for mon in view['opponent_team']:
            if mon['slot'] != foe_slot and _alive(mon):
                pct, unknown = _opp_entry(mon, view['opponent_side_conditions'])
                if pct >= ENTRY_SHOWN:
                    u = _usage(mon)
                    boots = unknown and u and any(i == 'heavydutyboots' and p >= REMOVER_FLOOR
                                                  for i, p in features_v3._norm(features_v3._top(u['items'])))
                    entry.append((mon['species'], pct, bool(boots)))
    theirs = []
    for mon in view['opponent_team']:
        if not _alive(mon):
            continue
        seen = [m['id'] for m in mon['moves'] if m['id'] in REMOVERS]
        if seen:
            theirs.append((mon['species'], seen[0], None))
            continue
        u = _usage(mon)
        if u:
            likely = [(m, p) for m, p in features_v7._moves(mon, u) if m in REMOVERS and p >= REMOVER_FLOOR]
            if likely:
                theirs.append((mon['species'], likely[0][0], round(likely[0][1], 4)))
    mine = [(m['species'], next(x['id'] for x in m['moves'] if x['id'] in REMOVERS))
            for m in view['own_team'] if _alive(m) and any(x['id'] in REMOVERS for x in m['moves'])]
    return dict(entry=entry, opp_remover=theirs, my_remover=mine)


def walls(value, view, facts, calc):
    """#39 {move action: (species, max)} for my attacking options."""
    own = {m['slot']: m for m in view['own_team']}
    me = own[view['own_active_slot']]
    bench = [m for m in view['opponent_team'] if m['slot'] != view['opponent_active_slot'] and _alive(m)]
    side = dict(weather=view['weather'], field=view['field'], attacker_side=view['own_side_conditions'],
                defender_side=view['opponent_side_conditions'])
    requests, slots = [], []
    for action_id, fact in facts['moves'].items():
        if fact['category'] == 'status' or not bench:
            continue
        _, move, variant = action_id.split(':')
        tera = me['original_set'].get('teraType', me['tera_type']) if variant == 'tera' else None
        attacker = features._own_spec(me, dex_v2.to_id(tera) if tera else None)
        for mon in bench:
            requests.append(dict(attacker=attacker, defender=_bench_foe(mon), move=move, **side))
            slots.append((action_id, mon['species']))
    best = {}
    for (action_id, species), result in zip(slots, _run(calc, requests) if requests else [], strict=True):
        if 'error' in result:
            continue
        if action_id not in best or result['max'] < best[action_id][1]:
            best[action_id] = (species, result['max'])
    out = {}
    for action_id, (species, wall) in best.items():
        active = facts['damage'].get(action_id)
        if active is None or 'error' in active or active['max'] <= 0:
            continue
        if wall <= WALL_RATIO * active['max'] or wall == 0:
            out[action_id] = (species, wall)
    return out


def tera_defence(value, view, worst, calc):
    """#40 {tera move action: (move, min, max)} when my Tera changes the worst threat's type multiplier."""
    if worst is None or not view['can_tera']:
        return {}
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me, foe = own[view['own_active_slot']], opp[view['opponent_active_slot']]
    tera = me['original_set'].get('teraType', me['tera_type'])
    tera = dex_v2.to_id(tera) if tera else None
    move = dex_v2.load()['moves'].get(worst['move'])
    if not tera or tera == 'stellar' or move is None:
        return {}
    if dex_v2.multiplier(move['type'], [tera]) == dex_v2.multiplier(move['type'], features._types(me)):
        return {}
    base, _ = spreads.opp_spec(foe)
    spec, _ = spreads.fixed(dict(base, item=worst['item']), foe)
    side = dict(weather=view['weather'], field=view['field'], attacker_side=view['opponent_side_conditions'],
                defender_side=view['own_side_conditions'])
    result = _run(calc, [dict(attacker=dict(spec, tera=worst['tera']), defender=features._own_spec(me, tera),
                              move=worst['move'], **side)])[0]
    if 'error' in result:
        return {}
    return {a: (worst['move'], result['min'], result['max']) for a in value.action_ids
            if a.startswith('move:') and a.endswith(':tera')}


# ----------------------------------------------------------------------------- compute

def board(view):
    side = lambda team: ([m for m in team if _alive(m)], sum(_hp(m) for m in team if _alive(m)))
    (mine, mine_hp), (theirs, theirs_hp) = side(view['own_team']), side(view['opponent_team'])
    return dict(me=len(mine), me_hp=mine_hp, opp=len(theirs), opp_hp=theirs_hp)


def compute(value, facts, risk, shown_fails, calc):
    """All v10 strategy facts. `facts`: the v5 facts, `risk`: `threat.compute`, `shown_fails`: the v8 marks."""
    if not spreads.active():
        raise RuntimeError('strategy facts need laya_threat.spreads.patched()')
    _, view = features_v5.resolved(value)
    snapshot = json.loads(value.body['state'])['snapshot']
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me = own.get(view['own_active_slot']) if view['own_active_slot'] else None
    foe = opp.get(view['opponent_active_slot']) if view['opponent_active_slot'] else None
    me = me if me is not None and _alive(me) else None
    foe = foe if foe is not None and _alive(foe) else None
    table = matchup(view, calc)
    out = dict(board=board(view), answers=answers(view, table), wincon=wincons(view, table), hazards=hazards(view),
               likely=None, first=None, duel=None, heals=[], walls={}, tera={}, pp_used=history.opp_pp_used(snapshot),
               matchup={'%d-%d' % k: v for k, v in table.items()})
    if foe is not None:
        out['heals'] = heals(foe, out['pp_used'])
    if me is not None and foe is not None:
        inferred = features_v3.infer_set(foe, view['opponent_can_tera'])
        if inferred['source'] == 'usage':
            out['first'] = features_v3.first_chance(facts['speed']['me'], foe, inferred, view)
        if view['decision_kind'] == 'turn_action':
            out['likely'] = likely_threat(view, foe, me, calc)
            out['duel'] = duel(view, facts, shown_fails, out['likely'], out['first'])
            out['walls'] = walls(value, view, facts, calc)
            out['tera'] = tera_defence(value, view, risk['active'], calc)
    return out
