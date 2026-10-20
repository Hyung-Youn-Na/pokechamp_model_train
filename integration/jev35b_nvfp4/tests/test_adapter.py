import asyncio
import copy
import hashlib
import json

import pytest

from integration.jev35b_nvfp4 import formatting as f
from integration.jev35b_nvfp4.config import MODEL_ID, engine_command
from integration.jev_planner.config import model_spec
from integration.jev_planner.runtime import validate_resources
from integration.jev27b.server import LocalService


def payload():
    return dict(state={'turn': 7, 'strategy': {'objective': 'preserve ☃', 'age': 2}}, questions={
        'action': dict(type='choice', instructions='Check goals\nThen act.', criteria={
            'move_9': dict(display_name='Lokix — U-turn', nested={'slot': 9}),
            'switch_2': dict(display_name='Switch to Pecharunt', slot=2)})})


def response(p):
    options = f.choice_request(p)['options']
    return dict(kind='choice', model=MODEL_ID, options=options, probabilities=[.25, .75],
                choice_index=1, choice=options[1], num_model_requests=1,
                usage=dict(prompt_tokens=123, completion_tokens=1))


def test_lossless_options_state_instructions_and_readout():
    p = payload(); frozen = copy.deepcopy(p)
    request = f.choice_request(p)
    assert request['state'] == p['state'] and request['question'] == p['questions']['action']['instructions']
    assert [json.loads(v) for v in request['options']] == [{k:v} for k,v in p['questions']['action']['criteria'].items()]
    mapped = f.mapped_response(p, response(p))
    assert mapped['answers']['action']['choice'] == 'switch_2'
    assert list(mapped['answers']['action']['probabilities']) == ['move_9', 'switch_2']
    assert mapped['usage']['output_tokens'] == 1 and p == frozen


@pytest.mark.parametrize('change', [dict(choice_index=0), dict(options=['changed']),
    dict(num_model_requests=2), dict(thinking={'used': True}), dict(model='other'),
    dict(usage=dict(prompt_tokens=100, completion_tokens=0))])
def test_reject_drift(change):
    p = payload()
    with pytest.raises(ValueError): f.mapped_response(p, dict(response(p), **change))


def test_profile_interpreter_and_frozen_engine_flags():
    spec = model_spec('jev35b-nvfp4')
    assert 'jev35b-nvfp4-runtime' in spec['python']
    assert 'jev27b-runtime' in model_spec('jev9b')['python']
    cfg = dict(executor={'model':'jev35b-nvfp4'}, evaluation={'resources':dict(
        gpu_indices=[0], **{k:spec[k] for k in ('allocator_bytes','gpu_bytes','host_bytes','disk_bytes')})})
    assert validate_resources(cfg)['revision'] == '10c2c62610e315e31a75baca849ad79d526e4658'
    cmd = engine_command()
    for key,val in [('--moe-backend','marlin'),('--max-lora-rank','320'),('--max-model-len','32769'),
                    ('--tensor-parallel-size','1'),('--max-num-seqs','1')]:
        assert cmd[cmd.index(key)+1] == val
    assert '--enforce-eager' in cmd


def test_retransmission_of_official_response_keeps_one_engine_call(tmp_path):
    class FakeOfficial:
        calls = 0
        def metadata(self): return dict(model=MODEL_ID, revision='revision', loaded=True, serving_identity='a'*64)
        def validate_input(self,p): f.choice_request(p)
        def evaluate(self,p):
            self.calls += 1
            return f.mapped_response(p, response(p))
    model = FakeOfficial()
    service = LocalService(model,tmp_path,model_id=MODEL_ID,revision='revision',validate_before_inference=True)
    raw = json.dumps(dict(model=MODEL_ID,**payload())).encode()
    kwargs = dict(request_id='repeat',body_sha256=hashlib.sha256(raw).hexdigest(),expected_identity='a'*64)
    try:
        a = service.evaluate(raw, **kwargs); b = service.evaluate(raw, **kwargs)
        assert a[:2] == b[:2] and not a[2] and b[2] and model.calls == 1
    finally: service.close()


def test_preflight_budget_reserves_eight_and_stops_before_battle(tmp_path):
    from integration.jev35b_nvfp4.preflight import run_preflight
    from integration.jev_planner.execute import RunBudget
    p = payload(); cfg = {'evaluation': {'executor_preflight': {'data': {'requests':[
        {'case':str(i),'payload':p} for i in range(8)]}}}}
    async def executor(p, *, decision): return f.mapped_response(p, response(p))
    budget = RunBudget(dict(total_seconds=4200,executor_calls=256))
    asyncio.run(run_preflight(cfg,executor,tmp_path,before_executor=budget.before_executor))
    assert budget.executor_calls == 8
    assert json.loads((tmp_path/'preflight.json').read_text())['passed']


def test_failed_preflight_preserves_reservation_and_never_returns_pass(tmp_path):
    from integration.jev35b_nvfp4.preflight import run_preflight
    from integration.jev_planner.execute import RunBudget
    p=payload();cfg={'evaluation':{'executor_preflight':{'data':{'requests':[
        {'case':str(i),'payload':p} for i in range(8)]}}}}
    calls=0
    async def executor(p, *, decision):
        nonlocal calls
        calls+=1
        if calls==3: raise RuntimeError('engine stopped')
        return f.mapped_response(p,response(p))
    budget=RunBudget(dict(total_seconds=4200,executor_calls=256))
    with pytest.raises(RuntimeError,match='engine stopped'):
        asyncio.run(run_preflight(cfg,executor,tmp_path,before_executor=budget.before_executor))
    saved=json.loads((tmp_path/'preflight.json').read_text())
    assert saved['passed'] is False and saved['preflight_reservations']==3
    assert saved['completed_preflight_responses']==2 and budget.executor_calls==3


