"""Pinned simulator oracle -> leakage-free System 1 choice and tokenizer data."""
from collections import Counter
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from transformers import AutoTokenizer
from integration.jevk5_battle import upstream_prompt as official

ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).parent
DEFAULT=Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/gen9-weather-terrain-system1/v1')
MODEL=Path('/root/.cache/huggingface/hub/models--alibiserikbay--JevK5-9B/snapshots/d6521a18a86999190e9d775c915af3d6d6772fc4')
PIN='e64915c0eab066db1d3e732b1280386468dd7415'
EXPECTED_TOTAL=12178
EXPECTED_RULES=22
INSTRUCTION=('Answer the supplied Generation 9 weather/terrain mechanics question using only the stated conditions. '
 'Choose one listed answer without generating an explanation. Weather and terrain are different field layers. '
 'Distinguish damage modifiers, base-power modifiers, stat modifiers, residual HP changes and status/move prevention. '
 'These are synthetic rule exercises, not legal-set or optimal-action claims.\nQuestion: ')



def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def write(f,x):f.write(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')


def project(row):
    return {'state':row['state'],'question':{'type':'choice','instructions':INSTRUCTION+row['question'],
        'criteria':row['criteria']}}


def identity():
    ps=ROOT/'pokemon-showdown'
    commit=subprocess.check_output(['git','-C',str(ps),'rev-parse','HEAD'],text=True).strip();assert commit==PIN
    dirty=subprocess.check_output(['git','-C',str(ps),'status','--porcelain'],text=True).strip();assert not dirty
    # Built files are actual oracle dependencies; source pin alone is insufficient.
    files=list(HERE.glob('*.py'))+list(HERE.glob('*.cjs'))+[ROOT/'integration/jevk5_battle/upstream_prompt.py',ROOT/'scripts/weather-terrain-system1-data']
    files += list((ps/'dist/sim').glob('*.js'))+list((ps/'dist/data').glob('*.js'))+list((ps/'dist/lib').glob('*.js'))
    files += list((ps/'dist/data/mods/gen9').glob('*.js'))+[ps/'dist/config/formats.js']
    return {'showdown_commit':commit,'showdown_dirty':dirty,'node':subprocess.check_output(['node','--version'],text=True).strip(),
            'sources':{str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))}}


