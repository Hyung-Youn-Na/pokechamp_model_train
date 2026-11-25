"""Unit & real-battle regression tests for Way A (Laya-Main Consensus Blunder Veto + Walled-Duel Fix)."""
from __future__ import annotations

import json
from pathlib import Path

from integration.laya_search import way_a as WA


def test_keep_laya_when_margins_small_or_vphi_vetoes_mcts_bias():
    """Laya stays in control on normal turns and is protected when MCTS & V_phi disagree."""
    p = {'move:a:normal': 0.55, 'move:b:normal': 0.30, 'switch:2': 0.15}
    # Small MCTS preference (+0.03 < 0.05) -> keep Laya
    pick, _, _, meta = WA.choose_way_a(
        p,
        {'move:a:normal': 0.50, 'move:b:normal': 0.53, 'switch:2': 0.48},
        {'move:a:normal': 0.50, 'move:b:normal': 0.51, 'switch:2': 0.49},
        state='board: me 5 alive 480% | opp 5 alive 470%',
    )
    assert pick == 'move:a:normal'
    assert meta['reason'] == 'keep_laya'

    # MCTS hallucination (+0.07) rejected by V_phi (-0.04) -> keep Laya!
    pick2, _, _, meta2 = WA.choose_way_a(
        p,
        {'move:a:normal': 0.50, 'move:b:normal': 0.57, 'switch:2': 0.45},
        {'move:a:normal': 0.50, 'move:b:normal': 0.46, 'switch:2': 0.48},
        state='board: me 5 alive 480% | opp 5 alive 470%',
    )
    assert pick2 == 'move:a:normal'
    assert meta2['reason'] == 'keep_laya'


def test_air_balloon_gholdengo_t10_and_t11_rescued_by_way_a_mcts50k_vphiv2():
    """Exact real-battle numbers from Air Balloon Gholdengo T10/T11: Way A vetoes Dragon Dance to switch!"""
    walled_state = (
        'board: me 5 alive 500% | opp 4 alive 400%\n'
        'duel: me 9+ hits (none) vs opp 3 hits (dazzlinggleam), opp first -> lose'
    )
    assert WA.is_walled_state(walled_state)
    # T10: Laya picks DD (0.5345), MCTS 50k picks switch:2/5 (+0.012~+0.016), EX-216 V_phi v2 has switch:5 (-0.027)
    p = {'move:dragondance:normal': 0.5345, 'switch:2': 0.1075, 'switch:5': 0.1402, 'move:earthquake:normal': 0.0118}
    q_mcts50 = {'move:dragondance:normal': 0.3840, 'switch:2': 0.3964, 'switch:5': 0.3992, 'move:earthquake:normal': 0.3518}
    q_vphi2 = {'move:dragondance:normal': 0.5280, 'switch:2': 0.5005, 'switch:5': 0.5010, 'move:earthquake:normal': 0.4614}
    pick, _, _, meta = WA.choose_way_a(p, q_mcts50, q_vphi2, state=walled_state, decision_kind='turn_action')
    assert pick in ('switch:2', 'switch:5'), f'Expected switch veto on walled Air Balloon T10, got {pick} ({meta})'
    assert meta['reason'] == 'walled_veto'


def test_water_absorb_taunt_severe_veto_and_court_change_vphi_veto():
    """Severe Taunt+WaterAbsorb penalty and V_phi 1-turn disaster both cleanly veto Laya."""
    # Xrlylyl T22 (Water Absorb + Taunt penalty -0.15)
    p = {'move:liquidation:normal': 0.65, 'switch:4': 0.25, 'switch:5': 0.10}
    q_mcts = {'move:liquidation:normal': 0.96, 'switch:4': 0.95, 'switch:5': 0.94}
    q_vphi = {'move:liquidation:normal': 0.9314, 'switch:4': 0.9243, 'switch:5': 0.9163}
    pick, _, _, meta = WA.choose_way_a(
        p, q_mcts, q_vphi,
        state='board: me 6 alive 520% | opp 1 alive 6%',
        absorb_penalties={'move:liquidation:normal': 0.15},
    )
    assert pick == 'switch:4'
    assert meta['reason'] == 'severe_mcts_veto'

    # Court Change 1-turn suicide caught by V_phi v2 (+0.16) while MCTS neutral
    p2 = {'move:courtchange:normal': 0.55, 'move:pyroball:normal': 0.35, 'switch:2': 0.10}
    q_m2 = {'move:courtchange:normal': 0.50, 'move:pyroball:normal': 0.505, 'switch:2': 0.45}
    q_v2 = {'move:courtchange:normal': 0.38, 'move:pyroball:normal': 0.54, 'switch:2': 0.42}
    pick2, _, _, meta2 = WA.choose_way_a(
        p2, q_m2, q_v2, state='board: me 4 alive 300% | opp 4 alive 300%',
    )
    assert pick2 == 'move:pyroball:normal'
    assert meta2['reason'] == 'vphi_blunder_veto'


def test_walled_duel_renderer_wrapper_on_real_air_balloon_t10():
    """Verify `install_walled_duel()` emits `duel: me 9+ hits (none) ... -> lose` on real T10 Air Balloon event."""
    ev_path = Path('/workspace/exports/laya-play/games/20261124-011825-nhy_test1629-laya-search2bv2-001/events.jsonl')
    if not ev_path.exists():
        return
    from integration.laya_engine import judge as J
    from integration.laya_imitation.features import Calc
    from integration.laya_v10 import data_v10
    from integration.laya_v13 import render_v13
    from integration.pokechamp.imitation.schema import ImitationInput

    render_v13.install()
    WA.install_walled_duel()
    fn = data_v10.live_renderer(Calc(), J.Judge())
    for line in ev_path.open():
        e = json.loads(line)
        if e.get('type') == 'http_request' and e['decision'] == 'nhy_test1629-27-119':
            body = dict(e['body']['input'])
            body.pop('fp1', None)
            st, _ = fn(ImitationInput.from_body(body))
            assert WA.is_walled_state(st), f'Expected walled duel line in rendered state:\n{st}'
            break
