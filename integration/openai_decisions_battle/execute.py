"""EX-109의 준비·모의경기·실 API 및 본수집 단계."""
import argparse
import asyncio
import json
import os
import time

from integration.openai_decisions.client import read_api_key
from integration.jev27b.study import write_json, file_hash, seal
from .core import ROOT, RUN, BASELINE, PORT, to_request, from_request, call_http


def gates():
    from integration.pokechamp import jev_battle as j, jev_v6
    from integration.pokechamp.observation.build import DEFAULT_BUILD
    from integration.jev27b.audit import cutoff_prefix
    from integration.pokechamp.observation.runtime import OfficialClient
    path=RUN/'preflight'
    first=json.loads((path/'result.json').read_text())
    if not first['passed']:raise RuntimeError('first API gate failed')
    if (path/'complete.json').exists():return json.loads((path/'complete.json').read_text())
    manifest=json.loads((BASELINE/'manifest.json').read_text())
    outcomes=json.loads((BASELINE/'result.json').read_text())['outcomes']
    by_user={o['username']:o for o in outcomes}
    protocols={};selected={}
    for line in (BASELINE/'events.jsonl').open():
        event=json.loads(line)
        if event['type']=='protocol':
            protocols.setdefault(event['username'],[]).append(dict(event_seq=event['sequence'],protocol=event['protocol']))
        if event['type']=='input':
            kind=event['payload']['state']['decision_kind']
            if kind not in selected and len(event['commands'])>1:
                user=event['decision'].split('-')[0]
                selected[kind]=(event,cutoff_prefix(protocols[user],event['boundary']),by_user[user])
        if set(selected)=={'lead','turn_action','forced_switch'}:break
    if len(selected)!=3:raise ValueError('three representative decision types required')
    key=read_api_key();os.environ.pop('OPENAI_API_KEY',None)
    adapter=jev_v6.Adapter(json.loads((DEFAULT_BUILD/'dex.json').read_text()))
    results=[]
    try:
        for ordinal,kind in enumerate(('lead','turn_action','forced_switch'),1):
            event,prefix,outcome=selected[kind]
            with_client=OfficialClient(event['actor'])
            try:current=with_client.snapshot(prefix,event['battle'],boundary=event['boundary'])
            finally:with_client.close()
            if current!=event['official']:raise ValueError('stored official cutoff changed')
            team=manifest['teams'][outcome['teams'][int(event['actor'][-1])-1]]['showdown_team']
            payload,commands,audit=adapter.generate(current,prefix,team,actor=event['actor'])
            if payload!=event['payload'] or commands!=event['commands']:raise ValueError('v6 saved input differs')
            request=to_request(payload)
            if from_request(request)!=payload:raise ValueError('lossy API adapter')
            if kind=='lead':
                results.append(dict(kind=kind,passed=True,reused_first_gate=True,**{'usage':first.get('usage')}))
                continue
            target=path/kind;target.mkdir(exist_ok=False)
            write_json(target/'request.json',request)
            def record(row):
                with (target/'events.jsonl').open('a') as stream:
                    stream.write(json.dumps(dict(at=time.time(),**row),ensure_ascii=False)+'\n');stream.flush()
            body=call_http(request,key,record,decision='ex109-gate-'+kind,request_number=ordinal)
            choice=j.validate_answer(body,payload['questions']['action']['criteria'])
            write_json(target/'normalized-response.json',body)
            results.append(dict(kind=kind,passed=True,choice=choice,usage=body.get('usage')))
    finally:adapter.close()
    receipt=dict(passed=True,requests=3,first_request_at=first['started'],results=results)
    write_json(path/'complete.json',receipt)
    return receipt


def mock():
    from .study import prepare_manifest
    from .battle import run
    manifest=prepare_manifest(fake=True,sample=True)
    original=os.getcwd();os.chdir(ROOT/'pokechamp')
    try:return asyncio.run(run(RUN/'mock',manifest=manifest,key='mock-key',first_request_at=time.time(),fake=True))
    finally:os.chdir(original)


def prepare():
    from .study import prepare_manifest, freeze
    if (RUN/'manifest.json').exists():raise FileExistsError('already frozen')
    receipt=json.loads((RUN/'preflight/complete.json').read_text())
    local=json.loads((RUN/'mock/result.json').read_text())
    if not receipt['passed'] or not local['passed']:raise RuntimeError('preflight or mock battle failed')
    manifest=prepare_manifest();freeze(manifest)
    write_json(RUN/'freeze.json',dict(manifest_sha256=file_hash(RUN/'manifest.json'),
        gates_sha256=file_hash(RUN/'preflight/complete.json'),mock_sha256=file_hash(RUN/'mock/result.json'),at=time.time()))
    return dict(passed=True,games=32)


def execute():
    from .battle import run
    from .study import verify_live_identity
    from integration.pokechamp.parallel_server import check_ports
    manifest=json.loads((RUN/'manifest.json').read_text());verify_live_identity(manifest)
    gates_receipt=json.loads((RUN/'preflight/complete.json').read_text())
    key=read_api_key();os.environ.pop('OPENAI_API_KEY',None)
    with (RUN/'execution.json').open('x') as stream:json.dump(dict(at=time.time(),pid=os.getpid()),stream)
    original=os.getcwd();error=None;result=None
    try:
        check_ports([PORT]);os.chdir(ROOT/'pokechamp')
        result=asyncio.run(run(RUN/'collection',manifest=manifest,key=key,
            first_request_at=gates_receipt['first_request_at'],prior_calls=3))
    except BaseException as exc:error=dict(type=type(exc).__name__,detail=str(exc).replace(key,'[REDACTED]'))
    finally:
        os.chdir(original)
        check_ports([PORT])
        write_json(RUN/'cleanup.json',dict(port_released=True,port=PORT,gpu_used=False,at=time.time()))
        write_json(RUN/'execution-result.json',dict(error=error,result=result))
    return dict(error=error,result=result)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['mock','gates','prepare','execute','status','export'])
    args=parser.parse_args()
    if args.stage=='status':
        result={str(p.relative_to(RUN)):json.loads(p.read_text()) for p in
            [RUN/'preflight/result.json',RUN/'preflight/complete.json',RUN/'freeze.json',
             RUN/'collection/progress.json',RUN/'execution-result.json'] if p.is_file()}
    elif args.stage=='export':
        from .viewer import export
        result=export()
    else:result=globals()[args.stage]()
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
