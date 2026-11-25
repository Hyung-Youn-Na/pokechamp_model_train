"""Unit tests for EX-225 (Way C-1 Clean) & EX-226 (Way B prompt tool injection + Tool Dropout + Human Anchor)."""
from __future__ import annotations

from integration.laya_v14 import data_way_b as DWB
from integration.laya_v14 import data_way_c1_v3 as DC1


def test_c1_clean_blocks_high_hp_roost_and_walled_protect_rescue():
    # High-HP 96% Dragonite vs 1% Garchomp: Roost must NOT be rescue-promoted when outside near-cands
    state = 'ME dragonite [dragon flying] 96% | ability multiscale\n'
    p = {'move:extremespeed:normal': 0.80, 'move:dragondance:normal': 0.15, 'move:roost:normal': 0.05}
    qm = {'move:extremespeed:normal': 0.65, 'move:dragondance:normal': 0.66, 'move:roost:normal': 0.66}
    qv = {'move:extremespeed:normal': 0.72, 'move:dragondance:normal': 0.71, 'move:roost:normal': 0.82}
    g, cands, _ = DC1.gold_way_c1_clean(p, qm, qv, state=state)
    assert g is not None
    assert 'move:roost:normal' not in cands, f'96% HP Roost must not be rescue-promoted: {cands}'

    # Walled Gliscor: Protect must NOT be rescue-promoted
    walled_st = 'duel: me 9+ hits (none) vs opp 5 hits (bodypress), me first -> lose\nME gliscor [ground flying] 100%\n'
    p2 = {'move:spikes:normal': 0.75, 'switch:4': 0.20, 'move:protect:normal': 0.05}
    qm2 = {'move:spikes:normal': 0.50, 'switch:4': 0.51, 'move:protect:normal': 0.55}
    qv2 = {'move:spikes:normal': 0.50, 'switch:4': 0.51, 'move:protect:normal': 0.54}
    g2, cands2, _ = DC1.gold_way_c1_clean(p2, qm2, qv2, state=walled_st)
    assert g2 is not None
    assert 'move:protect:normal' not in cands2


def test_way_b_eval_line_formatting_and_nonblunder_human_blend():
    valid = ['move:earthquake:normal', 'move:extremespeed:tera', 'move:roost:normal', 'switch:6']
    qm = {'move:earthquake:normal': 0.62, 'switch:6': 0.68, 'move:roost:normal': 0.60, 'move:extremespeed:tera': 0.64}
    qv = {'move:earthquake:normal': 0.55, 'switch:6': 0.61, 'move:roost:normal': 0.54, 'move:extremespeed:tera': 0.61}
    line = DWB.render_eval_line(qm, qv, valid)
    assert line == (
        'eval: mcts sw6 68% | extremespeed:tera -4% | earthquake -6% | roost -8%'
        ' || vphi extremespeed:tera 61% | sw6 = | earthquake -6% | roost -7%'
    )

    # Non-blunder human action within 0.03 of best -> 50/50 human blend preserved
    gold = {'switch:6': 0.80, 'move:extremespeed:tera': 0.20}
    blended, pres = DWB._blend_human_nonblunder(
        gold, 'move:extremespeed:tera', {'switch:6': 0.64, 'move:extremespeed:tera': 0.62},
        is_walled=False, has_absorb=False,
    )
    assert pres is True
    assert blended['move:extremespeed:tera'] == 0.60 and blended['switch:6'] == 0.40

    # Clear tactical blunder (gap 0.12 >= 0.03) -> pure clean teacher target!
    blended2, pres2 = DWB._blend_human_nonblunder(
        gold, 'move:extremespeed:tera', {'switch:6': 0.64, 'move:extremespeed:tera': 0.52},
        is_walled=False, has_absorb=False,
    )
    assert pres2 is False
    assert blended2 == gold


def test_matchup_eval_strips_calc_duel_and_renders_graded_advantage():
    from integration.laya_search import matchup_eval as ME

    raw_state = (
        'board: me 6 alive 600% | opp 6 alive 600%\n'
        'duel: me 2 hits (ceaselessedge) vs opp 6 hits (knockoff), opp first -> win\n'
        'ME tinglu [dark ground] 100%\n'
    )
    qm = {'move:ruination:normal': 0.4604, 'switch:3': 0.4783, 'switch:6': 0.4414}
    qv = {'move:ruination:normal': 0.4990, 'switch:3': 0.5430, 'switch:6': 0.5945}
    info = ME.assess_matchup(qm, qv, valid_ids=set(qm))
    assert info is not None and info['label'] == 'unfavorable' and info['is_unfavorable'] is True
    mline = ME.render_matchup_line(qm, qv, valid_ids=set(qm))
    assert mline == 'matchup: unfavorable (stay 48% vs switch 53%, -4%)'

    tools = DWB.render_tool_lines(qm, qv, list(qm))
    row = DWB._strip_and_inject_row({'state': raw_state}, tools)
    assert 'duel:' not in row['state']
    assert 'matchup: unfavorable (stay 48% vs switch 53%, -4%)' in row['state']
    assert 'eval: mcts sw3 48%' in row['state'] and '|| vphi sw6 59%' in row['state']


def test_serve_search_identity_for_ep249_way_b_and_no_search():
    from integration.laya_search import serve_search as SS

    sid_wb = SS.search_identity(
        iterations=50000, workers=4, value_checkpoint='/tmp/ex221',
        way_b=True, two_ply=True, walled_duel=True, no_calc_duel=True,
    )
    assert sid_wb['version'] == 'laya-way-b+2ply'
    assert sid_wb['way_b'] is True and sid_wb['two_ply'] is True and sid_wb['no_calc_duel'] is True
    assert 'data_way_b.py' in sid_wb['code']

    sid_ns = SS.search_identity(iterations=50000, workers=4, walled_duel=True, no_search=True)
    assert sid_ns['version'] == 'laya-standalone'
    assert sid_ns['no_search'] is True and sid_ns['iterations'] == 0 and sid_ns['workers'] == 0
