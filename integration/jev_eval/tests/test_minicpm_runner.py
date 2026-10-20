"""EX-091 runner boundaries with CPU fixtures and durable fake-serving records."""
from contextlib import nullcontext
import copy
from dataclasses import replace
import json
from types import SimpleNamespace

import httpx
import pytest

from integration.jev27b.server import LocalService
from integration.jev27b.tests.test_transport import FakeModel, IDENTITY
from integration.jev_eval import audit, client, config, execute, gates, model, resource, study
from integration.jev_eval.failures import ModelFailure, SharedFailure
from integration.jev_eval.storage import digest, file_hash, read, write


@pytest.fixture
def cfg(tmp_path):
    return replace(config.experiment('EX-091'), run=tmp_path / 'run',
                   export=tmp_path / 'viewer', model_dir=tmp_path / 'model')


def requests(cfg):
    rows = []
    for name, count, length in (
        ('lead-6', 6, 80), ('turn-13', 13, 120), ('forced-switch-5', 5, 90),
        ('longest-input', 8, 200), ('memory-short-1', 2, 60),
        ('memory-long-1', 8, 200), ('memory-short-2', 2, 60), ('memory-long-2', 8, 200)):
        body = dict(model=cfg.model_id, state=dict(version=cfg.input_version, fixture_length=length),
            questions={'action': dict(type='choice', instructions='선택\n기준 유지',
                criteria={f'action{i}': {'slot': i} for i in range(count)})})
        formatted = cfg.formatter.format_request(body)
        rows.append(dict(name=name, payload=body, candidate_ids=list(formatted.candidate_ids),
            input_tokens=length, prompt_sha256=formatted.prompt_sha256,
            input_ids_sha256=digest(list(range(length))),
            baseline_encoding=dict(input_tokens=length, prompt_sha256=formatted.prompt_sha256,
                                   input_ids_sha256=digest(list(range(length))))))
    return rows


def test_minicpm_single_cohort_has_no_predecessor_or_calculator_preparation(cfg, monkeypatch):
    monkeypatch.setattr(study, 'sealed_document', lambda *_: pytest.fail('unexpected predecessor'))
    execute.require_previous_experiment(cfg)
    assert study.prior_execution(cfg) is None
    assert study.cross_comparison(cfg, {}, {})['applicable'] is False
    monkeypatch.setattr(cfg.input_adapter, 'Adapter', lambda *_: pytest.fail('baseline recalculation'))
    receipt = gates.regenerate_requests(cfg)
    assert receipt['deferred'] and receipt['baseline_recalculations'] == 0
    assert not cfg.run.exists()


def test_unlimited_disk_still_counts_usage_and_propagates_real_io_failure(cfg, monkeypatch):
    measured = 400 * 1024**3
    monkeypatch.setattr(resource, 'disk_bytes', lambda *_: measured)
    monkeypatch.setattr(resource, 'disk_roots', lambda *_: (cfg.model_dir, cfg.run, cfg.export))
    receipt = execute.check_disk(cfg)
    assert receipt == dict(bytes=measured, limit_bytes=None,
                           roots=[str(p) for p in (cfg.model_dir, cfg.run, cfg.export)])
    with pytest.raises(SharedFailure, match='disk budget'):
        execute.check_disk('EX-090')
    def io_error(*_):
        raise OSError('fixture I/O error')
    monkeypatch.setattr(resource, 'disk_bytes', io_error)
    with pytest.raises(OSError, match='I/O'):
        execute.check_disk(cfg)


