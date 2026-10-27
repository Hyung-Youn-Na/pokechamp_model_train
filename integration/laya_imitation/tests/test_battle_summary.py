"""Denominators, pair scores and bootstrap bounds of the EX-119 summary."""
from integration.laya_imitation.battle import summarize


def rows(n_pairs=4):
    return [dict(slot_id='p%d-s%d' % (p, s), pair_id='p%d' % p) for p in range(n_pairs) for s in (0, 1)]


def outcome(row, status='completed', result='loss'):
    return dict(slot_id=row['slot_id'], status=status, result=result if status == 'completed' else None)


def test_counts_and_unattempted():
    r = rows()
    outs = [outcome(r[0], result='win'), outcome(r[1], result='draw'), outcome(r[2], status='failed')]
    s = summarize(r, outs, [0.1, 0.2, 0.3])
    assert s['status'] == dict(completed=2, failed=1, incomplete=0, invalid=0, unattempted=5)
    assert (s['wins'], s['draws'], s['losses']) == (1, 1, 0)
    assert s['mean_score'] == 0.75 and s['completed_pairs'] == 1
    assert s['inference_seconds']['n'] == 3


def test_bootstrap_within_pair_score_range():
    r = rows()
    results = ['win', 'win', 'loss', 'loss', 'win', 'loss', 'draw', 'draw']
    s = summarize(r, [outcome(x, result=y) for x, y in zip(r, results)], [])
    low, high = s['pair_bootstrap_95']
    assert 0 <= low <= s['mean_score'] <= high <= 1
    assert s['completed_pairs'] == 4
