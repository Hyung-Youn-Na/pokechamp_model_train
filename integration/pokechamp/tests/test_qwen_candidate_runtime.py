"""Explicit profile admission and diagnostic isolation, without a model/GPU."""
from contextlib import nullcontext
import copy
import json
import threading
import time
from types import SimpleNamespace
import urllib.error
from http.server import ThreadingHTTPServer

import pytest

from integration.pokechamp import qwen_value as v
from integration.pokechamp.qwen_server import Runtime, handler


@pytest.fixture
def body():
    row = json.loads((v.TRAINING / 'data/inputs.jsonl').read_text().splitlines()[0])
    return dict(observation=copy.deepcopy(row['observation']), actions=copy.deepcopy(row['actions']))


def test_candidate_profile_requires_explicit_admission(body):
    body['observation']['state']['version'] = v.STATE_VERSION
    with pytest.raises(ValueError, match='explicitly enabled'):
        v.validate_input(body)
    assert v.validate_input(body, allowed_versions=v.SUPPORTED_VERSIONS)[1] == body['actions']
    with pytest.raises(ValueError, match='configured'):
        v.validate_input(body, allowed_versions=('invented-version',))


def test_diagnostics_route_disabled_by_default(body, monkeypatch):
    class OldRuntime:
        def health(self):
            return {'ready': True}
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(OldRuntime()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(v, 'ENDPOINT', f'http://127.0.0.1:{server.server_port}')
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            v.request('/diagnose', body)
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_diagnostic_http_never_calls_value_evaluation(body, monkeypatch):
    calls = []
    class FakeRuntime:
        diagnostics_enabled = True
        def diagnose(self, value, deadline):
            calls.append('diagnose')
            assert value['action_id'] == body['actions'][0]['action_id']
            assert deadline > time.monotonic()
            return {'status': 'invalid_json', 'raw_output': 'A', 'prediction': None}
        def evaluate(self, *_):
            calls.append('evaluate')
            raise AssertionError('diagnostic attempted value evaluation')
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(FakeRuntime()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(v, 'ENDPOINT', f'http://127.0.0.1:{server.server_port}')
    try:
        result = v.request('/diagnose', dict(body, action_id=body['actions'][0]['action_id'],
                                           scenario={'opponent_action': 'unknown'}))
        assert calls == ['diagnose']
        assert result['status'] == 'invalid_json'
        assert not {'choice', 'command', 'q_values'} & result.keys()
    finally:
        server.shutdown()
        server.server_close()


def test_runtime_keeps_queue_encoding_and_forward_times_separate(body, tmp_path):
    from integration.pokechamp.tests.test_qwen_local import Tokenizer
    class Scalar:
        def cpu(self):
            return .6
    class Event:
        def __init__(self, **_kwargs):
            pass
        def record(self):
            pass
        def elapsed_time(self, _):
            return .1
    runtime = object.__new__(Runtime)
    runtime.lock = threading.Lock()
    runtime.failed = None
    runtime.requests = runtime.forwards = 0
    runtime.gpu_seconds = 0.
    runtime.tok = Tokenizer()
    runtime.policy = SimpleNamespace(probabilities=lambda _ids: [Scalar()])
    runtime.pv = SimpleNamespace(torch=SimpleNamespace(no_grad=nullcontext,
        cuda=SimpleNamespace(Event=Event, synchronize=lambda: None)))
    runtime.data = v.data_module()
    runtime.output = tmp_path
    runtime.save_progress = lambda: None
    result = runtime.evaluate(body, time.monotonic() + 5)
    assert result['queue_seconds'] >= 0 and result['encoding_seconds'] >= 0
    assert result['total_elapsed_seconds'] >= result['elapsed_seconds']
    assert result['total_elapsed_seconds'] >= result['encoding_seconds']
    assert v.validate_response(result, body['actions']) == body['actions'][0]['action_id']


def test_explicit_lifecycle_settings_cannot_reuse_different_owned_server(monkeypatch, tmp_path):
    from integration.pokechamp import qwen_control as control
    state = tmp_path / 'owner.json'
    state.write_text(json.dumps({'pid': 1}))
    monkeypatch.setattr(control, 'STATE', state)
    monkeypatch.setattr(control, 'owned', lambda _record: True)
    monkeypatch.setattr(control, 'status', lambda: {'health': {
        'allowed_input_versions': [v.OLD_VERSION], 'diagnostics_enabled': False}})
    with pytest.raises(ValueError, match='different explicit'):
        control.start(candidate_state=True, diagnostics=True)


def test_expired_loading_deadline_starts_no_process(monkeypatch):
    from integration.pokechamp import qwen_control as control
    monkeypatch.setattr(control.subprocess, 'Popen', lambda *_a, **_k: pytest.fail('started expired server'))
    with pytest.raises(TimeoutError, match='loading deadline'):
        control.start(deadline_at=time.time() - 1)


def test_runtime_uses_earlier_study_deadline():
    runtime = object.__new__(Runtime)
    runtime.study_deadline_at = time.time() + 2
    request_deadline = time.monotonic() + 600
    bounded = runtime.bounded_deadline(request_deadline)
    assert 0 < bounded - time.monotonic() <= 2
    assert runtime.bounded_deadline(time.monotonic() + .1) < bounded


def test_owned_study_stops_on_collection_error(tmp_path, monkeypatch):
    from integration.pokechamp import qwen_state_run as runner
    output = tmp_path / 'study'
    output.mkdir()
    (output / 'frozen-inputs.json').write_text('{}')
    state = tmp_path / 'owner.json'
    calls = []
    monkeypatch.setattr(runner.control, 'STATE', state)
    monkeypatch.setattr(runner, 'freeze', lambda _p: {'files': {}})
    monkeypatch.setattr(runner.control, 'status', lambda: {'owned_running': False, 'health': None})
    monkeypatch.setattr(runner, 'gpu_sample', lambda: {'physical_gpu': 1})
    def start(**options):
        calls.append(('start', options))
        owner = {'started_at': time.time(), 'owner': options['owner_token']}
        state.write_text(json.dumps(owner))
        return {'owner': owner}
    def fail(*_a, **_k):
        raise RuntimeError('fixture serving failure')
    monkeypatch.setattr(runner.control, 'start', start)
    monkeypatch.setattr(runner.study, 'verify_frozen_inputs', lambda _p: None)
    monkeypatch.setattr(runner.study, 'evaluate', fail)
    monkeypatch.setattr(runner.control, 'stop', lambda **_k: calls.append(('stop', _k)) or {'closure': {}})
    monkeypatch.setattr(runner.study, 'report', lambda _p: None)
    result = runner.run(output)
    assert not result['passed'] and result['error']['detail'] == 'fixture serving failure'
    assert [r[0] for r in calls] == ['start', 'stop']
    assert calls[0][1]['deadline_at'] == result['started_at'] + 7200
    assert calls[0][1]['candidate_state'] and calls[0][1]['diagnostics']
    assert (output / 'run-result.json').exists() and (output / 'checksums.sha256').exists()


def test_owned_study_refuses_existing_server(tmp_path, monkeypatch):
    from integration.pokechamp import qwen_state_run as runner
    monkeypatch.setattr(runner, 'freeze', lambda _p: {'files': {}})
    monkeypatch.setattr(runner.control, 'status', lambda: {'owned_running': True, 'health': {'ready': True}})
    monkeypatch.setattr(runner.control, 'start', lambda **_k: pytest.fail('reused existing server'))
    monkeypatch.setattr(runner.control, 'stop', lambda **_k: pytest.fail('stopped existing server'))
    with pytest.raises(ValueError, match='left untouched'):
        runner.run(tmp_path)


def test_cleanup_does_not_signal_replaced_process_identity(tmp_path, monkeypatch):
    from integration.pokechamp import qwen_control as control
    path = tmp_path / 'owner.json'
    path.write_text(json.dumps({'owner': 'replacement', 'pid': 42, 'start_ticks': '2'}))
    monkeypatch.setattr(control, 'STATE', path)
    monkeypatch.setattr(control.os, 'kill', lambda *_: pytest.fail('signalled a different owner'))
    result = control.stop(expected_owner={'owner': 'original', 'pid': 42, 'start_ticks': '1'})
    assert not result['stopped'] and 'left untouched' in result['reason']
