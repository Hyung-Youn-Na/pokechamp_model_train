"""Bounded train-only real-replay corpus, conditional observed-outcome labels."""
from collections import Counter
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import pyarrow.parquet as pq
from transformers import AutoTokenizer
from integration.jevk5_battle import upstream_prompt as official
from .parser import extract,projection,public_prefix,to_id,OUTCOMES
from .audit import audit_raw

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
SOURCE=Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/milkkarten/pokechamp')
DEFAULT=SOURCE.parents[1]/'generated/replay-ko-system1/v1'
MODEL=Path('/root/.cache/huggingface/hub/models--alibiserikbay--JevK5-9B/snapshots/d6521a18a86999190e9d775c915af3d6d6772fc4')
MAX_GAMES=1000;MAX_SCAN=10000;MAX_TOKENS=6144
QUESTION=('Predict the realized outcome of the proposed attack: did its direct damage knock out the stated target during its immediate resolution? '
 'The proposed actor/move/target is given as a condition, not a prediction of the chosen action. '
 'Use only the pre-attack public history. Hidden sets, exact HP, accuracy rolls and critical hits are unknown. '
 'This is a realized-outcome prediction task, not a guaranteed-KO calculation, counterfactual action value or optimal-action question.')


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def write(f,x):f.write(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
def numeric_id(x):
    m=re.search(r'(?<!\d)(\d{6,})(?!\d)',x)
    return m[1] if m else x


def dex_data():
    code="""const {Dex}=require('./pokemon-showdown/dist/sim');const d=Dex.forFormat('gen9ou');console.log(JSON.stringify({moves:Object.fromEntries(d.moves.all().map(m=>[m.id,{category:m.category,name:m.name}])),species:Object.fromEntries(d.species.all().map(s=>[s.id,s.baseSpecies]))}));"""
    return json.loads(subprocess.check_output(['node','-e',code],cwd=ROOT,text=True))


def protection(species):
    directory=ROOT/'.pokechamp-data/experiments/ex071-qwen-replay-imitation'
    paths=[directory/'preparation/groups.json',directory/'preparation/replays.jsonl',directory/'preparation/historical-teams.json',directory/'schedule.json']
    assignment=json.loads(paths[0].read_text())['assignment']
    held={k for k,v in assignment.items() if v['split'] in ['validation','test']}
    def signature(names):return '|'.join(sorted(to_id(species.get(to_id(n),n)) for n in names))
    ids={numeric_id(p.name) for p in (ROOT/'data/showdown-replays/raw').glob('*gen9ou*')}
    ids.update(numeric_id(k) for k in held)
    signatures=set()
    for line in paths[1].read_text().splitlines():
        r=json.loads(line)
        if r['replay_id'] in held:
            signatures.update(signature(t) for t in r['teams'].values())
    for row in json.loads(paths[2].read_text()):signatures.add(signature(row['species']))
    for row in json.loads(paths[3].read_text()):
        for team in row['teams'].values():signatures.add(signature(team['species']))
    return ids,signatures,signature,{'known_excluded_ids':len(ids),'known_excluded_coarse_team_signatures':len(signatures),
        'metadata_sources':{str(p):sha(p) for p in paths},'local_raw_filename_ids_sha256':digest(sorted(ids)),
        'method':'All local Gen9OU replay IDs; EX071 validation/test team rosters and historical/evaluation teams, collapsed to base species. Test replay content not opened.'}


def render(row):
    return official.prompt_text(row['input']['state'],row['input']['question']['instructions'],
                                [v for _,v in official.decision_options(row['input']['question'])])


def build(output):
    if output.exists():raise FileExistsError('Choose a new output; existing datasets are preserved')
    output.mkdir(parents=True);(output/'source-evidence').mkdir()
    archive=json.loads((SOURCE/'manifest.json').read_text())
    assert archive['revision']=='b5820ff5d0c8d5e5cec692d55f756b6e5a66a203'
    archived={r['path']:r['sha256'] for r in archive['files']}
    ps=ROOT/'pokemon-showdown'
    dex_pin=subprocess.check_output(['git','-C',str(ps),'rev-parse','HEAD'],text=True).strip()
    assert dex_pin=='e64915c0eab066db1d3e732b1280386468dd7415'
    dex_sources={str(p.relative_to(ROOT)):sha(p) for folder in ['dist/sim','dist/data','dist/lib'] for p in (ps/folder).glob('*.js')}
    dex=dex_data();dump(output/'dex-reference.json',dex)
    excluded_ids,excluded_teams,signature,protect_receipt=protection(dex['species'])
    tok=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
    label_ids=[tok.encode(c,add_special_tokens=False) for c in 'AB'];assert all(len(a)==1 for a in label_ids)
    counters=Counter();games=[];allrows=[];tokens=[];seen_ids=set();seen_logs=set();read_shards={};rejected=[];move_rejections=Counter()
    parser_sources={str(p.relative_to(ROOT)):sha(p) for p in sorted(HERE.glob('*.py'))}
    for path in sorted((SOURCE/'data').glob('train-*.parquet')):
        relative=str(path.relative_to(SOURCE));assert path.name.startswith('train-')
        actual=sha(path);assert actual==archived[relative],relative;read_shards[relative]=actual
        offset=0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=256):
            for j,source in enumerate(batch.to_pylist()):
                counters['source_rows_scanned']+=1
                if source['gamemode']!='gen9ou':continue
                counters['gen9ou_replays_considered']+=1
                bid=source['battle_id'];short=numeric_id(bid);lines=source['text'].splitlines()
                reason=None
                if short in excluded_ids:reason='known_local_or_evaluation_replay_id'
                if short in seen_ids:reason='duplicate_replay_id'
                seen_ids.add(short)
                rawkey=digest(public_prefix(lines,len(lines)))
                if rawkey in seen_logs:reason='duplicate_public_mechanics'
                seen_logs.add(rawkey)
                teams={'p1':[],'p2':[]}
                for l in lines:
                    f=l.split('|')
                    if len(f)>3 and f[1].lower()=='poke' and f[2] in teams:teams[f[2]].append(f[3].split(',')[0].replace('*','').rstrip('-'))
                sigs={k:signature(v) for k,v in teams.items()}
                if any(len(v)!=6 for v in teams.values()):reason='missing_six_member_preview'
                if set(sigs.values())&excluded_teams:reason='known_evaluation_team_roster'
                if reason:
                    counters['replay_excluded_'+reason]+=1
                    rejected.append({'battle_id':bid,'reason':reason,'source_file':relative,'source_row':offset+j})
                else:
                    candidates,failures=extract(source['text'],dex['moves']);move_rejections.update(failures)
                    counters['eligible_attack_frames_before_length']+=len(candidates)
                    # Label-aware cap is explicit; deterministic hashing selects within each realized class.
                    buckets={0:[],1:[]}
                    for c in candidates:buckets[c['target_index']].append(c)
                    selected=[]
                    for label in [0,1]:
                        for c in sorted(buckets[label],key=lambda x:digest([bid,x['move_index'],'ep198'])):
                            # Original prefix has no current action result; only identity is a given condition.
                            key=hashlib.sha256(f'{bid}:{c["move_index"]}'.encode()).hexdigest()[:24]
                            order=sorted(range(2),key=lambda value:digest([key,value]))
                            criteria={chr(65+k):OUTCOMES[value] for k,value in enumerate(order)}
                            target=order.index(label)
                            inp={'state':c['state'],'question':{'type':'choice','instructions':QUESTION,'criteria':criteria}}
                            row={'metadata':{'id':key,'replay_id':bid,'replay_group':short,'team_signatures':sigs,
                                'source_file':relative,'source_row':offset+j,'move_line_index':c['move_index'],
                                'source_log_sha256':hashlib.sha256(source['text'].encode()).hexdigest(),
                                'outcome_kind':c['outcome_kind'],'source_elo':source['elo'],'source_month':source['month_year']},
                                'input':inp,'target_index':target,'target_distribution':[int(k==target) for k in range(2)],
                                'evidence':c['evidence']|{'frame_end_index':c['frame_end'],'turn':c['turn']}}
                            text=render(row)
                            assert text==tok.apply_chat_template(official.messages(inp['state'],QUESTION,[v for _,v in official.decision_options(inp['question'])]),
                                tokenize=False,add_generation_prompt=True,enable_thinking=False)
                            ids=tok.encode(text,add_special_tokens=False)
                            if len(ids)>MAX_TOKENS:counters['candidate_over_token_limit']+=1;continue
                            assert tok.decode(ids,skip_special_tokens=False)==text
                            row['evidence']['input_tokens']=len(ids)
                            selected.append((row,ids));
                            if sum(r['metadata']['outcome_kind']=='direct_ko' if label==0 else r['metadata']['outcome_kind']!='direct_ko' for r,_ in selected)>=2:break
                    labels_present={r['metadata']['outcome_kind']=='direct_ko' for r,_ in selected}
                    if labels_present!={False,True}:
                        counters['replay_excluded_missing_both_classes_after_filters']+=1
                        rejected.append({'battle_id':bid,'reason':'missing_both_classes_after_filters','source_file':relative,'source_row':offset+j})
                    else:
                        # Full originals stay outside delivery; source rows are available for local re-audit.
                        rawfile=output/'source-evidence'/f'{short}.json';dump(rawfile,source)
                        games.append({'replay_id':bid,'source_file':relative,'source_row':offset+j,'source_log_sha256':hashlib.sha256(source['text'].encode()).hexdigest(),
                                      'team_signatures':sigs,'samples':len(selected),'raw_evidence_file':str(rawfile.relative_to(output))})
                        for row,ids in selected:
                            # Independent label/cutoff audit from the original coordinates.
                            assert row['input']['state']==projection(lines,row['metadata']['move_line_index'])
                            audit_raw(source['text'],row)
                            ev=row['evidence'];direct_zero=any(value==0 for _,value in ev['damage_events'])
                            if row['metadata']['outcome_kind']=='direct_ko':assert direct_zero and ev['faint_events']
                            else:assert not direct_zero and not ev['faint_events']
                            probe=copy.deepcopy(row);probe['metadata']={'id':'LEAK_SENTINEL'};probe['evidence']='LEAK_SENTINEL';probe['target_index']=1-row['target_index']
                            assert render(probe)==render(row)
                            allrows.append(row);tokens.append(ids)
                        counters['accepted_replays']+=1
                        if len(games)%100==0:print('accepted',len(games),'rows',len(allrows),flush=True)
                if len(games)>=MAX_GAMES or counters['gen9ou_replays_considered']>=MAX_SCAN:break
            if len(games)>=MAX_GAMES or counters['gen9ou_replays_considered']>=MAX_SCAN:break
            offset+=batch.num_rows
        if len(games)>=MAX_GAMES or counters['gen9ou_replays_considered']>=MAX_SCAN:break
    assert len(games)>0 and len(allrows)>=2*len(games)
    assert len({r['metadata']['id'] for r in allrows})==len(allrows)
    with (output/'canonical.jsonl').open('w') as canonical,(output/'all.choice.jsonl').open('w') as cf,(output/'all.jevk5.tokens.jsonl').open('w') as tf:
        for row,ids in zip(allrows,tokens,strict=True):
            write(canonical,row)
            write(cf,{k:row[k] for k in ['metadata','input','target_index','target_distribution']})
            write(tf,{'metadata':row['metadata'],'input_ids':ids,'label_ids':[v[0] for v in label_ids],
                      'target':row['target_index'],'expected':row['target_distribution'],'option_ids':['A','B']})
    # Check persisted projections against the selected source rows and labels.
    with (output/'all.choice.jsonl').open() as cf,(output/'all.jevk5.tokens.jsonl').open() as tf:
        for row,cl,tl in zip(allrows,cf,tf,strict=True):
            c=json.loads(cl);t=json.loads(tl)
            assert c['input']==row['input'] and c['target_index']==t['target']==row['target_index']
            assert t['input_ids']==tok.encode(render(row),add_special_tokens=False)
    for rel,value in parser_sources.items():assert sha(ROOT/rel)==value,'source changed during generation'
    coverage={'rows':len(allrows),'replays':len(games),'outcomes':dict(Counter(r['metadata']['outcome_kind'] for r in allrows)),
        'hit_count':dict(Counter(r['evidence']['hit_count'] for r in allrows)),
        'critical_hits':sum(r['evidence']['critical_hit'] for r in allrows),'selection_counters':dict(counters),
        'attack_frame_exclusions':dict(move_rejections),'split':'source_train_only; derived_train_pool_no_test',
        'sampling':'first eligible games in sorted train shards; within each game hash-ranked up to2 KO and2 nonKO; at least1each; not natural KO base rate'}
    validation={'passed':True,'source_train_shards_verified':len(read_shards),'source_cutoff_and_label_audited':len(allrows),
        'native_template_and_metadata_mutation_checked':len(allrows),'persisted_alignment':len(allrows),
        'max_input_tokens':max(map(len,tokens)),'min_input_tokens':min(map(len,tokens)),
        'input_truncations':0,'hidden_set_imputations':0,'target_completion_tokens':0,'model_forward':False,'training':False}
    dump(output/'coverage.json',coverage);dump(output/'validation.json',validation);dump(output/'replays.json',games)
    dump(output/'replay-exclusions.json',rejected);dump(output/'holdout-protection.json',protect_receipt)
    samples={}
    for r in allrows:
        key=r['metadata']['outcome_kind']+('_multihit' if r['evidence']['hit_count']>1 else '')+('_critical' if r['evidence']['critical_hit'] else '')
        samples.setdefault(key,r)
    dump(output/'review_samples.json',samples)
    shutil.copyfile(HERE/'README.md',output/'README.md');shutil.copyfile(HERE/'loss.py',output/'loss.py')
    shutil.copyfile(ROOT/'pokemon-showdown/LICENSE',output/'SHOWDOWN_LICENSE')
    for filename in ['LICENSE','NOTICE']:shutil.copyfile(ROOT/'integration/jevk5_battle'/filename,output/('PROMPT_'+filename))
    src=output/'generator-source';src.mkdir()
    for p in HERE.glob('*.py'):shutil.copyfile(p,src/p.name)
    dump(output/'manifest.json',{'schema':'replay-ko-system1-v1','plan':'EP-198','decision':'D-175',
        'source_dataset':archive['repository_id'],'source_revision':archive['revision'],'source_split':'train',
        'dex_reference':{'showdown_commit':dex_pin,'sources':dex_sources,'extracted_table_sha256':sha(output/'dex-reference.json')},
        'source_archive_manifest_sha256':sha(SOURCE/'manifest.json'),'read_train_shards':read_shards,
        'raw_evidence_root':str(output/'source-evidence'),
        'source_declared_license':archive['declared_license'],'source_license_note':'No declared license in archived README; no new license applied and no external publication.',
        'sources':parser_sources,'prompt_sha256':sha(ROOT/'integration/jevk5_battle/upstream_prompt.py'),
        'tokenizer':str(MODEL),'tokenizer_files':{p.name:sha(p) for p in MODEL.iterdir() if p.is_file() and ('token' in p.name or 'chat' in p.name)},
        'coverage':coverage,'validation':validation,'files':{str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file() and 'source-evidence' not in p.parts}})
    # Public derived package excludes full original records, which stay in the source-evidence directory.
    (output/'checksums.sha256').write_text(''.join(f'{sha(p)}  {p.relative_to(output)}\n' for p in sorted(output.rglob('*'))
        if p.is_file() and 'source-evidence' not in p.parts and p.name!='checksums.sha256'))
    return {'coverage':coverage,'validation':validation}


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,default=DEFAULT);args=a.parse_args();print(json.dumps(build(args.output),indent=2))
