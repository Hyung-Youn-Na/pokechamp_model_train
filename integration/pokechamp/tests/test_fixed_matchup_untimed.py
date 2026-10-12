"""D-124 CPU regressions; virtual time and fake battles, no experimental collection."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from integration.pokechamp.fixed_matchup import battle, first_round, pool, runner
from integration.pokechamp.fixed_matchup.config import PROTOCOL
from integration.pokechamp.fixed_matchup.runtime import Clock
from integration.pokechamp.fixed_matchup.schedule import matchup, players
from integration.pokechamp.fixed_matchup.storage import atomic, read


def untimed():
    protocol = deepcopy(PROTOCOL)
    protocol.update(total_seconds=None, game_seconds=None,
                    stage_seconds={stage: None for stage in PROTOCOL['stage_seconds']})
    return protocol


def test_unlimited_clock_retains_first_time_and_resources_after_long_elapsed(tmp_path):
    now = [100.]
    clock = Clock(tmp_path, now=lambda: now[0], protocol=untimed())
    checks = []
    clock.resources = lambda: checks.append(now[0])
    assert clock.enter('train') is None
    original = read(tmp_path / 'clock.json')
    now[0] += 10**9
    clock.check()
    assert checks[-1] == now[0]
    resumed = Clock(tmp_path, now=lambda: now[0], protocol=untimed())
    resumed.resources = lambda: None
    assert resumed.first == 100 and resumed.enter('train') is None
    assert read(tmp_path / 'clock.json') == original
    assert read(tmp_path / 'stages/train.json')['start'] == 100
    resumed.cancelled = True
    with pytest.raises(battle.BudgetExpired):
        resumed.check()


def test_unlimited_clock_resource_failure_is_not_disabled(tmp_path):
    clock = Clock(tmp_path, now=lambda: 100., protocol=untimed())
    def fail():
        raise MemoryError('synthetic resource limit')
    clock.resources = fail
    with pytest.raises(MemoryError, match='synthetic resource'):
        clock.enter('train')


@pytest.mark.parametrize('initial,reopen', [(PROTOCOL, untimed()), (untimed(), PROTOCOL)])
def test_clock_cannot_change_frozen_total_budget(tmp_path, initial, reopen):
    Clock(tmp_path, protocol=initial, now=lambda: 100.)
    original = read(tmp_path / 'clock.json')
    with pytest.raises(ValueError, match='total budget'):
        Clock(tmp_path, protocol=reopen, now=lambda: 1000.)
    assert read(tmp_path / 'clock.json') == original


@pytest.mark.parametrize('total,stage,expected', [(None, 10, 110), (20, None, 120), (20, 10, 110)])
def test_finite_stage_or_total_still_expires(tmp_path, total, stage, expected):
    protocol = untimed()
    protocol['total_seconds'] = total
    protocol['stage_seconds']['train'] = stage
    now = [100.]
    clock = Clock(tmp_path, protocol=protocol, now=lambda: now[0])
    clock.resources = lambda: None
    assert clock.enter('train') == expected
    now[0] = expected - .1
    clock.check()
    now[0] = expected
    with pytest.raises(battle.BudgetExpired):
        clock.check()


class FakeSimulator:
    """Two decisions separated by years of virtual elapsed time."""
    now = 100.
    def __init__(self, mode):
        self.steps = 0
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def init(self, teams, seed):
        return self.frame()
    def frame(self):
        observation = {'actions': [{'id': 'a', 'command': 'move 1'}]}
        return dict(ended=self.steps == 2, winner='p1', turn=self.steps,
                    observations={'p1': observation, 'p2': observation}, root={})
    def advance(self, joint):
        self.steps += 1
        FakeSimulator.now += 10**8
        return self.frame()
    def evidence(self):
        return {'synthetic': True}


def install_fake_battle():
    FakeSimulator.now = 100.
    battle.Simulator = FakeSimulator
    battle.time = SimpleNamespace(time=lambda: FakeSimulator.now,
                                  monotonic=lambda: FakeSimulator.now)


def spawned_fake_worker(*args, **kwargs):
    # Spawn imports a clean module: patch inside the child, then use real worker dispatch.
    install_fake_battle()
    pool.worker(*args, **kwargs)


def fake_job(deadline=None):
    return dict(matchup('synthetic', 'untimed', 0, 'A', 'p1',
                       [players('P0', 'policy'), players('P0', 'policy')]), deadline=deadline)


@pytest.mark.parametrize('game_seconds,deadline,status', [
    (None, None, 'completed'), (1200, None, 'incomplete'),
    (None, 150, 'incomplete'), (1200, 150, 'incomplete')])
def test_play_optional_deadlines_with_long_virtual_game(monkeypatch, game_seconds, deadline, status):
    monkeypatch.setattr(battle, 'Simulator', FakeSimulator)
    FakeSimulator.now = 100.
    monkeypatch.setattr(battle, 'time', SimpleNamespace(time=lambda: FakeSimulator.now,
                                                     monotonic=lambda: FakeSimulator.now))
    result = battle.play(fake_job(deadline), {'A': 'fake', 'B': 'fake'}, None,
                         game_seconds=game_seconds)
    assert result['status'] == status, result['reason']
    if status == 'completed':
        assert result['metrics']['seconds'] == 2 * 10**8
    else:
        assert all(r['z'] is None for r in result['records'])


@pytest.mark.parametrize('game_seconds,expected', [(None, 'completed'), (1200, 'incomplete')])
def test_game_budget_reaches_real_spawn_worker(monkeypatch, game_seconds, expected):
    # Construct while patched, then restore parent global before spawning: child uses real worker.
    original = pool.worker
    monkeypatch.setattr(pool, 'worker', spawned_fake_worker)
    workers = pool.Pool({'A': 'fake', 'B': 'fake'}, {}, workers=1, game_seconds=game_seconds)
    monkeypatch.setattr(pool, 'worker', original)
    received = []
    with workers:
        workers.collect([fake_job()], on_submit=lambda job: None, on_result=received.append)
    assert len(received) == 1 and received[0]['status'] == expected, received
    assert all(not process.is_alive() for process in workers.processes)


def test_runner_passes_explicit_unlimited_game_budget(tmp_path, monkeypatch):
    observed = {}
    class FakePool:
        metrics = {}
        def __init__(self, teams, models, **kwargs):
            observed.update(kwargs)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def collect(self, jobs, **kwargs):
            observed['jobs'] = jobs
    monkeypatch.setattr(runner, 'Pool', FakePool)
    clock = SimpleNamespace(stage_end=None, protocol=untimed(), check=lambda: None)
    runner.run_group(tmp_path, [fake_job()], {}, {}, clock,
                     dict(workers=1, batch_size=1), {})
    assert 'game_seconds' in observed and observed['game_seconds'] is None
    assert observed['jobs'][0]['deadline'] is None


def test_only_first_round_protocol_removes_time_limits():
    assert first_round.PROTOCOL['total_seconds'] is None
    assert first_round.PROTOCOL['game_seconds'] is None
    assert all(value is None for value in first_round.PROTOCOL['stage_seconds'].values())
    assert first_round.PROTOCOL['max_rounds'] == 1
    assert first_round.PROTOCOL['round_games'] == 32
    assert first_round.PROTOCOL['dev_games'] == first_round.PROTOCOL['test_games'] == 0
    assert PROTOCOL['total_seconds'] == 86400 and PROTOCOL['game_seconds'] == 1200


def test_stage_alarm_without_total_deadline_still_detects_stage_and_terminal(tmp_path):
    import importlib.util
    from integration.pokechamp.fixed_matchup.config import ROOT
    source = ROOT / 'project_context/exec-plans/evidence/ep128/stage_alarms.py'
    spec = importlib.util.spec_from_file_location('untimed_stage_alarm', source)
    alarms = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(alarms)
    atomic(tmp_path / 'clock.json', dict(start=100, total=None))
    assert alarms.event(tmp_path, True, 10**12) is None
    atomic(tmp_path / 'checkpoint-validation.json', {'passed': True})
    assert alarms.event(tmp_path, True, 10**12)[0] == 'checkpoint'
    assert alarms.event(tmp_path, False, 10**12)[0] == 'terminal'
    atomic(tmp_path / 'clock.json', dict(start=100, total=28800))
    assert alarms.event(tmp_path, True, 10**12)[0] == 'deadline'
