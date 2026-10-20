import copy
import json
from pathlib import Path
import pytest
from integration.strategist_eval.core import candidates,parse,select,ensure_current,build_input,RUN,system_prompt
from integration.strategist_eval.report import audit_events,summarize


def snapshot():
    return dict(request=dict(rqid=3,side=dict(id='p1',pokemon=[
        dict(ident='p1: A',details='Pikachu, L100',condition='50/100',active=True,moves=['thunderbolt']),
        dict(ident='p1: B',details='Eevee, L100',condition='100/100',active=False,moves=['tackle'])]),
        active=[dict(moves=[dict(move='Thunderbolt',id='thunderbolt',pp=10,disabled=False)])]),
        candidates=[dict(wire='move 1'),dict(wire='move 1 terastallize'),dict(wire='switch 2')])


def test_normal_tera_excluded():
    kind,legal=candidates(snapshot())
    assert kind=='turn_action'
    assert [c['command'] for c in legal]==['/choose move 1','/choose switch 2']


def test_lead_order():
    s=snapshot();s['request']['teamPreview']=True;s['candidates']=[dict(wire='team 1'),dict(wire='team 2')]
    kind,legal=candidates(s)
    assert kind=='lead' and legal[1]['command']=='/team 21'
    assert parse('Action: Switch to Eevee.',legal)['choice']=='team_2'


def test_forced_single():
    s=snapshot();s['request']['forceSwitch']=[True];s['candidates']=[dict(wire='switch 2')]
    kind,legal=candidates(s)
    assert kind=='forced_switch'
    result=select('',legal,'s','d')
    assert result['automatic'] and not result['fallback'] and result['error'] is None


@pytest.mark.parametrize('change',[dict(disabled=True),dict(pp=0)])
def test_unusable_move_rejected(change):
    s=snapshot();s['request']['active'][0]['moves'][0].update(change)
    with pytest.raises(ValueError):candidates(s)


@pytest.mark.parametrize('text,error,parsed',[
    ('','empty_response',False),(' \n ','empty_response',False),
    ('I choose Thunderbolt.','format_error',False),
    ('Action: Use Thunderboltt.','outside_candidates',True),
    ('Action: Switch to Pikachu.','outside_candidates',True),
    ('Action: Use Thunderbolt. because it is good','outside_candidates',True),
])
def test_errors(text,error,parsed):
    legal=candidates(snapshot())[1];r=parse(text,legal)
    assert r['error']==error and r['parsed']==parsed


def test_markdown_case_space_and_explanation():
    legal=candidates(snapshot())[1]
    assert parse('\n **Action:**  **Use** Thunderbolt.\nExplanation is incomplete',legal)==dict(parsed=True,error=None,choice='move_1')


def test_ambiguous_names():
    legal=candidates(snapshot())[1];legal.append(dict(legal[0],id='move_2',command='/choose move 2'))
    assert parse('Action: Use Thunderbolt.',legal)['error']=='ambiguous_name'


def test_fallback_seed_and_legality():
    legal=candidates(snapshot())[1]
    a=select('invalid',legal,'slot1','d1');randoms=[select('invalid',legal,'slot1',f'd{i}') for i in range(100)]
    assert a==select('invalid',legal,'slot1','d1')
    assert {r['choice'] for r in randoms}=={'move_1','switch_2'}
    assert a['fallback_seed']!=select('invalid',legal,'slot2','d1')['fallback_seed']


@pytest.mark.parametrize('latest,changed,failed',[(4,False,False),(3,True,False),(3,False,True)])
def test_stale_request(latest,changed,failed):
    s=snapshot();legal=candidates(s)[1];now=legal[:1] if changed else legal
    with pytest.raises(ValueError):ensure_current(3,latest,s['request'],legal,now,failed)


def test_tera_wire_guard():
    s=snapshot();legal=candidates(s)[1];legal[0]['command']+=' terastallize'
    with pytest.raises(ValueError):ensure_current(3,3,s['request'],legal,legal,False)


