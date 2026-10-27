"""Pinned Gen9 move/type facts for the compact renderer.

`export` runs once under the pokechamp interpreter (poke_env GenData) and writes `dex_gen9.json`;
`load` is stdlib-only, so the laya and pokechamp interpreters render from the same bytes.
"""
from __future__ import annotations
from functools import lru_cache
import hashlib
import json
from pathlib import Path

PATH = Path(__file__).with_name('dex_gen9.json')


def export(path=PATH):
    from poke_env.data import GenData
    data = GenData.from_gen(9)
    moves = {key: dict(type=m['type'].lower(), category=m['category'].lower(), power=int(m.get('basePower') or 0),
                       priority=int(m.get('priority') or 0))
             for key, m in sorted(data.moves.items())}
    chart = {atk.lower(): {d.lower(): float(v) for d, v in sorted(row.items())}
             for atk, row in sorted(data.type_chart.items())}
    # poke_env's chart is indexed [defender][attacker]; store it as attacker -> defender.
    flipped = {a: {d: chart[d][a] for d in chart} for a in chart}
    value = dict(source='poke_env.data.GenData.from_gen(9)', moves=moves, attack=flipped)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def load():
    return json.loads(PATH.read_text())


def digest():
    return hashlib.sha256(PATH.read_bytes()).hexdigest()


def multiplier(attack_type, defender_types):
    """Type-chart product, or None for a type outside the chart (stellar, '???')."""
    chart = load()['attack']
    if attack_type not in chart:
        return None
    value = 1.0
    for t in defender_types:
        value *= chart[attack_type].get(t, 1.0)
    return value


if __name__ == '__main__':
    print(export())
