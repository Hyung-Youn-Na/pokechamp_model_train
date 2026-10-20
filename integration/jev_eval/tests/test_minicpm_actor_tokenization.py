"""Actor/model tokenizer compatibility and unsanitized parent-env admission."""
from contextlib import nullcontext
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.jev_eval import config, execute, gates, resource, study
from integration.jev_eval.storage import digest, file_hash, read, write
from integration.minicpm5_jev import verify


@pytest.fixture
def saved(tmp_path, monkeypatch):
    """Two synthetic inputs, including an automatic one; no production census."""
    from transformers import AutoTokenizer

    cfg = replace(config.experiment('EX-091'), run=tmp_path / 'run',
                  model_dir=tmp_path / 'model', export=tmp_path / 'viewer')
    sources = {'fixture.py': 'frozen-source'}
    actor_env = dict(python=str(config.ACTOR_PYTHON),
                     packages=dict(transformers='4.57.1', tokenizers='0.22.1', torch='2.9.0'))
    model_env = dict(python=str(config.PYTHON),
                     packages=dict(transformers='5.17.0', tokenizers='0.23.2', torch='2.8.0'))
    root = tmp_path / 'baseline'
    directory = root / 'EX-089/collection'
    directory.mkdir(parents=True)
    monkeypatch.setattr(verify, 'RUNS', root)
    monkeypatch.setattr(verify, 'EXPECTED_INPUTS', 2)
    monkeypatch.setattr(verify, '_actor_environment', lambda: actor_env)
    monkeypatch.setattr(cfg.input_adapter, 'data_identity', lambda: {'fixture': 'input'})
    for forbidden in ('archived_inputs', '_baseline_identity', 'check_input'):
        monkeypatch.setattr(verify, forbidden, lambda *_a, **_k: pytest.fail('unexpected primary/prefix replay'))
    loads = []
    token = object()
    def load(path, **kwargs):
        loads.append((path, kwargs))
        return token
    monkeypatch.setattr(AutoTokenizer, 'from_pretrained', load)
    def tokenize(tok, formatted):
        assert tok is token
        return dict(input_ids=json.loads(formatted.state_text)['fixture_ids'])
    monkeypatch.setattr(cfg.formatter, 'tokenize_request', tokenize)
    cfg.tokenizer_dir.mkdir(parents=True)
    (cfg.tokenizer_dir / 'tokenizer.json').write_text('fixture tokenizer')
    for name in ('manifest.json', 'result.json', 'checksums.sha256'):
        (directory / name).write_text('fixture ' + name)
    events, details = [], []
    for number, count in ((1, 2), (2, 1)):
        payload = dict(state=dict(version=cfg.input_version, decision_kind='turn_action',
                                 fixture_ids=list(range(number, number + 3)), text='한글\n雪', empty=[]),
            questions={'action': dict(type='choice', instructions='frozen instructions',
                                     criteria={f'action{i}': {} for i in range(count)})})
        event = dict(type='input', decision=f'fixture-{number}', event_seq=number * 2, payload=payload,
                     commands={f'action{i}': f'/choose move {i + 1}' for i in range(count)})
        formatted = cfg.formatter.format_request(payload, allow_single=True)
        events.extend([dict(type='protocol', protocol='unused synthetic prefix'), event])
        ids = payload['state']['fixture_ids']
        details.append(dict(decision=event['decision'], input_event_seq=event['event_seq'],
            input_event_sha256=digest(event), candidate_ids=list(formatted.candidate_ids),
            input_tokens=len(ids), input_ids_sha256=digest(ids), prompt_sha256=formatted.prompt_sha256))
    (directory / 'events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in events))
    cfg.evidence.mkdir(parents=True)
    (cfg.evidence / verify.DETAILS).write_text(''.join(json.dumps(row) + '\n' for row in details))
    write(cfg.run / 'gates/requests-unencoded.json', {'fixture': 'requests'})
    (cfg.run / 'gates/token-ids.jsonl').write_text('fixture IDs')
    primary = dict(passed=True, experiment_id=cfg.experiment, checked_inputs=2, source=sources,
        format=cfg.format_version, input_data_identity=cfg.input_adapter.data_identity(),
        details_sha256=file_hash(cfg.evidence / verify.DETAILS),
        tokenizer_sha256=file_hash(cfg.tokenizer_dir / 'tokenizer.json'),
        tokenizer_environment=model_env,
        baseline_damage_recalculations=0, model_inferences=0, new_battles=0,
        gate_requests_sha256=file_hash(cfg.run / 'gates/requests-unencoded.json'),
        gate_token_ids_sha256=file_hash(cfg.run / 'gates/token-ids.jsonl'),
        baseline=dict(directory=str(directory), seal_sha256=file_hash(directory / 'checksums.sha256'),
            files={name: file_hash(directory / name) for name in ('manifest.json', 'result.json')},
            events_file_identity=verify.file_identity(directory / 'events.jsonl')))
    write(cfg.evidence / verify.RECEIPT, primary)
    return SimpleNamespace(cfg=cfg, sources=sources, actor_env=actor_env, model_env=model_env,
                           events=events, details=details, directory=directory, primary=primary,
                           loads=loads, token=token)


def test_actor_pass_matches_all_ids_in_order_and_reuses_immutable_receipt(saved):
    receipt = verify.verify_actor_tokenization(saved.cfg, saved.sources)
    assert receipt['passed'] and receipt['checked_inputs'] == 2
    assert receipt['input_tokens'] == 6 and receipt['maximum_input_tokens'] == 3
    assert receipt['actor_environment'] == saved.actor_env
    assert receipt['model_environment'] == saved.model_env
    assert receipt['actual_token_ids_equal'] and receipt['input_order_preserved']
    assert receipt['prefix_reaudits'] == receipt['baseline_damage_recalculations'] == 0
    assert saved.loads == [(saved.cfg.tokenizer_dir, dict(local_files_only=True, trust_remote_code=False))]
    assert verify.validate_actor_receipt(saved.cfg, saved.sources) == receipt
    assert verify.verify_actor_tokenization(saved.cfg, saved.sources) == receipt
    assert len(saved.loads) == 1


@pytest.mark.parametrize('corruption', ['token_ids', 'order', 'missing', 'extra', 'input_identity'])
def test_actor_pass_rejects_same_length_drift_and_input_coverage(saved, monkeypatch, corruption):
    if corruption == 'token_ids':
        monkeypatch.setattr(saved.cfg.formatter, 'tokenize_request',
            lambda _tok, formatted: dict(input_ids=list(reversed(json.loads(formatted.state_text)['fixture_ids']))))
    else:
        if corruption == 'order':
            saved.events[1], saved.events[3] = saved.events[3], saved.events[1]
        elif corruption == 'missing':
            saved.events.pop()
        elif corruption == 'extra':
            saved.events.append(saved.events[-1])
        else:
            saved.events[1]['decision'] = 'changed-input-identity'
        (saved.directory / 'events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in saved.events))
        saved.primary['baseline']['events_file_identity'] = verify.file_identity(saved.directory / 'events.jsonl')
        write(saved.cfg.evidence / verify.RECEIPT, saved.primary, immutable=False)
    with pytest.raises(ValueError, match='token IDs|input identity|input coverage|extra baseline input'):
        verify.verify_actor_tokenization(saved.cfg, saved.sources)
    receipt = read(saved.cfg.evidence / verify.ACTOR_RECEIPT)
    assert receipt['passed'] is False and receipt['checked_inputs'] <= 2
    assert receipt['error']['type'] == 'ValueError'
    with pytest.raises(ValueError):
        verify.verify_actor_tokenization(saved.cfg, saved.sources)
    assert len(saved.loads) == 1


@pytest.mark.parametrize('changed', ['primary_receipt', 'details', 'tokenizer', 'actor_version', 'receipt_count'])
def test_actor_receipt_rejects_changed_provenance_or_environment(saved, monkeypatch, changed):
    verify.verify_actor_tokenization(saved.cfg, saved.sources)
    if changed == 'primary_receipt':
        write(saved.cfg.evidence / verify.RECEIPT, dict(saved.primary, changed=True), immutable=False)
    elif changed == 'details':
        with (saved.cfg.evidence / verify.DETAILS).open('a') as output:
            output.write('{}\n')
    elif changed == 'tokenizer':
        (saved.cfg.tokenizer_dir / 'tokenizer.json').write_text('changed tokenizer')
    elif changed == 'actor_version':
        changed_env = dict(saved.actor_env, packages=dict(saved.actor_env['packages'], tokenizers='changed'))
        monkeypatch.setattr(verify, '_actor_environment', lambda: changed_env)
    else:
        path = saved.cfg.evidence / verify.ACTOR_RECEIPT
        write(path, dict(read(path), checked_inputs=1), immutable=False)
    with pytest.raises(ValueError, match='receipt'):
        verify.validate_actor_receipt(saved.cfg, saved.sources)


@pytest.mark.parametrize('fault', ['wrong_interpreter', 'initialized_cuda'])
def test_actor_environment_requires_its_own_cpu_runtime(monkeypatch, fault):
    import torch
    environment = dict(python=str(config.PYTHON if fault == 'wrong_interpreter' else config.ACTOR_PYTHON),
                       packages={})
    monkeypatch.setattr(verify, 'tokenizer_environment', lambda: environment)
    monkeypatch.setattr(torch.cuda, 'is_initialized', lambda: fault == 'initialized_cuda')
    with pytest.raises(ValueError, match='actor CPU environment'):
        verify._actor_environment()


def test_prepare_runs_actor_comparison_after_model_lengths_and_links_receipt(tmp_path, monkeypatch):
    cfg = replace(config.experiment('EX-091'), run=tmp_path / 'run', export=tmp_path / 'viewer')
    sources, order = {'fixture': 'source'}, []
    monkeypatch.setattr(execute, 'check_disk', lambda *_: {})
    monkeypatch.setattr(execute, 'source_snapshot', lambda *_: None)
    monkeypatch.setattr(execute, 'verify_cpu', lambda *_: None)
    monkeypatch.setattr(study, 'source_identity', lambda: sources)
    monkeypatch.setattr(study, 'prior_execution', lambda *_: None)
    monkeypatch.setattr(resource, 'ResourceMonitor', lambda *_a, **_k: nullcontext())
    monkeypatch.setattr(gates, 'regenerate_requests', lambda *_: dict(deferred=True))
    monkeypatch.setattr(verify, 'validate_receipt', lambda *_: dict(passed=True, checked_inputs=1139))
    def model_lengths(*_a, **_k):
        order.append('model_lengths')
        for name in ('model-ready.json', 'lengths.json', verify.RECEIPT):
            write(cfg.evidence / name, dict(passed=True))
    monkeypatch.setattr(execute, 'command_stage', model_lengths)
    def actor(selected, source):
        assert selected == cfg and source == sources and order == ['model_lengths']
        order.append('actor_comparison')
        receipt = dict(passed=True, checked_inputs=1139)
        write(cfg.evidence / verify.ACTOR_RECEIPT, receipt)
        return receipt
    monkeypatch.setattr(verify, 'verify_actor_tokenization', actor)
    prepared = execute.prepare(cfg)
    assert order == ['model_lengths', 'actor_comparison']
    assert prepared['actor_tokenization_verification'] == dict(
        path='evidence/' + verify.ACTOR_RECEIPT, checked_inputs=1139,
        sha256=file_hash(cfg.evidence / verify.ACTOR_RECEIPT))


@pytest.mark.parametrize('command', ['download', 'prepare', 'execute'])
def test_minicpm_parent_ingress_rejects_override_before_sanitized_child(tmp_path, monkeypatch, command):
    from integration.jev27b.model import ModelIntegrityError

    cfg = replace(config.experiment('EX-091'), run=tmp_path / 'run', export=tmp_path / 'viewer')
    monkeypatch.setenv('MINICPM_S1_TEMPERATURE', '2')
    monkeypatch.setattr(execute.subprocess, 'Popen', lambda *_a, **_k: pytest.fail('child was launched'))
    monkeypatch.setattr(execute.subprocess, 'run', lambda *_a, **_k: pytest.fail('download was launched'))
    with pytest.raises(ModelIntegrityError, match='overrides are not allowed'):
        if command == 'download':
            execute.main(['download', '--experiment', 'EX-091'])
        else:
            getattr(execute, command)(cfg)
    assert not cfg.run.exists()
    assert execute.status(cfg)['status'] == 'not_prepared'
    execute.reject_environment_overrides('EX-090')