def test_closure_uses_only_gpu0_its_lock_and_two_ports(cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(execute, 'ROOT', tmp_path)
    facts = {index: dict(uuid=f'gpu-{index}', memory_used_mib=0 if index == 0 else 9000)
             for index in range(4)}
    monkeypatch.setattr(resource, 'gpu_facts', lambda: facts)
    monkeypatch.setattr(resource, 'gpu_compute_processes', lambda: [dict(uuid='gpu-1', pid=42)])
    bound = []
    class Socket:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return None
        def setsockopt(self, *_):
            return None
        def bind(self, address):
            bound.append(address[1])
    monkeypatch.setattr(execute.socket, 'socket', lambda: Socket())
    receipt = execute.closure(cfg)
    assert receipt['passed'] and set(receipt['gpus']) == {0}
    assert receipt['gpu_locks_released'] == {0: True}
    assert set(bound) == {8109, 18791}
    assert [p.name for p in (tmp_path / '.pokechamp-data/locks').iterdir()] == ['gpu0.lock']
    bound.clear()
    assert not execute.closure()['passed']
    assert 18791 not in bound
    assert {18786, 18787, 18788, 18789, 18790, 8109} == set(bound)


@pytest.mark.parametrize('token_drift', [False, True])
def test_cpu_ready_selects_saved_inputs_and_encodes_with_profile_formatter(cfg, monkeypatch, token_drift):
    from integration.minicpm5_jev import verify
    tokenizer = object()
    expected = requests(cfg)
    selected = []
    sources = {'fixture': 'source'}
    ready = dict(passed=True, head_shape=[255, 2048], head_dtype='torch.float32',
                 backbone_loaded=False, cuda_initialized=False, gpu_inferences=0)
    monkeypatch.setattr(model, 'create_model', lambda _: SimpleNamespace(cpu_ready=lambda: (ready, tokenizer)))
    monkeypatch.setattr(study, 'source_identity', lambda: sources)
    def verify_saved(chosen, identity, tok):
        selected.append((chosen, identity, tok))
        write(cfg.run / 'gates/requests-unencoded.json', dict(experiment_id=cfg.experiment,
            requests=expected, input_data_identity={'frozen': 'input'}, max_inferences=8))
        return dict(passed=True, checked_inputs=1139)
    monkeypatch.setattr(verify, 'verify_baseline', verify_saved)
    calls = []
    def tokenize(tok, formatted):
        assert tok is tokenizer
        calls.append(formatted.prompt_sha256)
        ids = list(range(json.loads(formatted.state_text)['fixture_length']))
        return dict(input_ids=list(reversed(ids)) if token_drift else ids)
    monkeypatch.setattr(cfg.formatter, 'tokenize_request', tokenize)
    cfg.tokenizer_dir.mkdir(parents=True)
    (cfg.tokenizer_dir / 'tokenizer.json').write_text('fixture')
    if token_drift:
        with pytest.raises(ValueError, match='complete saved-input census'):
            gates.prepare_requests(cfg)
        assert not (cfg.run / 'gates/requests.json').exists()
        return
    receipt = gates.prepare_requests(cfg)
    assert selected == [(cfg, sources, tokenizer)] and len(calls) == 8
    assert read(cfg.evidence / 'model-ready.json') == ready
    assert receipt['format'] == cfg.format_version
    assert receipt['tokenizer_sha256'] == file_hash(cfg.tokenizer_dir / 'tokenizer.json')
    encoded = read(cfg.run / 'gates/requests.json')['requests']
    assert [row['input_ids_sha256'] for row in encoded] == [row['input_ids_sha256'] for row in expected]
    assert encoded[4]['input_tokens'] < encoded[5]['input_tokens']


@pytest.mark.parametrize('corruption', [None, 'token_ids', 'gpu_count', 'reserved_growth', 'merged'])
def test_one_gpu_eight_gate_inferences_and_exact_token_stream(cfg, monkeypatch, corruption):
    from integration.minicpm5_jev import verify
    monkeypatch.setattr(verify, 'validate_receipt', lambda *_: dict(passed=True))
    facts = {'fixture': 'facts'}
    monkeypatch.setattr(cfg.input_adapter, 'data_identity', lambda: facts)
    rows = requests(cfg)
    write(cfg.run / 'gates/requests.json', dict(requests=rows))
    write(cfg.evidence / 'lengths.json', dict(passed=True, input_data_identity=facts,
        requests_sha256=file_hash(cfg.run / 'gates/requests.json')))
    write(cfg.evidence / 'cpu.json', dict(passed=True, source={}))
    class Model(FakeModel):
        def metadata(self):
            return dict(super().metadata(), model=cfg.model_id, revision=cfg.revision,
                device_map=config.fixed_device_map(cfg), serving_config=dict(max_input_tokens=32768,
                    tensor_placement_verified=True, head_dtype='float32',
                    adapter='merged' if corruption == 'merged' else 'unmerged', format=cfg.format_version))
        def evaluate(self, body):
            response = super().evaluate(body)
            length = body['state']['fixture_length']
            response['model'] = cfg.model_id
            response['usage']['input_tokens'] = length
            response['metadata'] = dict(candidate_ids=list(body['questions']['action']['criteria']),
                format=cfg.format_version, prompt_sha256=cfg.formatter.format_request(body).prompt_sha256,
                input_ids_sha256='changed' if corruption == 'token_ids' else digest(list(range(length))),
                gpu_allocated_bytes=[1] * (4 if corruption == 'gpu_count' else 1),
                gpu_reserved_bytes=[3 if corruption == 'reserved_growth' and self.calls == 8 else 2],
                gpu_peak_allocated_bytes=[3], elapsed_seconds=1)
            return response
    loaded = Model()
    service = LocalService(loaded, cfg.run / 'serving', model_id=cfg.model_id,
                           revision=cfg.revision, protocol=config.PROTOCOL)
    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json=service.health())
        status, raw, reused = service.evaluate(request.content,
            request_id=request.headers['X-Request-ID'], body_sha256=request.headers['X-Body-SHA256'],
            expected_identity=IDENTITY)
        return httpx.Response(status, content=raw, headers={
            'X-Request-ID': request.headers['X-Request-ID'],
            'X-Body-SHA256': request.headers['X-Body-SHA256'],
            'X-Serving-Identity': IDENTITY, 'X-Cache-Reused': str(int(reused))})
    caller = client.LocalClient(cfg, expected_identity=IDENTITY, transport=httpx.MockTransport(handler))
    try:
        if corruption is None:
            receipt = gates.qualify(caller, {}, config=cfg)
            assert receipt['inferences'] == 8 and receipt['server_loads'] == 1
            assert receipt['physical_gpus'] == [0] and receipt['format'] == cfg.format_version
            assert loaded.calls == 8 and loaded.maximum_active == 1
            with pytest.raises(ValueError, match='fresh server'):
                gates.qualify(caller, {}, config=cfg)
            assert loaded.calls == 8
        else:
            expected_error = ModelFailure if corruption == 'reserved_growth' else ValueError
            with pytest.raises(expected_error):
                gates.qualify(caller, {}, config=cfg)
            assert loaded.calls == {'merged': 0, 'reserved_growth': 8}.get(corruption, 1)
            assert not (cfg.evidence / 'entry-gates.json').exists()
    finally:
        caller.close()
        service.close()


