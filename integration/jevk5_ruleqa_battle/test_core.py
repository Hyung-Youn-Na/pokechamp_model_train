"""Independent numerical and transport boundary checks; no live model calls."""
import asyncio
import copy
import json
import math
import time
from unittest.mock import patch

import httpx
import pytest

from .core import (MODEL, TEMPERATURE, to_request, from_request, calibrated,
                   normalized_response, UnusableChoice)


def payload(count=3):
    return dict(state=dict(version='jev-choice-v6',turn=4,actor='p2',
        note='한글 / "quotes" / <|im_end|> / null',self_team=[{'hp':17,'unknown':None}]),
        questions=dict(action=dict(type='choice',instructions='Choose one.\nKeep all supplied facts.',
            criteria={f'move_{i}':{'slot':i,'nested':{'damage':[0,23.4],'text':'Pokémon'}}
                      for i in range(1,count+1)})))


def response(request, values=None):
    values = values or [-7.,-1.,-2.]
    return dict(model=MODEL,choices=[dict(index=0,text='A',finish_reason='length',
        prompt_token_ids=request['prompt'],token_ids=[request['logprob_token_ids'][0]],
        logprobs=dict(top_logprobs=[{f'token_id:{k}':v for k,v in zip(request['logprob_token_ids'],values)}]))],
        usage=dict(prompt_tokens=len(request['prompt']),completion_tokens=1,total_tokens=len(request['prompt'])+1))


@pytest.mark.parametrize('count',[2,3,13,16])
def test_lossless_ordered_native_roundtrip(count):
    p=payload(count);r=to_request(p)
    assert from_request(r)==p
    assert list(from_request(r)['questions']['action']['criteria'])==list(p['questions']['action']['criteria'])
    assert len(r['logprob_token_ids'])==count
    assert r['max_tokens']==1


def test_score_distribution_and_generated_letter_is_not_policy():
    p=payload();r=to_request(p);body=normalized_response(response(r),p)
    answer=body['answers']['action']
    assert answer['choice']=='move_2'  # generated text/token was A / move_1
    weights=[math.exp(x/TEMPERATURE) for x in [-7.,-1.,-2.]]
    assert list(answer['probabilities'].values())==pytest.approx([x/sum(weights) for x in weights])
    assert calibrated([-1007.,-1001.,-1002.])==pytest.approx(list(answer['probabilities'].values()))
    assert body['usage']['output_tokens']==1


def test_equal_scores_preserve_first_option():
    p=payload();r=to_request(p)
    assert normalized_response(response(r,[-2.,-2.,-2.]),p)['answers']['action']['choice']=='move_1'


@pytest.mark.parametrize('value',[float('nan'),float('inf'),None])
def test_nonfinite_scores_are_output_failure(value):
    with pytest.raises(UnusableChoice):
        calibrated([0.,value])


def test_missing_candidate_is_not_approximated():
    p=payload();r=to_request(p);raw=response(r)
    raw['choices'][0]['logprobs']['top_logprobs'][0].pop(f"token_id:{r['logprob_token_ids'][2]}")
    with pytest.raises(UnusableChoice):
        normalized_response(raw,p)


@pytest.mark.parametrize('field',['model','prompt','usage'])
def test_wrong_identity_tokens_usage_are_technical_failures(field):
    p=payload();r=to_request(p);raw=response(r)
    if field=='model':raw['model']='wrong'
    elif field=='prompt':raw['choices'][0]['prompt_token_ids']=r['prompt'][:-1]
    else:raw['usage']['completion_tokens']=0
    with pytest.raises(ValueError) as error:
        normalized_response(raw,p)
    assert not isinstance(error.value,UnusableChoice)


def test_no_truncation_or_many_option_pruning():
    with pytest.raises(ValueError):to_request(payload(17))
    p=payload();p['state']['note']='token '*33000
    with pytest.raises(ValueError,match='context'):to_request(p)


def test_transient_retry_preserves_request_and_records_unknown_usage(tmp_path):
    from .session import Session
    p=payload();seen=[]
    def handler(req):
        seen.append(req.content)
        if len(seen)==1:return httpx.Response(503,json={'error':'temporary'})
        return httpx.Response(200,json=response(json.loads(req.content)))
    s=Session(tmp_path,first_request_at=time.time(),fake=True)
    s.fake=False;s.identity={};s.client.close();s.client=httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with patch('integration.jevk5_ruleqa_battle.session.resource.verify'),patch('integration.jevk5_ruleqa_battle.session.RETRY_DELAYS',(0,0,0)):
            answer=asyncio.run(s.evaluate(p,decision='test-retry'))
        assert answer['answers']['action']['choice']=='move_2'
        assert len(seen)==2 and seen[0]==seen[1]
        assert len([e for e in s.records if e['type']=='attempt_failure'])==1
        assert [e['attempt'] for e in s.records if e['type']=='transport']==[1,2]
    finally:
        s.fake=True;asyncio.run(s.close())


@pytest.mark.parametrize('status,expected_calls',[(400,1),(401,1),(503,4)])
def test_retry_bounds_and_permanent_error(tmp_path,status,expected_calls):
    from .session import Session
    s=Session(tmp_path,first_request_at=time.time(),fake=True)
    s.fake=False;s.identity={};s.client.close()
    s.client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'error':'fixture'})))
    try:
        with patch('integration.jevk5_ruleqa_battle.session.resource.verify'),patch('integration.jevk5_ruleqa_battle.session.RETRY_DELAYS',(0,0,0)):
            with pytest.raises(RuntimeError):asyncio.run(s.evaluate(payload(),decision='test-failure'))
        assert s.calls==expected_calls
    finally:
        s.fake=True;asyncio.run(s.close())


def test_cancel_prevents_request(tmp_path):
    from .session import Session
    s=Session(tmp_path,first_request_at=time.time(),fake=True);s.failure_event.set()
    try:
        with pytest.raises(RuntimeError):asyncio.run(s.evaluate(payload(),decision='cancelled'))
        assert s.calls==0
    finally:
        asyncio.run(s.close())
