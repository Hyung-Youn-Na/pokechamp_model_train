"""EX-134: laya-vs-laya schedule, mirrored side, attempt layout, summary and verdict."""
import json

from integration.laya_imitation import headtohead as h
from integration.laya_imitation.tests.test_comparison_summary import base, outcome


def test_schedule_covers_every_slot_once_per_other_model():
    rows = h.make_schedule(base())
    assert len(rows) == 128 * len(h.EX134.others) and len({r['slot_id'] for r in rows}) == len(rows)
    for other in h.EX134.others:
        sub = [r for r in rows if r['opponent_model'] == other]
        assert len(sub) == 128 and len({r['base_slot_id'] for r in sub}) == 128
        assert all(r['model'] == 'laya-v2t' and r['opponent'] == 'laya:' + other for r in sub)
    for i in range(0, len(rows), 2):
        a, b = rows[i], rows[i + 1]
        assert a['base_pair_id'] == b['base_pair_id'] and a['opponent_model'] == b['opponent_model']
        assert a['model_side'] == b['model_side'] and a['team_ids']['p1'] == b['team_ids']['p2']


def test_mirror_swaps_side_seeds_and_model():
    row = h.make_schedule(base())[0]
    m = h.mirror(row)
    assert m['model'] == row['opponent_model'] and m['opponent_model'] == row['model']
    assert m['model_side'] != row['model_side'] and m['model_seed'] == row['opponent_seed']
    assert m['opponent_seed'] == row['model_seed'] and m['teams'] == row['teams']
    assert h.mirror(m)['model'] == row['model'] and h.mirror(m)['model_seed'] == row['model_seed']


def test_attempt_layout_links_the_other_side(tmp_path):
    row = h.make_schedule(base())[0]
    request = dict(slot=row, names=dict(p1='layx', p2='oppx'), serving=dict(endpoint='http://a', checkpoint_sha256='A'),
                   deadline_monotonic=1.0, port=8108)
    (tmp_path / 'request.json').write_text(json.dumps(request))
    h.prepare_attempt(dict(endpoint='http://b', checkpoint_sha256='B'))(tmp_path)
    mirrored = json.loads((tmp_path / 'opponent/request.json').read_text())
    assert mirrored['serving']['checkpoint_sha256'] == 'B' and mirrored['slot']['model'] == row['opponent_model']
    assert mirrored['names'] == request['names'] and mirrored['deadline_monotonic'] == 1.0
    (tmp_path / 'opponent/events.jsonl').write_text('x\n')
    (tmp_path / 'events.jsonl').write_text('y\n')
    assert (tmp_path / 'opponent-events.jsonl').read_text() == 'x\n'
    assert (tmp_path / 'opponent/opponent-events.jsonl').read_text() == 'y\n'
    (tmp_path / 'battle-seed.jsonl').write_text('s\n')
    assert (tmp_path / 'opponent/battle-seed.jsonl').read_text() == 's\n'


def test_summary_and_verdict():
    rows = h.make_schedule(base())
    outs = [dict(outcome(r, 'win' if r['opponent_model'] == 'laya-v1' else 'loss'), model_side=r['model_side'],
                 opponent_model=r['opponent_model']) for r in rows]
    s = h.summarize_h2h(rows, outs, {})
    assert s['pairs']['laya-v1']['verdict'] == 'laya-v2t 우세'
    assert s['pairs']['laya-v2']['verdict'] == 'laya-v2 우세'
    split = [dict(outcome(r, 'win' if r['slot_id'].endswith('-a') else 'loss'), model_side=r['model_side'],
                  opponent_model=r['opponent_model']) for r in rows]
    assert h.summarize_h2h(rows, split, {})['pairs']['laya-v3t']['verdict'] == '구별되지 않음'
    short = [o for o in outs if not o['slot_id'].startswith('v1-m0')]
    assert h.summarize_h2h(rows, short, {})['pairs']['laya-v1']['verdict'].startswith('판정 보류')


def test_every_model_is_served_and_rendered():
    from integration.laya_imitation import serving
    for model in {m for st in h.STUDIES.values() for m in (st.base,) + st.others}:
        assert model in serving.MODELS and model in h.RENDER and model in h.RUNS and model in h.ABYSSAL


def test_ex135_is_the_new_candidates_on_gpu2():
    rows = h.make_schedule(base(), h.EX135)
    assert len(rows) == 256 and {r['opponent_model'] for r in rows} == {'laya-v2tw', 'laya-v4t'}
    assert h.EX135.gpu[0] == 2 and h.EX135.port == 8108 and h.EX135.out != h.EX134.out