def test_public_input_and_private_guard():
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    dex=json.loads((DEFAULT_BUILD/'dex.json').read_text())
    samples=json.loads((RUN/'gate-inputs.json').read_text())
    for sample in samples.values():
        assert build_input(sample['official'],sample['prefix'],sample['actor'],dex)==sample['payload']
        other='p2' if sample['actor']=='p1' else 'p1'
        changed=copy.deepcopy(sample['official'])
        for side in changed['sides']:
            if side['id']==other:
                for mon in side['pokemon']:
                    mon.update(ability='PRIVATEABILITY',item='PRIVATEITEM',hp=987654,max_hp=999999)
        text=build_input(changed,sample['prefix'],sample['actor'],dex)['messages'][1]['content']
        assert 'PRIVATE' not in text and '987654' not in text
        bad=copy.deepcopy(sample['prefix']);bad[-1]['protocol']+='\n|request|'+json.dumps(dict(side=dict(id=other)))
        with pytest.raises(ValueError):build_input(sample['official'],bad,sample['actor'],dex)
        stale=copy.deepcopy(sample['official']);stale['request']['rqid']+=1
        with pytest.raises(ValueError):build_input(stale,sample['prefix'],sample['actor'],dex)
    assert samples['lead']['payload']['messages'][0]['content']==system_prompt()


def test_bootstrap_denominators_and_failure_not_loss():
    rows=[dict(completed=True,paired_slot_id='a',outcome='player_won'),dict(completed=True,paired_slot_id='a',outcome='player_lost'),dict(completed=False,outcome='failed')]
    result=summarize({},dict(outcomes=rows),[])
    assert result['score']==.5 and result['paired_mean']==.5 and result['bootstrap95']==[.5,.5]
    assert result['failed']==1 and result['losses']==1 and result['unplayed']==29

@pytest.mark.parametrize('mode',['normal','forced','lead','single','bad_output','server_error','stale'])
def test_actual_decision_path(mode):
    import asyncio
    import threading
    from types import SimpleNamespace
    from integration.strategist_eval.battle import player_class
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    samples=json.loads((RUN/'gate-inputs.json').read_text())
    sample=copy.deepcopy(samples['forced_switch' if mode in ('forced','single') else 'lead' if mode=='lead' else 'turn_action'])
    official=sample['official']
    if mode=='single':
        official['candidates']=official['candidates'][:1]
    legal=candidates(official)[1]
    records=[];calls=[];sent=[]
    fake=SimpleNamespace(request=official['request'],latest_rqid=official['request']['rqid'],
        expected_actor=sample['actor'],prefix=sample['prefix'],boundary={},
        official=SimpleNamespace(snapshot=lambda *a,**k:official,identity={}))
    def call(messages,decision):
        calls.append(decision)
        if mode=='server_error':raise TimeoutError('model failed')
        if mode=='stale':fake.latest_rqid+=1
        return dict(raw='bad' if mode=='bad_output' else f"Action: {legal[0]['verb']} {legal[0]['name']}.")
    async def send(*args):sent.append(args)
    fake.ps_client=SimpleNamespace(send_message=send)
    fake.session=SimpleNamespace(count=0,slot_id='test-slot',record=records.append,
        dex=json.loads((DEFAULT_BUILD/'dex.json').read_text()),model=SimpleNamespace(call=call),
        failure_event=threading.Event(),remaining=lambda:100)
    battle=SimpleNamespace(in_team_preview=mode=='lead',turn=official['turn'],battle_tag='test')
    fn=player_class()._handle_battle_request
    if mode in ('server_error','stale'):
        with pytest.raises((TimeoutError,ValueError)):asyncio.run(fn(fake,battle))
        assert not sent and not any(r['type']=='selection' for r in records)
    else:
        asyncio.run(fn(fake,battle))
        assert len(sent)==1
        selection=next(r for r in records if r['type']=='selection')
        assert selection['automatic']==(mode=='single')
        assert selection['fallback']==(mode=='bad_output')
    assert len(calls)==(0 if mode=='single' else 1)
