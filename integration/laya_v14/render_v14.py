"""laya-compact-v14 (D-220 / EP-244): v13 plus recovery-aware and absorb-aware matchup signals.

`install()` applies v13 (`render_v13.install`) and then, in this process only (no frozen package of
`laya_imitation` / `laya_threat` / `laya_v10` / `laya_v11` / `laya_v12` / `laya_v13` is edited):
1. `recoverko`:
   - removes misleading ` 2HKO` tags on move criteria when opponent passive healing (`Leftovers`, `Poison Heal`,
     `Grassy Terrain`), likely drain-move healing (`Draining Kiss`, `Horn Leech`, `Giga Drain`, etc.), or revealed
     50% recovery (`Recover`, `Roost`, etc., vs `<50%` max damage) prevents a genuine 2HKO.
2. `drainheal`:
   - extends `opp heals:` (`strategy.heals`) to report revealed/likely drain moves (`Draining Kiss`, `Horn Leech`,
     `Giga Drain`, `Drain Punch`, `Bitter Blade`, `Matcha Gotcha`, `Leech Life`, `Parabolic Charge`, `Oblivion Wing`)
     and absorb-heal abilities (`Water Absorb`, `Volt Absorb`, `Earth Eater`, `Dry Skin`).
3. `absorbheal`:
   - appends `; heals opp 25%` on attacking moves absorbed for HP by the active opponent's ability
     (`Water Absorb`, `Dry Skin`, `Volt Absorb`, `Earth Eater`), and `; boosts opp` on boost-absorb abilities
     (`Flash Fire`, `Sap Sipper`, `Storm Drain`, `Lightning Rod`, `Motor Drive`, `Well-Baked Body`), respecting
     ability-ignoring attackers (`Mold Breaker`, `Teravolt`, `Turboblaze`).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from integration.laya_imitation import dex_v2, features, features_v3, features_v5, features_v7
from integration.laya_v10 import history, render_v10, strategy
from integration.laya_v11 import render_v11
from integration.laya_v13 import render_v13

HERE = Path(__file__).resolve().parent
MARKS = ('recoverko', 'drainheal', 'absorbheal')

DRAIN_MOVES = tuple(sorted(render_v11.DRAIN))
ABSORB_HEAL = {
    'waterabsorb': 'water',
    'dryskin': 'water',
    'voltabsorb': 'electric',
    'eartheater': 'ground',
}
ABSORB_BOOST = {
    'flashfire': 'fire',
    'sapsipper': 'grass',
    'stormdrain': 'water',
    'lightningrod': 'electric',
    'motordrive': 'electric',
    'wellbakedbody': 'fire',
}
MOLD_BREAKERS = frozenset(('moldbreaker', 'teravolt', 'turboblaze'))
IGNORE_ABILITY_MOVES = frozenset(('sunsteelstrike', 'moongeistbeam', 'photongeyser'))

_installed = False
_original = {}
VERSION = None


def _foe_ability_certain(foe) -> str:
    """Active opponent's revealed ability, or sole known ability when unambiguous (e.g. Ogerpon-Wellspring)."""
    ab = dex_v2.to_id(foe.get('ability') or '')
    if ab:
        return ab
    sp = dex_v2.to_id(foe.get('species') or '')
    if sp == 'ogerponwellspring':
        return 'waterabsorb'
    u = strategy._usage(foe)
    if u and u.get('abilities'):
        top = features_v3._norm(features_v3._top(u['abilities']))
        if top and top[0][1] >= 0.99:
            return dex_v2.to_id(top[0][0])
    return ''


def heals(foe, pp_used):
    """`strategy.heals` extended with drain moves and absorb-heal abilities."""
    out = list(_original['heals'](foe, pp_used))
    have = {(kind, name) for kind, name, _, _ in out}
    used = pp_used.get(foe['species'], {})
    for m in foe['moves']:
        mid = m['id']
        if mid in render_v11.DRAIN and ('move', mid) not in have:
            top = history.max_pp(mid)
            left = None if top is None or mid not in used else max(0, top - used[mid])
            out.append(('move', mid, 'seen', left))
            have.add(('move', mid))
    u = strategy._usage(foe)
    if u:
        for move, p in features_v7._moves(foe, u):
            if move in render_v11.DRAIN and p >= strategy.HEAL_FLOOR and ('move', move) not in have:
                out.append(('move', move, round(p, 4), None))
                have.add(('move', move))
    ab = dex_v2.to_id(foe.get('ability') or '')
    if ab in ABSORB_HEAL and ('ability', ab) not in have:
        out.append(('ability', ab, 'seen', None))
        have.add(('ability', ab))
    elif not ab and u:
        for ability, p in features_v3._norm(features_v3._top(u['abilities'])):
            aid = dex_v2.to_id(ability)
            if aid in ABSORB_HEAL and p >= strategy.HEAL_FLOOR and ('ability', aid) not in have:
                out.append(('ability', aid, round(p, 4), None))
                have.add(('ability', aid))
    return out


