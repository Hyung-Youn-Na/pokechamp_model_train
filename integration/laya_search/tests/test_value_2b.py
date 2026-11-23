"""Unit tests for EP-243 / D-219 2-B neural state-value pipeline (`featurize`, `value_model`, `data_value_2b`, `search_2b`)."""
from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from integration.laya_search import featurize as F
from integration.laya_search import search_2b as S2B
from integration.laya_search import value_model as VM
from integration.laya_search.data_value_2b import parse_winner_side


def _fake_mon(species, hp=100, maxhp=100, atk=200, df=200, spa=200, spd=200, spe=200,
              types=('water', 'none'), ability='unaware', item='heavydutyboots', status='none',
              tera=False, tera_type='dark', moves=('liquidation', 'curse', 'rest', 'sleeptalk')):
    return SimpleNamespace(
        id=species, hp=hp, maxhp=maxhp, attack=atk, defense=df, special_attack=spa,
        special_defense=spd, speed=spe, types=types, ability=ability, item=item,
        status=status, terastallized=tera, tera_type=tera_type,
        moves=[SimpleNamespace(id=m) for m in moves],
    )


def _fake_side(mons, active_idx=0, atk_b=0, spa_b=0, sr=0, spikes=0, vols=()):
    sc = SimpleNamespace(stealth_rock=sr, spikes=spikes, toxic_spikes=0, sticky_web=0,
                         reflect=0, light_screen=0, aurora_veil=0, tailwind=0)
    return SimpleNamespace(
        pokemon=mons, active_index=active_idx,
        attack_boost=atk_b, defense_boost=0, special_attack_boost=spa_b, special_defense_boost=0, speed_boost=0,
        volatile_statuses=list(vols), side_conditions=sc,
    )


def _fake_state(s1_mons=None, s2_mons=None, s1_active=0, s2_active=0, s1_sr=0, s2_sr=0):
    m1 = s1_mons or [_fake_mon(f'mona{i}', hp=100 - 10 * i) for i in range(6)]
    m2 = s2_mons or [_fake_mon(f'monb{i}', hp=80 - 5 * i) for i in range(6)]
    return SimpleNamespace(
        side_one=_fake_side(m1, active_idx=s1_active, sr=s1_sr),
        side_two=_fake_side(m2, active_idx=s2_active, sr=s2_sr),
        weather='none', terrain='none', trick_room=False,
    )


def test_extract_raw_shapes_and_swap_involution():
    st = _fake_state(s1_active=2, s2_active=4, s1_sr=1, s2_sr=0)
    raw = F.extract_raw(st)
    assert len(raw['mon_num']) == F.NUM_SLOTS
    assert all(len(r) == F.MON_NUM_DIM for r in raw['mon_num'])
    assert len(raw['mon_cat']) == F.NUM_SLOTS
    assert all(len(r) == F.MON_CAT_DIM for r in raw['mon_cat'])
    assert len(raw['global_num']) == F.GLOBAL_NUM_DIM
    # Active pokemon must be placed at slot 0 (side_one) and slot 6 (side_two)
    assert raw['mon_cat'][0][0] == 'mona2'
    assert raw['mon_cat'][6][0] == 'monb4'
    assert raw['mon_num'][0][1] == 1.0 and raw['mon_num'][6][1] == 1.0
    # Swap involution: swap(swap(x)) == x
    sw = F.swap_raw(raw)
    assert sw['mon_cat'][0][0] == 'monb4'
    assert sw['mon_cat'][6][0] == 'mona2'
    sw2 = F.swap_raw(sw)
    assert sw2 == raw


def test_state_terminal_detection():
    alive = [_fake_mon('a', hp=50)] + [_fake_mon(f'f{i}', hp=0) for i in range(5)]
    dead = [_fake_mon(f'd{i}', hp=0) for i in range(6)]
    assert F.state_terminal(_fake_state(alive, alive)) is None
    assert F.state_terminal(_fake_state(alive, dead)) == 1.0
    assert F.state_terminal(_fake_state(dead, alive)) == 0.0
    assert F.state_terminal(_fake_state(dead, dead)) == 0.5


