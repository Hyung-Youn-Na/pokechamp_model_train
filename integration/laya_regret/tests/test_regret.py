"""EP-235 unit checks (foul-play venv):
PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m pytest integration/laya_regret/tests
"""
import json

import pytest

from integration.laya_regret import paths as P
from integration.laya_regret import replay as R
from integration.laya_regret import search as S

GAME = P.SOURCE_RUN / 'games' / 'fp-b01-s1-a'
needs_data = pytest.mark.skipif(not GAME.exists(), reason='EX-174 games not mounted')


def test_aggregate_matches_foulplay_rule():
    # two samples, chance 0.6 / 0.4; visit shares (a .5, b .3, c .2) and (a .2, b .7, c .1)
    one = dict(total_visits=100, s1=[['a', 50, 30.0], ['b', 30, 12.0], ['c', 20, 4.0]])
    two = dict(total_visits=10, s1=[['a', 2, 1.0], ['b', 7, 5.6], ['c', 1, 0.1]])
    agg = S.aggregate([(0.6, one), (0.4, two)])
    assert agg['share']['a'] == pytest.approx(0.6 * 0.5 + 0.4 * 0.2)
    assert agg['share']['b'] == pytest.approx(0.6 * 0.3 + 0.4 * 0.7)
    assert sum(agg['share'].values()) == pytest.approx(1.0)
    assert agg['best'] == 'b'                                   # 0.46 vs a 0.38
    assert agg['considered'] == ['a', 'b']                      # a 0.38 >= 0.75 * 0.46
    # visit-weighted mean score: (0.6*30 + 0.4*1) / (0.6*50 + 0.4*2)
    assert agg['q']['a'] == pytest.approx((0.6 * 30 + 0.4 * 1) / (0.6 * 50 + 0.4 * 2))


def test_repeat_fraction_and_seed():
    picked = sum(S.in_repeat('fp-b%02d-s1-a' % (i % 64), i) for i in range(20000))
    assert abs(picked / 20000 - P.REPEAT_FRACTION) < 0.01
    assert S.seed_of('x', 3, 0) == S.seed_of('x', 3, 0) != S.seed_of('x', 3, 1)


@needs_data
def test_replay_maps_every_decision():
    game = R.load_game(GAME)
    points = list(R.replay(game))
    assert len(points) == len(game['choices'])                 # one decision point per laya request
    assert [p.rqid for p in points] == sorted(game['choices'])
    assert points[0].lead and not points[1].lead
    for point in points:
        chosen = game['choices'][point.rqid]
        assert R.fp_choice(point.view, chosen['command'])
        assert point.checks.get('own_active', True)


@needs_data
def test_sampling_is_seeded_and_options_cover_laya():
    game = R.load_game(GAME)
    point = list(R.replay(game))[5]
    first, ms = S.sample_states(point.view, S.seed_of(GAME.name, point.rqid, 0))
    again, _ = S.sample_states(point.view, S.seed_of(GAME.name, point.rqid, 0))
    assert first == again and ms == P.SEARCH_TIME_MS
    chosen = game['choices'][point.rqid]
    laya = {R.fp_choice(point.view, c) for c in chosen['commands'].values()}
    result = S.mcts(dict(id='t', state=first[0][0], ms=ms, iterations=5000))
    assert result['total_visits'] == 5000
    assert {o[0] for o in result['s1']} == laya
