"""Exhaustive mechanical gates; semantic review is a separate, explicit receipt."""
from __future__ import annotations
from collections import Counter,defaultdict
import copy
import json
import os
import subprocess
from .pipeline import ROOT,checked_manifest,read,write,sha,iter_records,load_scenario,now
from .records import render,messages,digest,dumps
from .questions import evaluate,require
from .state import correct,bounded_actor,CONFUSION
from .partition import assign,semantic_key,state_key
from ..observation.build import DEFAULT_BUILD


def assert_record(row):
    require(row['representation'] in ('short_qa','state_qa','state_mc'),'unknown representation')
    if row['representation']=='short_qa':require(isinstance(row['context'],str),'short context must be English text')
    else:
        require(set(row['context'])=={'state','battle_actions'},'model context contains non-whitelisted data')
        require(row['context']['state']['version']=='jev-ruleqa-state-v1','wrong State version')
        require(bool(row['context']['battle_actions']),'empty actual legal action candidates')
    if row['representation']=='state_mc':
        opts=row['options'];require(2<=len(opts)<=4,'invalid option count')
        require(len({o['id'] for o in opts})==len(opts),'duplicate option ID')
        require(len({o['text'] for o in opts})==len(opts),'duplicate option text')
        correct_options=[o for o in opts if o['text']==row['answer']]
        require(len(correct_options)==1 and correct_options[0]['id']==row['answer_id'],'non-unique or wrong MC answer')
    else:require(not row['options'],'open answer has choices')
    # The serialization whitelist is part of the release check, not a substring blacklist.
    serialized=messages(row,include_answer=False)
    user=json.loads(serialized[1]['content'])
    require(set(user)==({'context','conditions','question','qa_options'} if row['options'] else {'context','conditions','question'}),'unexpected model-input field')


def check_correction(case):
    raw=case['evidence']['v6'];fixed,edits=correct(raw)
    require(case['input']==dict(state=fixed['state'],battle_actions=fixed['questions']['action']['criteria']),'State differs outside declared correction/projection')
    require(edits==case['evidence']['edits'],'correction ledger mismatch')
    restored=copy.deepcopy(fixed)
    for edit in edits:
        path=edit['path']
        require(path[-1] in ('name','kind','general_effect') and 'volatiles' in path and 'confusion' in path,'correction outside whitelist')
        obj=restored
        for key in path[:-1]:obj=obj[key]
        require(obj[path[-1]]==edit['after'],'correction result mismatch');obj[path[-1]]=edit['before']
    restored['state']['version']=raw['state']['version']
    require(restored==raw,'v6 observations/numbers/actions changed')
    for team in ('self_team','opponent_team'):
        for mon in fixed['state'][team]:
            volatiles=mon.get('volatiles',{})
            volatile=volatiles.get('confusion') if isinstance(volatiles,dict) else None
            if volatile:
                rules=volatile.get('general_rules',[])
                require(any(r.get('general_effect')==CONFUSION for r in rules),'confusion description missing')
                require(all(r.get('kind')=='volatile_status' for r in rules if r.get('id')=='confusion'),'confusion still classified as a move')
    return len(edits)


def check_noninterference(case,dex):
    actor=case['result']['actor'];cutoff=case['evidence']['boundary']['public_lines']
    expected=bounded_actor(actor,cutoff)
    mutated=copy.deepcopy(actor)
    mutated['protocol']+='\n|move|p2a: PRIVATE_FUTURE|Explosion|p1a: target\n|win|PRIVATE_FUTURE'
    mutated['opponent_team']='PRIVATE_SET_MUTATED';mutated['rng_seed']=[9,8,7,6];mutated['future_request']={'secret':True}
    require(bounded_actor(mutated,cutoff)==expected,'future/private material crosses the decision boundary')
    private=copy.deepcopy(case['result']['oracle'])
    private['other'].update(ability='PRIVATE_CHANGED',item='PRIVATE_CHANGED',hp=37,maxhp=999,stats={'atk':999})
    for t in private['tests'].values():
        t['log']=['|move|p2a: CHANGED_FUTURE|Explosion|p1a: target']
        t['hp_after']=[[0 for _ in side] for side in t['hp_after']]
        t['random_calls']=[]
    # Oracle mismatches are expected after tampering; compare the public-fact answer function alone.
    changed_spec=copy.deepcopy(case['spec'])
    changed_spec['scene']['other']=[{'species':'PRIVATE_SET','ability':'PRIVATE_CHANGED','evs':{'atk':252}}]
    changed_spec['scene']['seed']=[9,9,9,9]
    question=evaluate(changed_spec,case['input'],private,dex,verify=False)
    for key in ('conditions','facts','question','answer','rationale','distractors'):
        require(question[key]==case['question'][key],'private/future oracle influences '+key)
    irrelevant=copy.deepcopy(case['input'])
    irrelevant['battle_actions']=dict(reversed(list(irrelevant['battle_actions'].items())))
    for team in ('self_team','opponent_team'):
        for m in irrelevant['state'][team]:m['nickname']='IRRELEVANT_RENAME'
    for event in irrelevant['state']['recent_completed_turn_log']:
        for participant in event.get('participants',[]):
            name=participant.removeprefix('Your ').removeprefix('Opposing ')
            event['text']=event.get('text','').replace(name,'IRRELEVANT_RENAME')
        event['participants']=[('Your ' if p.startswith('Your ') else 'Opposing ')+'IRRELEVANT_RENAME' for p in event.get('participants',[])]
    irrelevant['state']['unrelated_diagnostic']='ignored'
    changed=evaluate(case['spec'],irrelevant,case['result']['oracle'],dex)
    require(changed['answer']==case['question']['answer'],'irrelevant nickname/order/field changes answer')


