"""EP-236 unit checks that need neither foul-play nor laya (stdlib only)."""
import random

from integration.laya_distill import evaluation_distill as E


def test_kind():
    assert E._kind('switch:3') == 'switch'
    assert E._kind('move:earthquake:tera') == 'tera'
    assert E._kind('move:earthquake:normal') == 'move'


def test_paired_zero_when_identical():
    rows = [dict(sample_id='g%d:p1:%d:turn_action' % (i % 7, i), v=random.random()) for i in range(50)]
    d = E.paired(rows, rows, 'v', reps=200)
    assert d['n'] == 50 and d['replays'] == 7
    assert d['diff'] == 0 and d['ci95'] == [0, 0]


def test_paired_shift():
    base = [dict(sample_id='g%d:p1:%d:x' % (i % 5, i), v=1.0) for i in range(40)]
    new = [dict(r, v=1.5) for r in base]
    d = E.paired(new, base, 'v', reps=200)
    assert abs(d['diff'] - 0.5) < 1e-9 and d['ci95'][0] > 0.49
