"""Opponent team sets sampled from the frozen usage table, consistent with what is public (EP-229 stage 1).

For each opponent preview slot (the model's `opponent_team` entry): revealed moves are kept and the rest are drawn
without replacement in proportion to their usage share (up to four moves); a revealed item, ability or Tera type is
kept, otherwise each is drawn from its usage distribution, as is the nature/EV spread. Species without a usage entry
keep only what is revealed. Moves are treated as independent given the species (as the v7 set estimate does).
"""
from __future__ import annotations
import json
import random
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
USAGE = ROOT / 'integration/laya_imitation/usage_sets_v3.json'
STATS = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')
FULL_IVS = {s: 31 for s in STATS}


@lru_cache(maxsize=None)
def usage():
    return json.loads(USAGE.read_text())['pokemon']


def _draw(rng, dist, exclude=()):
    items = [(k, v) for k, v in sorted(dist.items()) if k not in exclude and v > 0]
    if not items:
        return None
    total = sum(v for _, v in items)
    u, acc = rng.random() * total, 0.0
    for k, v in items:
        acc += v
        if u <= acc:
            return k
    return items[-1][0]


def known_item(mon):
    """The original item when public: held, knocked off, consumed or otherwise revealed; else None."""
    state = mon.get('item_state') or {}
    return state.get('item') or mon.get('item') or None


def sample_set(mon, rng):
    u = usage().get(mon['species'], {})
    moves = [m['id'] for m in mon.get('moves') or []][:4]
    while len(moves) < 4:
        m = _draw(rng, u.get('moves', {}), exclude=moves)
        if m is None:
            break
        moves.append(m)
    spread = _draw(rng, u.get('spreads', {}))
    nature, evs = 'serious', {s: 84 for s in STATS}
    if spread:
        nature, values = spread.split(':')
        evs = dict(zip(STATS, map(int, values.split('/'))))
    tera = mon.get('tera_type') if mon.get('terastallized') or mon.get('tera_type') else None
    return dict(species=mon['species'], item=known_item(mon) or _draw(rng, u.get('items', {})) or '',
                ability=mon.get('ability') or _draw(rng, u.get('abilities', {})) or '',
                moves=moves, nature=nature.lower(), evs=evs, ivs=dict(FULL_IVS), level=100,
                teraType=tera or _draw(rng, u.get('tera_types', {})) or mon['types'][0])


def sample_team(opponent_team, rng):
    """Six sets in preview (slot) order for the model's `opponent_team`."""
    return [sample_set(mon, rng) for mon in sorted(opponent_team, key=lambda m: m['slot'])]


def sample_teams(opponent_team, n, seed):
    rng = random.Random(seed)
    return [sample_team(opponent_team, rng) for _ in range(n)]