def sample_ids(groups):
    selected=[]
    for r in range(1,25):
        # Four cases per family, emphasizing exceptions and numeric boundary values.
        pairs=[(0,0),(0,1),(39,0),(39,1)]
        if r==3:pairs=[(0,1),(10,1),(20,1),(30,1)]
        if r==6:pairs=[(0,0),(0,1),(20,1),(30,1)]
        if r==9:pairs=[(0,0),(0,1),(20,0),(20,1)]
        if r==11:pairs=[(0,1),(2,1),(20,0),(22,1)]
        if r==12:pairs=[(0,1),(5,0),(23,0),(39,0)]
        if r==16:pairs=[(0,0),(2,0),(2,1),(39,1)]
        if r==22:pairs=[(0,0),(17,0),(17,1),(37,0)]
        if r==23:pairs=[(0,0),(7,1),(8,1),(39,1)]
        if r==24:pairs=[(0,0),(1,1),(2,1),(10,0)]
        if groups==1:pairs=[(0,0),(0,1)]
        selected.extend(f'R{r:02}-{i:02}-{v}' for i,v in pairs)
    return selected


def write_samples(output,ids):
    entries=[];directory=output/'representatives';directory.mkdir(exist_ok=True)
    by_rule=defaultdict(list)
    for key in ids:
        c=load_scenario(output,key);q=c['question']
        mc=render(c['spec'],c['input'],q,splits=read(output/'splits.json'))[-1]
        entry=dict(scenario_id=key,rule_id=c['spec']['rule_id'],facts=q['facts'],conditions=q['conditions'],question=q['question'],answer=q['answer'],rationale=q['rationale'],options=mc['options'],answer_id=mc['answer_id'])
        entries.append(entry)
        by_rule[c['spec']['rule_id']].append(entry)
    write(output/'review_samples.json',entries)
    for rule,rows in by_rule.items():
        text=[]
        for row in rows:
            text.append(row['scenario_id']+'\n'+json.dumps(row['facts'],ensure_ascii=False,indent=2)+'\n'+row['conditions']+'\nQ: '+row['question']+'\nA: '+row['answer']+'\nReason: '+row['rationale']+'\nOptions: '+json.dumps(row['options'],ensure_ascii=False)+'\n')
        (directory/(rule+'.txt')).write_text('\n'.join(text))


