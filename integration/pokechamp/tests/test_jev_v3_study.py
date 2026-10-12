import asyncio
import copy
import json
import pytest
from integration.pokechamp import jev_study as s, jev_battle as j
from integration.pokechamp.jev_comparison import compare_data


def test_v3_direct_baseline():
    baseline = s.baseline_manifest()
    rows, teams, origin = s.study_schedule('EX-053')
    assert rows == baseline['schedule'] and teams == baseline['teams']
    assert origin['experiment'] == 'EX-052'
    assert len(rows) == 32 and len({r['paired_slot_id'] for r in rows}) == 16
    assert s.experiment_settings('EX-052')[3] == 'jev-choice-v2'
    assert s.experiment_settings('EX-053')[3] == 'jev-choice-v3'


def test_v3_old_receipt_rejected(tmp_path, monkeypatch):
    rows, teams, origin = s.study_schedule('EX-053')
    config = dict(model='test', endpoint='https://invalid.example/systemone')
    receipt = tmp_path / 'receipt.json'
    receipt.write_text(json.dumps(dict(passed=True, source=j.source_identity(), schedule_sha256=j.digest(rows), model=config)))
    out = tmp_path / 'fresh'
    monkeypatch.setattr(s, 'experiment_settings', lambda _: (out, receipt, 'EP-075', 'jev-choice-v3'))
    monkeypatch.setattr(s, 'configuration', lambda _: (config, {}))
    with pytest.raises(ValueError, match='identity verification'):
        asyncio.run(s.run(out, experiment='EX-053'))
    assert not out.exists()


def test_v3_refuses_old_output(tmp_path):
    with pytest.raises(ValueError, match='fixed'):
        asyncio.run(s.run(s.LIVE, experiment='EX-053'))


@pytest.mark.parametrize('field', ['experiment_id', 'prompt_sha256', 'effect_reference_identity', 'source', 'observation_build', 'teams_sha256', 'schedule_sha256', 'model', 'limits'])
def test_receipt_binds_treatment_and_runtime(field, tmp_path, monkeypatch):
    rows, teams, origin = s.study_schedule('EX-053')
    config = dict(model='test', endpoint='https://invalid.example/systemone')
    source = j.source_identity()
    identity = s.v3_identity(rows, teams, origin, config, source)
    identity[field] = None
    receipt = tmp_path / 'receipt.json'
    receipt.write_text(json.dumps(dict(passed=True, source=source, schedule_sha256=j.digest(rows),
                                       model=config, identity=identity)))
    out = tmp_path / 'fresh'
    monkeypatch.setattr(s, 'experiment_settings', lambda _: (out, receipt, 'EP-075', 'jev-choice-v3'))
    monkeypatch.setattr(s, 'configuration', lambda _: (config, {}))
    with pytest.raises(ValueError, match='identity verification'):
        asyncio.run(s.run(out, experiment='EX-053'))
    assert not out.exists()


def test_common_pairs_exclude_failed_and_missing_without_imputing_losses():
    rows, teams, _ = s.study_schedule('EX-053')
    pair_ids = list(dict.fromkeys(r["paired_slot_id"] for r in rows))[:2]
    rows = [r for r in rows if r["paired_slot_id"] in pair_ids]
    bm = dict(experiment_id='EX-052', schema_version='jev-choice-v2', schedule=rows, teams=teams, model={})
    nm = dict(bm, experiment_id='EX-053', schema_version='jev-choice-v3')
    old = [dict(r, username='old'+str(i), completed=True, audit_passed=True, outcome='player_lost', turns=10, requests=0) for i,r in enumerate(rows)]
    new = [dict(o, outcome='player_won') for o in old]
    # Select complete pairs by identity; submission order interleaves blocks.
    pair = rows[0]['paired_slot_id']
    new = [dict(o, completed=(o['paired_slot_id']==pair), outcome='player_won' if o['paired_slot_id']==pair else 'output_failure') for o in new]
    result = compare_data((bm,dict(outcomes=old,actual_models=['v2']),[]), (nm,dict(outcomes=new,actual_models=['v3']),[]))
    expected = sum(r['paired_slot_id']==pair for r in rows)
    assert expected == 2
    assert result['common_completed_pairs'] == 1
    assert result['mean_pair_score_delta'] == 1.
    assert result['comparable_games'] == expected
    assert all(r['delta_v3_minus_v2']['score'] is None for r in result['matches'] if not r['comparable'])
    assert result['model_changed']
