"""CPU checks for EX-083 placement, ownership, budgets, reloads and shutdown."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import sys
import threading
from types import SimpleNamespace
from uuid import UUID

import pytest

from integration.jev27b import config, model, preflight, resource, server


GIB = 1024**3


def test_real_pytorch_bare_uuid_matches_nvml_prefix_without_accepting_another_device():
    nvml = 'GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4'
    cuda = UUID('4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4')
    assert str(cuda).lower() != nvml.lower()  # The preserved pre-load defect.
    assert resource.canonical_gpu_uuid(cuda) == resource.canonical_gpu_uuid(nvml)
    assert resource.canonical_gpu_uuid(cuda) != resource.canonical_gpu_uuid(
        'GPU-c7e2d577-573f-0412-1ed6-ad6648efa454')
    for malformed in ('GPU-', 'GPU-4f27', 'MIG-' + str(cuda), None):
        with pytest.raises(RuntimeError, match='invalid full'):
            resource.canonical_gpu_uuid(malformed)


@pytest.mark.parametrize('change_pid', [False, True])
def test_nvml_host_pid_is_not_compared_to_container_pid_but_must_stay_single_and_stable(
        tmp_path, monkeypatch, change_pid):
    isolated_paths(monkeypatch, tmp_path)
    monitor = resource.ResourceMonitor(tmp_path, profile='ex083', budget_root=tmp_path,
        expected_uuids={i: facts()[i]['uuid'] for i in range(4)})
    monkeypatch.setattr(monitor, '_disk_bytes', lambda: 0)
    count = 0

    def sample():
        nonlocal count
        count += 1
        if count == 2:
            monitor.stop.set()
        return facts()

    monkeypatch.setattr(resource, 'gpu_facts', sample)
    monkeypatch.setattr(resource, 'gpu_compute_processes', lambda: [
        dict(uuid=facts()[i]['uuid'], pid=2**30 + int(change_pid and count == 2)) for i in range(4)])
    signals = []
    monkeypatch.setattr(resource.os, 'kill', lambda *args: signals.append(args))
    monitor._watch()
    rows = [json.loads(line) for line in (tmp_path / f'resources-{os.getpid()}.jsonl').read_text().splitlines()]
    assert rows[0]['errors'] == [] and rows[0]['initial_compute_host_pid'] == 2**30
    assert rows[0]['compute_pid_namespace'] == 'nvml-host'
    if change_pid:
        assert rows[-1]['errors'] == ['gpu_compute_pid_changed'] and len(signals) == 1
    else:
        assert rows[-1]['errors'] == [] and signals == []


def facts(count=4):
    return {i: dict(index=i, uuid=f'GPU-{UUID(int=i + 1)}', memory_total_mib=48 * 1024,
                    memory_used_mib=0, utilization_percent=0) for i in range(count)}


def assert_unlocked(directory, indices=range(4)):
    for index in indices:
        with (directory / f'gpu{index}.lock').open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def isolated_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(resource, 'ROOT', tmp_path)
    for name in ('RUNTIME', 'RUN', 'EVIDENCE', 'CONTINUATION_RUN'):
        monkeypatch.setattr(resource, name, tmp_path / name.lower())


def fake_gpu_runtime(monkeypatch, tmp_path, *, count=4):
    isolated_paths(monkeypatch, tmp_path)
    events, caps = [], []
    monkeypatch.setattr(resource, 'gpu_facts', lambda: facts(count))
    monkeypatch.setattr(resource, 'gpu_compute_processes', lambda: [])
    monkeypatch.setattr(resource, '_stop_on_parent_exit', lambda: events.append('parent-guard'))
    for key in ('CUDA_VISIBLE_DEVICES', 'CUDA_DEVICE_ORDER', 'CUBLAS_WORKSPACE_CONFIG',
                'TOKENIZERS_PARALLELISM', 'PYTHONDONTWRITEBYTECODE', 'HF_HUB_OFFLINE',
                'TRANSFORMERS_OFFLINE', 'TRITON_CACHE_DIR', 'TORCHINDUCTOR_CACHE_DIR',
                'TORCHINDUCTOR_COMPILE_THREADS', 'OMP_NUM_THREADS'):
        monkeypatch.setenv(key, os.environ.get(key, ''))

    class Monitor:
        def __init__(self, directory, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            events.append(('monitor-enter', self.kwargs))
            return self

        def __exit__(self, *args):
            events.append('monitor-exit')

    monkeypatch.setattr(resource, 'ResourceMonitor', Monitor)

    def properties(index):
        events.append(('cuda-properties', index))
        assert any(isinstance(row, tuple) and row[0] == 'monitor-enter' for row in events)
        # Real PyTorch 2.8 _CUuuid.__str__ has no NVML GPU- prefix.
        return SimpleNamespace(total_memory=48 * GIB, uuid=UUID(int=index + 1))

    cuda = SimpleNamespace(is_initialized=lambda: False, device_count=lambda: count,
                           get_device_properties=properties,
                           set_per_process_memory_fraction=lambda fraction, index: caps.append((index, fraction)))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=cuda))
    return cuda, events, caps


def test_explicit_placement_preserves_two_gpu_default_and_selects_four():
    original, continuation = model.fixed_device_map(), model.fixed_device_map('ex083')
    assert original['model.norm'] == original['lm_head'] == 1
    assert all(original[f'model.layers.{i}'] == (0 if i < 32 else 1) for i in range(64))
    assert continuation['model.embed_tokens'] == continuation['model.rotary_emb'] == 0
    assert continuation['model.norm'] == continuation['lm_head'] == 3
    for lower, upper, device in ((0, 14, 0), (14, 32, 1), (32, 50, 2), (50, 64, 3)):
        assert all(continuation[f'model.layers.{i}'] == device for i in range(lower, upper))
    with pytest.raises(ValueError, match='unknown frozen'):
        model.fixed_device_map('auto')


def test_tensor_placement_rejects_a_layer_on_the_wrong_owned_gpu():
    def tensor(device):
        return SimpleNamespace(device=SimpleNamespace(type='cuda', index=device))

    values = [('model.embed_tokens.weight', tensor(0)), ('model.layers.14.self_attn.weight', tensor(1)),
              ('model.layers.50.self_attn.weight', tensor(3)), ('model.norm.weight', tensor(3)),
              ('lm_head.weight', tensor(3))]
    loaded = SimpleNamespace(named_parameters=lambda: values,
                             named_buffers=lambda: [('model.rotary_emb.inv_freq', tensor(0))])
    model._check_placement(loaded, model.fixed_device_map('ex083'))
    values[1][1].device.index = 0
    with pytest.raises(model.ModelIntegrityError, match='model.layers.14'):
        model._check_placement(loaded, model.fixed_device_map('ex083'))


def test_four_gpu_nvml_and_allocator_budgets_are_independent():
    settings = config.runtime_profile('ex083')
    assert settings.physical_gpus == (0, 1, 2, 3)
    assert settings.allocator_bytes == 40 * GIB and settings.gpu_bytes == 44 * GIB
    assert settings.host_bytes == 32 * GIB and settings.disk_bytes == 100 * GIB
    sample = dict(rss_bytes=32 * GIB, disk_bytes=100 * GIB,
                  gpus={i: dict(memory_used_mib=44 * 1024) for i in range(4)},
                  gpu_allocated_bytes=[40 * GIB] * 4, gpu_reserved_bytes=[40 * GIB] * 4)
    assert resource.limit_errors(sample, profile='ex083') == []
    sample['gpu_reserved_bytes'][3] += 1
    assert resource.limit_errors(sample, profile='ex083') == ['gpu3_reserved_bytes_exceeded']
    sample['gpu_reserved_bytes'][3] -= 1
    sample['gpus'][2]['memory_used_mib'] += 1
    assert resource.limit_errors(sample, profile='ex083') == ['gpu2_memory_exceeded']
    sample['rss_bytes'] += 1
    sample['disk_bytes'] += 1
    assert resource.limit_errors(sample, profile='ex083') == [
        'host_memory_exceeded', 'disk_budget_exceeded', 'gpu2_memory_exceeded']


def test_model_memory_checks_cover_gpu3_and_preserve_old_budget(tmp_path):
    current = model.Jev27BModel(tmp_path, profile='ex083')
    old = model.Jev27BModel(tmp_path)
    cuda = SimpleNamespace(memory_allocated=lambda i: 40 * GIB,
                           memory_reserved=lambda i: 40 * GIB + int(i == 3),
                           max_memory_allocated=lambda i: 40 * GIB)
    for loaded in (current, old):
        loaded.loaded = True
        loaded._torch = SimpleNamespace(cuda=cuda)
    assert len(current._resource()['gpu_reserved_bytes']) == 4
    with pytest.raises(model.ModelIntegrityError, match='40 GiB'):
        current._check_memory()
    old._check_memory()
    assert len(old._resource()['gpu_reserved_bytes']) == 2


def test_partial_four_gpu_lock_failure_releases_only_acquired_locks(tmp_path, monkeypatch):
    isolated_paths(monkeypatch, tmp_path)
    locks = tmp_path / '.pokechamp-data/locks'
    locks.mkdir(parents=True)
    monkeypatch.setattr(resource, 'gpu_facts', lambda: pytest.fail('query before all four locks'))
    with (locks / 'gpu2.lock').open('a+') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match='GPU2 is owned'):
            with resource.own_gpus(tmp_path / 'evidence', profile='ex083'):
                pytest.fail('foreign ownership bypassed')
        assert_unlocked(locks, (0, 1))
        assert not (locks / 'gpu3.lock').exists()
        with (locks / 'gpu2.lock').open('a+') as probe:
            with pytest.raises(BlockingIOError):
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize('blocked', ['busy', 'compute', 'missing', 'duplicate_uuid', 'cuda_initialized', 'cuda_uuid'])
def test_failures_never_yield_and_return_all_four_locks(tmp_path, monkeypatch, blocked):
    cuda, events, caps = fake_gpu_runtime(monkeypatch, tmp_path)
    snapshot = facts()
    if blocked == 'busy':
        snapshot[3]['memory_used_mib'] = 257
    elif blocked == 'compute':
        monkeypatch.setattr(resource, 'gpu_compute_processes', lambda: [dict(uuid=snapshot[3]['uuid'], pid=42)])
    elif blocked == 'missing':
        del snapshot[3]
    elif blocked == 'duplicate_uuid':
        snapshot[3]['uuid'] = snapshot[2]['uuid']
    elif blocked == 'cuda_initialized':
        cuda.is_initialized = lambda: True
    elif blocked == 'cuda_uuid':
        cuda.get_device_properties = lambda i: SimpleNamespace(total_memory=48 * GIB, uuid='GPU-wrong')
    monkeypatch.setattr(resource, 'gpu_facts', lambda: snapshot)
    with pytest.raises(RuntimeError):
        with resource.own_gpus(tmp_path / 'evidence', profile='ex083'):
            pytest.fail('failed ownership gate yielded')
    assert caps == []
    if blocked in ('busy', 'compute', 'missing', 'duplicate_uuid'):
        assert not any(isinstance(event, tuple) and event[0] == 'monitor-enter' for event in events)
    assert_unlocked(tmp_path / '.pokechamp-data/locks')


@pytest.mark.parametrize('exception', [None, RuntimeError, KeyboardInterrupt, SystemExit])
def test_four_gpu_caps_uuid_mapping_and_cleanup(tmp_path, monkeypatch, exception):
    _, events, caps = fake_gpu_runtime(monkeypatch, tmp_path)
    output = tmp_path / 'evidence'

    def use_gpus():
        with resource.own_gpus(output, profile='ex083', budget_root=tmp_path / 'new-run') as selected:
            assert set(selected) == set(range(4))
            assert os.environ['CUDA_VISIBLE_DEVICES'] == ','.join(facts()[i]['uuid'] for i in range(4))
            assert caps == [(i, 40 / 48) for i in range(4)]
            for i in range(4):
                with (tmp_path / f'.pokechamp-data/locks/gpu{i}.lock').open('a+') as probe:
                    with pytest.raises(BlockingIOError):
                        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if exception:
                raise exception()

    if exception:
        with pytest.raises(exception):
            use_gpus()
    else:
        use_gpus()
    assert events[-1] == 'monitor-exit'
    assert_unlocked(tmp_path / '.pokechamp-data/locks')
    receipt = json.loads((output / f'gpu-acquire-{os.getpid()}.json').read_text())
    released = json.loads((output / f'gpu-release-{os.getpid()}.json').read_text())
    assert receipt['physical_gpus'] == released['physical_gpus'] == [0, 1, 2, 3]
    assert receipt['allocator_bytes'] == 40 * GIB and receipt['gpu_bytes'] == 44 * GIB


def test_default_ownership_still_uses_only_two_gpus_and_44gib(tmp_path, monkeypatch):
    _, _, caps = fake_gpu_runtime(monkeypatch, tmp_path, count=2)
    with resource.own_gpus(tmp_path / 'evidence') as selected:
        assert set(selected) == {0, 1}
        assert os.environ['CUDA_VISIBLE_DEVICES'] == ','.join(facts()[i]['uuid'] for i in range(2))
    assert caps == [(i, 44 / 48) for i in range(2)]
    assert not (tmp_path / '.pokechamp-data/locks/gpu2.lock').exists()


def test_four_gpu_release_waits_for_gpu3_and_checks_its_uuid(tmp_path, monkeypatch):
    isolated_paths(monkeypatch, tmp_path)
    locks = tmp_path / '.pokechamp-data/locks'
    locks.mkdir(parents=True)
    output, pid = tmp_path / 'evidence', 2**30
    output.mkdir()
    acquired = dict(pid=pid, profile='ex083', physical_gpus=[0, 1, 2, 3], gpus=facts())
    (output / f'gpu-acquire-{pid}.json').write_text(json.dumps(acquired))
    busy, idle = facts(), facts()
    busy[3]['utilization_percent'] = 100
    snapshots = iter((busy, idle))
    monkeypatch.setattr(resource, 'gpu_facts', lambda: next(snapshots))
    monkeypatch.setattr(resource, 'gpu_compute_processes', lambda: [])
    waits = []
    monkeypatch.setattr(resource.time, 'sleep', waits.append)
    result = resource.wait_owned_gpu_release(output, pid, profile='ex083')
    assert result['samples'] == 2 and waits == [.5]
    assert result['physical_gpus'] == [0, 1, 2, 3]
    assert_unlocked(locks)
    idle[3]['uuid'] = 'GPU-changed'
    monkeypatch.setattr(resource, 'gpu_facts', lambda: idle)
    with pytest.raises(RuntimeError, match='identity changed'):
        resource.wait_owned_gpu_release(output, pid, profile='ex083')
    assert_unlocked(locks)
    with pytest.raises(RuntimeError, match='matching owned process'):
        resource.wait_owned_gpu_release(output, pid)


def test_disk_counts_preserved_and_new_outputs_once(tmp_path, monkeypatch):
    isolated_paths(monkeypatch, tmp_path)
    new_run = tmp_path / 'new-run'
    roots = [resource.RUNTIME, resource.RUN, resource.EVIDENCE,
             tmp_path / 'exports/battle_viewers/ex082', new_run,
             tmp_path / 'exports/battle_viewers/ex083']
    for i, path in enumerate(roots, 1):
        (path / 'nested').mkdir(parents=True)
        (path / 'nested/file').write_bytes(b'x' * i)
    # A differently named default EX-083 path is not added to an explicit run.
    resource.CONTINUATION_RUN.mkdir()
    (resource.CONTINUATION_RUN / 'unrelated').write_bytes(b'x' * 100)
    assert resource.disk_bytes() == 1 + 2 + 3 + 4
    assert resource.disk_bytes(profile='ex083', budget_root=new_run,
                               extra_roots=(new_run / 'nested', resource.RUNTIME)) == 21
    monitor = resource.ResourceMonitor(new_run / 'evidence', profile='ex083', budget_root=new_run)
    assert monitor._disk_bytes() == 21


def test_monitor_aborts_on_gpu3_overflow_without_torch_or_locks(tmp_path, monkeypatch):
    isolated_paths(monkeypatch, tmp_path)
    snapshot = facts()
    snapshot[3]['memory_used_mib'] = 44 * 1024 + 1
    monkeypatch.setattr(resource, 'gpu_facts', lambda: snapshot)
    monitor = resource.ResourceMonitor(tmp_path, profile='ex083', budget_root=tmp_path)
    monkeypatch.setattr(monitor, '_disk_bytes', lambda: 0)
    stops = []
    monkeypatch.setattr(resource.os, 'kill', lambda pid, signum: stops.append((pid, signum)))
    monitor._watch()
    receipt = json.loads((tmp_path / f'resource-stop-{os.getpid()}.json').read_text())
    assert receipt['errors'] == ['gpu3_memory_exceeded']
    assert stops == [(os.getpid(), signal.SIGTERM)]
    assert set(receipt['sample']['gpus']) == {'0', '1', '2', '3'}
    assert not (tmp_path / '.pokechamp-data/locks').exists()


@pytest.mark.parametrize('failure', ['foreign_compute', 'identity'])
def test_monitor_guards_all_owned_identities(tmp_path, monkeypatch, failure):
    isolated_paths(monkeypatch, tmp_path)
    snapshot = facts()
    if failure == 'identity':
        snapshot[3]['uuid'] = 'GPU-changed'
    monkeypatch.setattr(resource, 'gpu_facts', lambda: snapshot)
    monkeypatch.setattr(resource, 'gpu_compute_processes',
                        lambda: [dict(uuid=facts()[3]['uuid'], pid=2**30),
                                 dict(uuid=facts()[0]['uuid'], pid=2**30 + 1)] if failure == 'foreign_compute' else [])
    monitor = resource.ResourceMonitor(tmp_path, profile='ex083', budget_root=tmp_path,
                                        expected_uuids={i: facts()[i]['uuid'] for i in range(4)})
    monkeypatch.setattr(monitor, '_disk_bytes', lambda: 0)
    monkeypatch.setattr(resource.os, 'kill', lambda *args: None)
    monitor._watch()
    receipt = json.loads((tmp_path / f'resource-stop-{os.getpid()}.json').read_text())
    assert receipt['errors'] == ['multiple_gpu_compute_processes' if failure == 'foreign_compute'
                                 else 'gpu_identity_changed']


@pytest.mark.parametrize('late_error', [False, True])
def test_monitor_shutdown_blocks_late_records_signals_and_false_success(tmp_path, monkeypatch, late_error):
    isolated_paths(monkeypatch, tmp_path)
    entered, release = threading.Event(), threading.Event()

    def slow_snapshot():
        entered.set()
        assert release.wait(5)
        if late_error:
            raise RuntimeError('late GPU query failure')
        result = facts()
        result[3]['memory_used_mib'] = 44 * 1024 + 1
        return result

    monkeypatch.setattr(resource, 'gpu_facts', slow_snapshot)
    signals = []
    monkeypatch.setattr(resource.os, 'kill', lambda *args: signals.append(args))
    monitor = resource.ResourceMonitor(tmp_path, profile='ex083', budget_root=tmp_path)
    monkeypatch.setattr(monitor, '_disk_bytes', lambda: 0)
    monitor.__enter__()
    original_join = monitor.thread.join
    try:
        assert entered.wait(2)
        # Exercise the timeout outcome immediately while keeping a real live thread.
        monkeypatch.setattr(monitor.thread, 'join', lambda timeout=None: original_join(timeout=0))
        with pytest.raises(RuntimeError, match='did not stop'):
            monitor.__exit__(None, None, None)
        assert monitor.thread.is_alive()
    finally:
        release.set()
        original_join(timeout=2)
    assert not monitor.thread.is_alive()
    assert signals == []
    assert not (tmp_path / f'resources-{os.getpid()}.jsonl').exists()
    assert not (tmp_path / f'resource-stop-{os.getpid()}.json').exists()


def test_preflight_profile_reuses_five_archived_inputs_and_refuses_overwrite(tmp_path, monkeypatch):
    evidence, output = tmp_path / 'parent', tmp_path / 'reload'
    (evidence / 'lengths').mkdir(parents=True)
    (evidence / 'download.json').write_text('{"passed":true}')
    (evidence / 'lengths/report.json').write_text('{"passed":true}')
    names = ['lead-1', 'lead-2', 'turn-sample-01', 'forced-switch', 'longest-ex058']
    cases = [dict(name=name, body=dict(case=name)) for name in names]
    (evidence / 'lengths/cases.json').write_text(json.dumps(cases))
    calls = []

    @contextmanager
    def ownership(directory, **kwargs):
        calls.append(('owned', str(directory), kwargs))
        yield

    class Model:
        def __init__(self, path, **kwargs):
            calls.append(('model', kwargs))

        def load(self):
            return self

        def metadata(self):
            return {'loaded': True}

        def evaluate(self, body):
            calls.append(('evaluate', body))
            return body

    monkeypatch.setattr(resource, 'own_gpus', ownership)
    monkeypatch.setattr(model, 'Jev27BModel', Model)
    before = (evidence / 'lengths/cases.json').read_bytes()
    preflight.infer(output, profile='ex083', evidence=evidence, budget_root=tmp_path)
    assert calls[0][2] == dict(profile='ex083', budget_root=tmp_path, extra_roots=(evidence,))
    assert calls[1] == ('model', dict(max_tokens=32768, profile='ex083'))
    assert [row[1] for row in calls[2:]] == [case['body'] for case in cases]
    assert json.loads((output / 'result.json').read_text())['profile'] == 'ex083'
    assert (evidence / 'lengths/cases.json').read_bytes() == before
    with pytest.raises(FileExistsError):
        preflight.infer(output, profile='ex083', evidence=evidence, budget_root=tmp_path)


def test_preflight_cli_passes_the_explicit_profile_and_parent_evidence(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(preflight, 'infer', lambda *args, **kwargs: calls.append((args, kwargs)))
    previous = signal.getsignal(signal.SIGTERM)
    try:
        preflight.main(['infer', str(tmp_path / 'reload'), '--profile', 'ex083',
                        '--evidence', str(tmp_path / 'parent'), '--budget-root', str(tmp_path)])
    finally:
        signal.signal(signal.SIGTERM, previous)
    assert calls == [((str(tmp_path / 'reload'),), dict(profile='ex083',
                       evidence=tmp_path / 'parent', budget_root=tmp_path))]
    monkeypatch.setattr(preflight, 'lengths', lambda: pytest.fail('original length output was entered'))
    with pytest.raises(SystemExit) as caught:
        preflight.main(['lengths', '--profile', 'ex083'])
    assert caught.value.code == 2


def test_server_profile_shutdown_passes_same_scope_to_model_and_ownership(tmp_path, monkeypatch):
    calls = []

    @contextmanager
    def ownership(directory, **kwargs):
        calls.append(('acquire', directory, kwargs))
        try:
            yield
        finally:
            calls.append('release')

    class Model:
        def __init__(self, path, **kwargs):
            calls.append(('model', path, kwargs))

        def load(self):
            return self

    class Service:
        def __init__(self, loaded, directory):
            pass

        def close(self):
            calls.append('service-close')

    class HttpServer:
        def __init__(self, address, service):
            pass

        def serve_forever(self, **kwargs):
            # Simulate the production SIGTERM path without signaling the test runner.
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

        def server_close(self):
            calls.append('http-close')

    monkeypatch.setattr(resource, 'own_gpus', ownership)
    monkeypatch.setattr(model, 'Jev27BModel', Model)
    monkeypatch.setattr(server, 'LocalService', Service)
    monkeypatch.setattr(server, 'LocalHTTPServer', HttpServer)
    previous = signal.getsignal(signal.SIGTERM)
    try:
        with pytest.raises(SystemExit) as caught:
            server.main(['--model-dir', str(tmp_path / 'model'), '--run-dir', str(tmp_path / 'server'),
                         '--profile', 'ex083', '--budget-root', str(tmp_path)])
        assert caught.value.code == 128 + signal.SIGTERM
    finally:
        signal.signal(signal.SIGTERM, previous)
    assert calls[0] == ('acquire', tmp_path / 'server', dict(profile='ex083', budget_root=tmp_path))
    assert calls[1] == ('model', tmp_path / 'model', dict(max_tokens=32768, profile='ex083'))
    assert calls[-3:] == ['http-close', 'service-close', 'release']
