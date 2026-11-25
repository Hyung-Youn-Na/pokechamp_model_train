"""Unit & invariant tests for EX-221 Future-Aware StateValueNetV3 (`featurize_v3`, `value_model_v3`)."""
from __future__ import annotations

import torch

from integration.laya_search import featurize as F
from integration.laya_search import featurize_v3 as F3
from integration.laya_search import matchup_features as MF
from integration.laya_search import value_model_v3 as VM3
from integration.laya_search.tests.test_value_v2 import _make_mon, _make_state


def test_v3_exact_antisymmetry_all_heads():
    """Win logit AND all 5 future auxiliary heads must satisfy exact zero-sum antisymmetry under side swap."""
    tables = MF.default_tables()
    model = VM3.StateValueNetV3(d_model=32, dropout=0.0)
    model.eval()

    raw = _make_state(
        [
            _make_mon(is_s1=True, is_active=True, species='dragonite', ability='multiscale',
                      item='heavydutyboots', types=('dragon', 'flying'), hp=0.85,
                      moves=('dragondance', 'earthquake', 'extremespeed', 'roost'), boosts=(1, 0, 0, 0, 0)),
            _make_mon(is_s1=True, is_active=False, species='gliscor', ability='poisonheal',
                      item='toxicorb', types=('ground', 'flying'), hp=1.0,
                      moves=('protect', 'spikes', 'toxic', 'earthquake')),
        ],
        [
            _make_mon(is_s1=False, is_active=True, species='gholdengo', ability='goodasgold',
                      item='airballoon', types=('steel', 'ghost'), hp=0.94,
                      moves=('nastyplot', 'shadowball', 'makeitrain', 'recover'), boosts=(0, 0, 2, 0, 0)),
        ],
        s1_sc=[2 / 6, 1.85 / 6, 0.0, 0, 1, 0, 0, 0, 0, 0, 0],
        s2_sc=[1 / 6, 0.94 / 6, 1.0, 1, 0, 0, 0, 0, 0, 0, 0],
    )
    # Add non-trivial v3 dynamic channels (PP + just_used_heal + just_used_setup)
    v3_mon = [[0.25, 0.25, 1.0, 0.0], [0.0, 1.0, 0.0, 0.0]] + [[0.0] * 4] * 4 + [[1.0, 1.0, 0.0, 0.0]] + [[0.0] * 4] * 5
    v3_glob = [1.0, 0.0, 0.0, 0.125, 0.0, 0.0, 1.0, 1.0]
    raw['v3_mon'] = v3_mon
    raw['v3_glob'] = v3_glob

    swapped = F3.swap_raw_v3(raw)

    def _run(r):
        mn = torch.tensor([r['mon_num']], dtype=torch.float32)
        mc = tables.encode_raw_mon_cat([r['mon_cat']], torch.device('cpu'))
        gn = torch.tensor([r['global_num']], dtype=torch.float32)
        vm = torch.tensor([r['v3_mon']], dtype=torch.float32)
        vg = torch.tensor([r['v3_glob']], dtype=torch.float32)
        mx, gx = VM3.build_v3_inputs(mn, mc, gn, vm, vg, tables, model.keep_idx, model.pair_idx)
        wl, fut = model.forward_all(mx, gx)
        return float(wl.item()), fut[0], mx, gx

    w1, f1, mx1, gx1 = _run(raw)
    w2, f2, mx2, gx2 = _run(swapped)

    assert abs(w1 + w2) < 1e-5, f'Win logit antisymmetry violated: {w1} vs {w2}'
    assert torch.allclose(f1, -f2, atol=1e-5), f'Future heads antisymmetry violated: {f1} vs {f2}'
    smx, sgx = VM3.swap_v3_tensors(mx1, gx1)
    assert torch.allclose(smx, mx2, atol=1e-5)
    assert torch.allclose(sgx, gx2, atol=1e-5)


def test_v3_board_adv_and_boost_diff_antisymmetry():
    raw = _make_state(
        [_make_mon(is_s1=True, is_active=True, hp=0.70, boosts=(2, 0, 0, 0, 1))],
        [_make_mon(is_s1=False, is_active=True, hp=0.95, boosts=(0, 6, 0, 0, 0))],
    )
    sw = F.swap_raw(raw)
    assert abs(F3.board_advantage(raw) + F3.board_advantage(sw)) < 1e-6
    assert abs(F3.active_boost_diff(raw) + F3.active_boost_diff(sw)) < 1e-6
    assert F3.active_boost_diff(raw) < 0.0  # opp has +6 def vs our +2 atk +1 spe
