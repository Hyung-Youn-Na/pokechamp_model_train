"""Response format recovery preserves raw attempts and the shared physical budget."""
import asyncio
import json
import httpx
import pytest
from integration.jev_planner import config as settings
from integration.jev_planner.core import PlanOutputError
from integration.jev_planner.planner import ZaiPlannerClient, PlannerTransportError
from integration.jev_planner.tests.test_planner import response, config
from integration.jev_planner.tests.test_config_cli import source_config
from integration.jev_planner.execute import RunBudget, BudgetExceeded


def client(handler, **kw):
    cfg = config() | dict(temperature=0, json_retries=5, retry_scope='response_format')
    return ZaiPlannerClient(cfg, api_key='synthetic', base_url='https://example.test/api/v4',
        transport=httpx.MockTransport(handler), environ={}, **kw)


def extra_note():
    value=json.loads(response().json()['choices'][0]['message']['content'])
    value['contingencies']=[dict(if_='a')]
    value['contingencies']=[{'if':'a','then':'b','note':''}]
    return response(content=json.dumps(value))


@pytest.mark.parametrize('bad', [lambda:response(content='{'), lambda:response(content='{}'),
    lambda:response(content=''), lambda:response(reason='length'),
    lambda:response(content='{"objective":"a","objective":"b"}'),
    lambda:response(content='{"x":NaN}'), extra_note,
    lambda:httpx.Response(200,text='invalid envelope'),
    lambda:httpx.Response(200,json={'choices':[], 'usage':{'prompt_tokens':17}})])
def test_format_error_then_success_exact_input_and_usage(bad):
    async def run():
        sent=[];records=[]
        def handler(req):
            sent.append(req.content)
            return bad() if len(sent)==1 else response()
        async with client(handler,record=records.append) as p:
            result=await p.plan([dict(role='user',content='frozen input')],request_id='d1')
        assert len(sent)==2 and sent[0]==sent[1]
        assert json.loads(sent[0])['temperature']==0
        assert result['plan'] and result['http_attempts']==2
        attempts=[r for r in records if r['type']=='planner_output_attempt']
        assert len(attempts)==2 and not attempts[0]['format_valid'] and attempts[1]['format_valid']
        assert sum(r['type'] in ('planner_json_retry','planner_format_retry') for r in records)==1
        transport=[r for r in records if r['type']=='planner_transport']
        assert transport[0]['response_body'] and transport[1]['usage']['prompt_tokens']==20
        if transport[0]['usage'] is not None:
            assert attempts[0]['usage']==transport[0]['usage']
    asyncio.run(run())


@pytest.mark.parametrize('envelope',[False,True])
def test_exhaustion_is_six_total_never_nested(envelope):
    async def run():
        sent=[];events=[]
        def handler(req):
            sent.append(req.content)
            return httpx.Response(200,text='bad') if envelope else extra_note()
        async with client(handler,record=events.append) as p:
            if envelope:
                with pytest.raises(PlanOutputError):await p.plan([dict(role='user',content='x')],request_id='d1')
            else:
                result=await p.plan([dict(role='user',content='x')],request_id='d1')
                assert result['plan'] is None
        assert len(sent)==6 and len(set(sent))==1
        assert sum(r['type']=='planner_format_retry' for r in events)==5
        assert sum(r['type']=='planner_output_attempt' for r in events)==6
    asyncio.run(run())


def test_format_and_transport_ordinals_budget_and_no_http_recovery_expansion():
    async def run():
        sent=[];events=[];budget=RunBudget(dict(total_seconds=30,planner_http_attempts=3))
        def handler(req):
            sent.append(req.content)
            if len(sent)==1:return httpx.Response(503)
            return extra_note()
        async def sleep(_):pass
        async with client(handler,record=events.append,before_attempt=budget.before_planner,sleep=sleep) as p:
            with pytest.raises(BudgetExceeded):await p.plan([dict(role='user',content='x')],request_id='d1')
        assert len(sent)==3 and budget.planner_http_attempts==3
        rows=[r for r in events if r['type']=='planner_transport']
        assert [r['attempt'] for r in rows]==[1,2,3]
        assert [r['json_attempt'] for r in rows]==[1,1,2]
        assert [r['transport_attempt'] for r in rows]==[1,2,1]
        sent.clear()
        def forbidden(req):sent.append(req);return httpx.Response(403)
        async with client(forbidden) as p:
            with pytest.raises(PlannerTransportError):await p.plan([dict(role='user',content='x')],request_id='d2')
        assert len(sent)==1
    asyncio.run(run())


def test_new_defaults_and_invalid_scope(tmp_path):
    cfg=settings.load_config(source_config(tmp_path))
    assert cfg['planner']['temperature']==0 and cfg['planner']['retry_scope']=='response_format'
    with pytest.raises(settings.ConfigurationError):
        settings.load_config(source_config(tmp_path,planner=dict(retry_scope='anything')))


def test_format_retry_metrics_count_raw_physical_usage():
    from integration.jev_planner.reporting import _role_metrics
    rows=[dict(type='planner_request'),dict(type='planner_format_retry'),dict(type='planner_json_retry')]
    for n in range(1,4):
        rows.append(dict(type='planner_transport',request_id='d1',attempt=n,
                         json_attempt=n,transport_attempt=1,network_called=True,
                         usage=dict(prompt_tokens=10*n,completion_tokens=n)))
    result=_role_metrics([dict(id='d1',records=rows)],'planner',mode='live')
    assert result['format_retries']==1 and result['json_retries']==1 and result['retry_attempts']==0
    assert result['http_attempts']==3 and result['tokens']['input']['total']==60


def test_cancel_between_format_generations():
    async def run():
        cancelled=[False];sent=[]
        def handler(req):
            sent.append(req);cancelled[0]=True;return extra_note()
        async with client(handler,cancelled=lambda:cancelled[0]) as p:
            with pytest.raises(asyncio.CancelledError):await p.plan([dict(role='user',content='x')],request_id='d1')
        assert len(sent)==1
    asyncio.run(run())
