"""EX-110 새32경기. EX-109 원자료와 실패 판정은 변경하지 않는다."""
import argparse
import asyncio
import json
import os
import time

from integration.openai_decisions.client import read_api_key
from integration.jev27b.study import write_json,file_hash
from .core import ROOT,RUN as PREVIOUS,PORT

RUN=PREVIOUS.parent/'EX-110'
EXPORT=ROOT/'exports/battle_viewers/ex110'


def prepare():
    from .study import prepare_manifest,freeze
    if (RUN/'manifest.json').exists() or (RUN/'execution.json').exists():
        raise FileExistsError('EX110 already prepared/executed')
    previous=json.loads((PREVIOUS/'collection/result.json').read_text())
    gates=json.loads((PREVIOUS/'preflight/complete.json').read_text())
    if not gates['passed'] or not previous['final_audit_passed']:
        raise ValueError('previous input/API validation or preservation incomplete')
    RUN.mkdir(parents=True,exist_ok=True)
    manifest=prepare_manifest(experiment_id='EX-110')
    manifest['execution_profile']='openai-decisions-v6-unlimited-v1'
    manifest['limits'].update(calls=None,collection_seconds=None,total_seconds=None,battle_seconds=None,
                             turns=None,decisions=None,retries=None)
    manifest['transport_policy']=dict(name='openai-transient-unlimited-v1',timeout=60,
        retry_statuses=[408,429,'5xx'],delays=[2,5,10,20,30,60],repeat_delay=60,
        retry_after=True,permanent_error_stop=True,provider_idempotency_guaranteed=False)
    manifest['previous_experiment']=dict(experiment='EX-109',path=str(PREVIOUS),
        result_sha256=file_hash(PREVIOUS/'collection/result.json'),
        seal_sha256=file_hash(PREVIOUS/'checksums.sha256'),requests=previous['total_api_requests'],
        included_in_new_game_results=False,input_validation_reused=True,
        gate_sha256=file_hash(PREVIOUS/'preflight/complete.json'),
        input_data_identity=json.loads((PREVIOUS/'manifest.json').read_text())['input_data_identity'])
    if manifest['input_data_identity']!=manifest['previous_experiment']['input_data_identity']:
        raise ValueError('v6 input changed')
    freeze(manifest,run=RUN,protocol_files=(
        'exec-plans/active/EP-180-openai-decisions-retry32.md',
        'experiments/EX-110-openai-decisions-retry32.md',
        'decisions/D-165-openai-decisions-retry32.md','CONTRACTS.md','RESEARCH_DESIGN.md'))
    write_json(RUN/'freeze.json',dict(manifest_sha256=file_hash(RUN/'manifest.json'),at=time.time()))
    return dict(passed=True,games=32,previous_games_included=0)


def execute():
    from .battle import run
    from .study import verify_live_identity
    from .retry import RetrySession,player_class
    from integration.pokechamp.parallel_server import check_ports
    manifest=json.loads((RUN/'manifest.json').read_text());verify_live_identity(manifest)
    key=read_api_key();os.environ.pop('OPENAI_API_KEY',None)
    started=time.time()
    with (RUN/'execution.json').open('x') as stream:json.dump(dict(at=started,pid=os.getpid()),stream)
    original=os.getcwd();error=None;result=None
    try:
        check_ports([PORT]);os.chdir(ROOT/'pokechamp')
        result=asyncio.run(run(RUN/'collection',manifest=manifest,key=key,first_request_at=started,
            prior_calls=manifest['previous_experiment']['requests'],session_factory=RetrySession,
            player_factory=player_class))
    except BaseException as exc:
        error=dict(type=type(exc).__name__,detail=str(exc).replace(key,'[REDACTED]'))
    finally:
        os.chdir(original)
        check_ports([PORT])
        write_json(RUN/'cleanup.json',dict(port_released=True,port=PORT,gpu_used=False,at=time.time()))
        write_json(RUN/'execution-result.json',dict(error=error,result=result))
    return dict(error=error,result=result)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['prepare','execute','status','export'])
    args=parser.parse_args()
    if args.stage=='status':
        result={str(p.relative_to(RUN)):json.loads(p.read_text()) for p in
            [RUN/'freeze.json',RUN/'collection/ledger.json',RUN/'collection/progress.json',
             RUN/'execution-result.json'] if p.is_file()}
    elif args.stage=='export':
        from .viewer import export
        result=export(RUN/'collection',EXPORT)
    else:result=globals()[args.stage]()
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
