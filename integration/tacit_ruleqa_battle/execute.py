"""Prepare, reserve, and execute one EX-108 after validated EX-107 export."""

from integration.project_context.registry import freeze_document, resolve_record
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from .core import ROOT,RUN,PRESERVED,TRAIN,BASE,ADAPTER,BASE_REV,MODEL_PY,PORT,SYSTEM,build_input,close_builder
from .storage import write,digest,source_files,seal


def readiness():
    state=json.loads((TRAIN/'pipeline.json').read_text())
    if state['stage']=='stopped':raise RuntimeError('EX107 pipeline stopped')
    if state['stage']!='awaiting-blind-review-and-final-report':return False
    for rank in range(3):
        if not json.loads((TRAIN/f'reload-rank-{rank}.json').read_text())['passed']:raise ValueError('adapter reload failed')
    for name in ['test-base','test-selected']:
        metrics=json.loads((TRAIN/'predictions'/name/'metrics.json').read_text())
        if any(v['n']!=192 for v in metrics['forms'].values()):raise ValueError('incomplete EX107 test')
    selection=json.loads((TRAIN/'selection.json').read_text())
    if selection['epoch'] not in (1,2,3):raise ValueError('invalid selected epoch')
    return True


def sample_inputs():
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    dex=json.loads((DEFAULT_BUILD/'dex.json').read_text())
    source=PRESERVED/'runs/model-training/EX-106'
    old=json.loads((source/'manifest.json').read_text());schedule={r['slot_id']:r for r in old['schedule']}
    pools={}
    for line in (source/'collection/events.jsonl').open():
        event=json.loads(line)
        if event['type']=='input':pools.setdefault((event['payload']['kind'],event['actor']),[]).append(event)
    selected={}
    for rows in pools.values():
        for row in [rows[0],rows[-1],max(rows,key=lambda r:len(json.dumps(r['official'])))]:selected[row['decision']]=row
    samples={};length_inputs=[];counts={}
    try:
        for row in selected.values():
            slot=schedule[row['slot_id']];team=old['teams'][slot['teams'][int(row['actor'][-1])-1]]['showdown_team']
            payload=build_input(row['official'],row['prefix'],row['actor'],dex,team)
            kind=payload['kind'];counts[kind]=counts.get(kind,0)+1;length_inputs.append(payload['messages'])
            if kind not in samples and len(payload['candidates'])>1:
                samples[kind]=dict(payload=payload,official=row['official'],prefix=row['prefix'],actor=row['actor'],own_team=team)
    finally:close_builder()
    if set(samples)!={'lead','turn_action','forced_switch'}:raise ValueError('missing gate kind')
    return samples,counts,length_inputs