def test_audit_checks_actual_minicpm_token_ids_and_usage(cfg, monkeypatch):
    row = requests(cfg)[0]
    token = object()
    ids = list(range(row['input_tokens']))
    monkeypatch.setattr(cfg.formatter, 'tokenize_request', lambda tok, _: dict(input_ids=ids))
    response = dict(metadata={k: row[k] for k in ('candidate_ids', 'prompt_sha256', 'input_ids_sha256')},
                    usage=dict(input_tokens=len(ids)))
    response['metadata']['format'] = cfg.format_version
    assert audit.response_format_evidence(cfg, row['payload'], response, tokenizer=token) is token
    for changed in ('input_ids_sha256', 'input_tokens'):
        corrupt = copy.deepcopy(response)
        target = corrupt['usage' if changed == 'input_tokens' else 'metadata']
        target[changed] = -1
        with pytest.raises(ValueError, match='token IDs or input usage'):
            audit.response_format_evidence(cfg, row['payload'], corrupt, tokenizer=token)


def test_preparation_and_manifest_link_complete_saved_input_receipt(cfg, monkeypatch):
    from integration.minicpm5_jev import verify
    sources = {'fixture': 'source'}
    validations = []
    def validate(selected, actual):
        validations.append((selected.experiment, actual))
        return dict(passed=True, checked_inputs=1139)
    monkeypatch.setattr(verify, 'validate_receipt', validate)
    monkeypatch.setattr(verify, 'validate_actor_receipt', validate)
    monkeypatch.setattr(study, 'source_identity', lambda: sources)
    cfg.tokenizer_dir.mkdir(parents=True)
    (cfg.tokenizer_dir / 'tokenizer.json').write_text('fixture')
    for name in ('model-ready.json', 'cpu.json', 'minicpm-baseline.json', 'minicpm-actor-tokenization.json'):
        write(cfg.evidence / name, dict(passed=True, source=sources))
    write(cfg.run / 'gates/requests.json', {})
    write(cfg.evidence / 'lengths.json', dict(passed=True, format=cfg.format_version,
        requests_sha256=file_hash(cfg.run / 'gates/requests.json'),
        tokenizer_sha256=file_hash(cfg.tokenizer_dir / 'tokenizer.json')))
    write(cfg.evidence / 'prepared.json', dict(passed=True, experiment_id=cfg.experiment, source=sources,
        baseline_verification=dict(path='evidence/minicpm-baseline.json', checked_inputs=1139,
            sha256=file_hash(cfg.evidence / 'minicpm-baseline.json')),
        actor_tokenization_verification=dict(path='evidence/minicpm-actor-tokenization.json',
            checked_inputs=1139, sha256=file_hash(cfg.evidence / 'minicpm-actor-tokenization.json'))))
    execute.verify_preparation(cfg)
    journal = cfg.run / 'journal.sqlite3'
    journal.touch()
    gate = dict(passed=True, experiment_id=cfg.experiment, serving_identity=IDENTITY, source=sources,
        inferences=8, server_loads=1, input_data_identity=cfg.input_adapter.data_identity(),
        server_journal=str(journal), format=cfg.format_version, physical_gpus=[0])
    manifest = study.prepare_manifest(cfg, IDENTITY, gate, endpoint=cfg.endpoint)
    assert validations == [(cfg.experiment, sources)] * 2
    assert manifest['baseline_input_verification']['checked_inputs'] == 1139
    assert manifest['resource_limits']['physical_gpus'] == [0]
    assert manifest['resource_limits']['disk_bytes'] is None
    assert manifest['model_package_comparison']['format'] == cfg.format_version
    assert manifest['damage_predictions_enabled'] and manifest['speed_comparison_retained']
    assert '공개 정보 보존과 현재 상태 교정의 결합 처치' not in manifest['interpretation']
    (cfg.tokenizer_dir / 'tokenizer.json').write_text('changed')
    with pytest.raises(SharedFailure, match='baseline/tokenizer'):
        execute.verify_preparation(cfg)