def test_blim_eval_team_sets_count():
    teams = F.blim_eval_team_sets()
    assert len(teams) == 64
    assert all(len(t) == 6 for t in teams)


def test_parse_winner_side():
    log = "|player|p1|Alice 123|1|1700\n|player|p2|Bob_99|2|1750\n|turn|1\n|win|Bob_99\n"
    assert parse_winner_side(log) == 'p2'
    log_tie = "|player|p1|Alice|1|1700\n|player|p2|Bob|2|1700\n|tie\n"
    assert parse_winner_side(log_tie) is None


def test_state_value_net_exact_antisymmetry_and_checkpoint_roundtrip(tmp_path: Path):
    st1 = _fake_state(s1_sr=1, s2_sr=0)
    raw1 = F.extract_raw(st1)
    raw1_sw = F.swap_raw(raw1)
    # Mirrored symmetric state must yield exact 0.5 win probability
    m = [_fake_mon(f'mirror{i}', hp=75) for i in range(6)]
    raw_sym = F.extract_raw(_fake_state(m, m, s1_sr=1, s2_sr=1))

    vocab = F.Vocab.build([raw1['mon_cat'], raw_sym['mon_cat']], min_freq=1)
    torch.manual_seed(0)
    model = VM.StateValueNet(vocab.sizes(), d_model=64, dropout=0.25)
    model.eval()

    def _to_t(raws):
        mn = torch.tensor([r['mon_num'] for r in raws], dtype=torch.float32)
        mc = torch.tensor([vocab.encode_cat(r['mon_cat']) for r in raws], dtype=torch.long)
        gn = torch.tensor([r['global_num'] for r in raws], dtype=torch.float32)
        return mn, mc, gn

    with torch.no_grad():
        p1, p1_sw, p_sym = model.win_prob(*_to_t([raw1, raw1_sw, raw_sym])).tolist()
    assert math.isclose(p1 + p1_sw, 1.0, abs_tol=1e-5)
    assert math.isclose(p_sym, 0.5, abs_tol=1e-5)

    # Save & reload must match bit-for-bit
    ckpt = tmp_path / 'ckpt'
    model.temperature.fill_(1.35)
    VM.save_value_checkpoint(model, vocab, ckpt, meta=dict(test=True))
    scorer = VM.ValueScorer(ckpt, device='cpu')
    reloaded = scorer.score_raw_batch([raw1, raw1_sw, raw_sym])
    assert math.isclose(reloaded[0] + reloaded[1], 1.0, abs_tol=1e-5)
    assert math.isclose(reloaded[2], 0.5, abs_tol=1e-5)


def test_choose_fused_2b_fixes_court_change_suicide_when_vphi_sees_survival():
    """When MCTS inherits evaluate.rs hazard bias (0.79 for Court Change suicide) but V_phi sees real survival win-rate."""
    p = {'move:courtchange:normal': 0.776, 'move:uturn:normal': 0.071, 'switch:4': 0.050}
    q_mcts = {'move:courtchange:normal': 0.792, 'move:uturn:normal': 0.508, 'switch:4': 0.488}
    # Learned V_phi: losing Cinderace drops win prob to 0.28, keeping Cinderace via U-turn keeps 0.64
    q_vphi = {'move:courtchange:normal': 0.280, 'move:uturn:normal': 0.640, 'switch:4': 0.610}
    # At alpha=0.65 (V_phi weighted), U-turn beats Court Change suicide cleanly
    pick, scores, delta = S2B.choose_fused_2b(p, q_mcts, q_vphi, alpha=0.65)
    assert pick == 'move:uturn:normal'
    assert delta > 0.015
    # Fallback when q_vphi is None (e.g. forced_switch) behaves identically to 2-A
    pick_2a, _, _ = S2B.choose_fused_2b(p, q_mcts, None)
    assert pick_2a == 'move:courtchange:normal'
