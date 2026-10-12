"""Single-slot recovery admission and complete CPU checkpoint-state preservation."""
from copy import deepcopy
import random

import pytest
import torch

from integration.pokechamp.fixed_matchup import first_round_recovery as module, artifacts
from integration.pokechamp.fixed_matchup.storage import atomic, digest, read, sha
from integration.pokechamp.tests.test_fixed_matchup_first_round import seal


@pytest.fixture
def parent_run(tmp_path, monkeypatch):
    parent, destination = tmp_path / 'parent', tmp_path / 'new'
    monkeypatch.setattr(module, 'PARENT_DIRECTORY', parent)
    monkeypatch.setattr(module, 'CRITICAL_SOURCES', ())
    protocol = deepcopy(module.first_round.PROTOCOL)
    protocol.update(game_seconds=1200, total_seconds=28800,
        stage_seconds=dict(verify=3600, pilot=0, train=21600, test=0, finalize=3600))
    for name, data in {'catalog.json': {'vocabulary': ['fixture']},
            'schedule.json': module.first_round.schedule(), 'settings.json': module.first_round.SETTING,
            'source/a.py': {'source': 'fixture'}, 'teams/A.txt': {'team': 'A'},
            'clock.json': dict(start=123., total=28800)}.items():
        atomic(parent / name, data)
    (parent / 'models').mkdir()
    model = dict(weights={'a': torch.tensor([1., 2.])}, vocabulary=['fixture'], config={}, schema='fixture')
    torch.save(model, parent / 'models/P0.pt')
    manifest = dict(protocol=protocol, sources={'a.py': sha(parent / 'source/a.py')},
        files={n: sha(parent / n) for n in ('catalog.json', 'schedule.json')},
        teams={'A': dict(file='A.txt', sha256=sha(parent / 'teams/A.txt'))})
    manifest['identity'] = digest(manifest)
    monkeypatch.setattr(module, 'PARENT_IDENTITY', manifest['identity'])
    atomic(parent / 'manifest.json', manifest)
    p0_hash = sha(parent / 'models/P0.pt')
    atomic(parent / 'models/P0.identity.json', dict(identity=manifest['identity'], sha256=p0_hash))
    atomic(parent / 'incomplete.json', dict(status='incomplete', reason='one_game_wallclock_timeout_before_learning',
        normal_games=31, incomplete_games=1, training_updates=0, checkpoint_round=0,
        original_identity=manifest['identity'], gpu_released=True))
    payload = dict(round=0, updates=0, replay_ids=[], identity=manifest['identity'],
        model=model, optimizer=dict(state={}, param_groups=[{'lr': 0.001, 'params': [0]}]),
        generator=torch.Generator().manual_seed(123).get_state(), torch_rng=torch.get_rng_state(),
        python_rng=random.getstate(), cuda_rng=[torch.Generator().manual_seed(42).get_state()],
        clock=read(parent / 'clock.json'), learning=None)
    (parent / 'checkpoints').mkdir()
    torch.save(payload, parent / 'checkpoints/round-000.pt')
    update_pointer(parent)
    for job in module.first_round.schedule()['train'][0]:
        failed = job['slot_id'] == module.FAILED_SLOT
        artifacts.claim(parent, job)
        artifacts.save_result(parent, dict(job=job, status='incomplete' if failed else 'completed',
            winner=None if failed else 'p1', reason='game/stage deadline or cancellation' if failed else None,
            turns=143 if failed else 10, metrics={'seconds': 1200.1 if failed else 20},
            records=[], evidence={}, roots=[], model_hashes={'current': p0_hash}))
    audited = []
    monkeypatch.setattr(module, 'audit_game', lambda path: audited.append(path.name))
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
    seal(parent)
    return parent, destination, payload, audited


def update_pointer(parent):
    pointer = dict(file='checkpoints/round-000.pt', round=0, sha256=sha(parent / 'checkpoints/round-000.pt'))
    atomic(parent / 'latest.json', pointer)
    atomic(parent / 'checkpoints/round-000.json', pointer)


