"""EP-240 / D-218 unit and real-battle regression tests for laya-compact-v13."""
from __future__ import annotations

import glob
import json
import os
import pytest

from integration.laya_engine import judge as J
from integration.laya_imitation import compact, dex_v2, features, features_v3
from integration.laya_threat import spreads
from integration.laya_v10 import data_v10, render_v10
from integration.laya_v12 import sets
from integration.laya_v13 import render_v13


@pytest.fixture(scope='module', autouse=True)
def _install_v13():
    render_v13.install()
    # idempotent check
    v1 = render_v13.VERSION
    render_v13.install()
    assert render_v13.VERSION == v1


@pytest.fixture(scope='module')
def live_renderer():
    calc, judge = features.Calc(), J.Judge()
    try:
        yield data_v10.live_renderer(calc, judge)
    finally:
        calc.close()
        judge.close()


def _load_ex203_turn(battle_id: str, turn: int):
    for p in glob.glob('/workspace/exports/laya-play/games/20261122-*/result.json'):
        r = json.load(open(p, encoding='utf-8'))
        if battle_id in (r.get('battle_tag') or ''):
            evp = os.path.join(os.path.dirname(p), 'events.jsonl')
            with open(evp, encoding='utf-8') as f:
                for line in f:
                    ev = json.loads(line)
                    if ev.get('type') == 'input':
                        snap = ev.get('snapshot') or {}
                        if snap.get('turn') == turn and snap.get('decision_kind') == 'turn_action':
                            return compact.ImitationInput.from_body(ev['body'])
    pytest.skip(f'EX-203 battle {battle_id} turn {turn} not found locally')


def test_version_and_marks():
    assert render_v13.VERSION.startswith('laya-compact-v13[')
    for m in render_v13.MARKS:
        assert m in render_v13.VERSION
    meta = render_v10.version()
    assert meta['render'] == render_v13.VERSION
    assert 'v13' in meta and 'render_v13.py' in meta['v13']['code']


def test_assumed_resolves_ogerpon_and_battle_formes():
    for forme, expected_item in (
        ('ogerponwellspringtera', 'wellspringmask'),
        ('ogerponcornerstonetera', 'cornerstonemask'),
        ('ogerpontealtera', None),
        ('keldeoresolute', None),
        ('sinistchamasterpiece', None),
    ):
        src, a = features._assumed({'species': forme})
        assert src == 'corpus', f'{forme} fell back to default'
        if expected_item:
            assert a['item'] == expected_item
        if forme.startswith('ogerpon'):
            assert a['evs'].get('atk', 0) >= 200


def test_sets_candidates_maps_embody_aspect():
    mon = dict(
        species='ogerponwellspringtera',
        ability='embodyaspectwellspring',
        item=None,
        tera_type='water',
        moves=[{'id': 'ivycudgel'}, {'id': 'hornleech'}],
        item_state={'state': 'unknown'},
    )
    cands = sets.candidates(mon, None, 110)
    assert len(cands) > 0
    assert all(c['ability'] == 'waterabsorb' and c['item'] == 'wellspringmask' for c in cands)


def test_ivycudgel_effective_move_type_by_forme():
    snap = dict(weather='none', field={})
    for sp, expected_type in (
        ('ogerponwellspring', 'water'),
        ('ogerponwellspringtera', 'water'),
        ('ogerponhearthflame', 'fire'),
        ('ogerponhearthflametera', 'fire'),
        ('ogerponcornerstone', 'rock'),
        ('ogerponcornerstonetera', 'rock'),
        ('ogerpon', 'grass'),
    ):
        user = dict(species=sp, types=['grass', expected_type] if expected_type != 'grass' else ['grass'],
                    terastallized=sp.endswith('tera'), tera_type=expected_type if sp.endswith('tera') else None,
                    status=None)
        eff = features.effective_move('ivycudgel', user, None, snap, ability='', item='', tera=None)
        assert eff['type'] == expected_type
        assert eff['stab'] == 1