def test_engine_failure_raw_body_is_kept_before_mapping(tmp_path):
    import httpx
    from integration.jev35b_nvfp4.model import OfficialModel
    model=OfficialModel();model.directory=tmp_path
    p=payload()
    model.validate_input=lambda p:(f.format_request(p),{'input_ids':[1]*123})
    model.client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(500,text='original failure body')),
                             base_url='http://127.0.0.1:18846')
    try:
        with pytest.raises(httpx.HTTPStatusError):model.evaluate(p)
        records=[json.loads(l) for l in (tmp_path/'engine-transport.jsonl').read_text().splitlines()]
        assert records[0]['body']==f.choice_request(p)
        assert records[1]['raw_body']=='original failure body' and records[1]['status_code']==500
    finally:model.client.close()


def test_frontend_keeps_gpu_lock_and_monitor_without_importing_cuda(tmp_path, monkeypatch):
    import builtins
    import fcntl
    from integration.jev27b import resource
    events=[]
    facts={0:dict(uuid='GPU-00000000-0000-0000-0000-000000000001',memory_used_mib=0,utilization_percent=0)}
    class Monitor:
        def __init__(self,*args,**kwargs):pass
        def __enter__(self):events.append('monitor_start')
        def __exit__(self,*args):events.append('monitor_stop')
    monkeypatch.setattr(resource,'ROOT',tmp_path)
    monkeypatch.setattr(resource,'gpu_facts',lambda:facts)
    monkeypatch.setattr(resource,'gpu_compute_processes',lambda:[])
    monkeypatch.setattr(resource,'ResourceMonitor',Monitor)
    monkeypatch.setattr(resource,'_stop_on_parent_exit',lambda:None)
    original_import=builtins.__import__
    def no_torch(name,*args,**kwargs):
        if name=='torch':raise AssertionError('journal frontend must not initialize CUDA')
        return original_import(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',no_torch)
    lock=tmp_path/'.pokechamp-data/locks/gpu0.lock'
    with resource.own_gpus(tmp_path/'serving',profile='planner-ex095',initialize_cuda=False) as owned:
        assert owned==facts and events==['monitor_start']
        with lock.open('a+') as handle:
            with pytest.raises(BlockingIOError):fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert events==['monitor_start','monitor_stop']
    with lock.open('a+') as handle:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert len(list((tmp_path/'serving').glob('gpu-acquire-*.json')))==1
    assert len(list((tmp_path/'serving').glob('gpu-release-*.json')))==1


@pytest.mark.parametrize('policy,passes',[(None,False),('strict',False),('probability_diagnostic',True)])
def test_probability_drift_policy_is_explicit_and_preserves_old_strict(tmp_path,policy,passes):
    from integration.jev35b_nvfp4.preflight import run_preflight
    from integration.jev_planner.execute import RunBudget
    p=payload();evaluation={'executor_preflight':{'data':{'requests':[{'case':str(i),'payload':p} for i in range(8)]}}}
    if policy is not None:evaluation['executor_repeat_policy']=policy
    calls=0
    async def executor(p, *, decision):
        nonlocal calls
        calls+=1
        r=response(p)
        if calls==8:r['probabilities']=[.26,.74]
        return f.mapped_response(p,r)
    budget=RunBudget(dict(total_seconds=4200,executor_calls=256))
    if passes:asyncio.run(run_preflight({'evaluation':evaluation},executor,tmp_path,before_executor=budget.before_executor))
    else:
        with pytest.raises(ValueError,match='repeated inference gate failed'):
            asyncio.run(run_preflight({'evaluation':evaluation},executor,tmp_path,before_executor=budget.before_executor))
    saved=json.loads((tmp_path/'preflight.json').read_text());assert saved['passed'] is passes and budget.executor_calls==8
    if passes:
        assert saved['choice_equal'] is True and saved['probability_within_tolerance'] is False
        assert saved['max_probability_delta']==pytest.approx(.01)


def test_diagnostic_probability_policy_still_blocks_changed_choice(tmp_path):
    from integration.jev35b_nvfp4.preflight import run_preflight
    from integration.jev_planner.execute import RunBudget
    p=payload();cfg={'evaluation':{'executor_repeat_policy':'probability_diagnostic','executor_preflight':{'data':{'requests':[{'case':str(i),'payload':p} for i in range(8)]}}}}
    count=0
    async def executor(p, *, decision):
        nonlocal count
        count+=1;r=response(p)
        if count==8:r.update(probabilities=[.8,.2],choice_index=0,choice=r['options'][0])
        return f.mapped_response(p,r)
    budget=RunBudget(dict(total_seconds=4200,executor_calls=256))
    with pytest.raises(ValueError,match='gate failed'):
        asyncio.run(run_preflight(cfg,executor,tmp_path,before_executor=budget.before_executor))
    assert not json.loads((tmp_path/'preflight.json').read_text())['passed']


def test_unknown_repeat_policy_is_rejected_before_any_inference(tmp_path):
    from integration.jev35b_nvfp4.preflight import run_preflight
    async def no_call(*args,**kwargs):raise AssertionError('must not infer')
    with pytest.raises(ValueError,match='unsupported'):
        asyncio.run(run_preflight({'evaluation':{'executor_repeat_policy':'typo'}},no_call,tmp_path,before_executor=lambda **k:None))
