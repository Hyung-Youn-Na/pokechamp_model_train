"""Unit tests for EX-218 Way C-1 teacher target builder (`gold_way_c1`) and hard-example prioritization."""
from __future__ import annotations

from integration.laya_v14 import data_way_c1 as C1


def test_gold_way_c1_promotes_walled_switch_and_water_absorb_rescue():
    # 1. Air Balloon Gholdengo T10 walled scenario: switch:5 promoted & gains decisive mass
    walled_st = 'board: me 5 alive 500% | opp 4 alive 400%\nduel: me 9+ hits (none) vs opp 3 hits (dazzlinggleam), opp first -> lose'
    p = {'move:dragondance:normal': 0.55, 'switch:5': 0.14, 'switch:2': 0.11, 'move:earthquake:normal': 0.02, 'move:roost:normal': 0.18}
    q_m50 = {'move:dragondance:normal': 0.36, 'switch:5': 0.42, 'switch:2': 0.41, 'move:earthquake:normal': 0.34, 'move:roost:normal': 0.35}
    q_v2 = {'move:dragondance:normal': 0.50, 'switch:5': 0.51, 'switch:2': 0.50, 'move:earthquake:normal': 0.45, 'move:roost:normal': 0.47}
    g, cands, _ = C1.gold_way_c1(p, q_m50, q_v2, state=walled_st)
    assert g is not None
    assert 'switch:5' in cands
    assert max(g, key=g.get) == 'switch:5', f'Expected switch:5 argmax on walled turn, got {g}'
    assert abs(sum(g.values()) - 1.0) < 1e-6

    # 2. Water Absorb + Taunt penalty (-0.15) flips Liquidation to switch:4
    p2 = {'move:liquidation:normal': 0.70, 'switch:4': 0.08, 'switch:5': 0.22}
    q_m2 = {'move:liquidation:normal': 0.96, 'switch:4': 0.95, 'switch:5': 0.92}
    q_v2b = {'move:liquidation:normal': 0.93, 'switch:4': 0.925, 'switch:5': 0.91}
    g2, cands2, _ = C1.gold_way_c1(p2, q_m2, q_v2b, absorb_penalties={'move:liquidation:normal': 0.15})
    assert g2 is not None
    assert 'switch:4' in cands2
    assert max(g2, key=g2.get) in ('switch:4', 'switch:5')


def test_hard_priority_always_ranks_walled_and_absorb_tier4():
    r_wall = {
        'sample_id': 'g1:p1:10:turn_action',
        'state': 'board: me 5 alive 500% | opp 4 alive 400%\nduel: me 9+ hits (none) vs opp 2 hits (shadowball), opp first -> lose',
        'questions': {'action': {'criteria': {'move:eq:normal': 'ground; fails', 'switch:2': 'darkrai'}}},
    }
    r_norm = {
        'sample_id': 'g1:p1:12:turn_action',
        'state': 'board: me 5 alive 500% | opp 5 alive 500%\nduel: me 2 hits (eq) vs opp 3 hits (tbolt), me first -> win',
        'questions': {'action': {'criteria': {'move:eq:normal': 'ground 2HKO', 'switch:2': 'darkrai'}}},
    }
    assert C1._hard_priority(r_wall)[0] == 4
    assert C1._hard_priority(r_norm)[0] == 0