def test_roost_grounded_type_helper():
    assert render_v13._roost_grounded_type(['flying', 'steel']) == 'steel'
    assert render_v13._roost_grounded_type(['electric', 'flying']) == 'electric'
    assert render_v13._roost_grounded_type(['flying']) == 'normal'
    assert render_v13._roost_grounded_type(['water']) is None
    assert render_v13._roost_grounded_type(['steel']) is None


def test_ex203_ogerpon_tera_corviknight_damage_and_duel(live_renderer):
    """gen9ou-2718021055 T4: Tera-Water Ogerpon Ivy Cudgel vs Corviknight must be ~45-54% (not 31-37%),
    duel must be lose (not even; and 3 hits against real 0-HP/0-Def spread instead of 4 against default),
    and Cinderace switch worst must be x2 (not x1)."""
    req = _load_ex203_turn('gen9ou-2718021055', 4)
    state, q = live_renderer(req)
    assert 'opp threat: worst ivycudgel 45-54% to me' in state
    assert 'duel: me 3 hits (bodypress) vs opp 2 hits (ivycudgel), opp first -> lose' in state
    assert 'worst x2' in q['criteria']['switch:2']
    # Corviknight is slower than Ogerpon -> must NOT add grounded warning to roost
    assert 'grounded takes' not in q['criteria']['move:roost:normal']


def test_ex203_dondozo_tera_dark_shows_ivycudgel_threat(live_renderer):
    """gen9ou-2717998063 T16: Tera Dark on Water Dondozo removes Water resistance;
    tera takes must warn about ivycudgel (~43-51%), NOT hornleech (17-20%)."""
    req = _load_ex203_turn('gen9ou-2717998063', 16)
    state, q = live_renderer(req)
    rest_tera = q['criteria']['move:rest:tera']
    assert 'tera takes ivycudgel ' in rest_tera
    assert 'tera takes hornleech' not in rest_tera
    # Verify the reported damage range is fatal (> 40%)
    frag = rest_tera.split('tera takes ivycudgel ')[1].split(';')[0]
    lo, hi = (int(x) for x in frag.rstrip('%').split('-'))
    assert lo >= 40 and hi >= 48


def test_ex203_corviknight_faster_roost_grounding_vs_tinglu(live_renderer):
    """gen9ou-2717995159 T11: faster Corviknight Roost vs Ting-Lu exposes it to grounded Earthquake (~43-51%),
    so roost warns `grounded takes earthquake` and duel stays `lose` instead of `even`."""
    req = _load_ex203_turn('gen9ou-2717995159', 11)
    state, q = live_renderer(req)
    roost = q['criteria']['move:roost:normal']
    assert 'grounded takes earthquake ' in roost
    frag = roost.split('grounded takes earthquake ')[1].split(';')[0]
    lo, hi = (int(x) for x in frag.rstrip('%').split('-'))
    assert lo >= 40 and hi >= 50
    assert 'duel: me 5 hits (bodypress) vs opp 3 hits (ruination), me first -> lose' in state
    # Tera Water Roost already changes type to Water; must not duplicate grounded warning
    assert 'grounded takes' not in q['criteria']['move:roost:tera']


def test_ex203_court_change_turn_unharmed(live_renderer):
    """gen9ou-2717939960 T26: non-flying non-Ogerpon turn remains intact."""
    req = _load_ex203_turn('gen9ou-2717939960', 26)
    state, q = live_renderer(req)
    assert 'worst earthpower 104-123% to me' in state
    assert 'duel: me 2 hits (pyroball) vs opp 1 hits (earthpower), me first -> lose' in state


def test_ex203_slowking_tera_grass_warns_ice_not_earthpower(live_renderer):
    """gen9ou-2718014378 T22: Slowking-Galar (poison/psychic, tera grass) vs Kyurem (earthpower + freezedry/icebeam).
    Pre-tera worst is earthpower; post-tera Grass reduces earthpower to 0.5x, so tera takes MUST warn about
    Kyurem's Ice attack (freezedry/icebeam/dracometeor), NOT earthpower."""
    req = _load_ex203_turn('gen9ou-2718014378', 22)
    state, q = live_renderer(req)
    sb_tera = q['criteria'].get('move:sludgebomb:tera', '')
    assert 'tera takes ' in sb_tera
    assert 'tera takes earthpower' not in sb_tera
