"""연속 통신 실패·HTTP 오류·취소·시간무상한의 무외부호출 검증."""
import asyncio
import json
import time

import httpx
import pytest

from .core import MODEL, TransportFailure, retry_after_seconds
from .retry import RetrySession
from .test_core import PAYLOAD


def make_session(tmp_path,handler):
    transport=httpx.MockTransport(handler)
    return RetrySession(tmp_path,key='secret-test',first_request_at=time.time()-86400*30,
        fake=True,client_factory=lambda:httpx.Client(transport=transport))


def success():
    return httpx.Response(200,json=dict(model=MODEL,answers=[dict(type='choice',name='action',
        choice='switch_2',confidence=.1,probabilities=[dict(value='move_1',probability=.9),
        dict(value='switch_2',probability=.1)])],usage=dict(input_tokens=99,output_tokens=0)))


def test_more_than_four_failures_then_success_identical_body_and_no_deadline(tmp_path):
    bodies=[];waits=[]
    def handler(request):
        bodies.append(request.content)
        n=len(bodies)
        if n==1:raise httpx.ConnectError('secret-test',request=request)
        if n==2:raise httpx.ReadTimeout('secret-test',request=request)
        if n==3:return httpx.Response(503,text='temporary')
        if n==4:return httpx.Response(429,headers={'Retry-After':'45'},text='rate limit')
        if n==5:return httpx.Response(408,text='timeout')
        return success()
    session=make_session(tmp_path,handler)
    async def wait(delay):waits.append(delay)
    session._backoff=wait
    async def run():
        try:return await session.evaluate(PAYLOAD,decision='same-logical-decision')
        finally:await session.close()
    result=asyncio.run(run())
    assert result['answers']['action']['choice']=='switch_2'
    assert len(bodies)==6 and len(set(bodies))==1
    assert waits==[2.,5.,10.,45.,30.]
    assert session.remaining()==float('inf')
    ledger=json.loads((tmp_path/'ledger.json').read_text())
    assert ledger['requests']==6 and ledger['deadline'] is None and ledger['limit'] is None and ledger['retries'] is None
    attempts=[e for e in session.records if e['type']=='transport']
    assert [e['attempt'] for e in attempts]==list(range(1,7))
    assert [e['request_number'] for e in attempts]==list(range(1,7))
    assert len({e['decision'] for e in attempts})==1
    assert 'secret-test' not in (tmp_path/'events.jsonl').read_text()
    assert [e['exception_type'] for e in session.records if e.get('exception_type')]==['ConnectError','ReadTimeout']
    session.record(dict(type='response',decision='same-logical-decision',body=result,elapsed_seconds=.1))
    from .study import summarize
    summary=summarize(session,[],[])
    assert summary['retry_attempts']==5 and summary['exhausted_requests']==0
    assert summary['recovered_requests']==1 and summary['usage_unknown_attempts']==5
    assert summary['received_usage']['input_tokens']==99 and summary['tokens'] is None


def test_retry_audit_preserves_input_and_command():
    import copy
    from .core import RUN
    from .audit import audit
    source=RUN/'mock'
    if not (source/'events.jsonl').exists():pytest.skip('local sealed v6 fixture unavailable')
    original=[json.loads(line) for line in (source/'events.jsonl').open()]
    first=next(e['decision'] for e in original if e['type']=='input')
    chosen=[]
    for event in original:
        if event.get('decision') not in (None,first):break
        chosen.append(copy.deepcopy(event))
        if event['type']=='wire':break
    synthetic=[]
    for event in chosen:
        if event['type']=='transport':
            synthetic.append(copy.deepcopy(event))
        elif event['type']=='http_request':
            synthetic.append(copy.deepcopy(event))
            common=dict(decision=first,request_number=1,attempt=1)
            synthetic.append(dict(type='attempt_failure',category='transport',status_code=None,**common))
            synthetic.append(dict(type='provider_retry',next_attempt=2,delay_seconds=2.,**common))
            transport=copy.deepcopy(next(e for e in chosen if e['type']=='transport'))
            transport.update(request_number=2,attempt=2);synthetic.append(transport)
            event.update(request_number=2,attempt=2);synthetic.append(event)
        else:
            if event['type']=='http_response':event.update(request_number=2,attempt=2)
            synthetic.append(event)
    manifest=json.loads((source/'manifest.json').read_text())
    manifest['execution_profile']='openai-decisions-v6-unlimited-v1'
    outcome=json.loads((source/'battle-1/outcome.json').read_text());outcome['completed']=False
    receipt=audit(source,synthetic,outcome,manifest)
    assert receipt['passed'],receipt['errors']
    altered=copy.deepcopy(synthetic)
    next(e for e in altered if e['type']=='http_request' and e['attempt']==2)['body']['input']='changed'
    receipt=audit(source,altered,outcome,manifest)
    assert not receipt['passed']


@pytest.mark.parametrize('status',[400,401,403,404])
def test_permanent_errors_not_retried(tmp_path,status):
    calls=[]
    def handler(request):calls.append(request);return httpx.Response(status,text='secret-test')
    session=make_session(tmp_path,handler)
    async def run():
        try:
            with pytest.raises(TransportFailure) as caught:
                await session.evaluate(PAYLOAD,decision='permanent')
            assert not caught.value.retryable
        finally:await session.close()
    asyncio.run(run())
    assert len(calls)==1


def test_cancellation_during_retry_wait(tmp_path):
    session=make_session(tmp_path,lambda request:httpx.Response(503))
    async def cancel_wait(delay):
        session.failure_event.set()
        await RetrySession._backoff(session,delay)
    session._backoff=cancel_wait
    async def run():
        try:
            with pytest.raises(RuntimeError,match='cancelled'):
                await session.evaluate(PAYLOAD,decision='cancel')
        finally:await session.close()
    asyncio.run(run())
    assert session.calls==1


def test_retry_after_invalid_and_finite():
    assert retry_after_seconds('60')==60
    assert retry_after_seconds('invalid')==0
    assert retry_after_seconds('inf')==0
    assert retry_after_seconds('-3')==0
