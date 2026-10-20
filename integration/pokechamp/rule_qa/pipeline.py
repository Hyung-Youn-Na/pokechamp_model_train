"""Four CPU-only CLI stages; validation receipts gate training export."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from . import VERSION,STATE_VERSION,SEED
from .specs import specifications,RULES
from .records import digest,dumps,render,messages,choice_export,split_map

ROOT=Path(__file__).resolve().parents[3]
MODULE=Path(__file__).parent
DEFAULT_OUTPUT=Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/showdown-ruleqa/v1')

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def identity():
    from ..jev_v6 import data_identity
    from ..observation.build import verify
    paths=list(MODULE.glob('*.py'))+list(MODULE.glob('*.cjs'))
    paths += [ROOT/'integration/jev_planner/candidate_labels.py', ROOT/'scripts/pokechamp-ruleqa']
    for folder in ('diagnostics','observation','improved_io','effects'):
        paths.extend(p for p in (MODULE.parent/folder).rglob('*') if p.suffix in ('.py','.cjs','.txt') and 'node_modules' not in p.parts)
    paths += [MODULE.parent/n for n in ('jev_v6.py','jev_v4.py','jev_battle.py','jev_effects.py')]
    paths += [ROOT/'pokemon-showdown/dist/data'/n for n in ('conditions.js','moves.js','abilities.js','items.js','typechart.js')]
    return dict(showdown_commit=subprocess.check_output(['git','-C',str(ROOT/'pokemon-showdown'),'rev-parse','HEAD'],text=True).strip(),
                showdown_dirty=subprocess.check_output(['git','-C',str(ROOT/'pokemon-showdown'),'status','--porcelain'],text=True).strip(),
                node=subprocess.check_output(['node','--version'],text=True).strip(),
                observation=verify(),data=data_identity(),
                sources={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))})

def prepare(output,groups):
    if (output/'manifest.json').exists():raise ValueError('output already prepared; use a new output for a changed source')
    specs=specifications(groups)
    validation=json.loads(subprocess.check_output(['node',str(MODULE/'prepare.cjs')],input=dumps(specs).encode()))
    if validation['failures']:raise ValueError('invalid Gen9 OU teams: '+dumps(validation['failures']))
    pins=identity()
    if pins['showdown_dirty']:raise ValueError('Showdown source must be clean for a pinned generation')
    manifest=dict(version=VERSION,state_version=STATE_VERSION,status='prepared',created_at=now(),seed=SEED,
                  groups_per_rule=groups,expected_scenarios=24*groups*2,expected_questions=24*groups*6,
                  rules=[dict(id=k,title=v) for k,v in RULES],specification_sha256=digest(specs),identity=pins,
                  environment=dict(python=sys.executable,max_workers=4,gpu=False,model_calls=0,downloads=0),
                  team_validation=validation,interpretation='Rule-learning material; no measured model or battle-performance improvement.',
                  staging='Controlled simulator interventions and real decision requests, not a natural-game sample. All interventions are retained in private evidence.')
    write(output/'manifest.json',manifest);write(output/'evidence/specifications.json',specs)
    write(output/'exclusions.json',[])
    return dict(status='prepared',scenarios=len(specs),questions=manifest['expected_questions'])

def checked_manifest(output):
    m=read(output/'manifest.json')
    if identity()!=m['identity']:raise ValueError('source/data/environment differs from prepared identity')
    return m

def work_chunk(specs):
    from .state import Builder
    from .questions import evaluate
    from .calculator import attach
    from ..observation.build import DEFAULT_BUILD
    dex=read(DEFAULT_BUILD/'dex.json')
    builder=Builder();rows=[]
    try:
        for spec in specs:
            case=dict(spec=spec)
            try:
                result=json.loads(subprocess.check_output(['node',str(MODULE/'simulator.cjs')],input=dumps([spec['scene']]).encode(),stderr=subprocess.PIPE))[0]
                case['result']=result
                payload,evidence=builder.build(result['actor'],spec['scenario_id'])
                case.update(input=payload,evidence=evidence)
                attach(spec,result,builder.adapter.engine)
                question=evaluate(spec,payload,result['oracle'],dex)
                case['question']=question
                rows.append(case)
            except Exception as exc:
                detail=str(exc)
                if isinstance(exc,subprocess.CalledProcessError):detail+='\n'+exc.stderr.decode(errors='replace')
                case['error']=dict(type=type(exc).__name__,detail=detail,traceback=traceback.format_exc())
                rows.append(case)
                # A failed official client is intentionally fail-closed. New independent scene, new client.
                builder.close();builder=Builder()
    finally:builder.close()
    return rows

RELABEL_ONLY_SOURCES={
    'integration/pokechamp/rule_qa/records.py',
    'integration/pokechamp/rule_qa/questions.py',
    'integration/pokechamp/rule_qa/pipeline.py',
    'integration/pokechamp/rule_qa/validation.py',
}

def verify_relabel_source(source,manifest):
    old=read(source/'manifest.json');receipt=read(source/'validation.json')
    if not receipt.get('passed') or receipt.get('canonical_sha256')!=sha(source/'canonical.jsonl'):
        raise ValueError('relabeling requires a mechanically verified, unchanged source dataset')
    if old['specification_sha256']!=manifest['specification_sha256']:
        raise ValueError('relabeling cannot change scene specifications')
    for key in ('version','state_version','groups_per_rule'):
        if old[key]!=manifest[key]:raise ValueError('relabeling changes dataset contract: '+key)
    a,b=old['identity'],manifest['identity']
    if {k:v for k,v in a.items() if k!='sources'}!={k:v for k,v in b.items() if k!='sources'}:
        raise ValueError('relabeling changes engine/data/environment identity')
    changed={p for p in set(a['sources'])|set(b['sources']) if a['sources'].get(p)!=b['sources'].get(p)}
    if not changed<=RELABEL_ONLY_SOURCES:
        raise ValueError('relabeling changes a scene/projection source: '+str(sorted(changed-RELABEL_ONLY_SOURCES)))
    return dict(source=str(source.resolve()),source_canonical_sha256=receipt['canonical_sha256'],
                source_manifest_sha256=sha(source/'manifest.json'),changed_sources=sorted(changed),
                simulator_runs=0,scene_components_preserved=['spec','input','result','evidence'])

def relabeled_rows(source,specs):
    from .questions import evaluate
    from ..observation.build import DEFAULT_BUILD
    dex=read(DEFAULT_BUILD/'dex.json')
    for spec in specs:
        case=load_scenario(source,spec['scenario_id'])
        if case['spec']!=spec or 'error' in case:raise ValueError('unverified/mismatched source scene')
        protected={k:case[k] for k in ('spec','input','result','evidence')}
        before=digest(protected)
        previous=case['question']
        case['question']=evaluate(spec,case['input'],case['result']['oracle'],dex)
        if digest(protected)!=before:raise ValueError('relabeling changed a protected scene component')
        case['label_revision']=dict(source=str(source.resolve()),protected_sha256=before,previous_question_sha256=digest(previous))
        yield case

def generate(output,workers,*,relabel_from=None):
    manifest=checked_manifest(output)
    if not 1<=workers<=4:raise ValueError('worker count must be 1..4')
    directory=output/'evidence/scenarios'
    if directory.exists() and any(directory.iterdir()):raise ValueError('generation evidence already exists; no silent overwrite/resume')
    directory.mkdir(parents=True,exist_ok=True)
    specs=read(output/'evidence/specifications.json')
    if digest(specs)!=manifest['specification_sha256']:raise ValueError('scenario specification changed')
    chunks=[specs[i:i+24] for i in range(0,len(specs),24)]
    failures=[];completed=0
    def save_rows(rows):
        nonlocal completed
        for row in rows:
            key=row['spec']['scenario_id']
            if 'error' in row:failures.append(dict(scenario_id=key,rule_id=row['spec']['rule_id'],error=row['error']))
            (directory/(key+'.json.gz')).write_bytes(gzip.compress(dumps(row).encode(),mtime=0))
            completed+=1
        write(output/'progress.json',dict(completed=completed,total=len(specs),failed=len(failures),updated_at=now()))
        print(f'Generated {completed}/{len(specs)} scenes; failures {len(failures)}',flush=True)
    if relabel_from is not None:
        provenance=verify_relabel_source(relabel_from,manifest)
        manifest['relabel_provenance']=provenance
        write(output/'relabel_provenance.json',provenance)
        rows=relabeled_rows(relabel_from,specs)
        batch=[]
        for row in rows:
            batch.append(row)
            if len(batch)==48:save_rows(batch);batch=[]
        if batch:save_rows(batch)
        workers=1
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            jobs=[pool.submit(work_chunk,c) for c in chunks]
            for job in as_completed(jobs):save_rows(job.result())
    write(output/'generation_failures.json',failures)
    from .partition import assign
    valid=[]
    for s in specs:
        case=load_scenario(output,s['scenario_id'])
        valid.append({k:case[k] for k in ('spec','input','question')} if 'error' not in case else case)
    if not failures:
        try:
            splits,clusters=assign(valid,manifest['groups_per_rule'])
        except Exception as exc:
            write(output/'partition_failure.json',dict(error=str(exc),created_at=now()))
            manifest.update(status='partition_failed',generated_scenarios=len(specs),generated_questions=0)
            write(output/'manifest.json',manifest)
            raise
        write(output/'splits.json',splits);write(output/'duplicate_clusters.json',clusters)
    else:splits=split_map()
    del valid
    records=0
    target=output/('canonical.partial.jsonl' if failures else 'canonical.jsonl')
    with target.open('w') as stream:
        for spec in specs:
            row=load_scenario(output,spec['scenario_id'])
            if 'error' in row:continue
            for item in render(spec,row['input'],row['question'],splits=splits):stream.write(dumps(item)+'\n');records+=1
    manifest.update(status='generation_failed' if failures else 'generated',generated_at=now(),generated_questions=records,
                    generated_scenarios=len(specs)-len(failures),generation_workers=workers)
    write(output/'manifest.json',manifest)
    if failures:raise ValueError(f'{len(failures)} scenario failures; export blocked')
    return dict(status='generated',scenarios=len(specs),questions=records)

def load_scenario(output,key):return json.loads(gzip.decompress((output/'evidence/scenarios'/(key+'.json.gz')).read_bytes()))

def iter_records(output):
    with (output/'canonical.jsonl').open() as stream:
        for line in stream:yield json.loads(line)

def export(output):
    manifest=checked_manifest(output);receipt=read(output/'validation.json')
    if not receipt['passed'] or manifest['groups_per_rule']!=40:raise ValueError('complete, validated v1 is required for training export')
    if receipt['canonical_sha256']!=sha(output/'canonical.jsonl'):raise ValueError('canonical data changed after validation')
    review=read(output/'semantic_review.json')
    from .validation import sample_ids
    reviews=review.get('scenarios',[])
    if (not review.get('passed') or review.get('canonical_sha256')!=receipt['canonical_sha256']
        or len(reviews)!=96 or {r.get('scenario_id') for r in reviews}!=set(sample_ids(40))
        or any(r.get('verdict')!='pass' or not r.get('notes') for r in reviews)):
        raise ValueError('96-scenario semantic review is missing, incomplete, or stale')
    target=output/'exports'
    if target.exists():raise ValueError('exports already exist; no silent overwrite')
    counts=Counter();streams={}
    try:
        for split in ('train','validation','test'):
            for fmt,path in [('canonical',output/(split+'.jsonl')),('messages',target/'messages'/(split+'.jsonl')),('multiple_choice',target/'multiple_choice'/(split+'.jsonl'))]:
                path.parent.mkdir(parents=True,exist_ok=True);streams[split,fmt]=path.open('x')
        for row in iter_records(output):
            split=row['split'];streams[split,'canonical'].write(dumps(row)+'\n');counts[split]+=1
            streams[split,'messages'].write(dumps(dict(messages=messages(row)))+'\n')
            if row['representation']=='state_mc':streams[split,'multiple_choice'].write(dumps(choice_export(row))+'\n');counts[split+'_mc']+=1
    finally:
        for stream in streams.values():stream.close()
    # Export round-trip is checked against canonical rows, not just row counts.
    for split in ('train','validation','test'):
        with (output/(split+'.jsonl')).open() as cs,(target/'messages'/(split+'.jsonl')).open() as ms,(target/'multiple_choice'/(split+'.jsonl')).open() as qs:
            for c,m in zip(cs,ms,strict=True):
                row=json.loads(c)
                if json.loads(m)!=dict(messages=messages(row)):raise ValueError('messages export mismatch')
                if row['representation']=='state_mc' and json.loads(next(qs))!=choice_export(row):raise ValueError('choice export mismatch')
            if next(qs,None) is not None:raise ValueError('extra multiple-choice rows')
    report=dict(passed=True,counts=dict(counts),files={str(p.relative_to(output)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(target.rglob('*.jsonl'))})
    write(output/'export_validation.json',report)
    manifest.update(status='exported',exported_at=now(),exports=report)
    write(output/'manifest.json',manifest)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','generate','validate','export'])
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--groups',type=int,choices=[1,40],default=40,help='1 is the non-exportable vertical slice')
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--relabel-from',type=Path,help='generate only: regenerate questions from verified unchanged scene evidence')
    args=parser.parse_args()
    if args.relabel_from is not None and args.command!='generate':parser.error('--relabel-from is only supported by generate')
    try:
        if args.command=='prepare':result=prepare(args.output,args.groups)
        elif args.command=='generate':result=generate(args.output,args.workers,relabel_from=args.relabel_from)
        elif args.command=='export':result=export(args.output)
        else:
            from .validation import validate
            result=validate(args.output)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}',file=sys.stderr);return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
