import copy
from collections import Counter
import pytest
from integration.pokechamp.rule_qa.state import bounded_actor,correct,CONFUSION
from integration.pokechamp.rule_qa.partition import assign
from integration.pokechamp.rule_qa.records import render,messages
from integration.pokechamp.rule_qa.validation import assert_record


def test_cutoff_rejects_foreign_request_and_ignores_future():
    actor=dict(protocol='|turn|1\n|turn|2\n|win|future',request={'side':{'id':'p1'}},own_team='own')
    assert bounded_actor(actor,2)['protocol']=='|turn|1\n|turn|2'
    actor['protocol']+='\n|request|PRIVATE_OPPONENT'
    assert bounded_actor(actor,2)['protocol']=='|turn|1\n|turn|2'
    actor['request']['side']['id']='p2'
    with pytest.raises(ValueError,match='foreign'):bounded_actor(actor,2)


def test_confusion_status_namespace_does_not_modify_the_attack():
    move=dict(id='confusion',name='Confusion',general_effect='Has a 10% chance to confuse the target.',kind='moves')
    raw={'state':{'version':'jev-choice-v6','self_team':[{'volatiles':{'confusion':{'observed':[3], 'general_rules':[copy.deepcopy(move)]}},'current_move_slots':[copy.deepcopy(move)],'stats':{'atk':123}}]}}
    frozen=copy.deepcopy(raw)
    fixed,edits=correct(raw)
    assert raw==frozen
    mon=fixed['state']['self_team'][0]
    assert mon['current_move_slots']==[move]
    assert mon['volatiles']['confusion']['general_rules'][0]['general_effect']==CONFUSION
    assert mon['stats']=={'atk':123}
    assert {e['path'][-1] for e in edits}=={'name','kind','general_effect'}


def dataset():
    return [dict(spec={'group_id':f'R{r:02}-{i:02}'},input={'state':{'meaningful_condition':[r,i,v]}},
                 question={'facts':{'numerical_condition':[r,i,v]},'conditions':'Gen9','question':'What follows?'})
            for r in range(1,25) for i in range(40) for v in (0,1)]


def test_duplicate_components_are_not_split_and_counts_are_exact():
    rows=dataset()
    rows[2]['question']=copy.deepcopy(rows[0]['question'])
    splits,clusters=assign(rows,40)
    assert splits['R01-00']==splits['R01-01']
    assert assign(rows,40)[0]==splits
    for r in range(1,25):
        assert Counter(v for k,v in splits.items() if k.startswith(f'R{r:02}-'))==dict(train=32,validation=4,test=4)


def test_unpartitionable_duplicate_population_is_blocked():
    rows=dataset()
    for row in rows[:80]:row['question']=copy.deepcopy(rows[0]['question'])
    with pytest.raises(ValueError,match='duplicate contrast|cannot allocate'):assign(rows,40)


def test_export_projection_does_not_serialize_metadata_or_answer_in_prompt():
    spec=dict(scenario_id='R01-00-0',rule_id='R01',group_id='R01-00')
    q=dict(conditions='Gen9',facts={'attacking_type':'Normal'},question='Multiplier?',answer='0×',rationale='Ghost is immune.',distractors=['1×','2×'])
    payload={'state':{'version':'jev-ruleqa-state-v1'},'battle_actions':{'switch_2':{'kind':'switch','slot':2}}}
    row=render(spec,payload,q)[-1]
    assert_record(row)
    row.update(seed='PRIVATE',oracle='PRIVATE')
    assert 'PRIVATE' not in str(messages(row,include_answer=False))
    row['answer_id']='Z'
    with pytest.raises(ValueError,match='MC answer'):assert_record(row)


def test_question_render_is_stable_after_sorted_json_roundtrip():
    import json
    spec=dict(scenario_id='R01-00-0',rule_id='R01',group_id='R01-00')
    q=dict(conditions='Gen9',facts={'target_types':['Ghost'],'attacking_type':'Normal','damage':{'unit':'percent','reason':None,'current':[0,0]}},question='Multiplier?',
           answer='0×',rationale='Ghost is immune.',distractors=['1×','2×'])
    payload={'state':{'version':'jev-ruleqa-state-v1'},'battle_actions':{'switch_2':{'kind':'switch','slot':2}}}
    assert render(spec,payload,q)==render(spec,payload,json.loads(json.dumps(q,sort_keys=True)))


def test_cross_rule_duplicates_can_share_validation_and_test():
    rows=dataset()
    for i in range(40):
        rows[9*80+2*i+1]['question']=copy.deepcopy(rows[7*80+2*i]['question'])
    splits,_=assign(rows,40)
    for i in range(40):assert splits[f'R08-{i:02}']==splits[f'R10-{i:02}']
    for rule in ('R08','R10'):
        assert Counter(v for k,v in splits.items() if k.startswith(rule+'-'))==dict(train=32,validation=4,test=4)


def test_relabel_rejects_changed_scene_source(tmp_path):
    import json
    from integration.pokechamp.rule_qa.pipeline import verify_relabel_source,sha
    (tmp_path/'canonical.jsonl').write_text('{}\n')
    (tmp_path/'validation.json').write_text(json.dumps({'passed':True,'canonical_sha256':sha(tmp_path/'canonical.jsonl')}))
    old=dict(version='v1',state_version='state',groups_per_rule=40,specification_sha256='spec',
             identity={'data':{},'sources':{'integration/pokechamp/rule_qa/simulator.cjs':'old'}})
    (tmp_path/'manifest.json').write_text(json.dumps(old))
    changed=copy.deepcopy(old);changed['identity']['sources']['integration/pokechamp/rule_qa/simulator.cjs']='new'
    with pytest.raises(ValueError,match='scene/projection'):verify_relabel_source(tmp_path,changed)
