"""Explicit download/prepare/execute/status/export stages for EX-106."""

from integration.project_context.registry import freeze_document, resolve_record
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from .core import ROOT, RUN, PRESERVED, BASE, ADAPTER, BASE_REV, MODEL_PY, build_input, system_prompt
from .storage import write, digest, source_files, seal


def download():
    RUN.mkdir(parents=True,exist_ok=True)
    hf='/root/.local/bin/hf'
    subprocess.run([hf,'download','Qwen/Qwen3-0.6B','--revision',BASE_REV,'--local-dir',str(BASE)],check=True)
    result=subprocess.run([hf,'cache','verify','Qwen/Qwen3-0.6B','--revision',BASE_REV,'--local-dir',str(BASE)],capture_output=True,text=True)
    write(RUN/'download.json',dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,revision=BASE_REV))
    result.check_returncode()


def sample_inputs():
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    dex=json.loads((DEFAULT_BUILD/'dex.json').read_text())
    source=PRESERVED/'runs/model-training/EX-089/collection/events.jsonl'
    frames={};samples={};counts={};length_inputs=[]
    for line in source.open():
        event=json.loads(line)
        if event['type']=='protocol':
            frames.setdefault(event['username'],[]).append(dict(event_seq=event['sequence'],protocol=event['protocol']))
        elif event['type']=='input':
            username=event['decision'].rsplit('-',2)[0]
            boundary=event['boundary'];prefix=[]
            for frame in frames[username]:
                if frame['event_seq']>boundary['protocol_event_seq']:
                    break
                current=dict(frame)
                if frame['event_seq']==boundary['protocol_event_seq']:
                    current['protocol']='\n'.join(current['protocol'].splitlines()[:boundary['line_index']+1])
                prefix.append(current)
            payload=build_input(event['official'],prefix,event['actor'],dex)
            kind=payload['kind'];counts[kind]=counts.get(kind,0)+1
            length_inputs.append(payload['messages'])
            if kind not in samples and len(payload['candidates'])>1:
                samples[kind]=dict(payload=payload,official=event['official'],prefix=prefix,actor=event['actor'])
    return samples,counts,length_inputs


