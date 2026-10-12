"""단계 알람 사건과 재시작 중복 방지를 외부 전송 없이 검사한다."""
from types import SimpleNamespace

import pytest

from integration.pokechamp.abyssal_rl_next import alarms
from integration.pokechamp.abyssal_rl_next.storage import atomic, read


def setup(tmp_path, monkeypatch, *, phase='calibration_collect'):
    atomic(tmp_path / 'manifest.json', {'experiment_id': 'EX-075'})
    atomic(tmp_path / 'state.json', {'phase': phase})
    atomic(tmp_path / 'selection.json', {'selection': {'round': 1}})
    atomic(tmp_path / 'clock.json', {'deadline_at': 100})
    monkeypatch.setattr(alarms, 'process_alive', lambda *args: True)
    return dict(codex='synthetic-codex', thread='synthetic', thread_verified=True,
                pid=123, start_ticks='123')


def test_stage_delivery_and_restart_dedup(tmp_path, monkeypatch):
    config = setup(tmp_path, monkeypatch)
    sent = []
    def sender(command, **kwargs):
        sent.append(command)
        return SimpleNamespace(returncode=0)
    first = alarms.deliver_once(tmp_path, config, now=10, sender=sender)
    assert first['events']['selection']['status'] == 'delivered'
    alarms.deliver_once(tmp_path, config, now=20, sender=sender)
    assert len(sent) == 1
    atomic(tmp_path / 'state.json', {'phase': 'test_initial'})
    atomic(tmp_path / 'evaluation-lock.json', {'locked': True})
    atomic(tmp_path / 'calibration-decision.json', {'complete': True})
    alarms.deliver_once(tmp_path, config, now=30, sender=sender)
    assert len(sent) == 2
    atomic(tmp_path / 'completed.json', {'closed': True})
    final = alarms.deliver_once(tmp_path, config, now=101, sender=sender)
    assert len(sent) == 3
    assert final['events']['terminal']['receipt'] == 'completed.json'
    alarms.deliver_once(tmp_path, config, now=102, sender=sender)
    assert len(sent) == 3


def test_failed_ambiguous_delivery_never_repeated(tmp_path, monkeypatch):
    config = setup(tmp_path, monkeypatch)
    calls = []
    def timeout(*args, **kwargs):
        calls.append(1)
        raise TimeoutError('synthetic')
    record = alarms.deliver_once(tmp_path, config, now=10, sender=timeout)
    assert record['events']['selection']['status'] == 'uncertain'
    alarms.deliver_once(tmp_path, config, now=20, sender=timeout)
    assert calls == [1]


def test_pre_manifest_launch_and_startup_failure(tmp_path, monkeypatch):
    config = setup(tmp_path, monkeypatch, phase='preflight')
    (tmp_path / 'manifest.json').unlink()
    (tmp_path / 'state.json').unlink()
    (tmp_path / 'clock.json').unlink()
    atomic(tmp_path / 'prepared/manifest.json', {'experiment': 'EX-075'})
    sent = []
    def sender(*args, **kwargs):
        sent.append(1)
        return SimpleNamespace(returncode=0)
    assert alarms.deliver_once(tmp_path, config, sender=sender)['events'] == {}
    monkeypatch.setattr(alarms, 'process_alive', lambda *args: False)
    final = alarms.deliver_once(tmp_path, config, sender=sender)
    assert final['events']['abnormal']['receipt'] == 'prepared/manifest.json'
    assert sent == [1]


def test_terminal_alarm_coalesces_later_completion(tmp_path, monkeypatch):
    config = setup(tmp_path, monkeypatch, phase='collect')
    sent = []
    def sender(*args, **kwargs):
        sent.append(1)
        return SimpleNamespace(returncode=0)
    alarms.deliver_once(tmp_path, config, now=101, sender=sender)
    atomic(tmp_path / 'completed.json', {'closed': True})
    alarms.deliver_once(tmp_path, config, now=102, sender=sender)
    assert sent == [1]


def test_unverified_recipient_rejected(tmp_path, monkeypatch):
    config = setup(tmp_path, monkeypatch)
    config['thread_verified'] = False
    with pytest.raises(ValueError, match='verified current conversation'):
        alarms.deliver_once(tmp_path, config, now=10)


def test_abnormal_does_not_suppress_recovery_stages_or_completion(tmp_path, monkeypatch):
    config = setup(tmp_path, monkeypatch, phase='preflight')
    sent = []
    def sender(*args, **kwargs):
        sent.append(1)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(alarms, 'process_alive', lambda *args: False)
    first = alarms.deliver_once(tmp_path, config, now=10, sender=sender)
    assert set(first['events']) == {'abnormal'}
    alarms.deliver_once(tmp_path, config, now=11, sender=sender)
    assert len(sent) == 1
    monkeypatch.setattr(alarms, 'process_alive', lambda *args: True)
    atomic(tmp_path / 'state.json', {'phase': 'test_initial'})
    atomic(tmp_path / 'evaluation-lock.json', {'locked': True})
    atomic(tmp_path / 'calibration-decision.json', {'complete': True})
    middle = alarms.deliver_once(tmp_path, config, now=20, sender=sender)
    assert set(middle['events']) == {'abnormal', 'selection', 'test_entry'}
    atomic(tmp_path / 'completed.json', {'closed': True})
    final = alarms.deliver_once(tmp_path, config, now=101, sender=sender)
    assert set(final['events']) == {'abnormal', 'selection', 'test_entry', 'terminal'}
    assert len(sent) == 4


def test_recovery_watcher_ignores_historical_abnormal(tmp_path, monkeypatch):
    config = setup(tmp_path, monkeypatch, phase='preflight')
    atomic(tmp_path / 'clock.json', {'deadline_at': 100000000000})
    atomic(tmp_path / 'detector.json', config)
    ledger = {'events': {'abnormal': {'status': 'delivered'}}}
    passes = []
    def deliver(*args):
        passes.append(1)
        if len(passes) == 2:
            atomic(tmp_path / 'completed.json', {'closed': True})
            ledger['events']['terminal'] = {'status': 'delivered'}
        return ledger
    sleeps = []
    monkeypatch.setattr(alarms, 'deliver_once', deliver)
    monkeypatch.setattr(alarms.time, 'sleep', lambda interval: sleeps.append(interval))
    result = alarms.watch(tmp_path, tmp_path / 'detector.json')
    assert len(passes) == 2 and sleeps == [30]
    assert 'terminal' in result['events']


def test_watcher_stops_on_current_abnormal(tmp_path, monkeypatch):
    config = setup(tmp_path, monkeypatch, phase='preflight')
    atomic(tmp_path / 'clock.json', {'deadline_at': 100000000000})
    atomic(tmp_path / 'detector.json', config)
    monkeypatch.setattr(alarms, 'process_alive', lambda *args: False)
    monkeypatch.setattr(alarms, 'deliver_once', lambda *args: {'events': {'abnormal': {'status': 'delivered'}}})
    monkeypatch.setattr(alarms.time, 'sleep', lambda _: pytest.fail('must stop after abnormal'))
    assert 'abnormal' in alarms.watch(tmp_path, tmp_path / 'detector.json')['events']