def test_only_failed_slot_pending_and_every_checkpoint_state_preserved(parent_run):
    parent, destination, payload, audited = parent_run
    before = {str(p.relative_to(parent)): sha(p) for p in parent.rglob('*') if p.is_file()}
    manifest = module.prepare_single_retry(parent, destination)
    rows, pending = artifacts.existing(destination, module.first_round.schedule()['train'][0])
    assert len(rows) == len(audited) == 31
    assert [j['slot_id'] for j in pending] == [module.FAILED_SLOT]
    assert module.FAILED_SLOT not in audited
    assert not (destination / 'games' / module.FAILED_SLOT).exists()
    assert not (destination / 'claims' / (module.FAILED_SLOT + '.json')).exists()
    assert all(not (destination / n).exists() for n in ('incomplete.json', 'completed.json', 'verification.json', 'stages', 'stops'))
    restored = torch.load(destination / 'checkpoints/round-000.pt', weights_only=True)
    assert module._same(restored, dict(payload, identity=manifest['identity'], clock=dict(start=123., total=None)))
    assert manifest['identity'] == digest({k: v for k, v in manifest.items() if k != 'identity'})
    assert all(sha(destination / n) == checksum for n, checksum in manifest['files'].items())
    assert before == {str(p.relative_to(parent)): sha(p) for p in parent.rglob('*') if p.is_file()}
    assert read(destination / 'latest.json')['sha256'] == sha(destination / 'checkpoints/round-000.pt')
    assert read(destination / 'models/P0.identity.json')['identity'] == manifest['identity']


@pytest.mark.parametrize('fault', ['identity', 'count', 'failure', 'model', 'claim', 'unsealed', 'audit', 'source', 'checkpoint', 'replay', 'optimizer', 'rng', 'clock'])
def test_invalid_parent_rejected_before_any_copy(parent_run, monkeypatch, fault):
    parent, destination, payload, audited = parent_run
    failed_path = parent / 'games' / module.FAILED_SLOT / 'result.json'
    normal_path = next(p for p in (parent / 'games').glob('*/result.json') if p != failed_path)
    if fault == 'identity':
        monkeypatch.setattr(module, 'PARENT_IDENTITY', 'wrong')
    elif fault in ('count', 'model', 'claim'):
        path = normal_path if fault != 'claim' else parent / 'claims' / (normal_path.parent.name + '.json')
        row = read(path)
        if fault == 'count':
            row['status'] = 'incomplete'
        elif fault == 'model':
            row['model_hashes'] = {'current': 'wrong'}
        else:
            row['job']['seed_key'] = ['wrong']
        atomic(path, row)
    elif fault == 'failure':
        row = read(failed_path)
        row['reason'] = 'different_failure'
        atomic(failed_path, row)
    elif fault == 'audit':
        def fail(path):
            raise ValueError('bad terminal audit')
        monkeypatch.setattr(module, 'audit_game', fail)
    elif fault == 'source':
        monkeypatch.setattr(module, 'CRITICAL_SOURCES', ('missing.py',))
    elif fault in ('checkpoint', 'replay', 'optimizer', 'rng', 'clock'):
        if fault == 'checkpoint':
            payload['model']['weights']['a'][0] = 999
        elif fault == 'replay':
            payload['replay_ids'] = ['old']
        elif fault == 'optimizer':
            payload['optimizer']['state'] = {0: {'step': 1}}
        elif fault == 'rng':
            del payload['cuda_rng']
        else:
            payload['clock']['start'] = 999
        torch.save(payload, parent / 'checkpoints/round-000.pt')
        update_pointer(parent)
    seal(parent)
    if fault == 'unsealed':
        path = parent / 'evidence.sha256'
        path.write_text(''.join(line for line in path.read_text().splitlines(True) if not line.endswith('  checkpoints/round-000.pt\n')))
        (parent / 'closure.sha256').write_text(f'{sha(path)}  evidence.sha256\n')
    with pytest.raises((ValueError, KeyError)):
        module.prepare_single_retry(parent, destination)
    assert not destination.exists()


def test_runner_submits_exactly_one_retry_and_never_resubmits_it(parent_run, monkeypatch):
    from types import SimpleNamespace
    from integration.pokechamp.fixed_matchup import runner
    parent, destination, payload, audited = parent_run
    module.prepare_single_retry(parent, destination)
    submitted = []
    class Pool:
        def __init__(self, *args, **kwargs):
            assert kwargs['game_seconds'] is None
            self.metrics = {}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def collect(self, jobs, *, on_submit, on_result, check, retain):
            for job in jobs:
                submitted.append(job['slot_id'])
                assert job['deadline'] is None
                on_submit(job)
                on_result(dict(job={k: v for k, v in job.items() if k != 'deadline'},
                    status='incomplete', reason='new failure', turns=1, metrics={}))
    monkeypatch.setattr(runner, 'Pool', Pool)
    clock = SimpleNamespace(stage_end=None, protocol=module.first_round.PROTOCOL, check=lambda: None)
    arguments = (destination, module.first_round.schedule()['train'][0], {}, {}, clock,
                 module.first_round.SETTING, {'current': 'models/P0.pt'})
    rows = runner.run_group(*arguments)
    assert len(rows) == 32 and submitted == [module.FAILED_SLOT]
    runner.run_group(*arguments)
    assert submitted == [module.FAILED_SLOT]
