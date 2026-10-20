"""Fixed Showdown metadata; never reads an opponent's private set."""
from functools import lru_cache
import copy
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PIN = 'e64915c0eab066db1d3e732b1280386468dd7415'


@lru_cache(maxsize=1)
def metadata():
    sha = subprocess.check_output(['git','-C',str(ROOT/'pokemon-showdown'),'rev-parse','HEAD'],text=True).strip()
    if sha != PIN:
        raise ValueError('candidate matchup requires the registered Showdown revision')
    snapshot = _file_identity()
    raw = subprocess.check_output(['node',str(Path(__file__).with_name('metadata.cjs'))])
    result = json.loads(raw)
    if result.get('generation') != 9:
        raise ValueError('wrong rule generation')
    result['_identity'] = dict(showdown_revision=PIN,generation=9,files=snapshot,
                               metadata_sha256=hashlib.sha256(raw).hexdigest())
    return result


def _file_identity():
    files = [Path(__file__).with_name('metadata.cjs'), ROOT/'pokemon-showdown/dist/sim/pokemon.js',
             ROOT/'pokemon-showdown/dist/data/moves.js', ROOT/'pokemon-showdown/dist/data/abilities.js',
             ROOT/'pokemon-showdown/dist/data/items.js', ROOT/'pokemon-showdown/dist/data/typechart.js']
    files += [Path(__file__),Path(__file__).with_name('summary.py'),Path(__file__).with_name('adapter.py')]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def identity():
    return copy.deepcopy(metadata()['_identity'])
