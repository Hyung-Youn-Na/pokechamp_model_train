"""EX-052 schedule provenance, cumulative admission, isolation and denominators."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from integration.pokechamp import jev_battle as j
from integration.pokechamp import jev_study as s
from integration.pokechamp.tests.test_jev_battle import sample


def test_schedule_matches_sealed_ex046():
    rows, teams, origin = s.origin_schedule()
    original = json.loads(s.ORIGIN.read_text())
    for new, old in zip(rows, original['schedule']):
        for key in ('slot_id', 'paired_slot_id', 'teams', 'battle_seed', 'actor_seeds', 'submission_order'):
            assert new[key] == old[key]
        index = next(i for i, a in enumerate(old['actor_settings']) if a['team_preview_policy'] == 'llm_lead')
        assert new['jev_actor'] == f'p{index + 1}'
    assert len(rows) == 32
    assert sum(r['jev_actor'] == 'p1' for r in rows) == 16
    assert len([r for r in rows if r['repetition'] == 1]) == 8
    assert origin['experiment'] == 'EX-046'
    assert set(teams) == {'1', '2', '6', '12'}


@pytest.mark.parametrize('mutation', ['team', 'pair_seed', 'order', 'duplicate', 'actor'])
def test_bad_schedule_rejected(mutation):
    rows, _, _ = s.origin_schedule()
    if mutation == 'team': rows[0]['teams'] = ['1', '6']
    if mutation == 'pair_seed': rows[0]['actor_seeds'][0] += 1
    if mutation == 'order': rows.reverse()
    if mutation == 'duplicate': rows[1] = copy.deepcopy(rows[0])
    if mutation == 'actor': rows[0]['jev_actor'] = 'p2' if rows[0]['jev_actor'] == 'p1' else 'p1'
    with pytest.raises(ValueError): s.validate_schedule(rows)


def test_unlimited_is_not_a_large_numeric_cap(tmp_path, sample, monkeypatch):
    state, prefix, dex = sample
    session = s.StudySession(tmp_path, fake=True)
    payload, _ = j.make_input(state, prefix, actor='p1', dex=dex)
    session.calls = 100000
    asyncio.run(session.evaluate(payload, decision='first'))
    first = session.started
    clock = session.monotonic_started
    asyncio.run(session.evaluate(payload, decision='second'))
    ledger = json.loads((tmp_path / 'ledger.json').read_text())
    assert session.calls == 100002 and ledger['limit'] is None
    assert session.started == first and session.monotonic_started == clock
    assert ledger['deadline'] == first + 20100
    monkeypatch.setattr(j.time, 'monotonic', lambda: clock + 20100)
    with pytest.raises(RuntimeError): asyncio.run(session.evaluate(payload))
    assert session.calls == 100002


def test_failed_match_is_not_a_loss_or_completed_pair():
    rows, _, _ = s.origin_schedule()
    pair = next(r['paired_slot_id'] for r in rows)
    selected = [r for r in rows if r['paired_slot_id'] == pair]
    fake = SimpleNamespace(records=[], calls=0, fake=True, started=None)
    outcomes = [dict(selected[0], completed=True, audit_passed=True, outcome='player_won'),
                dict(selected[1], completed=False, audit_passed=True, outcome='output_failure')]
    result = s.summarize(fake, outcomes, selected)
    assert result['completed'] == 1 and result['failed'] == 1
    assert result['actual_wins'] == 1 and result['actual_losses'] == 0
    assert result['completed_pairs'] == 0 and result['mean_pair_score'] is None
    assert not result['passed']
    outcomes[1].update(completed=True, outcome='tied')
    result = s.summarize(fake, outcomes, selected)
    assert result['mean_pair_score'] == .75


def test_missing_usage_is_not_claimed_as_known_zero():
    fake = SimpleNamespace(records=[dict(type='response', body=dict(model='test'), elapsed_seconds=1)],
                           calls=1, fake=True, started=None)
    result = s.summarize(fake, [], [])
    assert result['missing_usage_responses'] == 1


def test_wrong_live_path_rejected_before_mutation(tmp_path):
    with pytest.raises(ValueError, match='fixed'):
        asyncio.run(s.run(tmp_path / 'wrong'))
    assert not (tmp_path / 'wrong').exists()


def test_source_receipt_does_not_allow_reexecution(tmp_path, monkeypatch):
    rows, _, _ = s.origin_schedule()
    config = dict(model='test', endpoint='https://invalid.example/systemone')
    receipt = tmp_path / 'receipt.json'
    receipt.write_text(json.dumps(dict(passed=True, source=j.source_identity(), schedule_sha256=j.digest(rows), model=config)))
    directory = tmp_path / 'existing'
    directory.mkdir()
    sentinel = directory / 'sentinel'
    sentinel.write_text('preserve')
    monkeypatch.setattr(s, 'LIVE', directory)
    monkeypatch.setattr(s, 'RECEIPT', receipt)
    monkeypatch.setattr(s, 'configuration', lambda: (config, {}))
    with pytest.raises(FileExistsError): asyncio.run(s.run(directory))
    assert sentinel.read_text() == 'preserve'
