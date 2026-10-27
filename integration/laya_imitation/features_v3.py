"""EX-128 v3 opponent-set facts on top of the v2 facts (`features.compute`).

`compute(value, calc)` returns the v2 facts plus `v3`: the active foe's inferred set (usage marginals narrowed by
what is public), the chance that my active Pokemon moves first, and the largest hit from likely not-yet-seen foe
moves on my active and on each switch-in. The usage source is pinned in `usage_sets_v3.json` (Smogon chaos,
gen9ou 2026-08, 1695). Moves are marginal inclusion frequencies treated as independent; the remaining
`4 - revealed` slots are filled by rescaling the unseen moves' mass (EX-128 protocol).
"""
from __future__ import annotations
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from . import dex_v2, features

USAGE = Path(__file__).with_name('usage_sets_v3.json')
SOURCE = Path(__file__).resolve().parents[2] / ('exports/pokemon-role-data/pokemon_role_db_gen9ou_2026-08_1695/'
                                                 'data/processed/usage/gen9ou-1695.json')
STATS = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')
ALIAS = {'mimikyubusted': 'mimikyu'}
PIN_FLOOR = 1e-4       # usage entries below this share are not pinned
SPREAD_FLOOR = 0.001   # spreads below this share are dropped before renormalizing (speed)
ABILITY_FLOOR = 0.01
SHOW_FLOOR = 0.15      # oppset display floor
THREAT_FLOOR = 0.3     # unseen moves at or above this inclusion probability count as threats
TOP_MOVES = 8


def export(source=SOURCE, path=USAGE):
    """Pin the processed usage file (per-species abilities/items/moves/spreads/tera_types) with its provenance.

    Entries under PIN_FLOOR (spreads under SPREAD_FLOOR) are dropped here, so the pinned file is the definition.
    """
    raw = json.loads(Path(source).read_text())
    floors = dict(abilities=PIN_FLOOR, items=PIN_FLOOR, moves=PIN_FLOOR, spreads=SPREAD_FLOOR, tera_types=PIN_FLOOR)
    value = dict(source=str(source), source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                 upstream=raw['source'], format=raw['format'], month=raw['month'], rating=raw['rating'],
                 number_of_battles=raw['number_of_battles'], semantics=raw['distribution_semantics'],
                 floors=floors,
                 pokemon={k: {f: {m: p for m, p in (v.get(f) or {}).items() if p >= floor}
                              for f, floor in floors.items()} for k, v in sorted(raw['pokemon'].items())})
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def usage():
    return json.loads(USAGE.read_text())['pokemon']


def digest():
    return hashlib.sha256(USAGE.read_bytes()).hexdigest()


def species_key(species):
    if species in usage():
        return species
    key = ALIAS.get(species, species)
    if key.startswith('ogerpon') and key.endswith('tera'):
        key = key[:-4]
    return key if key in usage() else None


def _top(dist, floor=0.0, exclude=()):
    items = [(k, v) for k, v in dist.items() if k not in exclude and k != 'none' and v > floor]
    return sorted(items, key=lambda kv: (-kv[1], kv[0]))


def _norm(pairs):
    total = sum(p for _, p in pairs)
    return [(k, p / total) for k, p in pairs] if total > 0 else []


def _spread(text):
    nature, evs = text.split(':')
    return dex_v2.to_id(nature), dict(zip(STATS, (int(v) for v in evs.split('/'))))


def infer_set(foe, can_tera):
    """Public facts fixed, the rest from usage marginals; `source` is 'usage' or 'default' (no usage row)."""
    key = species_key(foe['species'])
    revealed = [m['id'] for m in foe['moves']]
    if key is None:
        return dict(source='default', species=foe['species'], revealed_moves=len(revealed))
    u = usage()[key]
    item = [(foe['item'], 1.0)] if foe['item'] else _norm(_top(u['items']))
    ability = [(foe['ability'], 1.0)] if foe['ability'] else _norm(_top(u['abilities']))
    if foe['terastallized'] or not can_tera:
        tera = []
    elif foe['tera_type']:
        tera = [(foe['tera_type'], 1.0)]
    else:
        tera = _norm(_top(u['tera_types']))
    slots = max(0, 4 - len(revealed))
    unseen = _top(u['moves'], exclude=set(revealed))
    mass = sum(p for _, p in unseen)
    scale = slots / mass if slots and mass > 0 else 0.0
    moves = [(m, min(1.0, p * scale)) for m, p in unseen[:TOP_MOVES]] if scale else []
    spreads = _norm([(s, p) for s, p in _top(u['spreads']) if p >= SPREAD_FLOOR])
    return dict(source='usage', species=foe['species'], usage_key=key, revealed_moves=len(revealed),
                item=_round(item), ability=_round(ability), tera=_round(tera), moves=_round(moves),
                spreads=_round(spreads))


