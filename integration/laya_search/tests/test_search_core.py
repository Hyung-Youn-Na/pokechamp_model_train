"""Unit and integration tests for EP-243 / D-219 2-A online multi-turn search (`integration/laya_search/`)."""
from __future__ import annotations

import math
import threading

import pytest

from integration.laya_search import search_core as SC
from integration.laya_search import serve_search as SS


def test_gpu_isolation_constants():
    assert SC.GPU0_UUID == 'GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4'
    assert SC.GPU1_UUID == 'GPU-c7e2d577-573f-0412-1ed6-ad6648efa454'
    assert len(SC.ALLOWED_GPU_UUIDS) == 2
    # GPUs 2 and 3 must never be listed
    assert 'GPU-c79ce3fd-81e7-454b-75ce-e63fad63baa4' not in SC.ALLOWED_GPU_UUIDS
    assert 'GPU-fd337c1e-b087-b26d-4dc0-a195c2b3a8d6' not in SC.ALLOWED_GPU_UUIDS


def test_choose_fused_rescues_kingambit_3v1_blunder():
    """Exact EX-203 gen9ou-2718019409 T35 numbers: low-prior Ice Beam (0.054) rescued by MCTS Q (+0.086)."""
    p = {
        'switch:2': 0.510,
        'switch:3': 0.399,
        'move:icebeam:normal': 0.054,
        'move:chillyreception:normal': 0.030,
        'move:sludgebomb:normal': 0.007,
    }
    q_mcts = {
        'switch:2': 0.518,
        'switch:3': 0.522,
        'move:icebeam:normal': 0.608,
        'move:chillyreception:normal': 0.578,
        'move:sludgebomb:normal': 0.520,
    }
    pick, scores, delta = SC.choose_fused(p, q_mcts)
    assert pick == 'move:icebeam:normal'
    assert delta > SC.MARGIN
    assert scores['move:icebeam:normal'] > scores['switch:2']


def test_choose_fused_avoids_dondozo_suicide_tera():
    """Exact EX-203 gen9ou-2717998063 T16 numbers: avoids rest:tera (0.500) in favor of rest:normal."""
    p = {'move:rest:tera': 0.500, 'switch:4': 0.189, 'move:rest:normal': 0.124, 'switch:3': 0.114}
    q_mcts = {'move:rest:tera': 0.332, 'switch:4': 0.380, 'move:rest:normal': 0.459, 'switch:3': 0.385}
    pick, scores, delta = SC.choose_fused(p, q_mcts)
    assert pick == 'move:rest:normal'
    assert delta > SC.MARGIN


def test_choose_fused_respects_laya_prior_on_near_ties():
    """When MCTS Q values are close, strong laya prior wins (does not degenerate to noisy MCTS flips)."""
    p = {'move:a:normal': 0.75, 'move:b:normal': 0.15, 'move:c:normal': 0.10}
    q_mcts = {'move:a:normal': 0.520, 'move:b:normal': 0.540, 'move:c:normal': 0.500}
    pick, scores, delta = SC.choose_fused(p, q_mcts)
    # 0.020 Q gap < 0.03 * ln(0.75/0.15) = 0.048 prior preference -> keeps move:a:normal
    assert pick == 'move:a:normal'


def test_choose_fused_respects_margin_threshold():
    p = {'move:a:normal': 0.50, 'move:b:normal': 0.50}
    q_mcts = {'move:a:normal': 0.500, 'move:b:normal': 0.510}  # delta 0.010 <= MARGIN 0.015
    pick, _, delta = SC.choose_fused(p, q_mcts)
    assert pick == 'move:a:normal'
    assert math.isclose(delta, 0.010, abs_tol=1e-9)


def test_choose_fused_fallback_on_missing_or_nan_q():
    p = {'move:a:normal': 0.6, 'move:b:normal': 0.4}
    assert SC.choose_fused(p, None)[0] == 'move:a:normal'
    assert SC.choose_fused(p, {})[0] == 'move:a:normal'
    assert SC.choose_fused(p, {'move:a:normal': float('nan'), 'move:b:normal': float('inf')})[0] == 'move:a:normal'


def test_served_probs_swaps_pick_to_strict_argmax():
    p = {'move:a:normal': 0.60, 'move:b:normal': 0.30, 'move:c:normal': 0.10}
    out = SC.served_probs(p, 'move:c:normal')
    assert max(out, key=out.get) == 'move:c:normal'
    assert math.isclose(sum(out.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(out['move:c:normal'], 0.60, abs_tol=1e-9)
    assert math.isclose(out['move:a:normal'], 0.10, abs_tol=1e-9)
    # Tie case still yields strict pick argmax
    tied = SC.served_probs({'a': 0.5, 'b': 0.5}, 'b')
    assert max(tied, key=tied.get) == 'b'
    assert math.isclose(sum(tied.values()), 1.0, abs_tol=1e-9)


def test_worker_pool_game_affinity_is_deterministic_and_threadsafe():
    class FakeWorker:
        def __init__(self, idx):
            self.idx = idx
            self.lock = threading.Lock()
            self.calls = []

        def call(self, req):
            with self.lock:
                self.calls.append(req['game'])
                return dict(worker=self.idx, game=req['game'])

    pool = object.__new__(SS.WorkerPool)
    pool.workers = [FakeWorker(i) for i in range(4)]

    results = []
    def run(gid):
        for _ in range(10):
            results.append(pool.call(dict(game=gid)))

    threads = [threading.Thread(target=run, args=(f'game-{i}',)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    by_game = {}
    for r in results:
        by_game.setdefault(r['game'], set()).add(r['worker'])
    assert len(by_game) == 8
    assert all(len(ws) == 1 for ws in by_game.values())