def prepare():
    if (RUN/'execution.json').exists():
        raise FileExistsError('execution already attempted')
    RUN.mkdir(parents=True,exist_ok=True)
    origin=PRESERVED/'runs/model-training/EX-089/collection/manifest.json'
    old=json.loads(origin.read_text())
    archive=json.loads((ADAPTER/'manifest.json').read_text())
    if archive['revision'] != 'f2726381423690cbe48f581c8027ce8b01012dae':
        raise ValueError('adapter archive revision mismatch')
    for entry in archive['files']:
        if digest(ADAPTER/entry['path']) != entry['sha256']:
            raise ValueError('adapter archive file mismatch: '+entry['path'])
    samples,counts,messages=sample_inputs()
    write(RUN/'gate-inputs.json',samples)
    corpus=RUN/'preparation-messages.json';write(corpus,messages)
    script='''import json,sys\nfrom transformers import AutoTokenizer\nt=AutoTokenizer.from_pretrained(sys.argv[1],local_files_only=True)\na=json.load(open(sys.argv[2]))\nn=[len(t(t.apply_chat_template(m,tokenize=False,add_generation_prompt=True,enable_thinking=False),add_special_tokens=False)['input_ids']) for m in a]\nprint(json.dumps(dict(count=len(n),minimum=min(n),maximum=max(n),over512=sum(x>512 for x in n),over1024=sum(x>1024 for x in n),lengths=n)))'''
    lengths=json.loads(subprocess.check_output([str(MODEL_PY),'-c',script,str(ADAPTER),str(corpus)],text=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',TOKENIZERS_PARALLELISM='false')))
    write(RUN/'preparation-lengths.json',lengths)
    # Historical states can differ from no-Tera live states; this is a construction check only.
    if lengths['over1024']:
        raise ValueError('historical input construction exceeds 1024; fix before freeze')
    corpus.unlink()
    files=source_files()+[ROOT/'scripts/strategist-eval']
    source={str(p.relative_to(ROOT)):digest(p) for p in files}
    assets={str(p):digest(p) for folder in (BASE,ADAPTER) for p in folder.iterdir() if p.is_file() and p.name!='manifest.json'}
    manifest=dict(experiment_id='EX-106',schedule=old['schedule'],teams=old['teams'],
        schedule_source=str(origin),schedule_source_sha256=digest(origin),source=source,
        model_assets=assets,base_revision=BASE_REV,system_prompt=system_prompt(),
        observation_build=old['observation_build'],submodules=old['submodules'],
        model=dict(dtype='float32',merged=False,thinking=False,max_new_tokens=64,seed=42),
        limits=dict(seconds=14400,calls=20000,input_tokens=1024,turns=300,decisions=600),
        historical_construction_counts=counts,created=time.time())
    for name in ('EP-172','EX-106','D-160'):
        source = resolve_record(name, root=ROOT)
        target = RUN / 'protocol' / source.name
        freeze_document(source, target)
    write(RUN/'manifest.json',manifest)
    for relative in source:
        target=RUN/'source'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/relative,target)
    write(RUN/'preparation.json',dict(passed=True,lengths={k:v for k,v in lengths.items() if k!='lengths'},manifest_sha256=digest(RUN/'manifest.json')))
    return dict(passed=True,lengths={k:v for k,v in lengths.items() if k!='lengths'})


def verify_source(manifest):
    for relative,sha in manifest['source'].items():
        if digest(ROOT/relative)!=sha:
            raise ValueError('source changed after preparation: '+relative)


def execute():
    from .serving import Server
    from .battle import run
    from .report import export
    manifest=json.loads((RUN/'manifest.json').read_text())
    verify_source(manifest)
    for path,sha in manifest['model_assets'].items():
        if digest(path)!=sha:
            raise ValueError('model asset changed: '+path)
    # Exclusive execution receipt prevents restarts/replays, including failed preflight.
    with (RUN/'execution.json').open('x') as stream:
        json.dump(dict(started=time.time(),pid=os.getpid()),stream)
    model=Server();error=None;result=None
    try:
        model.start()
        samples=json.loads((RUN/'gate-inputs.json').read_text())
        responses=[]
        for kind in ('lead','turn_action','forced_switch'):
            pair=[]
            for repeat in range(2):
                response=model.call(samples[kind]['payload']['messages'],f'gate:{kind}:{repeat}')
                pair.append(response);responses.append(response)
            write(RUN/'gates.json',dict(responses=responses))
            if pair[0]['output_ids']!=pair[1]['output_ids']:
                raise ValueError('greedy repeatability gate failed')
        write(RUN/'gates.json',dict(passed=True,responses=responses))
        verify_source(manifest)
        write(RUN/'freeze.json',dict(manifest_sha256=digest(RUN/'manifest.json'),gates_sha256=digest(RUN/'gates.json'),at=time.time()))
        os.chdir(ROOT/'pokechamp')
        result=asyncio.run(run(model,manifest))
    except BaseException as exc:
        error=dict(type=type(exc).__name__,detail=str(exc))
    finally:
        model.close()
        os.chdir(ROOT)
        from integration.jev27b.resource import gpu_facts,gpu_compute_processes
        from integration.pokechamp.parallel_server import check_ports
        from .core import PORT
        check_ports([PORT])
        released=gpu_facts()
        for _ in range(30):
            if released[0]['memory_used_mib']==0:
                break
            time.sleep(1);released=gpu_facts()
        write(RUN/'cleanup.json',dict(gpus=released,compute_processes=gpu_compute_processes(),port_released=PORT,
            model_stopped=model.process is None or model.process.poll() is not None))
        write(RUN/'execution-result.json',dict(error=error,result=result,calls=model.calls))
    report=export()
    browser=subprocess.run(['/tmp/ep037/tools/bin/python',str(ROOT/'integration/strategist_eval/browser_check.py')],capture_output=True,text=True)
    write(RUN/'browser-process.json',dict(returncode=browser.returncode,stdout=browser.stdout,stderr=browser.stderr))
    seal(RUN)
    if browser.returncode:
        raise RuntimeError('offline viewer check failed: '+browser.stderr[-2000:])
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['download','prepare','execute','status','export'])
    args=parser.parse_args()
    if args.stage=='status':
        result={p.name:json.loads(p.read_text()) for p in [RUN/'preparation.json',RUN/'usage.json',RUN/'collection/progress.json',RUN/'execution-result.json'] if p.exists()}
    elif args.stage=='export':
        from .report import export
        result=export()
    else:
        result=globals()[args.stage]()
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
