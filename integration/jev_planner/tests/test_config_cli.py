"""Frozen config axes, no-call preparation, mock CLI and whole-run budgets."""
import json

import pytest

from integration.jev_planner import config, execute, storage


def source_config(tmp_path, **changes):
    base = config.read_json(config.HERE / 'examples/default.json')
    base['prompts'] = {key: str((config.HERE / 'examples' / value).resolve())
                       for key, value in base['prompts'].items()}
    base['evaluation']['fixture'] = str(config.HERE / 'fixtures/demo.json')
    base.update(changes)
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(base))
    return path


@pytest.fixture
def small_snapshot(monkeypatch):
    path = 'integration/jev_planner/__init__.py'
    monkeypatch.setattr(execute, 'source_identity', lambda: {path: storage.file_hash(config.ROOT / path)})


def test_defaults_preserve_model_packages_and_resolve_prompts():
    cfg = config.load_config(config.HERE / 'examples/default.json')
    assert cfg['executor'] == dict(model='jev9b', input_version='jev-choice-v6', candidate_display='names-v1')
    assert cfg['trigger']['policy'] == 'events_or_periodic'
    assert cfg['trigger']['interval_turns'] == 3
    assert cfg['planner']['max_tokens'] == 8192
    assert cfg['planner']['transport']['retry_delays_seconds'] == [1., 2., 4.]
    assert cfg['prompts']['planner']['text'] and cfg['prompts']['executor']['text']
    for name in config.MODEL_EXPERIMENTS:
        spec = config.model_spec(name)
        assert spec['input_tokens'] == 32768 and spec['revision']
        assert config.formatter(name).MAX_OPTIONS == 16


def test_matrix_keeps_exactly_one_off_and_independent_axes():
    cfg = config.load_config(config.HERE / 'examples/matrix.json')
    items = config.conditions(cfg)
    assert len(items) == 11
    assert sum(item['config']['trigger']['policy'] == 'off' for item in items) == 1
    assert len({item['name'] for item in items}) == 11
    assert len({item['config']['prompts']['planner']['text'] for item in items}) == 2
    assert all('matrix' not in item['config'] for item in items)


@pytest.mark.parametrize('model', ['glm-5.3-flash', 'glm-5.3'])
def test_explicit_planner_model_preserves_options_and_default(tmp_path, model):
    cfg = config.load_config(source_config(tmp_path, planner=dict(
        model=model, reasoning_effort='low', temperature=0, max_tokens=131072)))
    assert cfg['planner']['model'] == model
    assert cfg['planner']['reasoning_effort'] == 'low'
    assert cfg['planner']['temperature'] == 0
    assert cfg['planner']['max_tokens'] == 131072
    assert config.DEFAULT_PLANNER['model'] == 'glm-5.3-flash'


@pytest.mark.parametrize('planner', [dict(model='glm-unknown'), dict(provider='other', model='glm-5.3')])
def test_unsupported_planner_model_or_provider_rejected(tmp_path, planner):
    with pytest.raises(config.ConfigurationError, match='planner requires zai'):
        config.load_config(source_config(tmp_path, planner=planner))


@pytest.mark.parametrize('changed', [dict(trigger={'policy': 'typo'}),
    dict(trigger={'interval_turns': 0}), dict(trigger={'events': ['faint', 'faint']}),
    dict(planner={'thinking': {'type': 'disabled'}}), dict(planner={'reasoning_effort': 'medium'}),
    dict(planner={'max_tokens': 131073}), dict(executor={'model': 'unknown'}),
    dict(planner={'api_key': 'must-not-be-in-config'})])
def test_invalid_settings_rejected_before_execution(tmp_path, changed):
    with pytest.raises(config.ConfigurationError):
        config.load_config(source_config(tmp_path, **changed))


def test_duplicate_json_keys_and_nonfinite_values_rejected(tmp_path):
    path = tmp_path / 'invalid.json'
    path.write_text('{"name":"one", "name":"two"}')
    with pytest.raises(config.ConfigurationError, match='duplicate'):
        config.load_config(path)
    path.write_text('{"planner":{"temperature":NaN}}')
    with pytest.raises(config.ConfigurationError, match='non-finite'):
        config.load_config(path)


