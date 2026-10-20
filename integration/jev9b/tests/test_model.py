"""CPU boundaries for the explicit official 9B package and unchanged 27B defaults."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest

from integration.jev27b import model as old_model, resource as shared_resource
from integration.jev9b import config, download, formatting, model, resource


def payload(count=13):
    ids = [f'move:{i}' for i in range(1, 5)] + [f'tera:{i}' for i in range(1, 5)]
    ids += [f'switch:{i}' for i in range(2, 7)]
    return dict(model=config.MODEL_ID, state=dict(version='jev-choice-v4', text='전체 상태'),
        questions={'action': dict(type='choice', instructions='모든 후보에서 한 개를 선택한다.',
            criteria={key: dict(kind=key.split(':')[0], slot=int(key.split(':')[1]),
                                extra=['preserved', {'nested': True}]) for key in ids[:count]})})


def test_thirteen_full_candidates_preserve_identity_order_and_last_head_slot():
    body = payload()
    frozen = copy.deepcopy(body)
    rendered = formatting.format_request(body)
    original = list(body['questions']['action']['criteria'])
    assert list(rendered.candidate_ids) == original and body == frozen
    lines = rendered.prompt.split('[options]\n', 1)[1].split('\n[decision]:', 1)[0].splitlines()
    for index, (key, option) in enumerate(zip(original, lines, strict=True)):
        assert option[:3] == f'{"ABCDEFGHIJKLM"[index]}) '
        assert json.loads(option[3:]) == {key: frozen['questions']['action']['criteria'][key]}
    values = [.0] * 12 + [1.0]
    answer = formatting.answer_from_probabilities(rendered, values)
    assert answer['choice'] == original[-1]
    assert list(answer['probabilities']) == original
    assert answer['probabilities'][original[-1]] == 1.0


def test_untruncated_limit_and_single_choice_rejected_before_a_forward():
    calls = []
    def tokenizer(text, **kwargs):
        calls.append(kwargs)
        return dict(input_ids=[7] * 32769, attention_mask=[1] * 32769)
    rendered = formatting.format_request(payload())
    with pytest.raises(formatting.InputTooLong) as error:
        formatting.tokenize_request(tokenizer, rendered)
    assert error.value.token_count == 32769 and error.value.max_tokens == 32768
    assert calls == [dict(add_special_tokens=False, truncation=False, padding=False,
                          return_attention_mask=True)]
    with pytest.raises(formatting.InputValidationError, match='single candidates'):
        formatting.format_request(payload(1))


def test_nine_b_head_calibration_identity_and_old_profile_are_distinct(tmp_path):
    new, old = model.Jev9BModel(tmp_path), old_model.Jev27BModel(tmp_path)
    assert new.metadata()['model'] == 'autotrust/JEV-9B'
    assert new.metadata()['revision'] == '7ac669b8fb476ba926491e3d1c39f9330d68dbed'
    assert old.metadata()['model'] == 'autotrust/JEV-27B'
    torch = SimpleNamespace(float32='float32')
    def head(width, dtype='float32'):
        return {'proj.weight': SimpleNamespace(shape=(24, width), dtype=dtype),
                'proj.bias': SimpleNamespace(shape=(24,), dtype=dtype)}
    new._validate_head(head(4096), torch)
    old._validate_head(head(5120), torch)
    for bad in (head(5120), head(4096, 'bfloat16')):
        with pytest.raises(model.ModelIntegrityError, match='FP32'):
            new._validate_head(bad, torch)
    cfg = dict(hidden_size=4096, weights_mode='unmerged', adapter_subfolder='adapter',
        slots=dict(num_slots=24, ranges={'choice': [8, 24]}, template_version='bare-v1'))
    calibration = {'per_kind': {'choice': 0.9840233476014968}}
    new._validate_configuration(cfg, calibration)
    calibration['per_kind']['choice'] = old.choice_temperature
    with pytest.raises(model.ModelIntegrityError, match='calibration'):
        new._validate_configuration(cfg, calibration)
    with pytest.raises(ValueError, match='does not support'):
        old_model.Jev27BModel(tmp_path, profile='ex085')
    with pytest.raises(ValueError, match='does not support'):
        model.Jev9BModel(tmp_path, profile='ex083')


def test_gpu_profile_is_six_ten_ten_six_and_checks_all_devices(tmp_path):
    placement = model.fixed_device_map()
    assert [sum(placement[f'model.layers.{i}'] == device for i in range(32))
            for device in range(4)] == [6, 10, 10, 6]
    assert placement['model.embed_tokens'] == 0
    assert placement['model.norm'] == placement['lm_head'] == 3
    assert old_model.fixed_device_map()['model.norm'] == 1
    settings = config.runtime_profile()
    assert settings.allocator_bytes == 40 * 1024**3 and settings.gpu_bytes == 44 * 1024**3
    sample = dict(rss_bytes=0, disk_bytes=0,
        gpus={i: {'memory_used_mib': 44 * 1024} for i in range(4)},
        gpu_allocated_bytes=[40 * 1024**3] * 4)
    assert resource.limit_errors(sample) == []
    sample['gpu_allocated_bytes'][3] += 1
    assert resource.limit_errors(sample) == ['gpu3_allocated_bytes_exceeded']
    with pytest.raises(ValueError, match='unknown frozen'):
        resource.disk_roots(profile='ex082')


def isolated_budget_paths(tmp_path, monkeypatch):
    paths = dict(ROOT=tmp_path, RUNTIME=tmp_path/'old-runtime', RUN=tmp_path/'old-run',
        EVIDENCE=tmp_path/'old-run/evidence', CONTINUATION_RUN=tmp_path/'baseline',
        JEV9B_RUNTIME=tmp_path/'new-runtime', JEV9B_RUN=tmp_path/'new-run')
    for name, value in paths.items():
        monkeypatch.setattr(shared_resource, name, value)
    environments = (tmp_path/'actor/.venv', tmp_path/'browser-tools', tmp_path/'browser-cache')
    monkeypatch.setattr(resource, 'SHARED_ENVIRONMENT_ROOTS', environments)
    return paths, environments


def test_disk_budget_includes_environment_both_references_new_model_and_temporary_viewer(tmp_path, monkeypatch):
    assert resource.SHARED_ENVIRONMENT_ROOTS == (config.ROOT/'pokechamp/.venv',
        Path('/tmp/ep037/tools'), Path('/root/.cache/ms-playwright'))
    paths, environments = isolated_budget_paths(tmp_path, monkeypatch)
    roots = [paths[n] for n in ('RUNTIME', 'RUN', 'CONTINUATION_RUN', 'JEV9B_RUNTIME', 'JEV9B_RUN')]
    roots.extend(tmp_path/'exports/battle_viewers'/name for name in ('ex082', 'ex083', 'ex085'))
    temporary = tmp_path/'temporary-viewer'
    roots.extend((temporary, *environments))
    for index, root in enumerate(roots, 1):
        root.mkdir(parents=True)
        (root/'file').write_bytes(b'x' * index)
    alias = tmp_path/'actor-alias'
    alias.symlink_to(environments[0], target_is_directory=True)
    extras = (temporary, paths['EVIDENCE'], environments[0]/'nested', alias)
    assert resource.disk_bytes(extra_roots=extras) == sum(range(1, 13))
    counted = resource.disk_roots(extra_roots=extras)
    assert all(counted.count(path.resolve()) == 1 for path in environments)
    assert environments[0]/'nested' not in counted
    assert all(path not in shared_resource.disk_roots() for path in environments)


def test_resource_monitor_counts_fixed_environments_through_inherited_sampler(tmp_path, monkeypatch):
    paths, environments = isolated_budget_paths(tmp_path, monkeypatch)
    temporary = tmp_path/'temporary-viewer'
    for count, root in enumerate((*environments, temporary), 1):
        root.mkdir(parents=True)
        (root/'file').write_bytes(b'x' * count)
    monitor = resource.ResourceMonitor(tmp_path/'monitor', budget_root=paths['JEV9B_RUN'],
        extra_roots=(temporary, environments[0]/'nested'))
    assert monitor.thread is None
    assert monitor._disk_bytes() == 10
    assert all(path.resolve() in monitor.roots for path in (*environments, temporary))


def test_ownership_passes_fixed_environments_to_actual_shared_monitor_and_receipt(tmp_path, monkeypatch):
    paths, environments = isolated_budget_paths(tmp_path, monkeypatch)
    temporary = tmp_path/'temporary-viewer'
    facts = {i: dict(index=i, uuid=f'GPU-{UUID(int=i+1)}', memory_total_mib=48*1024,
                     memory_used_mib=0, utilization_percent=0) for i in range(4)}
    monkeypatch.setattr(shared_resource, 'gpu_facts', lambda: facts)
    monkeypatch.setattr(shared_resource, 'gpu_compute_processes', lambda: [])
    monkeypatch.setattr(shared_resource, '_stop_on_parent_exit', lambda: None)
    for key in ('CUDA_VISIBLE_DEVICES', 'CUDA_DEVICE_ORDER', 'CUBLAS_WORKSPACE_CONFIG',
                'TOKENIZERS_PARALLELISM', 'PYTHONDONTWRITEBYTECODE', 'HF_HUB_OFFLINE',
                'TRANSFORMERS_OFFLINE', 'TRITON_CACHE_DIR', 'TORCHINDUCTOR_CACHE_DIR',
                'TORCHINDUCTOR_COMPILE_THREADS', 'OMP_NUM_THREADS'):
        monkeypatch.setenv(key, os.environ.get(key, ''))
    caps, monitors = [], []
    cuda = SimpleNamespace(is_initialized=lambda: False, device_count=lambda: 4,
        get_device_properties=lambda i: SimpleNamespace(total_memory=48*1024**3, uuid=UUID(int=i+1)),
        set_per_process_memory_fraction=lambda fraction, index: caps.append((index, fraction)))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=cuda))

    class MonitorWithoutThread(shared_resource.ResourceMonitor):
        def __enter__(self):
            monitors.append(self)
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(shared_resource, 'ResourceMonitor', MonitorWithoutThread)
    directory = tmp_path/'serving'
    with resource.own_gpus(directory, budget_root=paths['JEV9B_RUN'], extra_roots=(temporary,)):
        assert caps == [(i, 40/48) for i in range(4)]
        assert len(monitors) == 1
        assert all(path.resolve() in monitors[0].roots for path in (*environments, temporary))
    receipt = json.loads((directory/f'gpu-acquire-{os.getpid()}.json').read_text())
    assert all(str(path.resolve()) in receipt['disk_roots'] for path in (*environments, temporary))


def test_once_verified_receipt_refuses_a_same_length_replacement_without_rehash(tmp_path, monkeypatch):
    directory, evidence = tmp_path/'model', tmp_path/'evidence'
    directory.mkdir()
    evidence.mkdir()
    raw = b'{"pinned":"value"}'
    name = 'config.json'
    (directory/name).write_bytes(raw)
    git_oid = hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    entry = dict(type='file', path=name, size=len(raw), oid=git_oid)
    monkeypatch.setattr(download, 'OFFICIAL_FILES', {name: (len(raw), git_oid, None)})
    row = dict(path=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
        official_sha256=None, git_oid=git_oid, file_identity=download.file_identity(directory/name))
    receipt = dict(passed=True, model=config.MODEL_ID, revision=config.REVISION,
        model_directory=str(directory.resolve()), files=[row], bytes=len(raw))
    (evidence/'download.json').write_text(json.dumps(receipt))
    (evidence/'official-tree.json').write_text(json.dumps(dict(model=config.MODEL_ID,
        revision=config.REVISION, files=[entry])))
    monkeypatch.setattr(download, 'file_hash', lambda *_: pytest.fail('repeated model content hash'))
    assert download.verify_receipt(directory, evidence) == receipt
    replacement = directory/'replacement'
    replacement.write_bytes(raw.replace(b'value', b'other'))
    replacement.replace(directory/name)
    with pytest.raises(ValueError, match='verified model file changed'):
        download.verify_receipt(directory, evidence)