def build(output):
    if output.exists():raise FileExistsError('Use a new output; previous datasets are preserved')
    before=identity()
    rows=json.loads(subprocess.check_output(['node',str(HERE/'generate.cjs')],text=True))
    assert len(rows)==EXPECTED_TOTAL and len({r['id'] for r in rows})==len(rows)
    assert sum(r['rule_id']=='weather_defensive_stat' for r in rows)==6840
    output.mkdir(parents=True);counts=Counter(r['rule_id'] for r in rows)
    assert len(counts)==EXPECTED_RULES
    for row in rows:
        row['semantic_group']=row.get('semantic_group',row['id'])
        options=sorted(row['options'],key=lambda s:hashlib.sha256((row['id']+'|'+s).encode()).hexdigest())
        assert 2<=len(options)<=16 and len(set(options))==len(options) and options.count(row['answer'])==1
        row['criteria']={chr(65+i):v for i,v in enumerate(options)}
        row['target']=options.index(row['answer'])
    groups=Counter(r['semantic_group'] for r in rows)
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    label_tokens={n:[tok.encode(c,add_special_tokens=False) for c in official.LETTERS[:n]] for n in {len(r['options']) for r in rows}}
    for values in label_tokens.values():assert all(len(x)==1 for x in values) and len({x[0] for x in values})==len(values)
    texts=[];prepared=[];samples={}
    with (output/'canonical.jsonl').open('w') as canon,(output/'all.choice.jsonl').open('w') as choices:
        for row in rows:
            payload=project(row);n=len(row['criteria']);target=row['target']
            meta={'id':row['id'],'rule_id':row['rule_id'],'semantic_group':row['semantic_group'],
                  'inverse_rule_weight':1/counts[row['rule_id']],'inverse_group_weight':1/groups[row['semantic_group']]}
            record={'metadata':meta,'input':payload,'target_index':target,'target_distribution':[int(i==target) for i in range(n)]}
            write(canon,row);write(choices,record)
            options=[text for _,text in official.decision_options(payload['question'])]
            text=official.prompt_text(payload['state'],payload['question']['instructions'],options)
            assert text==tok.apply_chat_template(official.messages(payload['state'],payload['question']['instructions'],options),
                tokenize=False,add_generation_prompt=True,enable_thinking=False)
            probe=copy.deepcopy(row)
            for field in ['id','rule_id','semantic_group','answer','target','evidence']:probe[field]='LEAK_SENTINEL'
            assert project(probe)==payload
            texts.append(text);prepared.append({'metadata':meta,'target':target,'expected':record['target_distribution'],
                'label_ids':[x[0] for x in label_tokens[n]],'option_ids':list(row['criteria'])})
            samples.setdefault(row['rule_id'],row)
    lengths=[]
    with (output/'all.jevk5.tokens.jsonl').open('w') as f:
        for start in range(0,len(rows),128):
            batch=tok(texts[start:start+128],add_special_tokens=False,padding=False,truncation=False)['input_ids']
            for i,ids in enumerate(batch,start):
                assert 0<len(ids)<=6144 and tok.decode(ids,skip_special_tokens=False)==texts[i]
                lengths.append(len(ids));write(f,dict(prepared[i],input_ids=ids))
    with (output/'all.choice.jsonl').open() as cf,(output/'all.jevk5.tokens.jsonl').open() as tf:
        for row,cl,tl in zip(rows,cf,tf,strict=True):
            c=json.loads(cl);t=json.loads(tl)
            assert c['metadata']['id']==t['metadata']['id']==row['id']
            assert list(c['input']['question']['criteria'].values())[c['target_index']]==row['answer']
            assert c['target_index']==t['target'] and c['target_distribution']==t['expected']
    assert counts['weather_defensive_stat']==6840
    assert counts['sand_type_immunity']==3420
    assert counts['weather_damage_modifier']==360
    assert counts['terrain_base_power']==1440
    assert counts['grassy_ground_move_exception']==16
    coverage={'rows':len(rows),'rule_families':dict(counts),'semantic_groups':len(groups),
              'type_tera_grid':{'type_combinations':171,'tera_states':20,'checks_per_combination':3,'rows':10260},
              'weather_damage_grid':{'weather_states':5,'move_types':18,'attacker_umbrella_states':2,'defender_umbrella_states':2,'rows':360},
              'terrain_power_grid':{'terrain_states':5,'move_types':18,'grounded_and_semi_invulnerable_booleans':4,'rows':1440},
              'choice_counts':dict(Counter(len(r['criteria']) for r in rows)),
              'split':'train_pool_only','exhaustive_scope':'Only declared finite grids; representative ability/item/move and lifecycle examples are bounded.'}
    validation={'passed':True,'oracle_rows':len(rows),'native_template_rows':len(rows),'metadata_mutation_rows':len(rows),
                'persisted_alignment_rows':len(rows),'unique_correct_answer':True,'tokens':{'min':min(lengths),'max':max(lengths)},
                'single_token_letters':True,'answer_completion_tokens':0,'gpu_used':False,'model_forward':False,'training':False}
    dump(output/'coverage.json',coverage);dump(output/'validation.json',validation);dump(output/'review_samples.json',list(samples.values()))
    shutil.copyfile(HERE/'README.md',output/'README.md');shutil.copyfile(HERE/'loss.py',output/'loss.py')
    for source,name in [(ROOT/'pokemon-showdown/LICENSE','SHOWDOWN_LICENSE'),(ROOT/'integration/jevk5_battle/LICENSE','PROMPT_LICENSE'),(ROOT/'integration/jevk5_battle/NOTICE','PROMPT_NOTICE')]:shutil.copyfile(source,output/name)
    src=output/'generator-source';src.mkdir()
    for p in HERE.iterdir():
        if p.is_file() and p.suffix in ['.py','.cjs']:shutil.copyfile(p,src/p.name)
    assert identity()==before,'Source changed during generation'
    dump(output/'manifest.json',{'schema':'gen9-weather-terrain-system1-v1','plan':'EP-197','identity':before,
         'tokenizer':str(MODEL),'tokenizer_files':{p.name:sha(p) for p in MODEL.iterdir() if p.is_file() and ('token' in p.name or 'chat' in p.name)},
         'coverage':coverage,'validation':validation,'files':{str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file()}})
    (output/'checksums.sha256').write_text(''.join(f'{sha(p)}  {p.relative_to(output)}\n' for p in sorted(output.rglob('*')) if p.is_file() and p.name!='checksums.sha256'))
    return {'coverage':coverage,'validation':validation}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=DEFAULT);a=p.parse_args();print(json.dumps(build(a.output),ensure_ascii=False,indent=2))
