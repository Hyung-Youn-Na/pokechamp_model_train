"""v10 lock facts (D-204 decision 2, #27-32) from the public state and the whole-game history.

- `options`: {move action: mark} for my move options that would lock me: a working Choice item (one received through
  Trick included) or Gorilla Tactics -> `locks`; Outrage / Thrash / Petal Dance -> `locks 2-3t confuse`, Rollout /
  Ice Ball -> `locks 5t`, Uproar -> `locks 3t`. Trick / Switcheroo hand the item away, so they get no mark.
- `me` / `opp`: (move, cause) when that active Pokemon is already locked: a working Choice item or Gorilla Tactics and
  a move chosen since it came in, or a lock move used last turn without a fatigue end.
- `opp_likely`: (move, p) for a foe whose item is unknown, that chose the same attacking move every time since it came
  in, when the usage share of Choice items (or of an unrevealed Gorilla Tactics) is at least LIKELY_FLOOR.
"""
from __future__ import annotations
import json

from integration.laya_imitation import dex_v2, features_v3

from . import history

CHOICE = ('choiceband', 'choicespecs', 'choicescarf')
CONSECUTIVE = {'outrage': '2-3t confuse', 'thrash': '2-3t confuse', 'petaldance': '2-3t confuse',
               'rollout': '5t', 'iceball': '5t', 'uproar': '3t'}
HANDS_OVER = ('trick', 'switcheroo')
LIKELY_FLOOR = 0.15


def _item_works(mon, snapshot):
    return mon['ability'] != 'klutz' and 'magic_room' not in snapshot['field'] and 'embargo' not in mon['effects']


def own_cause(mon, snapshot):
    ability = mon['ability'] or dex_v2.to_id(mon['original_set'].get('ability'))
    if mon['item'] in CHOICE and _item_works(mon, snapshot):
        return mon['item']
    return 'gorillatactics' if ability == 'gorillatactics' else None


def opp_cause(mon, snapshot):
    held = (mon.get('item_state') or {}).get('state') == 'held'
    if held and mon['item_state']['item'] in CHOICE and _item_works(mon, snapshot):
        return mon['item_state']['item']
    return 'gorillatactics' if mon['ability'] == 'gorillatactics' else None


def _attacking(move):
    facts = dex_v2.load()['moves'].get(move)
    return facts is not None and facts['category'] != 'status'


def _locked(evts, side, turn, cause):
    last = history.last_turn_move(evts, side, turn)
    if last in CONSECUTIVE and not history.fatigued(evts, side, turn):
        return last, CONSECUTIVE[last].split()[0]
    chosen = history.since_switch_in(evts, side)
    if cause and chosen:
        return chosen[-1], cause
    return None


def likely_share(mon):
    key = features_v3.species_key(mon['species'])
    if key is None:
        return 0.0
    u = features_v3.usage()[key]
    item = sum(p for k, p in features_v3._norm(features_v3._top(u['items'])) if k in CHOICE)
    ability = 0.0 if mon['ability'] else \
        sum(p for k, p in features_v3._norm(features_v3._top(u['abilities'])) if k == 'gorillatactics')
    return 1.0 - (1.0 - item) * (1.0 - ability)


def compute(value):
    """Lock facts of one `ImitationInput` (with `early_history` when the caller has it)."""
    snapshot = json.loads(value.body['state'])['snapshot']
    evts = history.events(snapshot)
    turn = snapshot['turn']
    own = {m['slot']: m for m in snapshot['own_team']}
    opp = {m['slot']: m for m in snapshot['opponent_team']}
    me = own.get(snapshot['own_active_slot']) if snapshot['own_active_slot'] else None
    foe = opp.get(snapshot['opponent_active_slot']) if snapshot['opponent_active_slot'] else None
    out = dict(options={}, me=None, opp=None, opp_likely=None)
    if me is not None and me['status'] != 'fnt':
        cause = own_cause(me, snapshot)
        for action_id in value.action_ids:
            kind, *rest = action_id.split(':')
            if kind != 'move':
                continue
            if rest[0] in CONSECUTIVE:
                out['options'][action_id] = 'locks ' + CONSECUTIVE[rest[0]]
            elif cause and rest[0] not in HANDS_OVER:
                out['options'][action_id] = 'locks'
        if snapshot['decision_kind'] == 'turn_action':
            out['me'] = _locked(evts, '@self', turn, cause)
    if foe is not None and foe['status'] != 'fnt':
        out['opp'] = _locked(evts, '@opponent', turn, opp_cause(foe, snapshot))
        unknown = (foe.get('item_state') or {}).get('state', 'unknown' if not foe['item'] else 'held') == 'unknown'
        chosen = history.since_switch_in(evts, '@opponent')
        if out['opp'] is None and unknown and chosen and len(set(chosen)) == 1 and _attacking(chosen[-1]):
            p = likely_share(foe)
            if p >= LIKELY_FLOOR:
                out['opp_likely'] = (chosen[-1], round(p, 4))
    return out
