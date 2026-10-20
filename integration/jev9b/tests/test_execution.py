"""Bounded qualification, transport cancellation, and the final write boundary."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from integration.jev9b import battle, client, execute, gates, study


@pytest.mark.parametrize('failures,permanent', [(3, False), (4, False), (1, True)])
def test_session_reuses_identical_body_and_id(tmp_path, failures, permanent):
    calls, delays = [], []

    class Client:
        def health(self):
            return dict(ready=True, identity='fixture', model=battle.MODEL, revision=battle.REVISION)

        def evaluate(self, body, *, request_id, retries):
            calls.append((copy.deepcopy(body), request_id, retries))
            if len(calls) <= failures:
                raise client.LocalRequestError('fixture', retryable=not permanent)
            return {'answer': 'completed'}

        def close(self):
            pass

    session = battle.Session(tmp_path, expected_identity='fixture', client_factory=lambda **_: Client())
    async def backoff(seconds):
        delays.append(seconds)
    session._backoff = backoff
    payload = dict(state={}, questions={'action': dict(type='choice', instructions='x',
                   criteria={'first': {}, 'second': {}})})
    try:
        if failures == 3 and not permanent:
            assert asyncio.run(session.evaluate(payload, decision='one')) == {'answer': 'completed'}
        else:
            with pytest.raises(client.LocalRequestError):
                asyncio.run(session.evaluate(payload, decision='one'))
        assert len(calls) == (1 if permanent else 4)
        assert all(call == calls[0] for call in calls)
        assert calls[0][0]['model'] == 'autotrust/JEV-9B'
        assert calls[0][1].startswith('ex085-')
        assert delays == ([] if permanent else [10., 30., 60.])
        ledger = json.loads((tmp_path/'ledger.json').read_text())
        assert ledger['logical_requests'] == 1 and ledger['requests'] == len(calls)
    finally:
        asyncio.run(session.close())


def test_cancel_during_retry_wait_prevents_another_attempt(tmp_path):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise client.LocalRequestError('timeout', retryable=True)
    transport = SimpleNamespace(health=lambda: dict(ready=True, identity='fixture',
        model=battle.MODEL, revision=battle.REVISION), evaluate=fail, close=lambda: None)
    session = battle.Session(tmp_path, expected_identity='fixture', client_factory=lambda **_: transport)
    async def cancel(_):
        session.fail(RuntimeError('cancelled'))
    session._backoff = cancel
    try:
        with pytest.raises(RuntimeError, match='halted'):
            asyncio.run(session.evaluate(dict(state={}, questions={'action': dict(type='choice',
                instructions='x', criteria={'a': {}, 'b': {}})}), decision='one'))
        assert len(calls) == 1
    finally:
        asyncio.run(session.close())


def test_repeat_gate_checks_numerics_and_reclamation():
    first = dict(answers={'action': dict(choice='a', probabilities={'a': .75, 'b': .25})},
                 metadata=dict(gpu_allocated_bytes=[1]*4, gpu_reserved_bytes=[2]*4))
    assert gates.compare_repeat(first, copy.deepcopy(first))['passed']
    altered = copy.deepcopy(first)
    altered['answers']['action']['probabilities'] = {'a': .751, 'b': .249}
    with pytest.raises(ValueError, match='tolerance'):
        gates.compare_repeat(first, altered)
    altered = copy.deepcopy(first)
    altered['metadata']['gpu_reserved_bytes'][0] = 3
    assert gates.compare_repeat(first, altered, check_memory=False)['passed']
    with pytest.raises(ValueError, match='reclaim'):
        gates.compare_repeat(first, altered)
    altered['answers']['action']['choice'] = 'b'
    with pytest.raises(ValueError, match='tolerance'):
        gates.compare_repeat(first, altered, check_memory=False)


def test_terminal_status_is_included_in_final_seal(tmp_path, monkeypatch):
    from contextlib import redirect_stdout
    monkeypatch.setattr(execute, 'RUN', tmp_path)
    monkeypatch.setattr(execute, 'EVIDENCE', tmp_path/'evidence')
    monkeypatch.setattr(execute, 'report', lambda _: (tmp_path/'report.md').write_text('완료\n'))
    completion = dict(passed=True, error=None, result=dict(completed=32))
    with (tmp_path/'controller.log').open('w') as output, redirect_stdout(output):
        execute.finish_completion(completion)
    assert json.loads((tmp_path/'controller.log').read_text())['completed'] == 32
    assert 'controller.log' in study.verify_seal(tmp_path)


def test_preflight_never_overwrites_execution(tmp_path, monkeypatch):
    (tmp_path/'execution.json').write_text('{}')
    monkeypatch.setattr(execute, 'RUN', tmp_path)
    with pytest.raises(FileExistsError):
        execute.execute()


def test_failed_preflight_costs_survive_without_collection(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setattr(execute, 'RUN', tmp_path)
    serving = tmp_path/'serving/server'
    serving.mkdir(parents=True)
    (serving.parent/'loaded.json').write_text('{}')
    db = sqlite3.connect(serving/'requests.sqlite3')
    db.execute('CREATE TABLE events(request_id TEXT,kind TEXT)')
    db.execute('CREATE TABLE requests(request_id TEXT,state TEXT,response_body BLOB)')
    db.executemany('INSERT INTO events VALUES (?,?)', [
        ('ex085-gate-lead', 'inference_started'), ('ex085-gate-long', 'inference_started')])
    body = dict(usage=dict(input_tokens=12, output_tokens=0), metadata=dict(elapsed_seconds=1.5))
    db.execute('INSERT INTO requests VALUES (?,?,?)', ('ex085-gate-lead', 'completed', json.dumps(body)))
    db.execute('INSERT INTO requests VALUES (?,?,?)', ('ex085-gate-long', 'failed', None))
    db.commit()
    db.close()
    costs = execute.inference_accounting(tmp_path/'collection')
    assert costs['confirmed_server_loads'] == 1
    assert costs['collection_inferences'] == 0 and costs['preflight_inferences'] == 2
    assert costs['preflight_received_usage']['input_tokens'] == 12
    assert costs['preflight_usage_unknown_requests'] == 1
    assert costs['preflight_inference_seconds'] == 1.5


def test_controller_keeps_saved_denominator_after_interrupt(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from integration.jev9b import resource
    import httpx
    evidence = tmp_path/'evidence'
    evidence.mkdir()
    for name in ('download.json', 'model-ready.json', 'lengths.json'):
        (evidence/name).write_text('{"passed":true}')
    partial = dict(passed=False, planned=32, attempted=2, completed=1, failed=1,
                   invalid=0, unattempted=30)
    monkeypatch.setattr(execute, 'RUN', tmp_path)
    monkeypatch.setattr(execute, 'EVIDENCE', evidence)
    monkeypatch.setattr(execute, 'EXPORT', tmp_path/'export')
    monkeypatch.setattr(execute.signal, 'signal', lambda *_: None)
    monkeypatch.setattr(study, 'source_identity', lambda: {})
    monkeypatch.setattr(execute, 'source_snapshot', lambda *_: None)
    monkeypatch.setattr(execute, 'command_stage', lambda *a, **kw: dict(passed=True))
    monkeypatch.setattr(execute, 'closure', lambda: dict(passed=True))
    monkeypatch.setattr(execute, 'resource_summary', lambda: {})
    monkeypatch.setattr(execute, 'inference_accounting', lambda *_: {})
    monkeypatch.setattr(execute, 'finalize', lambda **_: dict(passed=True))
    monkeypatch.setattr(execute, 'finish_completion', lambda _: None)
    monkeypatch.setattr(resource, 'ResourceMonitor', lambda *a, **kw: nullcontext())
    monkeypatch.setattr(client, 'LocalClient', lambda *_: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(execute.subprocess, 'Popen', lambda *a, **kw: SimpleNamespace(pid=123, poll=lambda: None))
    monkeypatch.setattr(execute, 'stop_owned_process', lambda *_: None)
    monkeypatch.setattr(httpx, 'get', lambda *a, **kw: SimpleNamespace(status_code=200))
    monkeypatch.setattr(gates, 'qualify', lambda *_: dict(serving_identity='fixture'))
    def interrupted(coroutine):
        coroutine.close()
        (tmp_path/'collection').mkdir()
        (tmp_path/'collection/result.json').write_text(json.dumps(partial))
        raise KeyboardInterrupt('fixture cancellation')
    monkeypatch.setattr(execute.asyncio, 'run', interrupted)
    completion = execute.execute()
    assert not completion['passed']
    assert completion['result'] == partial
    assert completion['error']['type'] == 'KeyboardInterrupt'
