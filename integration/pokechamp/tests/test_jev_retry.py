import asyncio
import copy
import json
import traceback

import httpx
import pytest
from integration.pokechamp import jev, jev_battle as j, jev_retry as policy
from integration.pokechamp.tests.test_jev import BODY, QUESTIONS, KEY
from integration.pokechamp.tests.test_jev_battle import sample


@pytest.mark.parametrize('version,expected_waits', [(policy.V1,[1,2,4]),(policy.CURRENT,[10,30,60])])
@pytest.mark.parametrize('error', [429, 500, 503, 599, 'timeout', 'transport'])
@pytest.mark.parametrize('succeed', [True, False])
def test_fixed_three_client_retries(error, succeed, monkeypatch, version, expected_waits):
    sent, waits = [], []
    monkeypatch.setattr(jev.time, 'sleep', waits.append)
    def handler(request):
        sent.append(request.content)
        if succeed and len(sent) == 4:return httpx.Response(200, json=BODY)
        if error == 'timeout':raise httpx.ReadTimeout(KEY, request=request)
        if error == 'transport':raise httpx.ConnectError(KEY, request=request)
        return httpx.Response(error, text=KEY)
    with jev.JevClient(api_key=KEY, transport=httpx.MockTransport(handler), retry_policy=version) as client:
        if succeed:assert client.evaluate(state={'test': 1}, questions=QUESTIONS) == BODY
        else:
            with pytest.raises(jev.JevRequestError) as exc:client.evaluate(state={}, questions=QUESTIONS)
            assert KEY not in ''.join(traceback.format_exception(exc.value))
            assert exc.value.__context__ is None
    assert len(sent) == 4 and len(set(sent)) == 1 and waits == expected_waits


@pytest.mark.parametrize('status', [200, 400, 401, 403, 404, 422, 302])
def test_success_and_permanent_errors_do_not_retry(status, monkeypatch):
    sent=[]
    monkeypatch.setattr(jev.time, 'sleep', lambda _: pytest.fail('unexpected retry'))
    def handler(request):
        sent.append(request)
        return httpx.Response(status,json=BODY)
    with jev.JevClient(api_key=KEY,transport=httpx.MockTransport(handler)) as client:
        if status==200:client.evaluate(state={},questions=QUESTIONS)
        else:
            with pytest.raises(jev.JevRequestError):client.evaluate(state={},questions=QUESTIONS)
    assert len(sent)==1


def install_transport(monkeypatch, handler):
    def factory(**kwargs):
        # Session owns retries; forwarding this is critical to avoid 4 x 4 attempts.
        assert kwargs['retry_policy'] == policy.LEGACY
        return jev.JevClient(api_key=KEY,transport=httpx.MockTransport(handler),
                             retry_policy=kwargs['retry_policy'],timeout=kwargs['timeout'])
    monkeypatch.setattr(jev.JevClient,'from_env',factory)


