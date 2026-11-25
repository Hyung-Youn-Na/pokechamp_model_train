"""EP-244 / D-220 unit and real-battle regression tests for 2-B v2 (`search_2b_v2`)."""
from __future__ import annotations

import copy
import pytest

from integration.laya_search import featurize as F
from integration.laya_search import search_2b_v2 as S2BV2


def test_foe_options_clean_strips_pp_annotations():
    state = (
        "turn 22 | turn_action | my tera ready | opp tera used\n"
        "OPP hatterene [water] 43% | ability ? | item leftovers | boosts spa+3 spd+3 | "
        "seen calmmind drainingkiss(13/16 used) storedpower | streak drainingkiss x3\n"
        "opp set: ability magicbounce 1; likely moves nuzzle .45, mysticalfire .44\n"
        "opp team: glimmora [rock poison] 100% || kingambit [dark steel] fainted\n"
    )
    opts = S2BV2.foe_options_clean(state)
    assert 'foe:move:drainingkiss' in opts
    assert 'foe:move:calmmind' in opts
    assert 'foe:move:storedpower' in opts
    assert not any('(' in k or 'used)' in k for k in opts), opts
    assert 'foe:switch:glimmora' in opts
    assert 'foe:switch:kingambit' not in opts


def test_is_duel_lose_detection():
    assert S2BV2.is_duel_lose("turn 5\nduel: me - hits (earthquake) vs opp 4 hits (drainingkiss), me first -> lose\n")
    assert not S2BV2.is_duel_lose("turn 5\nduel: me 1 hits (pyroball) vs opp 1 hits (storedpower), me first -> win\n")
    assert not S2BV2.is_duel_lose("turn 5\nME tinglu 100%\n")


def test_sleepman610_t5_draining_kiss_v2_overrides_to_switch():
    """Real EX-211 sleepman610 T5 (Ting-Lu vs +1 Draining Kiss Hatterene):
    In v1, `earthquake` stayed #1 despite `duel: lose` and `q_vphi` ranking switch:4/switch:1 above earthquake.
    In v2, scale-matched V_phi + `duel: lose` prior relaxation should flip the pick away from `earthquake`."""
    state = (
        "turn 5 | turn_action\n"
        "duel: me - hits (earthquake) vs opp 4 hits (drainingkiss), me first -> lose\n"
    )
    p = {
        'move:earthquake:normal': 0.827,
        'switch:1': 0.0873,
        'switch:2': 0.0355,
        'move:payback:normal': 0.0187,
        'move:rest:normal': 0.0151,
        'switch:4': 0.0049,
        'switch:6': 0.0056,
    }
    q_mcts = {
        'move:earthquake:normal': 0.5184,
        'move:payback:normal': 0.4734,
        'switch:4': 0.4449,
        'switch:1': 0.4422,
        'switch:6': 0.4416,
        'switch:2': 0.435,
        'move:rest:normal': 0.44,
    }
    q_vphi = {
        'switch:4': 0.5267,
        'switch:1': 0.5074,
        'move:earthquake:normal': 0.5025,
        'switch:2': 0.4933,
        'switch:6': 0.4919,
        'move:payback:normal': 0.481,
        'move:rest:normal': 0.485,
    }
    pick, scores, delta, meta = S2BV2.choose_fused_2b_v2(p, q_mcts, q_vphi, state=state)
    assert meta['duel_lose'] is True
    assert meta['eff_lam'] == S2BV2.PRIOR_LAMBDA_LOSE
    assert meta['scale_v'] > 1.5
    # V_phi + relaxed prior makes switch:4 strongly competitive (and beats or closely challenges earthquake)
    assert scores['switch:4'] > scores['switch:2']
    # Specifically check that on T6 where earthquake p drops to 0.63 and V_phi gap widens (0.4744 vs 0.4477),
    # v2 overrides to switch or rest rather than repeating earthquake!
    p6 = {'move:earthquake:normal': 0.6304, 'move:rest:normal': 0.2648, 'switch:1': 0.0665, 'switch:4': 0.0049}
    qm6 = {'move:earthquake:normal': 0.531, 'move:rest:normal': 0.4961, 'switch:1': 0.45, 'switch:4': 0.4542}
    qv6 = {'switch:4': 0.4744, 'move:rest:normal': 0.472, 'switch:1': 0.4546, 'move:earthquake:normal': 0.4477}
    pick6, _, _, _ = S2BV2.choose_fused_2b_v2(p6, qm6, qv6, state=state)
    assert pick6 != 'move:earthquake:normal', f'T6 should not repeat earthquake, got {pick6}'


def test_xrlylyl_t22_water_absorb_penalty_overrides_liquidation():
    """Real EX-211 Xrlylyl T22 (Taunted Dondozo vs 6% Water Absorb Ogerpon-Wellspring):
    With absorb-heal penalty + patched V_phi state, v2 avoids clicking Liquidation to heal Ogerpon."""
    p = {
        'move:liquidation:normal': 0.5498,
        'switch:2': 0.1755,
        'switch:4': 0.1454,
        'switch:3': 0.0535,
        'switch:5': 0.0349,
        'switch:1': 0.0325,
    }
    q_mcts = {
        'move:liquidation:normal': 0.3474,
        'switch:4': 0.3116,
        'switch:5': 0.3068,
        'switch:3': 0.2909,
        'switch:2': 0.2419,
        'switch:1': 0.233,
    }
    # After patching opp hp 6% -> 31% on liquidation child states, q_vphi for liquidation drops slightly below switch:4
    q_vphi = {
        'switch:4': 0.9357,
        'switch:5': 0.9335,
        'switch:3': 0.9334,
        'move:liquidation:normal': 0.925,
        'switch:2': 0.927,
        'switch:1': 0.9264,
    }
    pen = {'move:liquidation:normal': 0.14}
    pick, _, delta, _ = S2BV2.choose_fused_2b_v2(p, q_mcts, q_vphi, absorb_penalties=pen)
    assert pick != 'move:liquidation:normal', f'should switch instead of healing Water Absorb opp, got {pick}'
    assert delta > 0.015


def test_patch_raw_opp_heal_preserves_antisymmetry():
    mon_num = [[0.0] * F.MON_NUM_DIM for _ in range(12)]
    for i in range(6):
        mon_num[i][0] = 1.0
    mon_num[0][1] = 1.0; mon_num[0][2] = 1.0; mon_num[0][3] = 0.80
    mon_num[6][0] = 0.0; mon_num[6][1] = 1.0; mon_num[6][2] = 1.0; mon_num[6][3] = 0.06
    gn = [0.0] * F.GLOBAL_NUM_DIM
    gn[1] = 0.80 / 6.0
    gn[12] = 0.06 / 6.0
    gn[23] = gn[1] - gn[12]
    raw = dict(mon_num=mon_num, mon_cat=[['none'] * F.MON_CAT_DIM for _ in range(12)], global_num=gn)

    patched = S2BV2._patch_raw_opp_heal(raw, 0.25)
    assert patched['mon_num'][6][3] == pytest.approx(0.31)
    assert patched['global_num'][12] == pytest.approx(0.31 / 6.0)
    assert patched['global_num'][23] == pytest.approx((0.80 - 0.31) / 6.0)
    # Double-swap returns identical dict
    assert F.swap_raw(F.swap_raw(patched)) == patched
