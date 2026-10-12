"""Smoke admission and independent transport recording; no real server or GPU."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from integration.pokechamp import kev_control as c, kev_battle as b
from integration.pokechamp.branch_rollouts.common import file_hash, write


def test_registered_team_is_new_and_exact_own_submission():
    from integration.pokechamp.qwen_battle import verify_teams
    from poke_env.teambuilder.constant_teambuilder import ConstantTeambuilder
    config = c.configuration()
    original = json.loads((c.SOURCE / 'manifest.json').read_text())
    assert config['teams']['own']['showdown_team'] == original['own']['text']
    assert ConstantTeambuilder(b.team_submission(config['teams']['own'])).yield_team() == original['own']['packed']
    assert config['teams']['opponent']['number'] not in c.EXCLUDED_TEAMS
    assert config['teams']['opponent']['number'] == 1
    assert verify_teams(config['teams'])['passed']
    assert len(config['schedule']) == 1 and config['schedule'][0]['kev_actor'] == 'p2'
    assert config['tera_allowed'] is True and config['limits']['fallback'] == 0


def proc(tmp_path, **env_updates):
    folder = tmp_path / '12345'
    folder.mkdir()
    argv = ['.venv/bin/python', '-m', 'kev.serve', '--run', 'runs/pokechamp-r1/4b-kev4b-delta', '--port', '8019']
    (folder / 'cmdline').write_bytes('\0'.join(argv).encode() + b'\0')
    env = dict(CUDA_VISIBLE_DEVICES='3', KEV_MERGE='1', KEV_FUSED='1', KEV_API_KEY='secret-test-value')
    env.update(env_updates)
    (folder / 'environ').write_bytes('\0'.join(f'{k}={v}' for k, v in env.items()).encode() + b'\0')
    (folder / 'cwd').symlink_to(c.KEV, target_is_directory=True)
    # Fields after comm start at state (field3); starttime is field22.
    (folder / 'stat').write_text('12345 (python) S ' + ' '.join(['0'] * 18 + ['24680']) + '\n')
    (folder / 'status').write_text('Name:\tpython\nNSpid:\t12345\n')
    (folder / 'ns').mkdir()
    (folder / 'ns/pid').symlink_to('pid:[fake-test-namespace]')
    return folder


def test_server_process_checks_explicit_gpu_merged_fused_and_redacts_credentials(tmp_path):
    proc(tmp_path)
    identity = c._server_process(tmp_path)
    assert identity['pid'] == 12345 and identity['gpu_index'] == 3
    assert identity['start_ticks'] == '24680' and identity['merged'] is True and identity['fused'] is True
    assert identity['cuda_graphs'] == '1'
    assert identity['api_key_present'] and 'secret-test-value' not in json.dumps(identity)


@pytest.mark.parametrize('updates', [dict(CUDA_VISIBLE_DEVICES='0'), dict(CUDA_VISIBLE_DEVICES='1,3'),
                                    dict(KEV_MERGE='0'), dict(KEV_FUSED='0'), dict(KEV_DATE_FACTS='1'),
                                    dict(KEV_LORA_SCALE='0.5'), dict(KEV_DTYPE='fp32'),
                                    dict(KEV_CUDA_GRAPHS='0')])
def test_server_process_rejects_out_of_contract_settings(tmp_path, updates):
    proc(tmp_path, **updates)
    with pytest.raises(ValueError):
        c._server_process(tmp_path)


def admission_fixture(tmp_path, monkeypatch):
    plan = dict(schedule=[dict(kev_actor='p2')], checkpoint={'head': 'immutable'})
    write(tmp_path / 'configuration.json', plan)
    write(tmp_path / 'validation/server-probe.json', {'passed': True})
    server = dict(identity={'pid': 123, 'start_ticks': '42'}, checkpoint=plan['checkpoint'])
    receipt = dict(passed=True, configuration_sha256=file_hash(tmp_path / 'configuration.json'),
                   acceptance_sha256=file_hash(tmp_path / 'validation/server-probe.json'), server=server)
    write(tmp_path / 'probe.json', receipt)
    monkeypatch.setattr(c, 'verify_prepared', lambda path: plan)
    monkeypatch.setattr(c, 'server_identity', lambda: server)
    return plan, server, receipt


def test_battle_requires_same_process_and_complete_prediction_gate(tmp_path, monkeypatch):
    plan, server, receipt = admission_fixture(tmp_path, monkeypatch)
    assert b.admit(tmp_path) == (plan, server)
    receipt['passed'] = False
    write(tmp_path / 'probe.json', receipt)
    with pytest.raises(ValueError, match='gate required'):
        b.admit(tmp_path)
    receipt['passed'] = True
    write(tmp_path / 'probe.json', receipt)
    monkeypatch.setattr(c, 'server_identity', lambda: dict(server, identity={'pid': 123, 'start_ticks': '99'}))
    with pytest.raises(ValueError, match='server changed'):
        b.admit(tmp_path)


def test_altered_acceptance_cannot_admit_smoke(tmp_path, monkeypatch):
    admission_fixture(tmp_path, monkeypatch)
    write(tmp_path / 'validation/server-probe.json', {'passed': True, 'changed': True})
    with pytest.raises(ValueError, match='gate required'):
        b.admit(tmp_path)


def test_transport_instrumentation_captures_unexpected_action_and_actual_send_failure():
    sent, records = [], []

    async def send(message, room='', message_2=None):
        if message == '/choose failed':
            raise OSError('socket closed')
        sent.append((message, room, message_2))

    player = SimpleNamespace(username='kev-one', ps_client=SimpleNamespace(send_message=send))
    b.record_sends(player, SimpleNamespace(record=records.append))
    asyncio.run(player.ps_client.send_message('/choose default', 'battle', '1'))
    asyncio.run(player.ps_client.send_message('/team 123456', 'battle', '2'))
    asyncio.run(player.ps_client.send_message('/utm packed-team'))
    with pytest.raises(OSError):
        asyncio.run(player.ps_client.send_message('/choose failed', 'battle', '3'))
    assert len(sent) == 3
    actions = [r for r in records if r['type'] == 'ps_send']
    assert [r['command'] for r in actions] == ['/choose default', '/team 123456']
    assert [r['request_id'] for r in actions] == ['1', '2']
    assert records[-1]['type'] == 'team_submission' and records[-1]['packed_team'] == 'packed-team'


def test_second_output_cannot_repeat_experiment(tmp_path, monkeypatch):
    admission = tmp_path / 'ex068-admission.json'
    write(admission, {'directory': '/first-output', 'planned': 1})
    monkeypatch.setattr(c, 'BATTLE_ADMISSION', admission)
    second = tmp_path / 'second-output'
    second.mkdir()
    write(second / 'configuration.json', {})
    monkeypatch.setattr(b, 'admit', lambda path: ({}, {}))
    with pytest.raises(FileExistsError):
        b.run(second)
    assert not (second / 'live').exists()


def test_http_readiness_requires_owned_loopback_listener(tmp_path):
    (tmp_path / 'net').mkdir()
    table = tmp_path / 'net/tcp'
    row = '0: 0100007F:1F53 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 987654\n'
    table.write_text('header\n' + row)
    fd = tmp_path / '12345/fd'
    fd.mkdir(parents=True)
    (fd / '3').symlink_to('socket:[987654]')
    assert c._listener_owned(12345, tmp_path) == '987654'
    (fd / '3').unlink()
    (fd / '3').symlink_to('socket:[111111]')
    with pytest.raises(ValueError, match='does not belong'):
        c._listener_owned(12345, tmp_path)
    table.write_text('header\n' + row.replace('0100007F', '00000000'))
    with pytest.raises(ValueError, match='loopback'):
        c._listener_owned(12345, tmp_path)


def test_nvml_namespace_difference_preserves_both_ids_and_refuses_shared_gpu(tmp_path):
    process = dict(pid=12345, namespace_pids=[12345])
    rows = 'GPU-OTHER, 99\nGPU-THREE, 54321\n'
    identity = c._gpu_process_identity(process, 'GPU-THREE', rows, tmp_path)
    assert identity['gpu_process_pid'] == 54321 and identity['gpu_pid_direct_match'] is False
    assert identity['gpu_association'] == 'cuda_env+owned_listener+cuda_ready+exclusive_gpu3'
    with pytest.raises(ValueError, match='exactly one'):
        c._gpu_process_identity(process, 'GPU-THREE', rows + 'GPU-THREE, 333\n', tmp_path)
    (tmp_path / '54321').mkdir()
    with pytest.raises(ValueError, match='different visible'):
        c._gpu_process_identity(process, 'GPU-THREE', rows, tmp_path)
    direct = c._gpu_process_identity(process, 'GPU-THREE', 'GPU-THREE, 12345\n', tmp_path)
    assert direct['gpu_pid_direct_match'] is True


def additional_probe_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'PROBE_ADMISSION', tmp_path / 'original-admission.json')
    monkeypatch.setattr(c, 'FUSED_PROBE_ADMISSION', tmp_path / 'fused-admission.json')
    write(c.PROBE_ADMISSION, {'attempted': 1, 'at': 100})
    plan = dict(authorization={'sha256': 'approval'}, checkpoint={'head': 'same'})
    server = dict(passed=True, identity={'pid': 12, 'start_ticks': '34'}, checkpoint=plan['checkpoint'])
    output = tmp_path / 'first'
    write(output / 'configuration.json', plan)
    write(output / 'validation/prepared.json', {'passed': True})
    return output, plan, server


def test_additional_probe_budget_is_global_and_preserves_original_admission(tmp_path, monkeypatch):
    output, plan, server = additional_probe_fixture(tmp_path, monkeypatch)
    original = c.PROBE_ADMISSION.read_bytes()
    admission = c.claim_probe_admission(output, plan, server)
    assert admission['prior_validation_requests'] == 1 and admission['additional_validation_limit'] == 3
    assert admission['original_probe_admission_sha256'] == file_hash(c.PROBE_ADMISSION)
    assert c.PROBE_ADMISSION.read_bytes() == original
    second = tmp_path / 'second'
    write(second / 'configuration.json', plan)
    write(second / 'validation/prepared.json', {'passed': True})
    with pytest.raises(FileExistsError):
        c.claim_probe_admission(second, plan, server)
    assert json.loads(c.FUSED_PROBE_ADMISSION.read_text()) == admission


@pytest.mark.parametrize(('prediction', 'postcheck'), [('pass', 'pass'), ('fail', 'pass'),
                                                       ('fail', 'error'), ('pass', 'change')])
def test_probe_always_preserves_postcheck_and_original_failure(tmp_path, monkeypatch, prediction, postcheck):
    from integration.pokechamp import kev_acceptance as a
    output, plan, server = additional_probe_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(c, 'verify_prepared', lambda path: plan)
    calls = []

    def identity():
        calls.append(True)
        if len(calls) == 2 and postcheck == 'error':
            raise OSError('postcheck offline')
        if len(calls) == 2 and postcheck == 'change':
            return dict(server, identity={'pid': 13, 'start_ticks': '35'})
        return server

    async def probe(path, *, server_receipt, admission):
        assert server_receipt == server and admission['directory'] == str(output)
        result = dict(passed=prediction == 'pass', attempted_observations=3 if prediction == 'pass' else 1)
        write(output / 'validation/server-probe.json', result)
        if prediction == 'fail':
            raise ValueError('original prediction mismatch')
        return result

    monkeypatch.setattr(c, 'server_identity', identity)
    monkeypatch.setattr(a, 'probe', probe)
    if prediction == 'pass' and postcheck == 'pass':
        assert c.probe(output)['passed']
    else:
        expected = 'original prediction mismatch' if prediction == 'fail' else 'server changed'
        with pytest.raises(ValueError, match=expected):
            c.probe(output)
    receipt = json.loads((output / 'probe.json').read_text())
    assert len(calls) == 2
    assert receipt['passed'] is (prediction == 'pass' and postcheck == 'pass')
    assert receipt['postcheck_passed'] is (postcheck == 'pass')
    assert receipt['cumulative_validation_requests'] == (4 if prediction == 'pass' else 2)
    if prediction == 'fail':
        assert receipt['error']['detail'] == 'original prediction mismatch'
    if postcheck == 'error':
        assert receipt['postcheck_error']['detail'] == 'postcheck offline'


def predecessor_fixture(tmp_path, monkeypatch):
    old, new = tmp_path / 'old', tmp_path / 'new'
    monkeypatch.setattr(c, 'PREDECESSOR', old)
    original = dict(checkpoint={'head': 'fixed'}, data_identity={'dex': 'fixed'}, teams={'own': 'fixed'},
        schedule=[{'seed': 'fixed'}], limits={'games': 1, 'retries': 0},
        source={'integration/pokechamp/kev_control.py': 'old', 'unchanged.py': 'same'},
        created_at=1, server_lifecycle='old')
    current = copy.deepcopy(original)
    current.update(created_at=2, server_lifecycle='new', execution_version='ex068-v3',
                   authorization={'sha256': 'approval'}, serving=c.SERVING)
    current['source'].update({'integration/pokechamp/kev_control.py': 'new', c.DECISION: 'new'})
    write(old / 'configuration.json', original)
    replay = dict(passed=True, source={'inputs': 'same'}, reference={'rows': 'same'},
                  own_team_sha256='same', missing_kinds=[], planned_observations=3, candidates=24, observations=[])
    for index in range(3):
        record = dict(observation_id=f'validation-{index}', request_sha256='same',
            request={'state': 'same', 'questions': {'team_1': 'question'}},
            action_ids=['team_1'], commands={'team_1': '/team 123456'}, development_predictions={'team_1': .25},
            input_generation_seconds=1, audit='same')
        relative = f'observations/{index}.json'
        write(old / 'validation' / relative, record)
        write(new / 'validation' / relative, dict(record, input_generation_seconds=2))
        replay['observations'].append({'record': relative})
    write(old / 'validation/input-replay.json', replay)
    write(new / 'validation/input-replay.json', replay)
    return old, new, current


def test_predecessor_comparison_accepts_only_approved_changes(tmp_path, monkeypatch):
    old, new, plan = predecessor_fixture(tmp_path, monkeypatch)
    result = c.compare_predecessor(new, plan)
    assert result['passed'] and result['changed_sources'] == ['integration/pokechamp/kev_control.py']
    assert result['added_sources'] == [c.DECISION] and len(result['observations']) == 3


@pytest.mark.parametrize('change', ['checkpoint', 'data_identity', 'teams', 'schedule', 'limits',
                                  'source', 'request', 'action_ids', 'commands', 'development_predictions'])
def test_predecessor_drift_cannot_reach_probe(tmp_path, monkeypatch, change):
    old, new, plan = predecessor_fixture(tmp_path, monkeypatch)
    if change in {'checkpoint', 'data_identity', 'teams', 'schedule', 'limits'}:
        plan[change] = {'changed': True}
    elif change == 'source':
        plan['source']['unchanged.py'] = 'changed'
    else:
        path = new / 'validation/observations/0.json'
        record = json.loads(path.read_text())
        record[change] = {'changed': True}
        write(path, record)
    with pytest.raises(ValueError):
        c.compare_predecessor(new, plan)


def approval_fixture(tmp_path, monkeypatch):
    original = tmp_path / '.pokechamp-data/kev/ex068'
    previous = tmp_path / '.pokechamp-data/kev/ex068-v2'
    receipt = tmp_path / '.pokechamp-data/kev/ex068-fused-authorization.json'
    monkeypatch.setattr(c, 'ROOT', tmp_path)
    monkeypatch.setattr(c, 'PREDECESSOR', previous)
    monkeypatch.setattr(c, 'FUSED_AUTHORIZATION', receipt)
    write(original / 'server-owner.json', {'started_at': 100})
    write(previous / 'validation/probe-start.json', {'at': 110})
    write(previous / 'validation/server-probe.json', {'passed': False, 'attempted_observations': 1})
    seals = {}
    for folder in (original, previous):
        seal = folder / 'checksums.sha256'
        seal.write_text(''.join(file_hash(path) + '  ' + str(path.relative_to(folder)) + '\n'
                                for path in sorted(folder.rglob('*.json'))))
        seals[str(seal.relative_to(tmp_path))] = file_hash(seal)
    approval = dict(decision='D-109', additional_validation_limit=3, prior_validation_requests=1,
        global_battle_limit=1, prior_battle_attempts=0, original_failure_preserved=True,
        serving={k: c.SERVING[k] for k in ('merged', 'fused', 'dtype', 'temperature', 'gpu_index')},
        original_server_started_at=100, original_probe_started_at=110, predecessor_files=seals)
    write(receipt, approval)
    monkeypatch.setattr(c, 'AUTHORIZATION_SHA256', file_hash(receipt))
    return original, previous, receipt


@pytest.mark.parametrize('change', ['none', 'approval', 'old_failure', 'old_clock'])
def test_authorization_binds_original_failure_and_sealed_clocks(tmp_path, monkeypatch, change):
    original, previous, receipt = approval_fixture(tmp_path, monkeypatch)
    if change == 'none':
        assert c.authorization()['receipt']['prior_validation_requests'] == 1
        return
    if change == 'approval':
        receipt.write_text(receipt.read_text() + ' ')
    elif change == 'old_failure':
        write(previous / 'validation/server-probe.json', {'passed': True, 'attempted_observations': 0})
    else:
        write(original / 'server-owner.json', {'started_at': 999})
    with pytest.raises(ValueError):
        c.authorization()
