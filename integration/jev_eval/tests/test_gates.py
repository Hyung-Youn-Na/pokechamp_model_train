"""Saved cutoff and bounded qualification behavior, using a CPU fake serving journal."""
import copy
from dataclasses import replace
import json
from types import SimpleNamespace

import httpx
import pytest

from integration.jev27b.formatting import format_request
from integration.jev27b.server import LocalService
from integration.jev27b.study import seal
from integration.jev27b.tests.test_transport import FakeModel, IDENTITY
from integration.jev_eval import gates
from integration.jev_eval.client import LocalClient, LocalRequestError
from integration.jev_eval.config import PROTOCOL, experiment, fixed_device_map
from integration.jev_eval.failures import ModelFailure
from integration.jev_eval.storage import file_hash, read, write


def test_archived_gate_uses_exact_actor_row_cutoff_and_own_team(tmp_path):
    write(tmp_path / 'manifest.json', dict(teams={
        'own': {'showdown_team': 'allowed-own-team'},
        'enemy': {'showdown_team': 'private-opponent-answer-set'}}))
    write(tmp_path / 'result.json', dict(outcomes=[dict(username='model', jev_actor='p1',
                                                     teams=['own', 'enemy'])]))
    rows = [dict(type='protocol', username='foreign', sequence=1, protocol='|request|private'),
        dict(type='protocol', username='model', sequence=5,
             protocol='>battle-a\n|turn|2\n|-item|p2a: A|Future Item'),
        dict(type='input', decision='model-1', actor='p1', event_seq=3, commands={'move_1': '/choose move 1'},
             boundary=dict(protocol_event_seq=5, line_index=1), official=dict(consumed=2)),
        dict(type='protocol', username='model', sequence=6, protocol='|win|future')]
    (tmp_path / 'events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    seal(tmp_path)
    case = gates.archived_cases(tmp_path, ['model-1'])['model-1']
    assert case['own_team'] == 'allowed-own-team'
    assert case['prefix'] == [{'event_seq': 5, 'protocol': '>battle-a\n|turn|2'}]
    assert 'private-opponent-answer-set' not in json.dumps(case)
    assert 'Future Item' not in json.dumps(case) and 'future' not in json.dumps(case)
    with pytest.raises(ValueError, match='missing'):
        gates.archived_cases(tmp_path, ['model-missing'])


def fixture_requests(cfg):
    rows = []
    for name, count, length in (
        ('lead-6', 6, 80), ('turn-13', 13, 120), ('forced-switch-5', 5, 90),
        ('long-public-bench', 8, 200), ('memory-short-1', 2, 60),
        ('memory-long-1', 8, 200), ('memory-short-2', 2, 60), ('memory-long-2', 8, 200)):
        body = dict(model=cfg.model_id, state=dict(version=cfg.input_version, fixture_length=length),
            questions={'action': dict(type='choice', instructions='Choose one.',
                criteria={f'action{i}': {'slot': i} for i in range(count)})})
        formatted = format_request(body)
        rows.append(dict(name=name, payload=body, candidate_ids=list(formatted.candidate_ids),
                         input_tokens=length, prompt_sha256=formatted.prompt_sha256))
    return rows


@pytest.mark.parametrize('name', ['EX-086', 'EX-087', 'EX-088', 'EX-089', 'EX-090'])
@pytest.mark.parametrize('drift', [False, True])
def test_one_server_eight_fresh_inferences_and_repeat_gate(tmp_path, monkeypatch, name, drift):
    cfg = replace(experiment(name), run=tmp_path)
    facts_identity = {'fixture': 'public-facts-v6'}
    monkeypatch.setattr(cfg.input_adapter, 'data_identity', lambda: facts_identity)
    if name == 'EX-090':
        from integration.jev_eval import no_damage_verify
        monkeypatch.setattr(no_damage_verify, 'validate_receipt', lambda *_: dict(passed=True))
    rows = fixture_requests(cfg)
    write(tmp_path / 'gates/requests.json', {'requests': rows})
    write(cfg.evidence / 'lengths.json', dict(passed=True, input_data_identity=facts_identity,
                                           requests_sha256=file_hash(tmp_path / 'gates/requests.json')))
    write(cfg.evidence / 'cpu.json', {'passed': True, 'source': {}})

    class Model(FakeModel):
        def metadata(self):
            return dict(super().metadata(), model=cfg.model_id, revision=cfg.revision,
                device_map=fixed_device_map(cfg), serving_config=dict(max_input_tokens=32768,
                    tensor_placement_verified=True, head_dtype='float32', adapter='merged',
                    format=cfg.format_version))

        def evaluate(self, body):
            response = super().evaluate(body)
            response['model'] = cfg.model_id
            response['usage']['input_tokens'] = body['state']['fixture_length']
            response['metadata'] = dict(candidate_ids=list(body['questions']['action']['criteria']),
                format=cfg.format_version,
                prompt_sha256=format_request(body).prompt_sha256, gpu_allocated_bytes=[1] * 4,
                gpu_reserved_bytes=[2] * 4, gpu_peak_allocated_bytes=[3] * 4, elapsed_seconds=1)
            if drift and self.calls == 6:
                values = response['answers']['action']['probabilities']
                values['action0'], values['action1'] = .999, .001
            return response

    model = Model()
    service = LocalService(model, tmp_path / 'serving', model_id=cfg.model_id,
                           revision=cfg.revision, protocol=PROTOCOL)

    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json=service.health())
        status, raw, reused = service.evaluate(request.content,
            request_id=request.headers['X-Request-ID'],
            body_sha256=request.headers['X-Body-SHA256'], expected_identity=IDENTITY)
        return httpx.Response(status, content=raw, headers={
            'X-Request-ID': request.headers['X-Request-ID'],
            'X-Body-SHA256': request.headers['X-Body-SHA256'],
            'X-Serving-Identity': IDENTITY, 'X-Cache-Reused': str(int(reused))})

    client = LocalClient(cfg, expected_identity=IDENTITY, transport=httpx.MockTransport(handler))
    try:
        if drift:
            with pytest.raises(ModelFailure, match='tolerance'):
                gates.qualify(client, {}, config=cfg)
            assert not (cfg.evidence / 'entry-gates.json').exists()
        else:
            receipt = gates.qualify(client, {}, config=cfg)
            assert receipt['server_loads'] == 1 and receipt['inferences'] == 8
            assert receipt['experiment_id'] == name
            assert receipt['repeated_memory_passed']
            assert receipt['input_tokens'] == sum(row['input_tokens'] for row in rows)
        assert model.calls == 8 and model.maximum_active == 1
        assert service.health()['requests'] == {'completed': 8}
        with pytest.raises(ValueError, match='fresh server'):
            gates.qualify(client, {}, config=cfg)
        assert model.calls == 8
    finally:
        client.close()
        service.close()


