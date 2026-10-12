"""EX-046 isolated registration and inherited official safety boundaries."""
import pytest
from integration.pokechamp import team_preview_study as study, distributed_lead as d
from integration.pokechamp.tests import test_official_lead as old


def test_new_identity_preserves_conditions_and_old_protocol(tmp_path):
    root = tmp_path / 'new'
    value = study.prepare(root, experiment_id='EX-046')
    prior = study.prepare(tmp_path / 'old', experiment_id='EX-045')
    assert study.verify_prepared(root) == value
    assert value['experiment_id'] == 'ex046-fake'
    assert study.study_link(value).name == 'ex046-study-link.json'
    assert study.binding_for(root,value)['experiment'] == 'EX-046'
    assert study.binding_for(root,value)['observation_identity'] == prior['observation_identity']
    assert d.protocol('EX-045')['decision'] == 'D-067'
    assert d.protocol('EX-046') == dict(d.protocol('EX-045'),experiment='EX-046',decision='D-069')
    for key in ('schedule','teams','provider_configs','provider_executions','models','execution','observation_identity','delivery_prompt_identity','team_preview_prompt_identity'):
        assert value[key] == prior[key], key
    with pytest.raises(ValueError,match='requires official'):
        study.prepare(tmp_path/'legacy',experiment_id='EX-046',observation_backend='legacy-poke-env')
    with pytest.raises(ValueError,match='local identity'):
        d.prepare(tmp_path/'bypass',experiment_id='EX-046',transport='cloud',concurrency=8,local_identity='ep058-local-eight')


@pytest.mark.parametrize('passed,expected',[(True,32),(False,4)])
def test_gate_and_audit_before_slot_reuse(tmp_path,monkeypatch,passed,expected):
    monkeypatch.setattr(old,'EXPERIMENT','EX-046')
    old.test_official_audit_barrier_and_local_four_only(tmp_path,monkeypatch,passed,False,expected)


@pytest.mark.parametrize('name',[
    'test_unlimited_8001_deadline_halt_and_clock_reset',
    'test_time_expiry_prevents_both_provider_http',
    'test_first_failed_gate_game_stops_peer_requests_before_other_games_finish',
    'test_cloud_worker_verification_needs_only_assigned_key',
    'test_real_mock_http_4_plus_4_keys_retries_and_permit_release',
])
def test_ex046_boundaries(tmp_path,monkeypatch,name):
    monkeypatch.setattr(old,'EXPERIMENT','EX-046')
    old.test_ex045_common_boundaries(tmp_path,monkeypatch,name)
