"""CPU admission, wire retry, paired arithmetic and model-local stop boundaries."""
from __future__ import annotations

import asyncio
import copy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.jev_eval import battle, client, config, execute, failures, model, resource, study


@pytest.fixture(params=['EX-088', 'EX-089'])
def cfg(request, tmp_path):
    return replace(config.experiment(request.param), run=tmp_path / request.param,
                   export=tmp_path / (request.param + '-viewer'))


def test_profiles_preserve_legacy_defaults_and_freeze_new_placements():
    from integration.jev27b.model import Jev27BModel, fixed_device_map as old_map
    from integration.jev9b.model import Jev9BModel, fixed_device_map as old9_map
    for name, counts, old in (('EX-086', (14, 18, 18, 14), old_map('ex083')),
                              ('EX-087', (6, 10, 10, 6), old9_map()),
                              ('EX-088', (14, 18, 18, 14), old_map('ex083')),
                              ('EX-089', (6, 10, 10, 6), old9_map()),
                              ('EX-090', (6, 10, 10, 6), old9_map())):
        cfg = config.experiment(name)
        placement = config.fixed_device_map(cfg)
        assert placement == old
        assert tuple(sum(key.startswith('model.layers.') and value == gpu
                         for key, value in placement.items()) for gpu in range(4)) == counts
        assert placement['model.embed_tokens'] == 0
        assert placement['model.norm'] == placement['lm_head'] == 3
        loaded = model.create_model(cfg)
        assert loaded.profile.name == cfg.runtime_name
        assert loaded.model_id == cfg.model_id and loaded.revision == cfg.revision
        assert loaded.format_version == cfg.format_version
        assert loaded.device_map_factory(cfg.runtime_name) == placement
        assert loaded.profile.allocator_bytes == 40 * 1024**3
        assert loaded.profile.gpu_bytes == 44 * 1024**3
        assert loaded.max_tokens == 32768
    assert Jev27BModel(Path('/nonexistent')).profile.name == 'ex082'
    assert Jev9BModel(Path('/nonexistent')).profile.name == 'ex085'
    with pytest.raises(ValueError, match='unknown frozen'):
        config.experiment('EX-085')
    with pytest.raises(ValueError, match='does not support'):
        Jev27BModel(Path('/nonexistent'), profile='ex086')
    unknown = replace(config.experiment('EX-088'), model_id='unknown-model')
    with pytest.raises(ValueError, match='unknown frozen JEV model'):
        model.create_model(unknown)
    with pytest.raises(ValueError, match='unknown frozen JEV model'):
        _ = unknown.format_version


def test_new_loader_classifies_allocator_limit_without_relaxing_it(cfg, monkeypatch):
    from integration.jev27b.model import Jev27BModel, ModelIntegrityError
    loaded = model.create_model(cfg)
    limit = cfg.runtime.allocator_bytes
    monkeypatch.setattr(loaded, '_resource', lambda: dict(gpu_allocated_bytes=[0, 0, 0, limit + 1]))
    with pytest.raises(failures.ModelFailure, match='GPU allocator use exceeded 40 GiB'):
        loaded._check_memory()
    original = Jev27BModel(Path('/nonexistent'), profile='ex083')
    monkeypatch.setattr(original, '_resource', lambda: dict(gpu_allocated_bytes=[0, 0, 0, limit + 1]))
    with pytest.raises(ModelIntegrityError, match='GPU allocator'):
        original._check_memory()
    def corrupt(_self):
        raise ModelIntegrityError('pinned model file mismatch')
    monkeypatch.setattr(Jev27BModel, '_check_memory', corrupt)
    with pytest.raises(ModelIntegrityError, match='file mismatch'):
        loaded._check_memory()


