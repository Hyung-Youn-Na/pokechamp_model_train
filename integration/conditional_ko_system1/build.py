"""Keep observed replay labels intact; create separately marked conditional problems."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from transformers import AutoTokenizer
from integration.jevk5_battle import upstream_prompt as official

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
PARENT=Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/replay-ko-system1/v1')
DEFAULT=PARENT.parents[1]/'conditional-ko-system1/v1'
MODEL=Path('/root/.cache/huggingface/hub/models--alibiserikbay--JevK5-9B/snapshots/d6521a18a86999190e9d775c915af3d6d6772fc4')
OPTIONS=['Guaranteed KO under the stated conditions','KO depends on the damage roll','Cannot KO under the stated conditions']
INSTRUCTION=('Classify direct-target KO under the explicitly supplied fixed conditions using the verified minimum and maximum damage. '
 'The action reaches damage resolution, passes accuracy, is noncritical, and has one hit. Type immunity remains in force. '
 'Current target HP is exact in this controlled problem. This is not a claim about the original replay\'s hidden set or outcome. '
 'Use the provided damage bounds; do not predict damage or action order. Choose one option without explanation.')


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def line(f,x):f.write(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')


def classify(low,high,hp):
    if not(0<=low<=high and hp>0):raise ValueError('Invalid bounds/HP')
    return 0 if low>=hp else 1 if high>=hp else 2


def active_species(history):
    active={}
    for text in history:
        f=text.split('|')
        if len(f)>3 and f[1].lower() in {'switch','drag','detailschange','-formechange'}:
            active[f[2]]=f[3].split(',')[0]
    return active


def render(row):
    q=row['input']['question'];return official.prompt_text(row['input']['state'],q['instructions'],[v for _,v in official.decision_options(q)])


def build(output):
    if output.exists():raise FileExistsError('Existing data preserved; choose a new output')
    for l in (PARENT/'checksums.sha256').read_text().splitlines():
        h,n=l.split('  ',1);assert sha(PARENT/n)==h,n
    parent=[json.loads(l) for l in (PARENT/'canonical.jsonl').read_text().splitlines()];assert len(parent)==3981
    profiles={};unmapped=[]
    for r in parent:
        attack=r['input']['state']['proposed_attack'];active=active_species(r['input']['state']['public_history'])
        if attack['actor'] not in active or attack['target'] not in active:
            unmapped.append(r['metadata']['id']);continue
        value={'attacker':active[attack['actor']],'defender':active[attack['target']],'move':attack['move']}
        key=digest(value)[:24]
        profiles.setdefault(key,dict(key=key,**value,source_ids=[],source_replays=[]))
        profiles[key]['source_ids'].append(r['metadata']['id']);profiles[key]['source_replays'].append(r['metadata']['replay_id'])
    output.mkdir(parents=True)
    with (output/'original-replay-qualification.jsonl').open('w') as f:
        for r in parent:
            line(f,{'source_id':r['metadata']['id'],'replay_id':r['metadata']['replay_id'],
                'conditional_ko_label':None,'qualification':'Not verified: original exact sets and noncritical damage bounds unavailable in this export',
                'display_ko_category':'정보 부족 — 원경기 조건부 KO 미판정',
                'observed_dataset_preserved':True,'use_as_conditional_training_target':False})
    requests=list(profiles.values());dump(output/'profile-requests.json',requests)
    result=json.loads(subprocess.check_output(['node',str(HERE/'calculate.cjs'),str(output/'profile-requests.json')],text=True))
    dump(output/'calculation-evidence.json',result)
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    label_ids=[tok.encode(c,add_special_tokens=False) for c in 'ABC'];assert all(len(x)==1 for x in label_ids)
    rows=[];texts=[];targets=[];labels=Counter()
    for p in result['profiles']:
        damages=[x['damage'] for x in p['rolls']]
        low=min(damages);high=max(damages);maximum=p['target_max_hp']
        assert len(p['rolls'])==16 and low==p['min_damage'] and high==p['max_damage']
        hps={maximum}
        if low>0:hps.add(min(low,maximum))
        if low<high and low+1<=maximum:hps.add(low+1)
        if high+1<=maximum:hps.add(high+1)
        for hp in sorted(hps):
            expected=classify(low,high,hp)
            ko_rolls=sum(v>=hp for v in damages)
            assert expected==(0 if ko_rolls==16 else 2 if ko_rolls==0 else 1)
            engine_check=next(x for x in p['validation']['hp_application_boundary_checks'] if x['target_hp']==hp)
            assert engine_check['ko_roll_count']==ko_rolls
            if expected==0:assert all(max(0,hp-v)==0 for v in damages)
            elif expected==2:assert all(hp-v>0 for v in damages)
            key=p['key']+f'-hp{hp}'
            order=sorted(range(3),key=lambda i:digest([key,i]));target=order.index(expected)
            state={'provenance_scope':'Controlled hypothetical profile. Species/move are replay-derived; exact sets and current HP are supplied assumptions, NOT reconstructed original values.',
                'conditions':p['conditions'],'attacker':p['attacker'],'defender':dict(p['defender'],current_hp=hp,max_hp=maximum),
                'move':p['move'],'verified_noncritical_damage_range_hp':[low,high],
                'damage_range_scope':'One hit under these exact assumptions; the 16 standard damage factors are enumerated. Immunity is included; no KO-prevention ability/item/volatile is present.'}
            row={'metadata':{'id':key,'profile_group':p['key'],'source_ids':profiles[p['key']]['source_ids'],
                           'source_replays':sorted(set(profiles[p['key']]['source_replays'])),
                           'hp_origin':'Controlled boundary/full-HP exercise, not observed replay HP'},
                'input':{'state':state,'question':{'type':'choice','instructions':INSTRUCTION,'criteria':{chr(65+j):OPTIONS[i] for j,i in enumerate(order)}}},
                'target_index':target,'target_distribution':[int(j==target) for j in range(3)],
                'evidence':{'class_index':expected,'damage_rolls':damages,'ko_rolls':ko_rolls,'source_profile':p['key']}}
            text=render(row);q=row['input']['question']
            assert text==tok.apply_chat_template(official.messages(state,INSTRUCTION,[v for _,v in official.decision_options(q)]),tokenize=False,add_generation_prompt=True,enable_thinking=False)
            probe=copy.deepcopy(row);probe['metadata']={};probe['evidence']={};probe['target_index']=(target+1)%3
            assert render(probe)==text
            rows.append(row);texts.append(text);targets.append(target);labels[OPTIONS[expected]]+=1
    assert len(labels)==3 and len(rows)>0
    lengths=[]
    with (output/'canonical.jsonl').open('w') as ca,(output/'all.choice.jsonl').open('w') as cf,(output/'all.jevk5.tokens.jsonl').open('w') as tf:
        for start in range(0,len(rows),128):
            enc=tok(texts[start:start+128],add_special_tokens=False,padding=False,truncation=False)['input_ids']
            for i,ids in enumerate(enc,start):
                assert 0<len(ids)<=6144 and tok.decode(ids,skip_special_tokens=False)==texts[i]
                lengths.append(len(ids));r=rows[i];line(ca,r);line(cf,{k:r[k] for k in ['metadata','input','target_index','target_distribution']})
                line(tf,{'metadata':r['metadata'],'input_ids':ids,'label_ids':[v[0] for v in label_ids],'target':r['target_index'],'expected':r['target_distribution'],'option_ids':['A','B','C']})
    with (output/'all.choice.jsonl').open() as cf,(output/'all.jevk5.tokens.jsonl').open() as tf:
        for row,c,t in zip(rows,cf,tf,strict=True):
            c=json.loads(c);t=json.loads(t)
            assert c['input']==row['input'] and c['target_index']==t['target']==row['target_index']
            assert t['input_ids']==tok.encode(render(row),add_special_tokens=False)
    samples={}
    for r in rows:samples.setdefault(OPTIONS[r['evidence']['class_index']],r)
    dump(output/'review_samples.json',samples)
    coverage={'original_replay_records':len(parent),'original_records_relabelled_as_guaranteed':0,'original_records_unverified':len(parent),
        'requested_unique_profiles':len(requests),'supported_profiles':len(result['profiles']),
        'excluded_profiles':len(result['exclusions']),'profile_exclusions':dict(Counter(x['reason'] for x in result['exclusions'])),
        'unmapped_original_rows':len(unmapped),'training_questions':len(rows),'classes':dict(labels),
        'split':'Controlled training pool; no validation/test. Group by profile and connected replay IDs.',
        'task':'Classify KO from supplied verified damage bounds and exact HP, not predict damage from a raw replay.'}
    validation={'passed':True,'engine_profiles':len(result['profiles']),'rolls_per_profile':16,
        'boundary_and_all_rolls_label_agreement':len(rows),'native_template_and_metadata_projection':len(rows),
        'persisted_alignment':len(rows),'input_tokens':{'min':min(lengths),'max':max(lengths)},
        'original_observed_outcomes_used_for_labels':False,'model_forward':False,'training':False}
    dump(output/'coverage.json',coverage);dump(output/'validation.json',validation)
    shutil.copyfile(HERE/'README.md',output/'README.md');shutil.copyfile(HERE/'loss.py',output/'loss.py')
    src=output/'generator-source';src.mkdir()
    for p in HERE.iterdir():
        if p.is_file() and p.suffix in ['.py','.cjs']:shutil.copyfile(p,src/p.name)
    for source,name in [(ROOT/'pokemon-showdown/LICENSE','SHOWDOWN_LICENSE'),(ROOT/'integration/jevk5_battle/LICENSE','PROMPT_LICENSE'),(ROOT/'integration/jevk5_battle/NOTICE','PROMPT_NOTICE')]:shutil.copyfile(source,output/name)
    ps=ROOT/'pokemon-showdown';commit=subprocess.check_output(['git','-C',str(ps),'rev-parse','HEAD'],text=True).strip()
    assert commit=='e64915c0eab066db1d3e732b1280386468dd7415'
    dump(output/'manifest.json',{'schema':'conditional-ko-system1-v1','plan':'EP-199','decision':'D-176',
        'parent':str(PARENT),'parent_manifest_sha256':sha(PARENT/'manifest.json'),'parent_canonical_sha256':sha(PARENT/'canonical.jsonl'),
        'showdown_commit':commit,'engine_sources':{str(p.relative_to(ROOT)):sha(p) for folder in ['dist/sim','dist/data','dist/lib'] for p in (ps/folder).glob('*.js')},
        'sources':{str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.is_file()},
        'prompt_source_sha256':sha(ROOT/'integration/jevk5_battle/upstream_prompt.py'),
        'tokenizer':str(MODEL),'tokenizer_files':{p.name:sha(p) for p in MODEL.iterdir() if p.is_file() and ('token' in p.name or 'chat' in p.name)},
        'coverage':coverage,'validation':validation,'files':{str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file()}})
    (output/'checksums.sha256').write_text(''.join(f'{sha(p)}  {p.relative_to(output)}\n' for p in sorted(output.rglob('*')) if p.is_file() and p.name!='checksums.sha256'))
    return {'coverage':coverage,'validation':validation}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=DEFAULT);a=p.parse_args();print(json.dumps(build(a.output),ensure_ascii=False,indent=2))
