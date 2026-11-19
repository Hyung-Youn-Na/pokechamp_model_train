"""Opponent-set usage for species the pinned `usage_sets_v3.json` (Smogon chaos gen9ou 2026-08, 1695) lacks.

v10rt was trained with `usage_sets_v3.json`, so its 291 species keep exactly those entries. Species that were not in
the 2026-08 OU stats but are legal on the official server now (for example Roaring Moon) had no `opp set`, bench
`likely`, `opp threat` or `locked?` estimates at all. The extension adds only those species, from a newer month of
the same Smogon chaos source, normalized by the same `pokemon_role_db` code and pinned with the same floors as
`features_v3.export`. Serving overlays it in its own process (`install`): `usage_sets_v3.json` and every renderer
file stay byte-identical, so the renderer-identity check still passes, and the ready file records the extension.

Build:  python3 -m integration.laya_ladder.usage_extension build PROCESSED_JSON [--out FILE]
        (PROCESSED_JSON = pokemon_role_db `data/processed/usage/gen9ou-1695.json` of the newer month)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT = HERE / 'usage_extension_2026-10_1695.json'
V3 = HERE.parent / 'laya_imitation' / 'usage_sets_v3.json'
# features_v3.export floors (PIN_FLOOR 1e-4, SPREAD_FLOOR 0.001)
FLOORS = dict(abilities=1e-4, items=1e-4, moves=1e-4, spreads=0.001, tera_types=1e-4)


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(processed: Path, out: Path = DEFAULT, v3: Path = V3) -> dict:
    raw = json.loads(Path(processed).read_text())
    base = json.loads(Path(v3).read_text())
    if raw['format'] != base['format'] or raw['rating'] != base['rating']:
        raise ValueError('format/rating differ from usage_sets_v3 (%s %s vs %s %s)'
                         % (raw['format'], raw['rating'], base['format'], base['rating']))
    have = set(base['pokemon'])
    pokemon = {k: {f: {m: p for m, p in (v.get(f) or {}).items() if p >= floor} for f, floor in FLOORS.items()}
               for k, v in sorted(raw['pokemon'].items()) if k not in have}
    value = dict(base_file='usage_sets_v3.json', base_sha256=sha(v3), base_month=base['month'],
                 source=str(processed), source_sha256=sha(processed), upstream=raw['source'], format=raw['format'],
                 month=raw['month'], rating=raw['rating'], number_of_battles=raw['number_of_battles'],
                 semantics=raw['distribution_semantics'], floors=FLOORS, added_species=sorted(pokemon),
                 pokemon=pokemon)
    Path(out).write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    return value


def install(path: Path = DEFAULT) -> dict | None:
    """Overlay the extension on features_v3.usage() in this process; v3 entries always win. Returns its identity."""
    path = Path(path)
    if not path.is_file():
        return None
    from integration.laya_imitation import features_v3
    ext = json.loads(path.read_text())
    if ext['base_sha256'] != features_v3.digest():
        raise ValueError('usage extension was built on a different usage_sets_v3.json')
    base = features_v3.usage()
    merged = dict(ext['pokemon'])
    merged.update(base)
    original = features_v3.usage

    def usage():
        return merged
    usage.cache_clear = original.cache_clear
    usage.original = original
    features_v3.usage = usage
    return dict(file=path.name, sha256=sha(path), month=ext['month'], rating=ext['rating'],
                added=len(ext['added_species']))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('processed', type=Path)
    b.add_argument('--out', type=Path, default=DEFAULT)
    args = p.parse_args(argv)
    value = build(args.processed, args.out)
    print('[usage] %s: %d species added from %s %d (%d battles)'
          % (args.out, len(value['added_species']), value['month'], value['rating'], value['number_of_battles']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
