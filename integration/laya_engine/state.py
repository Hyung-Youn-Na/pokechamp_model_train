"""EP-224 judge scenarios: an `ImitationInput` (item-state-resolved snapshot + four-turn history) -> `judge.cjs` input.

Only the serving input is read, so offline rows and live decisions give the same scenario:
- both teams: species, HP, fainted, status (sleep and Toxic counters), boosts and Tera of the actives, own sets in full,
  the foe's revealed moves plus probe moves (it never uses its real hidden moves);
- side conditions (layers), weather, terrain and pseudo-weather;
- the actives' lasting volatiles from the snapshot `effects` (Substitute, Taunt, Encore, Leech Seed, ...), except the
  ones that only restrict my own menu (the request's options already reflect them);
- from the history: whether my active has acted since it came in, my Protect streak (judged as the first use; the
  streak becomes a separate `likely fails`), a successful Destiny Bond last turn, Wish and Future Sight pending, the
  foe's last move (Encore / Disable / Spite / Instruct), Protean / Libero already used.
Hidden foe information is enumerated by the judge: every species Ability when unrevealed, and for an unknown item no
item, a generic held item and every usage item that changes move outcomes. The foe's action is a probe: a status
move that does nothing, by default; reactive moves (Sucker Punch, Counter, Encore, ...) also get physical, special
and priority attacks in both speed orders, and Ground moves against a Flying foe its Roost first. A sleeping user is
judged both staying asleep and waking when the counters allow either.
"""
from __future__ import annotations
import json

from integration.laya_imitation import features_v3

STATUS_PROBE = 'splash'
REACTIVE = frozenset((
    'suckerpunch', 'thunderclap', 'upperhand', 'counter', 'mirrorcoat', 'metalburst', 'comeuppance', 'focuspunch',
    'shelltrap', 'mefirst', 'encore', 'disable', 'spite', 'instruct', 'mirrormove', 'copycat', 'quash', 'afteryou',
    'snatch', 'grudge', 'beakblast'))
STALL = frozenset(('protect', 'detect', 'kingsshield', 'spikyshield', 'banefulbunker', 'obstruct', 'silktrap',
                   'burningbulwark', 'endure'))
FUTURE = frozenset(('futuresight', 'doomdesire'))
SLEEP_USABLE = frozenset(('sleeptalk', 'snore'))
CLEARERS = frozenset(('defog', 'rapidspin', 'mortalspin', 'tidyup', 'courtchange'))
# My field setters and the foe moves that would clear the way for them first (my screens, the foe side's hazards).
SETTERS = {'stealthrock': ('defog', 'rapidspin', 'mortalspin', 'tidyup', 'courtchange'),
           'spikes': ('defog', 'rapidspin', 'mortalspin', 'tidyup', 'courtchange'),
           'toxicspikes': ('defog', 'rapidspin', 'mortalspin', 'tidyup', 'courtchange'),
           'stickyweb': ('defog', 'rapidspin', 'mortalspin', 'tidyup', 'courtchange'),
           'reflect': ('defog', 'brickbreak', 'psychicfangs', 'ragingbull', 'courtchange'),
           'lightscreen': ('defog', 'brickbreak', 'psychicfangs', 'ragingbull', 'courtchange'),
           'auroraveil': ('defog', 'brickbreak', 'psychicfangs', 'ragingbull', 'courtchange')}
HIDDEN_FLOOR = 0.05      # a hidden foe move this likely (usage, rescaled to the hidden slots) gets its own case
# Items that can change whether a move fails; any other unknown item is one generic held item.
SPECIAL_ITEMS = frozenset(('safetygoggles', 'covertcloak', 'ringtarget', 'ironball', 'abilityshield', 'clearamulet',
                           'mentalherb', 'protectivepads', 'utilityumbrella', 'focussash', 'boosterenergy'))
GENERIC_ITEM = 'leftovers'
ITEM_FLOOR = 0.005
# Snapshot `effects` keys (underscores removed) rebuilt as engine volatiles on the actives.
VOLATILES = frozenset((
    'substitute', 'taunt', 'encore', 'confusion', 'saltcure', 'healblock', 'leechseed', 'yawn', 'trapped', 'curse',
    'nightmare', 'torment', 'embargo', 'magnetrise', 'aquaring', 'ingrain', 'focusenergy', 'charge', 'smackdown',
    'telekinesis', 'gastroacid', 'tarshot', 'noretreat', 'dragoncheer', 'laserfocus', 'powertrick', 'glaiverush',
    'syrupbomb', 'throatchop', 'stockpile', 'minimize', 'defensecurl', 'imprison', 'disable'))
