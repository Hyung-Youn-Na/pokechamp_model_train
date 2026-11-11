"""One-turn damage estimate shared by the read opponent (EX-163) and the mixing rule (EX-164).

Deliberately coarse and public-information only: base stats with neutral 84-EV spreads, level 100, average roll,
STAB 1.5, the type chart of `laya_imitation/dex_gen9.json` and the ability immunities below when the ability is
known or is the species' only possible one. No items, boosts, weather, crits or variable-power formulas (moves with
power 0 count as 60). The result is a percentage of the defender's maximum HP, capped at its current HP.
"""
from __future__ import annotations
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEX = ROOT / 'integration/laya_imitation/dex_gen9.json'
POKEDEX = ROOT / 'pokechamp/poke_env/data/static/pokedex/gen9pokedex.json'
USAGE = ROOT / 'integration/laya_imitation/usage_sets_v3.json'

VARIABLE_POWER = 60
ROLL = 0.925
# ability id -> {attacking type: multiplier}
ABILITY = {'levitate': {'ground': 0.0}, 'eartheater': {'ground': 0.0}, 'flashfire': {'fire': 0.0},
           'wellbakedbody': {'fire': 0.0}, 'waterabsorb': {'water': 0.0}, 'stormdrain': {'water': 0.0},
           'dryskin': {'water': 0.0}, 'voltabsorb': {'electric': 0.0}, 'lightningrod': {'electric': 0.0},
           'motordrive': {'electric': 0.0}, 'sapsipper': {'grass': 0.0}, 'thickfat': {'fire': 0.5, 'ice': 0.5},
           'purifyingsalt': {'ghost': 0.5}, 'heatproof': {'fire': 0.5}, 'waterbubble': {'fire': 0.5}}
DEFENSIVE_STAT = {'psyshock': 'def', 'psystrike': 'def', 'secretsword': 'def'}


def _id(text):
    return ''.join(ch for ch in str(text).lower() if ch.isalnum())


@lru_cache(maxsize=None)
def _dex():
    return json.loads(DEX.read_text())


@lru_cache(maxsize=None)
def _pokedex():
    return json.loads(POKEDEX.read_text())


@lru_cache(maxsize=None)
def _usage():
    return json.loads(USAGE.read_text())['pokemon']


def move(move_id):
    """{category, power, type} or None for an unknown move."""
    return _dex()['moves'].get(_id(move_id))


def damaging(move_id):
    m = move(move_id)
    return m is not None and m['category'] != 'status'


def species(name):
    return _pokedex().get(_id(name))


def sole_ability(name):
    entry = species(name)
    if not entry:
        return None
    values = {_id(v) for v in entry.get('abilities', {}).values()}
    return values.pop() if len(values) == 1 else None


def effectiveness(move_type, defender_types, ability=None):
    chart = _dex()['attack'][move_type]
    value = 1.0
    for t in defender_types:
        if t and _id(t) in chart:   # unknown types (e.g. stellar) count as neutral
            value *= chart[_id(t)]
    return value * ABILITY.get(_id(ability) if ability else '', {}).get(move_type, 1.0)


def usage_moves(name, floor):
    """Damaging moves of the species' usage set with share >= floor, highest share first."""
    moves = _usage().get(_id(name), {}).get('moves', {})
    return [m for m, share in sorted(moves.items(), key=lambda kv: (-kv[1], kv[0])) if share >= floor and damaging(m)]


def _stat(base):
    return 2 * base + 57


def _hp(base):
    return 2 * base + 162


def damage(move_id, attacker, attacker_types, defender, defender_types, defender_hp=100.0, defender_ability=None):
    """Estimated % of the defender's max HP (capped at `defender_hp`); 0 for status or unknown moves/species."""
    m = move(move_id)
    a, d = species(attacker), species(defender)
    if m is None or m['category'] == 'status' or a is None or d is None:
        return 0.0
    ability = defender_ability or sole_ability(defender)
    eff = effectiveness(m['type'], defender_types, ability)
    if eff == 0:
        return 0.0
    physical = m['category'] == 'physical'
    key = _id(move_id)
    if key == 'bodypress':
        attack = _stat(a['baseStats']['def'])
    elif key == 'foulplay':
        attack = _stat(d['baseStats']['atk'])
    else:
        attack = _stat(a['baseStats']['atk' if physical else 'spa'])
    defence = _stat(d['baseStats'][DEFENSIVE_STAT.get(key, 'def' if physical else 'spd')])
    power = m['power'] or VARIABLE_POWER
    stab = 1.5 if m['type'] in {_id(t) for t in attacker_types if t} else 1.0
    raw = (42 * power * attack / defence / 50 + 2) * stab * eff * ROLL
    return min(100.0 * raw / _hp(d['baseStats']['hp']), float(defender_hp))


def identity():
    from integration.laya_imitation.storage import sha
    return dict(dex=sha(DEX), pokedex=sha(POKEDEX), usage=sha(USAGE), variable_power=VARIABLE_POWER, roll=ROLL)
