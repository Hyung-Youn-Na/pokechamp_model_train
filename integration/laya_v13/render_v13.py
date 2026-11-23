"""laya-compact-v13 (D-218 / EP-240): v12 plus input bugfixes revealed by EX-203 1500+ / top-bot audit.

`install()` applies v12 (`render_v12.install`) and then, in this process only (no file of laya_imitation /
laya_threat / laya_v10 / laya_v11 / laya_v12 is edited):
1. `formespec`:
   - `features._assumed` resolves battle-changed formes (`ogerponwellspringtera`, `keldeoresolute`, etc.) back to
     their base species in `assumed_sets_v2.json` instead of falling back to 0-Atk/0-SpA/no-item `default`;
   - `spreads.opp_spec` also conditions from `usage()` when `source == 'default'` and the species is in usage;
   - `sets.candidates` maps post-Tera/forme abilities (`embodyaspect*`, `teraformzero`) back to the pre-Tera set
     ability so joint-set conditioning keeps working after Terastallization.
2. `teradefence`:
   - `strategy.tera_defence` evaluates ALL plausible foe threat variants (`threat.candidate_moves` x
     `candidate_items` x `candidate_teras`) against `me` with its Tera type, instead of only re-evaluating the
     single pre-Tera worst move (which hid newly fatal moves like Tera-Water Ivy Cudgel vs Tera-Dark Dondozo).
3. `roostground`:
   - when `me` is Flying-type and not strictly slower than `foe`, `move:roost:normal` (and `move:roost:tera` when
     Tera is Flying) computes the foe's worst plausible hit against Roost-grounded `me` and appends
     `; grounded takes <move> <lo>-<hi>%` when it exceeds the pre-Roost threat;
   - in `duel`, if `me`'s only reliable recovery is `roost` and faster `roost` exposes `me` to >= 50% damage from
     the foe's likely attacks while grounded, `lose` is not flipped to `even`.
4. `ivycudgel`:
   - `features.effective_move` assigns Ivy Cudgel its forme/mask type (`water`, `fire`, `rock`) and STAB so switch
     `worst x2` summaries and move effectiveness are exact.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from integration.laya_imitation import dex_v2, features, features_v3, features_v5, features_v7
from integration.laya_threat import render_v9, spreads, threat
from integration.laya_v10 import render_v10, strategy
from integration.laya_v11 import render_v11
from integration.laya_v12 import observe, render_v12, sets

HERE = Path(__file__).resolve().parent
MARKS = ('formespec', 'teradefence', 'roostground', 'ivycudgel')

EXTRA_FORMES = {
    'ogerponwellspringtera': 'ogerponwellspring',
    'ogerponhearthflametera': 'ogerponhearthflame',
    'ogerponcornerstonetera': 'ogerponcornerstone',
    'ogerpontealtera': 'ogerpon',
    'palafinhero': 'palafin',
    'terapagosstellar': 'terapagos',
    'terapagosterastal': 'terapagos',
    'zamazentacrowned': 'zamazenta',
    'zaciancrowned': 'zacian',
}

ABILITY_PRE_FORME = {
    'embodyaspectteal': 'defiant',
    'embodyaspectwellspring': 'waterabsorb',
    'embodyaspecthearthflame': 'moldbreaker',
    'embodyaspectcornerstone': 'sturdy',
    'teraformzero': 'terashell',
}

IVY_CUDGEL_SPECIES = {
    'ogerponwellspring': 'water',
    'ogerponwellspringtera': 'water',
    'ogerponhearthflame': 'fire',
    'ogerponhearthflametera': 'fire',
    'ogerponcornerstone': 'rock',
    'ogerponcornerstonetera': 'rock',
}

IVY_CUDGEL_ITEM = {
    'wellspringmask': 'water',
    'hearthflamemask': 'fire',
    'cornerstonemask': 'rock',
}

_installed = False
_original = {}
VERSION = None


# ----------------------------------------------------------------------------- 1. formespec

def _base_candidates(species):
    out = []
    for cand in (
        EXTRA_FORMES.get(species),
        observe.canon(species),
        render_v11.FORMES.get(species),
        render_v11.FORMES.get(observe.canon(species)),
        features_v3.species_key(species),
    ):
        if cand and cand != species and cand not in out:
            out.append(cand)
    return out


def assumed(mon):
    source, a = _original['assumed'](mon)
    if source != 'default':
        return source, a
    table = dex_v2.assumed()
    for cand in _base_candidates(mon['species']):
        entry = table.get(cand)
        if entry is not None:
            return 'corpus', entry['set']
    return source, a


def opp_spec(mon):
    spec, source = _original['opp_spec'](mon)
    ctx = render_v12._ctx
    if ctx is None or source != 'default':
        return spec, source
    key = features_v3.species_key(mon['species'])
    if key is None or key not in ctx.foes:
        return spec, source
    entry = render_v12.usage().get(key)
    if not entry:
        return spec, source
    foe = ctx.obs.foe(mon['species'])
    hidden_item = not mon.get('item') and ((mon.get('item_state') or {}).get('state') in (None, 'unknown'))
    out = dict(spec)
    items = entry.get('items') or {}
    if hidden_item and items:
        top_item, _ = max(items.items(), key=lambda kv: (kv[1], kv[0]))
        out['item'] = top_item
    abilities = entry.get('abilities') or {}
    if not mon.get('ability') and abilities:
        top_ab, _ = max(abilities.items(), key=lambda kv: (kv[1], kv[0]))
        out['ability'] = top_ab
    spread_table = entry.get('spreads') or {}
    if spread_table:
        top_sp, _ = max(spread_table.items(), key=lambda kv: (kv[1], kv[0]))
        nature, evs = sets._parse_spread(top_sp)
        out['nature'] = nature
        out['evs'] = {k: v for k, v in evs.items() if v}
    if foe is not None and not mon.get('ability') and out.get('ability') in foe.no_abilities and abilities:
        out['ability'] = max(abilities.items(), key=lambda kv: (kv[1], kv[0]))[0]
    out = spreads.fixed(out, mon)[0]
    return out, 'usage'


def sets_candidates(mon, foe, base_spe):
    ab = observe.ident(mon.get('ability') or '')
    mapped = ABILITY_PRE_FORME.get(ab)
    if mapped:
        mon = dict(mon, ability=mapped)
    return _original['sets_candidates'](mon, foe, base_spe)


# ----------------------------------------------------------------------------- 4. ivycudgel

def effective_move(move_id, user, target, snapshot, *, ability, item, tera, user_stats=None):
    eff = _original['effective_move'](move_id, user, target, snapshot, ability=ability, item=item, tera=tera,
                                      user_stats=user_stats)
    if eff is None or move_id != 'ivycudgel':
        return eff
    new_type = IVY_CUDGEL_SPECIES.get(user.get('species', '')) or IVY_CUDGEL_ITEM.get(item or '')
    if not new_type or new_type == eff['type']:
        return eff
    stab_types = set(user.get('types') or ())
    if tera and tera != 'stellar':
        stab_types.add(tera)
    if user.get('terastallized') and user.get('tera_type') and user['tera_type'] != 'stellar':
        stab_types.add(user['tera_type'])
    stab = (2 if ability == 'adaptability' else 1) if new_type in stab_types else 0
    return dict(eff, type=new_type, stab=stab, reasons=list(eff['reasons']) + ['mask'])


# ----------------------------------------------------------------------------- 2. teradefence & 3. roostground

def _foe_variants_and_moves(view, foe):
    base, _ = spreads.opp_spec(foe)
    moves = threat.candidate_moves(foe)
    if not moves:
        return [], []
    variants = []
    for item in threat.candidate_items(foe, base['item']):
        spec, _ = spreads.fixed(dict(base, item=item), foe)
        for tera in threat.candidate_teras(foe, view['opponent_can_tera']):
            variants.append((dict(spec, tera=tera), item, tera))
    return variants, moves


def _worst_against(view, foe, defender, calc):
    variants, moves = _foe_variants_and_moves(view, foe)
    if not variants or not moves:
        return None
    side = dict(weather=view['weather'], field=view['field'], attacker_side=view['opponent_side_conditions'],
                defender_side=view['own_side_conditions'])
    requests, labels = [], []
    for spec, _, _ in variants:
        for move in moves:
            requests.append(dict(attacker=spec, defender=defender, move=move, **side))
            labels.append(move)
    best = None
    for move, result in zip(labels, strategy._run(calc, requests), strict=True):
        if 'error' in result:
            continue
        key = (result['max'], result['min'])
        if best is None or key > (best['max'], best['min']):
            best = dict(move=move, min=result['min'], max=result['max'])
    return best


def tera_defence(value, view, worst, calc):
    """#40 fixed: re-evaluate ALL plausible foe attacks against `me` with its Tera type."""
    if worst is None or not view['can_tera']:
        return {}
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me, foe = own[view['own_active_slot']], opp[view['opponent_active_slot']]
    tera = me['original_set'].get('teraType', me['tera_type'])
    tera = dex_v2.to_id(tera) if tera else None
    if not tera or tera == 'stellar':
        return {}
    post = _worst_against(view, foe, features._own_spec(me, tera, active=True), calc)
    if post is None:
        return {}
    if post['max'] < render_v9.ACTIVE_FLOOR and worst['max'] < render_v9.ACTIVE_FLOOR:
        return {}
    if post['move'] == worst['move'] and round(post['min']) == round(worst['min']) \
            and round(post['max']) == round(worst['max']):
        return {}
    return {a: (post['move'], post['min'], post['max']) for a in value.action_ids
            if a.startswith('move:') and a.endswith(':tera')}


