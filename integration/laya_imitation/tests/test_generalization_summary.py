"""EX-120 summaries: matchup-cluster interval, team/seed/pair breakdowns, denominators and the frozen verdict."""
from integration.laya_imitation import teams as t
from integration.laya_imitation.generalization import summarize_generalization, verdict
from integration.laya_imitation.tests.test_teams import checker, pool


def schedule():
    chosen, _, _ = t.select(pool(), checker())
    return t.make_schedule(chosen)


def outcome(row, result='win', status='completed'):
    return dict(slot_id=row['slot_id'], status=status, result=result if status == 'completed' else None, turns=30)


def test_all_wins_and_denominators():
    rows = schedule()
    s = summarize_generalization(rows, [outcome(r) for r in rows])
    assert s['mean_score'] == 1.0 and s['matchup_bootstrap_95'] == [1.0, 1.0]
    assert s['completed_matchups'] == 32 and s['swapped_pairs']['both_won'] == 64
    assert all(v['as_model_n'] == 4 and v['as_opponent_n'] == 4 for v in s['teams'].values())
    assert verdict(s)['primary'] == '새 팀에서도 Abyssal보다 우세'


def test_team_advantage_pattern_and_unfinished_slots():
    rows = schedule()
    outs = [outcome(r, 'win' if r['swap'] == 'a' else 'loss') for r in rows[:-4]]
    outs.append(outcome(rows[-4], status='failed'))
    s = summarize_generalization(rows, outs)
    assert s['status'] == dict(completed=124, failed=1, incomplete=0, invalid=0, unattempted=3)
    assert s['swapped_pairs']['split'] == 62
    low, high = s['matchup_bootstrap_95']
    assert 0 <= low <= s['mean_score'] <= high <= 1
    assert s['seeds']['1']['n'] + s['seeds']['2']['n'] == 124


def test_verdict_withholds_below_120_normal_games():
    rows = schedule()
    s = summarize_generalization(rows, [outcome(r) for r in rows[:100]])
    assert verdict(s)['primary'].startswith('판정 보류')


def test_verdict_failure_and_ex119_comparison():
    rows = schedule()
    s = summarize_generalization(rows, [outcome(r, 'loss' if i % 3 else 'win') for i, r in enumerate(rows)])
    v = verdict(s)
    assert v['primary'] == '우세 유지 실패' and v['ex119'] == 'EX-089 4팀 결과는 일반 수준보다 높았다'
