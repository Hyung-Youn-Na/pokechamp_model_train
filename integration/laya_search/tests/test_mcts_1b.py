"""Unit tests for EP-243 / D-219 1-B offline MCTS-5k Q rerank pipeline (`data_mcts_1b`, `train_mcts_1b`)."""
from __future__ import annotations

import math

import pytest

from integration.laya_search import data_mcts_1b as D1B
from integration.laya_search import train_mcts_1b as T1B


def test_select_candidates_promotes_kingambit_rescue():
    """Low-prior Ice Beam (0.054 < 0.15 * 0.510 = 0.0765) is auto-promoted when Q gap >= 0.08."""
    p = {
        'switch:2': 0.510,
        'switch:3': 0.399,
        'move:icebeam:normal': 0.054,
        'move:chillyreception:normal': 0.030,
        'move:sludgebomb:normal': 0.007,
    }
    q = {
        'switch:2': 0.510,
        'switch:3': 0.534,
        'move:icebeam:normal': 0.612,  # gap = +0.102 >= 0.08
        'move:chillyreception:normal': 0.580,
        'move:sludgebomb:normal': 0.525,
    }
    cands = D1B.select_candidates(p, q)
    assert 'switch:2' in cands and 'switch:3' in cands
    assert 'move:icebeam:normal' in cands


def test_gold_mcts_q_flips_kingambit_and_preserves_outside_mass():
    p = {
        'switch:2': 0.510,
        'switch:3': 0.399,
        'move:icebeam:normal': 0.054,
        'move:chillyreception:normal': 0.030,
        'move:sludgebomb:normal': 0.007,
    }
    q = {
        'switch:2': 0.510,
        'switch:3': 0.534,
        'move:icebeam:normal': 0.612,
        'move:chillyreception:normal': 0.580,
        'move:sludgebomb:normal': 0.525,
    }
    g, cands = D1B.gold_mcts_q(p, q)
    assert g is not None
    assert math.isclose(sum(g.values()), 1.0, abs_tol=1e-9)
    # Candidate mass preserved; outside moves untouched
    assert math.isclose(g['move:sludgebomb:normal'], 0.007, abs_tol=1e-9)
    # Ice Beam becomes the new argmax target!
    assert max(g, key=g.get) == 'move:icebeam:normal'


def test_gold_mcts_q_preserves_prior_on_close_q():
    p = {'move:a:normal': 0.70, 'move:b:normal': 0.20, 'move:c:normal': 0.10}
    q = {'move:a:normal': 0.52, 'move:b:normal': 0.54, 'move:c:normal': 0.50}  # +0.02 gap < ln(3.5)*0.04 = 0.05
    g, _ = D1B.gold_mcts_q(p, q)
    assert g is not None
    assert max(g, key=g.get) == 'move:a:normal'


def test_train_1b_gpu_isolation_and_arguments():
    assert T1B.GPUS == '0,1'
    argv = T1B.arguments('train')
    assert '--gpus' in argv
    assert argv[argv.index('--gpus') + 1] == '0,1'
    with pytest.raises(ValueError):
        D1B.infer(rank=2, world=2)
    with pytest.raises(ValueError):
        D1B.infer(rank=0, world=4)
