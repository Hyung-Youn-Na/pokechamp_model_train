"""Bounded content regeneration, separate transport attempts and shared budget."""
import asyncio
import json

import httpx
import pytest

from integration.jev_planner import config as settings
from integration.jev_planner.core import PlanOutputError, parse_plan
from integration.jev_planner.execute import BudgetExceeded, RunBudget
from integration.jev_planner.planner import ZaiPlannerClient, PlannerTransportError
from integration.jev_planner.tests.test_planner import config, response
from integration.jev_planner.tests.test_config_cli import source_config


def client(handler, **kwargs):
    cfg = config(); cfg['json_retries'] = 5
    return ZaiPlannerClient(cfg, api_key='synthetic-key', base_url='https://example.test/api/v4',
        transport=httpx.MockTransport(handler), environ={}, **kwargs)


@pytest.mark.parametrize('invalid_count', [0, 1, 5, 6])
def test_initial_plus_five_exact_bytes_and_preserved_attempts(invalid_count):
    async def run():
        sent, records, admitted = [], [], []
        def handler(request):
            sent.append(request.content)
            return response(content='{"contingencies":[{"if":"a","then":"b"]}]}') if len(sent) <= invalid_count else response()
        async with client(handler, record=records.append, before_attempt=lambda **r: admitted.append(r)) as planner:
            result = await planner.plan([dict(role='user', content='immutable input')], request_id='decision-1')
        count = min(invalid_count + 1, 6)
        assert len(sent) == count and len(set(sent)) == 1
        assert [r['attempt'] for r in admitted] == list(range(1, count + 1))
        attempts = [r for r in records if r['type'] == 'planner_output_attempt']
        assert len(attempts) == count and [r['json_attempt'] for r in attempts] == list(range(1, count + 1))
        assert sum(r['type'] == 'planner_json_retry' for r in records) == count - 1
        assert result['http_attempts'] == count and result['json_attempts'] == count
        assert all(r['usage']['prompt_tokens'] == 20 for r in attempts)
        if invalid_count == 6:
            assert result['plan'] is None
            with pytest.raises(PlanOutputError): parse_plan(result['content'])
        else: assert result['plan'] == parse_plan(result['content'])
    asyncio.run(run())


@pytest.mark.parametrize('content', ['{}', '[]', '{"objective":"one","objective":"two"}', '{"x":NaN}'])
def test_schema_and_duplicate_nonfinite_are_not_syntax_retries(content):
    async def run():
        sent=[]
        def handler(request): sent.append(request); return response(content=content)
        async with client(handler) as planner:
            result = await planner.plan([dict(role='user', content='input')], request_id='d1')
        assert len(sent) == 1 and result['plan'] is None
    asyncio.run(run())


def test_json_and_http_retries_have_global_physical_and_local_transport_ordinals():
    async def run():
        sent, records, delays = [], [], []
        def handler(request):
            sent.append(request.content)
            if len(sent) in (1, 3): return httpx.Response(503)
            return response(content='bad JSON') if len(sent) == 2 else response()
        async def sleep(value): delays.append(value)
        async with client(handler, record=records.append, sleep=sleep) as planner:
            result = await planner.plan([dict(role='user', content='input')], request_id='d1')
        transport=[r for r in records if r['type']=='planner_transport']
        assert [r['attempt'] for r in transport] == [1,2,3,4]
        assert [r['transport_attempt'] for r in transport] == [1,2,1,2]
        assert [r['json_attempt'] for r in transport] == [1,1,2,2]
        assert len(set(sent)) == 1 and delays == [1.,1.] and result['http_attempts'] == 4
    asyncio.run(run())


def test_shared_budget_and_cancel_prevent_more_generations():
    async def run():
        sent=[];budget=RunBudget(dict(total_seconds=30,planner_http_attempts=2))
        def handler(request): sent.append(request); return response(content='{')
        async with client(handler,before_attempt=budget.before_planner) as planner:
            with pytest.raises(BudgetExceeded):
                await planner.plan([dict(role='user',content='input')],request_id='d1')
        assert len(sent)==budget.planner_http_attempts==2
        cancelled=[False];sent.clear()
        def cancelling(request): sent.append(request);cancelled[0]=True;return response(content='{')
        async with client(cancelling,cancelled=lambda:cancelled[0]) as planner:
            with pytest.raises(asyncio.CancelledError):
                await planner.plan([dict(role='user',content='input')],request_id='d2')
        assert len(sent)==1
    asyncio.run(run())


def test_envelope_and_final_http_failure_do_not_start_content_recovery():
    async def run():
        sent=[]
        def malformed(request):sent.append(request);return httpx.Response(200,text='invalid HTTP envelope')
        async with client(malformed) as planner:
            with pytest.raises(PlanOutputError):await planner.plan([dict(role='user',content='input')],request_id='d1')
        assert len(sent)==1
        sent.clear()
        def forbidden(request):sent.append(request);return httpx.Response(403)
        async with client(forbidden) as planner:
            with pytest.raises(PlannerTransportError):await planner.plan([dict(role='user',content='input')],request_id='d2')
        assert len(sent)==1
    asyncio.run(run())


def test_new_default_and_invalid_json_retry_config(tmp_path):
    assert settings.load_config(source_config(tmp_path))['planner']['json_retries']==5
    for value in (-1,6,True,1.5,'5'):
        with pytest.raises(settings.ConfigurationError):
            settings.load_config(source_config(tmp_path,planner=dict(json_retries=value)))


def test_reporting_keeps_every_physical_usage_and_distinguishes_retry_kinds():
    from integration.jev_planner.reporting import _role_metrics
    rows=[dict(type='planner_request'),dict(type='planner_json_retry'),
          dict(type='planner_response',usage=dict(prompt_tokens=20))]
    for n,(generation,transport) in enumerate([(1,1),(2,1),(2,2)],1):
        rows.append(dict(type='planner_transport',request_id='d1',attempt=n,json_attempt=generation,
                         transport_attempt=transport,network_called=True,usage=dict(prompt_tokens=10*n)))
    result=_role_metrics([dict(id='d1',records=rows)],'planner',mode='live')
    assert result['logical_calls']==1 and result['http_attempts']==3
    assert result['json_retries']==1 and result['retry_attempts']==1
    assert result['tokens']['input']['total']==60
