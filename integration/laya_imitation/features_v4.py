"""EX-130 v4 facts on top of the v2 facts (`features.compute`): known failures and switch-in offense.

`compute(value, calc)` returns the v2 facts plus `v4`:
- `fails`: {move action: outcome} for options the visible state decides as not working (`fails`, `immune`,
  `absorbed`, `reflected`), from the engine-checked EX-126 rules (`effect_knowledge.option_outcomes`; an unrevealed
  foe Ability or item counts only when every case agrees). Tera Blast / Tera Starstorm keep their Tera action open
  because Terastallizing changes their type.
- `out`: {switch action: {move, min, max}}, the strongest attack of that switch-in on the active foe, through the
  same pinned calculator and the v2 assumed foe set (`features._opp_spec`).
"""
from __future__ import annotations
import json

from . import dex_v2, features
from .effect_knowledge import option_outcomes

FAILING = ('fails', 'immune', 'absorbed', 'reflected')
TERA_TYPED = ('terablast', 'terastarstorm')


def known_failures(value):
    out = {}
    for action_id, label in option_outcomes(dict(input=value.body)).items():
        _, move, mode = action_id.split(':')
        if label in FAILING and not (mode == 'tera' and move in TERA_TYPED):
            out[action_id] = label
    return out


def compute(value, calc):
    facts = features.compute(value, calc)
    snapshot = json.loads(value.body['state'])['snapshot']
    own = {m['slot']: m for m in snapshot['own_team']}
    opp = {m['slot']: m for m in snapshot['opponent_team']}
    foe = opp.get(snapshot['opponent_active_slot']) if snapshot['opponent_active_slot'] else None
    v4 = dict(fails=known_failures(value), out={})
    facts['v4'] = v4
    if foe is None:
        return facts
    defender, _ = features._opp_spec(foe)
    moves = dex_v2.load()['moves']
    requests, slots = [], []
    for action_id in value.action_ids:
        if not action_id.startswith('switch:'):
            continue
        mon = own[int(action_id.split(':')[1])]
        attacker = features._own_spec(mon, active=False)
        for m in mon['moves']:
            info = moves.get(m['id'])
            if info is None or info['category'] == 'status':
                continue
            requests.append(dict(attacker=attacker, defender=defender, move=m['id'], weather=snapshot['weather'],
                                 field=snapshot['field'], attacker_side=snapshot['own_side_conditions'],
                                 defender_side=snapshot['opponent_side_conditions']))
            slots.append((action_id, m['id']))
    results = calc.run(requests) if requests else []
    for (action_id, move), result in zip(slots, results, strict=True):
        if 'error' in result:
            v4['out'].setdefault(action_id, dict(error=result['error']))
            continue
        cur = v4['out'].get(action_id)
        if cur is None or 'error' in cur or (result['max'], move) > (cur['max'], cur['move']):
            v4['out'][action_id] = dict(move=move, min=result['min'], max=result['max'])
    return facts