def test_shared_disk_set_includes_both_models_references_environments_and_future_outputs(cfg):
    roots = resource.disk_roots(cfg, extra_roots=(Path('/tmp/ep141-relocated-viewer'),))
    required = [config.ROOT / '.pokechamp-data/jev27b-runtime',
        config.ROOT / '.pokechamp-data/jev9b-runtime', config.ROOT / 'pokechamp/.venv',
        Path('/tmp/ep037/tools'), Path('/root/.cache/ms-playwright'),
        *(config.RUNS / name for name in ('EX-083', 'EX-085', 'EX-086', 'EX-087', 'EX-088', 'EX-089')),
        *(config.ROOT / 'exports/battle_viewers' / name for name in
          ('ex083', 'ex085', 'ex086', 'ex087', 'ex088', 'ex089')),
        *(config.ROOT / 'project_context/exec-plans/evidence' / name for name in ('ep140', 'ep141')),
        Path('/tmp/ep141-relocated-viewer')]
    assert all(any(path.resolve() == root or root in path.resolve().parents for root in roots)
               for path in required)
    assert all(not any(other != path and other in path.parents for other in roots) for path in roots)


def test_complete_choice_wire_order_and_model_are_explicit(cfg):
    body = dict(state={'version': config.VERSION}, questions={'action': dict(type='choice',
        instructions='선택', criteria={'switch:5': {}, 'move:1': {}, 'tera:4': {}})})
    frozen = copy.deepcopy(body)
    encoded = client.request_bytes(body, config=cfg)
    assert json.loads(encoded)['model'] == cfg.model_id
    assert list(json.loads(encoded)['questions']['action']['criteria']) == ['switch:5', 'move:1', 'tera:4']
    assert body == frozen
    with pytest.raises(ValueError, match='unexpected'):
        client.request_bytes(dict(body, model='foreign'), config=cfg)


@pytest.mark.parametrize('count,permanent', [(3, False), (4, False), (1, True)])
def test_session_retries_same_body_and_request_id(cfg, tmp_path, count, permanent):
    attempts, delays = [], []
    class FakeClient:
        def health(self):
            return dict(ready=True, identity='fixture', model=cfg.model_id, revision=cfg.revision)
        def evaluate(self, body, *, request_id, retries):
            attempts.append((copy.deepcopy(body), request_id, retries))
            if len(attempts) <= count:
                raise client.LocalRequestError('timeout', retryable=not permanent)
            return {'answer': 'completed'}
        def close(self):
            pass
    session = battle.Session(tmp_path, config=cfg, expected_identity='fixture',
                             client_factory=lambda **_: FakeClient())
    async def backoff(seconds):
        delays.append(seconds)
    session._backoff = backoff
    payload = dict(state={}, questions={'action': dict(type='choice', instructions='x',
                   criteria={'first': {}, 'second': {}})})
    try:
        if count == 3 and not permanent:
            assert asyncio.run(session.evaluate(payload, decision='one')) == {'answer': 'completed'}
        else:
            with pytest.raises(client.LocalRequestError):
                asyncio.run(session.evaluate(payload, decision='one'))
        assert len(attempts) == (1 if permanent else 4)
        assert all(attempt == attempts[0] for attempt in attempts)
        assert attempts[0][0]['model'] == cfg.model_id
        assert attempts[0][1].startswith(cfg.namespace + '-')
        assert delays == ([] if permanent else [10., 30., 60.])
        ledger = json.loads((tmp_path / 'ledger.json').read_text())
        assert ledger['logical_requests'] == 1 and ledger['requests'] == len(attempts)
    finally:
        asyncio.run(session.close())


@pytest.mark.parametrize('error,scope', [
    (failures.ModelFailure('load'), 'model'),
    (client.LocalRequestError('timeout'), 'model'),
    (client.LocalRequestError('out_of_memory'), 'model'),
    (client.LocalRequestError('input_validation'), 'shared'),
    (client.LocalRequestError('journal_integrity'), 'shared'),
    (client.LocalRequestError('serving_identity'), 'shared'),
    (ValueError('ambiguous public identity'), 'shared'),
    (failures.SharedFailure('audit'), 'shared'),
])
def test_only_known_model_serving_faults_are_isolated(error, scope):
    assert failures.error_record(error)['scope'] == scope