def test_prepare_needs_no_credentials_and_keeps_snapshots_after_prompt_edit(tmp_path, small_snapshot, monkeypatch):
    from integration.jev_planner.planner import ZaiPlannerClient
    monkeypatch.setattr(ZaiPlannerClient, 'from_env', lambda *_a, **_kw: pytest.fail('no credentials in prepare'))
    prompt = tmp_path / 'prompt.txt'
    prompt.write_text('Original strategy prompt')
    path = source_config(tmp_path, prompts={'planner': str(prompt),
        'executor': str(config.HERE / 'prompts/executor-guidance.txt')})
    output = tmp_path / 'frozen'
    prepared = execute.prepare(path, output)
    assert prepared['api_requests'] == prepared['gpu_inferences'] == 0
    prompt.write_text('A new variant for a future run')
    manifest = storage.verify_prepared(output)
    assert manifest['conditions'][0]['config']['prompts']['planner']['text'] == 'Original strategy prompt'
    with pytest.raises(FileExistsError):
        execute.prepare(path, output)


def test_mock_trace_end_to_end_and_duplicate_send(tmp_path, small_snapshot, monkeypatch):
    from integration.jev_planner.planner import ZaiPlannerClient
    monkeypatch.setattr(ZaiPlannerClient, 'from_env', lambda *_a, **_kw: pytest.fail('no actual planner'))
    output = tmp_path / 'trace'
    execute.prepare(config.HERE / 'examples/default.json', output)
    result = execute.run(output, mode='mock')
    assert result['passed']
    assert result['budget']['planner_http_attempts'] == 0
    assert result['budget']['simulated_planner_calls'] == 3
    summary = result['conditions'][0]['summary']
    assert summary['planner']['logical_calls'] == 3
    assert summary['cached_selection_records'] == 1
    assert summary['battle_score'] is None
    events = [json.loads(line) for line in (output / 'conditions/planner-demo/events.jsonl').read_text().splitlines()]
    assert sum(event['type'] == 'wire' for event in events) == 6
    assert (output / 'checksums.sha256').is_file()
    with pytest.raises(FileExistsError):
        execute.run(output, mode='mock')


def test_mode_switch_and_live_trace_refused_before_execution(tmp_path, small_snapshot):
    path = source_config(tmp_path)
    with pytest.raises(config.ConfigurationError, match='new battles'):
        execute.prepare(path, tmp_path / 'no-live', mode='live')
    assert not (tmp_path / 'no-live').exists()
    output = tmp_path / 'mock'
    execute.prepare(path, output)
    with pytest.raises(config.ConfigurationError, match='mode differs'):
        execute.run(output, mode='live')
    assert not (output / 'execution.json').exists()


def test_budget_failure_keeps_attempted_trace_and_stops_later_conditions(tmp_path, small_snapshot):
    path = source_config(tmp_path, evaluation={'kind': 'trace',
        'fixture': str(config.HERE / 'fixtures/demo.json'), 'limits': {'executor_calls': 1}},
        matrix={'triggers': ['off', 'events'], 'planner_prompts': [
            {'name': 'compact', 'path': str(config.HERE / 'prompts/strategy-compact.txt')}]})
    output = tmp_path / 'limited'
    execute.prepare(path, output)
    result = execute.run(output, mode='mock')
    assert not result['passed'] and result['error']['category'] == 'budget'
    first, second = result['conditions']
    assert first['summary']['failures']['failed'] == 1
    assert first['summary']['failures']['attempted'] == 1
    assert second['summary']['failures']['unattempted'] == 1
    assert result['budget']['executor_calls'] == 1


def test_missing_registered_ex_and_resource_declaration_block_live(tmp_path):
    cfg = config.load_config(config.HERE / 'examples/battle-mock.json')
    with pytest.raises(config.ConfigurationError, match='registered EX'):
        config.validate_mode(cfg, 'live')
    record = tmp_path / 'EX-092-unregistered.md'
    record.write_text('not a registered experiment')
    cfg['evaluation']['experiment_record'] = dict(path=str(record), text=record.read_text())
    with pytest.raises(config.ConfigurationError, match='INDEX'):
        config.validate_mode(cfg, 'live')


def test_whole_matrix_game_limit_is_not_reset_per_condition(tmp_path):
    cfg = config.load_config(config.HERE / 'examples/battle-mock.json')
    assert len(config.validate_prepared(cfg, 'mock')) == 2
    cfg['evaluation']['limits']['games'] = 2
    with pytest.raises(config.ConfigurationError, match='matrix plans 4 games'):
        config.validate_prepared(cfg, 'mock')


