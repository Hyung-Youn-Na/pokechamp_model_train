"""Observable EX-062 contract and no-send failure boundaries; no GPU/battles."""
import asyncio
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import urllib.error
from http.server import ThreadingHTTPServer

import pytest

from integration.pokechamp import qwen_value as v
from integration.pokechamp.qwen_player import Session, player_class
from integration.pokechamp.qwen_server import Runtime, handler


def test_audit_keeps_complete_frame_empty_rows_and_excludes_future():
    from integration.pokechamp.qwen_audit import cutoff_prefix
    from integration.pokechamp.observation.runtime import rows
    frames = [dict(event_seq=1, protocol='>battle\n|init|battle\n\n'),
              dict(event_seq=2, protocol='>battle\n|request|{}\n|future|hidden'),
              dict(event_seq=3, protocol='|future|hidden')]
    prefix = cutoff_prefix(frames, dict(protocol_event_seq=2, line_index=1))
    assert prefix == [dict(event_seq=1, protocol='>battle\n|init|battle\n\n'),
                      dict(event_seq=2, protocol='>battle\n|request|{}')]
    assert rows(prefix) == [(1, 0, '>battle'), (1, 1, '|init|battle'), (1, 2, ''),
                            (2, 0, '>battle'), (2, 1, '|request|{}')]


def test_training_matchup_matches_sealed_source_and_preview():
    from integration.pokechamp.qwen_battle import configuration, verify_teams
    records, schedule, provenance, probe = configuration('EX-063')
    sealed = json.loads((v.ROOT / '.pokechamp-data/rollouts/ex058-b19-rollout-v1/manifest.json').read_text())
    original = sealed['original_request']['slot']
    assert len(schedule) == 1 and schedule[0]['qwen_actor'] == sealed['actor'] == 'p2'
    for key in ('teams', 'battle_seed', 'actor_seeds'):
        assert schedule[0][key] == original[key]
    assert provenance['original_outcome'] == sealed['original_outcome']
    assert 'ep104/gpu-probe' in str(probe)
    for side, key in zip(('p1', 'p2'), original['teams']):
        row = records[key]
        assert row['original_packed'] == sealed['teams'][side]['team']
        assert row['submitted_packed'] == sealed['simulator_teams'][side]['team']
        for raw, submitted in zip(row['original_packed'].split(']'), row['submitted_packed'].split(']')):
            before, after = raw.split('|'), submitted.split('|')
            assert before[:7] == after[:7] and before[8:] == after[8:]
            assert not before[7] or before[7] == after[7]
    assert verify_teams(records)['passed']


def test_original_two_match_schedule_remains_separate(monkeypatch):
    from integration.pokechamp import qwen_battle as battle
    monkeypatch.setattr(battle, 'teams', lambda: {'1': {}, '10': {}})
    records, schedule, provenance, probe = battle.configuration('EX-062')
    assert len(schedule) == 2 and [r['qwen_actor'] for r in schedule] == ['p1', 'p2']
    assert all(r['teams'] == ['1', '10'] and r['actor_seeds'] == [20260930, 20260931] for r in schedule)
    assert probe == v.EVIDENCE / 'gpu-probe' and provenance == {}


@pytest.fixture
def body():
    row = json.loads((v.TRAINING / 'data/inputs.jsonl').read_text().splitlines()[0])
    return dict(observation=copy.deepcopy(row['observation']), actions=copy.deepcopy(row['actions']))


class Tokenizer:
    def apply_chat_template(self, messages, **kwargs):
        assert kwargs['enable_thinking'] is False
        return json.dumps(messages)

    def encode(self, prompt, **kwargs):
        return [1, 2, 3]


def response(body, qs=None):
    actions, encoded = v.encoded_candidates(body, Tokenizer())
    qs = qs or [0.7] * len(actions)
    chosen = max(range(len(actions)), key=lambda i: qs[i])
    return dict(profile=v.PROFILE, revision=v.REVISION, adapter_sha256=v.ADAPTER_SHA,
        q_values={a['action_id']: q for a, q in zip(actions, qs)},
        choice=actions[chosen]['action_id'], command=actions[chosen]['command'],
        candidates=[row for ids, row in encoded])


def test_saved_22_observations_all_commands_and_order():
    count = 0
    for row in v.data_module().jsonl(v.TRAINING / 'data/inputs.jsonl'):
        body = dict(observation=row['observation'], actions=row['actions'])
        assert v.validate_input(body)[1] == row['actions']
        count += len(row['actions'])
    assert count == 167