def _roost_grounded_type(types_list):
    if 'flying' not in types_list:
        return None
    rest = [t for t in types_list if t != 'flying']
    if len(rest) == 1:
        return rest[0]
    if len(rest) == 0:
        return 'normal'
    return None


def _can_roost_first(facts, first):
    if first is not None:
        return first >= 0.25
    order = (facts.get('speed') or {}).get('order') or ''
    return order in ('first', 'likely first', 'tie')


def _roost_likely_max(view, me, foe, calc, grounded_type):
    revealed = [m['id'] for m in foe['moves'] if strategy._damaging(m['id'])]
    u = strategy._usage(foe)
    hidden = [m for m, _ in features_v7._moves(foe, u) if strategy._damaging(m)] if u else []
    moves = revealed or hidden[:1]
    if not moves:
        return 0.0
    attacker = features._opp_spec(foe)[0]
    defender = dict(features._own_spec(me, active=True), tera=grounded_type)
    side = dict(weather=view['weather'], field=view['field'], attacker_side=view['opponent_side_conditions'],
                defender_side=view['own_side_conditions'])
    results = strategy._run(calc, [dict(attacker=attacker, defender=defender, move=m, **side) for m in moves])
    ok = [r['max'] for r in results if 'error' not in r]
    return max(ok) if ok else 0.0