def test_source_and_prompt_tamper_refused(tmp_path, small_snapshot):
    output = tmp_path / 'run'
    execute.prepare(config.HERE / 'examples/default.json', output)
    (output / 'conditions/planner-demo/prompts/planner.txt').write_text('changed')
    with pytest.raises(ValueError, match='prompt changed'):
        storage.verify_prepared(output)


def test_preview_is_no_call_and_off_has_no_bridge(monkeypatch):
    from integration.jev_planner.planner import MockPlanner, ZaiPlannerClient
    monkeypatch.setattr(MockPlanner, 'plan', lambda *_a, **_kw: pytest.fail('preview does not run planner'))
    monkeypatch.setattr(ZaiPlannerClient, 'from_env', lambda *_a, **_kw: pytest.fail('preview has no credential loading'))
    result = execute.preview(config.HERE / 'examples/matrix.json', condition='off')
    assert result['api_requests'] == result['gpu_inferences'] == 0
    assert result['conditions'][0]['planner_messages'] is None
    assert result['conditions'][0]['executor_guidance'] is None
    assert 'planner_advice' not in result['conditions'][0]['executor_base_payload']['state']


def test_planner_cleanup_error_keeps_results_and_stops_following_conditions(tmp_path, small_snapshot, monkeypatch):
    from integration.jev_planner.planner import MockPlanner
    async def broken_close(self):
        raise RuntimeError('owner loop closed')
    monkeypatch.setattr(MockPlanner, 'aclose', broken_close)
    path = source_config(tmp_path, matrix={'triggers': ['events', 'periodic'],
        'planner_prompts': [{'name': 'compact', 'path': str(config.HERE / 'prompts/strategy-compact.txt')}]})
    output = tmp_path / 'cleanup'
    execute.prepare(path, output)
    result = execute.run(output, mode='mock')
    assert not result['passed'] and result['error']['category'] == 'cleanup'
    assert result['conditions'][0]['summary']['failures']['completed'] == 1
    assert result['conditions'][1]['summary']['failures']['unattempted'] == 1
    assert (output / 'checksums.sha256').is_file()


def test_interleaved_trace_halt_does_not_complete_partly_consumed_actor(tmp_path, small_snapshot):
    import copy
    fixture = config.read_json(config.HERE / 'fixtures/demo.json')
    first, second = fixture['cases'][:2]
    values = []
    for item, battle in ((first, 'A'), (first, 'B'), (second, 'A'), (second, 'B')):
        value = copy.deepcopy(item)
        value['battle'] = battle
        values.append(value)
    fixture['cases'] = values
    fixture_path = tmp_path / 'interleaved.json'
    fixture_path.write_text(json.dumps(fixture))
    path = source_config(tmp_path, trigger={'policy': 'off'}, evaluation={'kind': 'trace',
        'fixture': str(fixture_path), 'limits': {'executor_calls': 2}})
    output = tmp_path / 'interleaved'
    execute.prepare(path, output)
    result = execute.run(output, mode='mock')
    failures = result['conditions'][0]['summary']['failures']
    assert failures['attempted'] == failures['failed'] == 2
    assert failures['completed'] == 0


def test_watchdog_signal_runs_cancellation_cleanup_and_restores_handlers(tmp_path, monkeypatch):
    import asyncio
    import signal
    callbacks, removed, restored = {}, [], []
    async def body(directory, manifest):
        callback, args = callbacks[signal.SIGTERM]
        callback(*args)
        # A repeated watchdog notification must not cancel cleanup a second time.
        callback(*args)
        try:
            await asyncio.sleep(0)
        except asyncio.CancelledError:
            await asyncio.sleep(0)
            return {'cleanup_completed': True}
    monkeypatch.setattr(execute, '_run', body)
    monkeypatch.setattr(signal, 'signal', lambda signum, previous: restored.append(signum))
    async def scenario():
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, 'add_signal_handler',
                            lambda signum, callback, *args: callbacks.setdefault(signum, (callback, args)))
        monkeypatch.setattr(loop, 'remove_signal_handler', lambda signum: removed.append(signum))
        return await execute._run_interruptible(tmp_path, {})
    assert asyncio.run(scenario()) == {'cleanup_completed': True}
    assert set(removed) == set(restored) == {signal.SIGTERM, signal.SIGINT}