def _foe_one_turn_recovery(view, me, foe, facts) -> float:
    """Opponent's expected HP% recovered between our 1st and 2nd hit (passive net heal + likely drain move)."""
    heal_p, chip_p, _ = render_v11.passive(foe, view, False)
    net_passive = max(0.0, heal_p - chip_p)
    likely = (facts.get('strategy') or {}).get('likely')
    drain_back = 0.0
    if likely and likely.get('move') in render_v11.DRAIN and likely.get('min', 0.0) > 0.0:
        mine_hp = render_v11.max_hp(features._own_spec(me, active=True))
        foe_max_hp = render_v11.max_hp(features._opp_spec(foe)[0])
        if foe_max_hp > 0:
            drain_back = render_v11.DRAIN[likely['move']] * float(likely['min']) * float(mine_hp) / float(foe_max_hp)
    return net_passive + drain_back


def render(value, facts):
    state, question = _original['render'](value, facts)
    _, view = features_v5.resolved(value)
    if view.get('decision_kind') != 'turn_action':
        return state, question
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me = own.get(view['own_active_slot']) if view['own_active_slot'] else None
    foe = opp.get(view['opponent_active_slot']) if view['opponent_active_slot'] else None
    if me is None or foe is None or not strategy._alive(me) or not strategy._alive(foe):
        return state, question

    foe_hp = strategy._hp(foe)
    rec1 = _foe_one_turn_recovery(view, me, foe, facts)
    foe_reliable = render_v11._reliable(foe, False)
    foe_ab = _foe_ability_certain(foe)
    me_ab = dex_v2.to_id(me.get('ability') or '')
    inner = facts.get('facts') or facts
    damage_map = inner.get('damage') or {}
    moves_map = inner.get('moves') or {}
    dex_moves = dex_v2.load()['moves']

    criteria = dict(question['criteria'])
    changed = False
    for action_id, text in list(criteria.items()):
        if not action_id.startswith('move:'):
            continue
        parts = action_id.split(':')
        if len(parts) < 3:
            continue
        move_id = parts[1]
        d = damage_map.get(action_id)
        updated = text

        # 1. recoverko: strip misleading 2HKO when opponent recovery prevents 2HKO
        if ' 2HKO' in updated and isinstance(d, dict) and 'error' not in d and d.get('min', 0.0) > 0.0:
            dmin = float(d['min'])
            dmax = float(d.get('max', dmin))
            if dmin < foe_hp:
                hp_after_two = min(100.0, foe_hp - dmin + rec1) - dmin
                if (rec1 > 0.5 and hp_after_two > 1e-6) or (foe_reliable and dmax < 50.0):
                    updated = updated.replace(' 2HKO', '')

        # 2. absorbheal: explicit opponent heal/boost warning on absorbed attacking moves
        if foe_ab and me_ab not in MOLD_BREAKERS and move_id not in IGNORE_ABILITY_MOVES:
            mv_info = moves_map.get(action_id) or dex_moves.get(move_id)
            if mv_info and mv_info.get('category') != 'status':
                eff_type = dex_v2.to_id(mv_info.get('type') or '')
                if ABSORB_HEAL.get(foe_ab) == eff_type and '; heals opp 25%' not in updated:
                    updated += '; heals opp 25%'
                elif ABSORB_BOOST.get(foe_ab) == eff_type and '; boosts opp' not in updated:
                    updated += '; boosts opp'

        if updated != text:
            criteria[action_id] = updated
            changed = True

    if not changed:
        return state, question
    return state, dict(question, criteria=criteria)


def version():
    base = _original['version']()
    return dict(
        base,
        render=VERSION,
        v13_render=render_v13.VERSION,
        v14=dict(
            marks=MARKS,
            drain_moves=DRAIN_MOVES,
            absorb_heal=ABSORB_HEAL,
            absorb_boost=ABSORB_BOOST,
            code={'render_v14.py': hashlib.sha256((HERE / 'render_v14.py').read_bytes()).hexdigest()},
        ),
    )


def install():
    """Apply v13 and then v14 recovery/absorb signals to this process (idempotent)."""
    global _installed, VERSION
    if _installed:
        return
    render_v13.install()
    _original.update(
        heals=strategy.heals,
        render=render_v10.render,
        version=render_v10.version,
    )
    strategy.heals = heals
    render_v10.render = render
    render_v10.version = version
    VERSION = render_v13.VERSION.replace('laya-compact-v13[', 'laya-compact-v14[').rstrip(']') + ',' + ','.join(MARKS) + ']'
    _installed = True
