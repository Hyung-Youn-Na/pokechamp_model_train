"""EX-078 inheritance isolation and one-round routing (CPU, no real battles)."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from integration.pokechamp.fixed_matchup import first_round as module
from integration.pokechamp.fixed_matchup.storage import atomic, digest, read, sha


def seal(parent):
    files = sorted(p for p in parent.rglob('*') if p.is_file()
                   and p.name not in ('evidence.sha256', 'closure.sha256'))
    (parent / 'evidence.sha256').write_text(''.join(f'{sha(p)}  {p.relative_to(parent)}\n' for p in files))
    (parent / 'closure.sha256').write_text(f"{sha(parent / 'evidence.sha256')}  evidence.sha256\n")


@pytest.fixture
def parent_run(tmp_path, monkeypatch):
    parent, destination = tmp_path / 'parent', tmp_path / 'new'
    for name, payload in {'catalog.json': {'vocabulary': ['fixture']},
            'schedule.json': {'pilot': []}, 'settings.json': module.SETTING,
            'source/a.py': {'source': 'frozen'}, 'teams/A.txt': {'team': 'A'},
            'models/P0.pt': {'initial_weights': True}}.items():
        atomic(parent / name, payload)
    manifest = dict(protocol=deepcopy(module.PARENT_PROTOCOL),
        sources={'a.py': sha(parent / 'source/a.py')},
        files={n: sha(parent / n) for n in ('catalog.json', 'schedule.json')},
        teams={'A': dict(file='A.txt', sha256=sha(parent / 'teams/A.txt'))})
    manifest['identity'] = digest(manifest)
    monkeypatch.setattr(module, 'PARENT_IDENTITY', manifest['identity'])
    atomic(parent / 'manifest.json', manifest)
    atomic(parent / 'models/P0.identity.json', dict(identity=manifest['identity'], sha256=sha(parent / 'models/P0.pt')))
    atomic(parent / 'incomplete.json', dict(status='incomplete', reason='user_requested_stop',
        gpu_released=True, training_games=0, training_updates=0, test_games=0))
    atomic(parent / 'clock.json', {'first': 1})
    seal(parent)

    def prepare(path, *, protocol, schedule):
        for name in ('catalog.json', 'teams/A.txt'):
            atomic(path / name, read(parent / name))
        atomic(path / 'schedule.json', schedule)
        result = dict(protocol=protocol, teams=manifest['teams'], sources={},
                      files={n: sha(path / n) for n in ('catalog.json', 'schedule.json')})
        result['identity'] = digest(result)
        atomic(path / 'manifest.json', result)
        return result
    monkeypatch.setattr(module, 'prepare', prepare)
    return parent, destination


def test_preparation_inherits_only_p0_and_settings(parent_run):
    parent, destination = parent_run
    before = {str(p.relative_to(parent)): sha(p) for p in parent.rglob('*') if p.is_file()}
    manifest = module.prepare_first_round(parent, destination)
    assert manifest['protocol']['test_games'] == manifest['protocol']['dev_games'] == 0
    assert manifest['protocol']['total_seconds'] is None
    assert manifest['protocol']['game_seconds'] is None
    assert all(v is None for v in manifest['protocol']['stage_seconds'].values())
    assert manifest['identity'] == digest({k: v for k, v in manifest.items() if k != 'identity'})
    assert read(destination / 'schedule.json') == module.schedule()
    assert len(module.schedule()['train']) == 1 and len(module.schedule()['train'][0]) == 32
    assert sha(destination / 'models/P0.pt') == sha(parent / 'models/P0.pt')
    for name in ('games', 'claims', 'clock.json', 'benchmarks', 'verification.json', 'models/P0.identity.json'):
        assert not (destination / name).exists()
    assert before == {str(p.relative_to(parent)): sha(p) for p in parent.rglob('*') if p.is_file()}
    assert all(sha(destination / name) == checksum for name, checksum in manifest['files'].items())


@pytest.mark.parametrize('name', ['manifest.json', 'source/a.py', 'models/P0.pt', 'clock.json', 'settings.json'])
def test_corrupt_parent_rejected_before_new_directory(parent_run, name):
    parent, destination = parent_run
    atomic(parent / name, {'corrupt': True})
    with pytest.raises((ValueError, KeyError)):
        module.prepare_first_round(parent, destination)
    assert not destination.exists()


@pytest.mark.parametrize('mutation', ['trained', 'not_stopped', 'wrong_setting', 'nonpilot_claim', 'unsealed_p0'])
def test_unapproved_parent_rejected_after_resealing(parent_run, mutation):
    parent, destination = parent_run
    if mutation == 'trained':
        atomic(parent / 'models/round-001.pt', {})
    elif mutation == 'not_stopped':
        row = read(parent / 'incomplete.json')
        row['reason'] = 'different_reason'
        atomic(parent / 'incomplete.json', row)
    elif mutation == 'wrong_setting':
        atomic(parent / 'settings.json', {'workers': 16, 'batch_size': 64})
    elif mutation == 'nonpilot_claim':
        atomic(parent / 'claims/train.json', {'job': {'stage': 'train'}})
    seal(parent)
    if mutation == 'unsealed_p0':
        path = parent / 'evidence.sha256'
        path.write_text(''.join(line for line in path.read_text().splitlines(True) if not line.endswith('  models/P0.pt\n')))
        (parent / 'closure.sha256').write_text(f'{sha(path)}  evidence.sha256\n')
    with pytest.raises(ValueError):
        module.prepare_first_round(parent, destination)
    assert not destination.exists()


@pytest.fixture
def training_run(tmp_path, monkeypatch):
    import torch
    from integration.pokechamp.fixed_matchup.model import Policy
    from integration.pokechamp.fixed_matchup import finalize
    torch.set_num_threads(1)
    torch.manual_seed(42)
    model = Policy(['fixture'])
    model.save(tmp_path / 'models/P0.pt')
    atomic(tmp_path / 'clock.json', {'first': 123, 'deadline': 999})
    atomic(tmp_path / 'schedule.json', module.schedule())
    original_load = Policy.load
    monkeypatch.setattr(Policy, 'load', lambda path, device='cpu': original_load(path, 'cpu'))
    token = dict(categories=['fixture'], numbers=[0.] * 32)
    observation = dict(schema='fixed-matchup-public-v1', tokens=[token],
                       actions=[dict(id='a', command='move 1', token=token)])
    replay = [dict(id='record1', observation=observation, observation_hash=digest(observation),
                   target=[1.], z=1, terminal_status='completed')]
    rows = [dict(job=j, status='completed', model_hashes={'current': sha(tmp_path / 'models/P0.pt')})
            for j in module.schedule()['train'][0]]
    called = []
    def collect(directory, jobs, teams, models, clock, setting, model_files):
        called.append(('collect', jobs))
        return rows
    monkeypatch.setattr(module, 'run_group', collect)
    monkeypatch.setattr(module.artifacts, 'replay_rows', lambda directory, through_round: replay)
    monkeypatch.setattr(finalize, 'audit_game', lambda path: called.append(('audit', path.name)))
    clock = SimpleNamespace(enter=lambda stage: called.append(('stage', stage)), check=lambda: None)
    return tmp_path, {'identity': 'fixture'}, clock, rows, called, replay


def test_single_round_saves_and_reloads_complete_checkpoint(training_run, monkeypatch):
    directory, manifest, clock, rows, called, replay = training_run
    result = module.train_first_round(directory, manifest, {}, clock, module.SETTING)
    assert result['passed'] and result['round'] == 1 and result['updates'] == 2
    assert result['changed_tensors'] > 0 and result['prediction_max_absolute_error'] <= 1e-5
    assert len([c for c in called if c[0] == 'collect']) == 1
    assert len([c for c in called if c[0] == 'audit']) == 32
    assert sorted(p.name for p in (directory / 'checkpoints').glob('*.pt')) == ['round-000.pt', 'round-001.pt']
    assert not (directory / 'dev').exists() and not (directory / 'evaluation-lock.json').exists()
    monkeypatch.setattr(module.artifacts, 'existing', lambda directory, jobs: (rows, []))
    called.clear()
    resumed = module.train_first_round(directory, manifest, {}, clock, module.SETTING)
    assert resumed == result
    assert not any(c[0] == 'collect' for c in called)


@pytest.mark.parametrize('failure', ['incomplete', 'missing', 'audit'])
def test_failed_round_never_learns_or_creates_round1(training_run, monkeypatch, failure):
    directory, manifest, clock, rows, called, replay = training_run
    if failure == 'incomplete':
        rows[0]['status'] = 'incomplete'
    elif failure == 'missing':
        rows.pop()
    else:
        from integration.pokechamp.fixed_matchup import finalize
        def fail(path):
            raise ValueError('invalid terminal evidence')
        monkeypatch.setattr(finalize, 'audit_game', fail)
    with pytest.raises((RuntimeError, ValueError)):
        module.train_first_round(directory, manifest, {}, clock, module.SETTING)
    assert not (directory / 'checkpoints/round-001.pt').exists()
    assert not (directory / 'checkpoint-validation.json').exists()


@pytest.mark.parametrize('fault', ['unchanged', 'replay_ids', 'prediction'])
def test_checkpoint_validation_rejects_wrong_training_state(training_run, monkeypatch, fault):
    import torch
    from integration.pokechamp.fixed_matchup.model import Policy
    directory, manifest, clock, rows, called, replay = training_run
    module.train_first_round(directory, manifest, {}, clock, module.SETTING)
    payload = torch.load(directory / 'checkpoints/round-001.pt', weights_only=True)
    policy = Policy.load(directory / 'models/round-001.pt')
    if fault == 'unchanged':
        policy = Policy.load(directory / 'models/P0.pt')
    elif fault == 'replay_ids':
        payload['replay_ids'] = ['another_run']
    else:
        original = policy.evaluate_batch
        def wrong(observations):
            predictions = original(observations)
            predictions[0]['value'] += 0.01
            return predictions
        monkeypatch.setattr(policy, 'evaluate_batch', wrong)
    with pytest.raises(ValueError):
        module.validate_checkpoint(directory, manifest, policy, payload, replay)
