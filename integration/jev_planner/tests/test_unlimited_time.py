"""Null clocks reach both actors while call budgets, cancellation and finite clocks survive."""
import asyncio,json,math
from types import SimpleNamespace
import pytest
from integration.jev_planner import config,battle,time_limits
from integration.jev_planner.execute import RunBudget,BudgetExceeded
from integration.jev_planner.tests.test_config_cli import source_config
from integration.jev_planner.tests.test_battle import configuration

@pytest.mark.parametrize('battle_limit,total_limit',[(None,None),(None,90),(30,None),(30,90)])
def test_nullable_time_config_and_opponent_window(tmp_path,monkeypatch,battle_limit,total_limit):
    p=source_config(tmp_path,evaluation=dict(kind='trace',fixture=str(config.HERE/'fixtures/demo.json'),limits=dict(battle_seconds=battle_limit,total_seconds=total_limit)))
    cfg=config.load_config(p)
    assert cfg['evaluation']['limits']['battle_seconds']==battle_limit
    assert cfg['evaluation']['limits']['total_seconds']==total_limit
    monkeypatch.setattr(time_limits.time,'monotonic',lambda:100)
    remaining=time_limits.remaining_seconds(total_limit,90)
    window=time_limits.battle_window(battle_limit,remaining)
    assert window==(None if battle_limit is None and total_limit is None else min(math.inf if battle_limit is None else battle_limit,math.inf if total_limit is None else total_limit-10))
    raw=json.loads(json.dumps(dict(watchdog_seconds=window),allow_nan=False))
    expected=math.inf if window is None else 100+window
    assert time_limits.deadline_after(raw['watchdog_seconds'])==expected

@pytest.mark.parametrize('field',['planner_http_attempts','executor_calls','games'])
def test_null_never_removes_count_budgets(tmp_path,field):
    with pytest.raises(config.ConfigurationError):
        config.load_config(source_config(tmp_path,evaluation=dict(limits={field:None})))

@pytest.mark.parametrize('value',[0,-1,True,float('inf'),'unlimited'])
def test_invalid_time_values_stay_rejected(tmp_path,value):
    with pytest.raises(config.ConfigurationError):
        config.load_config(source_config(tmp_path,evaluation=dict(limits=dict(total_seconds=value))))

def test_old_finite_and_unlimited_budget_after_many_hours(monkeypatch):
    now=[10.];monkeypatch.setattr(time_limits.time,'monotonic',lambda:now[0])
    finite=RunBudget(dict(total_seconds=30,planner_http_attempts=2,executor_calls=2))
    unlimited=RunBudget(dict(total_seconds=None,planner_http_attempts=2,executor_calls=2))
    now[0]+=10**6
    with pytest.raises(BudgetExceeded):finite.before_planner(request_id='x',attempt=1)
    assert math.isinf(unlimited.remaining())
    for _ in range(2):unlimited.before_planner(request_id='x',attempt=1);unlimited.before_executor(decision='x')
    with pytest.raises(BudgetExceeded):unlimited.before_planner(request_id='x',attempt=3)
    with pytest.raises(BudgetExceeded):unlimited.before_executor(decision='x')
    assert json.loads(json.dumps(unlimited.summary(),allow_nan=False))['limits']['total_seconds'] is None

def test_session_and_direct_battle_validation_keep_external_clock(tmp_path,monkeypatch):
    cfg=configuration();cfg['evaluation']['limits'].update(total_seconds=None,battle_seconds=None)
    battle.validate_schedule(cfg)
    s=object.__new__(battle.Session);s.config=cfg;s.monotonic_started=0;s.external_remaining=lambda:math.inf
    monkeypatch.setattr(time_limits.time,'monotonic',lambda:10**9)
    assert math.isinf(s.remaining())
    s.external_remaining=lambda:2.;assert s.remaining()==2.
    cfg['evaluation']['limits']['executor_calls']=None
    with pytest.raises(ValueError):battle.validate_schedule(cfg)

@pytest.mark.parametrize('role',['p1','p2'])
@pytest.mark.parametrize('cancel',[False,True])
def test_both_actor_play_loops_no_elapsed_deadline_but_keep_cancel(tmp_path,monkeypatch,role,cancel):
    from integration.pokechamp.jev_study import play
    import poke_env.concurrency as concurrency
    async def bridge(coro):return await coro
    monkeypatch.setattr(concurrency,'handle_threaded_coroutines',bridge)
    monkeypatch.setattr(time_limits,'time',SimpleNamespace(monotonic=lambda:10**9))
    other='p2' if role=='p1' else 'p1';(tmp_path/f'{other}.ready.json').write_text('{}')
    if cancel:(tmp_path/'cancel.json').write_text('{}')
    async def login():return True
    game=SimpleNamespace(player_role=role,won=True,lost=False,turn=3,battle_tag='fixture')
    p=SimpleNamespace(ps_client=SimpleNamespace(logged_in=SimpleNamespace(wait=login)),battles={},n_finished_battles=0)
    async def finish(*_):p.battles={'fixture':game};p.n_finished_battles=1
    p.send_challenges=p.accept_challenges=finish
    async def run():
        call=play(p,role,dict(p1='one',p2='two'),tmp_path,session=None,deadline=time_limits.deadline_after(None))
        if cancel:
            with pytest.raises(RuntimeError,match='peer_failure'):await call
        else:assert (await call)['completed']
    asyncio.run(run())