@pytest.mark.parametrize('name', ['jev-ex050-leads.json', 'jev-offline-forced.json', 'jev-damage-prefix.json'])
def test_lead_force_move_tera_switch_mapping(name):
    from integration.pokechamp.jev_v4 import Adapter
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    fixture = json.loads((Path(__file__).parent / 'fixtures' / name).read_text())
    case = fixture[0] if isinstance(fixture, list) else fixture
    official = case.get('event', case).get('official')
    adapter = Adapter(json.loads((DEFAULT_BUILD / 'dex.json').read_text()))
    try:
        payload, commands, _ = adapter.generate(official, case['prefix'], case.get('own_team', ''),
                                               actor=official['request']['side']['id'])
        body = dict(observation=payload, actions=v.actions_from(payload, commands))
        v.validate_input(body)
        assert [a['action_id'] for a in body['actions']] == list(commands)
        if name == 'jev-ex050-leads.json':
            assert all(a['command'].startswith('team ') for a in body['actions'])
        elif name == 'jev-offline-forced.json':
            assert all(a['command'].startswith('switch ') for a in body['actions'])
        else:
            assert any('terastallize' in a['command'] for a in body['actions'])
    finally:
        adapter.close()


def test_tie_independent_q_and_single_candidate(body):
    answer = response(body)
    assert sum(answer['q_values'].values()) != 1
    assert v.validate_response(answer, body['actions']) == body['actions'][0]['action_id']
    key = body['actions'][0]['action_id']
    body['actions'] = body['actions'][:1]
    body['observation']['questions']['action']['criteria'] = {key: body['actions'][0]['description']}
    assert v.validate_response(response(body), body['actions']) == key


@pytest.mark.parametrize('mutation', ['forbidden', 'extra', 'reverse', 'command', 'duplicate'])
def test_rejected_input(body, mutation):
    if mutation == 'forbidden':
        body['observation']['state']['snapshot'] = {}
    elif mutation == 'extra':
        body['counts'] = {}
    elif mutation == 'reverse':
        body['actions'].reverse()
    elif mutation == 'command':
        body['actions'][0]['command'] = 'move 9'
    else:
        body['actions'].append(body['actions'][0])
    with pytest.raises(ValueError):
        v.validate_input(body)


@pytest.mark.parametrize('mutation', ['missing', 'nan', 'choice', 'command', 'audit'])
def test_unusable_response(body, mutation):
    answer = response(body)
    key = body['actions'][0]['action_id']
    if mutation == 'missing':
        answer['q_values'].pop(key)
    elif mutation == 'nan':
        answer['q_values'][key] = float('nan')
    elif mutation == 'choice':
        answer['choice'] = 'illegal'
    elif mutation == 'command':
        answer['command'] = 'switch 7'
    else:
        answer['candidates'].pop()
    with pytest.raises(ValueError):
        v.validate_response(answer, body['actions'])


def test_length_overflow_before_forward(body):
    class LongTokenizer(Tokenizer):
        def encode(self, *_args, **_kwargs):
            return [1] * (v.MAX_LEN + 1)
    with pytest.raises(ValueError, match='no truncation'):
        v.encoded_candidates(body, LongTokenizer())


