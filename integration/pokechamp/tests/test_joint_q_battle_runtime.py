"""EX081 CPU transport, live send boundary and owned one-attempt orchestration."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import urllib.error

import pytest

from integration.pokechamp import jev_battle as j
from integration.pokechamp.joint_q.battle_eval import battle as b, client, player as p, protocol
from integration.pokechamp.joint_q.serializer import JointInput, VERSION


@pytest.fixture
def joint():
    return JointInput(json.dumps(dict(version=VERSION, instructions='원 입력 보존',
        state=dict(version=VERSION, actor='p2', turn=1), actions=[
            dict(action_id='move_1', kind='move', name='Volt Switch'),
            dict(action_id='move_1_terastallize', kind='move', name='Volt Switch'),
            dict(action_id='switch_2', kind='switch', pokemon='Hydrapple'),
            dict(action_id='team_3', kind='team', pokemon='Zamazenta')]), ensure_ascii=False))


@pytest.fixture
def identity():
    return dict(profile=protocol.PROFILE, model='Qwen/Qwen3.5-4B-Base', revision='base-revision',
        checkpoint_sha256='c' * 64, head_sha256='h' * 64, server_pid=1234,
        server_started_at=1.0, source_sha256='s' * 64, physical_gpu=0, gpu_uuid='GPU-0', ready=True)


def answer(joint, identity, values=None):
    q = dict(zip(joint.action_ids, [.5] * len(joint.action_ids) if values is None else values))
    return dict(identity, input_sha256=protocol.input_sha256(joint), q_values=q,
        choice=max(q, key=q.get), prompt_sha256='p' * 64, token_sha256='t' * 64,
        tokens=1000, readout_positions=list(range(900, 900 + len(q))), elapsed_seconds=.001, gpu_seconds=.001)


@pytest.fixture
def http_server():
    state = SimpleNamespace(status=200, raw=b'{}', headers={}, requests=[])

    class Handler(BaseHTTPRequestHandler):
        def reply(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            state.requests.append(dict(method=self.command, path=self.path, body=body, headers=dict(self.headers)))
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


def test_wire_preserves_payload_and_bypasses_proxy(joint, identity, http_server, monkeypatch):
    for key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy'):
        monkeypatch.setenv(key, 'http://127.0.0.1:1')
    monkeypatch.setenv('NO_PROXY', '')
    monkeypatch.setenv('no_proxy', '')
    body = protocol.request_payload(joint)
    http_server.raw = json.dumps(answer(joint, identity)).encode()
    observed = []
    response = client.request(body=body, endpoint=http_server.endpoint,
        on_response=lambda status, raw: observed.append((status, raw)))
    assert protocol.validate_response(response, joint.action_ids) == 'move_1'
    sent = http_server.requests[0]
    assert sent['method'] == 'POST' and sent['path'] == '/evaluate'
    assert sent['body'] == client.request_bytes(body)
    assert json.loads(sent['body']) == {'profile': protocol.PROFILE, 'payload_json': joint.payload_json}
    assert observed == [(200, http_server.raw.decode())]
    http_server.raw = json.dumps(identity).encode()
    assert client.health(http_server.endpoint, identity) == identity
    assert http_server.requests[-1]['method'] == 'GET' and http_server.requests[-1]['path'] == '/health'


@pytest.mark.parametrize('status', [302, 307, 400, 422, 500])
def test_http_error_no_redirect_or_retry(joint, http_server, status):
    http_server.status, http_server.raw = status, b'rejected'
    http_server.headers = {'Location': 'http://outside.invalid/'}
    seen = []
    with pytest.raises(urllib.error.HTTPError):
        client.request(body=protocol.request_payload(joint), endpoint=http_server.endpoint,
            on_response=lambda code, raw: seen.append((code, raw)))
    assert len(http_server.requests) == 1 and seen == [(status, 'rejected')]


@pytest.mark.parametrize('raw', [b'not json', b'\xff', b'{"x":NaN}', b'{"x":1e999}', b'{"x":1,"x":2}'])
def test_malformed_response_preserved_before_parse(joint, http_server, raw):
    http_server.raw = raw
    seen = []
    with pytest.raises((ValueError, UnicodeError)):
        client.request(body=protocol.request_payload(joint), endpoint=http_server.endpoint,
            on_response=lambda code, body: seen.append((code, body)))
    assert seen == [(200, raw.decode('utf-8', errors='replace'))]


@pytest.mark.parametrize('field', ['winner', 'private', 'actor_seeds', 'q_targets', 'original_choice'])
def test_teacher_or_private_input_never_reaches_transport(joint, field, http_server):
    payload = joint.payload
    payload['state'][field] = 'forbidden'
    body = dict(profile=protocol.PROFILE, payload_json=json.dumps(payload))
    with pytest.raises(ValueError, match='teacher/private'):
        client.request(body=body, endpoint=http_server.endpoint)
    assert http_server.requests == []


@pytest.mark.parametrize('field', client.HEALTH_IDENTITY)
def test_server_identity_drift_is_shared_failure(identity, field):
    wrong = dict(identity)
    wrong[field] = 'changed'
    with pytest.raises(client.IdentityError):
        client.validate_identity(wrong, identity, health=True)


@pytest.fixture
def session(tmp_path, identity, http_server, monkeypatch):
    monkeypatch.setattr(p, 'InputGenerator', lambda _dex: SimpleNamespace(close=lambda: None))
    value = p.Session(tmp_path, endpoint=http_server.endpoint, identity=identity,
        deadline_monotonic=time.monotonic() + 600)
    try:
        yield value
    finally:
        value.close()


def test_singleton_still_calls_model_and_records_exact_wire(session, joint, identity, http_server):
    payload = joint.payload
    payload['actions'] = payload['actions'][:1]
    joint = JointInput(json.dumps(payload))
    http_server.raw = json.dumps(answer(joint, identity, [0])).encode()
    response = asyncio.run(session.evaluate(protocol.request_payload(joint), decision='singleton'))
    assert response['q_values'] == {'move_1': 0}
    assert session.calls == len(http_server.requests) == 1
    assert [event['type'] for event in session.records] == ['http_request', 'http_response', 'response']
    assert session.records[0]['raw_body'].encode() == http_server.requests[0]['body']
    assert session.records[1]['raw_body'] == http_server.raw.decode()


@pytest.mark.parametrize('mutation', ['missing', 'order', 'nan', 'choice'])
def test_unusable_model_output_is_battle_isolated(session, joint, identity, http_server, mutation):
    response = answer(joint, identity)
    if mutation == 'missing':
        del response['q_values']['move_1']
    elif mutation == 'order':
        response['q_values'] = dict(reversed(list(response['q_values'].items())))
    elif mutation == 'nan':
        response['q_values']['move_1'] = float('nan')
    else:
        response['choice'] = 'switch_2'
    http_server.raw = json.dumps(response).encode()
    with pytest.raises(j.UnusableChoice):
        asyncio.run(session.evaluate(protocol.request_payload(joint), decision='bad'))
    assert len(http_server.requests) == 1
    assert any(event['type'] == 'http_response' for event in session.records)
    assert not any(event['type'] in ('response', 'wire') for event in session.records)


def test_input_hash_mismatch_is_shared_failure(session, joint, identity, http_server):
    response = answer(joint, identity)
    response['input_sha256'] = 'wrong input'
    http_server.raw = json.dumps(response).encode()
    with pytest.raises(client.IdentityError):
        asyncio.run(session.evaluate(protocol.request_payload(joint), decision='wrong-input'))


def test_expired_reply_is_preserved_and_never_accepted(session, joint, identity, monkeypatch):
    calls = []
    session.timeout = .01

    def slow(*_args, on_response=None, **_kwargs):
        calls.append(1)
        time.sleep(.04)
        response = answer(joint, identity)
        on_response(200, json.dumps(response))
        return response

    monkeypatch.setattr(client, 'request', slow)
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(session.evaluate(protocol.request_payload(joint), decision='late'))
    assert calls == [1]
    assert any(event['type'] == 'request_expired' for event in session.records)
    assert any(event['type'] == 'http_response' for event in session.records)
    assert not any(event['type'] in ('response', 'selection', 'wire') for event in session.records)


def fixture_player(joint, identity, tmp_path, monkeypatch, *, failure=None, choice=None):
    value = object.__new__(p.player_class())
    commands = {'move_1': '/choose move 1', 'move_1_terastallize': '/choose move 1 terastallize',
                'switch_2': '/choose switch 2', 'team_3': '/team 312456'}
    value.expected_actor, value.latest_rqid = 'p2', 1
    value.request = dict(side=dict(id='p2'), rqid=1)
    value.prefix, value.boundary, value.submitted_team = [], {'protocol_event_seq': 1, 'line_index': 0}, 'own'
    snapshots, records, sent = [], [], []

    def snapshot(*_args, **_kwargs):
        snapshots.append(1)
        if len(snapshots) > 1 and failure == 'snapshot':
            raise ValueError('official snapshot failed')
        return dict(request=None if failure == 'withdrawn' else dict(rqid=2 if failure == 'official' else 1))

    value.official = SimpleNamespace(snapshot=snapshot, identity={})

    async def send(*args):
        sent.append(args)

    value.ps_client = SimpleNamespace(username='jointfixture', send_message=send)

    async def evaluate(body, **_kwargs):
        assert body == protocol.request_payload(joint)
        if failure == 'stale':
            value.latest_rqid = 2
        elif failure == 'cancelled':
            raise asyncio.CancelledError()
        elif failure == 'timeout':
            raise asyncio.TimeoutError()
        elif failure == 'failed':
            value.session.failure_event.set()
        response = answer(joint, identity, [int(key == choice) for key in joint.action_ids] if choice else None)
        if failure == 'incomplete':
            del response['q_values']['move_1']
        return response

    async def generate(*_args, **_kwargs):
        return joint, commands, {'audit': 'preserved'}

    value.session = SimpleNamespace(directory=tmp_path, records=records, dex={}, initial_pp_policy=None,
        failure_event=asyncio.Event(), evaluate=evaluate, generate=generate,
        timeout=0 if failure == 'expired' else 600, remaining=lambda: -1 if failure == 'budget' else 600,
        record=records.append)
    current = dict(commands)
    if failure == 'changed':
        current.pop('switch_2')
    elif failure == 'order':
        current = dict(reversed(list(current.items())))
    monkeypatch.setattr(j, 'make_input', lambda *_a, **_k: ({}, current))
    return value, records, sent


@pytest.mark.parametrize('failure', ['stale', 'official', 'changed', 'order', 'timeout', 'expired', 'budget',
                                    'failed', 'incomplete', 'cancelled', 'snapshot', 'withdrawn'])
def test_invalid_or_stale_request_never_sends(joint, identity, tmp_path, monkeypatch, failure):
    value, records, sent = fixture_player(joint, identity, tmp_path, monkeypatch, failure=failure)
    with pytest.raises((ValueError, RuntimeError, asyncio.TimeoutError, asyncio.CancelledError)):
        asyncio.run(value._handle_battle_request(SimpleNamespace(in_team_preview=False, battle_tag='fixture')))
    assert sent == [] and not any(event['type'] in ('selection', 'wire') for event in records)
    assert records[-1]['type'] == 'decision_rejected' and records[-1]['transmission'] == 'forbidden'


@pytest.mark.parametrize('choice,kind,command', [
    ('move_1', 'turn_action', '/choose move 1'),
    ('move_1_terastallize', 'turn_action', '/choose move 1 terastallize'),
    ('switch_2', 'turn_action', '/choose switch 2'),
    ('switch_2', 'forced_switch', '/choose switch 2'),
    ('team_3', 'lead', '/team 312456')])
def test_legal_actions_preserve_exact_wire_and_revalidate(joint, identity, tmp_path, monkeypatch, choice, kind, command):
    payload = joint.payload
    payload['state']['decision_kind'] = kind
    joint = JointInput(json.dumps(payload))
    value, records, sent = fixture_player(joint, identity, tmp_path, monkeypatch, choice=choice)
    value.request.update(teamPreview=kind == 'lead', forceSwitch=[kind == 'forced_switch'])
    asyncio.run(value._handle_battle_request(SimpleNamespace(in_team_preview=kind == 'lead', battle_tag='fixture')))
    assert sent == [(command, 'fixture', '1')]
    assert [event['type'] for event in records] == ['input', 'revalidation', 'selection', 'wire']
    assert records[0]['payload_json'] == joint.payload_json
    assert records[1]['passed'] is True
    assert records[2]['choice'] == choice and records[2]['automatic'] is False


def test_tie_uses_first_original_candidate(joint, identity, tmp_path, monkeypatch):
    value, records, sent = fixture_player(joint, identity, tmp_path, monkeypatch)
    asyncio.run(value._handle_battle_request(SimpleNamespace(in_team_preview=False, battle_tag='fixture')))
    assert sent == [('/choose move 1', 'fixture', '1')]
    assert records[-2]['choice'] == 'move_1'


def test_new_request_id_seen_before_locked_processing(monkeypatch):
    async def scenario():
        gate, processed = asyncio.Event(), []

        class Base:
            async def _handle_battle_message(self, messages):
                await gate.wait()
                processed.append(messages)

        monkeypatch.setattr(j, 'player_class', lambda: Base)
        value = p.player_class()()
        messages = [['', 'request', '{"rqid":2}']]
        task = asyncio.create_task(value._handle_battle_message(messages))
        await asyncio.sleep(0)
        assert value.latest_rqid == 2 and processed == []
        gate.set()
        await task
        await value._handle_battle_message([['', 'request', '']])
        assert value.latest_rqid is None

    asyncio.run(scenario())


def test_unusable_choice_is_not_escalated_by_peer_notice():
    model = dict(actor='p2', failure_scope='battle', error=dict(type='UnusableChoice', detail='missing choice'))
    peer = dict(actor='p1', failure_scope='collection',
                error=dict(type='RuntimeError', detail='opponent technical failure: UnusableChoice'))
    assert b.actor_failure({'p2': model, 'p1': peer}) == (model['error'], 'battle')
    peer['error']['detail'] = 'parser failed independently'
    assert b.actor_failure({'p2': model, 'p1': peer}) == (peer['error'], 'collection')


def test_admission_preserves_prior_attempt_and_full_budget(tmp_path):
    row = dict(game_id='test-1', directory='games/001-test-1', live_directory='games/001-test-1/live', joint_actor='p2')
    plan = dict(experiment_id='EX-081', profile=protocol.PROFILE, limits=b.LIMITS, schedule=[row])
    with pytest.raises(TimeoutError):
        b._validate_game(tmp_path, plan, row, time.time() + 5390)
    game, _ = b._validate_game(tmp_path, plan, row, time.time() + 6000)
    game.mkdir(parents=True)
    with pytest.raises(FileExistsError, match='recollection'):
        b._validate_game(tmp_path, plan, row, time.time() + 6000)


def test_source_change_stops_collection(tmp_path, monkeypatch):
    monkeypatch.setattr(b, 'ROOT', tmp_path)
    source = tmp_path / 'source.py'
    source.write_text('frozen')
    plan = {'source': {'source.py': b.sha(source)}}
    b.verify_sources(plan)
    source.write_text('changed')
    with pytest.raises(client.IdentityError, match='source changed'):
        b.verify_sources(plan)


@pytest.mark.parametrize('isolated', [False, True])
def test_harness_owns_cleanup_and_never_recollects(tmp_path, monkeypatch, identity, isolated):
    from integration.pokechamp import benchmark, parallel_server
    from integration.pokechamp.joint_q.battle_eval import audit
    row = dict(slot=1, global_slot=1, game_id='test-1', directory='games/001-test-1',
        live_directory='games/001-test-1/live', joint_actor='p2', actor_seeds=[101, 202],
        teams=['opponent', 'own'], battle_seed='1,2,3,4')
    plan = dict(experiment_id='EX-081', profile=protocol.PROFILE, limits=b.LIMITS, schedule=[row],
        source={'fixture': 'hash'}, teams={'opponent': {}, 'own': {}}, server=identity)
    (tmp_path / 'configuration.json').write_text(json.dumps(plan))
    calls, closed, stopped = [], [], []

    class FakeServer:
        def __init__(self, attempt, port, seed):
            self.created, self.process = False, None
            assert port == 8106 and seed == row['battle_seed']

        def start(self):
            self.created = True

        def close(self):
            self.created = False
            closed.append('owned-server')

    class Process:
        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))
            assert command[2] == b.MODULE and kwargs['env']['CUDA_VISIBLE_DEVICES'] == ''
            assert kwargs['cwd'] == b.ROOT / 'pokechamp' and kwargs['start_new_session'] is True
            actor = command[-1]
            attempt = Path(command[command.index('--attempt') + 1])
            seed = row['actor_seeds'][int(actor[-1]) - 1]
            result = dict(actor=actor, completed=True, outcome='player_won' if actor == 'p2' else 'player_lost',
                turns=8, battle_tag='battle-test', python_random_seed=seed, numpy_random_seed=seed,
                python_hash_seed=str(seed))
            if isolated and actor == 'p2':
                result.update(completed=False, failure_scope='battle',
                    error=dict(type='UnusableChoice', detail='no executable choice'))
            b.atomic(attempt / f'{actor}.result.json', result)

        def poll(self):
            return 0

    monkeypatch.setattr(b, 'verify_sources', lambda _plan: None)
    monkeypatch.setattr(client, 'health', lambda *_args, **_kwargs: identity)
    monkeypatch.setattr(b, 'reserve_port', lambda *_args: (8106, (tmp_path / 'port.lock').open('w')))
    monkeypatch.setattr(parallel_server, 'BattleServer', FakeServer)
    monkeypatch.setattr(b.subprocess, 'Popen', Process)
    monkeypatch.setattr(benchmark, 'terminate', lambda process: stopped.append(process))
    monkeypatch.setattr(audit, 'audit', lambda *_args: {'passed': True})
    result = b.run_game(tmp_path, plan, row, 'http://127.0.0.1:8110', time.time() + 6000)
    assert result['continue_allowed'] is True and result['valid'] is (not isolated)
    assert result['failure_scope'] == ('battle' if isolated else None)
    assert closed == ['owned-server'] and len(stopped) == len(calls) == 2
    assert (tmp_path / row['live_directory'] / 'checksums.sha256').exists()
    with pytest.raises(FileExistsError):
        b.run_game(tmp_path, plan, row, 'http://127.0.0.1:8110', time.time() + 6000)
    assert len(calls) == 2
