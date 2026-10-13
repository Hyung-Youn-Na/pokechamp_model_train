"""CPU rejection tests for numerical, fresh-inference, and continuous-memory gates."""
import copy
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from integration.jev27b import continuation_gates as gates
from integration.jev27b import continue_execute as controller
from integration.jev27b.client import request_bytes
from integration.jev27b.config import EVIDENCE
from integration.jev27b.server import RequestRegistry, json_bytes
from integration.jev27b.storage import read


@pytest.fixture
def saved_case():
    case = read(EVIDENCE / 'lengths/cases.json')[2]
    response = read(EVIDENCE / 'reload-a/result.json')['cases'][2]['body']
    return case['body'], response


def test_numerical_gate_accepts_exact_archived_result_and_rejects_choice_or_probability(saved_case):
    body, original = saved_case
    assert gates.numerical_difference(original, original, body)['passed']
    changed = copy.deepcopy(original)
    keys = list(changed['answers']['action']['probabilities'])
    choice = changed['answers']['action']['choice']
    changed['answers']['action']['choice'] = next(key for key in keys if key != choice)
    assert not gates.numerical_difference(original, changed, body)['passed']
    changed = copy.deepcopy(original)
    key = next(key for key, value in changed['answers']['action']['probabilities'].items() if value < .9)
    changed['answers']['action']['probabilities'][key] += .0002
    assert not gates.numerical_difference(original, changed, body)['passed']


@pytest.mark.parametrize('mutation', ['candidate-order', 'prompt', 'token-count', 'nan'])
def test_numerical_gate_rejects_linkage_and_nonfinite_values(saved_case, mutation):
    body, original = saved_case
    changed = copy.deepcopy(original)
    if mutation == 'candidate-order':
        changed['metadata']['candidate_ids'].reverse()
    elif mutation == 'prompt':
        changed['metadata']['prompt_sha256'] = '0' * 64
    elif mutation == 'token-count':
        changed['usage']['input_tokens'] += 1
    else:
        key = next(iter(changed['answers']['action']['probabilities']))
        changed['answers']['action']['probabilities'][key] = float('nan')
    with pytest.raises(ValueError):
        gates.numerical_difference(original, changed, body)


def test_archived_replay_includes_failed_battle_responses_and_original_unfinished_request():
    parent = EVIDENCE.parents[3] / '.pokechamp-data/jev/ex082-live'
    rows, stopped, shortest = gates.archived_requests(parent)
    assert len(rows) == 591
    result = read(parent / 'result.json')
    failed_user = result['outcomes'][23]['username']
    assert sum(row['decision'].startswith(failed_user + '-') for row in rows) == 10
    assert stopped['decision'].startswith(failed_user + '-')
    assert stopped['decision'] not in {row['decision'] for row in rows}
    assert shortest['response']['body']['usage']['input_tokens'] == 11439


def test_allocator_gate_checks_every_device_and_reserved_peak():
    metadata = {key: [gates.ALLOCATOR_BYTES] * 4 for key in (
        'gpu_allocated_bytes', 'gpu_reserved_bytes', 'gpu_peak_allocated_bytes')}
    gates.allocator_evidence(dict(metadata=metadata))
    for key in metadata:
        for device in range(4):
            changed = copy.deepcopy(metadata)
            changed[key][device] += 1
            with pytest.raises(ValueError, match='40GiB'):
                gates.allocator_evidence(dict(metadata=changed))
    with pytest.raises(ValueError, match='four GPU'):
        gates.allocator_evidence(dict(metadata={key: [0, 0] for key in metadata}))


def test_fresh_inference_requires_durable_start_and_uncached_transport(tmp_path, saved_case):
    import hashlib
    body, response = saved_case
    raw = request_bytes(body)
    registry = RequestRegistry(tmp_path / 'requests.sqlite3', 'a' * 64)
    try:
        request_id = 'ex083-cpu-fresh'
        registry.accept(request_id, raw, hashlib.sha256(raw).hexdigest(), 'b' * 64)
        transport = dict(cache_reused=False, attempt=1)
        with pytest.raises(ValueError, match='durable journal'):
            gates.verify_fresh_inference(registry.path, request_id, body, response, transport)
        registry.start(request_id)
        registry.finish(request_id, 200, json_bytes(response))
        assert gates.verify_fresh_inference(registry.path, request_id, body, response, transport)['passed']
        with pytest.raises(ValueError, match='new request ID'):
            gates.verify_fresh_inference(registry.path, request_id, body, response, dict(cache_reused=True, attempt=1))
        registry.db.execute("INSERT INTO events(at,kind,request_id,details) VALUES(0,'inference_started',?,'{}')", (request_id,))
        with pytest.raises(ValueError, match='durable journal'):
            gates.verify_fresh_inference(registry.path, request_id, body, response, transport)
    finally:
        registry.close()


