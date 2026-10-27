import asyncio
from copy import deepcopy
import json
import time
from functools import lru_cache

import httpx
import pytest

from integration.openai_decisions_battle.core import MODEL, to_request, from_request, TransportFailure
from integration.openai_decisions.client import DecisionsError
from integration.pokechamp import jev_battle as j
from .transform import transform, restore
from .session import RecoverySession
from .metrics import response_metrics
from .offline import BASELINE
from .audit import audit_responses


@lru_cache
def examples():
    selected={}
    for line in (BASELINE/'collection/events.jsonl').open():
        e=json.loads(line)
        if e['type']=='input': selected.setdefault(e['payload']['state']['decision_kind'],e['payload'])
        if len(selected)==3:break
    return selected


def response(choice='move_1', **extra):
    return dict(model=MODEL,answers=[dict(name='action',type='choice',choice=choice,**extra)],
                usage=dict(input_tokens=10,output_tokens=0))


def run_script(tmp_path, script, *, cancel=False):
    sent=[];steps=iter(script)
    def handler(request):
        sent.append(request.content)
        item=next(steps)
        if isinstance(item,Exception):raise item
        if isinstance(item,int):return httpx.Response(item)
        if isinstance(item,str):return httpx.Response(200,text=item)
        return httpx.Response(200,json=item)
    session=RecoverySession(tmp_path,key='test-key',fake=True,first_request_at=time.time(),
        client_factory=lambda:httpx.Client(transport=httpx.MockTransport(handler)))
    waits=[]
    async def backoff(seconds):
        waits.append(seconds)
        if cancel:raise asyncio.CancelledError()
    session._backoff=backoff
    async def run():
        try:return await session.evaluate(transform(examples()['turn_action']),decision='test')
        finally:await session.close()
    error=None;body=None
    try:body=asyncio.run(run())
    except BaseException as exc:error=exc
    assert all(s==sent[0] for s in sent)
    return session,sent,waits,body,error


def check_history(session, body, *, exhausted=False):
    attempts={}
    for e in session.records:
        if e.get('request_number'):attempts.setdefault(e['request_number'],{})[e['type']]=e
    group={} if exhausted else {'response':{'body':body}}
    audit_responses(attempts,transform(examples()['turn_action'])['questions']['action']['criteria'],group,
                    {'completed':not exhausted})


@pytest.mark.parametrize('kind',['lead','turn_action','forced_switch'])
def test_roundtrip_and_wire(kind):
    old=examples()[kind];new=transform(old)
    assert restore(new)==old
    assert new['state']['opponent_team']==old['state']['opponent_team'] or restore(new)['state']['opponent_team']==old['state']['opponent_team']
    if len(new['questions']['action']['criteria'])>1:assert from_request(to_request(new))==new
    assert list(new['questions']['action']['criteria'])==list(old['questions']['action']['criteria'])


def test_move_locality_unavailable_zero_null_dynamic():
    old=deepcopy(examples()['turn_action'])
    active=next(m for m in old['state']['self_team'] if m['active'])
    move=active['current_move_slots'][0]
    move['damage']['ranges']={'current':[0,0],'self_tera':None,'opponent_tera':[1,2],'both_tera':[3,4]}
    move['type']='Normal' # Dynamic result is deliberately independent of Dex metadata.
    active['current_move_slots'].append(dict(slot=99,id='unavailable',disabled=True,pp=0))
    new=transform(old)
    assert restore(new)==old
    owner=next(m for m in new['state']['self_team'] if m['active'])
    assert owner['current_move_slots']==[dict(slot=99,id='unavailable',disabled=True,pp=0)]
    candidates=new['questions']['action']['criteria']
    assert candidates['move_1']['move']['type']=='Normal'
    assert candidates['move_1']['damage']['selected_range']=={'current':[0,0]}
    assert candidates['move_1_terastallize']['damage']['selected_range']=={'self_tera':None}
    assert candidates['move_1']['current_matchup']['type_matchup']==old['questions']['action']['criteria']['move_1']['current_matchup']['type_matchup'] or candidates['move_1']['current_matchup']['type_matchup']['attack_type']==old['questions']['action']['criteria']['move_1']['current_matchup']['type_matchup']['attack_type']


