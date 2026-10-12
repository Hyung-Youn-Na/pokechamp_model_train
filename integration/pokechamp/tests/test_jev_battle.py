"""Native JEV projection, slots and failure boundaries."""
import asyncio
import json
import pytest
from integration.pokechamp.jev_battle import Session, make_input, recent_events, validate_answer
from integration.pokechamp.observation.build import DEFAULT_BUILD
from integration.pokechamp.observation.runtime import OfficialClient
from integration.pokechamp.tests.test_observation_comparison import fixture

@pytest.fixture
def sample():
    prefix, _ = fixture()
    client = OfficialClient('p1')
    try:
        official = client.snapshot(prefix, 'jev-test')
    finally:
        client.close()
    return official, prefix, json.loads((DEFAULT_BUILD / 'dex.json').read_text())

def test_projection_and_slots(sample):
    state, prefix, dex = sample
    payload, commands = make_input(state, prefix, actor='p1', dex=dex)
    assert commands == {'move_1':'/choose move 1','move_1_terastallize':'/choose move 1 terastallize','switch_2':'/choose switch 2'}
    mon = payload['state']['opponent_team'][0]
    assert mon['ability'] == mon['item'] == 'unknown'
    assert mon['hp']['current'] == 67
    assert payload['state']['self_team'][0]['condition'] == '123/393'
    state['sides'][1]['pokemon'][0]['ability']='Magic Bounce'
    payload,_=make_input(state,prefix,actor='p1',dex=dex)
    assert payload['state']['opponent_team'][0]['ability']=='unknown'
    prefix.append(dict(event_seq=2,protocol='|-ability|p2a: Hat|Magic Bounce'))
    state['consumed']+=1
    payload,_=make_input(state,prefix,actor='p1',dex=dex)
    assert payload['state']['opponent_team'][0]['ability']=='Magic Bounce'

def test_history():
    prefix=[dict(event_seq=1,protocol='|turn|1\n|faint|old\n|turn|2\n|-damage|public\n|request|secret\n|chat|secret\n|turn|3\n|move|public\n|turn|4\n|faint|public\n|turn|5\n|move|future')]
    result=recent_events(prefix,5)
    assert [e['turn'] for e in result]==[2,3,4]
    assert not any(word in json.dumps(result) for word in ('secret','future','old'))

def test_force_lead_wait_struggle_duplicate_slot(sample):
    state,prefix,dex=sample
    state['request']['forceSwitch']=[True]
    state['candidates']=[dict(wire='switch 2',action={'switch':'Slowking-Galar'})]
    state['request']['side']['pokemon'][1]['details']='Slowking-Galar, M'
    payload,commands=make_input(state,prefix,actor='p1',dex=dex)
    assert commands=={'switch_2':'/choose switch 2'}
    assert payload['state']['decision_kind']=='forced_switch'
    state['request'].pop('forceSwitch')
    state['request']['teamPreview']=True
    state['candidates']=[dict(wire='team 2',action={'team':2})]
    with pytest.raises(ValueError, match='initial team preview'):
        make_input(state,prefix,actor='p1',dex=dex)
    assert make_input(state,prefix,actor='p1',dex=dex,version='jev-choice-v1')[1]=={'team_2':'/team 21'}
    state['request'].pop('teamPreview')
    state['request']['active'][0]['moves']=[dict(id='struggle',move='Struggle')]
    state['candidates']=[dict(wire='move 1',action={'move':'struggle'})]
    payload,_=make_input(state,prefix,actor='p1',dex=dex)
    assert payload['questions']['action']['criteria']['move_1']['move']['id']=='struggle'
    state['request']['wait']=True
    assert make_input(state,prefix,actor='p1',dex=dex) is None