def test_next_model_requires_shared_integrity_and_cleanup_even_for_isolated_failure():
    record = dict(closure={'passed': True}, cleanup_errors=[], shared_integrity_passed=True,
                  error=dict(scope='model', type='ResourceFailure'))
    assert failures.may_continue_other_model(record)
    for changed in (dict(shared_integrity_passed=False), dict(closure={'passed': False}),
                    dict(cleanup_errors=['not released']), dict(error={'scope': 'shared'})):
        assert not failures.may_continue_other_model(dict(record, **changed))
    assert failures.resource_scope([dict(errors=['gpu3_memory_exceeded'])]) == 'model'
    assert failures.resource_scope([dict(errors=['disk_budget_exceeded'])]) == 'shared'
    assert failures.resource_scope([dict(errors=['gpu_identity_changed'])]) == 'shared'


def test_both_new_comparisons_use_only_complete_common_pairs_and_keep_failure_denominators():
    schedule = [dict(slot_id=f'{pair}-{side}', paired_slot_id=pair, jev_actor=side)
                for pair in ('a', 'b') for side in ('p1', 'p2')]
    before = [dict(row, completed=True, audit_passed=True, outcome='player_won') for row in schedule]
    after = [dict(row, completed=True, audit_passed=True, outcome='tied') for row in schedule[:3]]
    after[-1].update(completed=False, outcome='output_failure', error={'type': 'UnusableChoice'})
    for old, new in (('EX-083', 'EX-086'), ('EX-085', 'EX-087'), ('EX-086', 'EX-087'),
                     ('EX-083', 'EX-088'), ('EX-085', 'EX-089'), ('EX-088', 'EX-089')):
        result = study.compare_outcomes(before, after, schedule,
            before_experiment=old, after_experiment=new)
        assert result['before_experiment'] == old and result['after_experiment'] == new
        assert result['common_completed_pairs'] == 1 and result['missing_common_pairs'] == ['b']
        assert result['mean_pair_score_delta'] == -.5
        assert result['after_denominators']['failed'] == result['after_denominators']['unattempted'] == 1
        assert result['after_denominators']['overall']['losses'] == 0


def test_status_does_not_create_outputs_and_prepare_refuses_any_existing_root(cfg, monkeypatch):
    assert execute.status(cfg)['status'] == 'not_prepared'
    assert not cfg.run.exists() and not cfg.export.exists()
    cfg.run.mkdir()
    (cfg.run / 'original').write_text('preserve')
    with pytest.raises(FileExistsError, match='overwrite'):
        execute.prepare(cfg)
    assert (cfg.run / 'original').read_text() == 'preserve'


def test_execution_never_overwrites_or_resumes(cfg):
    cfg.run.mkdir()
    (cfg.run / 'execution.json').write_text('{}')
    with pytest.raises(FileExistsError, match='overwrite or resume'):
        execute.execute(cfg)


def test_stopped_before_execution_completion_also_prevents_old_run_reuse(cfg):
    cfg.evidence.mkdir(parents=True)
    (cfg.evidence / 'completion.json').write_text('{"passed": false}')
    with pytest.raises(FileExistsError, match='overwrite or resume'):
        execute.execute(cfg)


