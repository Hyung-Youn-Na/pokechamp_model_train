"""Bounded EX114 prepare, qualification, collection and export."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import time

from integration.jev27b.study import write_json, file_hash
from .core import ROOT, RUN, BASELINE, PORT, MODEL_DIR, to_request, from_request


def capture():
    from .resource import capture as inspect_server
    RUN.mkdir(parents=True,exist_ok=True)
    path = RUN/'external-identity.json'
    if path.exists():
        raise FileExistsError('external identity already captured')
    receipt = inspect_server()
    write_json(path,receipt)
    return dict(passed=True,revision=receipt['revision'],gpu_uuid=receipt['gpu_uuid'])


def mock():
    from .study import prepare_manifest
    from .battle import run
    manifest = prepare_manifest(fake=True,sample=True)
    original=os.getcwd();os.chdir(ROOT/'pokechamp')
    try:
        return asyncio.run(run(RUN/'mock',manifest=manifest,key=None,
                               first_request_at=time.time(),fake=True))
    finally:
        os.chdir(original)


def representatives():
    from integration.jev27b.audit import cutoff_prefix
    outcomes = json.loads((BASELINE/'result.json').read_text())['outcomes']
    by_user = {o['username']:o for o in outcomes}
    protocols={}; selected={}
    with (BASELINE/'events.jsonl').open() as stream:
        for line in stream:
            event=json.loads(line)
            if event['type']=='protocol':
                protocols.setdefault(event['username'],[]).append(dict(
                    event_seq=event['sequence'],protocol=event['protocol']))
            if event['type']=='input':
                kind=event['payload']['state']['decision_kind']
                if kind not in selected and len(event['commands'])>1:
                    user=event['decision'].split('-')[0]
                    selected[kind]=(event,cutoff_prefix(protocols[user],event['boundary']),by_user[user])
            if set(selected)=={'lead','turn_action','forced_switch'}:
                break
    if len(selected)!=3:
        raise ValueError('three representative types required')
    return selected


def gates():
    from integration.pokechamp import jev_v6
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    from integration.pokechamp.observation.runtime import OfficialClient
    from .session import Session
    from .resource import borrowed_gpu
    path=RUN/'preflight'
    path.mkdir(exist_ok=False)
    old=json.loads((BASELINE/'manifest.json').read_text())
    selected=representatives()
    adapter=jev_v6.Adapter(json.loads((DEFAULT_BUILD/'dex.json').read_text()))
    inputs=[]
    try:
        for kind in ('lead','turn_action','forced_switch'):
            event,prefix,outcome=selected[kind]
            client=OfficialClient(event['actor'])
            try:
                current=client.snapshot(prefix,event['battle'],boundary=event['boundary'])
            finally:
                client.close()
            if current!=event['official']:
                raise ValueError('stored official cutoff changed')
            team=old['teams'][outcome['teams'][int(event['actor'][-1])-1]]['showdown_team']
            payload,commands,_=adapter.generate(current,prefix,team,actor=event['actor'])
            if payload!=event['payload'] or commands!=event['commands']:
                raise ValueError('current v6 differs from saved representative')
            request=to_request(payload)
            if from_request(request)!=payload:
                raise ValueError('lossy native adapter')
            inputs.append(dict(kind=kind,payload=payload,request=request,source_decision=event['decision']))
    finally:
        adapter.close()
    write_json(path/'inputs.json',inputs)
    # Independently verify the vendored, fixed chat template against the model's
    # actual Transformers native template using the existing vLLM environment.
    code = '''import json,sys
from transformers import AutoTokenizer
sys.path.insert(0,"/workspace")
from integration.jevk5_ruleqa_battle.upstream_prompt import messages
from integration.jevk5_ruleqa_battle.core import MODEL_DIR,dumps
rows=json.load(open(sys.argv[1]));tok=AutoTokenizer.from_pretrained(MODEL_DIR,local_files_only=True)
for row in rows:
 p=row['payload'];q=p['questions']['action'];options=[k+': '+dumps(v) for k,v in q['criteria'].items()]
 text=tok.apply_chat_template(messages(p['state'],q['instructions'],options),tokenize=False,add_generation_prompt=True,enable_thinking=False)
 assert tok.encode(text,add_special_tokens=False)==row['request']['prompt'],row['kind']
print(json.dumps({'passed':True,'representatives':len(rows)}))
'''
    native=json.loads(subprocess.check_output([str(ROOT/'.pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python'),
        '-B','-c',code,str(path/'inputs.json')],text=True))
    write_json(path/'native-template.json',native)
    async def run():
        session=Session(path,key=None,first_request_at=time.time())
        results=[]
        try:
            for row in inputs:
                for repeat in (1,2):
                    started=time.monotonic()
                    body=await session.evaluate(row['payload'],decision='gate-'+row['kind']+'-'+str(repeat))
                    results.append(dict(kind=row['kind'],repeat=repeat,body=body,
                        seconds=time.monotonic()-started,input_tokens=len(row['request']['prompt'])))
        finally:
            await session.close()
            write_json(path/'attempt-results.json',dict(results=results,first_request_at=session.started,
                                                       requests=session.calls))
        deltas=[]
        for a,b in zip(results[::2],results[1::2]):
            x=a['body']['answers']['action'];y=b['body']['answers']['action']
            deltas.append(dict(kind=a['kind'],same_choice=x['choice']==y['choice'],
                max_probability_difference=max(abs(x['probabilities'][k]-y['probabilities'][k]) for k in x['probabilities'])))
        receipt=dict(passed=len(results)==6,requests=session.calls,logical_requests=6,
            first_request_at=session.started,results=results,repeat_diagnostics=deltas,
            native_template=native,source=__import__('integration.jevk5_ruleqa_battle.study',fromlist=['source_identity']).source_identity())
        write_json(path/'complete.json',receipt)
        return dict(passed=receipt['passed'],requests=session.calls,repeat_diagnostics=deltas,
                    lengths=[r['input_tokens'] for r in results])
    with borrowed_gpu(path):
        return asyncio.run(run())


def prepare():
    from .study import prepare_manifest,freeze,source_identity
    if (RUN/'manifest.json').exists():
        raise FileExistsError('already frozen')
    gate=json.loads((RUN/'preflight/complete.json').read_text())
    mock_result=json.loads((RUN/'mock/result.json').read_text())
    if not gate['passed'] or not mock_result['passed'] or gate['source']!=source_identity():
        raise ValueError('qualification failed or source drift')
    manifest=prepare_manifest()
    manifest['external_identity_sha256']=file_hash(RUN/'external-identity.json')
    freeze(manifest)
    write_json(RUN/'freeze.json',dict(at=time.time(),manifest_sha256=file_hash(RUN/'manifest.json'),
        gates_sha256=file_hash(RUN/'preflight/complete.json'),mock_sha256=file_hash(RUN/'mock/result.json')))
    return dict(passed=True,games=32,port=PORT)


def execute():
    from .battle import run
    from .study import verify_live_identity
    from .resource import borrowed_gpu,verify
    from integration.pokechamp.parallel_server import check_ports
    manifest=json.loads((RUN/'manifest.json').read_text())
    verify_live_identity(manifest)
    if file_hash(RUN/'external-identity.json')!=manifest['external_identity_sha256']:
        raise ValueError('external identity receipt changed')
    identity=json.loads((RUN/'external-identity.json').read_text())
    verify(identity,health=True)
    gate=json.loads((RUN/'preflight/complete.json').read_text())
    with (RUN/'execution.json').open('x') as stream:
        json.dump(dict(at=time.time(),pid=os.getpid()),stream)
    original=os.getcwd();error=None;result=None
    try:
        check_ports([PORT])
        with borrowed_gpu(RUN):
            os.chdir(ROOT/'pokechamp')
            result=asyncio.run(run(RUN/'collection',manifest=manifest,key=None,
                first_request_at=gate['first_request_at'],prior_calls=gate['requests']))
    except BaseException as exc:
        error=dict(type=type(exc).__name__,detail=str(exc))
    finally:
        os.chdir(original)
        check_ports([PORT])
        write_json(RUN/'cleanup.json',dict(port_released=True,port=PORT,at=time.time(),
            external_server_preserved=True,controller_gpu_lock_released=True))
        write_json(RUN/'execution-result.json',dict(error=error,result=result))
    return dict(error=error,passed=bool(result and result['passed']),
                completed=result['completed'] if result else 0)



def run():
    from .resource import OwnedServer
    from .viewer import export
    from .report import finalize
    from .core import EXPORT
    for name in ['cpu-check.json','mock-browser.json']:
        if not json.loads((RUN/name).read_text())['passed']:raise ValueError('preflight CPU/mock UI verification required')
    if not json.loads((RUN/'mock/result.json').read_text())['passed']:raise ValueError('mock audit failed')
    if (RUN/'pipeline.json').exists():raise FileExistsError('EX114 already attempted')
    write_json(RUN/'pipeline.json',dict(started=time.time(),pid=os.getpid(),recollection=0))
    try:
        with OwnedServer():
            capture()
            qualified=gates()
            if not qualified['passed']:raise RuntimeError('six gate qualification failed')
            prepare()
            result=execute()
        if not (RUN/'collection/result.json').exists():raise RuntimeError('collection did not produce a result')
        export()
        subprocess.run(['/tmp/ep037/tools/bin/python','-B','-m','integration.jevk5_ruleqa_battle.browser_check',
                        str(EXPORT),str(RUN/'browser.json')],cwd=ROOT,check=True)
        final=finalize()
        return dict(passed=final['experiment_completed'],completed=final['completed'],overall=final['overall'],viewer=str(EXPORT/'index.html'))
    except BaseException as exc:
        write_json(RUN/'pipeline-failure.json',dict(at=time.time(),error=repr(exc)))
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['run','mock','status','export'])
    stage=parser.parse_args().stage
    if stage=='status':
        result={str(p.relative_to(RUN)):json.loads(p.read_text()) for p in
            (RUN/'preflight/complete.json',RUN/'collection/progress.json',RUN/'execution-result.json') if p.exists()}
    elif stage=='export':
        from .viewer import export
        result=export()
    else:
        result=globals()[stage]()
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