def _round(pairs):
    return [[k, round(p, 4)] for k, p in pairs]


def _modal(pairs, default=''):
    return pairs[0][0] if pairs else default


def first_chance(me_speed, foe, inferred, snapshot):
    """P(my active moves first) over spreads x Scarf x ability; ties count half, Trick Room flips it."""
    base = dex_v2.load()['species'].get(foe['species'], {}).get('base')
    if me_speed is None or not base or not inferred['spreads']:
        return None
    scarf = 1.0 if foe['item'] == 'choicescarf' else 0.0 if foe['item'] else \
        sum(p for k, p in inferred['item'] if k == 'choicescarf')
    abilities = _norm([(k, p) for k, p in inferred['ability'] if p >= ABILITY_FLOOR]) or [('', 1.0)]
    first = total = 0.0
    for text, p_spread in inferred['spreads']:
        nature, evs = _spread(text)
        raw = features._stat(base['spe'], 31, evs['spe'], 100, features._nature(nature, 'spe'))
        for ability, p_ability in abilities:
            for item, p_item in (('choicescarf', scarf), ('', 1.0 - scarf)):
                if p_item <= 0:
                    continue
                opp = features._speed_mods(raw, foe, snapshot, 'opponent_side_conditions', ability, item)
                win = 1.0 if me_speed > opp else 0.5 if me_speed == opp else 0.0
                first += p_spread * p_ability * p_item * win
                total += p_spread * p_ability * p_item
    first /= total   # the stored shares are rounded, so renormalize
    if 'trick_room' in snapshot['field']:
        first = 1.0 - first
    return round(first, 4)


def _attacker(foe, inferred):
    nature, evs = _spread(inferred['spreads'][0][0]) if inferred['spreads'] else ('serious', {})
    return dict(species=foe['species'], level=100, nature=nature, evs=evs, ivs={},
                ability=foe['ability'] or _modal(inferred['ability']), item=foe['item'] or _modal(inferred['item']),
                boosts={k: v for k, v in foe['boosts'].items() if v}, status=foe['status'] or '',
                hp_percent=foe['hp_percent'] if foe['hp_percent'] is not None else 100,
                tera=foe['tera_type'] if foe['terastallized'] else None)


def threats(inferred):
    """Unseen damaging moves with inclusion probability >= THREAT_FLOOR."""
    moves = dex_v2.load()['moves']
    return [(m, p) for m, p in inferred.get('moves') or [] if p >= THREAT_FLOOR and m in moves
            and moves[m]['category'] != 'status']


def compute(value, calc):
    facts = features.compute(value, calc)
    snapshot = json.loads(value.body['state'])['snapshot']
    own = {m['slot']: m for m in snapshot['own_team']}
    opp = {m['slot']: m for m in snapshot['opponent_team']}
    me = own.get(snapshot['own_active_slot']) if snapshot['own_active_slot'] else None
    foe = opp.get(snapshot['opponent_active_slot']) if snapshot['opponent_active_slot'] else None
    v3 = dict(oppset=None, first=None, threat=dict(active=None, switch={}))
    facts['v3'] = v3
    if foe is None:
        return facts
    inferred = infer_set(foe, snapshot['opponent_can_tera'])
    v3['oppset'] = inferred
    if inferred['source'] != 'usage':
        return facts
    v3['first'] = first_chance(facts['speed']['me'], foe, inferred, snapshot)
    likely = threats(inferred)
    if not likely:
        return facts
    attacker = _attacker(foe, inferred)
    targets = ([('active', features._own_spec(me))] if me is not None and me['status'] != 'fnt' else []) + \
        [(a, features._own_spec(own[int(a.split(':')[1])], active=False)) for a in value.action_ids
         if a.startswith('switch:')]
    requests, slots = [], []
    for target, spec in targets:
        for move, p in likely:
            requests.append(dict(attacker=attacker, defender=spec, move=move, weather=snapshot['weather'],
                                 field=snapshot['field'], attacker_side=snapshot['opponent_side_conditions'],
                                 defender_side=snapshot['own_side_conditions']))
            slots.append((target, move, p))
    best = {}
    for (target, move, p), result in zip(slots, calc.run(requests), strict=True):
        if 'error' in result or result['max'] <= 0:
            continue
        cur = best.get(target)
        if cur is None or (result['max'], move) > (cur['max'], cur['move']):
            best[target] = dict(move=move, p=p, min=result['min'], max=result['max'])
    v3['threat'] = dict(active=best.get('active'), switch={k: v for k, v in best.items() if k != 'active'})
    return facts