def test_preflight_costs_survive_before_collection_and_detect_ninth_call(cfg):
    import sqlite3
    serving = cfg.run / 'serving/server'
    serving.mkdir(parents=True)
    (serving.parent / 'loaded.json').write_text('{}')
    db = sqlite3.connect(serving / 'requests.sqlite3')
    db.execute('CREATE TABLE events(request_id TEXT,kind TEXT)')
    db.execute('CREATE TABLE requests(request_id TEXT,state TEXT,response_body BLOB)')
    db.executemany('INSERT INTO events VALUES (?,?)', [
        (cfg.namespace + '-gate-lead', 'inference_started'),
        (cfg.namespace + '-gate-long', 'inference_started')])
    body = dict(usage=dict(input_tokens=12, output_tokens=0), metadata=dict(elapsed_seconds=1.5))
    db.execute('INSERT INTO requests VALUES (?,?,?)',
               (cfg.namespace + '-gate-lead', 'completed', json.dumps(body)))
    db.execute('INSERT INTO requests VALUES (?,?,?)',
               (cfg.namespace + '-gate-long', 'failed', None))
    db.commit()
    costs = execute.inference_accounting(cfg, cfg.run / 'collection')
    assert costs['confirmed_server_loads'] == 1
    assert costs['collection_inferences'] == 0 and costs['preflight_inferences'] == 2
    assert costs['preflight_received_usage']['input_tokens'] == 12
    assert costs['preflight_usage_unknown_requests'] == 1
    db.executemany('INSERT INTO events VALUES (?,?)',
                   [(cfg.namespace + f'-gate-extra{i}', 'inference_started') for i in range(7)])
    db.commit()
    with pytest.raises(ValueError, match='eight'):
        execute.inference_accounting(cfg, cfg.run / 'collection')
    db.close()


def test_poststop_accounting_uses_database_with_transport_jsons_and_no_sidecars(cfg, monkeypatch):
    """A real WAL-mode journal and neighboring JSON transport receipts stay distinct."""
    import hashlib
    import sqlite3
    serving = cfg.run / 'serving/server'
    serving.mkdir(parents=True)
    gates = cfg.run / 'gates'
    gates.mkdir()
    collection = cfg.run / 'collection'
    collection.mkdir()
    cfg.evidence.mkdir()
    (cfg.evidence / 'server-process.json').write_text('{}')
    (serving.parent / 'model-loaded.json').write_text('{}')
    lead, long, decision = (cfg.namespace + '-' + suffix for suffix in
                            ('gate-lead', 'gate-long', 'collection-one'))
    database_path = serving / 'requests.sqlite3'
    with sqlite3.connect(database_path) as db:
        assert db.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
        db.execute('CREATE TABLE events(request_id TEXT,kind TEXT)')
        db.execute('CREATE TABLE requests(request_id TEXT,state TEXT,response_body BLOB)')
        db.executemany('INSERT INTO events VALUES (?,?)',
                       [(key, 'inference_started') for key in (lead, long, decision)])
        response = dict(usage=dict(input_tokens=17, output_tokens=0),
                        metadata=dict(elapsed_seconds=2.5, gpu_peak_allocated_bytes=[4] * 4,
                                      gpu_reserved_bytes=[5] * 4))
        db.executemany('INSERT INTO requests VALUES (?,?,?)', [
            (lead, 'completed', json.dumps(response)), (long, 'failed', None),
            (decision, 'completed', json.dumps(response))])
    db.close()
    (collection / 'events.jsonl').write_text(json.dumps(dict(type='transport', request_id=decision)) + '\n')
    for name, request_id, status in [('lead', lead, 200), ('long', long, None)]:
        (gates / (name + '-transport.json')).write_text(json.dumps(dict(
            type='transport', request_id=request_id, status_code=status)))
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in serving.iterdir()}
    assert set(before) == {'requests.sqlite3'}
    costs = execute.inference_accounting(cfg, collection)
    assert costs['collection_inferences'] == 1 and costs['preflight_inferences'] == 2
    assert costs['total_server_inferences'] == 3 and costs['requests_not_accepted'] == 0
    assert costs['preflight_http_attempts'] == 2 and costs['preflight_http_responses'] == 1
    assert costs['preflight_http_no_response'] == 1 and costs['preflight_http_errors'] == 0
    assert costs['preflight_received_usage']['input_tokens'] == 17
    assert costs['preflight_usage_unknown_requests'] == 1
    assert costs['preflight_inference_seconds'] == 2.5
    monkeypatch.setattr(resource, 'disk_bytes', lambda *_a, **_k: 0)
    measured = execute.resource_summary(cfg)
    assert measured['allocator_peak_bytes'] == 4 and measured['reserved_peak_bytes'] == 5
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in serving.iterdir()}
    assert after == before


