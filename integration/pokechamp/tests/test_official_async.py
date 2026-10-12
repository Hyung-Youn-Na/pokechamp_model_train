"""Real official timers, serial commands, failure disposal and wall-clock budgets."""
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from integration.pokechamp.observation.runtime import OfficialClient, ObservationError
from integration.pokechamp.observation.build import DEFAULT_BUILD
from integration.pokechamp.tests.test_observation_comparison import fixture

ROOT = Path(__file__).resolve().parents[3]
PRELOAD = ROOT / 'integration/pokechamp/diagnostics/official_async_delay.cjs'
CLIENT = ROOT / 'integration/pokechamp/observation/client.cjs'


def delay(monkeypatch, mode='delay'):
    monkeypatch.setenv('NODE_OPTIONS', '--require=' + str(PRELOAD))
    monkeypatch.setenv('EP058_DELAY_MODE', mode)


def test_real_timer_last_row_request_and_repeated_yields(monkeypatch, tmp_path):
    prefix, _ = fixture()
    with OfficialClient('p1') as client:
        expected = client.snapshot(prefix, 'a')
    delay(monkeypatch, 'repeat')
    log = tmp_path/'timers.jsonl'
    monkeypatch.setenv('EP058_DELAY_LOG', str(log))
    with OfficialClient('p1') as client:
        assert client.snapshot(prefix, 'a') == expected
        assert client.snapshot(prefix, 'a', replay=True) == expected
        assert client.snapshot(prefix, 'b') == expected
        more = prefix + [dict(event_seq=2, protocol='|turn|3')]
        state = client.snapshot(more, 'a')
        assert state['turn'] == 3
        assert state == client.snapshot(more, 'x', replay=True)
        client.drop('a')
        assert client.snapshot(prefix, 'a') == expected
    assert len(log.read_text().splitlines()) >= 6


@pytest.mark.parametrize('mode,pattern', [('hang','deadline'), ('throw','timer callback exception')])
def test_async_failure_is_terminal_and_not_success_metric(monkeypatch, mode, pattern):
    delay(monkeypatch, mode)
    prefix, _ = fixture()
    client = OfficialClient('p1', timeout=1)
    started = time.monotonic()
    with pytest.raises(ObservationError, match=pattern):
        client.snapshot(prefix,'a')
    assert time.monotonic()-started < 4
    assert client.closed and client.process.poll() is not None
    assert not client.metrics and len(client.failures) == 1
    if mode == 'throw':
        node = client.failures[0]['node']
        assert node['stage'] == 'drain' and node['at_queue_end'] is False
        assert node['consumed'] < len(prefix[0]['protocol'].splitlines())
    with pytest.raises(ObservationError, match='closed'):
        client.snapshot(prefix,'a')


def test_serial_pipelined_commands_and_eof_cancellation(monkeypatch):
    delay(monkeypatch)
    prefix, _ = fixture()
    lines = prefix[0]['protocol'].splitlines()
    commands = [dict(op='append',actor='p1',battle_id='a',offset=0,lines=lines),
                dict(op='replay',actor='p1',battle_id='b',lines=lines),
                dict(op='drop',actor='p1',battle_id='a'),
                dict(op='append',actor='p1',battle_id='a',offset=0,lines=lines)]
    proc = subprocess.Popen(['node',str(CLIENT),'serve',str(DEFAULT_BUILD),'p1'],
                            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        proc.stdin.write(''.join(json.dumps(c)+'\n' for c in commands)); proc.stdin.flush()
        responses = [json.loads(proc.stdout.readline()) for _ in commands]
        assert all(r['ok'] for r in responses)
        assert responses[0]['state'] == responses[1]['state'] == responses[3]['state']
        assert responses[2]['state'] is None
        proc.stdin.write(json.dumps(commands[1])+'\n'); proc.stdin.flush()
        time.sleep(.1)
        proc.stdin.close()
        assert proc.wait(timeout=2) == 0
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
        proc.stdout.close()


def test_sixteen_actor_processes_delayed_isolated(monkeypatch):
    prefix, _ = fixture()
    with OfficialClient('p1') as client:
        expected = client.snapshot(prefix,'reference')
    delay(monkeypatch)
    import threading
    barrier = threading.Barrier(16)
    def run(index):
        with OfficialClient('p1') as client:
            barrier.wait(timeout=60)
            result = client.snapshot(prefix, str(index))
            assert result == expected
            assert result == client.snapshot(prefix, str(index), replay=True)
            return client.process.pid
    with ThreadPoolExecutor(max_workers=16) as pool:
        pids = list(pool.map(run,range(16)))
    assert len(set(pids)) == 16
    for pid in pids:
        with pytest.raises(ProcessLookupError): os.kill(pid,0)


def test_local_eight_uses_followup_rows_once_and_rejects_cloud(tmp_path, monkeypatch):
    from contextlib import ExitStack
    from collections import Counter
    import threading
    from integration.pokechamp import team_preview_run as runner, team_preview_study as study
    from integration.pokechamp import distributed_lead as d
    from integration.pokechamp.diagnostics import corrected_lead as auditor
    root = tmp_path/'prepared'
    value = d.prepare(root,experiment_id='EX-045',transport='fake',concurrency=8,local_identity='ep058-local-eight')
    barrier = threading.Barrier(8)
    submitted = []
    def worker(data, root, value, slot, number, **kw):
        assert number == 1 and kw['hard_timeout_seconds'] == 1200
        assert 1700 < kw['cleanup_deadline']-time.time() <= 1740
        submitted.append(slot)
        barrier.wait(timeout=60)
        return dict(slot=slot, slot_id=slot['slot_id'], attempt_id=slot['slot_id']+'-a1',eligible=True,category=None)
    monkeypatch.setattr(auditor,'before_reuse',lambda *args:dict(passed=True))
    with ExitStack() as stack:
        broker = d.Brokers(stack,tmp_path,value)
        runner.execute_schedule(root,tmp_path/'data',value,broker,worker=worker,local_eight=True,
                                gate_check=lambda *args:pytest.fail('local diagnostic cannot create main gate'))
        assert Counter(r['provider_id'] for r in submitted) == {'ollama':4,'zai':4}
        assert {r['slot_id'] for r in submitted} == {r['slot_id'] for r in runner.local_eight_rows(value['schedule'])}
        assert not (root/'first-pair-check.json').exists()
        with pytest.raises(ValueError,match='fake transport'):
            runner.execute_schedule(root,tmp_path/'data',dict(value,transport='cloud'),broker,local_eight=True)


def test_one_deadline_for_repeated_yields(monkeypatch):
    delay(monkeypatch,'repeat')
    prefix, _ = fixture()
    prefix += [dict(event_seq=2,protocol='|turn|3\n|turn|4')]
    client = OfficialClient('p1',timeout=.75)
    started = time.monotonic()
    with pytest.raises(ObservationError,match='deadline'):
        client.snapshot(prefix,'a')
    assert time.monotonic()-started < 3
    assert not client.metrics and client.closed


def test_local_identity_cannot_be_prepared_for_cloud(tmp_path):
    from integration.pokechamp.distributed_lead import prepare
    with pytest.raises(ValueError,match='fake transport'):
        prepare(tmp_path/'cloud',transport='cloud',concurrency=8,experiment_id='EX-045',local_identity='ep058-local-eight')
    assert not (tmp_path/'cloud').exists()