@pytest.mark.parametrize('drift', ['none', 'allocated', 'reserved', 'server', 'uuid'])
def test_continuous_gate_checks_same_process_and_repeated_input_memory(tmp_path, monkeypatch, drift):
    from integration.jev27b import resource
    calls = []
    devices = {i: dict(uuid=f'gpu-{i}', memory_used_mib=20000) for i in range(4)}
    request = dict(body={}, decision='stopped', request_id='old-failed')
    shortest = dict(request=dict(body={}, decision='short', request_id='old-short'),
                    response=dict(body=dict(usage=dict(input_tokens=11439))))
    memory = lambda: dict(gpu_allocated_bytes=[10] * 4,
                          gpu_reserved_bytes=[20] * 4, gpu_peak_allocated_bytes=[15] * 4)

    def call(_client, _body, request_id, *_args, **_kwargs):
        calls.append(request_id)
        measured = memory()
        if len(calls) == 5 and drift in ('allocated', 'reserved'):
            measured['gpu_' + drift + '_bytes'][3] += 1
        return dict(request_id=request_id, allocator=measured,
                    response=dict(usage=dict(input_tokens=16604 if 'stopped' in request_id else 11439)))

    def health():
        return dict(server_pid=6 if drift == 'server' else 5, resource=memory())

    def gpu_facts():
        actual = copy.deepcopy(devices)
        if drift == 'uuid':
            actual[3]['uuid'] = 'foreign'
        return actual

    monkeypatch.setattr(gates, 'call_record', call)
    monkeypatch.setattr(resource, 'gpu_facts', gpu_facts)
    operation = lambda: gates.memory_gate(SimpleNamespace(health=health), request, shortest,
        tmp_path / 'memory', tmp_path / 'journal', server_pid=5, expected_gpus=devices)
    if drift == 'none':
        result = operation()
        assert result['passed'] and result['actual_inferences'] == 5
        assert [key.rsplit('memory-', 1)[1] for key in calls] == [
            'stopped-prime', 'short-1', 'stopped-1', 'short-2', 'stopped-2']
    else:
        with pytest.raises((RuntimeError, ValueError)):
            operation()


def test_existing_output_and_parent_overlap_refuse_without_inference(tmp_path, monkeypatch):
    from integration.jev27b import continuation
    monkeypatch.setattr(continuation, 'validate_parent', lambda _: pytest.fail('refuse before parent reads'))
    parent = tmp_path / 'parent'
    parent.mkdir()
    with pytest.raises(ValueError, match='disjoint'):
        controller.execute(parent, parent / 'new')
    existing = tmp_path / 'existing'
    existing.mkdir()
    sentinel = existing / 'evidence.txt'
    sentinel.write_text('original')
    with pytest.raises(FileExistsError, match='cannot resume'):
        controller.execute(parent, existing)
    assert sentinel.read_text() == 'original'


def test_failed_reload_comparison_never_enters_server_or_collection(tmp_path, monkeypatch):
    """The saved reload comparator must reject a single changed native decision."""
    import shutil
    for name in ('reload-a', 'reload-b'):
        target = tmp_path / name
        target.mkdir()
        data = read(EVIDENCE / name / 'result.json')
        data['metadata']['serving_identity'] = 'd' * 64
        if name == 'reload-b':
            action = data['cases'][0]['body']['answers']['action']
            action['choice'] = next(key for key in action['probabilities'] if key != action['choice'])
        (target / 'result.json').write_text(json.dumps(data))
    with pytest.raises(RuntimeError, match='numerical gate failed'):
        gates.compare_reloads(tmp_path)
    assert read(tmp_path / 'reload-comparison.json')['passed'] is False
