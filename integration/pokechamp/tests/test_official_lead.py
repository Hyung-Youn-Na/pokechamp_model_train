"""EX-045 immutable official projections, audit boundaries and one-shot local gate."""
import copy
import json
from collections import Counter
from contextlib import ExitStack

import pytest

from integration.pokechamp import benchmark as b, distributed_lead as d
from integration.pokechamp import team_preview_study as study, team_preview_run as runner
from integration.pokechamp.diagnostics import corrected_lead as auditor
from integration.pokechamp.diagnostics.official_cutoff import raw_checks, recent_prefix, call_link
from integration.pokechamp.observation import OFFICIAL, selection
from integration.pokechamp.tests import test_distributed_lead as legacy


EXPERIMENT = 'EX-045'

def prepared(path):
    return path / 'prepared', study.prepare(path / 'prepared', experiment_id=EXPERIMENT)


def test_ex045_official_identity_and_exact_historical_sample(tmp_path):
    root, value = prepared(tmp_path)
    assert study.verify_prepared(root) == value
    assert value['schedule'] == d.schedule('EX-043') == d.schedule('EX-044')
    assert value['experiment_id'] == 'ex045-fake'
    assert value['execution_protocol']['input_audit'] == 'official-cutoff-v1'
    assert value['execution_protocol']['decision'] == 'D-067'
    assert Counter(r['provider_id'] for r in value['schedule']) == {'ollama': 16, 'zai': 16}
    assert value['delivery_prompt_identity']['version'] == 'b2-official-v1'
    assert value['observation_backend'] == OFFICIAL
    for provider in d.PROVIDERS:
        projected = d.selected(value, next(r for r in value['schedule'] if r['provider_id'] == provider))
        evidence = projected['execution']['evidence']
        assert evidence['observation_identity'] == value['observation_identity']
        assert evidence['battle_prompt_version'] == 'v1.4.0'
        assert evidence['team_preview_prompt_identity'] == value['team_preview_prompt_identity']
        assert projected['execution']['battle_concurrency'] == 4
    binding = study.binding_for(root, value)
    assert binding['observation_identity'] == value['observation_identity']
    assert binding['battle_prompt_identity']['version'] == 'v1.4.0'
    assert study.study_link(value).name == 'ex045-study-link.json'
    with pytest.raises(ValueError, match='requires official'):
        study.prepare(tmp_path / 'bad', experiment_id='EX-045', observation_backend='legacy-poke-env')
    value['provider_executions']['zai']['evidence']['observation_backend'] = 'legacy-poke-env'
    (root / 'plan.json').unlink()
    b.seal_json(root / 'plan.json', value)
    with pytest.raises(ValueError, match='provider drift'):
        study.verify_prepared(root)


@pytest.mark.parametrize('experiment', ['EX-042', 'EX-043', 'EX-044'])
def test_legacy_distributed_seals_unchanged(tmp_path, experiment):
    root = tmp_path / experiment
    value = study.prepare(root, experiment_id=experiment)
    assert 'observation_backend' not in value
    assert 'observation_backend' not in value['execution']['evidence']
    assert value['execution']['evidence']['battle_prompt_version'] == 'v1.3.0'
    assert value['delivery_prompt_identity']['version'] != 'b2-official-v1'
    assert study.verify_prepared(root) == value


@pytest.mark.parametrize('passed,local,expected', [(True,False,32),(False,False,4),(True,True,4)])
def test_official_audit_barrier_and_local_four_only(tmp_path, monkeypatch, passed, local, expected):
    root, value = prepared(tmp_path)
    first, _ = runner.staged_schedule(value['schedule'])
    inspected, dispatched, ports = set(), [], {}
    monkeypatch.setattr(study, 'verify_prepared', lambda _: value)
    monkeypatch.setattr(study, 'collection_deadline', lambda _: None)
    def worker(data, directory, value, slot, number, **kw):
        assert number == 1
        assert slot in first or len(inspected) >= 4
        assert ports.get(kw['port']) is None or ports[kw['port']] in inspected
        assert (kw['port'] < 8104) == (slot['provider_id'] == 'ollama')
        assert kw.get('hard_timeout_seconds') == (600 if local else None)
        ports[kw['port']] = slot['slot_id']
        dispatched.append(slot['slot_id'])
        return dict(slot=slot,slot_id=slot['slot_id'],attempt_id=slot['slot_id']+'-a1',eligible=True,category=None)
    def inspect(directory, attempt):
        inspected.add(attempt['slot_id'])
        return dict(passed=passed)
    monkeypatch.setattr(auditor, 'before_reuse', inspect)
    with ExitStack() as stack:
        brokers = d.Brokers(stack,tmp_path,value)
        runner.execute_schedule(root,tmp_path/'data',value,brokers,worker=worker,
                                gate_check=lambda *a:dict(passed=True),local_first_four=local)
    assert len(dispatched) == len(set(dispatched)) == expected


