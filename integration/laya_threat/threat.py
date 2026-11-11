"""Worst plausible incoming damage from the active foe (D-202 part 2).

v2-v7 show `hit a-b%` on a switch option only for moves the foe has already used, with the assumed item, before any
Tera. A foe that just came in (Chilly Reception, U-turn, a KO) shows nothing, and an unrevealed Choice Specs or a
same-type Tera is never counted. `compute(value, calc)` returns, for the decision's switch options and (on
`turn_action`) the active Pokemon, the strongest result over:
- moves: the revealed attacking moves plus up to HIDDEN_MOVES hidden attacking moves whose v7 likelihood (usage
  inclusion rescaled to the free move slots) is at least MOVE_FLOOR;
- items: a held item as is, a removed one as none; an unknown one as the assumed item plus the most used damage item
  (BOOST_ITEMS) with usage at least ITEM_FLOOR when it differs;
- Tera: the foe's current Tera; or, while the foe can still Terastallize and its Tera is unknown, also the most used
  Tera type with usage at least TERA_FLOOR.
Each item variant gets its own item-consistent spread (`spreads.fixed`). Damage is the pinned calculator's % of the
target's max HP, with the snapshot's weather, field and side conditions, as for `hit`.
"""
from __future__ import annotations
from functools import lru_cache
import json

from integration.laya_imitation import features, features_v3, features_v7

from . import spreads

HIDDEN_MOVES = 4
MOVE_FLOOR = 0.20
ITEM_FLOOR = 0.15
TERA_FLOOR = 0.25
BOOST_ITEMS = ('choicespecs', 'choiceband', 'lifeorb', 'expertbelt')


@lru_cache(maxsize=1)
def _usage():
    return features_v3.usage()


def _attacking(move_id):
    return spreads._category(move_id) in ('physical', 'special')


def candidate_moves(foe):
    revealed = [m['id'] for m in foe['moves'] if _attacking(m['id'])]
    key = features_v3.species_key(foe['species'])
    hidden = []
    if key is not None:
        hidden = [m for m, p in features_v7._moves(foe, _usage()[key]) if p >= MOVE_FLOOR and _attacking(m)]
    return revealed + [m for m in hidden if m not in revealed][:HIDDEN_MOVES]


def candidate_items(foe, base_item):
    state = (foe.get('item_state') or {}).get('state')
    if state == 'held' or (state is None and foe['item']):
        return [base_item]
    if state == 'removed':
        return ['']
    out = [base_item]
    key = features_v3.species_key(foe['species'])
    if key is not None:
        for item, p in features_v3._top(_usage()[key]['items']):
            if item in BOOST_ITEMS and p >= ITEM_FLOOR and item != base_item:
                out.append(item)
                break
    return out


def candidate_teras(foe, can_tera):
    if foe['terastallized']:
        return [foe['tera_type']]
    out = [None]
    key = features_v3.species_key(foe['species'])
    if can_tera and not foe['tera_type'] and key is not None:
        top = features_v3._top(_usage()[key]['tera_types'])
        if top and top[0][1] >= TERA_FLOOR:
            out.append(top[0][0])
    return out


def compute(value, calc):
    """{'active': entry or None, 'switch': {action id: entry}}; entry = min, max, move, item, tera, base_item, item_known."""
    from integration.laya_imitation.features_v5 import resolved
    _, view = resolved(value)
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me = own.get(view['own_active_slot']) if view['own_active_slot'] else None
    foe = opp.get(view['opponent_active_slot']) if view['opponent_active_slot'] else None
    out = dict(active=None, switch={})
    if foe is None or foe['status'] == 'fnt':
        return out
    base, _ = spreads.opp_spec(foe)
    state = (foe.get('item_state') or {}).get('state')
    known = state in ('held', 'removed') or (state is None and bool(foe['item']))
    moves = candidate_moves(foe)
    if not moves:
        return out
    variants = []
    for item in candidate_items(foe, base['item']):
        spec, _ = spreads.fixed(dict(base, item=item), foe)
        for tera in candidate_teras(foe, view['opponent_can_tera']):
            variants.append((dict(spec, tera=tera), item, tera))
    targets = []
    if me is not None and me['status'] != 'fnt' and view['decision_kind'] == 'turn_action':
        targets.append(('active', features._own_spec(me, active=True)))
    for action_id in value.action_ids:
        if action_id.startswith('switch:'):
            mon = own.get(int(action_id.split(':')[1]))
            if mon is not None:
                targets.append((action_id, features._own_spec(mon, active=False)))
    side = dict(weather=view['weather'], field=view['field'], attacker_side=view['opponent_side_conditions'],
                defender_side=view['own_side_conditions'])
    requests, slots = [], []
    for target, defender in targets:
        for spec, item, tera in variants:
            for move in moves:
                requests.append(dict(attacker=spec, defender=defender, move=move, **side))
                slots.append((target, move, item, tera))
    best = {}
    for (target, move, item, tera), result in zip(slots, calc.run(requests) if requests else [], strict=True):
        if 'error' in result:
            continue
        cur = best.get(target)
        if cur is None or (result['max'], result['min']) > (cur['max'], cur['min']):
            best[target] = dict(min=result['min'], max=result['max'], move=move, item=item, tera=tera,
                                base_item=base['item'], item_known=known, terastallized=bool(foe['terastallized']))
    out['active'] = best.pop('active', None)
    out['switch'] = best
    return out


def dumps(facts):
    return json.dumps(facts, sort_keys=True)
