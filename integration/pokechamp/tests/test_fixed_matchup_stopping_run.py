"""EX-079 continuation with real CPU learner state and synthetic collected evidence."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
import torch

from integration.pokechamp.fixed_matchup import artifacts, finalize, model
from integration.pokechamp.fixed_matchup import stopping_run as module
from integration.pokechamp.fixed_matchup.storage import atomic, digest, read, sha


@pytest.fixture
def run_fixture(tmp_path, monkeypatch):
    torch.set_num_threads(1)
    torch.manual_seed(11)
    policy = model.Policy(['fixture'])
    policy.save(tmp_path / 'models/P0.pt')
    token = dict(categories=['fixture'], numbers=[0.] * 32)
    observation = dict(schema='fixed-matchup-public-v1', tokens=[token],
                       actions=[dict(id='a', command='move 1', token=token)])
    replay = [dict(id='sample', observation=observation, observation_hash=digest(observation),
                   target=[1.], z=1, terminal_status='completed')]
    optimizer = torch.optim.AdamW(policy.parameters(), lr=module.PROTOCOL['lr'],
                                 weight_decay=module.PROTOCOL['weight_decay'])
    generator = torch.Generator().manual_seed(1)
    manifest = {'identity': 'synthetic-stopping'}
    atomic(tmp_path / 'clock.json', {'first': 123})
    atomic(tmp_path / 'inheritance.json', {'fixture': True})
    artifacts.save_checkpoint(tmp_path, 0, policy, optimizer, generator,
                              identity=manifest['identity'], replay_ids=[], updates=0)
    learned = model.learn(policy, optimizer, replay, generator=generator, epochs=44, max_steps=44)
    assert learned['steps'] == 44
    artifacts.save_checkpoint(tmp_path, 1, policy, optimizer, generator,
                              identity=manifest['identity'], replay_ids=['sample'], updates=44, learning=learned)
    payload = artifacts.restore_checkpoint(tmp_path, policy, optimizer, generator, identity=manifest['identity'])
    artifacts.publish_round(tmp_path, payload)
    schedules = module.schedule()
    saved, events, fault = {}, [], {}

    def make_rows(jobs, files):
        hashes = {key: sha(tmp_path / file) for key, file in files.items()}
        return [dict(job=deepcopy(job), status='completed', winner='', model_hashes=hashes) for job in jobs]

    for row in make_rows(schedules['train'][0], {'current': 'models/P0.pt'}):
        saved[row['job']['slot_id']] = row

    def existing(directory, jobs):
        return ([saved[job['slot_id']] for job in jobs if job['slot_id'] in saved],
                [job for job in jobs if job['slot_id'] not in saved])

    def collect(directory, jobs, teams, models, clock, setting, files):
        stage, round_id = jobs[0]['stage'], jobs[0]['round_id']
        events.append(('collect', stage, round_id))
        rows = make_rows(jobs, files)
        if fault.get('stage') == stage:
            if fault['kind'] == 'missing':
                rows.pop()
            elif fault['kind'] == 'incomplete':
                rows[0].update(status='incomplete', winner=None)
            elif fault['kind'] == 'hash':
                rows[0]['model_hashes'] = {'current': 'wrong'}
            elif fault['kind'] == 'duplicate':
                rows[-1] = deepcopy(rows[0])
            elif fault['kind'] == 'job':
                rows[0]['job']['seed_key'] = ['unexpected-seed']
        for row in rows:
            slot = row['job']['slot_id']
            saved[slot] = row
            atomic(tmp_path / 'games' / slot / 'result.json', row)
        return rows

    def audit(path):
        row = saved[path.name]
        events.append(('audit', row['job']['stage'], row['job']['round_id']))
        if fault.get('kind') == 'audit' and fault['stage'] == row['job']['stage']:
            raise ValueError('synthetic terminal evidence corruption')
        return row, {}

    original_learn = model.learn
    def learn(*args, **kwargs):
        events.append(('learn',))
        return original_learn(*args, **kwargs)

    monkeypatch.setattr(artifacts, 'existing', existing)
    monkeypatch.setattr(artifacts, 'replay_rows', lambda directory, through_round: replay)
    monkeypatch.setattr(module, 'run_group', collect)
    monkeypatch.setattr(finalize, 'audit_game', audit)
    monkeypatch.setattr(model, 'learn', learn)
    clock = SimpleNamespace(check=lambda: None, enter=lambda stage: None)
    def run():
        return module.policy_phase(tmp_path, manifest, {}, schedules, policy, clock, module.SETTING, device='cpu')
    return SimpleNamespace(directory=tmp_path, run=run, saved=saved, events=events, fault=fault,
                           replay=replay, schedules=schedules)


def test_normal_plateau_stops_at12_selects_round1_and_resume_never_retrains(run_fixture):
    f = run_fixture
    selected = f.run()
    assert selected['round'] == 1
    assert selected['sha256'] == sha(f.directory / 'models/round-001.pt')
    stop = read(f.directory / 'training-stop.json')
    assert stop['state']['round'] == 12 and stop['state']['reason'] == 'plateau'
    assert len([e for e in f.events if e[0] == 'learn']) == 11
    assert [e[2] for e in f.events if e[:2] == ('collect', 'train')] == list(range(2, 13))
    assert [e[2] for e in f.events if e[:2] == ('collect', 'dev')] == [1, 4, 8, 12]
    before = {str(p.relative_to(f.directory)): sha(p) for p in f.directory.rglob('*') if p.is_file()}
    f.events.clear()
    assert f.run() == selected
    assert not any(e[0] in ('learn', 'collect') for e in f.events)
    assert before == {str(p.relative_to(f.directory)): sha(p) for p in f.directory.rglob('*') if p.is_file()}


@pytest.mark.parametrize('stage', ['dev', 'train'])
@pytest.mark.parametrize('kind', ['missing', 'incomplete', 'hash', 'duplicate', 'job', 'audit'])
def test_incomplete_corrupt_or_unaudited_group_never_learns_or_selects(run_fixture, stage, kind):
    f = run_fixture
    f.fault.update(stage=stage, kind=kind)
    with pytest.raises((RuntimeError, ValueError)):
        f.run()
    assert not any(e[0] == 'learn' for e in f.events)
    assert not (f.directory / 'selection.json').exists()
    assert not (f.directory / 'evaluation-lock.json').exists()
    assert not (f.directory / 'checkpoints/round-002.pt').exists()


def test_existing_failed_reservation_forbids_collecting_remaining_group(run_fixture):
    f = run_fixture
    job = f.schedules['dev']['1'][0]
    f.saved[job['slot_id']] = dict(job=job, status='incomplete', winner=None)
    with pytest.raises(RuntimeError, match='reserved'):
        f.run()
    assert not any(e[0] in ('learn', 'collect') for e in f.events)


@pytest.mark.parametrize('name', ['selection.json', 'training-stop.json', 'evaluation-lock.json'])
def test_premature_selection_or_test_lock_fails_closed(run_fixture, name):
    f = run_fixture
    atomic(f.directory / name, {'pretend': 'stopped'})
    with pytest.raises(ValueError, match='without a normal stopping'):
        f.run()
    assert not any(e[0] in ('learn', 'collect') for e in f.events)


def test_resume_rejects_tampered_dev_score_selection_and_selected_weights(run_fixture):
    f = run_fixture
    selected = f.run()
    f.events.clear()
    path = f.directory / 'dev/round-004.json'
    original = read(path)
    atomic(path, dict(original, score=.99))
    with pytest.raises(ValueError, match='authoritative games'):
        f.run()
    atomic(path, original)
    atomic(f.directory / 'selection.json', dict(selected, round=4))
    with pytest.raises(ValueError, match='selected checkpoint changed'):
        f.run()
    atomic(f.directory / 'selection.json', selected)
    payload = torch.load(f.directory / selected['file'], weights_only=True)
    next(iter(payload['weights'].values())).add_(1)
    torch.save(payload, f.directory / selected['file'])
    with pytest.raises(ValueError, match='published policy disagrees'):
        f.run()
    assert not any(e[0] in ('learn', 'collect') for e in f.events)


def test_resume_rejects_missing_development_prerequisite(run_fixture):
    f = run_fixture
    f.run()
    (f.directory / 'dev/round-004.json').unlink()
    f.events.clear()
    with pytest.raises(ValueError):
        f.run()
    assert not any(e[0] in ('learn', 'collect') for e in f.events)


def test_resume_finishes_current_dev_commit_without_retraining_or_recollection(run_fixture):
    f = run_fixture
    selected = f.run()
    # A crash can occur after all round12 evaluation games, before its dev commit.
    for name in ('dev/round-012.json', 'training-stop.json', 'selection.json'):
        (f.directory / name).unlink()
    f.events.clear()
    assert f.run() == selected
    assert read(f.directory / 'training-stop.json')['state']['round'] == 12
    assert not any(e[0] in ('learn', 'collect') for e in f.events)