@pytest.mark.parametrize('name',[
    'test_unlimited_8001_deadline_halt_and_clock_reset',
    'test_time_expiry_prevents_both_provider_http',
    'test_first_failed_gate_game_stops_peer_requests_before_other_games_finish',
    'test_cloud_worker_verification_needs_only_assigned_key',
    'test_real_mock_http_4_plus_4_keys_retries_and_permit_release',
])
def test_ex045_common_boundaries(tmp_path,monkeypatch,name):
    monkeypatch.setattr(legacy,'prepare',prepared)
    monkeypatch.setattr(auditor,'before_reuse',lambda *a:dict(passed=True))
    reserve = study.reserve
    def official_reserve(root, actor, payload, **kw):
        payload = copy.deepcopy(payload)
        if payload.get('request', {}).get('identity'):
            payload['request'].update(selection(check_build=False))
        return reserve(root, actor, payload, **kw)
    monkeypatch.setattr(study, 'reserve', official_reserve)
    original = legacy.backend
    def backend(*args, **kw):
        result = original(*args, **kw)
        context = result._request_context
        result._request_context = lambda: dict(context(), **selection(check_build=False))
        return result
    monkeypatch.setattr(legacy,'backend',backend)
    getattr(legacy,name)(tmp_path,monkeypatch)


def test_official_raw_magic_bounce_and_item_holder(tmp_path):
    from integration.pokechamp.tests.test_official_observation import TEAM
    from integration.pokechamp.tests.test_observation_comparison import fixture
    from integration.pokechamp.observation.runtime import OfficialClient
    from integration.pokechamp.observation.normalize import normalize
    prefix, _ = fixture()
    prefix.append(dict(event_seq=2,protocol='|move|p2a: Hat|Toxic|p1a: Slowking|[from] ability: Magic Bounce\n|-damage|p1a: Slowking|100/393|[from] item: Rocky Helmet|[of] p2a: Hat'))
    with OfficialClient('p1') as client:
        state = client.snapshot(prefix,'fixture')
        value, _ = normalize(state,TEAM,prefix,prefix,battle_id='fixture',actor_id='p1',decision_seq=1,build_identity=client.identity)
        value['condition_id']='B'
        assert not raw_checks(value,prefix,'p1')['issues']
        bad=copy.deepcopy(value)
        bad['current_observation']['opponent_confirmed'][0]['moves'].append('toxic')
        assert any(r['check']=='opponent.moves' for r in raw_checks(bad,prefix,'p1')['issues'])


def test_recent_window_retains_original_row_offset():
    prefix=[dict(event_seq=1,protocol='|turn|1\n|move|p1a: A|Tackle|p2a: B\n|turn|2')]
    previous=[dict(protocol_event_seq=1,line_index=0)]*10
    recent=recent_prefix(prefix,previous)
    assert recent==[dict(event_seq=1,protocol='|move|p1a: A|Tackle|p2a: B\n|turn|2',line_offset=1)]
    assert prefix[0]['protocol'].startswith('|turn|1')


def test_cancel_before_reservation_is_not_missing_http(monkeypatch):
    from integration.pokechamp.diagnostics import official_cutoff as audit
    monkeypatch.setattr(audit,'original_for_call',lambda *a:{})
    call=dict(status='failure',event_seq=8,request=dict(http_attempts=[dict(network_called=False)]))
    assert call_link(call,{}, {})['state']=='cancelled_before_reservation'
    call['request']['http_attempts'][0]['network_called']=True
    with pytest.raises(ValueError,match='unexplained'):
        call_link(call,{}, {})


def test_official_registration_binds_build_and_prompt(tmp_path, monkeypatch):
    root, value = prepared(tmp_path)
    value = dict(value, transport='cloud', experiment_id='ex045-cloud', execution_authorized=False)
    value['execution'] = d.execution('EX-045','cloud',8)
    value['provider_executions'] = {p:d.execution('EX-045','cloud',4,p) for p in d.PROVIDERS}
    monkeypatch.setattr(study,'verify_prepared',lambda *a,**k:value)
    monkeypatch.setattr(d,'STUDY_LINK',tmp_path/'study-binding.json')
    approval=tmp_path/'approval.md'
    approval.write_text('Fixture only: no external requests.')
    reg=study.register_execution(root,approval_record=approval)
    assert reg['observation_identity']==value['observation_identity']
    assert reg['battle_prompt_identity']['version']=='v1.4.0'
    assert reg['delivery_prompt_identity']['version']=='b2-official-v1'
    assert reg['call_limit'] is None
    with pytest.raises(FileExistsError):
        study.register_execution(root,approval_record=approval)
