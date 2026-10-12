"""EX-079 CPU inheritance admission, immutable provenance and full-state retention."""
from copy import deepcopy
import random

import pytest
import torch

from integration.pokechamp.fixed_matchup import artifacts, stopping_prepare as module
from integration.pokechamp.fixed_matchup.storage import atomic, digest, read, sha
from integration.pokechamp.tests.test_fixed_matchup_first_round import seal


@pytest.fixture
def parent_run(tmp_path, monkeypatch):
    parent, destination = tmp_path / 'parent', tmp_path / 'child'
    monkeypatch.setattr(module, 'PARENT_DIRECTORY', parent)
    monkeypatch.setattr(module, 'CRITICAL_SOURCES', ())
    for name, value in {'catalog.json': {'vocabulary': ['fixture']},
            'schedule.json': module.first_round.schedule(), 'settings.json': module.first_round.SETTING,
            'clock.json': {'start': 123., 'total': None}, 'teams/A.txt': {'team': 'A'},
            'source/a.py': {'frozen': True}}.items():
        atomic(parent / name, value)
    manifest = dict(protocol=deepcopy(module.first_round.PROTOCOL),
        sources={'a.py': sha(parent / 'source/a.py')},
        files={n: sha(parent / n) for n in ('catalog.json', 'schedule.json')},
        teams={'A': dict(file='A.txt', sha256=sha(parent / 'teams/A.txt'))})
    manifest['identity'] = digest(manifest)
    monkeypatch.setattr(module, 'PARENT_IDENTITY', manifest['identity'])
    atomic(parent / 'manifest.json', manifest)
    (parent / 'models').mkdir()
    p0 = dict(weights={str(i): torch.tensor([1., 2.]) for i in range(59)}, vocabulary=['fixture'], config={}, schema='fixture')
    model = deepcopy(p0)
    for tensor in model['weights'].values():
        tensor.add_(1)
    torch.save(p0, parent / 'models/P0.pt')
    torch.save(model, parent / 'models/round-001.pt')
    p0_hash = sha(parent / 'models/P0.pt')
    atomic(parent / 'models/P0.identity.json', dict(identity=manifest['identity'], sha256=p0_hash))
    ids = []
    for number, job in enumerate(module.first_round.schedule()['train'][0]):
        records = [dict(id=f'{number}-{i}', submitted=True, mode='search', terminal_status='completed')
                   for i in range(172 if number == 31 else 170)]
        # 31*170 +166 =5436, keep records in schedule/lexical slot order.
        if number == 31:
            records = records[:166]
        artifacts.claim(parent, job)
        artifacts.save_result(parent, dict(job=job, status='completed', winner='p1', turns=10,
            records=records, evidence={}, roots=[], metrics={}, model_hashes={'current': p0_hash}))
        ids.extend(r['id'] for r in records)
    audited = []
    monkeypatch.setattr(module, 'audit_game', lambda path: audited.append(path.name))
    payloads = []
    (parent / 'checkpoints').mkdir()
    for number in (0, 1):
        payload = dict(round=number, updates=44 if number else 0, replay_ids=ids if number else [],
            identity=manifest['identity'], model=model if number else p0,
            optimizer=dict(state={i: {'step': torch.tensor(44.)} for i in range(59)} if number else {}, param_groups=[]),
            generator=torch.Generator().manual_seed(123).get_state(), torch_rng=torch.get_rng_state(),
            python_rng=random.getstate(), cuda_rng=[torch.Generator().manual_seed(42).get_state()],
            clock=read(parent / 'clock.json'), learning={'steps': 44, 'metrics': []} if number else None)
        torch.save(payload, parent / f'checkpoints/round-{number:03d}.pt')
        payloads.append(payload)
    update_pointers(parent)
    atomic(parent / 'training/round-001.json', payloads[1]['learning'])
    atomic(parent / 'checkpoint-validation.json', dict(identity=manifest['identity'], passed=True, finite=True,
        round=1, updates=44, changed_tensors=59, optimizer_states=59, observations=5436,
        checkpoint=read(parent / 'latest.json'), p0_sha256=p0_hash, model_sha256=sha(parent / 'models/round-001.pt'),
        replay_ids_sha256=digest(ids), learning=payloads[1]['learning']))
    atomic(parent / 'completed.json', dict(identity=manifest['identity'], procedure_complete=True,
        diagnostic_complete=True, audit=dict(passed=True, normal_games=32, games=32, decisions=5436)))
    def prepare(path, *, protocol, schedule):
        for name in ('catalog.json', 'teams/A.txt'):
            atomic(path / name, read(parent / name))
        atomic(path / 'schedule.json', schedule)
        child = dict(protocol=protocol, teams=manifest['teams'], sources={},
            files={n: sha(path / n) for n in ('catalog.json', 'schedule.json')})
        child['identity'] = digest(child)
        atomic(path / 'manifest.json', child)
        return child
    monkeypatch.setattr(module, 'prepare', prepare)
    seal(parent)
    return parent, destination, payloads, audited