OWN_MENU_ONLY = frozenset(('taunt', 'encore', 'torment', 'healblock', 'throatchop', 'disable', 'imprison'))
WEATHER = {'snow': 'snowscape'}
TERRAINS = frozenset(('electricterrain', 'grassyterrain', 'mistyterrain', 'psychicterrain'))
LAYERED = frozenset(('spikes', 'toxicspikes'))
ABSORB_WATER = frozenset(('waterabsorb', 'stormdrain', 'dryskin'))


def _id(text):
    return ''.join(ch for ch in str(text or '').lower() if ch.isalnum())


def _species(name):
    s = _id(name)
    if s.startswith('ogerpon') and s.endswith('tera'):
        s = s[:-4]
    return s


# ----------------------------------------------------------------------------- history

def _moves(history, who):
    """[(index, turn, move id, failed)] for `who`'s own moves (not called ones), in order."""
    out = []
    for i, e in enumerate(history):
        a = e['args']
        if e['event'] != 'move' or not a or a[0] != who or any(x.startswith('[from]') for x in a[2:]):
            continue
        failed = False
        for f in history[i + 1:]:
            if f['event'] in ('move', 'turn', 'upkeep'):
                break
            if f['event'] in ('-fail', '-immune', '-block'):
                failed = True
                break
        out.append((i, e['turn'], _id(a[1]) if len(a) > 1 else '', failed))
    return out


def _entered(history, who):
    """Index of `who`'s last switch-in in the window, or None."""
    idx = [i for i, e in enumerate(history) if e['event'] in ('switch', 'drag') and e['args'][:1] == [who]]
    return idx[-1] if idx else None


def recall(snapshot):
    """History-derived state for both actives (see the module docstring)."""
    history, turn = snapshot['history'], snapshot['turn']
    own_moves, foe_moves = _moves(history, '@self'), _moves(history, '@opponent')
    me_in, foe_in = _entered(history, '@self'), _entered(history, '@opponent')
    since_me = [m for m in own_moves if me_in is None or m[0] > me_in]
    cant_me = any(e['event'] == 'cant' and e['args'][:1] == ['@self'] for i, e in enumerate(history)
                  if me_in is None or i > me_in)
    acted = bool(since_me or cant_me) if me_in is not None else turn > 1
    by_turn = {}
    for i, t, m, failed in since_me:
        by_turn.setdefault(t, (m, failed))
    streak, t = 0, turn - 1
    while t in by_turn and by_turn[t][0] in STALL and not by_turn[t][1]:
        streak += 1
        t -= 1
    last = by_turn.get(turn - 1)
    since_foe = [m for m in foe_moves if foe_in is None or m[0] > foe_in]
    foe_last = since_foe[-1][2] if since_foe else (None if foe_in is not None else '?')
    protean = lambda who, start: any(
        e['event'] == '-start' and e['args'][:1] == [who] and len(e['args']) > 1 and e['args'][1] == 'typechange'
        and any('Protean' in x or 'Libero' in x for x in e['args'][2:])
        for i, e in enumerate(history) if start is None or i > start)
    return dict(
        acted=acted, stall_streak=streak, destiny_bond=bool(last and last[0] == 'destinybond' and not last[1]),
        wish=any(m == 'wish' and not f and t == turn - 1 for _, t, m, f in own_moves),
        future=any(m in FUTURE and not f and t in (turn - 1, turn - 2) for _, t, m, f in own_moves),
        foe_last=foe_last, me_protean=protean('@self', me_in), foe_protean=protean('@opponent', foe_in))


# ----------------------------------------------------------------------------- scenario

def _probes(me_types, me_ability):
    physical = 'bite' if 'ghost' in me_types else 'tackle'
    special = 'ember' if me_ability in ABSORB_WATER else 'watergun'
    priority = 'shadowsneak' if 'ghost' in me_types else 'quickattack'
    return physical, special, priority