@pytest.mark.parametrize('bad',[{'probabilities':{'a':1}}, {'probabilities':{'a':float('nan'),'b':0}}, {'probabilities':{'a':1.1,'b':-.1}}, {'probabilities':{'a':float('inf'),'b':0}}, {'choice':'c'}, {'choice':'b'}, {'confidence':True}, {'confidence':2}])
def test_invalid_answer(bad):
    answer=dict(type='choice',choice='a',probabilities=dict(a=.7,b=.3),confidence=.4)
    answer.update(bad)
    with pytest.raises(ValueError):
        validate_answer(dict(answers=dict(action=answer)),{'a':{},'b':{}},version='choice-values-v2')

def test_actor_cutoff(sample):
    state,prefix,dex=sample
    with pytest.raises(ValueError,match='foreign'):
        make_input(state,prefix,actor='p2',dex=dex)
    state['consumed']+=1
    with pytest.raises(ValueError,match='cutoff'):
        make_input(state,prefix,actor='p1',dex=dex)

def test_transport_budget(sample,tmp_path):
    state,prefix,dex=sample
    payload,_=make_input(state,prefix,actor='p1',dex=dex)
    session=Session(tmp_path,fake=True)
    result=asyncio.run(session.evaluate(payload))
    validate_answer(result,payload['questions']['action']['criteria'])
    assert json.loads((tmp_path/'ledger.json').read_text())['requests']==1
    session.calls=300
    with pytest.raises(RuntimeError):
        asyncio.run(session.evaluate(payload))
    session.calls=1;session.monotonic_started=0
    with pytest.raises(RuntimeError):
        asyncio.run(session.evaluate(payload))

def test_legacy_native_http_failure_is_preserved_and_not_retried(tmp_path, sample, monkeypatch):
    import httpx
    from integration.pokechamp.jev import JevClient, JevRequestError
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, text='rate limit diagnostic')
    def factory(**kwargs):
        return JevClient(api_key='synthetic-key', transport=httpx.MockTransport(handler), retry_policy=kwargs['retry_policy'])
    monkeypatch.setattr(JevClient, 'from_env', factory)
    state, prefix, dex = sample
    payload, _ = make_input(state, prefix, actor='p1', dex=dex)
    session = Session(tmp_path, environ={}, retry_policy="jev-no-retry-v1")
    with pytest.raises(JevRequestError) as error:
        asyncio.run(session.evaluate(payload))
    assert error.value.status_code == 429
    assert len(calls) == session.calls == 1
    responses = [e for e in session.records if e['type'] == 'http_response']
    assert responses[0]['raw_body'] == 'rate limit diagnostic'


def test_native_raw_response_redacts_credentials(tmp_path, sample, monkeypatch):
    import httpx
    from integration.pokechamp.jev import JevClient, JevRequestError
    secret = 'synthetic-private-key'
    monkeypatch.setattr(JevClient, 'from_env', lambda **kw: JevClient(api_key=secret,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=secret))))
    state, prefix, dex = sample
    session = Session(tmp_path, environ={'TYPESAFE_API_KEY': secret})
    with pytest.raises(JevRequestError):
        asyncio.run(session.evaluate(make_input(state,prefix,actor='p1',dex=dex)[0]))
    assert secret not in (tmp_path/'events.jsonl').read_text()
    assert '[REDACTED]' in (tmp_path/'events.jsonl').read_text()


def test_official_process_does_not_inherit_provider_credentials(monkeypatch):
    from pathlib import Path
    for name in ('TYPESAFE_API_KEY','ZAI_API_KEY','OLLAMA_API_KEY'):
        monkeypatch.setenv(name, 'synthetic-private-value')
    with OfficialClient('p1') as client:
        child_env = (Path('/proc')/str(client.process.pid)/'environ').read_bytes()
        assert b'synthetic-private-value' not in child_env

def test_provider_await_does_not_reorder_frames():
    from integration.pokechamp.jev_battle import player_class
    cls = player_class()
    player = cls.__new__(cls)
    async def exercise():
        player.protocol_lock = asyncio.Lock()
        events = []
        async def process(value):
            events.append(('start',value))
            await asyncio.sleep(.01)
            events.append(('end',value))
        player._process_battle_message = process
        await asyncio.gather(player._handle_battle_message(1),player._handle_battle_message(2))
        assert events == [('start',1),('end',1),('start',2),('end',2)]
    asyncio.run(exercise())


