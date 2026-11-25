"""Unit & mechanical invariant tests for EX-216 Matchup-Aware StateValueNetV2."""
from __future__ import annotations

import torch

from integration.laya_search import featurize as F
from integration.laya_search import matchup_features as MF
from integration.laya_search import value_model_v2 as VM2


def _make_mon(
    *,
    is_s1: bool,
    is_active: bool = False,
    alive: bool = True,
    hp: float = 1.0,
    stats=(350, 300, 250, 300, 250, 250),
    species='dragonite',
    ability='multiscale',
    item='heavydutyboots',
    types=('dragon', 'flying'),
    tera_type='normal',
    terastallized=False,
    moves=('dragondance', 'earthquake', 'extremespeed', 'roost'),
    boosts=(0, 0, 0, 0, 0),
):
    maxhp, atk, df, spa, spd, spe = stats
    num = [
        1.0 if is_s1 else 0.0,
        1.0 if is_active else 0.0,
        1.0 if alive else 0.0,
        hp if alive else 0.0,
        maxhp / 500.0, atk / 500.0, df / 500.0, spa / 500.0, spd / 500.0, spe / 500.0,
        1.0 if item != 'none' else 0.0,
        1.0 if item == 'heavydutyboots' else 0.0,
        1.0 if item in F.CHOICE_ITEMS else 0.0,
        1.0 if item in F.LEFTOVERS_ITEMS else 0.0,
        1.0 if terastallized else 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,  # status
        *[b / 6.0 for b in boosts],
        0.0, 0.0, 0.0,  # vols
    ]
    cat = [species, ability, item, types[0], types[1], tera_type, *moves]
    return num, cat


def _make_state(s1_mons, s2_mons, *, s1_sc=None, s2_sc=None, field=None):
    pad_n = [0.0] * F.MON_NUM_DIM
    pad_c = ['none'] * F.MON_CAT_DIM
    mn, mc = [], []
    for i in range(6):
        if i < len(s1_mons):
            mn.append(s1_mons[i][0])
            mc.append(s1_mons[i][1])
        else:
            mn.append(list(pad_n))
            mc.append(list(pad_c))
    for i in range(6):
        if i < len(s2_mons):
            mn.append(s2_mons[i][0])
            mc.append(s2_mons[i][1])
        else:
            mn.append(list(pad_n))
            mc.append(list(pad_c))
    s1v = s1_sc or [len(s1_mons) / 6.0, sum(m[0][3] for m in s1_mons) / 6.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0]
    s2v = s2_sc or [len(s2_mons) / 6.0, sum(m[0][3] for m in s2_mons) / 6.0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0]
    diffs = [s1v[0] - s2v[0], s1v[1] - s2v[1], s1v[2] - s2v[2], 0.0]
    fld = field or [0.0] * 9
    return dict(mon_num=mn, mon_cat=mc, global_num=s1v + s2v + diffs + fld)


def test_air_balloon_gholdengo_walls_dragonite():
    """Dragonite (EQ + ESpeed) vs Air Balloon Gholdengo must be detected as WALLED (0 dmg, is_walled=1)."""
    tables = MF.default_tables()
    raw = _make_state(
        [_make_mon(is_s1=True, is_active=True, species='dragonite', ability='multiscale',
                   item='heavydutyboots', types=('dragon', 'flying'),
                   moves=('dragondance', 'earthquake', 'extremespeed', 'roost'), stats=(372, 390, 226, 212, 236, 223))],
        [_make_mon(is_s1=False, is_active=True, species='gholdengo', ability='goodasgold',
                   item='airballoon', types=('steel', 'ghost'),
                   moves=('nastyplot', 'dazzlinggleam', 'psyshock', 'shadowball'), stats=(315, 112, 227, 365, 218, 293))],
    )
    mn = torch.tensor([raw['mon_num']], dtype=torch.float32)
    mc = tables.encode_raw_mon_cat([raw['mon_cat']], torch.device('cpu'))
    gn = torch.tensor([raw['global_num']], dtype=torch.float32)
    mon_m, glob_m = MF.compute_matchup_features(mn, mc, gn, tables)

    # Dragonite (slot 0): best_dmg_vs_opp_act (idx 23+0) == 0, is_walled (idx 23+3) == 1.0
    dnite_dmg = float(mon_m[0, 0, MF.MON_KIT_DIM + 0])
    dnite_walled = float(mon_m[0, 0, MF.MON_KIT_DIM + 3])
    ghold_dmg = float(mon_m[0, 6, MF.MON_KIT_DIM + 0])
    ghold_balloon = float(mon_m[0, 6, 0])
    act_walled_diff = float(glob_m[0, 2])
    assert dnite_dmg == 0.0, f'Expected 0 dmg vs Air Balloon Gholdengo, got {dnite_dmg}'
    assert dnite_walled == 1.0, f'Expected Dragonite walled=1.0, got {dnite_walled}'
    assert ghold_balloon == 1.0
    assert ghold_dmg > 0.15
    assert act_walled_diff == -1.0  # I am walled (-1), opp is not

    # Now pop the Air Balloon -> Earthquake hits super-effectively!
    raw['mon_cat'][6][2] = 'none'
    mc2 = tables.encode_raw_mon_cat([raw['mon_cat']], torch.device('cpu'))
    mon_m2, glob_m2 = MF.compute_matchup_features(mn, mc2, gn, tables)
    assert float(mon_m2[0, 0, MF.MON_KIT_DIM + 0]) > 0.65
    assert float(mon_m2[0, 0, MF.MON_KIT_DIM + 3]) == 0.0
    assert float(glob_m2[0, 2]) == 0.0