def test_single_gpu_resource_summary_retains_phase_costs_and_unlimited_disk(cfg, monkeypatch):
    import sqlite3
    cfg.evidence.mkdir(parents=True)
    write(cfg.evidence / 'entry-gates.json', dict(at=2))
    samples = [dict(at=1, rss_bytes=10, disk_bytes=100, errors=[], gpus={'0': {'memory_used_mib': 11}}),
               dict(at=3, rss_bytes=20, disk_bytes=200, errors=[], gpus={'0': {'memory_used_mib': 22}})]
    (cfg.evidence / 'resources-fixture.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in samples))
    directory = cfg.run / 'serving/server'
    directory.mkdir(parents=True)
    with sqlite3.connect(directory / 'requests.sqlite3') as db:
        db.execute('CREATE TABLE requests(request_id TEXT, state TEXT, response_body TEXT)')
        for key, memory in (('ex091-gate-lead', 30), ('ex091-decision-one', 40)):
            response = dict(metadata=dict(gpu_peak_allocated_bytes=[memory], gpu_reserved_bytes=[memory + 1]))
            db.execute('INSERT INTO requests VALUES (?, ?, ?)', (key, 'completed', json.dumps(response)))
    monkeypatch.setattr(resource, 'disk_bytes', lambda *_: 300)
    measured = execute.resource_summary(cfg)
    assert measured['gpu_max_mib'] == {'0': 22}
    assert measured['disk_limit_bytes'] is None and measured['final_disk_bytes'] == 300
    assert measured['phases']['preflight']['gpu_max_mib'] == {'0': 11}
    assert measured['phases']['collection_and_finalization']['allocator_peak_bytes'] == 40
    assert measured['phases']['preflight']['allocator_peak_bytes'] == 30


def test_minicpm_pair_score_uses_only_common_valid_pairs_and_package_interpretation():
    schedule = [dict(slot_id=f'{pair}-{side}', paired_slot_id=pair, jev_actor=side)
                for pair in ('valid', 'failed') for side in ('p1', 'p2')]
    before = [dict(row, completed=True, audit_passed=True, outcome='player_lost') for row in schedule]
    after = [dict(row, completed=True, audit_passed=True, outcome='tied') for row in schedule]
    after[-1].update(completed=False, outcome='output_failure', error={'type': 'UnusableChoice'})
    compared = study.compare_outcomes(before, after, schedule,
                                     before_experiment='EX-089', after_experiment='EX-091')
    assert compared['common_completed_pairs'] == 1 and compared['mean_pair_score_delta'] == .5
    assert compared['pair_changes'] == dict(improved=1, worsened=0, unchanged=0)
    assert compared['after_denominators']['failed'] == 1
    assert compared['after_denominators']['overall']['losses'] == 0
    assert compared['treatment'] == 'model_package_with_lossless_minicpm_format'
    assert '모델 패키지' in compared['interpretation']


@pytest.mark.parametrize('interrupted', [False, True])
def test_collection_ended_stage_precedes_cleanup_and_requires_no_alarm(cfg, monkeypatch, interrupted):
    cfg.evidence.mkdir(parents=True)
    result = dict(passed=False, error=None, final_audit_passed=True, completed=0)
    order = []
    monkeypatch.setattr(execute, 'verify_preparation', lambda *_: dict(source={}))
    monkeypatch.setattr(execute, 'require_previous_experiment', lambda *_: None)
    monkeypatch.setattr(execute, 'check_disk', lambda *_: {})
    monkeypatch.setattr(execute.signal, 'signal', lambda *_: None)
    monkeypatch.setattr(execute, 'closure', lambda selected: dict(passed=selected == cfg))
    monkeypatch.setattr(execute, 'resource_summary', lambda *_: {})
    monkeypatch.setattr(execute, 'inference_accounting', lambda *_: {})
    monkeypatch.setattr(resource, 'ResourceMonitor', lambda *_a, **_k: nullcontext())
    monkeypatch.setattr(client, 'LocalClient', lambda *_: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(execute.subprocess, 'Popen',
                        lambda *_a, **_k: SimpleNamespace(pid=123, poll=lambda: None))
    def stopped(*_):
        stage = read(cfg.evidence / 'collection-ended.json')
        assert stage['returned'] is not interrupted and stage['result_available']
        assert bool(stage['error']) is interrupted
        assert 'completed' not in stage
        order.append('cleanup')
    monkeypatch.setattr(execute, 'stop_owned_process', stopped)
    monkeypatch.setattr(httpx, 'get', lambda *_a, **_k: SimpleNamespace(status_code=200))
    monkeypatch.setattr(gates, 'qualify', lambda *_a, **_k: dict(serving_identity=IDENTITY))
    def run(coroutine):
        coroutine.close()
        write(cfg.run / 'collection/result.json', result)
        if interrupted:
            raise KeyboardInterrupt('fixture interrupted collection')
        return result
    monkeypatch.setattr(execute.asyncio, 'run', run)
    monkeypatch.setattr(execute, 'finalize', lambda *_a, **_k: order.append('finalize') or dict(passed=True))
    monkeypatch.setattr(execute, 'finish_completion', lambda *_: order.append('completion'))
    completion = execute.execute(cfg)
    assert order == ['cleanup', 'finalize', 'completion']
    assert (completion['error'] or {}).get('type') == ('KeyboardInterrupt' if interrupted else None)


def test_cost_comparison_reuses_saved_ex089_costs_and_seals_after_completion(cfg, monkeypatch):
    baseline = dict(result=dict(input_tokens=[200], decisions=1),
                    inference_accounting=dict(preflight_inferences=8), resources={'gpus': 'baseline'})
    calls = []
    monkeypatch.setattr(study, 'sealed_document', lambda path, name: calls.append((path, name)) or baseline)
    monkeypatch.setattr(execute, 'report', lambda *_: None)
    def seal(path):
        assert read(path / 'evidence/completion.json')['cost_comparison']['before_experiment'] == 'EX-089'
        calls.append('sealed')
    monkeypatch.setattr(study, 'seal', seal)
    completion = dict(passed=False, error=None, result=dict(input_tokens=[100], decisions=2, completed=0),
        inference_accounting=dict(preflight_inferences=8), resources={'gpus': 'new'})
    execute.finish_completion(cfg, completion)
    assert calls == [(config.experiment('EX-089').run, 'evidence/completion.json'), 'sealed']
    costs = read(cfg.evidence / 'cost-comparison.json')
    assert costs['before']['collection']['input_tokens']['total'] == 200
    assert costs['after']['collection']['input_tokens']['total'] == 100
    assert costs['before']['inference_accounting']['preflight_inferences'] == 8