def foe_items(foe):
    """Hypotheses for the foe active's item from its resolved `item_state`."""
    state = (foe.get('item_state') or {}).get('state')
    if state == 'held' or (state is None and foe['item']):
        return [foe['item']]
    if state == 'removed':
        return ['']
    key = features_v3.species_key(foe['species'])
    usage = features_v3.usage().get(key, {}).get('items', {}) if key else {}
    special = sorted((k for k, p in usage.items() if k in SPECIAL_ITEMS and p >= ITEM_FLOOR), key=lambda k: -usage[k])
    return [GENERIC_ITEM, ''] + special


def hidden_moves(foe):
    """{move: probability} for the foe's hidden moves (usage inclusion rescaled to the hidden slots, `features_v7`)."""
    from integration.laya_imitation import features_v7
    key = features_v3.species_key(foe['species'])
    if key is None or len(foe['moves']) >= 4:
        return {}
    return dict(features_v7._moves(foe, features_v3.usage()[key]))


def _volatiles(mon, own, foe_last):
    out = {}
    for key in (mon.get('effects') or {}):
        v = _id(key)
        if v not in VOLATILES or (own and v in OWN_MENU_ONLY):
            continue
        out[v] = {'move': foe_last} if v in ('encore', 'disable') and foe_last not in (None, '?') else {}
    return out


def _own(m, active):
    o = m['original_set']
    return dict(species=_species(m['species']), ability=m['ability'] or o.get('ability') or '', item=m['item'] or '',
                moves=[x['id'] for x in m['moves']], pp={x['id']: x['pp'] for x in m['moves'] if x['pp'] is not None},
                nature=o.get('nature') or 'serious', evs=o.get('evs'), ivs=o.get('ivs'), level=o.get('level', 100),
                gender=o.get('gender') or '', tera_type=m['tera_type'] or o.get('teraType'),
                hp=m['hp_percent'], status=m['status'] if m['status'] != 'fnt' else None,
                fainted=m['status'] == 'fnt', boosts=m['boosts'] if active else {},
                terastallized=bool(m['terastallized']), types=list(m['types']))


def _opp(m, probes):
    revealed = [x['id'] for x in m['moves']]
    return dict(species=_species(m['species']), ability=m['ability'] or '', item=m['item'] or '',
                moves=revealed + [p for p in probes if p not in revealed], level=100,
                tera_type=m['tera_type'], hp=m['hp_percent'], status=m['status'] if m['status'] != 'fnt' else None,
                fainted=m['status'] == 'fnt', boosts=m['boosts'], terastallized=bool(m['terastallized']),
                types=list(m['types']))


def _sleep(me, ability):
    """Possible [startTime, time] for my sleeping active: one staying asleep, one waking this turn (if possible)."""
    if me['status'] != 'slp':
        return [None]
    starts = (3,) if me.get('status_source') == 'rest' else (2, 3, 4)
    step = 2 if ability == 'earlybird' else 1
    count = me.get('status_counter')
    out = {}
    for start in starts:
        for c in ([count] if count is not None else range(0, 4)):
            time = start - step * c
            if time <= 0:
                continue
            out.setdefault('wake' if time - step <= 0 else 'stay', [start, time])
    return [out[k] for k in ('stay', 'wake') if k in out] or [None]


def wake_chance(me, ability):
    """Probability that my sleeping active wakes on this turn's move attempt (uniform Showdown sleep lengths)."""
    if me['status'] != 'slp' or me.get('status_counter') is None:
        return None
    starts = (3,) if me.get('status_source') == 'rest' else (2, 3, 4)
    step = 2 if ability == 'earlybird' else 1
    c = me['status_counter']
    alive = [s for s in starts if s - step * c > 0]
    return sum(1 for s in alive if s - step * (c + 1) <= 0) / len(alive) if alive else None