def _reliable_moves(mon):
    return [m['id'] for m in mon['moves'] if m['id'] in render_v11.RELIABLE and (m.get('pp') is None or m['pp'] > 0)]


def strategy_compute(value, facts, risk, shown_fails, calc):
    out = _original['strategy_compute'](value, facts, risk, shown_fails, calc)
    out['roost_grounded'] = {}
    _, view = features_v5.resolved(value)
    if view['decision_kind'] != 'turn_action':
        return out
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me = own.get(view['own_active_slot']) if view['own_active_slot'] else None
    foe = opp.get(view['opponent_active_slot']) if view['opponent_active_slot'] else None
    if me is None or foe is None or not strategy._alive(me) or not strategy._alive(foe):
        return out

    can_first = _can_roost_first(facts, out.get('first'))
    if can_first:
        cur_types = features._types(me)
        grounded_normal = _roost_grounded_type(cur_types)
        if grounded_normal is not None and 'move:roost:normal' in value.action_ids:
            defender = dict(features._own_spec(me, active=True), tera=grounded_normal)
            gw = _worst_against(view, foe, defender, calc)
            base_max = risk['active']['max'] if risk.get('active') is not None else 0.0
            if gw is not None and gw['max'] >= render_v9.ACTIVE_FLOOR and gw['max'] > base_max + 1.0:
                out['roost_grounded']['move:roost:normal'] = (gw['move'], gw['min'], gw['max'])
        if 'move:roost:tera' in value.action_ids and view.get('can_tera'):
            tera = dex_v2.to_id(me['original_set'].get('teraType', me['tera_type']) or '')
            if tera == 'flying':
                defender = dict(features._own_spec(me, 'flying', active=True), tera='normal')
                gw = _worst_against(view, foe, defender, calc)
                ref = out['tera'].get('move:roost:tera')
                ref_max = ref[2] if ref is not None else (risk['active']['max'] if risk.get('active') is not None else 0.0)
                if gw is not None and gw['max'] >= render_v9.ACTIVE_FLOOR and gw['max'] > ref_max + 1.0:
                    out['roost_grounded']['move:roost:tera'] = (gw['move'], gw['min'], gw['max'])

    # duel fix: if me's only reliable recovery is Roost and faster Roost exposes me to >= 50% grounded damage,
    # do not flip `lose` to `even`.
    d = out.get('duel')
    if d is not None and d['result'] == 'even' and d['me_first'] and d['opp_hits'] is not None and d['opp_hits'] != 1:
        would_lose = d['me_hits'] is None or d['me_hits'] > d['opp_hits']
        grounded_normal = _roost_grounded_type(features._types(me))
        if would_lose and grounded_normal is not None and _reliable_moves(me) == ['roost']:
            likely = out.get('likely')
            if likely is not None and likely['max'] < 50:
                if _roost_likely_max(view, me, foe, calc, grounded_normal) >= 50:
                    out['duel'] = dict(d, result='lose')
    return out


