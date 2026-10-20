import asyncio
import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from integration.quyet import battle, client, policy, server, study
from integration.quyet.tests.test_transport import FakeModel, IDENTITY
from integration.pokechamp import jev_battle as j


def payload():
    criteria = {}
    for slot in range(1, 5):
        for tera in (False, True):
            criteria[f'move_{slot}' + ('_terastallize' if tera else '')] = {
                'kind': 'move', 'slot': slot, 'terastallize': tera,
                'move_ref': {'self_team_slot': 1, 'current_move_slot': slot}}
    criteria.update({f'switch_{i}': {'kind': 'switch', 'slot': i, 'pokemon': f'Pokemon{i}'} for i in range(2, 7)})
    return {'state': {'decision_kind': 'turn_action', 'request_id': 8, 'observation': {'nested': [1, None]}},
            'questions': {'action': {'type': 'choice',
                'instructions': (j.ROOT / 'integration/pokechamp/prompts/jev-choice-v4.txt').read_text(),
                'criteria': criteria}}}


class Session:
    def __init__(self, choices=()):
        self.records, self.calls, self.choices = [], [], iter(choices)

    def record(self, event):
        self.records.append(copy.deepcopy(event))

    async def evaluate(self, request, *, decision, stage):
        self.calls.append(copy.deepcopy(request))
        choice = next(self.choices, next(iter(request['questions']['action']['criteria'])))
        return {'answers': {'action': {'type': 'choice', 'choice': choice}}}


async def current(_):
    pass


def test_thirteen_candidates_preserve_8_5_and_full_information():
    p = payload(); before = copy.deepcopy(p)
    groups = policy.split_candidates(p)
    assert [len(v) for v in groups.values()] == [8, 5]
    assert list(groups['move']) == list(p['questions']['action']['criteria'])[:8]
    assert list(groups['switch']) == list(p['questions']['action']['criteria'])[8:]
    req = policy.type_request(p)
    assert req['questions']['action']['criteria']['move']['candidates'] == groups['move']
    assert req['questions']['action']['criteria']['switch']['candidates'] == groups['switch']
    assert req['state'] == policy.detail_request(p, 'move')['state'] == p['state']
    original_tail = p['questions']['action']['instructions'].split('\n\n', 1)[1]
    assert req['questions']['action']['instructions'].split('\n\n', 1)[1] == original_tail
    assert p == before


@pytest.mark.parametrize('phase,kinds,expected_calls', [
    ('turn_action', ['move','switch'], 2), ('turn_action', ['move'], 1),
    ('turn_action', ['switch'], 1), ('forced_switch', ['switch'], 1), ('lead', ['team'], 1)])
def test_phase_call_counts(phase, kinds, expected_calls):
    p = payload();p['state']['decision_kind'] = phase
    if phase == 'lead':
        p['questions']['action']['criteria'] = {f'team_{i}': {'kind':'team','slot':i} for i in range(1,7)}
    else:
        p['questions']['action']['criteria'] = {k:v for k,v in p['questions']['action']['criteria'].items() if v['kind'] in kinds}
    session = Session()
    asyncio.run(policy.select(p, decision='d', session=session, check_current=current))
    assert len(session.calls) == expected_calls
    assert [e['stage'] for e in session.records if e['type'] == 'stage_selection'] == list(policy.STAGES)


@pytest.mark.parametrize('phase,kind', [('turn_action','move'), ('turn_action','switch'), ('forced_switch','switch'), ('lead','team')])
def test_single_candidate_zero_calls(phase, kind):
    p=payload();p['state']['decision_kind']=phase
    p['questions']['action']['criteria']={'only':{'kind':kind,'slot':1}}
    session=Session()
    assert asyncio.run(policy.select(p,decision='d',session=session,check_current=current)) == 'only'
    assert session.calls == []


def test_mixed_types_selected_single_detail_has_only_type_call():
    p=payload();p['questions']['action']['criteria'] = {'m':{'kind':'move','slot':1},'s':{'kind':'switch','slot':2}}
    s=Session(['switch'])
    assert asyncio.run(policy.select(p,decision='d',session=s,check_current=current)) == 's'
    assert len(s.calls)==1


@pytest.mark.parametrize('choices', [['invalid'], ['move','switch_2']])
def test_outside_selected_branch_is_rejected(choices):
    s=Session(choices)
    with pytest.raises(j.UnusableChoice):
        asyncio.run(policy.select(payload(),decision='d',session=s,check_current=current))
    assert s.records[-1]['type']=='stage_failure'
    assert len(s.calls)==len(choices)


