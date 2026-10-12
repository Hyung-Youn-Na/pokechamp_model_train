"""Boundary tests for the EX-082 physical resource guard."""
import fcntl
import json
import os
import signal

import pytest

from integration.jev27b import resource
from integration.jev27b.config import DISK_BYTES, GPU_BYTES, HOST_BYTES


def test_exact_limits_and_each_overflow():
    sample = dict(rss_bytes=HOST_BYTES, disk_bytes=DISK_BYTES,
                  gpus={i: dict(memory_used_mib=GPU_BYTES // 1024**2) for i in (0, 1)})
    assert resource.limit_errors(sample) == []
    sample['rss_bytes'] += 1
    assert resource.limit_errors(sample) == ['host_memory_exceeded']
    sample['disk_bytes'] += 1
    sample['gpus'][1]['memory_used_mib'] += 1
    assert resource.limit_errors(sample) == ['host_memory_exceeded', 'disk_budget_exceeded',
                                              'gpu1_memory_exceeded']


def test_busy_gpu_releases_both_locks_without_monitor_or_cuda(tmp_path, monkeypatch):
    monkeypatch.setattr(resource, 'ROOT', tmp_path)
    monkeypatch.setattr(resource, 'gpu_facts', lambda: {
        0: dict(memory_used_mib=0, utilization_percent=0),
        1: dict(memory_used_mib=257, utilization_percent=0)})
    monkeypatch.setattr(resource.ResourceMonitor, '__enter__',
                        lambda _: pytest.fail('busy GPU must never enter monitor/CUDA'))
    with pytest.raises(RuntimeError, match='GPU1 is not idle'):
        with resource.own_gpus(tmp_path / 'evidence'):
            pytest.fail('busy GPU acquired')
    locks = tmp_path / '.pokechamp-data/locks'
    assert {p.name for p in locks.iterdir()} == {'gpu0.lock', 'gpu1.lock'}
    for path in locks.iterdir():
        with path.open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_foreign_owner_is_not_taken_over(tmp_path, monkeypatch):
    monkeypatch.setattr(resource, 'ROOT', tmp_path)
    monkeypatch.setattr(resource, 'gpu_facts', lambda: pytest.fail('lock ownership precedes GPU queries'))
    locks = tmp_path / '.pokechamp-data/locks'
    locks.mkdir(parents=True)
    with (locks / 'gpu0.lock').open('a+') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match='owned by another run'):
            with resource.own_gpus(tmp_path / 'evidence'):
                pytest.fail('foreign lock taken')
    assert not (locks / 'gpu1.lock').exists()


def test_failed_stop_evidence_still_terminates_owned_process(tmp_path, monkeypatch):
    signals = []
    monkeypatch.setattr(resource, 'write', lambda *a, **k: (_ for _ in ()).throw(OSError('disk full')))
    monkeypatch.setattr(resource.os, 'kill', lambda pid, signum: signals.append((pid, signum)))
    monitor = resource.ResourceMonitor(tmp_path)
    monitor._abort(['host_memory_exceeded'], {})
    assert signals == [(os.getpid(), signal.SIGTERM)]
    assert monitor.stop.is_set()


def release_fixture(tmp_path, monkeypatch, pid=2**30):
    monkeypatch.setattr(resource, 'ROOT', tmp_path)
    locks = tmp_path / '.pokechamp-data/locks'
    locks.mkdir(parents=True)
    for i in (0, 1):
        (locks / f'gpu{i}.lock').touch()
    directory = tmp_path / 'release'
    directory.mkdir()
    (directory / f'gpu-acquire-{pid}.json').write_text(json.dumps(dict(pid=pid,
        gpus={str(i): dict(uuid=f'gpu-{i}') for i in (0, 1)})))
    return directory, locks, pid


def test_owned_release_waits_for_stale_utilization_and_ignores_gpu23(tmp_path, monkeypatch):
    directory, locks, pid = release_fixture(tmp_path, monkeypatch)
    snapshots = iter([{i: dict(uuid=f'gpu-{i}', memory_used_mib=0,
                         utilization_percent=util) for i in (0, 1)} for util in (100, 0)])
    monkeypatch.setattr(resource, 'gpu_facts', lambda: next(snapshots))
    monkeypatch.setattr(resource, 'gpu_compute_processes', lambda: [dict(uuid='gpu-2', pid=os.getpid())])
    waits = []
    monkeypatch.setattr(resource.time, 'sleep', waits.append)
    receipt = resource.wait_owned_gpu_release(directory, pid)
    assert receipt['passed'] and receipt['samples'] == 2 and waits == [.5]
    assert receipt['idle_memory_mib'] == 256 and receipt['idle_utilization_percent'] == 5
    assert len((directory / f'gpu-release-wait-{pid}.jsonl').read_text().splitlines()) == 2
    for path in locks.iterdir():
        with path.open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_owned_release_rejects_foreign_compute_process(tmp_path, monkeypatch):
    directory, locks, pid = release_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(resource, 'gpu_facts', lambda: {
        i: dict(uuid=f'gpu-{i}', memory_used_mib=0, utilization_percent=0) for i in (0, 1)})
    monkeypatch.setattr(resource, 'gpu_compute_processes', lambda: [dict(uuid='gpu-0', pid=42)])
    monkeypatch.setattr(resource.time, 'sleep', lambda _: pytest.fail('foreign process must fail immediately'))
    with pytest.raises(RuntimeError, match='foreign compute process'):
        resource.wait_owned_gpu_release(directory, pid)
    assert not (directory / f'gpu-settled-{pid}.json').exists()
    for path in locks.iterdir():
        with path.open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_owned_release_rejects_foreign_lock_before_gpu_query(tmp_path, monkeypatch):
    directory, locks, pid = release_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(resource, 'gpu_facts', lambda: pytest.fail('foreign lock precedes GPU queries'))
    with (locks / 'gpu0.lock').open('a+') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match='owned by another run during release'):
            resource.wait_owned_gpu_release(directory, pid)


def test_owned_release_rejects_live_or_reused_pid(tmp_path, monkeypatch):
    directory, _, pid = release_fixture(tmp_path, monkeypatch, pid=os.getpid())
    monkeypatch.setattr(resource, 'gpu_facts', lambda: pytest.fail('live PID precedes GPU queries'))
    with pytest.raises(RuntimeError, match='still alive or has been reused'):
        resource.wait_owned_gpu_release(directory, pid)