def render(value, facts):
    state, question = _original['render'](value, facts)
    roost_g = (facts.get('strategy') or {}).get('roost_grounded') or {}
    if not roost_g:
        return state, question
    criteria = dict(question['criteria'])
    for action_id, (move, lo, hi) in roost_g.items():
        if action_id in criteria:
            criteria[action_id] += '; grounded takes %s %s-%s%%' % (move, render_v10._pct(lo), render_v10._pct(hi))
    return state, dict(question, criteria=criteria)


def version():
    base = _original['version']()
    return dict(
        base,
        render=VERSION,
        v12_render=render_v12.VERSION,
        v13=dict(
            marks=MARKS,
            extra_formes=EXTRA_FORMES,
            ability_pre_forme=ABILITY_PRE_FORME,
            code={'render_v13.py': hashlib.sha256((HERE / 'render_v13.py').read_bytes()).hexdigest()},
        ),
    )


def install():
    """Apply v12 and then v13 bugfixes to this process (idempotent)."""
    global _installed, VERSION
    if _installed:
        return
    render_v12.install()
    _original.update(
        assumed=features._assumed,
        opp_spec=spreads.opp_spec,
        sets_candidates=sets.candidates,
        effective_move=features.effective_move,
        tera_defence=strategy.tera_defence,
        strategy_compute=strategy.compute,
        render=render_v10.render,
        version=render_v10.version,
    )
    features._assumed = assumed
    spreads.opp_spec = opp_spec
    sets.candidates = sets_candidates
    features.effective_move = effective_move
    strategy.tera_defence = tera_defence
    strategy.compute = strategy_compute
    render_v10.render = render
    render_v10.version = version
    VERSION = render_v12.VERSION.replace('laya-compact-v12[', 'laya-compact-v13[').rstrip(']') + ',' + ','.join(MARKS) + ']'
    _installed = True
