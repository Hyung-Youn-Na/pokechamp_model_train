"""Kev training-wire fidelity and fail-closed live decisions; no GPU or real Kev."""
import asyncio
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from types import SimpleNamespace
import urllib.error

import pytest

from integration.pokechamp import jev_battle as j, kev_player as p, kev_value as v
from integration.pokechamp.joint_q.serializer import JointInput, VERSION


@pytest.fixture
def joint():
    payload = dict(version=VERSION, instructions='Training instructions 그대로',
        state=dict(version=VERSION, turn=1, actor='p2'),
        actions=[dict(action_id='move_1', kind='move', name='Volt Switch'),
                 dict(action_id='move_1_terastallize', kind='move', name='Volt Switch'),
                 dict(action_id='switch_2', kind='switch', pokemon='Hydrapple'),
                 dict(action_id='team_3', kind='team', pokemon='Zamazenta')])
    return JointInput(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))


def response(joint, values=None):
    values = [.4255] * len(joint.action_ids) if values is None else values
    return dict(model='kev-latest', answers={key: dict(type='noul', noul=value)
                for key, value in zip(joint.action_ids, values)},
                usage=dict(input_tokens=10370, output_tokens=142), latency_ms=266.6)


def test_exact_training_questions_and_string_bytes(joint):
    body = v.request_payload(joint)
    assert list(body) == ['model', 'state', 'questions']
    assert body['model'] == 'kev-latest'
    assert type(body['state']) is str and body['state'].encode() == joint.payload_json.encode()
    assert list(body['questions']) == list(joint.action_ids)
    for key, description in zip(joint.action_ids, ['use Volt Switch', 'use Volt Switch and Terastallize',
                                                  'switch to Hydrapple', 'lead with Zamazenta']):
        assert body['questions'][key] == dict(type='noul', instructions=(
            f'Candidate {key} ({description}): if we choose it now and both sides then continue '
            'with the Abyssal policy, do we win the game?'))
    assert v.input_sha256(joint) == hashlib.sha256(joint.payload_json.encode()).hexdigest()
    assert json.loads(v.request_bytes(body)) == body
    assert v.validate_input(body).payload_json == joint.payload_json
    with pytest.raises(TypeError):
        v.request_payload(dict(model_input=joint.payload))


@pytest.mark.parametrize('mutation', ['object', 'criteria', 'reorder', 'missing', 'wording', 'teacher', 'system', 'nan_state'])
def test_input_drift_is_rejected(joint, mutation):
    body = v.request_payload(joint)
    key = joint.action_ids[0]
    if mutation == 'object':
        body['state'] = joint.payload
    elif mutation == 'criteria':
        body['questions'][key]['criteria'] = {'true': 'win'}
    elif mutation == 'reorder':
        body['questions'] = dict(reversed(list(body['questions'].items())))
    elif mutation == 'missing':
        del body['questions'][key]
    elif mutation == 'wording':
        body['questions'][key]['instructions'] += ' '
    elif mutation == 'teacher':
        payload = joint.payload
        payload['state']['original_choice'] = 'move_1'
        body['state'] = json.dumps(payload)
    elif mutation == 'system':
        body['system'] = 'Choose the best action.'
    else:
        payload = joint.payload
        payload['state']['turn'] = float('nan')
        body['state'] = json.dumps(payload)
    with pytest.raises(ValueError):
        v.validate_input(body)


def test_independent_probabilities_tie_order_and_singleton(joint):
    answer = response(joint)
    answer['answers'] = dict(reversed(list(answer['answers'].items())))
    assert sum(a['noul'] for a in answer['answers'].values()) != 1
    assert list(v.probabilities(answer, joint.action_ids)) == list(joint.action_ids)
    assert v.validate_response(answer, joint.action_ids) == 'move_1'
    answer['answers']['switch_2']['noul'] = 1
    assert v.validate_response(answer, joint.action_ids) == 'switch_2'
    assert v.validate_response(dict(answers={'move_1': dict(type='noul', noul=0)}), ['move_1']) == 'move_1'


@pytest.mark.parametrize('bad', [None, True, False, '0.7', [], {}, -.01, 1.01,
                                float('nan'), float('inf'), -float('inf'), 10 ** 400])