def update_pointers(parent):
    for number in (0, 1):
        file = f'checkpoints/round-{number:03d}.pt'
        pointer = dict(file=file, round=number, sha256=sha(parent / file))
        atomic(parent / f'checkpoints/round-{number:03d}.json', pointer)
    atomic(parent / 'latest.json', pointer)


def test_complete_checkpoint_and_parent_bytes_preserved(parent_run):
    parent, destination, payloads, audited = parent_run
    before = {str(p.relative_to(parent)): sha(p) for p in parent.rglob('*') if p.is_file()}
    manifest = module.prepare_stopping(parent, destination)
    assert len(audited) == 32
    assert manifest['identity'] == digest({k: v for k, v in manifest.items() if k != 'identity'})
    assert all(sha(destination / n) == checksum for n, checksum in manifest['files'].items())
    assert 'latest.json' not in manifest['files']
    for number, payload in enumerate(payloads):
        restored = torch.load(destination / f'checkpoints/round-{number:03d}.pt', weights_only=True)
        assert module._same(restored, dict(payload, identity=manifest['identity']))
    assert artifacts.committed_pointer(destination)['round'] == 1
    assert len(artifacts.replay_rows(destination, 1)) == 5436
    assert before == {str(p.relative_to(parent)): sha(p) for p in parent.rglob('*') if p.is_file()}
    assert not any((destination / n).exists() for n in ('completed.json', 'verification.json', 'evaluation-lock.json', 'resource.json'))
    assert read(destination / 'inheritance.json')['inherited_updates'] == 44


@pytest.mark.parametrize('fault', ['identity', 'incomplete', 'source', 'unsealed', 'claim', 'audit',
    'model', 'updates', 'optimizer', 'rng', 'clock', 'replay', 'nan', 'validation', 'checkpoint0'])
def test_rejects_bad_parent_before_creating_child(parent_run, monkeypatch, fault):
    parent, destination, payloads, audited = parent_run
    payload = payloads[1]
    if fault == 'identity':
        monkeypatch.setattr(module, 'PARENT_IDENTITY', 'wrong')
    elif fault == 'source':
        monkeypatch.setattr(module, 'CRITICAL_SOURCES', ('missing.py',))
    elif fault == 'incomplete':
        atomic(parent / 'incomplete.json', {'reason': 'failed'})
    elif fault == 'claim':
        path = next((parent / 'claims').glob('*.json'))
        row = read(path)
        row['job']['seed_key'] = ['wrong']
        atomic(path, row)
    elif fault == 'audit':
        def fail(path):
            raise ValueError('audit failure')
        monkeypatch.setattr(module, 'audit_game', fail)
    elif fault == 'validation':
        row = read(parent / 'checkpoint-validation.json')
        row['passed'] = False
        atomic(parent / 'checkpoint-validation.json', row)
    elif fault not in ('unsealed',):
        if fault == 'model':
            payload['model']['weights']['0'][0] = 999
        elif fault == 'updates':
            payload['updates'] = 43
        elif fault == 'optimizer':
            payload['optimizer']['state'].pop(0)
        elif fault == 'rng':
            del payload['cuda_rng']
        elif fault == 'clock':
            payload['clock']['start'] = 999
        elif fault == 'replay':
            payload['replay_ids'].reverse()
        elif fault == 'nan':
            payload['optimizer']['state'][0]['step'] = torch.tensor(float('nan'))
        elif fault == 'checkpoint0':
            payloads[0]['updates'] = 1
            torch.save(payloads[0], parent / 'checkpoints/round-000.pt')
        torch.save(payload, parent / 'checkpoints/round-001.pt')
        update_pointers(parent)
    seal(parent)
    if fault == 'unsealed':
        path = parent / 'evidence.sha256'
        path.write_text(''.join(line for line in path.read_text().splitlines(True)
                               if not line.endswith('  checkpoints/round-001.pt\n')))
        (parent / 'closure.sha256').write_text(f'{sha(path)}  evidence.sha256\n')
    with pytest.raises((ValueError, KeyError)):
        module.prepare_stopping(parent, destination)
    assert not destination.exists()
