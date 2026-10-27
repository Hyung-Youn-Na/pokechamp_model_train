"""새 실험의 출처 동결·상한·분모 집계."""

from integration.project_context.registry import freeze_document

from integration.project_context.registry import record_relative
import copy
import json
import shutil
import subprocess
import time
from pathlib import Path

from integration.pokechamp import jev_battle as j, jev_v6
from integration.jev27b.study import file_hash, write_json, seal, summarize as inherited_summary
from .core import ROOT, RUN, BASELINE, MODEL, ENDPOINT, CALL_LIMIT, COLLECTION_SECONDS, ADAPTER, TEMPERATURE, MAX_CONTEXT


def source_identity():
    sources=j.source_identity()
    for folder in ('jevk5_ruleqa_battle','jev27b','jev_eval'):
        for path in (ROOT/'integration'/folder).rglob('*'):
            if path.is_file() and path.suffix in ('.py','.json','.txt','.html','.js','.cjs'):
                sources[str(path.relative_to(ROOT))]=file_hash(path)
    for name in ('scripts/jevk5-ruleqa-battle','integration/jevk5_ruleqa_battle/NOTICE','integration/jevk5_ruleqa_battle/LICENSE','integration/jevk5_ruleqa_battle/README.md'):
        if (ROOT/name).exists():sources[name]=file_hash(ROOT/name)
    for name in ('integration/jev_planner/replay.js','integration/pokechamp/viewer_assets/action-labels.js','integration/pokechamp/viewer_assets/jev-researcher.html'):
        sources[name]=file_hash(ROOT/name)
    return sources


def prepare_manifest(*, fake=False, sample=False, experiment_id='EX-114'):
    from integration.pokechamp.jev_study import validate_schedule
    from integration.pokechamp.observation.build import verify
    from integration.pokechamp import cli
    verify();cli._assert_submodule_pins(require_clean=True)
    old=json.loads((BASELINE/'manifest.json').read_text())
    validate_schedule(old['schedule'])
    seals={name:sha for sha,name in (line.split('  ',1) for line in (BASELINE/'checksums.sha256').read_text().splitlines())}
    if file_hash(BASELINE/'manifest.json')!=seals['manifest.json']:
        raise ValueError('baseline manifest seal mismatch')
    schedule=old['schedule'][:2] if sample else old['schedule']
    return dict(experiment_id=experiment_id,fake=fake,execution_profile='jevk5-ruleqa-v6-v1',
        schema_version=jev_v6.VERSION,validation_version=j.VALIDATION_VERSION,
        input_data_identity=jev_v6.data_identity(),prompt=jev_v6.PROMPT.read_text(),
        schedule=copy.deepcopy(schedule),teams=copy.deepcopy(old['teams']),
        schedule_origin=str(BASELINE/'manifest.json'),schedule_origin_sha256=file_hash(BASELINE/'manifest.json'),
        observation_build=old['observation_build'],submodules=old['submodules'],
        model=dict(model=MODEL,endpoint=ENDPOINT,revision='d6521a18a86999190e9d775c915af3d6d6772fc4',temperature=TEMPERATURE,adapter=str(ADAPTER),adapter_sha256=file_hash(ADAPTER/'adapter_model.safetensors'),max_context=MAX_CONTEXT,physical_gpu=2),source=source_identity(),timer_enabled=False,
        limits=dict(games=len(schedule),calls=CALL_LIMIT,collection_seconds=COLLECTION_SECONDS,
                    timeout=120,retries=3,concurrency=1,recollection=0),
        created_at=time.time(),efficacy_evidence=False,
        viewer=dict(ui_version='battle-viewer-ui-v1',renderer='jevk5-ruleqa-researcher-v1',extensions=['실제 프롬프트','선택지 확률','선택·전송']))


def freeze(manifest, *, run=RUN, protocol_files=None):
    write_json(run/'manifest.json',manifest)
    for relative in manifest['source']:
        target=run/'source'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/relative,target)
    for name in (protocol_files or (record_relative('EP-191'),
                 record_relative('EX-114'),
                 record_relative('D-173'),'CONTRACTS.md','RESEARCH_DESIGN.md')):
        target=run/'protocol'/name;target.parent.mkdir(parents=True,exist_ok=True)
        freeze_document(ROOT/'project_context'/name, target)
    write_json(run/'environment.json',dict(
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        working_changes=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
        interpreter=str(ROOT/'pokechamp/.venv/bin/python')))


def verify_live_identity(manifest):
    if manifest['source']!=source_identity():raise ValueError('frozen source changed')
    if manifest['input_data_identity']!=jev_v6.data_identity():raise ValueError('v6 data changed')


def summarize(session,outcomes,schedule,error=None):
    result=inherited_summary(session,outcomes,schedule,error,
        expected_games=len(schedule),expected_pairs=16 if len(schedule)==32 else None)
    result.update(external_requests=0, local_http_requests=0 if session.fake else session.calls,
        fake=session.fake, collection_deadline=session.started+COLLECTION_SECONDS,
        preflight_requests=session.prior_calls,total_api_requests=session.prior_calls+session.calls,
        usage_unknown_attempts=sum(e['type']=='attempt_failure' for e in session.records))
    if result['usage_unknown_attempts']: result['tokens']=None
    return result


def final_check(directory,result):
    events=[json.loads(line) for line in (directory/'events.jsonl').open()]
    errors=[]
    if [e['event_seq'] for e in events]!=list(range(1,len(events)+1)):errors.append('event sequence gap')
    physical=[e['request_number'] for e in events if e['type']=='transport']
    if physical!=list(range(1,len(physical)+1)):errors.append('physical request sequence gap')
    for outcome in result['outcomes']:
        receipt=json.loads((directory/f"battle-{outcome['slot']}"/'audit.json').read_text())
        if not receipt['passed']:errors.append('per-game audit failed')
        if not outcome.get('server_cleaned') or not outcome.get('opponent_cleaned'):errors.append('owned resource remains')
    for field,kind in (('requests','transport'),('sent_actions','wire'),('received_responses','response')):
        if result[field]!=sum(e['type']==kind for e in events):errors.append('count mismatch: '+field)
    if result['planned']!=result['attempted']+result['unattempted']:errors.append('denominator mismatch')
    return dict(passed=not errors,errors=errors,events=len(events),games=len(result['outcomes']))