def test_terminal_print_precedes_final_seal(cfg, monkeypatch):
    from contextlib import redirect_stdout
    cfg.evidence.mkdir(parents=True)
    monkeypatch.setattr(execute, 'report', lambda *_: (cfg.run / 'report.md').write_text('완료\n'))
    completion = dict(passed=True, error=None, result=dict(completed=32))
    with (cfg.run / 'controller.log').open('w') as output, redirect_stdout(output):
        execute.finish_completion(cfg, completion)
    assert json.loads((cfg.run / 'controller.log').read_text())['completed'] == 32
    assert 'controller.log' in study.verify_seal(cfg.run)


def test_source_identity_includes_new_viewer_and_reused_executed_assets():
    sources = study.source_identity()
    assert 'scripts/jev-eval' in sources
    assert 'integration/jev_eval/turn_logs.py' in sources
    assert 'integration/jev_eval/viewer.py' in sources
    assert 'integration/pokechamp/viewer_assets/action-labels.js' in sources
    assert any(name.startswith('integration/jev_eval/') and name.endswith('.html') for name in sources)
    assert any(name.startswith('integration/jev_eval/') and name.endswith('.js') for name in sources)


@pytest.mark.parametrize('technical', [failures.ModelFailure('model exited'),
                                       failures.SharedFailure('public identity ambiguous')])
def test_runner_isolates_illegal_choice_then_stops_at_technical_failure(cfg, monkeypatch, technical):
    from integration.jev_eval import audit
    from integration.pokechamp import cli, parallel_server, benchmark, jev_battle as j
    monkeypatch.chdir(battle.ROOT / 'pokechamp')
    # Resolve the real actor's dependency graph before replacing subprocess in
    # this CPU-only lifecycle fixture (some dependencies annotate Popen[T]).
    from poke_env.ps_client.account_configuration import AccountConfiguration
    assert AccountConfiguration is not None
    baseline, _ = study.load_baseline()
    manifest = dict(baseline, experiment_id=cfg.experiment, source={})
    output = cfg.run / 'collection'
    monkeypatch.setattr(study, 'prepare_manifest', lambda *_a, **_k: manifest)
    monkeypatch.setattr(study, 'verify_live_identity', lambda *_a: None)
    monkeypatch.setattr(study, 'snapshot_sources', lambda *_a: None)
    audits = []
    def audit_once(*_args, **kwargs):
        audits.append(kwargs['result']['outcomes'][0]['slot_id'])
        return dict(passed=True, errors=[])
    monkeypatch.setattr(audit, 'audit', audit_once)
    monkeypatch.setattr(audit, 'final_check', lambda *_a, **_k: dict(passed=True, errors=[]))

    class Session:
        def __init__(self, directory, **_kwargs):
            self.directory, self.records = directory, []
            self.calls, self.started, self.monotonic_started = 0, None, None
            self.failure_event = asyncio.Event()
        def record(self, event):
            self.records.append(event)
            with (self.directory / 'events.jsonl').open('a') as stream:
                stream.write(json.dumps(event) + '\n')
        def fail(self, error):
            self.failure_event.set()
        async def health(self):
            return {}
        async def close(self):
            return
        async def wait_decisions(self):
            return
    class Process:
        pid = 1
        returncode = None
        def poll(self):
            return self.returncode
    class Server:
        def __init__(self, *_args):
            self.created = False
            self.process = Process()
        def start(self):
            self.created = True
        def close(self):
            self.created = False
            self.process.returncode = 0
    class Player:
        official = None
        def __init__(self, **_kwargs):
            pass
    admitted, adapters = [], []
    async def play(_player, _role, _names, attempt, **_kwargs):
        admitted.append(json.loads((attempt / 'request.json').read_text())['slot']['slot_id'])
        if len(admitted) == 1:
            raise j.UnusableChoice('illegal model candidate')
        raise technical
    def player_class(**kwargs):
        adapters.append(kwargs['input_adapter'].VERSION)
        return Player
    async def close_players(_players):
        return
    monkeypatch.setattr(battle, 'Session', Session)
    monkeypatch.setattr(battle, 'player_class', player_class)
    monkeypatch.setattr(battle, 'play_owned', play)
    monkeypatch.setattr(parallel_server, 'BattleServer', Server)
    monkeypatch.setattr(battle.subprocess, 'Popen', lambda *_a, **_k: Process())
    monkeypatch.setattr(benchmark, 'terminate', lambda p: setattr(p, 'returncode', 0))
    monkeypatch.setattr(cli, '_close_players', close_players)
    result = asyncio.run(battle.run(output, config=cfg, expected_identity='fixture', gate_receipt={}))
    assert admitted == [row['slot_id'] for row in baseline['schedule'][:2]] == audits
    assert adapters == [config.VERSION, config.VERSION]
    assert result['attempted'] == result['failed'] == 2 and result['unattempted'] == 30
    assert result['outcomes'][0]['failure_scope'] == 'battle'
    assert result['outcomes'][1]['failure_scope'] == 'collection'
    assert result['actual_losses'] == result['completed_pairs'] == 0
    assert result['error']['scope'] == failures.error_record(technical)['scope']


