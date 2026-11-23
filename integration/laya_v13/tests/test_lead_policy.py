"""EP-242 unit and EX-203 regression tests for `integration.laya_v13.lead_policy`."""
from __future__ import annotations

import csv
import glob
import json
import math
import os
import re
import pytest

from integration.laya_imitation import compact, features, features_v5
from integration.laya_v13 import lead_policy, render_v13


@pytest.fixture(scope='module', autouse=True)
def _install_v13():
    render_v13.install()


@pytest.fixture(scope='module')
def calc():
    c = features.Calc()
    try:
        yield c
    finally:
        c.close()


def _load_ex203_lead(battle_id: str):
    for p in glob.glob('/workspace/exports/laya-play/games/20261122-*/result.json'):
        r = json.load(open(p, encoding='utf-8'))
        if battle_id in (r.get('battle_tag') or ''):
            evp = os.path.join(os.path.dirname(p), 'events.jsonl')
            lead_inp = None
            with open(evp, encoding='utf-8') as f:
                for line in f:
                    ev = json.loads(line)
                    if ev.get('type') == 'input' and (ev.get('snapshot') or {}).get('decision_kind') == 'lead':
                        lead_inp = ev
                    elif ev.get('type') == 'selection' and lead_inp and ev.get('decision') == lead_inp['decision']:
                        return compact.ImitationInput.from_body(lead_inp['body']), ev['probabilities']
    pytest.skip(f'EX-203 battle {battle_id} lead not found locally')


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


def test_cell_score_bounds_and_ordering():
    fast_ohko = lead_policy.cell_score(dict(out=120.0, takes=40.0, speed='faster'))
    slow_ohko_victim = lead_policy.cell_score(dict(out=40.0, takes=120.0, speed='slower'))
    even_slow = lead_policy.cell_score(dict(out=40.0, takes=40.0, speed='slower'))
    even_fast = lead_policy.cell_score(dict(out=40.0, takes=40.0, speed='faster'))
    assert -1.0 <= slow_ohko_victim < even_slow < even_fast < fast_ohko <= 1.0
    assert fast_ohko > 0.7
    assert slow_ohko_victim < -0.7


def test_min_p_filter_keeps_top_and_normalizes():
    probs = {'lead:1': 0.50, 'lead:2': 0.25, 'lead:3': 0.15, 'lead:4': 0.05, 'lead:5': 0.03, 'lead:6': 0.02}
    w = lead_policy.min_p_filter(probs, min_p=0.25, temperature=1.0)
    assert set(w.keys()) == {'lead:1', 'lead:2', 'lead:3'}
    assert abs(sum(w.values()) - 1.0) < 1e-9
    # Even min_p=1.0 keeps the top choice cleanly
    w1 = lead_policy.min_p_filter(probs, min_p=1.0, temperature=1.0)
    assert w1 == {'lead:1': 1.0}


def test_opp_lead_prior_weights_hazard_and_sash_leads():
    fake_usage = {
        'ribombee': dict(moves=dict(stickyweb=1.0), items=dict(focussash=0.9)),
        'kingambit': dict(moves=dict(kowtowcleave=1.0), items=dict(leftovers=0.7)),
    }
    team = [dict(slot=1, species='kingambit'), dict(slot=2, species='ribombee'), dict(slot=3, species='unknownmon')]
    q = lead_policy.opp_lead_prior(team, usage_table=fake_usage, species_key_fn=lambda s: s if s in fake_usage else None)
    assert abs(sum(q.values()) - 1.0) < 1e-9
    assert q[2] > q[1] == q[3]


def test_non_lead_decision_returns_none(calc):
    req = _load_ex203_turn('gen9ou-2717939960', 26)
    probs = {'move:pyroball:normal': 0.6, 'switch:3': 0.4}
    assert lead_policy.reweight_lead(probs, req, calc=calc) is None
    choice, info = lead_policy.choose_lead(probs, req, calc=calc, seed=7)
    assert choice == 'move:pyroball:normal' and info is None


def test_reweight_lead_preserves_favorable_and_diversifies_ground_heavy_team(calc):
    # vs Zapdos/Kyurem/Ogerpon/Iron Treads/Pecharunt/Kingambit: Raging Bolt dominates
    req_a, probs_a = _load_ex203_lead('gen9ou-2717939960')
    info_a = lead_policy.reweight_lead(probs_a, req_a, calc=calc)
    assert info_a is not None
    assert info_a['top'] == 'lead:3'
    assert abs(sum(info_a['weights'].values()) - 1.0) < 1e-5

    # vs Kingambit/Iron Valiant/Great Tusk/Raging Bolt/Ting-Lu/Zamazenta: Slowking-G gains mass alongside Raging Bolt
    req_b, probs_b = _load_ex203_lead('gen9ou-2717927680')
    info_b = lead_policy.reweight_lead(probs_b, req_b, calc=calc)
    assert info_b is not None
    assert 'lead:1' in info_b['weights'] and 'lead:3' in info_b['weights']
    assert info_b['weights']['lead:1'] >= 0.15
    assert 'lead:4' not in info_b['weights']  # Corviknight 1% filtered out by min_p
    assert abs(sum(info_b['weights'].values()) - 1.0) < 1e-5