def build(view, action_ids, sid=''):
    """Scenario for `judge.cjs`, or None when the decision has no move options or no actives."""
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    if view['decision_kind'] != 'turn_action' or not view['own_active_slot'] or not view['opponent_active_slot']:
        return None
    me, foe = own[view['own_active_slot']], opp[view['opponent_active_slot']]
    if me['status'] == 'fnt' or foe['status'] == 'fnt':
        return None
    moves = [a for a in action_ids if a.startswith('move:') and a.split(':')[1] != 'struggle']
    if not moves:
        return None
    r = recall(view)
    me_ability = me['ability'] or _id(me['original_set'].get('ability'))
    physical, special, priority = _probes(me['types'], me_ability)
    revealed = [x['id'] for x in foe['moves']]
    hidden = hidden_moves(foe)
    probes = [STATUS_PROBE, physical, special, priority]
    roost = 'flying' in foe['types'] and ('roost' in revealed or hidden.get('roost', 0) >= HIDDEN_FLOOR)
    hazard = next((m for m in ('stealthrock', 'spikes', 'toxicspikes', 'stickyweb') if m not in revealed
                   and hidden.get(m, 0) >= HIDDEN_FLOOR), None)
    probes += (['roost'] if roost else []) + ([hazard] if hazard else [])
    removers = sorted({m for ms in SETTERS.values() for m in ms
                       if m not in revealed and hidden.get(m, 0) >= HIDDEN_FLOOR})
    probes += removers
    own_team = [_own(m, m is me) for m in sorted(own.values(), key=lambda m: m['slot'])]
    opp_team = [_opp(m, probes) for m in sorted(opp.values(), key=lambda m: m['slot'])]
    mine = own_team[me['slot'] - 1]
    if mine['status'] == 'frz':
        mine['status'] = None       # staying frozen never executes the move; only the thawing case says anything
    mine.update(acted=r['acted'], protean_used=r['me_protean'],
                volatiles=_volatiles(me, True, r['foe_last']))
    if r['destiny_bond']:
        mine['volatiles']['destinybond'] = {}
    theirs = opp_team[foe['slot'] - 1]
    theirs.update(acted=True, last_move=r['foe_last'], probe_move=physical, protean_used=r['foe_protean'],
                  volatiles=_volatiles(foe, False, r['foe_last']))
    if not theirs['ability']:
        theirs['ability'] = None
    from integration.laya_imitation.effect_knowledge import effects
    move_types = effects()['moves']
    sleeps = _sleep(me, me_ability)
    options = []
    for action_id in moves:
        _, move, mode = action_id.split(':')
        # The foe may act first: a hit (my HP is no longer full), any of its revealed moves (hazards, Haze, Roost, ...)
        # and likely hidden ones that change my move's outcome. Moves that switch or faint the foe are skipped by the
        # judge (a foe switch is out of scope).
        plans = [dict(order='me', foe_move=STATUS_PROBE), dict(order='foe', foe_move=physical)]
        plans += [dict(order='foe', foe_move=m) for m in revealed if m != physical]
        if move in REACTIVE:
            plans += [dict(order=o, foe_move=f) for o in ('foe', 'me') for f in (physical, special, priority)
                      if (o, f) != ('foe', physical)]
            plans.append(dict(order='foe', foe_move=STATUS_PROBE))
        info = move_types.get(move)
        if roost and 'roost' not in revealed and info and info['type'] == 'ground' and info['category'] != 'status':
            plans.append(dict(order='foe', foe_move='roost'))
        if hazard and move in CLEARERS:
            plans.append(dict(order='foe', foe_move=hazard))
        plans += [dict(order='foe', foe_move=m) for m in removers if m in SETTERS.get(move, ())]
        options.append(dict(id=action_id, move=move, tera=mode == 'tera',
                            plans=[dict(p, sleep=s) for s in sleeps for p in plans]))
    sides = {}
    for side, key, can in (('p1', 'own_side_conditions', view['can_tera']),
                           ('p2', 'opponent_side_conditions', view['opponent_can_tera'])):
        conditions = {}
        for k, v in (view[key] or {}).items():
            cid = _id(k)
            conditions[cid] = int(v) if cid in LAYERED else 5
        sides[side] = dict(conditions=conditions, slots=[], can_tera=bool(can))
    if r['wish']:
        sides['p1']['slots'].append('wish')
    if r['future']:
        sides['p2']['slots'].append('futuremove')
    weather = _id(view['weather']) if view['weather'] else None
    terrain, pseudo = None, {}
    for k in (view['field'] or {}):
        fid = _id(k)
        if fid in TERRAINS:
            terrain = dict(id=fid, turns=5)
        else:
            pseudo[fid] = 5
    return dict(id=sid, p1=dict(team=own_team, active=me['slot'] - 1, **sides['p1']),
                p2=dict(team=opp_team, active=foe['slot'] - 1, **sides['p2']),
                weather=dict(id=WEATHER.get(weather, weather), turns=5) if weather else None,
                terrain=terrain, pseudo=pseudo, foe_items=foe_items(foe), options=options,
                recall=r, wake=wake_chance(me, me_ability))


def dumps(scenario):
    return json.dumps(scenario, separators=(',', ':'), sort_keys=True)