def validate(output):
    manifest=checked_manifest(output);groups=manifest['groups_per_rule'];expected=24*groups*6
    dex=read(DEFAULT_BUILD/'dex.json');splits=read(output/'splits.json')
    errors=[];counts=Counter();rule_counts=Counter();seen=set();by_scenario=defaultdict(list)
    for row in iter_records(output):
        try:
            assert_record(row)
            require(row['id'] not in seen,'duplicate question ID')
            require(row['split']==splits[row['group_id']],'derived question crosses source-group split')
            if row['representation']=='state_mc':
                permuted=copy.deepcopy(row)
                permuted['options']=[dict(id=chr(65+i),text=o['text']) for i,o in enumerate(reversed(row['options']))]
                permuted['answer_id']=next(o['id'] for o in permuted['options'] if o['text']==row['answer'])
                assert_record(permuted)
                require(next(o['text'] for o in permuted['options'] if o['id']==permuted['answer_id'])==row['answer'],'QA option permutation changes answer meaning')
            seen.add(row['id']);counts[row['split']]+=1;rule_counts[row['rule_id']]+=1;by_scenario[row['scenario_id']].append(row)
        except Exception as e:errors.append(dict(rule_id=row.get('rule_id'),scenario_id=row.get('scenario_id'),error=str(e)))
    reduced=[];corrections=0;checks=Counter();contrasts=defaultdict(list)
    for spec in read(output/'evidence/specifications.json'):
        key=spec['scenario_id']
        try:
            c=load_scenario(output,key)
            require('error' not in c,'generation failure')
            require(c['spec']==spec,'stored scenario differs from prepared specification')
            question=evaluate(spec,c['input'],c['result']['oracle'],dex)
            require(question==c['question'],'stored labels/explanations differ from structured rule evaluation')
            require(by_scenario[key]==render(spec,c['input'],question,splits=splits),'canonical expressions differ from verified facts')
            for row in by_scenario[key]:
                for field in ('conditions','question','answer','rationale'):
                    require(row[field]==question[field],'canonical field differs from public question: '+field)
                if row['representation']!='short_qa':require(row['context']==c['input'],'canonical State/actions differ from protected projection')
                if row['representation']=='state_mc':
                    require({o['text'] for o in row['options']}=={question['answer'],*question['distractors']},'canonical options differ from public question')
            corrections+=check_correction(c)
            check_noninterference(c,dex)
            reduced.append({k:c[k] for k in ('spec','input','question')})
            contrasts[spec['group_id']].append(question['answer'])
            checks.update(question['checks']);checks['information_boundary']+=1;checks['irrelevant_mutation']+=1;checks['state_preservation']+=1
        except Exception as e:errors.append(dict(rule_id=spec['rule_id'],scenario_id=key,error=type(e).__name__+': '+str(e)))
    for group,answers in contrasts.items():
        if len(answers)!=2 or answers[0]==answers[1]:errors.append(dict(rule_id=group.split('-')[0],group_id=group,error='contrast does not change the answer'))
    if len(seen)!=expected:errors.append(dict(error=f'expected {expected} questions, found {len(seen)}'))
    if any(rule_counts[f'R{r:02}']!=groups*6 for r in range(1,25)):errors.append(dict(error='per-rule count mismatch'))
    if groups==40 and counts!=dict(train=4608,validation=576,test=576):errors.append(dict(error='split row counts mismatch'))
    try:
        assigned,clusters=assign(reduced,groups)
        require(assigned==splits,'duplicate-aware deterministic split mismatch')
        require(clusters==read(output/'duplicate_clusters.json'),'duplicate cluster inventory mismatch')
        for cluster in clusters:require(len({splits[g] for g in cluster})==1,'near/exact duplicate group split leakage')
    except Exception as e:errors.append(dict(error='partition: '+str(e)))
    # Required real-tokenizer census runs with no model weights or network access.
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='1')
    result=subprocess.run([str(ROOT/'.pokechamp-data/jev27b-runtime/.venv/bin/python'),'-m','integration.pokechamp.rule_qa.lengths',str(output)],env=env,text=True,capture_output=True)
    if result.returncode:errors.append(dict(error='tokenizer census failed: '+result.stderr[-4000:]))
    elif not read(output/'lengths.json')['passed']:errors.append(dict(error='token limit exceeded'))
    write_samples(output,sample_ids(groups))
    checks['qa_option_permutations']=sum(r['representation']=='state_mc' for rows in by_scenario.values() for r in rows)
    report=dict(passed=not errors,validated_at=now(),canonical_sha256=sha(output/'canonical.jsonl'),
                questions=len(seen),scenarios=len(by_scenario),counts=dict(counts),per_rule=dict(rule_counts),
                checks=dict(checks),correction_fields=corrections,errors=errors,
                blocked_rules=sorted({e['rule_id'] for e in errors if e.get('rule_id')}),
                semantic_review='pending separate review receipt',tokenizer_report='lengths.json',
                duplicate_policy='Join equal minimal public fact/condition/question cases and identical normalized States at source-group level. Nicknames/request IDs are ignored; actual species, moves and relevant numerical inputs retain their meaning. This is a within-template split, not an unseen-template generalization test.')
    write(output/'validation.json',report)
    manifest.update(status='validated_pending_semantic_review' if not errors else 'validation_failed',validation=report)
    write(output/'manifest.json',manifest)
    if errors:raise ValueError(f'{len(errors)} validation errors; export blocked; see {output}/validation.json')
    return dict(passed=True,questions=len(seen),scenarios=len(by_scenario),counts=dict(counts),semantic_review='pending')