def test_noul_requires_finite_numeric_probability(joint, bad):
    answer = response(joint)
    answer['answers']['move_1']['noul'] = bad
    with pytest.raises(ValueError):
        v.validate_response(answer, joint.action_ids)


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'wrong_type', 'absent_type', 'not_object', 'no_answers'])
def test_complete_noul_answer_coverage(joint, mutation):
    answer = response(joint)
    if mutation == 'missing':
        del answer['answers']['move_1']
    elif mutation == 'extra':
        answer['answers']['move_9'] = dict(type='noul', noul=.9)
    elif mutation == 'wrong_type':
        answer['answers']['move_1']['type'] = 'choice'
    elif mutation == 'absent_type':
        del answer['answers']['move_1']['type']
    elif mutation == 'not_object':
        answer['answers']['move_1'] = .9
    else:
        del answer['answers']
    with pytest.raises(ValueError):
        v.validate_response(answer, joint.action_ids)


@pytest.fixture
def http_server():
    state = SimpleNamespace(status=200, raw=b'{}', headers={}, requests=[])

    class Handler(BaseHTTPRequestHandler):
        def reply(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            state.requests.append(dict(method=self.command, path=self.path, body=body,
                                       headers=dict(self.headers)))
            self.send_response(state.status)
            for key, value in state.headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(state.raw)

        do_POST = do_GET = reply

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.endpoint = f'http://127.0.0.1:{server.server_port}'
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_actual_wire_is_exact_and_never_uses_environment_proxy(joint, http_server, monkeypatch):
    for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
        monkeypatch.setenv(key, 'http://127.0.0.1:1')
    monkeypatch.setenv('NO_PROXY', '')
    monkeypatch.setenv('no_proxy', '')
    body = v.request_payload(joint)
    http_server.raw = json.dumps(response(joint)).encode()
    observed = []
    answer = v.request(body=body, endpoint=http_server.endpoint, api_key='test-private-key',
                       on_response=lambda status, raw: observed.append((status, raw)))
    assert v.validate_response(answer, joint.action_ids) == 'move_1'
    request = http_server.requests[0]
    assert request['method'] == 'POST' and request['path'] == '/v1/systemone'
    assert request['body'] == v.request_bytes(body)
    assert request['headers']['Authorization'] == 'Bearer test-private-key'
    assert observed == [(200, http_server.raw.decode())]
    http_server.raw = b'{"data":[]}'
    assert v.request('/v1/models', endpoint=http_server.endpoint) == {'data': []}
    assert http_server.requests[-1]['method'] == 'GET'


@pytest.mark.parametrize('endpoint', ['https://127.0.0.1:8019', 'http://8.8.8.8:8019',
    'http://localhost:8019', 'http://127.0.0.1:8019/path', 'http://127.0.0.1:8019?x=1',
    'http://127.0.0.1:8019#part', 'http://secret@127.0.0.1:8019', 'http://127.0.0.1:0',
    'http://127.0.0.1:8019\n', 'http://127.0.0.1:8019/', 'http://127.0.0.1'])
def test_endpoint_requires_explicit_numeric_loopback(endpoint):
    if endpoint.endswith('/'):
        assert v.base_url(endpoint) == endpoint[:-1]
    else:
        with pytest.raises(ValueError):
            v.base_url(endpoint)


@pytest.mark.parametrize('status', [302, 307, 401, 422, 500])
def test_http_errors_and_redirects_are_single_attempt(joint, http_server, status):
    http_server.status = status
    http_server.raw = b'rejected'
    http_server.headers = {'Location': 'http://outside.invalid/exfiltrate'}
    observed = []
    with pytest.raises(urllib.error.HTTPError) as exc:
        v.request(body=v.request_payload(joint), endpoint=http_server.endpoint,
                  on_response=lambda code, raw: observed.append((code, raw)))
    assert exc.value.code == status and observed == [(status, 'rejected')]
    assert len(http_server.requests) == 1


@pytest.mark.parametrize('raw', [b'not json', b'\xff', b'{"answers":NaN}', b'{"answers":1e999}',
                               b'{"answers":{},"answers":{}}'])
def test_raw_invalid_json_is_preserved(joint, http_server, raw):
    http_server.raw = raw
    observed = []
    with pytest.raises((ValueError, UnicodeError)):
        v.request(body=v.request_payload(joint), endpoint=http_server.endpoint,
                  on_response=lambda code, body: observed.append((code, body)))
    assert observed == [(200, raw.decode('utf-8', errors='replace'))]


@pytest.fixture
def session(tmp_path):
    value = p.Session(tmp_path)
    try:
        yield value
    finally:
        value.close()


def test_session_always_queries_singleton_and_logs_raw_response(session, joint, http_server):
    payload = joint.payload
    payload['actions'] = payload['actions'][:1]
    singleton = JointInput(json.dumps(payload))
    session.endpoint = http_server.endpoint
    http_server.raw = json.dumps(response(singleton, [.0])).encode()
    answer = asyncio.run(session.evaluate(v.request_payload(singleton), decision='single'))
    assert answer['answers']['move_1']['noul'] == 0
    assert session.calls == len(http_server.requests) == 1
    assert [e['type'] for e in session.records] == ['http_request', 'http_response', 'response']
    assert session.records[0]['body']['state'] == singleton.payload_json
    assert session.records[1]['raw_body'] == http_server.raw.decode()
    session.close()
    session.close()
    assert session.generator.closed


def test_api_key_is_redacted_even_if_server_echoes_it(tmp_path, joint, http_server):
    session = p.Session(tmp_path, environ={'KEV_API_KEY': 'secret-for-test'}, endpoint=http_server.endpoint)
    http_server.status = 401
    http_server.raw = b'bad bearer secret-for-test'
    try:
        with pytest.raises(RuntimeError, match='HTTP error 401'):
            asyncio.run(session.evaluate(v.request_payload(joint), decision='key'))
        assert 'secret-for-test' not in (tmp_path / 'events.jsonl').read_text()
        assert '[REDACTED]' in session.records[1]['raw_body']
    finally:
        session.close()


def test_expiry_preserves_late_reply_without_retry(session, joint, monkeypatch):
    calls = []
    session.timeout = .01

    def slow(*_args, on_response=None, **_kwargs):
        calls.append(1)
        time.sleep(.04)
        answer = response(joint)
        on_response(200, json.dumps(answer))
        return answer

    monkeypatch.setattr(v, 'request', slow)
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(session.evaluate(v.request_payload(joint), decision='late'))
    assert calls == [1]
    assert any(e['type'] == 'request_expired' for e in session.records)
    assert any(e['type'] == 'http_response' for e in session.records)
    assert not any(e['type'] in ('response', 'selection', 'wire') for e in session.records)


def test_bad_noul_session_raises_unusable_choice_with_original_response(session, joint, http_server):
    session.endpoint = http_server.endpoint
    answer = response(joint)
    del answer['answers']['move_1']
    http_server.raw = json.dumps(answer).encode()
    with pytest.raises(j.UnusableChoice):
        asyncio.run(session.evaluate(v.request_payload(joint), decision='missing'))
    assert session.records[1]['raw_body'] == http_server.raw.decode()
    assert session.records[-1]['type'] == 'response_rejected'
    assert session.calls == 1


def fixture_player(joint, tmp_path, monkeypatch, failure=None, profile=v.PROFILE):
    player = object.__new__(p.player_class())
    commands = {'move_1': '/choose move 1', 'move_1_terastallize': '/choose move 1 terastallize',
                'switch_2': '/choose switch 2', 'team_3': '/team 312456'}
    player.expected_actor = 'p2'
    player.request = dict(side=dict(id='p2'), rqid=1)
    player.latest_rqid = 1
    player.prefix, player.boundary, player.submitted_team = [], {'protocol_event_seq': 1, 'line_index': 0}, 'own'
    snapshot_calls = []

    def snapshot(*_args, **_kwargs):
        snapshot_calls.append(1)
        if len(snapshot_calls) > 1 and failure == 'snapshot':
            raise ValueError('official snapshot failed')
        if failure == 'withdrawn':
            return {'request': None}
        return dict(request=dict(rqid=2 if failure == 'official' else 1))

    player.official = SimpleNamespace(snapshot=snapshot, identity={})
    sent, records = [], []

    async def send(*args):
        sent.append(args)

    player.ps_client = SimpleNamespace(username='kevfixture', send_message=send)

    async def evaluate(body, **_kwargs):
        assert body == v.request_payload(joint, profile=profile)
        if failure == 'stale':
            player.latest_rqid = 2
        elif failure == 'cancelled':
            raise asyncio.CancelledError()
        elif failure == 'timeout':
            raise asyncio.TimeoutError()
        elif failure == 'http':
            raise RuntimeError('Kev serving HTTP error 422')
        elif failure == 'failed':
            player.session.failure_event.set()
        answer = response(joint)
        if failure == 'incomplete':
            del answer['answers']['move_1']
        return answer

    async def generate(*_args, **_kwargs):
        return joint, commands, {'audit': 'preserved'}

    player.session = SimpleNamespace(directory=tmp_path, records=records, dex={}, initial_pp_policy=None, profile=profile,
        failure_event=asyncio.Event(), evaluate=evaluate, generate=generate,
        timeout=0 if failure == 'expired' else 600, remaining=lambda: -1 if failure == 'budget' else 600,
        record=records.append)
    current = dict(commands)
    if failure == 'changed':
        current.pop('switch_2')
    monkeypatch.setattr(j, 'make_input', lambda *_a, **_k: ({}, current))
    return player, sent, records


@pytest.mark.parametrize('failure', ['stale', 'official', 'changed', 'timeout', 'expired', 'budget',
                                    'failed', 'incomplete', 'http', 'cancelled', 'snapshot', 'withdrawn'])
def test_invalid_or_late_decision_never_sends(joint, tmp_path, monkeypatch, failure):
    player, sent, records = fixture_player(joint, tmp_path, monkeypatch, failure)
    with pytest.raises((ValueError, RuntimeError, asyncio.TimeoutError, asyncio.CancelledError)):
        asyncio.run(player._handle_battle_request(SimpleNamespace(in_team_preview=False, battle_tag='fixture')))
    assert sent == []
    assert not any(e['type'] in ('selection', 'wire') for e in records)
    assert records[-1]['type'] == 'decision_rejected' and records[-1]['transmission'] == 'forbidden'
    if failure in ('stale', 'official', 'changed', 'expired', 'budget', 'failed', 'snapshot', 'withdrawn'):
        assert next(e for e in records if e['type'] == 'revalidation')['passed'] is False


@pytest.mark.parametrize('profile', [v.PROFILE, v.CONTINUATION_PROFILE])
def test_success_is_ordered_maximum_and_revalidates_before_wire(joint, tmp_path, monkeypatch, profile):
    player, sent, records = fixture_player(joint, tmp_path, monkeypatch, profile=profile)
    asyncio.run(player._handle_battle_request(SimpleNamespace(in_team_preview=False, battle_tag='fixture')))
    assert sent == [('/choose move 1', 'fixture', '1')]
    assert [e['type'] for e in records] == ['input', 'revalidation', 'selection', 'wire']
    assert records[0]['input_sha256'] == v.input_sha256(joint)
    assert records[0]['payload_json'] == joint.payload_json
    assert records[1]['passed'] is True
    assert records[1]['request_id'] == records[1]['latest_request_id'] == records[1]['current_request_id'] == 1
    assert records[2]['automatic'] is False and records[2]['choice'] == 'move_1'
    assert list(records[2]['probabilities']) == list(joint.action_ids)


def test_new_rqid_is_seen_before_queued_protocol_processing(monkeypatch):
    async def scenario():
        gate, processed = asyncio.Event(), []

        class Base:
            async def _handle_battle_message(self, messages):
                await gate.wait()
                processed.append(messages)

        monkeypatch.setattr(j, 'player_class', lambda: Base)
        player = p.player_class()()
        messages = [['', 'request', '{"rqid":2}']]
        task = asyncio.create_task(player._handle_battle_message(messages))
        await asyncio.sleep(0)
        assert player.latest_rqid == 2 and processed == []
        gate.set()
        await task
        assert processed == [messages]
        await player._handle_battle_message([['', 'request', '']])
        assert player.latest_rqid is None

    asyncio.run(scenario())


def test_automatic_default_has_no_transmission(joint, tmp_path, monkeypatch):
    player, sent, records = fixture_player(joint, tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='automatic default forbidden'):
        asyncio.run(player._handle_battle_request(SimpleNamespace(in_team_preview=False, battle_tag='fixture'),
                                                 maybe_default_order=True))
    assert sent == records == []


def test_generator_delegates_only_official_public_self_inputs_and_closes(monkeypatch):
    observed, closed = [], []
    engine = SimpleNamespace(close=lambda: closed.append(True))
    snapshot, roles = object(), object()
    monkeypatch.setattr(p, 'Engine', lambda: engine)
    monkeypatch.setattr(p, 'SetSnapshot', lambda: snapshot)
    monkeypatch.setattr(p, 'RoleDB', lambda: roles)

    def generate(*args, **kwargs):
        observed.append((args, kwargs))
        return 'joint', {'move_1': '/choose move 1'}, {}

    monkeypatch.setattr(p.serializer, 'generate', generate)
    generator = p.InputGenerator(dex={'dex': 'original'})
    official, prefix, own = {'request': {'side': {'id': 'p2'}}}, ['public-prefix'], 'own-team'
    assert generator.generate(official, prefix, own, actor='p2')[0] == 'joint'
    assert observed == [((official, prefix, own), dict(dex={'dex': 'original'}, engine=engine,
                                                     snapshot=snapshot, roles=roles))]
    with pytest.raises(ValueError, match='foreign actor'):
        generator.generate(official, prefix, own, actor='p1')
    generator.close()
    generator.close()
    assert closed == [True]
    with pytest.raises(RuntimeError, match='closed'):
        generator.generate(official, prefix, own, actor='p2')