def test_refusal_then_success_usage(tmp_path):
    refusal=dict(model=MODEL,answers=[dict(name='action',type='refusal')],usage=dict(input_tokens=7,output_tokens=0))
    s,sent,waits,body,error=run_script(tmp_path,[refusal,response()])
    assert error is None and len(sent)==2 and not waits
    check_history(s,body)
    metrics=response_metrics(s.records)
    assert metrics['received_usage']['input_tokens']==17 and metrics['usage_unknown_attempts']==0
    assert metrics['response_requeries']==1 and metrics['response_recovered_decisions']==1


def test_exhaustion(tmp_path):
    s,sent,_,body,error=run_script(tmp_path,[response('outside'),response(None),'not JSON'])
    assert isinstance(error,j.UnusableChoice) and len(sent)==3
    check_history(s,body,exhausted=True)
    assert response_metrics(s.records)['response_exhausted_decisions']==1


def test_mixed_retries_independent_counts(tmp_path):
    s,sent,waits,body,error=run_script(tmp_path,[503,503,response(None),httpx.ReadTimeout('test'),response()])
    assert error is None and len(sent)==5 and waits==[2,5,2]
    check_history(s,body)
    m=response_metrics(s.records)
    assert m['response_attempts']==2 and m['transport_retries']==3 and m['usage_unknown_attempts']==3


def test_cancel_wait(tmp_path):
    _,sent,_,_,error=run_script(tmp_path,[503],cancel=True)
    assert isinstance(error,asyncio.CancelledError) and len(sent)==1


def test_legal_low_confidence_bad_probabilities_not_requeried(tmp_path):
    _,sent,_,body,error=run_script(tmp_path,[response(confidence=-10,probabilities=[dict(value='outside',probability=9)])])
    assert error is None and len(sent)==1 and body['answers']['action']['choice']=='move_1'


@pytest.mark.parametrize('error_response',[401,400,dict(model='wrong',answers=[])])
def test_technical_not_requeried(tmp_path,error_response):
    _,sent,_,_,error=run_script(tmp_path,[error_response])
    assert isinstance(error,DecisionsError) and not isinstance(error,j.UnusableChoice) and len(sent)==1


def test_gate_manifest():
    from .execute import manifest
    value=manifest()
    assert len(value['schedule'])==32 and value['schema_version']=='jev-choice-v7'
    assert value['input_profile']=='candidate-action-v1'
    assert value['limits']['response_attempts']==3 and value['limits']['calls'] is None


def test_paired_comparison_excludes_missing_and_incomplete_pairs():
    from .analysis import paired_comparison
    schedule=[dict(slot_id=str(i),paired_slot_id=str(i//2)) for i in range(4)]
    def outcome(i,result):return dict(slot_id=str(i),completed=True,audit_passed=True,outcome=result)
    old=[outcome(i,'player_lost') for i in range(4)]
    new=[outcome(0,'player_won'),outcome(1,'tied'),outcome(2,'player_lost')]
    result=paired_comparison(old,new,schedule)
    assert result['common_valid_slots']==3 and result['common_slot_difference']==.5
    assert result['common_complete_pairs']==1 and result['common_pair_difference']==.75
    assert result['slots'][3]['new'] is None


def test_paired_comparison_excludes_terminal_technical_error():
    from .analysis import paired_comparison
    schedule=[dict(slot_id='a',paired_slot_id='p')]
    old=[dict(slot_id='a',completed=True,audit_passed=True,outcome='player_won')]
    new=[dict(old[0],error={'type':'CleanupFailure'})]
    result=paired_comparison(old,new,schedule)
    assert result['common_valid_slots']==0 and result['slots'][0]['new'] is None


def test_historical_raw_response_count():
    events=[dict(type='transport',request_number=1,decision='a'),
        dict(type='http_response',request_number=1,status_code=200,raw_body=json.dumps(response()))]
    assert response_metrics(events)['response_attempts']==1
