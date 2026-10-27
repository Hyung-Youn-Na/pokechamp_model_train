"""Reviewed Smogon annotations -> multi-role support and direct choice CE data."""
import argparse
from collections import Counter,defaultdict
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
from transformers import AutoTokenizer
from integration.jevk5_battle import upstream_prompt as official

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
SOURCE=ROOT/'data/smogon-dex/strategies/gen9ou-20261019'
ANNOTATIONS=ROOT/'project_context/exec-plans/evidence/ep200'
DEFAULT=Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/smogon-role-system1/v1')
MODEL=Path('/root/.cache/huggingface/hub/models--alibiserikbay--JevK5-9B/snapshots/d6521a18a86999190e9d775c915af3d6d6772fc4')
FIELDS=['pokemon','levels','abilities','items','teratypes','moveslots','evconfigs','ivconfigs','natures']
OPTIONS=['Supported by the included Smogon analysis','Not established by the included analysis annotation']
INSTRUCTION=('For this fully specified Smogon set family, classify whether the included analysis supports the queried role. '
 'At least one listed variant may provide the role under its stated conditions; not every option combination must have it. '
 'Multiple roles can be supported. Not established means no accepted annotation support in this snapshot, NOT that the Pokemon cannot perform the role. '
 'Do not infer a single main role, current battle role or optimal action. Choose one answer without an explanation.')


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def write(f,x):f.write(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')


def configuration(row):
    result={k:copy.deepcopy(row[k]) for k in FIELDS}
    # List order does not distinguish otherwise identical set families. Keep move-slot alternatives grouped.
    for k in FIELDS:
        if isinstance(result[k],list):
            if k=='moveslots':result[k]=[sorted(slot,key=lambda x:json.dumps(x,sort_keys=True)) for slot in result[k]]
            result[k]=sorted(result[k],key=lambda x:json.dumps(x,sort_keys=True))
    return result


def role_input(config,role):
    return {'state':{'set_family':config,'queried_role':{'id':role['id'],'definition':role['definition']},
                     'scope':'Smogon Gen9 OU snapshot collected 2026-10-19. Structured options only; hidden battle sets are not inferred.'},
            'question':{'type':'choice','instructions':INSTRUCTION}}


def render(row):
    q=row['input']['question'];return official.prompt_text(row['input']['state'],q['instructions'],[v for _,v in official.decision_options(q)])


def build(output):
    if output.exists():raise FileExistsError('Existing snapshots preserved; choose a new output')
    source_seal={}
    for l in (SOURCE/'checksums.sha256').read_text().splitlines():
        h,n=l.split('  ',1)
        if n in ['sets.jsonl','strategies.jsonl','manifest.json','validation.json','statistics.json']:
            assert sha(SOURCE/n)==h,n;source_seal[n]=h
    assert 'sets.jsonl' in source_seal and 'strategies.jsonl' in source_seal
    source=[json.loads(l) for l in (SOURCE/'sets.jsonl').read_text().splitlines()]
    assert len(source)==215 and len({r['set_id'] for r in source})==215
    included={r['set_id']:r for r in source if not r['strategy_outdated'] and r['description_text'].strip()}
    assert len(included)==177
    roles=json.loads((HERE/'roles.json').read_text());role_ids=[r['id'] for r in roles];assert len(role_ids)==len(set(role_ids))==21
    annotation_paths=[ANNOTATIONS/f'annotations-{i}.json' for i in range(3)]
    annotations=[]
    for p in annotation_paths:annotations.extend(json.loads(p.read_text()))
    assert len(annotations)==177 and {a['set_id'] for a in annotations}==set(included)
    annotated={};grouped={};role_count=Counter();evidence_count=0
    for a in annotations:
        r=included[a['set_id']];assert a['reviewed'] is True
        assert len({x['role_id'] for x in a['roles']})==len(a['roles'])
        evidences=[]
        for item in a['roles']:
            assert item['role_id'] in role_ids
            quote=item['evidence_quote'];assert quote.strip() and quote in r['description_text'],(r['set_id'],item['role_id'],quote)
            start=r['description_text'].index(quote)
            assert item['claim'].strip() and isinstance(item['conditions'],str)
            evidences.append({'role_id':item['role_id'],'source_set_id':r['set_id'],'source_strategy_id':r['strategy_id'],
                'source_urls':r['source_urls'],'description_text_sha256':hashlib.sha256(r['description_text'].encode()).hexdigest(),
                'evidence_char_start':start,'evidence_char_end':start+len(quote),
                'evidence_sha256':hashlib.sha256(quote.encode()).hexdigest(),
                'annotation_claim':item['claim'],'conditions':item['conditions']})
            role_count[item['role_id']]+=1;evidence_count+=1
        annotated[r['set_id']]={'set_id':r['set_id'],'documented_role_ids':sorted(x['role_id'] for x in evidences),
            'evidence':evidences,'annotation_notes':a.get('notes',''),'set_title_for_reference_only':r['name'],'pokemon':r['pokemon'],
            'source_urls':r['source_urls'],'reviewed':True}
        config=configuration(r);key=digest(config)[:24]
        group=grouped.setdefault(key,{'id':key,'configuration':config,'source_set_ids':[],'documented_roles':set(),'evidence':[]})
        group['source_set_ids'].append(r['set_id']);group['documented_roles'].update(x['role_id'] for x in evidences);group['evidence'].extend(evidences)
        # No title/body/annotation/metadata field may influence the input configuration.
        probe=copy.deepcopy(r)
        for k in ['name','description_html','description_text','source_set','set_id','strategy_id','source_urls','referenced_urls','strategy_added','strategy_edited']:
            probe[k]='LEAK_SENTINEL'
        assert configuration(probe)==config
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True);label_ids=[tok.encode(c,add_special_tokens=False) for c in 'AB']
    assert all(len(x)==1 for x in label_ids)
    output.mkdir(parents=True)
    rows=[];texts=[];outcomes=Counter();group_records=[]
    for group in grouped.values():
        positive=group['documented_roles']
        group_records.append({'metadata':{'group_id':group['id'],'source_set_ids':group['source_set_ids'],'species_group':group['configuration']['pokemon']},
            'input':{'set_family':group['configuration']},'role_order':role_ids,
            'source_support_targets':[int(k in positive) for k in role_ids],
            'supported_role_ids':sorted(positive),'target_semantics':'1=annotated support; 0=not established, NOT role impossibility'})
        for role in roles:
            supported=role['id'] in positive;semantic_index=0 if supported else 1
            key=group['id']+'-'+role['id'];order=sorted(range(2),key=lambda j:digest([key,j]));target=order.index(semantic_index)
            inp=role_input(group['configuration'],role);inp['question']['criteria']={chr(65+i):OPTIONS[j] for i,j in enumerate(order)}
            row={'metadata':{'id':key,'group_id':group['id'],'species_group':group['configuration']['pokemon'],
                  'source_set_ids':group['source_set_ids'],'queried_role_id':role['id'],'label_basis':'Codex annotation grounded in Smogon description; not official Smogon role tags'},
                 'input':inp,'target_index':target,'target_distribution':[int(i==target) for i in range(2)],
                 'evidence':{'supported':supported,'positive_support':[e for e in group['evidence'] if e['role_id']==role['id']],
                             'absent_label_scope':'No accepted annotation support within the included descriptions; not a claim of actual role inability'}}
            text=render(row)
            assert text==tok.apply_chat_template(official.messages(inp['state'],INSTRUCTION,[v for _,v in official.decision_options(inp['question'])]),tokenize=False,add_generation_prompt=True,enable_thinking=False)
            probe=copy.deepcopy(row);probe['metadata']={};probe['evidence']={};probe['target_index']=1-target
            assert render(probe)==text
            rows.append(row);texts.append(text);outcomes[OPTIONS[semantic_index]]+=1
    with (output/'canonical.jsonl').open('w') as ca,(output/'all.choice.jsonl').open('w') as cf,(output/'all.jevk5.tokens.jsonl').open('w') as tf:
        lengths=[]
        for start in range(0,len(rows),128):
            enc=tok(texts[start:start+128],add_special_tokens=False,padding=False,truncation=False)['input_ids']
            for i,ids in enumerate(enc,start):
                assert 0<len(ids)<=6144 and tok.decode(ids,skip_special_tokens=False)==texts[i]
                r=rows[i];lengths.append(len(ids));write(ca,r);write(cf,{k:r[k] for k in ['metadata','input','target_index','target_distribution']})
                write(tf,{'metadata':r['metadata'],'input_ids':ids,'label_ids':[x[0] for x in label_ids],'target':r['target_index'],'expected':r['target_distribution'],'option_ids':['A','B']})
    with (output/'sets.multilabel.jsonl').open('w') as f:
        for r in group_records:write(f,r)
    with (output/'all.choice.jsonl').open() as cf,(output/'all.jevk5.tokens.jsonl').open() as tf:
        for r,c,t in zip(rows,cf,tf,strict=True):
            c=json.loads(c);t=json.loads(t)
            assert c['input']==r['input'] and c['target_index']==t['target']==r['target_index']
            assert list(c['input']['question']['criteria'].values())[c['target_index']]==OPTIONS[0 if r['evidence']['supported'] else 1]
            assert t['input_ids']==tok.encode(render(r),add_special_tokens=False)
    dump(output/'annotations.json',list(annotated.values()));shutil.copyfile(HERE/'roles.json',output/'roles.json')
    excluded=[{'set_id':r['set_id'],'pokemon':r['pokemon'],'reason':'outdated_analysis' if r['strategy_outdated'] else 'empty_source_description','source_urls':r['source_urls']} for r in source if r['set_id'] not in included]
    dump(output/'excluded-sets.json',excluded)
    strategies={r['strategy_id']:r for r in map(json.loads,(SOURCE/'strategies.jsonl').read_text().splitlines())}
    dump(output/'source-attribution.json',[{k:strategies[s][k] for k in ['strategy_id','added','edited','source_refs','credits']} for s in sorted({r['strategy_id'] for r in included.values()})])
    korean={r['id']:r['name_ko'] for r in roles}
    with (output/'roles.ko.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['세트ID','포켓몬','세트명_참조용','본문근거역할','조건부근거','출처'])
        for r in annotated.values():
            w.writerow([r['set_id'],r['pokemon'],r['set_title_for_reference_only'],'; '.join(korean[x] for x in r['documented_role_ids']),
                        '; '.join(f"{korean[x['role_id']]}: {x['conditions']}" for x in r['evidence'] if x['conditions']),'; '.join(r['source_urls'])])
    coverage={'source_sets':215,'site_current_sets':208,'annotated_nonempty_sets':177,
        'excluded_outdated_sets':sum(r['reason']=='outdated_analysis' for r in excluded),
        'excluded_empty_current_sets':sum(r['reason']=='empty_source_description' for r in excluded),
        'unique_configuration_groups':len(grouped),'species':len({r['pokemon'] for r in included.values()}),
        'sets_with_no_scoped_positive_annotation':sum(not a['roles'] for a in annotations),
        'roles':21,'source_positive_annotations':evidence_count,'positive_annotations_by_role':dict(role_count),
        'training_questions':len(rows),'targets':dict(outcomes),'split':'training_pool_only; group by config/strategy/species, not independent rows'}
    validation={'passed':True,'all_177_descriptions_annotation_records_present':True,'source_evidence_spans_checked':evidence_count,
        'configuration_metadata_mutation_checks':177,'native_template_and_label_metadata_mutation_checks':len(rows),
        'persisted_alignment':len(rows),'input_tokens':{'min':min(lengths),'max':max(lengths)},
        'raw_description_or_set_title_in_model_input':False,'original_role_db_labels_used':False,
        'annotation_is_smogon_official_label':False,'human_blind_review':False,'model_forward':False,'training':False}
    dump(output/'coverage.json',coverage);dump(output/'validation.json',validation)
    samples={}
    for r in rows:
        key=r['metadata']['queried_role_id']+'-'+str(r['evidence']['supported']);samples.setdefault(key,r)
    dump(output/'review_samples.json',samples)
    shutil.copyfile(HERE/'README.md',output/'README.md');shutil.copyfile(HERE/'loss.py',output/'loss.py')
    src=output/'generator-source';src.mkdir()
    for p in HERE.iterdir():
        if p.is_file() and p.suffix in ['.py','.json']:shutil.copyfile(p,src/p.name)
    for name in ['LICENSE','NOTICE']:shutil.copyfile(ROOT/'integration/jevk5_battle'/name,output/('PROMPT_'+name))
    dump(output/'manifest.json',{'schema':'smogon-role-system1-v1','plan':'EP-200','decision':'D-177',
        'source_snapshot':str(SOURCE),'source_seal':source_seal,'annotation_files':{str(p.relative_to(ROOT)):sha(p) for p in annotation_paths},
        'sources':{str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.is_file()},
        'prompt_source_sha256':sha(ROOT/'integration/jevk5_battle/upstream_prompt.py'),
        'tokenizer':str(MODEL),'tokenizer_files':{p.name:sha(p) for p in MODEL.iterdir() if p.is_file() and ('token' in p.name or 'chat' in p.name)},
        'coverage':coverage,'validation':validation,'files':{str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file()}})
    (output/'checksums.sha256').write_text(''.join(f'{sha(p)}  {p.relative_to(output)}\n' for p in sorted(output.rglob('*')) if p.is_file() and p.name!='checksums.sha256'))
    return {'coverage':coverage,'validation':validation}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=DEFAULT);a=p.parse_args();print(json.dumps(build(a.output),ensure_ascii=False,indent=2))
