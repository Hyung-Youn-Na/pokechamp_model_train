"""EP-234 unit checks (foul-play venv):
PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m pytest integration/laya_fp1/tests
"""
from collections import Counter
import json
from pathlib import Path

import pytest

from integration.laya_fp1 import render_fp1 as R
from integration.laya_fp1 import tracker as T

RECOVERED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-ladder-source/v1/'
                 'preparation/recovered/gen9ou-2708814832.json.gz')
RAW = Path('/workspace/data/showdown-replays/ladder-recent/gen9ou-r1500-newest/raw/gen9ou-2708814832.json.json')
needs_data = pytest.mark.skipif(not (RECOVERED.exists() and RAW.exists()), reason='replay data not mounted')


def _game():
    from integration.laya_fp1.data_fp1 import load
    return load(RECOVERED), load(RAW)


@needs_data
def test_rewrite_own_hp_and_snow():
    rec, raw = _game()
    sets = rec['result']['original_sets']['p1']
    tr = T.Tracker(raw, 'p1', sets)
    species = sets[0]['species']
    maxhp = tr.maxhp[T.ident(species)]
    line = tr._rewrite('|switch|p1a: Nick|%s, L100|50/100' % species)
    assert line.endswith('|%d/%d' % (round(maxhp / 2), maxhp))
    assert tr._rewrite('|-damage|p1a: Nick|0 fnt') == '|-damage|p1a: Nick|0 fnt'
    assert tr._rewrite('|-damage|p2a: Foe|40/100') == '|-damage|p2a: Foe|40/100'        # opponent stays %
    assert tr._rewrite('|-damage|p2a: Foe|317/341 par') == '|-damage|p2a: Foe|93/100 par'   # exact -> %
    assert tr._rewrite('|switch|p1a: Nick|%s, L100|%d/%d' % (species, maxhp, maxhp)).endswith('|%d/%d' % (maxhp, maxhp))
    assert tr._rewrite('|-weather|Snow|[from] ability: Snow Warning') == \
        '|-weather|Snowscape|[from] ability: Snow Warning'
    assert tr._rewrite('|-weather|Snowscape|[upkeep]') == '|-weather|Snowscape|[upkeep]'


@needs_data
def test_tracker_matches_snapshots_and_options_map():
    rec, raw = _game()
    sets = rec['result']['original_sets']['p1']
    tr = T.Tracker(raw, 'p1', sets)
    n = 0
    for r in T.recovered_records(rec, 'p1'):
        if r['decision_kind'] == 'lead':
            tr.chose(r.get('label'))
            continue
        tr.advance(r['cutoff_line'], r['snapshot'], r['decision_kind'])
        v = tr.view()
        snap = r['snapshot']
        me = {m['slot']: m for m in snap['own_team']}[snap['own_active_slot']]
        assert T.ident(me['species']) in (v.user.active.name, v.user.active.base_name)
        for a in r['actions']:
            choice = R.engine_choice(a['id'], v, sets)
            assert choice
            if a['id'].startswith('switch:'):
                assert choice in [p.name for p in v.user.reserve]
        tr.chose(r.get('label'))
        n += 1
    assert n > 20


@needs_data
def test_render_is_deterministic_and_clean():
    rec, raw = _game()
    sets = rec['result']['original_sets']['p1']
    outs = []
    for _ in range(2):
        tr = T.Tracker(raw, 'p1', sets)
        out = []
        for r in T.recovered_records(rec, 'p1')[:12]:
            if r['decision_kind'] == 'lead':
                tr.chose(r.get('label'))
                continue
            tr.advance(r['cutoff_line'], r['snapshot'], r['decision_kind'])
            sid = 'x:p1:%d:%s' % (r['cutoff_line'], r['decision_kind'])
            state, crit, diag = R.render(tr.view(), sid, r['actions'], r['decision_kind'], sets)
            assert diag['engine_errors'] == 0
            assert list(crit) == [a['id'] for a in r['actions']]
            out.append((state, crit))
            tr.chose(r.get('label'))
        outs.append(out)
    assert outs[0] == outs[1]


def test_silent_defaults_flags():
    from poke_engine import Pokemon, Side, State
    fainted = [Pokemon.create_fainted() for _ in range(5)]
    bad = Pokemon(id='gholdengo', ability='notarealability', item='notarealitem', weight_kg=0.0)
    good = Pokemon(id='pikachu', ability='static', item='lightball', weight_kg=6.0, tera_type='electric')
    state = State(side_one=Side(pokemon=[bad] + fainted), side_two=Side(pokemon=[good] + fainted))
    flags = Counter()
    R.silent_defaults(state, flags)
    kinds = {k.split(':')[0] for k in flags}
    assert kinds == {'weight0', 'tera_typeless', 'ability_none', 'item_unknown'}
    assert all(':gholdengo' in k for k in flags)


def test_unknown_choice_is_a_priority_move():
    from fp.data import all_move_json
    T.setup()
    assert all_move_json[T.UNKNOWN_CHOICE]['priority'] > 1
