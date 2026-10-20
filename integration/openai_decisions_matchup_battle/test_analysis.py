"""새 실측을 보지 않고 고정한 분모·분리 지표·cutoff·사용량 검사."""
import json

import pytest

from integration.candidate_matchup.tests.test_summary import payload
from integration.candidate_matchup.rules import metadata
from integration.candidate_matchup.summary import decorate
from .analysis import classify, review_case, usage_metrics, score, difference


@pytest.fixture(scope='module')
def rules():
    return metadata()


def select(choice='move_1', automatic=False):
    return dict(choice=choice, automatic=automatic)


def test_primary_uses_model_choice_and_available_alternative(rules):
    p = payload(rules)
    p['questions']['action']['criteria']['switch_2'] = dict(kind='switch', slot=2)
    r = classify(p, select())
    assert r['primary_eligible'] and r['selected']['blocked']
    assert r['selected']['type_zero'] and not r['all_blocked']
    r = classify(p, select('switch_2'))
    assert r['primary_eligible'] and not r['selected']['blocked']
    assert classify(p, None)['primary_eligible'] is False


def test_automatic_and_all_blocked_excluded(rules):
    p = payload(rules)
    r = classify(p, select(automatic=True))
    assert r['automatic'] and r['all_blocked'] and not r['primary_eligible']
    c = p['questions']['action']['criteria']
    c['move_1_tera'] = dict(c['move_1'], terastallize=True)
    r = classify(p, select())
    assert r['all_blocked'] and not r['primary_eligible']


def test_overlay_is_removed_before_same_frozen_classification(rules):
    p = payload(rules)
    enriched = decorate(p)
    enriched['questions']['action']['criteria']['move_1']['current_matchup']['public_effects']['result'] = 'no_known_blocker'
    assert classify(p, select()) == classify(enriched, select())


def test_unknown_not_blocked_and_secondary_not_whole_move(rules):
    p = payload(rules)
    p['state']['opponent_team'][0]['item'] = {'knowledge': 'unknown'}
    r = classify(p, select())
    assert r['unknown_present'] and not r['selected']['blocked']
    p = payload(rules, 'nuzzle', ('Electric',))
    r = classify(p, select())
    assert r['selected']['secondary_status_blocked'] or r['selected']['primary_status_blocked']
    assert not r['selected']['blocked']


def test_reflection_separate_and_primary_status_separate(rules):
    p = payload(rules, 'willowisp', ('Normal',), ability='magicbounce')
    r = classify(p, select())
    assert r['selected']['reflected'] and not r['selected']['blocked']
    p = payload(rules, 'willowisp', ('Fire',))
    r = classify(p, select())
    assert r['selected']['primary_status_blocked'] and not r['selected']['blocked']


def test_review_uses_cutoff_and_before_selected_action_only():
    lines = ['|move|p1a: Mew|Earth Power|p2a: Old', '|switch|p2a: New|New|100/100',
             '|-terastallize|p2a: New|Flying', '|-status|p1a: Mew|brn',
             '|move|p1a: Mew|Earth Power|p2a: New', '|-immune|p2a: New',
             '|turn|3', '|switch|p2a: Later|Later|100/100']
    rows = [dict(sequence=10, line_index=i, protocol=line) for i, line in enumerate(lines)]
    entry = dict(boundary=dict(protocol_event_seq=10, line_index=0), actor='p1')
    r = review_case(entry, dict(move='Earth Power'), rows)
    assert len(r['opponent_switches']) == len(r['opponent_tera']) == len(r['preceding_state_changes']) == 1
    assert r['actual_result_markers'] == {'-immune': 1}
    assert len(r['public_window']) == 5 and r['selected_move_observed']


def test_usage_counts_physical_retries_and_unknown_cost():
    events = [dict(type='transport', decision='a', request_number=1, attempt=1),
              dict(type='attempt_failure', request_number=1, elapsed_seconds=60),
              dict(type='provider_retry', delay_seconds=2),
              dict(type='transport', decision='a', request_number=2, attempt=2),
              dict(type='http_response', request_number=2, elapsed_seconds=.5,
                   raw_body=json.dumps(dict(usage=dict(input_tokens=20, output_tokens=0)))),
              dict(type='response', elapsed_seconds=62.5)]
    r = usage_metrics(events)
    assert (r['logical_requests'], r['http_attempts'], r['retries'], r['usage_unknown_attempts']) == (1, 2, 1, 1)
    assert r['confirmed_tokens']['input_tokens'] == 20 and r['retry_wait_seconds'] == 2
    assert r['http_latency_seconds']['p95'] == 60


def test_score_requires_completed_audited_result():
    for name, expected in [('player_won', 1), ('player_lost', 0), ('tied', .5)]:
        r = dict(completed=True, audit_passed=True, outcome=name)
        assert score(r) == expected
        assert score(dict(r, audit_passed=False)) is None
    assert score(None) is None and difference(None, 1) is None