def test_controller_retains_saved_denominator_after_interrupt(cfg, monkeypatch):
    from contextlib import nullcontext
    from integration.jev_eval import gates
    import httpx
    cfg.evidence.mkdir(parents=True)
    partial = dict(passed=False, planned=32, attempted=2, completed=1, failed=1,
                   invalid=0, unattempted=30, final_audit_passed=True)
    monkeypatch.setattr(execute, 'verify_preparation', lambda *_: dict(source={}))
    monkeypatch.setattr(execute, 'require_previous_experiment', lambda *_: None)
    monkeypatch.setattr(execute, 'check_disk', lambda *_: {})
    monkeypatch.setattr(execute.signal, 'signal', lambda *_: None)
    monkeypatch.setattr(execute, 'closure', lambda: dict(passed=True))
    monkeypatch.setattr(execute, 'resource_summary', lambda *_: {})
    monkeypatch.setattr(execute, 'inference_accounting', lambda *_: {})
    monkeypatch.setattr(execute, 'finalize', lambda *_a, **_k: dict(passed=True))
    monkeypatch.setattr(execute, 'finish_completion', lambda *_: None)
    monkeypatch.setattr(resource, 'ResourceMonitor', lambda *_a, **_k: nullcontext())
    monkeypatch.setattr(client, 'LocalClient', lambda *_: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(execute.subprocess, 'Popen',
                        lambda *_a, **_k: SimpleNamespace(pid=123, poll=lambda: None))
    monkeypatch.setattr(execute, 'stop_owned_process', lambda *_: None)
    monkeypatch.setattr(httpx, 'get', lambda *_a, **_k: SimpleNamespace(status_code=200))
    monkeypatch.setattr(gates, 'qualify', lambda *_a, **_k: dict(serving_identity='fixture'))
    def interrupted(coroutine):
        coroutine.close()
        (cfg.run / 'collection').mkdir()
        (cfg.run / 'collection/result.json').write_text(json.dumps(partial))
        raise KeyboardInterrupt('fixture cancellation')
    monkeypatch.setattr(execute.asyncio, 'run', interrupted)
    completion = execute.execute(cfg)
    assert not completion['passed']
    assert completion['result'] == partial
    assert completion['error']['type'] == 'KeyboardInterrupt'
    assert completion['error']['scope'] == 'shared'
