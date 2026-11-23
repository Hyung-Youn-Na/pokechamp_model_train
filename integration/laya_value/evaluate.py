"""EP-239 EX-199: poke-engine 0.0.48 `src/genx/evaluate.rs` (foul-play MCTS's leaf evaluation) in Python.

    evaluate(state) -> float     side one minus side two, in engine points (100 = one Pokemon's full HP)

A line-by-line port of `evaluate.rs` (gen 9 uses `genx`) over the `poke_engine` Python objects (foul-play venv). The
binding does not expose `evaluate`, and a separate engine build was not available, so the port is checked against the
engine through `mcts()` (`verify_evaluate.py`: states where every leaf under a root move has one known evaluation,
whose average score must equal `sigmoid(evaluate(leaf) - evaluate(root))`).
Move categories (burn) come from foul-play's `fp/data/moves.json` (the engine's own move table is not exposed).
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

POKEMON_ALIVE = 30.0
POKEMON_HP = 100.0
USED_TERA = -75.0
BOOST_WEIGHT = dict(attack_boost=30.0, defense_boost=15.0, special_attack_boost=30.0, special_defense_boost=15.0,
                    speed_boost=30.0)
BOOST_MULTIPLIER = {6: 3.3, 5: 3.15, 4: 3.0, 3: 2.5, 2: 2.0, 1: 1.0, 0: 0.0,
                    -1: -1.0, -2: -2.0, -3: -2.5, -4: -3.0, -5: -3.15, -6: -3.3}
STATUS = dict(freeze=-40.0, sleep=-25.0, paralyze=-25.0)
POKEMON_TOXIC = -30.0
POKEMON_POISONED = -10.0
POKEMON_BURNED = -25.0
LEECH_SEED = -30.0
SUBSTITUTE = 40.0
CONFUSION = -20.0
SIDE = dict(reflect=20.0, light_screen=20.0, aurora_veil=40.0, safeguard=5.0, tailwind=7.0, healing_wish=30.0)
STEALTH_ROCK = -10.0
SPIKES = -7.0
TOXIC_SPIKES = -7.0
STICKY_WEB = -25.0
MOVES = Path(__file__).resolve().parents[2] / '.tools/foul-play/src/fp/data/moves.json'


def norm(value):
    return str(value).lower().replace(' ', '').replace('-', '').replace('_', '')


@lru_cache(maxsize=1)
def _categories():
    return {k: v.get('category') for k, v in json.loads(MOVES.read_text()).items()}


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-0.0125 * x))


def evaluate_poison(p, base):
    a = norm(p.ability)
    if a == 'poisonheal':
        return 15.0
    if a in ('guts', 'marvelscale', 'quickfeet', 'toxicboost', 'magicguard'):
        return 10.0
    return base


def evaluate_burned(p):
    if norm(p.ability) in ('guts', 'marvelscale', 'quickfeet'):
        return -2.0 * POKEMON_BURNED
    cats = _categories()
    multiplier = float(sum(1 for m in p.moves if cats.get(norm(m.id)) == 'physical'))
    if p.special_attack > p.attack:
        multiplier /= 2.0
    return multiplier * POKEMON_BURNED


def has_type(p, t):
    if p.terastallized:                       # the `terastallization` build (foul-play's)
        return norm(p.tera_type) == t
    return t in (norm(p.types[0]), norm(p.types[1]))


def is_grounded(p):
    item = norm(p.item)
    if item == 'ironball':
        return True
    if has_type(p, 'flying') or norm(p.ability) in ('levitate', 'eelevate') or item == 'airballoon':
        return False
    return True


def evaluate_hazards(p, side):
    score = 0.0
    grounded = is_grounded(p)
    sc = side.side_conditions
    if norm(p.item) != 'heavydutyboots':
        if norm(p.ability) != 'magicguard':
            score += sc.stealth_rock * STEALTH_ROCK
            if grounded:
                score += sc.spikes * SPIKES
                score += sc.toxic_spikes * TOXIC_SPIKES
        if grounded:
            score += sc.sticky_web * STICKY_WEB
    return score


def evaluate_pokemon(p):
    score = POKEMON_HP * p.hp / p.maxhp
    status = norm(p.status)
    if status == 'burn':
        score += evaluate_burned(p)
    elif status in STATUS:
        score += STATUS[status]
    elif status == 'toxic':
        score += evaluate_poison(p, POKEMON_TOXIC)
    elif status == 'poison':
        score += evaluate_poison(p, POKEMON_POISONED)
    if norm(p.item) != 'none':
        score += 10.0
    if score < 0.0:
        score = 0.0
    return score + POKEMON_ALIVE


def _side(side):
    score, tera = 0.0, False
    active = int(str(side.active_index))
    vols = {norm(v) for v in side.volatile_statuses}
    for i, p in enumerate(side.pokemon):
        if p.hp > 0:
            score += evaluate_pokemon(p)
            score += evaluate_hazards(p, side)
            if i == active:
                if 'leechseed' in vols:
                    score += LEECH_SEED
                if 'substitute' in vols:
                    score += SUBSTITUTE
                if 'confusion' in vols:
                    score += CONFUSION
                for name, weight in BOOST_WEIGHT.items():
                    score += BOOST_MULTIPLIER[int(getattr(side, name))] * weight
        if p.terastallized:
            tera = True
    if tera:
        score += USED_TERA
    for name, weight in SIDE.items():
        score += getattr(side.side_conditions, name) * weight
    return score


def evaluate(state):
    return _side(state.side_one) - _side(state.side_two)
