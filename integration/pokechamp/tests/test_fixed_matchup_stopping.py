"""EX-079 stopping boundaries and frozen evaluation isolation (CPU only)."""
from copy import deepcopy
import json

import pytest

from integration.pokechamp.fixed_matchup.stopping import PROTOCOL, schedule, stopping_decision
from integration.pokechamp.fixed_matchup.schedule import test_schedule as previous_test_schedule


def history(*scores):
    return [dict(round=r, score=s, file=f'models/round-{r:03d}.pt', sha256=f'hash-{r}')
            for r, s in zip([1, *range(4, 33, 4)], scores)]


def test_empty_and_baseline_do_not_count_as_target_or_stale():
    assert not stopping_decision([])['stop']
    state = stopping_decision(history(.8))
    assert (state['anchor'], state['best_round'], state['stale'], state['target_streak']) == (.8, 1, 0, 0)
    assert not state['stop']


def test_plateau_waits_until_round12_and_keeps_earliest_best():
    assert not stopping_decision(history(.5, .5, .5))['stop']
    state = stopping_decision(history(.5, .5, .5, .5))
    assert (state['round'], state['reason'], state['stale'], state['best_round']) == (12, 'plateau', 3, 1)


def test_target_requires_three_postbaseline_evaluations_and_has_priority():
    assert not stopping_decision(history(.65, .65, .65))['stop']
    state = stopping_decision(history(.65, .65, .65, .65))
    assert state['target_streak'] == 3
    assert state['reason'] == 'target'
    assert state['reasons'] == ['target', 'plateau']


def test_target_streak_resets_below_threshold():
    state = stopping_decision(history(.55, .65, .64, .65))
    assert state['target_streak'] == 1
    assert not state['stop']
    state = stopping_decision(history(.55, .65, .64, .65, .66))
    assert state['target_streak'] == 2
    assert state['reason'] == 'plateau'


@pytest.mark.parametrize('baseline,score', [(.1, .12), (.55, .57), (.5, .52)])
def test_exact_two_percentage_point_improvement_resets_stale(baseline, score):
    state = stopping_decision(history(baseline, baseline, score))
    assert state['stale'] == 0
    assert state['anchor'] == score


def test_small_gains_accumulate_against_anchor_while_actual_best_advances():
    state = stopping_decision(history(.5, .51, .519))
    assert state['anchor'] == .5 and state['stale'] == 2
    assert state['best_round'] == 8 and state['best_score'] == .519
    state = stopping_decision(history(.5, .51, .519, .52))
    assert state['anchor'] == .52 and state['stale'] == 0
    assert not state['stop']


def test_best_can_be_below_improvement_threshold_and_ties_keep_first():
    state = stopping_decision(history(.5, .519, .519, .518))
    assert state['reason'] == 'plateau'
    assert state['best_round'] == 4 and state['best_score'] == .519
    assert state['anchor'] == .5


def test_max_round32_is_enforced_even_during_continued_improvement():
    rows = history(.1, .12, .14, .16, .18, .20, .22, .24, .26)
    assert all(not stopping_decision(rows[:i])['stop'] for i in range(1, len(rows)))
    state = stopping_decision(rows)
    assert state['reason'] == 'max_rounds' and state['reasons'] == ['max_rounds']


def test_all_three_stop_reasons_are_preserved_in_priority_order():
    state = stopping_decision(history(.1, .2, .3, .4, .5, .64, .65, .65, .65))
    assert state['round'] == 32 and state['reason'] == 'target'
    assert state['reasons'] == ['target', 'plateau', 'max_rounds']


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), -.1, 1.1, True, '0.5', None])
def test_invalid_scores_cannot_be_used_for_selection(value):
    with pytest.raises(ValueError):
        stopping_decision(history(.5, value))


@pytest.mark.parametrize('fault', ['missing_round', 'duplicate', 'out_of_order', 'noninteger', 'missing_field', 'post_stop'])
def test_noncontiguous_or_poststop_history_rejected(fault):
    rows = history(.1, .2, .3, .4)
    if fault == 'missing_round':
        rows.pop(1)
    elif fault == 'duplicate':
        rows[2]['round'] = 4
    elif fault == 'out_of_order':
        rows[1], rows[2] = rows[2], rows[1]
    elif fault == 'noninteger':
        rows[0]['round'] = True
    elif fault == 'missing_field':
        del rows[1]['sha256']
    else:
        rows = history(.5, .5, .5, .5, .6)
    with pytest.raises(ValueError):
        stopping_decision(rows)


def test_restart_reconstructs_state_without_mutating_history():
    rows = history(.5, .51, .519, .52, .53, .531, .535)
    before = deepcopy(rows)
    for length in range(len(rows) + 1):
        prefix = rows[:length]
        assert stopping_decision(prefix) == stopping_decision(json.loads(json.dumps(prefix)))
    assert rows == before


def test_schedule_budget_and_orientation_balance():
    frozen = schedule()
    assert frozen == schedule()
    assert frozen['pilot'] == []
    assert len(frozen['train']) == 32 and all(len(jobs) == 32 for jobs in frozen['train'])
    assert list(frozen['dev']) == ['1', '4', '8', '12', '16', '20', '24', '28', '32']
    assert all(len(jobs) == 64 for jobs in frozen['dev'].values())
    assert len(frozen['test']) == 640
    assert sum(map(len, frozen['train'][1:])) + sum(map(len, frozen['dev'].values())) + len(frozen['test']) == 2208
    for jobs in frozen['dev'].values():
        assert {(r['block'], r['model_team'], r['model_side']) for r in jobs} == {
            (b, t, p) for b in range(16) for t in ('A', 'B') for p in ('p1', 'p2')}
        assert all(r['players'][r['model_side']] == {'model': 'current', 'mode': 'policy'} for r in jobs)
    assert PROTOCOL['total_seconds'] is PROTOCOL['game_seconds'] is None
    assert all(value is None for value in PROTOCOL['stage_seconds'].values())
    assert PROTOCOL['retries'] == PROTOCOL['replacements'] == 0


def test_dev_common_random_numbers_and_unique_slots_are_disjoint_from_test_training():
    frozen = schedule()
    baseline = frozen['dev']['1']
    for jobs in frozen['dev'].values():
        assert [r['seed_key'] for r in jobs] == [r['seed_key'] for r in baseline]
        assert [r['simulator_seed'] for r in jobs] == [r['simulator_seed'] for r in baseline]
    train = sum(frozen['train'], [])
    dev = sum(frozen['dev'].values(), [])
    test = frozen['test']
    groups = [train, dev, test, previous_test_schedule()]
    namespaces = [{json.dumps(r['seed_key']) for r in group} for group in groups]
    for index, left in enumerate(namespaces):
        for right in namespaces[index + 1:]:
            assert left.isdisjoint(right)
    slots = [r['slot_id'] for r in train + dev + test]
    assert len(slots) == len(set(slots))