@pytest.mark.parametrize('where', ['action_type','action_detail','final_transmission'])
@pytest.mark.parametrize('reason', ['rqid','commands','cancel'])
def test_stale_or_cancelled_has_no_final_selection(where,reason):
    s=Session()
    async def check(stage):
        if stage == where:
            battle.ensure_current(8,9 if reason=='rqid' else 8,{'rqid':8},['a'],
                                  ['b'] if reason=='commands' else ['a'],reason=='cancel')
    with pytest.raises(ValueError):
        asyncio.run(policy.select(payload(),decision='d',session=s,check_current=check))
    assert len(s.calls)=={'action_type':0,'action_detail':1,'final_transmission':2}[where]
    assert not any(e['type']=='wire' for e in s.records)


@pytest.mark.parametrize('lost_response', [False, True])
def test_only_failed_detail_retries_same_id_without_repeating_type(tmp_path,lost_response):
    model=FakeModel(); service=server.LocalService(model,tmp_path/'serving')
    attempts=[]; detail_attempt=0
    def handle(request):
        nonlocal detail_attempt
        if request.method=='GET': return httpx.Response(200,json=service.health())
        body=json.loads(request.content);is_detail='move' not in body['questions']['action']['criteria']
        attempts.append(request)
        if is_detail:
            detail_attempt+=1
            if not lost_response and detail_attempt<=3:
                return httpx.Response(503,json={'error':'temporary'})
        status,raw,reused=service.evaluate(request.content,request_id=request.headers['X-Request-ID'],
            body_sha256=request.headers['X-Body-SHA256'],expected_identity=IDENTITY)
        if lost_response and is_detail and detail_attempt==1:
            raise httpx.ReadTimeout('lost after inference',request=request)
        return httpx.Response(status,content=raw,headers={
            'X-Request-ID':request.headers['X-Request-ID'],'X-Body-SHA256':request.headers['X-Body-SHA256'],
            'X-Serving-Identity':IDENTITY,'X-Cache-Reused':str(int(reused))})
    def factory(**kwargs): return client.LocalClient(**kwargs,transport=httpx.MockTransport(handle))
    output=tmp_path/'collection';output.mkdir()
    s=battle.Session(output,expected_identity=IDENTITY,client_factory=factory);waits=[]
    async def no_wait(seconds): waits.append(seconds)
    s._backoff=no_wait
    try:
        assert asyncio.run(policy.select(payload(),decision='d',session=s,check_current=current))=='move_1'
        assert model.calls==2
        assert len(attempts)==(3 if lost_response else 5)
        assert len({r.headers['X-Request-ID'] for r in attempts[1:]})==1
        assert len({r.content for r in attempts[1:]})==1
        assert attempts[0].headers['X-Request-ID'] != attempts[1].headers['X-Request-ID']
        assert waits==([10] if lost_response else [10,30,60])
        with pytest.raises(ValueError,match='duplicate'):
            asyncio.run(s.evaluate(policy.type_request(payload()),decision='d',stage='action_type'))
    finally:
        asyncio.run(s.close());service.close()


def test_stage_usage_unknown_and_pair_failure_is_not_loss():
    response={'type':'stage_response','decision':'d','stage':'action_type','elapsed_seconds':1,
              'body':{'usage':{'input_tokens':10,'output_tokens':0}}}
    events=[response,*[{'type':'transport','decision':'d','stage':s} for s in policy.STAGES]]
    s=SimpleNamespace(records=events,calls=2,started=1,monotonic_started=None)
    schedule=[{'slot_id':'a','paired_slot_id':'pair','jev_actor':'p1'},
              {'slot_id':'b','paired_slot_id':'pair','jev_actor':'p2'}]
    good=[dict(r,completed=True,audit_passed=True,outcome='player_won') for r in schedule]
    failed=[good[0],dict(schedule[1],completed=False,audit_passed=True,outcome='output_failure',error={'detail':'bad'})]
    result=study.summarize(s,failed,schedule)
    assert result['tokens'] is None and result['received_usage']['input_tokens']==10
    assert result['usage_unknown_requests']==1 and result['overall']['losses']==0 and result['failed']==1
    assert study.compare_outcomes(good,failed,schedule)['common_completed_pairs']==0
    assert study.compare_outcomes(good,good,schedule)['mean_pair_score_delta']==0


def test_cached_http_attempt_does_not_double_count_usage():
    records=[{'type':'transport','decision':'d','stage':'action_type'}]*2
    records += [{'type':'stage_response','decision':'d','stage':'action_type','elapsed_seconds':2,
                 'body':{'usage':{'input_tokens':13,'output_tokens':0}}}]
    s=SimpleNamespace(records=records,calls=2,started=1,monotonic_started=None)
    result=study.summarize(s,[],[{'slot_id':'a'}])
    assert result['tokens']['input_tokens']==13 and result['retry_attempts']==1