def prepare():
    if not readiness():raise RuntimeError('EX107 export/reload not ready')
    if (RUN/'execution.json').exists() or (RUN/'manifest.json').exists():raise FileExistsError('already prepared/executed')
    RUN.mkdir(parents=True,exist_ok=True)
    origin=PRESERVED/'runs/model-training/EX-089/collection/manifest.json';old=json.loads(origin.read_text())
    samples,counts,messages=sample_inputs();write(RUN/'gate-inputs.json',samples)
    corpus=RUN/'preparation-messages.json';write(corpus,messages)
    script='''import json,sys\nfrom transformers import AutoTokenizer\nt=AutoTokenizer.from_pretrained(sys.argv[1],local_files_only=True)\na=json.load(open(sys.argv[2]))\nn=[len(t.apply_chat_template(m,tokenize=True,add_generation_prompt=True,enable_thinking=False)['input_ids']) for m in a]\nprint(json.dumps(dict(count=len(n),minimum=min(n),maximum=max(n),over32768=sum(x>32768 for x in n),lengths=n)))'''
    lengths=json.loads(subprocess.check_output([str(MODEL_PY),'-c',script,str(ADAPTER/'tokenizer'),str(corpus)],text=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',TOKENIZERS_PARALLELISM='false')))
    write(RUN/'preparation-lengths.json',lengths)
    if lengths['over32768']:raise ValueError('historical full State exceeds input limit')
    files=source_files()+[ROOT/'scripts/tacit-ruleqa-battle']
    source={str(p.relative_to(ROOT)):digest(p) for p in files}
    assets={str(p):digest(p) for folder in (BASE,ADAPTER) for p in folder.rglob('*') if p.is_file() and '.cache' not in p.parts}
    manifest=dict(experiment_id='EX-108',schedule=old['schedule'],teams=old['teams'],schedule_source=str(origin),
        schedule_source_sha256=digest(origin),source=source,model_assets=assets,base_revision=BASE_REV,
        selected_epoch=json.loads((TRAIN/'selection.json').read_text())['epoch'],selection_sha256=digest(TRAIN/'selection.json'),
        observation_build=old['observation_build'],submodules=old['submodules'],system_prompt=SYSTEM,
        model=dict(dtype='bfloat16',adapter_dtype='float32',merged=False,thinking=False,max_new_tokens=192,seed=20261019),
        limits=dict(seconds=43200,calls=20000,input_tokens=32768,turns=300,decisions=600),
        historical_construction_counts=counts,created=time.time())
    for name in ('EP-176','EX-108','D-162'):
        source_document = resolve_record(name, root=ROOT)
        target = RUN / 'protocol' / source_document.name
        freeze_document(source_document, target)
    write(RUN/'manifest.json',manifest)
    for relative in source:
        target=RUN/'source'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/relative,target)
    write(RUN/'preparation.json',dict(passed=True,lengths=lengths,manifest_sha256=digest(RUN/'manifest.json')))
    return dict(passed=True,lengths=lengths)


def verify_source(manifest):
    for relative,sha in manifest['source'].items():
        if digest(ROOT/relative)!=sha:raise ValueError('source changed: '+relative)


def execute():
    from .serving import Server
    from .battle import run
    from .report import export
    if not readiness():raise RuntimeError('upstream not ready')
    manifest=json.loads((RUN/'manifest.json').read_text());verify_source(manifest)
    for path,sha in manifest['model_assets'].items():
        if digest(path)!=sha:raise ValueError('model identity changed: '+path)
    with (RUN/'execution.json').open('x') as stream:json.dump(dict(started=time.time(),pid=os.getpid()),stream)
    model=Server();error=None;result=None
    try:
        model.start();samples=json.loads((RUN/'gate-inputs.json').read_text());responses=[]
        for kind in ('lead','turn_action','forced_switch'):
            pair=[]
            for repeat in range(2):
                response=model.call(samples[kind]['payload']['messages'],f'gate:{kind}:{repeat}')
                pair.append(response);responses.append(response)
            write(RUN/'gates.json',dict(responses=responses))
            if pair[0]['output_ids']!=pair[1]['output_ids']:raise ValueError('greedy repeatability failed')
        write(RUN/'gates.json',dict(passed=True,responses=responses));verify_source(manifest)
        write(RUN/'freeze.json',dict(manifest_sha256=digest(RUN/'manifest.json'),gates_sha256=digest(RUN/'gates.json'),at=time.time()))
        os.chdir(ROOT/'pokechamp');result=asyncio.run(run(model,manifest))
    except BaseException as exc:error=dict(type=type(exc).__name__,detail=str(exc))
    finally:
        model.close();close_builder();os.chdir(ROOT)
        from integration.jev27b.resource import gpu_facts,gpu_compute_processes
        from integration.pokechamp.parallel_server import check_ports
        check_ports([PORT]);released=gpu_facts()
        for _ in range(30):
            if released[1]['memory_used_mib']==0:break
            time.sleep(1);released=gpu_facts()
        write(RUN/'cleanup.json',dict(gpus=released,compute_processes=gpu_compute_processes(),port_released=PORT,
            model_stopped=model.process is None or model.process.poll() is not None))
        write(RUN/'execution-result.json',dict(error=error,result=result,calls=model.calls))
    try:report=export()
    finally:close_builder()
    browser=subprocess.run(['/tmp/ep037/tools/bin/python',str(ROOT/'integration/tacit_ruleqa_battle/browser_check.py')],capture_output=True,text=True)
    write(RUN/'browser-process.json',dict(returncode=browser.returncode,stdout=browser.stdout,stderr=browser.stderr))
    seal(RUN)
    if browser.returncode:raise RuntimeError('offline viewer check failed: '+browser.stderr[-2000:])
    return report


def schedule():
    import fcntl,traceback
    RUN.mkdir(parents=True,exist_ok=True)
    with (RUN/'reservation.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (RUN/'reservation.json').open('x') as f:
            json.dump(dict(stage='waiting-for-EX107',pid=os.getpid(),created=time.time(),games=32,thinking=False,gpu=1),f)
        try:
            while not readiness():time.sleep(30)
            write(RUN/'reservation-state.json',dict(stage='preparing',at=time.time()))
            prepare()
            write(RUN/'reservation-state.json',dict(stage='running',at=time.time()))
            result=execute()
            write(RUN/'reservation-state.json',dict(stage='finished',at=time.time(),report=result))
        except BaseException:
            error=traceback.format_exc()
            seal(RUN)
            write(RUN/'reservation-state.json',dict(stage='stopped',at=time.time(),error=error))
            raise


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','schedule','execute','status','export']);args=parser.parse_args()
    if args.stage=='status':result={p.name:json.loads(p.read_text()) for p in [RUN/'reservation.json',RUN/'reservation-state.json',RUN/'preparation.json',RUN/'usage.json',RUN/'collection/progress.json',RUN/'execution-result.json'] if p.exists()}
    elif args.stage=='export':
        from .report import export
        try:result=export()
        finally:close_builder()
    else:result=globals()[args.stage]()
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
