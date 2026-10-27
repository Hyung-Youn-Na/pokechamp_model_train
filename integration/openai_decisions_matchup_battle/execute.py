"""EX-112: explicit profile, immutable schedule, no paid preflight."""

from integration.project_context.registry import record_relative
import argparse
import asyncio
import json
import os
import random
import time

import httpx

from integration.candidate_matchup import adapter
from integration.openai_decisions.client import read_api_key
from integration.openai_decisions_battle.core import ROOT, PORT, MODEL
from integration.openai_decisions_battle.retry import RetrySession
from integration.openai_decisions_battle import study
from integration.jev27b.study import write_json, file_hash

RUN=study.RUN.parent/'EX-112'
BASELINE=study.RUN.parent/'EX-110'
EXPORT=ROOT/'exports/battle_viewers/ex112'
PROFILE='openai-decisions-matchup-unlimited-v1'


def player_class():
    from integration.jev27b.battle import player_class as inherited
    return inherited(input_adapter=adapter)


def mock_session(*args, **kwargs):
    counter=0
    def handler(request):
        nonlocal counter
        counter+=1
        body=json.loads(request.content)
        choices=body['questions'][0]['choices']
        choice=random.Random(counter+101).choice(choices)['value']
        return httpx.Response(200,json=dict(model=MODEL,answers=[dict(name='action',type='choice',
            choice=choice,confidence=1.,probabilities=[dict(value=c['value'],probability=float(c['value']==choice)) for c in choices])],
            usage=dict(input_tokens=0,output_tokens=0)))
    return RetrySession(*args,client_factory=lambda:httpx.Client(transport=httpx.MockTransport(handler)),**kwargs)


def manifest(*,fake=False):
    value=study.prepare_manifest(fake=fake,sample=fake,experiment_id='EX-112')
    old=json.loads((BASELINE/'manifest.json').read_text())
    for name in ('schedule','teams','prompt','schema_version','model'):
        expected=old[name][:2] if fake and name=='schedule' else old[name]
        if value[name]!=expected:raise ValueError('EX110 configuration mismatch: '+name)
    value.update(execution_profile=PROFILE,candidate_matchup_profile=adapter.VERSION,
        input_data_identity=adapter.data_identity(),source=study.source_identity(candidate_matchup=True),
        primary_metric='blocked_choice_with_alternative',evaluation_version='candidate-matchup-comparison-v1',
        baseline=dict(path=str(BASELINE/'collection'),manifest_sha256=file_hash(BASELINE/'collection/manifest.json'),
                      result_sha256=file_hash(BASELINE/'collection/result.json')))
    if value['input_data_identity']['base']!=old['input_data_identity']:raise ValueError('base v6 data changed')
    value['limits'].update(calls=None,collection_seconds=None,total_seconds=None,battle_seconds=None,
                          turns=None,decisions=None,retries=None,recollection=0)
    value['transport_policy']=old['transport_policy']
    return value


def mock():
    from integration.openai_decisions_battle.battle import run
    from integration.openai_decisions_battle.viewer import export
    value=manifest(fake=True)
    original=os.getcwd()
    try:
        os.chdir(ROOT/'pokechamp')
        result=asyncio.run(run(RUN/'mock',manifest=value,key='mock-key',first_request_at=time.time(),
            fake=True,session_factory=mock_session,player_factory=player_class))
    finally:os.chdir(original)
    if not result['passed']:raise RuntimeError('mock collection failed; inspect preserved result')
    receipt=export(RUN/'mock',RUN/'mock-viewer')
    return dict(result=result,export=receipt)


def prepare():
    if (RUN/'manifest.json').exists() or (RUN/'execution.json').exists():raise FileExistsError('EX112 already prepared/executed')
    local=json.loads((RUN/'mock/result.json').read_text())
    browser=json.loads((RUN/'evidence/mock-browser.json').read_text())
    if not local['passed'] or not browser['passed']:raise ValueError('mock collection/export gate failed')
    value=manifest()
    # Mock and live must share the exact input/runtime/evaluation implementation.
    previous=json.loads((RUN/'mock/manifest.json').read_text())
    if previous['source']!=value['source'] or previous['input_data_identity']!=value['input_data_identity']:
        raise ValueError('source changed after mock; review and repeat affected validation before freezing')
    study.freeze(value,run=RUN,protocol_files=(
        record_relative('EP-183'),
        record_relative('EX-112'),
        record_relative('D-168'),'CONTRACTS.md','RESEARCH_DESIGN.md'))
    write_json(RUN/'freeze.json',dict(manifest_sha256=file_hash(RUN/'manifest.json'),
        mock_sha256=file_hash(RUN/'mock/result.json'),browser_sha256=file_hash(RUN/'evidence/mock-browser.json'),at=time.time()))
    return dict(passed=True,games=32)


def execute():
    from integration.openai_decisions_battle.battle import run
    from integration.pokechamp.parallel_server import check_ports
    value=json.loads((RUN/'manifest.json').read_text());study.verify_live_identity(value)
    key=read_api_key();os.environ.pop('OPENAI_API_KEY',None)
    started=time.time()
    with (RUN/'execution.json').open('x') as stream:json.dump(dict(at=started,pid=os.getpid()),stream)
    original=os.getcwd();error=None;result=None
    try:
        check_ports([PORT]);os.chdir(ROOT/'pokechamp')
        result=asyncio.run(run(RUN/'collection',manifest=value,key=key,first_request_at=started,
            session_factory=RetrySession,player_factory=player_class))
    except BaseException as exc:
        error=dict(type=type(exc).__name__,detail=str(exc).replace(key,'[REDACTED]'))
    finally:
        os.chdir(original)
        check_ports([PORT])
        write_json(RUN/'cleanup.json',dict(port_released=True,port=PORT,gpu_used=False,at=time.time()))
        write_json(RUN/'execution-result.json',dict(error=error,result=result))
    return dict(error=error,result=result)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['mock','prepare','execute','status','export'])
    args=parser.parse_args()
    if args.stage=='status':
        result={str(p.relative_to(RUN)):json.loads(p.read_text()) for p in
            [RUN/'freeze.json',RUN/'collection/ledger.json',RUN/'collection/progress.json',RUN/'execution-result.json'] if p.is_file()}
    elif args.stage=='export':
        from integration.openai_decisions_battle.viewer import export
        result=export(RUN/'collection',EXPORT)
    else:result=globals()[args.stage]()
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
