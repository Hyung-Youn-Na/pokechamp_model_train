"""Whole-game public history for the v10 lock and PP rules: the opt-in `early_history` (D-198) + the four-turn `history`.

Each event is `{'turn', 'event', 'args'}` with `args[0]` the side (`@self` / `@opponent`). Moves called by another move
(`[from]`: Sleep Talk, Magic Bounce, Dancer, ...) cost no PP and choose nothing, so they are skipped. Without
`early_history` the window is the four-turn `history` only.
"""
from __future__ import annotations
from functools import lru_cache
import json
from pathlib import Path
import re

from integration.laya_imitation import dex_v2

SWITCH = ('switch', 'drag', 'replace')
PP = Path(__file__).with_name('pp_gen9.json')
EFFECTS = Path(__file__).parents[1] / 'laya_imitation/dex_gen9_effects.json'
SELF_TARGETS = ('self', 'adjacentAllyOrSelf', 'allySide', 'allyTeam', 'allies')


def move_id(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower())


def species_id(name):
    """'Kingambit, M' -> 'kingambit'."""
    return move_id(str(name).split(',')[0])


@lru_cache(maxsize=1)
def base_pp():
    return json.loads(PP.read_text())['pp']


@lru_cache(maxsize=1)
def targets():
    return {k: v['target'] for k, v in json.loads(EFFECTS.read_text())['moves'].items()}


def max_pp(move):
    """Max PP with PP Ups (8/5 of the base; a 1-PP move stays 1), None for an unknown move."""
    base = base_pp().get(move)
    return None if base is None else base if base <= 1 else base * 8 // 5


def events(snapshot):
    return list(snapshot.get('early_history') or []) + list(snapshot['history'])


def _called(e):
    return any(str(a).startswith('[from]') for a in e['args'])


def own_move(e, side):
    return e['event'] == 'move' and e['args'][:1] == [side] and len(e['args']) > 1 and not _called(e)


def since_switch_in(evts, side):
    """Moves `side`'s active Pokemon chose since it last came in, oldest first."""
    out = []
    for e in evts:
        if e['event'] in SWITCH and e['args'][:1] == [side]:
            out = []
        elif own_move(e, side):
            out.append(move_id(e['args'][1]))
    return out


def last_turn_move(evts, side, turn):
    """`side`'s own move on turn `turn` - 1, or None."""
    used = [move_id(e['args'][1]) for e in evts if e['turn'] == turn - 1 and own_move(e, side)]
    return used[-1] if used else None


def fatigued(evts, side, turn):
    """`side` became confused from fatigue (a lock ended) on turn `turn` - 1."""
    return any(e['turn'] == turn - 1 and e['event'] == '-start' and e['args'][:1] == [side] and
               'confusion' in str(e['args'][1:2]).lower() and '[fatigue]' in e['args'] for e in evts)


def opp_pp_used(snapshot):
    """{opponent species: {move: PP used}} over the visible game. Pressure on my active doubles a use aimed at it."""
    ability = {m['species']: m['ability'] or dex_v2.to_id(m['original_set'].get('ability')) for m in snapshot['own_team']}
    active = {'@self': None, '@opponent': None}
    used = {}
    for e in events(snapshot):
        side = e['args'][0] if e['args'] else None
        if e['event'] in SWITCH and side in active and len(e['args']) > 1:
            active[side] = species_id(e['args'][1])
        elif own_move(e, '@opponent') and active['@opponent']:
            move = move_id(e['args'][1])
            cost = 2 if ability.get(active['@self']) == 'pressure' and targets().get(move) not in SELF_TARGETS else 1
            moves = used.setdefault(active['@opponent'], {})
            moves[move] = moves.get(move, 0) + cost
    return used