def test_water_absorb_and_draining_kiss_mechanics():
    """Water Absorb zeros Water attacks; Draining Kiss computes drain heal & blocks false 2HKO."""
    tables = MF.default_tables()
    raw = _make_state(
        [_make_mon(is_s1=True, is_active=True, species='dondozo', ability='unaware',
                   item='leftovers', types=('water', 'none'),
                   moves=('waterfall', 'liquidation', 'rest', 'sleeptalk'), stats=(504, 236, 361, 149, 167, 106))],
        [_make_mon(is_s1=False, is_active=True, species='ogerponwellspring', ability='waterabsorb',
                   item='wellspringmask', types=('grass', 'water'),
                   moves=('ivycudgel', 'hornleech', 'taunt', 'swordsdance'), stats=(301, 339, 204, 140, 228, 350))],
    )
    mn = torch.tensor([raw['mon_num']], dtype=torch.float32)
    mc = tables.encode_raw_mon_cat([raw['mon_cat']], torch.device('cpu'))
    gn = torch.tensor([raw['global_num']], dtype=torch.float32)
    mon_m, _ = MF.compute_matchup_features(mn, mc, gn, tables)
    # Dondozo with only Water attacks is walled by Water Absorb Ogerpon-Wellspring!
    assert float(mon_m[0, 0, MF.MON_KIT_DIM + 0]) == 0.0
    assert float(mon_m[0, 0, MF.MON_KIT_DIM + 3]) == 1.0
    # Ogerpon-Wellspring has absorb_heal flag, drain flag, and positive drain heal vs Dondozo
    assert float(mon_m[0, 6, 8]) == 1.0   # absorb_heal_ab
    assert float(mon_m[0, 6, 15]) == 1.0  # has_drain_move
    assert float(mon_m[0, 6, MF.MON_KIT_DIM + 5]) > 0.25  # Horn Leech drain heal %


def test_exact_antisymmetry_and_tera_type_flip():
    """`V_phi_v2(swap(s)) == 1 - V_phi_v2(s)` to floating-point precision, and Tera changes defensive type."""
    tables = MF.default_tables()
    model = VM2.StateValueNetV2(d_model=32, dropout=0.0)
    model.eval()

    raw = _make_state(
        [
            _make_mon(is_s1=True, is_active=True, species='great_tusk', ability='protosynthesis',
                      item='heavydutyboots', types=('ground', 'fighting'), tera_type='steel',
                      terastallized=True, moves=('headlongrush', 'closecombat', 'icespinner', 'rapidspin'),
                      boosts=(1, 0, 0, 0, 1)),
            _make_mon(is_s1=True, is_active=False, species='gholdengo', ability='goodasgold',
                      item='airballoon', types=('steel', 'ghost'),
                      moves=('shadowball', 'makeitrain', 'recover', 'nastyplot')),
        ],
        [
            _make_mon(is_s1=False, is_active=True, species='hatterene', ability='magicbounce',
                      item='leftovers', types=('psychic', 'fairy'), tera_type='water',
                      moves=('calmmind', 'drainingkiss', 'psyshock', 'mysticalfire'), hp=0.65),
        ],
        s1_sc=[2 / 6, 2 / 6, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        s2_sc=[1 / 6, 0.65 / 6, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0],
        field=[0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
    )
    swapped = F.swap_raw(raw)

    def _prob(r):
        mn = torch.tensor([r['mon_num']], dtype=torch.float32)
        mc = tables.encode_raw_mon_cat([r['mon_cat']], torch.device('cpu'))
        gn = torch.tensor([r['global_num']], dtype=torch.float32)
        mx, gx = VM2.build_v2_inputs(mn, mc, gn, tables, model.keep_idx)
        return float(model.win_prob(mx, gx).item()), mx, gx

    p1, mx1, gx1 = _prob(raw)
    p2, mx2, gx2 = _prob(swapped)
    assert abs((p1 + p2) - 1.0) < 1e-5, f'Antisymmetry violated: p1={p1}, p2={p2}'
    # Also verify exact swap_v2_tensors == build_v2_inputs(swap_raw)
    smx, sgx = VM2.swap_v2_tensors(mx1, gx1)
    assert torch.allclose(smx, mx2, atol=1e-5), f'mon swap max diff={(smx - mx2).abs().max()}'
    assert torch.allclose(sgx, gx2, atol=1e-5), f'glob swap max diff={(sgx - gx2).abs().max()}'
