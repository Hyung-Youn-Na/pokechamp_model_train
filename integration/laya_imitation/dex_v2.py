"""Pinned Gen9 facts for the v2 renderer (the v1 `dex_gen9.json` stays frozen).

`export` runs once under the pokechamp interpreter (poke_env GenData) and writes `dex_gen9_v2.json`;
`export_assumed` derives per-species modal sets from the EX-071 imputation corpus into
`assumed_sets_v2.json`. `load*` are stdlib-only so the laya and pokechamp interpreters read the same bytes.
"""
from __future__ import annotations
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

PATH = Path(__file__).with_name('dex_gen9_v2.json')
ASSUMED = Path(__file__).with_name('assumed_sets_v2.json')
FLAGS = ('contact', 'sound', 'punch', 'bite', 'slicing', 'pulse', 'bullet')


def to_id(value):
    return re.sub('[^a-z0-9]', '', str(value).lower())


def export(path=PATH):
    from poke_env.data import GenData
    data = GenData.from_gen(9)
    moves = {key: dict(type=m['type'].lower(), category=m['category'].lower(), power=int(m.get('basePower') or 0),
                       priority=int(m.get('priority') or 0),
                       flags=sorted(f for f in FLAGS if (m.get('flags') or {}).get(f)))
             for key, m in sorted(data.moves.items())}
    species = {key: dict(types=[t.lower() for t in p['types']], base={k: int(v) for k, v in p['baseStats'].items()},
                         abilities=sorted(to_id(a) for a in p.get('abilities', {}).values()))
               for key, p in sorted(data.pokedex.items()) if 'baseStats' in p}
    chart = {atk.lower(): {d.lower(): float(v) for d, v in sorted(row.items())}
             for atk, row in sorted(data.type_chart.items())}
    flipped = {a: {d: chart[d][a] for d in chart} for a in chart}
    value = dict(source='poke_env.data.GenData.from_gen(9)', moves=moves, species=species, attack=flipped)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_assumed(corpus, path=ASSUMED):
    """Most frequent normalized set per species (count, then canonical-JSON sha256 as the tie-break)."""
    best = {}
    with open(corpus) as f:
        for line in f:
            row = json.loads(line)
            s = row['set']
            key = to_id(s['species'])
            canon = json.dumps(s, sort_keys=True, separators=(',', ':'))
            rank = (-row['count'], hashlib.sha256(canon.encode()).hexdigest())
            if key not in best or rank < best[key][0]:
                best[key] = (rank, s, row['count'])
    value = dict(source=str(corpus), source_sha256=hashlib.sha256(Path(corpus).read_bytes()).hexdigest(),
                 rule='max count, then sha256(canonical set)', sets={
                     k: dict(count=c, set=dict(item=to_id(s.get('item') or ''), ability=to_id(s.get('ability') or ''),
                                               nature=to_id(s.get('nature') or 'serious'), level=int(s.get('level') or 100),
                                               evs={k2: int(v) for k2, v in (s.get('evs') or {}).items()},
                                               ivs={k2: int(v) for k2, v in (s.get('ivs') or {}).items()},
                                               moves=[to_id(m) for m in s.get('moves', [])],
                                               tera=to_id(s.get('teraType') or '')))
                     for k, (_, s, c) in sorted(best.items())})
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def load():
    return json.loads(PATH.read_text())


@lru_cache(maxsize=1)
def assumed():
    return json.loads(ASSUMED.read_text())['sets']


def digest():
    return dict(dex=hashlib.sha256(PATH.read_bytes()).hexdigest(), assumed=hashlib.sha256(ASSUMED.read_bytes()).hexdigest())


def multiplier(attack_type, defender_types):
    chart = load()['attack']
    if attack_type not in chart:
        return None
    value = 1.0
    for t in defender_types:
        value *= chart[attack_type].get(t, 1.0)
    return value


if __name__ == '__main__':
    import sys
    print(export())
    print(export_assumed(sys.argv[1]))
