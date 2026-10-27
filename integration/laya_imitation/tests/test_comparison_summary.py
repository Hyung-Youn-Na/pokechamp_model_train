"""EX-122: interleaved 256-slot schedule, paired matchup-cluster difference, replication count and verdict."""
from integration.laya_imitation import comparison as cmp
from integration.laya_imitation import teams as t
from integration.laya_imitation.tests.test_teams import checker, pool


def base():
    chosen, _, _ = t.select(pool(), checker())
    return t.make_schedule(chosen)


def outcome(row, result, status='completed'):
    return dict(slot_id=row['slot_id'], model=row['model'], status=status, result=result if status == 'completed' else None,
                turns=30)


def test_schedule_interleaves_pairs_and_keeps_seeds():
    b = base()
    rows = cmp.make_schedule(b)
    assert len(rows) == 256 and len({r['slot_id'] for r in rows}) == 256
    assert sum(r['model'] == 'laya-v1' for r in rows) == 128
    for i in range(0, 256, 4):
        block = rows[i:i + 4]
        assert {r['base_pair_id'] for r in block} == {block[0]['base_pair_id']}
        assert [r['model'] for r in block][0] == block[1]['model'] != block[2]['model'] == block[3]['model']
    by_base = {}
    for r in rows:
        by_base.setdefault(r['base_slot_id'], []).append(r)
    for a, b2 in by_base.values():
        assert a['simulator_seed'] == b2['simulator_seed'] and a['teams'] == b2['teams']
    assert len({rows[i]['model'] for i in range(0, 256, 4)}) == 2


def test_paired_difference_and_verdict():
    rows = cmp.make_schedule(base())
    outs = [outcome(r, 'win' if r['model'] == 'laya-v2' else 'loss') for r in rows]
    s = cmp.summarize_compare(rows, outs, {})
    assert s['paired']['slots'] == 128 and s['paired']['mean_diff'] == 1.0 and s['paired']['new_better'] == 128
    assert cmp.verdict(s) == 'v2가 배틀 성적을 개선'
    same = cmp.summarize_compare(rows, [outcome(r, 'win') for r in rows], {})
    assert same['paired']['matchup_bootstrap_95'] == [0.0, 0.0] and cmp.verdict(same) == '구별되지 않음'


def test_replication_and_withhold():
    rows = cmp.make_schedule(base())
    ex120 = [dict(slot_id=r['base_slot_id'], status='completed', result='win', turns=30)
             for r in rows if r['model'] == 'laya-v1']
    outs = [outcome(r, 'win') for r in rows[:200]]
    s = cmp.summarize_compare(rows, outs, {}, ex120)
    assert s['v1_replication']['compared'] == sum(r['model'] == 'laya-v1' for r in rows[:200])
    assert s['v1_replication']['same_result_and_turns'] == s['v1_replication']['compared']
    assert cmp.verdict(s).startswith('판정 보류')


def test_ex125_study_schedule_and_verdict_text():
    rows = cmp.make_schedule(base(), cmp.EX125)
    assert {r['model'] for r in rows} == {'laya-v2', 'laya-v2t'}
    assert {r['slot_id'].split('-')[0] for r in rows} == {'v2', 'v2t'}
    outs = [outcome(r, 'win' if r['model'] == 'laya-v2t' else 'loss') for r in rows]
    s = cmp.summarize_compare(rows, outs, {}, None, cmp.EX125)
    assert s['paired']['mean_diff'] == 1.0 and s['v1_replication'] is None
    assert cmp.verdict(s, cmp.EX125) == 'v2+테라가 배틀 성적을 개선'


def test_ex127_study_schedule_and_verdict_text():
    rows = cmp.make_schedule(base(), cmp.EX127)
    assert {r['model'] for r in rows} == {'laya-v2t', 'laya-v2te'}
    assert {r['slot_id'].split('-')[0] for r in rows} == {'v2t', 'v2te'}
    assert cmp.EX127.gpu[0] == 2 and cmp.EX127.port == 8108
    outs = [outcome(r, 'win' if r['model'] == 'laya-v2te' else 'loss') for r in rows]
    s = cmp.summarize_compare(rows, outs, {}, None, cmp.EX127)
    assert cmp.verdict(s, cmp.EX127) == '효과 지식이 배틀 성적을 개선'


def test_ex133_study_schedule_and_verdict_text():
    rows = cmp.make_schedule(base(), cmp.EX133)
    assert {r['model'] for r in rows} == {'laya-v2t', 'laya-v2tw'}
    assert {r['slot_id'].split('-')[0] for r in rows} == {'v2t', 'v2tw'}
    assert cmp.EX133.gpu[0] == 0 and cmp.EX133.port == 8107 and cmp.RENDER['laya-v2tw'] == 'v2'
    outs = [outcome(r, 'win' if r['model'] == 'laya-v2tw' else 'loss') for r in rows]
    s = cmp.summarize_compare(rows, outs, {}, None, cmp.EX133)
    assert cmp.verdict(s, cmp.EX133) == '승패 가중이 배틀 성적을 개선'


def test_failed_moves_counts_model_side_only(tmp_path):
    import json
    protocol = '\n'.join(['|turn|3', '|move|p2a: Gliscor|Protect|p2a: Gliscor', '|-singleturn|p2a: Gliscor|Protect',
                          '|move|p1a: Ninetales|Aurora Veil||[still]', '|-fail|p1a: Ninetales',
                          '|move|p1a: Ninetales|Blizzard|p2a: Gliscor', '|-activate|p2a: Gliscor|move: Protect',
                          '|turn|4', '|move|p1a: Ninetales|Thunder Wave|p2a: Gliscor', '|-immune|p2a: Gliscor',
                          '|move|p2a: Gliscor|Earthquake|p1a: Ninetales', '|-fail|p2a: Gliscor',
                          '|move|p1a: Ninetales|Sleep Talk|p1a: Ninetales',
                          '|move|p1a: Ninetales|Blizzard|p2a: Gliscor|[from] move: Sleep Talk', '|-fail|p1a: Ninetales'])
    game = tmp_path / 'games' / 'v2te-m01-s1-a'
    game.mkdir(parents=True)
    (game / 'events.jsonl').write_text(json.dumps(dict(type='protocol', protocol=protocol)) + '\n')
    row = dict(slot_id='v2te-m01-s1-a', model='laya-v2te')
    out = cmp.failed_moves(tmp_path, [row], [dict(slot_id=row['slot_id'], model_side='p1')])['laya-v2te']
    assert (out['games'], out['moves'], out['failed']) == (1, 4, 2)
    assert out['aurora_veil'] == dict(used=1, failed=1)
    assert out['top_failed'] == [['Aurora Veil', 1, 1], ['Thunder Wave', 1, 1]]


def test_every_compared_model_can_be_served():
    from integration.laya_imitation import serving
    for study in (cmp.EX122, cmp.EX125, cmp.EX127, cmp.EX129, cmp.EX131, cmp.EX133):
        assert set(study.models) | {study.mock_model} <= set(serving.MODELS)
        assert set(study.models) | {study.mock_model} <= set(cmp.RENDER)
