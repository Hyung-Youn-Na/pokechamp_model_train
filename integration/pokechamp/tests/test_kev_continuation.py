"""CPU-only EX-070 question, propagation, immutable comparison and budget tests."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest

from integration.pokechamp import kev_continuation as run, kev_battle, kev_value as v
from integration.pokechamp import kev_player, kev_audit
from integration.pokechamp.branch_rollouts.common import read, write
from integration.pokechamp.joint_q.serializer import JointInput
from integration.pokechamp.tests.test_kev_player import joint, response, http_server


def test_verbatim_question_and_unchanged_state_candidates_and_default(joint):
    before = joint.payload_json
    old = v.request_payload(joint)
    new = v.request_payload(joint, profile=v.CONTINUATION_PROFILE)
    text = ("If we choose this action now, and our side subsequently continues using Kev's current "
            "action-selection policy while the opponent continues using the Abyssal policy, "
            "what is our probability of winning the game?")
    for action in joint.payload['actions']:
        key = action['action_id']
        assert new['questions'][key] == dict(type='noul', instructions=f'Candidate {key} ({v.describe(action)}): {text}')
        assert '\n' not in new['questions'][key]['instructions']
    assert list(new) == ['model', 'state', 'questions']
    assert before == joint.payload_json == old['state'] == new['state']
    assert list(new['questions']) == list(old['questions']) == list(joint.action_ids)
    assert v.request_bytes(old) == v.request_bytes(v.request_payload(joint, profile=v.PROFILE))
    assert kev_audit.expected_request(joint, 'kev-latest', profile=v.CONTINUATION_PROFILE) == new


@pytest.mark.parametrize('profile', [None, '', 'unknown', 'kev-continuation-noul-v2', []])
def test_unknown_profile_rejected_before_transport(joint, profile, monkeypatch):
    monkeypatch.setattr(v.urllib.request, 'build_opener', lambda *a: pytest.fail('transport must not start'))
    for call in (lambda: v.request_payload(joint, profile=profile),
                 lambda: v.validate_input(v.request_payload(joint), profile=profile),
                 lambda: v.request(body=v.request_payload(joint), profile=profile),
                 lambda: kev_battle.session_options(dict(profile=profile))):
        with pytest.raises(ValueError):
            call()


@pytest.mark.parametrize('declared', [v.PROFILE, v.CONTINUATION_PROFILE])
def test_profile_mismatch_and_wording_mutations_rejected(joint, declared):
    other = v.CONTINUATION_PROFILE if declared == v.PROFILE else v.PROFILE
    with pytest.raises(ValueError):
        v.validate_input(v.request_payload(joint, profile=other), profile=declared)
    body = v.request_payload(joint, profile=declared)
    for edit in ('wording', 'order', 'type'):
        changed = copy.deepcopy(body)
        if edit == 'wording':
            changed['questions'][joint.action_ids[0]]['instructions'] += '\n'
        elif edit == 'order':
            changed['questions'] = dict(reversed(list(changed['questions'].items())))
        else:
            changed['questions'][joint.action_ids[0]]['type'] = 'probability'
        with pytest.raises(ValueError):
            v.request_bytes(changed, profile=declared)


def test_worker_session_actual_http_propagates_profile(tmp_path, joint, http_server):
    options = kev_battle.session_options(dict(profile=v.CONTINUATION_PROFILE, request_seconds=600))
    session = kev_player.Session(tmp_path, endpoint=http_server.endpoint, **options)
    body = v.request_payload(joint, profile=v.CONTINUATION_PROFILE)
    http_server.raw = json.dumps(response(joint)).encode()
    try:
        assert asyncio.run(session.evaluate(body, decision='profile-1')) == response(joint)
        assert session.calls == 1
        assert json.loads(http_server.requests[0]['body']) == body
        event = next(row for row in session.records if row['type'] == 'http_request')
        assert event['profile'] == v.CONTINUATION_PROFILE and event['body'] == body
        with pytest.raises(ValueError):
            asyncio.run(session.evaluate(v.request_payload(joint), decision='mismatch'))
        assert session.calls == 1
    finally:
        session.close()
    assert kev_battle.session_options({}) == dict(profile=v.PROFILE, timeout=600)


def test_schedule_and_serving_equal_frozen_ex069_first_match():
    plan = run.configuration()
    baseline = read(run.BASELINE / 'configuration.json')
    assert plan['schedule'] == [baseline['schedule'][0]]
    assert plan['schedule'][0]['game_id'] == 'test-t100817-s0'
    assert plan['teams'] == {key: baseline['teams'][key] for key in baseline['schedule'][0]['teams']}
    assert plan['serving'] == baseline['serving']
    assert plan['tera_allowed'] is True and plan['timer_enabled'] is False
    assert plan['question_sha256'] == hashlib.sha256(plan['question_template'].encode()).hexdigest()
    assert plan['limits'] == dict(games=1, request_seconds=600, battle_seconds=1800, total_seconds=3600,
        cleanup_reserve_seconds=60, concurrency=1, retries=0, fallback=0, recollection=0)


def test_global_admission_prevents_output_directory_reset_and_keeps_clock(tmp_path, monkeypatch):
    monkeypatch.setattr(run, 'ADMISSION', tmp_path / 'global.json')
    for name in ('one', 'two'):
        folder = tmp_path / name
        folder.mkdir()
        write(folder / 'configuration.json', {'registered': True})
    first = run.claim(tmp_path / 'one')
    frozen = run.ADMISSION.read_bytes()
    assert run.collection_deadline(first) == first['monotonic'] + 3540
    with pytest.raises(FileExistsError):
        run.claim(tmp_path / 'two')
    assert run.ADMISSION.read_bytes() == frozen


@pytest.mark.parametrize('change', ['model', 'data', 'serving', 'source'])
def test_unchanged_model_data_and_unrelated_sources_are_mandatory(change):
    baseline = read(run.BASELINE / 'configuration.json')
    plan = dict(run.configuration(), **{key: copy.deepcopy(baseline[key]) for key in
        ('checkpoint', 'data_identity', 'worker_assets', 'source')})
    if change == 'model':
        plan['checkpoint']['files']['head.pt'] = 'changed'
    elif change == 'data':
        plan['data_identity'] = {}
    elif change == 'serving':
        plan['serving']['gpu_index'] = 1
    else:
        name = next(key for key in plan['source'] if '/joint_q/serializer.py' in key)
        plan['source'][name] = 'changed'
    with pytest.raises(ValueError):
        run.compare_identity(plan)


def test_unsupervised_collection_cannot_start_server_or_battle(tmp_path, monkeypatch):
    monkeypatch.setattr(run, 'ADMISSION', tmp_path / 'admission.json')
    write(run.ADMISSION, dict(directory=str(tmp_path), coordinator_pid=-1))
    monkeypatch.setattr(run.control, 'server_identity', lambda: pytest.fail('no GPU/server call'))
    with pytest.raises(ValueError):
        run.collect(tmp_path)


@pytest.mark.parametrize('profile', [v.PROFILE, v.CONTINUATION_PROFILE])
def test_match_transmits_frozen_profile_and_deadline_to_worker(tmp_path, monkeypatch, profile):
    from integration.pokechamp import kev_main, parallel_server
    plan = run.configuration()
    plan['profile'] = profile
    write(tmp_path / 'configuration.json', plan)
    row = plan['schedule'][0]
    captured = []

    class Server:
        def __init__(self, *args):
            self.created, self.process = False, None
        def start(self):
            pass
        def close(self):
            pass

    class Process:
        def __init__(self, args, **kwargs):
            attempt = Path(args[args.index('--attempt')+1])
            actor = args[args.index('--role')+1]
            request = read(attempt / 'request.json')
            captured.append(request)
            seed = row['actor_seeds'][int(actor[-1])-1]
            write(attempt / (actor + '.result.json'), dict(completed=True, actor=actor, turns=35,
                outcome='player_lost' if actor == 'p2' else 'player_won', battle_tag='fake',
                python_random_seed=seed, numpy_random_seed=seed, python_hash_seed=str(seed)))
        def poll(self):
            return 0

    monkeypatch.setattr(parallel_server, 'BattleServer', Server)
    monkeypatch.setattr(kev_main.subprocess, 'Popen', Process)
    monkeypatch.setattr(kev_main, 'process_guard', lambda *a: dict(passed=True))
    monkeypatch.setattr(kev_audit, 'audit', lambda *a: dict(passed=True))
    now = run.time.monotonic()
    result = kev_main._match(tmp_path, plan, row, {'models': {}}, now + 2000,
                             source_provider=lambda: plan['source'])
    assert result['passed'] and len(captured) == 2
    for request in captured:
        assert request['profile'] == profile and request['request_seconds'] == 600
        assert request['slot'] == row
        assert now + 1800 <= request['deadline_monotonic'] < now + 1802
    manifest = read(tmp_path / row['live_directory'] / 'manifest.json')
    assert manifest['profile'] == profile and manifest['global_planned'] == 1


def test_owned_cleanup_preserves_an_unrelated_process():
    import subprocess
    import sys
    import psutil
    args = [sys.executable, '-c', 'import time; time.sleep(30)']
    owned = subprocess.Popen(args, start_new_session=True)
    foreign = subprocess.Popen(args, start_new_session=True)
    try:
        assert run._stop_owned([psutil.Process(owned.pid)]) == []
        owned.wait(timeout=2)
        assert foreign.poll() is None
    finally:
        for process in (owned, foreign):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=2)


def test_startup_deadline_cleans_owned_process_without_attempting_battle(tmp_path, monkeypatch):
    import subprocess
    import sys
    real_popen = subprocess.Popen
    processes = []
    plan = run.configuration()
    write(tmp_path / 'configuration.json', plan)
    monkeypatch.setattr(run, 'ADMISSION', tmp_path / 'global-admission.json')
    monkeypatch.setattr(run, 'verify_prepared', lambda directory: plan)
    monkeypatch.setattr(run, 'gpu_snapshot', lambda: dict(gpu3_apps=[]))
    monkeypatch.setattr(run, 'port_open', lambda: False)
    monkeypatch.setattr(run, 'collection_deadline', lambda admission: admission['monotonic'] - 1)

    def cpu_process(*args, **kwargs):
        process = real_popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
        processes.append(process)
        return process

    monkeypatch.setattr(run.subprocess, 'Popen', cpu_process)
    result = run.run(tmp_path)
    assert len(processes) == 1 and processes[0].poll() is not None
    assert result['execution_error']['type'] == 'TimeoutError'
    assert result['cleanup']['passed'] and not result['passed']
    assert result['attempted'] == result['failed'] == 0 and result['unattempted'] == 1
    assert not (tmp_path / 'battle-started.json').exists()
