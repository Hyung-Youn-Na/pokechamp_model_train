"""EX115 explicit registration, mock gates, freeze and sequential 32 slots."""
import argparse
import asyncio
import json
import os
import random
import sys
import time

import httpx

from integration.openai_decisions.client import read_api_key
from integration.openai_decisions_battle.core import ROOT, PORT, MODEL
from integration.openai_decisions_battle import study
from integration.jev27b.study import write_json, file_hash
from integration.project_context.registry import record_relative
from . import adapter
from .transform import PROFILE as INPUT_PROFILE, VERSION, PROMPT
from .session import RecoverySession
from .offline import RUN, BASELINE

EXPORT = ROOT/'exports/battle_viewers/ex115'
PROFILE = 'openai-decisions-candidate-action-recovery-v1'
MOCK_NAME = 'mock-qualified'
EXPERIMENT = 'EX-115'


def player_class():
    from integration.jev27b.battle import player_class as inherited
    return inherited(input_adapter=adapter)


def mock_session(*args, **kwargs):
    counter = 0
    def handler(request):
        nonlocal counter
        counter += 1
        if counter == 1:
            return httpx.Response(503)
        if counter == 2:
            return httpx.Response(200, json=dict(model=MODEL, answers=[dict(name='action',type='refusal')],
                                                usage=dict(input_tokens=7,output_tokens=0)))
        choices = json.loads(request.content)['questions'][0]['choices']
        choice = random.Random(counter+101).choice(choices)['value']
        return httpx.Response(200,json=dict(model=MODEL,answers=[dict(name='action',type='choice',choice=choice,
            confidence=1.,probabilities=[dict(value=c['value'],probability=float(c['value']==choice)) for c in choices])],
            usage=dict(input_tokens=0,output_tokens=0)))
    return RecoverySession(*args,client_factory=lambda:httpx.Client(transport=httpx.MockTransport(handler)),**kwargs)


def manifest(*, fake=False):
    value = study.prepare_manifest(fake=fake,sample=fake,experiment_id=EXPERIMENT)
    old = json.loads((BASELINE/'manifest.json').read_text())
    for name in ('schedule','teams','model'):
        expected = old[name][:2] if fake and name=='schedule' else old[name]
        if value[name] != expected: raise ValueError('EX112 configuration mismatch: '+name)
    identity = adapter.data_identity()
    if identity['base'] != old['input_data_identity']:
        raise ValueError('EX112 calculation/rules data changed')
    value.update(execution_profile=PROFILE, input_profile=INPUT_PROFILE,
        candidate_matchup_profile='candidate-matchup-v1',schema_version=VERSION,prompt=PROMPT.read_text(),
        input_data_identity=identity,source=study.source_identity(candidate_matchup=True,candidate_action=True),
        primary_metric='valid_game_score_and_completion',evaluation_version='candidate-action-comparison-v1',
        viewer=dict(ui='battle-viewer-ui-v1',renderer='candidate-action-researcher-v2',
                    extensions=['재구성 전 입력','후보별 적용 결과','선택·전송']),
        baseline=dict(path=str(BASELINE/'collection'),manifest_sha256=file_hash(BASELINE/'collection/manifest.json'),
                      result_sha256=file_hash(BASELINE/'collection/result.json')))
    value['limits'].update(calls=None,collection_seconds=None,total_seconds=None,battle_seconds=None,
        turns=None,decisions=None,retries=None,recollection=0,response_attempts=3)
    value['transport_policy'] = old['transport_policy']
    value['response_policy'] = dict(version='unusable-response-same-input-v1',max_attempts=3,
        transport_retries_separate=True,first_legal_choice=True,fallback=False)
    if EXPERIMENT == 'EX-117':
        baseline = json.loads((BASELINE.parent/'EX-115/manifest.json').read_text())
        if value['schedule'] != (baseline['schedule'][:2] if fake else baseline['schedule']):
            raise ValueError('EX115 schedule changed')
        if identity['prompt_sha256'] != '6a4bd45bb2e4d89a58a8daff959b3e29fb2691fffd6b575b9d00397ae01f1e64':
            raise ValueError('EX117 requires the approved D181 prompt')
        value['viewer']['renderer'] = 'candidate-action-researcher-v2'
        value['primary_baseline'] = dict(experiment='EX-115', path=str(BASELINE.parent/'EX-115/collection'))
    return value