def test_lead_sampler_reproducible_and_valid_choice(calc):
    req_b, probs_b = _load_ex203_lead('gen9ou-2717927680')
    c1, info1 = lead_policy.choose_lead(probs_b, req_b, calc=calc, seed=20261123)
    c2, info2 = lead_policy.choose_lead(probs_b, req_b, calc=calc, seed=20261123)
    assert c1 == c2
    assert c1 in info1['weights']
    assert info1['weights'] == info2['weights']


def test_with_lead_2b_serving_wrapper_non_invasive(calc):
    req_lead, probs_lead = _load_ex203_lead('gen9ou-2717927680')
    req_turn = _load_ex203_turn('gen9ou-2717939960', 26)

    class DummyPolicy:
        def predict(self, value):
            if value is req_lead:
                return dict(input_sha256=value.sha256, action_ids=list(probs_lead),
                            probabilities=dict(probs_lead), choice='lead:3')
            return dict(input_sha256=value.sha256, action_ids=['move:pyroball:normal'],
                        probabilities={'move:pyroball:normal': 1.0}, choice='move:pyroball:normal')

    Wrapped = lead_policy.with_lead_2b(DummyPolicy, calc=calc)
    pol = Wrapped()
    out_lead = pol.predict(req_lead)
    assert out_lead['choice'] == 'lead:3'            # argmax unchanged
    assert out_lead['probabilities'] == probs_lead   # model probabilities unchanged
    assert 'lead_2b' in out_lead and 'weights' in out_lead['lead_2b']
    out_turn = pol.predict(req_turn)
    assert 'lead_2b' not in out_turn


def test_identity_metadata():
    meta = lead_policy.identity()
    assert meta['version'] == lead_policy.VERSION
    assert len(meta['sha256']) == 64


def test_ex203_1500_human_aggregate_regression(calc):
    """Verify 2b improves 1500+ human bad-lead rate and MinMax over argmax on EX-203."""
    replays_csv = '/workspace/exports/laya-play/ladder/replays.csv'
    if not os.path.exists(replays_csv):
        pytest.skip('EX-203 replays.csv not found')
    replays = {}
    with open(replays_csv, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            m = re.match(r'^(?:battle-)?(gen9ou-\d+)', r['battle_id'])
            if m:
                replays[m.group(1)] = r

    top_bots = {'MissingNo.ZeroBot', 'nickgen6rbrlbot'}
    ev_arg = []
    ev_2b = []
    n_games = 0
    for res_path in sorted(glob.glob('/workspace/exports/laya-play/games/20261122-*/result.json')):
        res = json.load(open(res_path, encoding='utf-8'))
        m = re.match(r'^(?:battle-)?(gen9ou-\d+)', res.get('battle_tag') or '')
        if not m:
            continue
        rep = replays.get(m.group(1), {})
        try:
            opp_r = int(rep.get('opponent_rating_before') or 0)
        except ValueError:
            continue
        if opp_r < 1500 or res.get('opponent') in top_bots:
            continue
        evp = os.path.join(os.path.dirname(res_path), 'events.jsonl')
        sha = lead_body = lead_probs = lead_dec = own_side = opp_lead_sp = None
        cur_turn = 0
        with open(evp, encoding='utf-8') as f:
            for line in f:
                ev = json.loads(line)
                t = ev.get('type')
                if t == 'response' and not sha:
                    sha = (ev.get('body') or {}).get('checkpoint_sha256', '')
                elif t == 'input' and (ev.get('snapshot') or {}).get('decision_kind') == 'lead':
                    lead_body, lead_dec, own_side = ev['body'], ev['decision'], ev.get('actor')
                elif t == 'selection' and lead_dec and ev.get('decision') == lead_dec:
                    lead_probs = ev.get('probabilities')
                elif t == 'protocol':
                    for pl in ev.get('protocol', '').splitlines():
                        parts = pl.split('|')
                        if len(parts) >= 3 and parts[1] == 'turn':
                            try:
                                cur_turn = int(parts[2])
                            except ValueError:
                                pass
                        elif len(parts) >= 4 and parts[1] == 'switch' and cur_turn == 0 and own_side:
                            if parts[2][:2] != own_side and opp_lead_sp is None:
                                opp_lead_sp = re.sub(r'[^a-z0-9]', '', parts[3].split(',')[0].lower())
        if not sha or not sha.startswith('22531f2f') or not lead_body or not lead_probs or not opp_lead_sp:
            continue
        req = compact.ImitationInput.from_body(lead_body)
        _, view = features_v5.resolved(req)
        from integration.laya_threat import spreads
        from integration.laya_v10 import strategy
        with spreads.patched():
            tbl = strategy.matchup(view, calc)
        opp_slot = next(
            (pm['slot'] for pm in view['opponent_team']
             if pm['species'] == opp_lead_sp or opp_lead_sp.startswith(pm['species'][:6])),
            None,
        )
        if opp_slot is None:
            continue
        info = lead_policy.reweight_lead(lead_probs, req, calc=calc, matchup_table=tbl)
        assert info is not None
        argmax_id = max(sorted(lead_probs), key=lambda k: lead_probs[k])
        argmax_slot = int(argmax_id.split(':')[1])
        ev_arg.append(lead_policy.cell_score(tbl[(argmax_slot, opp_slot)]))
        ev_2b.append(sum(w * lead_policy.cell_score(tbl[(int(k.split(':')[1]), opp_slot)])
                         for k, w in info['weights'].items()))
        n_games += 1

    assert n_games == 19
    assert sum(ev_2b) / n_games > sum(ev_arg) / n_games
