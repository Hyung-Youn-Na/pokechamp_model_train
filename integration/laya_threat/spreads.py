"""Item-consistent spreads for the assumed foe set (D-202 part 1).

`assumed_sets_v2.json` takes each species' most frequent EX-071 set. Three of them mix one set's spread with another's
item or moves (Kyurem: Choice Specs with Adamant 252 Atk / 0 SpA), and a revealed item can contradict the assumed
spread (a Choice Specs reveal on a physical spread). Every damage figure then misses the attacker's real stat.

`opp_spec(mon)` is `features._opp_spec` with one change: when the spread contradicts the attack category, the most
used Smogon spread (`usage_sets_v3.json`, 2026-08) that serves the category replaces nature and EVs. The category is
special for Choice Specs and physical for Choice Band (forced: the attacking stat needs MIN_EV EVs and a nature that
does not lower it); otherwise it is the strict majority of the revealed attacks that scale with Atk or SpA (UTILITY
moves do not count; nothing revealed means no constraint), and only a nature that lowers that stat with fewer than
MIN_EV EVs in it is a contradiction (bulky spreads with no attacking EVs stay). Everything else (level, IVs, ability, item,
boosts, status, HP, Tera) is `_opp_spec`'s.

`patched()` swaps `features._opp_spec` for `opp_spec` for the duration of a v9 render; every v2-v7 damage request
for the foe (`features.compute`, `features_v4`, `features_v5`) goes through that module attribute, and a v7 render in
the same process (battle export) keeps the original.
"""
from __future__ import annotations
from contextlib import contextmanager
from functools import lru_cache

from integration.laya_imitation import dex_v2, features, features_v3

MIN_EV = 128
LOWERS = dict(atk=('bold', 'modest', 'calm', 'timid'), spa=('adamant', 'impish', 'careful', 'jolly'))
STAT = dict(physical='atk', special='spa')
ORDER = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')
# Attacks any spread carries (laya-play `setcheck.cjs` UTIL) and damage that ignores the attacking stat: they say
# nothing about the spread's category.
UTILITY = frozenset(('uturn', 'flipturn', 'rapidspin', 'knockoff', 'bodypress', 'foulplay', 'suckerpunch',
                     'quickattack', 'nuzzle', 'voltswitch', 'partingshot', 'firstimpression', 'mortalspin',
                     'icespinner', 'seismictoss', 'nightshade', 'superfang', 'ruination', 'finalgambit', 'endeavor',
                     'counter', 'mirrorcoat', 'metalburst', 'comeuppance', 'bide'))

_original = features._opp_spec


def _category(move_id):
    info = dex_v2.load()['moves'].get(move_id)
    return info['category'] if info else None


def _stat_category(move_id):
    """physical / special for attacks that scale with the attacker's Atk / SpA, else None."""
    return None if move_id in UTILITY else _category(move_id)


def item_category(item):
    return 'special' if item == 'choicespecs' else 'physical' if item == 'choiceband' else None


def category(mon, item):
    """The attack category the foe's spread must serve (None: no constraint)."""
    forced = item_category(item)
    if forced:
        return forced
    seen = [_stat_category(m['id']) for m in mon['moves']]
    phys, spec = seen.count('physical'), seen.count('special')
    if phys != spec:
        return 'physical' if phys > spec else 'special'
    return None


def serves(nature, evs, cat):
    """The spread is built for `cat`: MIN_EV EVs in its stat and a nature that does not lower it."""
    stat = STAT[cat]
    return (evs or {}).get(stat, 0) >= MIN_EV and (nature or '').lower() not in LOWERS[stat]


def fits(nature, evs, cat, forced):
    if cat is None:
        return True
    if forced:
        return serves(nature, evs, cat)
    stat = STAT[cat]
    return (evs or {}).get(stat, 0) >= MIN_EV or (nature or '').lower() not in LOWERS[stat]


def parse(spread):
    nature, evs = spread.split(':')
    return nature.lower(), dict(zip(ORDER, (int(v) for v in evs.split('/'))))


@lru_cache(maxsize=None)
def usage_spread(species, cat):
    """(nature, evs) of the most used usage spread that serves `cat`, or None."""
    key = features_v3.species_key(species)
    if key is None:
        return None
    for spread, _ in sorted(features_v3.usage()[key].get('spreads', {}).items(), key=lambda kv: (-kv[1], kv[0])):
        nature, evs = parse(spread)
        if serves(nature, evs, cat):
            return nature, evs
    return None


def fixed(spec, mon):
    """`spec` with an item-consistent spread; returns (spec, changed)."""
    cat = category(mon, spec['item'])
    if fits(spec['nature'], spec['evs'], cat, item_category(spec['item']) is not None):
        return spec, False
    alt = usage_spread(mon['species'], cat)
    if alt is None:
        return spec, False
    return dict(spec, nature=alt[0], evs={k: v for k, v in alt[1].items() if v}), True


def opp_spec(mon):
    spec, source = _original(mon)
    if source == 'default':
        return spec, source
    return fixed(spec, mon)[0], source


@contextmanager
def patched():
    previous = features._opp_spec
    features._opp_spec = opp_spec
    try:
        yield
    finally:
        features._opp_spec = previous


def active():
    return features._opp_spec is opp_spec