def mock():
    from integration.openai_decisions_battle.battle import run
    from .viewer import export
    value=manifest(fake=True)
    original=os.getcwd()
    try:
        os.chdir(ROOT/'pokechamp')
        result=asyncio.run(run(RUN/MOCK_NAME,manifest=value,key='mock-key',first_request_at=time.time(),
            fake=True,session_factory=mock_session,player_factory=player_class))
    finally: os.chdir(original)
    if not result['passed']: raise RuntimeError('mock collection failed; inspect preserved result')
    receipt=export(RUN/MOCK_NAME,RUN/(MOCK_NAME+'-viewer'))
    return dict(result=result,export=receipt)


def prepare():
    if (RUN/'manifest.json').exists() or (RUN/'execution.json').exists():
        raise FileExistsError(EXPERIMENT+' already prepared/executed')
    for path in (f'{MOCK_NAME}/result.json','evidence/mock-browser.json','offline/verification.json','evidence/tests.json'):
        if not json.loads((RUN/path).read_text())['passed']:
            raise ValueError('failed gate: '+path)
    value=manifest()
    previous=json.loads((RUN/f'{MOCK_NAME}/manifest.json').read_text())
    if previous['source']!=value['source'] or previous['input_data_identity']!=value['input_data_identity']:
        raise ValueError('source changed after mock; repeat affected validation before freezing')
    ids = ('EP-206','EX-117','D-182','D-181') if EXPERIMENT == 'EX-117' else ('EP-202','EX-115','D-179')
    study.freeze(value,run=RUN,protocol_files=tuple(record_relative(i) for i in ids)+('CONTRACTS.md','RESEARCH_DESIGN.md'))
    write_json(RUN/'freeze.json',dict(manifest_sha256=file_hash(RUN/'manifest.json'),
        gates={p:file_hash(RUN/p) for p in (f'{MOCK_NAME}/result.json','evidence/mock-browser.json','offline/verification.json','evidence/tests.json')},
        at=time.time()))
    return dict(passed=True,games=32)


def execute():
    from integration.openai_decisions_battle.battle import run
    from integration.pokechamp.parallel_server import check_ports
    value=json.loads((RUN/'manifest.json').read_text());study.verify_live_identity(value)
    key=read_api_key();os.environ.pop('OPENAI_API_KEY',None)
    started=time.time()
    with (RUN/'execution.json').open('x') as stream: json.dump(dict(at=started,pid=os.getpid()),stream)
    original=os.getcwd();error=None;result=None
    try:
        check_ports([PORT]);os.chdir(ROOT/'pokechamp')
        result=asyncio.run(run(RUN/'collection',manifest=value,key=key,first_request_at=started,
            session_factory=RecoverySession,player_factory=player_class))
    except BaseException as exc:
        error=dict(type=type(exc).__name__,detail=str(exc).replace(key,'[REDACTED]'))
    finally:
        os.chdir(original)
        check_ports([PORT])
        write_json(RUN/'cleanup.json',dict(port_released=True,port=PORT,gpu_used=False,at=time.time()))
        write_json(RUN/'execution-result.json',dict(error=error,result=result))
    return dict(error=error,result=result)


def main():
    global MOCK_NAME, EXPERIMENT, RUN, EXPORT
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['mock','prepare','execute','status','export','collect','offline'])
    parser.add_argument('--mock-name',default=MOCK_NAME)
    parser.add_argument('--experiment',choices=['EX-115','EX-117'],default='EX-115')
    args=parser.parse_args()
    EXPERIMENT=args.experiment
    RUN=BASELINE.parent/EXPERIMENT
    EXPORT=ROOT/'exports/battle_viewers'/EXPERIMENT.lower().replace('-','')
    import re
    if not re.fullmatch(r'mock-[a-z0-9-]+',args.mock_name):parser.error('mock name must start with mock- and contain lowercase letters/digits/hyphens')
    MOCK_NAME=args.mock_name
    if args.stage in ('collect','offline'):
        if EXPERIMENT != 'EX-117': parser.error('collect/offline requires EX-117')
        from . import survival
        result=survival.collect(sys.modules[__name__]) if args.stage=='collect' else survival.offline()
    elif args.stage=='status':
        result={str(p.relative_to(RUN)):json.loads(p.read_text()) for p in
            [RUN/'freeze.json',RUN/'collection/progress.json',RUN/'execution-result.json'] if p.is_file()}
    elif args.stage=='export':
        from .viewer import export
        result=export(RUN/'collection',EXPORT)
    else:result=globals()[args.stage]()
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