def test_http_routes_validation_and_timeout(body, monkeypatch):
    class FakeRuntime:
        def health(self):
            return dict(ready=True)
        def evaluate(self, value, deadline):
            v.validate_input(value)
            return response(value)
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(FakeRuntime()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(v, 'ENDPOINT', f'http://127.0.0.1:{server.server_port}')
    try:
        assert v.request('/health')['ready']
        v.validate_response(v.request('/evaluate', body), body['actions'])
        with pytest.raises(urllib.error.HTTPError) as error:
            v.request('/evaluate', dict(body, snapshot={}))
        assert error.value.code == 400
        with pytest.raises(urllib.error.HTTPError) as error:
            v.request('/unknown')
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize('failure', ['stale', 'changed', 'timeout', 'incomplete'])
def test_handler_failures_never_send(body, failure, monkeypatch, tmp_path):
    from integration.pokechamp import jev_v4, jev_battle as j
    player = object.__new__(player_class())
    commands = {a['action_id']: ('/team ' + a['command'][5:] if a['command'].startswith('team ')
                else '/choose ' + a['command']) for a in body['actions']}
    player.expected_actor = 'p1'
    player.request = dict(side=dict(id='p1'), rqid=1)
    player.latest_rqid = 1
    player.prefix, player.boundary, player.submitted_team = [], {}, ''
    player.official = SimpleNamespace(snapshot=lambda *_args, **_kwargs: {}, identity={})
    sent = []
    async def send(*args):
        sent.append(args)
    player.ps_client = SimpleNamespace(username='qvfixture', send_message=send)
    answer = response(body)
    async def evaluate(_body, **_kwargs):
        if failure == 'stale':
            player.latest_rqid = 2
        elif failure == 'timeout':
            raise asyncio.TimeoutError()
        elif failure == 'incomplete':
            answer['q_values'].clear()
        return answer
    player.session = SimpleNamespace(directory=tmp_path, records=[], dex={}, initial_pp_policy=None,
        failure_event=asyncio.Event(), evaluate=evaluate, record=lambda e: None)
    async def generate(*_args, **_kwargs):
        return body['observation'], commands, {}, 0
    monkeypatch.setattr(jev_v4, 'generate', generate)
    monkeypatch.setattr(jev_v4, 'save_audit', lambda *_: {})
    current = dict(commands)
    if failure == 'changed':
        current.pop(next(iter(current)))
    monkeypatch.setattr(j, 'make_input', lambda *_args, **_kwargs: ({}, current))
    battle = SimpleNamespace(in_team_preview=False, battle_tag='fixture')
    with pytest.raises((ValueError, asyncio.TimeoutError)):
        asyncio.run(player._handle_battle_request(battle))
    assert sent == []


def test_expired_http_is_recorded_and_never_retried(body, monkeypatch, tmp_path):
    session = Session(tmp_path)
    calls = []
    def late(*_args, **_kwargs):
        calls.append(1)
        time.sleep(.04)
        return response(body)
    monkeypatch.setattr(v, 'request', late)
    monkeypatch.setattr(v, 'TIMEOUT', .01)
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(session.evaluate(body, decision='late'))
    assert len(calls) == 1
    assert any(e['type'] == 'request_expired' for e in session.records)
    assert not any(e['type'] == 'wire' for e in session.records)


def test_owned_process_refuses_foreign_pid(monkeypatch):
    from integration.pokechamp import qwen_control as c
    record = dict(pid=123, start_ticks='5', owner='owner-token')
    monkeypatch.setattr(c, 'process_identity', lambda _: dict(start_ticks='6', state='S',
        args=['integration.pokechamp.qwen_server', 'owner-token']))
    assert not c.owned(record)
    monkeypatch.setattr(c, 'process_identity', lambda _: dict(start_ticks='5', state='S', args=['foreign']))
    assert not c.owned(record)


def test_runtime_serializes_gpu_and_evaluates_single_candidate(body, tmp_path):
    key = body['actions'][0]['action_id']
    body['actions'] = body['actions'][:1]
    body['observation']['questions']['action']['criteria'] = {key: body['actions'][0]['description']}
    active, peak, calls = 0, 0, 0
    class Scalar:
        def cpu(self):
            return .6
    def probabilities(ids):
        nonlocal active, peak, calls
        active += 1
        peak = max(peak, active)
        time.sleep(.02)
        calls += 1
        active -= 1
        return [Scalar()]
    class Event:
        def __init__(self, **_kwargs):
            pass
        def record(self):
            pass
        def elapsed_time(self, _):
            return 20
    runtime = object.__new__(Runtime)
    runtime.lock = threading.Lock()
    runtime.failed = None
    runtime.requests = runtime.forwards = 0
    runtime.gpu_seconds = 0.
    runtime.tok = Tokenizer()
    runtime.policy = SimpleNamespace(probabilities=probabilities)
    runtime.pv = SimpleNamespace(torch=SimpleNamespace(no_grad=nullcontext,
        cuda=SimpleNamespace(Event=Event, synchronize=lambda: None)))
    runtime.data = v.data_module()
    runtime.output = tmp_path
    runtime.save_progress = lambda: None
    results = []
    def run():
        results.append(runtime.evaluate(body, time.monotonic()+5))
    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert calls == runtime.forwards == runtime.requests == 2
    assert peak == 1 and len(results) == 2
    assert all(r['choice'] == key for r in results)


@pytest.mark.parametrize('caller', ['workspace', 'temporary'])
def test_worker_assets_use_pokechamp_cwd_from_any_launcher(caller, monkeypatch, tmp_path):
    from integration.pokechamp.qwen_battle import verify_worker_assets, WORKER_CWD
    monkeypatch.chdir(v.ROOT if caller == 'workspace' else tmp_path)
    proof = verify_worker_assets()
    assert proof['cwd'] == str(WORKER_CWD)
    assert proof['sets'] > 0
    assert proof['sha256'] == v.data_module().sha256(WORKER_CWD / 'poke_env/data/static/gen9/ou/sets_1500.json')
