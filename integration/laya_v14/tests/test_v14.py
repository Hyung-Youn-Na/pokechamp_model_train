"""EP-244 / D-220 unit and real-battle regression tests for `laya-compact-v14` (`render_v14`)."""
from __future__ import annotations

import glob
import json
import os
import pytest

from integration.laya_engine import judge as J
from integration.laya_imitation import compact, features
from integration.laya_v10 import data_v10
from integration.laya_v14 import render_v14


@pytest.fixture(scope='module', autouse=True)
def _install_v14():
    render_v14.install()
    v1 = render_v14.VERSION
    render_v14.install()
    assert render_v14.VERSION == v1
    assert 'laya-compact-v14[' in v1
    for m in ('recoverko', 'drainheal', 'absorbheal'):
        assert m in v1


@pytest.fixture(scope='module')
def live_renderer():
    calc, judge = features.Calc(), J.Judge()
    try:
        yield data_v10.live_renderer(calc, judge)
    finally:
        calc.close()
        judge.close()


def _load_ex211_turn(game_prefix: str, turn: int):
    matches = sorted(glob.glob(f'/workspace/exports/laya-play/games/{game_prefix}*/events.jsonl'))
    if not matches:
        pytest.skip(f'EX-211 game {game_prefix} not found locally')
    with open(matches[0], encoding='utf-8') as f:
        for line in f:
            ev = json.loads(line)
            if ev.get('type') == 'input':
                body = dict(ev['body'])
                fp1 = body.pop('fp1', None) or {}
                snap = fp1.get('snapshot') or ev.get('snapshot') or {}
                if snap.get('turn') == turn and fp1.get('decision_kind') == 'turn_action':
                    return compact.ImitationInput.from_body(body)
    pytest.skip(f'EX-211 game {game_prefix} turn {turn} not found')


def test_v14_sleepman610_t4_strips_false_2hko_and_lists_drainingkiss(live_renderer):
    """sleepman610 T4 (Ting-Lu vs +1 Hatterene 49%):
    - v13 wrongly printed `dmg 29-34% 2HKO` despite Hatterene healing +34% from Draining Kiss + 6% Leftovers.
    - v14 MUST strip `2HKO` from Earthquake and include `drainingkiss` in `opp heals:`."""
    req = _load_ex211_turn('20261123-235250', 4)
    state, q = live_renderer(req)
    assert 'duel: me - hits (earthquake) vs opp 5 hits (drainingkiss), me first -> lose' in state
    eq = q['criteria']['move:earthquake:normal']
    assert '2HKO' not in eq, f'false 2HKO still present: {eq}'
    heals_lines = [l for l in state.splitlines() if l.startswith('opp heals:')]
    assert heals_lines, 'expected opp heals: line'
    assert 'drainingkiss' in heals_lines[0], heals_lines[0]


def test_v14_xrlylyl_t22_marks_water_absorb_heals_opp_25(live_renderer):
    """Xrlylyl T22 (Taunted Dondozo vs Ogerpon-Wellspring Water Absorb):
    - v13 only wrote `; fails` on Liquidation.
    - v14 MUST append `; heals opp 25%` AND include `waterabsorb` in `opp heals:`."""
    req = _load_ex211_turn('20261123-234704', 22)
    state, q = live_renderer(req)
    liq = q['criteria']['move:liquidation:normal']
    assert '; fails' in liq
    assert '; heals opp 25%' in liq, f'missing absorb heal warning: {liq}'
    heals_lines = [l for l in state.splitlines() if l.startswith('opp heals:')]
    assert heals_lines and 'waterabsorb' in heals_lines[0], heals_lines