@pytest.mark.parametrize("version,expected_waits", [(policy.V1,[1,2,4]),(policy.CURRENT,[10,30,60])])
@pytest.mark.parametrize("succeed", [True, False])
def test_session_retries_counted_and_auditable(tmp_path, sample, monkeypatch, succeed, version, expected_waits):
    sent=[]
    def handler(request):
        sent.append(request)
        if len(sent)<4:return httpx.Response(503,text='upstream connection termination')
        return httpx.Response(200,json=BODY)
    install_transport(monkeypatch,handler)
    # Exercise all requested delays without a wall-clock wait of 100 seconds.
    waits=[]
    original_wait_for=asyncio.wait_for
    async def backoff(awaitable, *, timeout):
        if isinstance(awaitable, asyncio.Future):
            return await original_wait_for(awaitable, timeout=timeout)
        waits.append(timeout)
        awaitable.close()
        raise asyncio.TimeoutError
    monkeypatch.setattr(j.asyncio, 'wait_for', backoff)
    session=j.Session(tmp_path,environ={},retry_policy=version)
    state,prefix,dex=sample
    payload,_=j.make_input(state,prefix,actor='p1',dex=dex)
    # Native response keys must match the action request.
    native=copy.deepcopy(BODY);native['answers']={'action':dict(type='choice',choice='test')}
    def action_handler(request):
        sent.append(request)
        return httpx.Response(503,text='upstream connection termination') if len(sent)<4 or not succeed else httpx.Response(200,json=native)
    install_transport(monkeypatch,action_handler)
    if succeed:
        body=asyncio.run(session.evaluate(payload,decision='one'))
        assert body==native
    else:
        with pytest.raises(jev.JevRequestError):asyncio.run(session.evaluate(payload,decision='one'))
    assert len(sent)==session.calls==4 and waits==expected_waits
    ledger=json.loads((tmp_path/'ledger.json').read_text())
    assert ledger['requests']==4 and ledger['first_request_at']==session.started
    assert ledger['deadline']==session.started+1800
    assert len({r.content for r in sent})==1
    if succeed:session.record(dict(type='response',decision='one',body=body))
    result=policy.audit_attempts(session.records,{'one':dict(payload=payload)},dict(requests=4),version=version)
    assert result==dict(physical_attempts=4,logical_requests=1,retries=3)
    with pytest.raises(AssertionError):
        policy.audit_attempts(session.records,{'one':dict(payload=payload)},dict(requests=4),
                              version=policy.V1 if version==policy.CURRENT else policy.CURRENT)
    records=copy.deepcopy(session.records)
    next(e for e in records if e['type']=='http_request')['body']['state']={}
    with pytest.raises(AssertionError):policy.audit_attempts(records,{'one':dict(payload=payload)},dict(requests=4),version=version)


@pytest.mark.parametrize('reason',['budget','deadline','backoff_deadline','cancel'])
def test_no_retry_past_limit(tmp_path,sample,monkeypatch,reason):
    sent=[]
    session=j.Session(tmp_path,environ={},call_limit=1 if reason=='budget' else 300)
    def handler(request):
        sent.append(request)
        if reason=='deadline':session.monotonic_started-=1800
        if reason=='backoff_deadline':session.monotonic_started-=1795
        if reason=='cancel':session.failure_event.set()
        return httpx.Response(503,text='upstream unavailable')
    install_transport(monkeypatch,handler)
    state,prefix,dex=sample
    with pytest.raises(jev.JevRequestError):
        asyncio.run(session.evaluate(j.make_input(state,prefix,actor='p1',dex=dex)[0],decision='one'))
    assert len(sent)==session.calls==1


def test_cancel_during_backoff_stops_next_http(tmp_path,sample,monkeypatch):
    sent=[]
    install_transport(monkeypatch,lambda req:sent.append(req) or httpx.Response(503))
    session=j.Session(tmp_path,environ={})
    state,prefix,dex=sample
    async def run():
        task=asyncio.create_task(session.evaluate(j.make_input(state,prefix,actor='p1',dex=dex)[0],decision='one'))
        while not any(e['type']=='provider_retry' for e in session.records):await asyncio.sleep(.01)
        session.failure_event.set()
        with pytest.raises(RuntimeError,match='cancelled'):await task
    asyncio.run(run())
    assert session.calls==len(sent)==1


def test_new_study_session_defaults_to_three_and_old_profiles_stay_legacy(tmp_path):
    from integration.pokechamp.jev_study import StudySession
    session=StudySession(tmp_path,fake=True)
    assert session.retry_policy == policy.CURRENT
    assert policy.delays_for(session.retry_policy)==(10.,30.,60.)


@pytest.mark.parametrize('success_attempt',[1,2,3])
def test_client_stops_after_early_recovery(success_attempt,monkeypatch):
    sent=[]
    monkeypatch.setattr(jev.time,'sleep',lambda _:None)
    def handler(request):
        sent.append(request)
        return httpx.Response(200,json=BODY) if len(sent)==success_attempt else httpx.Response(503)
    with jev.JevClient(api_key=KEY,transport=httpx.MockTransport(handler)) as client:
        assert client.evaluate(state={},questions=QUESTIONS)==BODY
    assert len(sent)==success_attempt
