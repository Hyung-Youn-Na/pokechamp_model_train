"""EP-237: the usage entry of one opposing Pokemon conditioned on what the game has shown (`observe.Observation`).

`conditioned(entry, mon, foe, snapshot, calc)` returns a usage entry of the same shape as `usage_sets_v3.json`
(`abilities`, `items`, `moves`, `spreads`, `tera_types`), so every v11 consumer (`opp set`, `opp watch`, bench
`likely`, `opp threat`, `locked?`, the duel's healing item, the first-move chance) reads the conditioned one unchanged:

1. joint sets (foul-play `prepare_battles`): the foul-play full sets of the species (`data/foulplay_full_sets_gen9ou.json`,
   a pinned copy of `fp/data/pkmn_sets_cache/gen9ou/pokemon_full_sets.json`) that contain every revealed move and agree
   with the revealed ability / item / Tera type, minus ruled-out items / abilities, minus spreads outside the observed
   speed bounds, minus (with a calculator) sets whose damage range misses an observed hit (`update_dataset_possibilities`,
   same 0.975 / 1.025 margins, crits and KOs handled the same way). Weighted by the set counts.
2. the usage marginals with the same eliminations (items / abilities removed, spreads and Choice Scarf reweighted by the
   speed bounds).
The result mixes 1 and 2 as JOINT_SHARE : 1 - JOINT_SHARE when 1 is not empty (the set file has a median of 3 sets per
species, so rare sets keep some mass), else it is 2. Boots inferred from Stealth Rock make the item Boots.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from .observe import ident

SETS = Path(__file__).resolve().parent / 'data/foulplay_full_sets_gen9ou.json'
JOINT_SHARE = 0.85
ORDER = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')
PLUS = dict(atk={'lonely', 'brave', 'adamant', 'naughty'}, defense={'bold', 'relaxed', 'impish', 'lax'},
            spa={'modest', 'mild', 'quiet', 'rash'}, spd={'calm', 'gentle', 'sassy', 'careful'},
            spe={'timid', 'hasty', 'jolly', 'naive'})
MINUS = dict(atk={'bold', 'timid', 'modest', 'calm'}, spa={'adamant', 'impish', 'careful', 'jolly'},
             spe={'brave', 'relaxed', 'quiet', 'sassy'})
MAX_FIT_SETS = 150
MAX_FIT_HITS = 6
UNLISTED = 1e-3        # mass of plain spreads the usage file does not list (see `_filtered`)
RULED_FLOOR = 0.05      # a ruled-out guess is written when its usage share was at least this
TOL = 1.5               # % of max HP: the foe's HP is shown in whole percent
_damage_cache = {}
CACHE_LIMIT = 200000
STATS = dict(fit_calls=0, fit_requests=0, fit_removed=0, fit_skipped_many=0)


def sha():
    return hashlib.sha256(SETS.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def load():
    out = {}
    for species, sets in json.loads(SETS.read_text()).items():
        rows = []
        for key, w in sets.items():
            p = key.split('|')
            evs = dict(zip(ORDER, (int(v) for v in p[4].split(','))))
            rows.append(dict(tera=ident(p[0]), ability=ident(p[1]), item=ident(p[2]), nature=ident(p[3]), evs=evs,
                             moves=frozenset(ident(m) for m in p[5:]), w=float(w)))
        out[ident(species)] = rows
    return out


def speed_of(base, nature, evs, item, level=100, iv=31):
    mult = 1.1 if nature in PLUS['spe'] else 0.9 if nature in MINUS['spe'] else 1.0
    raw = int((int((2 * base + iv + evs.get('spe', 0) // 4) * level / 100) + 5) * mult)
    return int(raw * 1.5) if item == 'choicescarf' else raw


def _spread_key(nature, evs):
    return '%s:%s' % (nature.capitalize(), '/'.join(str(evs.get(k, 0)) for k in ORDER))


def _parse_spread(key):
    nature, evs = key.split(':')
    return nature.lower(), dict(zip(ORDER, (int(v) for v in evs.split('/'))))


def _norm(d):
    total = sum(d.values())
    return {k: v / total for k, v in d.items()} if total > 0 else dict(d)


def _public(mon):
    state = (mon.get('item_state') or {}).get('state')
    item = mon['item_state']['item'] if state in ('held', 'removed', 'consumed') and mon['item_state'].get('item') \
        else mon.get('item')
    return dict(item=ident(item) if item else None, ability=ident(mon['ability']) if mon.get('ability') else None,
                tera=ident(mon['tera_type']) if mon.get('tera_type') else None,
                moves={m['id'] for m in mon.get('moves') or []})


def set_rows(species):
    from integration.laya_v11 import render_v11
    from .observe import canon
    table = load()
    for key in (species, canon(species), render_v11.FORMES.get(species), render_v11.FORMES.get(canon(species))):
        if key and key in table:
            return table[key]
    return []


def candidates(mon, foe, base_spe):
    rows = set_rows(mon['species'])
    if not rows:
        return []
    pub = _public(mon)
    if foe is not None and foe.traded:
        pub = dict(pub, item=None)          # a traded item is not the set's item
    lo, hi = foe.speed if foe is not None else (0, 10 ** 9)
    out = []
    for r in rows:
        if not pub['moves'] <= r['moves']:
            continue
        if pub['ability'] and r['ability'] != pub['ability']:
            continue
        if pub['item'] and r['item'] != pub['item']:
            continue
        if pub['tera'] and r['tera'] != pub['tera']:
            continue
        if foe is not None:
            if not pub['item'] and (r['item'] in foe.no_items or (foe.boots and r['item'] != 'heavydutyboots')):
                continue
            if not pub['ability'] and r['ability'] in foe.no_abilities:
                continue
            if base_spe is not None and not lo <= speed_of(base_spe, r['nature'], r['evs'], r['item']) <= hi:
                continue
        out.append(r)
    return out


# ------------------------------------------------------------------------------ damage fit
def _terrain_key(terrain):
    return {'electricterrain': 'electric_terrain', 'grassyterrain': 'grassy_terrain',
            'psychicterrain': 'psychic_terrain', 'mistyterrain': 'misty_terrain'}.get(terrain[0] if terrain else None)


def _screens(d):
    return {dict(lightscreen='light_screen', auroraveil='aurora_veil').get(k, k): 1 for k in d}


def _request(hit, cand, mon, own_mon):
    from integration.laya_imitation import features
    foe_spec = dict(species=mon['species'], level=100, nature=cand['nature'], evs=cand['evs'], ivs={},
                    ability=cand['ability'], item=cand['item'], boosts={k: v for k, v in hit['foe_boosts'].items() if v},
                    status=hit['foe_status'] if hit['foe_status'] not in ('fnt',) else '',
                    hp_percent=hit['foe_hp'] if hit['direction'] == 'dealt' else hit['before'],
                    tera=hit['foe_tera'])
    me = dict(own_mon, boosts=hit['me_boosts'], status=hit['me_status'] or None,
              hp_percent=hit['before'] if hit['direction'] == 'dealt' else hit['me_hp'],
              terastallized=bool(hit['me_tera']), tera_type=hit['me_tera'] or own_mon.get('tera_type'))
    me_spec = features._own_spec(me, hit['me_tera'], active=True)
    terrain = _terrain_key(hit['terrain'])
    fld = {terrain: 1} if terrain else {}
    if hit['direction'] == 'dealt':
        return dict(attacker=foe_spec, defender=me_spec, move=hit['move'], weather=hit['weather'] or 'none', field=fld,
                    attacker_side=_screens(hit['screens']['opp']), defender_side=_screens(hit['screens']['self']))
    return dict(attacker=me_spec, defender=foe_spec, move=hit['move'], weather=hit['weather'] or 'none', field=fld,
                attacker_side=_screens(hit['screens']['self']), defender_side=_screens(hit['screens']['opp']))


def _consistent(result, hit):
    if 'error' in result:
        return True
    actual = hit['before'] - hit['after']
    if actual <= 0:
        return True
    upper = result['max'] * 1.025 + TOL
    if hit['after'] <= 0:              # a KO only bounds the damage from below
        return upper >= actual
    lower = result['min'] * 0.975 - TOL
    return lower <= actual <= upper


def damage_fit(cands, mon, foe, snapshot, calc):
    """`cands` minus the sets whose range misses an observed non-crit hit (never empty: foul-play keeps all then)."""
    if calc is None or foe is None or not foe.hits or not cands:
        return cands, 0
    if len(cands) > MAX_FIT_SETS:
        STATS['fit_skipped_many'] += 1
        return cands, 0
    STATS['fit_calls'] += 1
    own = {m['species']: m for m in snapshot['own_team']}
    hits = [h for h in foe.hits if h['me'] in own][-MAX_FIT_HITS:]
    if not hits:
        return cands, 0
    if len(_damage_cache) > CACHE_LIMIT:      # clear before looking up, so every key used below is present
        _damage_cache.clear()
    requests, where = [], []
    for ci, cand in enumerate(cands):
        for hi, hit in enumerate(hits):
            req = _request(hit, cand, mon, own[hit['me']])
            key = json.dumps(req, sort_keys=True, separators=(',', ':'))
            if key not in _damage_cache:
                requests.append((key, req))
            where.append((ci, hi, key))
    if requests:
        unique = dict(requests)
        keys = list(unique)
        results = calc.run([unique[k] for k in keys])
        STATS['fit_requests'] += len(keys)
        _damage_cache.update(zip(keys, results))
    bad = {ci for ci, hi, key in where if not _consistent(_damage_cache[key], hits[hi])}
    kept = [c for i, c in enumerate(cands) if i not in bad]
    STATS['fit_removed'] += len(bad) if kept else 0
    return (kept, len(bad)) if kept else (cands, 0)


# ------------------------------------------------------------------------------ the conditioned entry
def _from_sets(rows, revealed):
    total = sum(r['w'] for r in rows)
    items, abilities, tera, spreads, moves = {}, {}, {}, {}, {}
    for r in rows:
        w = r['w'] / total
        items[r['item']] = items.get(r['item'], 0) + w
        abilities[r['ability']] = abilities.get(r['ability'], 0) + w
        tera[r['tera']] = tera.get(r['tera'], 0) + w
        k = _spread_key(r['nature'], r['evs'])
        spreads[k] = spreads.get(k, 0) + w
        for m in r['moves'] - revealed:
            moves[m] = moves.get(m, 0) + w
    return dict(items=items, abilities=abilities, tera_types=tera, spreads=spreads, moves=moves)


def _filtered(entry, foe, base_spe, pub=None):
    """(entry, fell_back): the usage entry with the eliminations; `fell_back` names the fields (items / abilities)
    where every guess was ruled out and the unfiltered one was kept."""
    pub = pub or {}
    fell_back = set()
    items = dict(entry.get('items', {}))
    if not pub.get('item'):
        kept = {k: v for k, v in items.items() if k not in foe.no_items}
        if foe.boots:
            kept = {'heavydutyboots': 1.0}
        if kept:
            items = _norm(kept)
        elif items:
            fell_back.add('items')
    abilities = dict(entry.get('abilities', {}))
    if not pub.get('ability'):
        kept = {k: v for k, v in abilities.items() if k not in foe.no_abilities}
        if kept:
            abilities = _norm(kept)
        elif abilities:
            fell_back.add('abilities')
    spreads = dict(entry.get('spreads', {}))
    lo, hi = foe.speed
    if base_spe is not None and (lo > 0 or hi < 10 ** 9) and spreads:
        if pub.get('item'):
            p_scarf = 1.0 if pub['item'] == 'choicescarf' else 0.0
        else:
            p_scarf = items.get('choicescarf', 0.0)
        plain = scarf = 0.0
        weights = {}
        for key, p in spreads.items():
            nature, evs = _parse_spread(key)
            ok_plain = lo <= speed_of(base_spe, nature, evs, '') <= hi
            ok_scarf = lo <= speed_of(base_spe, nature, evs, 'choicescarf') <= hi
            plain += p * ok_plain * (1 - p_scarf)
            scarf += p * ok_scarf * p_scarf
            weights[key] = p * (ok_plain * (1 - p_scarf) + ok_scarf * p_scarf)
        # the usage file drops spreads under 0.1%: an unlisted plain spread can still reach any speed up to the
        # species' plain maximum, so a Scarf is never certain from speed alone while that is possible
        if not pub.get('item') and lo <= speed_of(base_spe, 'jolly', dict(spe=252), '') and hi >= 0:
            plain += UNLISTED * (1 - p_scarf)
        kept = {k: v for k, v in weights.items() if v > 0}
        if plain + scarf > 0:
            if kept:
                spreads = _norm(kept)
            if not pub.get('item') and ('choicescarf' in items or scarf > 0):
                new = scarf / (plain + scarf)
                rest = {k: v for k, v in items.items() if k != 'choicescarf'}
                rest_total = sum(rest.values())
                items = {k: v * (1 - new) / rest_total for k, v in rest.items()} if rest_total > 0 else {}
                if new > 0:
                    items['choicescarf'] = new
    return dict(entry, items=items, abilities=abilities, spreads=spreads), fell_back


def _mix(a, b, share, revealed=frozenset()):
    out = {}
    for field in ('items', 'abilities', 'tera_types', 'spreads', 'moves'):
        x, y = a.get(field, {}), b.get(field, {})
        if field == 'moves':                      # both over the unrevealed moves, so the usage share stays `1 - share`
            ys = _norm({k: v for k, v in y.items() if k not in revealed})
            xs = _norm(x) if x else {}
            keys = set(xs) | set(ys)
            out[field] = {k: share * xs.get(k, 0) + (1 - share) * ys.get(k, 0) for k in keys}
            continue
        keys = set(x) | set(y)
        out[field] = {k: share * x.get(k, 0) + (1 - share) * y.get(k, 0) for k in keys if share * x.get(k, 0) + (1 - share) * y.get(k, 0) > 0}
    return out


def conditioned(entry, mon, foe, snapshot, calc=None, dex=None):
    """(entry, info). `info` records what changed (for the renderer marks and tests)."""
    if dex is None:
        from integration.laya_imitation import dex_v2
        dex = dex_v2.load()
    base = dex['species'].get(mon['species'], {}).get('base')
    base_spe = base['spe'] if base else None
    info = dict(sets=0, fit_removed=0, ruled_out=[])
    if foe is None:
        return entry, info
    pub = _public(mon)
    if foe.traded:
        pub = dict(pub, item=None)
    marg, fell_back = _filtered(entry, foe, base_spe, pub)
    hidden_item = not pub['item'] and (mon.get('item_state') or {}).get('state') in (None, 'unknown')
    ruled = [k for k in foe.no_items if hidden_item and 'items' not in fell_back and
             entry.get('items', {}).get(k, 0) >= RULED_FLOOR]
    ruled += [k for k in foe.no_abilities if not pub['ability'] and 'abilities' not in fell_back and
              entry.get('abilities', {}).get(k, 0) >= RULED_FLOOR]
    if foe.boots and hidden_item:
        info['boots'] = True
    info['ruled_out'] = sorted(ruled, key=lambda k: (-max(entry.get('items', {}).get(k, 0),
                                                          entry.get('abilities', {}).get(k, 0)), k))
    public = pub
    if not (public['moves'] or public['item'] or public['ability'] or public['tera']):
        return marg, info            # nothing revealed to condition the joint sets on: keep the usage source
    cands = candidates(mon, foe, base_spe)
    cands, removed = damage_fit(cands, mon, foe, snapshot, calc)
    info.update(sets=len(cands), fit_removed=removed)
    if not cands:
        return marg, info
    joint = _from_sets(cands, pub['moves'])
    out = _mix(joint, marg, JOINT_SHARE, frozenset(pub['moves']))
    return out, info
