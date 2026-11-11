"""EX-149 v7 opponent-set facts (D-200): usage-based guesses for the foe's hidden slots, from the snapshot alone.

`compute(value)` needs no damage calculator. It reads the item-state-resolved snapshot (`features_v5.resolved`) and the
pinned usage file of EX-128 (`usage_sets_v3.json`, through `features_v3`), and returns:
- `active`: the active foe's hidden slots. Item only when its `item_state` is `unknown` (a held or removed item is
  known); ability and Tera only when unknown; moves as v3 does (marginal inclusion rescaled to the `4 - revealed` slots),
  shown from MOVE_FLOOR, at most MOVE_LIMIT.
- `watch`: game-changing items / moves of the active foe that are still hidden with probability >= WATCH_FLOOR.
- `bench`: per living benched foe, the top hidden item (>= BENCH_ITEM_FLOOR) and up to BENCH_MOVES hidden moves
  (>= BENCH_MOVE_FLOOR).
- `fails_tc`: when either active has a `typechange` effect (Protean, Libero, ...), v4's `effect_knowledge` marks nothing;
  here only the type-independent hazard rule is applied (a foe-side hazard at its maximum layers fails, unless the foe
  may bounce it).
"""
from __future__ import annotations
import json

from . import features_v3
from .effect_knowledge import _layers, move, rules

SHOW_FLOOR = 0.15
MOVE_FLOOR = 0.25
MOVE_LIMIT = 6
WATCH_FLOOR = 0.15
WATCH_ITEMS = ('choicescarf', 'choiceband', 'choicespecs', 'focussash', 'boosterenergy', 'weaknesspolicy', 'redcard',
               'ejectbutton', 'ejectpack', 'airballoon')
WATCH_MOVES = ('trick', 'switcheroo', 'encore', 'destinybond', 'memento', 'healingwish', 'lunardance', 'partingshot',
               'shedtail', 'whirlwind', 'roar', 'dragontail', 'haze', 'clearsmog', 'taunt', 'knockoff', 'suckerpunch',
               'extremespeed', 'swordsdance', 'dragondance', 'nastyplot', 'calmmind', 'quiverdance', 'shellsmash',
               'bellydrum', 'curse', 'bulkup', 'irondefense', 'substitute', 'spore', 'sleeppowder', 'yawn')
BENCH_ITEM_FLOOR = 0.30
BENCH_MOVE_FLOOR = 0.30
BENCH_MOVES = 2


def _item_hidden(mon):
    state = (mon.get('item_state') or {}).get('state')
    return state == 'unknown' if state else not mon['item']


def _moves(mon, u):
    revealed = [m['id'] for m in mon['moves']]
    slots = max(0, 4 - len(revealed))
    unseen = features_v3._top(u['moves'], exclude=set(revealed))
    mass = sum(p for _, p in unseen)
    scale = slots / mass if slots and mass > 0 else 0.0
    return [(m, min(1.0, p * scale)) for m, p in unseen] if scale else []


def _round(pairs):
    return [[k, round(p, 4)] for k, p in pairs]


def active_set(foe, can_tera):
    key = features_v3.species_key(foe['species'])
    if key is None:
        return dict(source='default', species=foe['species']), []
    u = features_v3.usage()[key]
    item = features_v3._norm(features_v3._top(u['items'])) if _item_hidden(foe) else []
    ability = features_v3._norm(features_v3._top(u['abilities'])) if not foe['ability'] else []
    tera = features_v3._norm(features_v3._top(u['tera_types'])) \
        if can_tera and not foe['terastallized'] and not foe['tera_type'] else []
    moves = _moves(foe, u)
    shown = dict(source='usage', species=foe['species'],
                 item=_round([(k, p) for k, p in item if p >= SHOW_FLOOR][:2]),
                 ability=_round([(k, p) for k, p in ability if p >= SHOW_FLOOR][:2]),
                 tera=_round([(k, p) for k, p in tera if p >= SHOW_FLOOR][:2]),
                 moves=_round([(m, p) for m, p in moves if p >= MOVE_FLOOR][:MOVE_LIMIT]))
    watch = [(k, p) for k, p in item if k in WATCH_ITEMS and p >= WATCH_FLOOR] + \
        [(m, p) for m, p in moves if m in WATCH_MOVES and p >= WATCH_FLOOR]
    return shown, _round(sorted(watch, key=lambda kv: (-kv[1], kv[0])))


def bench_set(mon):
    key = features_v3.species_key(mon['species'])
    if key is None:
        return None
    u = features_v3.usage()[key]
    item = features_v3._norm(features_v3._top(u['items'])) if _item_hidden(mon) else []
    item = [(k, p) for k, p in item[:1] if p >= BENCH_ITEM_FLOOR]
    moves = [(m, p) for m, p in _moves(mon, u) if p >= BENCH_MOVE_FLOOR][:BENCH_MOVES]
    if not item and not moves:
        return None
    return dict(item=_round(item), moves=_round(moves))


def typechange_failures(view, action_ids):
    """{move action id: 'fails'} from the hazard-layer rule only, for snapshots where v4 marks nothing (typechange)."""
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me = own.get(view['own_active_slot']) if view['own_active_slot'] else None
    foe = opp.get(view['opponent_active_slot']) if view['opponent_active_slot'] else None
    if me is None or foe is None or view['decision_kind'] != 'turn_action':
        return {}
    if 'typechange' not in (me['effects'] or ()) and 'typechange' not in (foe['effects'] or ()):
        return {}
    if foe['ability'] in (None, 'magicbounce'):
        species = features_v3.species_key(foe['species'])
        abilities = features_v3.usage().get(species, {}).get('abilities', {}) if species else {}
        if foe['ability'] == 'magicbounce' or abilities.get('magicbounce', 0) > 0 or species is None:
            return {}
    hazards = rules()['hazards']
    out = {}
    for action_id in action_ids:
        kind, *rest = action_id.split(':')
        if kind != 'move' or rest[0] not in hazards:
            continue
        try:
            target = move(rest[0])['target']
        except KeyError:
            continue
        key, most = hazards[rest[0]]
        if target == 'foeSide' and _layers(view['opponent_side_conditions'], key) >= most:
            out[action_id] = 'fails'
    return out


def compute(value):
    from .features_v5 import resolved
    _, view = resolved(value)
    opp = {m['slot']: m for m in view['opponent_team']}
    foe = opp.get(view['opponent_active_slot']) if view['opponent_active_slot'] else None
    out = dict(active=None, watch=[], bench={}, fails_tc=typechange_failures(view, value.action_ids))
    if foe is not None and foe['status'] != 'fnt':
        out['active'], out['watch'] = active_set(foe, view['opponent_can_tera'])
    for slot, mon in sorted(opp.items()):
        if mon is foe or mon['status'] == 'fnt':
            continue
        b = bench_set(mon)
        if b is not None:
            out['bench'][str(slot)] = b
    return out


def digest():
    return features_v3.digest()


def dumps(facts):
    return json.dumps(facts, sort_keys=True)