def test_public_bench_requirement_does_not_accept_active_only_or_unknown():
    body = {'state': {'opponent_team': [dict(active=True, moves=[{'id': 'protect'}]),
        dict(active=False, moves=[], item={'knowledge': 'unknown'}, ability={'knowledge': 'unknown'})]}}
    assert not gates.has_public_bench(body)
    body['state']['opponent_team'][1]['moves'] = 'unknown'
    assert not gates.has_public_bench(body)
    revealed = copy.deepcopy(body)
    revealed['state']['opponent_team'][1]['item'] = {'knowledge': 'confirmed_absent'}
    assert gates.has_public_bench(revealed)
    revealed['state']['opponent_team'][1]['item'] = {'id': 'leftovers', 'name': 'Leftovers'}
    assert gates.has_public_bench(revealed)


def test_failed_preflight_preserves_attempt_without_retry_or_gate_receipt(tmp_path, monkeypatch):
    from integration.pokechamp import jev_v6
    cfg = replace(experiment('EX-086'), run=tmp_path)
    monkeypatch.setattr(jev_v6, 'data_identity', lambda: {})
    write(tmp_path / 'gates/requests.json', {'requests': fixture_requests(cfg)})
    write(cfg.evidence / 'lengths.json', dict(passed=True, input_data_identity={},
        requests_sha256=file_hash(tmp_path / 'gates/requests.json')))
    write(cfg.evidence / 'cpu.json', {'passed': True, 'source': {}})
    attempts = []
    client = SimpleNamespace(last_transport=None, health=lambda: dict(
        device_map=fixed_device_map(cfg), identity=IDENTITY, requests={},
        serving_config=dict(tensor_placement_verified=True, head_dtype='float32', adapter='merged',
                            format=cfg.format_version)))

    def fail(payload, *, request_id, retries):
        attempts.append((request_id, retries))
        client.last_transport = dict(request_id=request_id, type='transport',
                                     category='timeout', attempt=1, status_code=None)
        raise LocalRequestError('timeout', retryable=True)

    client.evaluate = fail
    with pytest.raises(LocalRequestError):
        gates.qualify(client, {}, config=cfg)
    assert attempts == [('ex086-gate-lead-6', 0)]
    assert read(tmp_path / 'gates/lead-6-transport.json')['category'] == 'timeout'
    assert (tmp_path / 'gates/lead-6-request.json').is_file()
    assert not (cfg.evidence / 'entry-gates.json').exists()
