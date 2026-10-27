"""EX-136 v5 facts (D-195): v4 facts on an item-resolved snapshot, plus the opponent item/counter block.

Needs the D-195 parser fields (`item_state`, `status_counter`, `status_source`, `weather_turn`); EX-071 prepared rows
get them from `laya-item-state/v1` (`item_state.merge`). `compute(value, calc)`:
- resolves each opponent item from `item_state` (held -> that item, removed/unknown -> None) and runs
  `features_v4.compute` on that snapshot, so Knock Off power, Choice Scarf speed, the EX-126 failure rules and the
  calculator see effect-revealed items (Leftovers, Rocky Helmet, ...) and never a removed one;
- when the active foe's item is removed, or unknown with an assumed-set Air Balloon, recomputes every damage figure
  (`dmg`, `hit`, `out`) with no foe item: a removed item is gone and Air Balloon is never assumed. Ground moves
  against an unknown-item foe whose assumed set holds Air Balloon are listed in `v5.balloon` (`; balloon?`);
- shows ground moves as `x0` against a foe with a held Air Balloon or a revealed Levitate.
`features.py` / `features_v4.py` stay byte-identical: the v2-v4 servers check them against their datasets.
"""
from __future__ import annotations
import copy
import json

from integration.pokechamp.imitation.schema import ImitationInput
from integration.pokechamp.imitation.storage import canonical

from . import dex_v2, features, features_v4

IGNORES_ABILITY = ('moldbreaker', 'teravolt', 'turboblaze')


def has_fields(snapshot):
    return 'weather_turn' in snapshot and all('item_state' in m for m in snapshot['opponent_team'])


def resolved(value):
    """The same input with every opponent `item` taken from `item_state` (held -> item, otherwise None)."""
    body = value.body
    state = json.loads(body['state'])
    snapshot = state['snapshot']
    if not has_fields(snapshot):
        raise ValueError('v5 needs the D-195 snapshot fields (item_state, weather_turn)')
    view = copy.deepcopy(snapshot)
    for mon in view['opponent_team']:
        held = mon['item_state']
        mon['item'] = held['item'] if held['state'] == 'held' else None
    return ImitationInput.from_body(dict(body, state=canonical(dict(state, snapshot=view)))), view


def _damage(value, view, calc, facts, opp_spec):
    """Redo `features.compute`'s damage requests and `features_v4`'s `out` with a given foe spec."""
    own = {m['slot']: m for m in view['own_team']}
    me = own.get(view['own_active_slot']) if view['own_active_slot'] else None
    foe = {m['slot']: m for m in view['opponent_team']}[view['opponent_active_slot']]
    moves = dex_v2.load()['moves']
    requests, slots = [], []
    side = lambda a, d: dict(weather=view['weather'], field=view['field'], attacker_side=view[a], defender_side=view[d])
    for action_id in value.action_ids:
        kind, *rest = action_id.split(':')
        if kind == 'move' and action_id in facts['damage']:
            tera = me['original_set'].get('teraType', me['tera_type']) if rest[1] == 'tera' else None
            tera = dex_v2.to_id(tera) if tera else None
            requests.append(dict(attacker=features._own_spec(me, tera), defender=opp_spec, move=rest[0],
                                 **side('own_side_conditions', 'opponent_side_conditions')))
            slots.append(('move', action_id, rest[0]))
        elif kind == 'switch':
            mon = own[int(rest[0])]
            for m in foe['moves']:
                info = moves.get(m['id'])
                if info is not None and info['category'] != 'status':
                    requests.append(dict(attacker=opp_spec, defender=features._own_spec(mon, active=False), move=m['id'],
                                         **side('opponent_side_conditions', 'own_side_conditions')))
                    slots.append(('hit', action_id, m['id']))
            attacker = features._own_spec(mon, active=False)
            for m in mon['moves']:
                info = moves.get(m['id'])
                if info is not None and info['category'] != 'status':
                    requests.append(dict(attacker=attacker, defender=opp_spec, move=m['id'],
                                         **side('own_side_conditions', 'opponent_side_conditions')))
                    slots.append(('out', action_id, m['id']))
    results = calc.run(requests) if requests else []
    hits, outs = {}, {}
    for (kind, action_id, move), result in zip(slots, results, strict=True):
        if kind == 'move':
            facts['damage'][action_id] = result
            continue
        target = hits if kind == 'hit' else outs
        if 'error' in result:
            target.setdefault(action_id, dict(error=result['error']))
            continue
        cur = target.get(action_id)
        if cur is None or 'error' in cur or (result['max'], move) > (cur['max'], cur['move']):
            target[action_id] = dict(result, move=move) if kind == 'hit' else dict(move=move, min=result['min'],
                                                                                  max=result['max'])
    for action_id in [a for a in facts['damage'] if a.startswith('switch:')]:
        facts['damage'].pop(action_id)
    facts['damage'].update(hits)
    facts['v4']['out'] = outs


def compute(value, calc):
    resolved_value, view = resolved(value)
    facts = features_v4.compute(resolved_value, calc)
    v5 = dict(foe_item=None, recomputed=False, balloon=[], grounded_x0=[])
    facts['v5'] = v5
    if not view['opponent_active_slot']:
        return facts
    foe = {m['slot']: m for m in view['opponent_team']}[view['opponent_active_slot']]
    held = foe['item_state']
    v5['foe_item'] = held
    opp_spec, _ = features._opp_spec(foe)
    assumed_balloon = held['state'] == 'unknown' and opp_spec['item'] == 'airballoon'
    if held['state'] == 'removed' or assumed_balloon:
        opp_spec = dict(opp_spec, item='')
        _damage(resolved_value, view, calc, facts, opp_spec)
        v5['recomputed'] = True
    own = {m['slot']: m for m in view['own_team']}
    me = own.get(view['own_active_slot']) if view['own_active_slot'] else None
    attacker_ability = (me['ability'] or dex_v2.to_id(me['original_set'].get('ability'))) if me else ''
    floating = foe['item'] == 'airballoon' or foe['ability'] == 'levitate'
    for action_id, fact in facts['moves'].items():
        if fact['category'] == 'status' or fact['type'] != 'ground':
            continue
        if assumed_balloon:
            v5['balloon'].append(action_id)
        if floating and attacker_ability not in IGNORES_ABILITY and fact.get('mult') not in (None, 0):
            fact['mult'] = 0
            v5['grounded_x0'].append(action_id)
    return facts