def test_provider_timeout_is_one_attempt(tmp_path,sample,monkeypatch):
    import httpx
    from integration.pokechamp.jev import JevClient,JevRequestError
    calls=[]
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('synthetic timeout')
    monkeypatch.setattr(JevClient,'from_env',lambda **kw: JevClient(api_key='synthetic-key',transport=httpx.MockTransport(handler),retry_policy=kw['retry_policy']))
    state,prefix,dex=sample
    session=Session(tmp_path,environ={},retry_policy="jev-no-retry-v1")
    with pytest.raises(JevRequestError) as error:
        asyncio.run(session.evaluate(make_input(state,prefix,actor='p1',dex=dex)[0]))
    assert error.value.category=='timeout'
    assert len(calls)==session.calls==1


@pytest.mark.parametrize('probabilities', [dict(a=.50,b=.49), dict(a=.51,b=.50), dict(a=.8,b=.8)])
def test_probability_sum_is_not_a_gate(probabilities):
    import copy
    from integration.pokechamp.jev_battle import LEGACY_VALIDATION_VERSION
    body=dict(answers=dict(action=dict(type='choice',choice='a',probabilities=probabilities,confidence=.2)))
    original=copy.deepcopy(body)
    assert validate_answer(body,{'a':{},'b':{}})=='a'
    assert body==original
    with pytest.raises(ValueError):
        validate_answer(body,{'a':{},'b':{}},version=LEGACY_VALIDATION_VERSION)


def test_unknown_validation_version_fails():
    with pytest.raises(ValueError,match='unknown choice validation'):
        validate_answer({}, {}, version='unregistered')

def test_live_repeat_cannot_write_old_run(tmp_path):
    from integration.pokechamp.jev_battle import LIVE, LIVE_EXPERIMENT, run
    assert LIVE_EXPERIMENT == 'EX-051' and LIVE.name == 'ex051-live'
    with pytest.raises(ValueError,match='fixed'):
        asyncio.run(run(tmp_path/'ex047-live',fake=False))
    assert not (tmp_path/'ex047-live').exists()


@pytest.mark.parametrize('auxiliary', [
    {}, {'probabilities': {'a': .24, 'b': .25}, 'confidence': .4},
    {'probabilities': {'a': 2, 'foreign': -1}, 'confidence': True},
    {'probabilities': None, 'confidence': 'uncertain'},
])
def test_legal_choice_survives_auxiliary_errors(auxiliary):
    import copy
    from integration.pokechamp.jev_battle import judgment_diagnostics
    answer = dict(type='choice', choice='a', **auxiliary)
    body = dict(answers=dict(action=answer))
    before = copy.deepcopy(body)
    assert validate_answer(body, {'a': {}, 'b': {}}) == 'a'
    assert judgment_diagnostics(answer, {'a': {}, 'b': {}})
    assert body == before


@pytest.mark.parametrize('body', [{}, {'answers': []}, {'answers': {'action': None}},
    {'answers': {'action': {'type': 'choice', 'choice': ['a']}}},
    {'answers': {'action': {'type': 'choice', 'choice': 'foreign'}}}])
def test_unusable_choice_has_match_scope(body):
    from integration.pokechamp.jev_battle import UnusableChoice
    with pytest.raises(UnusableChoice):
        validate_answer(body, {'a': {}})


def test_v2_argmax_is_preserved_for_historical_audits():
    body = dict(answers=dict(action=dict(type='choice', choice='a',
        probabilities=dict(a=.24, b=.25), confidence=.5)))
    with pytest.raises(ValueError, match='maximum'):
        validate_answer(body, {'a': {}, 'b': {}}, version='choice-values-v2')
    assert validate_answer(body, {'a': {}, 'b': {}}) == 'a'
