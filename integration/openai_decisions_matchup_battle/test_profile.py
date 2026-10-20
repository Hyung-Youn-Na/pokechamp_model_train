import asyncio
import copy
import gzip
import json
import time
from pathlib import Path

import httpx
import pytest

from integration.candidate_matchup import adapter, decorate, remove_summaries
from integration.openai_decisions_battle.core import from_request, to_request, MODEL
from integration.openai_decisions_battle.retry import RetrySession
from integration.openai_decisions_battle.audit import audit
from integration.jev27b.audit import cutoff_prefix
from .execute import BASELINE, manifest


def representatives():
    selected={}
    for line in (BASELINE/'collection/events.jsonl').open():
        event=json.loads(line)
        if event['type']!='input':continue
        kind=event['payload']['state']['decision_kind']
        if kind not in selected:selected[kind]=event
        if set(selected)=={'lead','turn_action','forced_switch'}:break
    return selected


def test_manifest_base_schedule_and_profile():
    value=manifest()
    assert value['schema_version']=='jev-choice-v6'
    assert value['candidate_matchup_profile']=='candidate-matchup-v1'
    assert len(value['schedule'])==32
    assert all(value['limits'][k] is None for k in ('calls','retries','turns','decisions','total_seconds'))
    assert any('candidate_matchup/summary.py' in p for p in value['source'])
    assert any('openai_decisions_matchup_battle/analysis.py' in p for p in value['source'])


def test_enriched_body_sent_unchanged_through_retry(tmp_path):
    base=representatives()['turn_action']['payload'];payload=decorate(base);bodies=[]
    def handler(request):
        bodies.append(request.content)
        if len(bodies)==1:return httpx.Response(503)
        body=json.loads(request.content);choice=body['questions'][0]['choices'][0]['value']
        return httpx.Response(200,json=dict(model=MODEL,answers=[dict(name='action',type='choice',choice=choice)]))
    session=RetrySession(tmp_path,key='mock-key',fake=True,first_request_at=time.time(),
        client_factory=lambda:httpx.Client(transport=httpx.MockTransport(handler)))
    async def wait(seconds):pass
    session._backoff=wait
    async def run():
        try:await session.evaluate(payload,decision='test')
        finally:await session.close()
    asyncio.run(run())
    assert len(bodies)==2 and bodies[0]==bodies[1]
    restored=from_request(json.loads(bodies[0]))
    assert restored==payload and remove_summaries(restored)==base
    assert any('current_matchup' in c for c in restored['questions']['action']['criteria'].values())


def test_official_regeneration_and_profile_audit(tmp_path):
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    from integration.pokechamp.observation.runtime import OfficialClient
    from integration.jev27b.study import file_hash
    source=BASELINE/'collection'
    value=json.loads((source/'manifest.json').read_text());value['candidate_matchup_profile']=adapter.VERSION
    events=[];first=None
    for line in (source/'events.jsonl').open():
        event=json.loads(line)
        if event['type']=='input' and first is None:first=event['decision']
        if event.get('decision') and event['decision']!=first:break
        events.append(event)
        if event['type']=='wire':break
    entry=next(e for e in events if e['type']=='input')
    outcome=json.loads((source/'battle-1/outcome.json').read_text());outcome['completed']=False
    protocols=[dict(event_seq=e['sequence'],protocol=e['protocol']) for e in events if e['type']=='protocol' and e['username']==outcome['username']]
    prefix=cutoff_prefix(protocols,entry['boundary'])
    build=adapter.Adapter(json.loads((DEFAULT_BUILD/'dex.json').read_text()))
    try:
        team=value['teams'][outcome['teams'][int(entry['actor'][-1])-1]]['showdown_team']
        payload,commands,generated=build.generate(entry['official'],prefix,team,actor=entry['actor'])
    finally:build.close()
    assert remove_summaries(payload)==entry['payload'] and commands==entry['commands']
    entry['payload']=payload;entry['input_audit']=adapter.save_audit(tmp_path,first,generated)
    for e in events:
        if e['type']=='http_request':
            from integration.openai_decisions_battle.core import dumps
            e['body']=to_request(payload);e['raw_body']=dumps(e['body'])
    assert audit(tmp_path,events,outcome,value)['passed']
    wrong=copy.deepcopy(value);wrong.pop('candidate_matchup_profile')
    assert not audit(tmp_path,events,outcome,wrong)['passed']
    wrong=copy.deepcopy(value);wrong['candidate_matchup_profile']='unknown'
    assert not audit(tmp_path,events,outcome,wrong)['passed']


def test_lead_forced_and_self_tera_preservation():
    examples=representatives()
    for kind in ('lead','forced_switch'):
        base=examples[kind]['payload'];enriched=decorate(base)
        assert enriched==base and remove_summaries(enriched)==base
        if len(base['questions']['action']['criteria'])>1:assert from_request(to_request(enriched))==base
    found=False
    for line in (BASELINE/'collection/events.jsonl').open():
        event=json.loads(line)
        if event['type']!='input':continue
        base=event['payload'];enriched=decorate(base)
        for key,candidate in enriched['questions']['action']['criteria'].items():
            summary=candidate.get('current_matchup')
            if summary and summary['damage'].get('branch')=='self_tera':
                found=True
                assert remove_summaries(enriched)==base
                assert from_request(to_request(enriched))==enriched
                break
        if found:break
    assert found
