"""Frozen EX-067 gates, preserved EX-066 identities, and explicit provenance."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

from .storage import ROOT, atomic, digest, read, rows, sha
from .manifest import verify
from .tera_config import policy_spec, validate_manifest

TEST_FILES = (
    'test_abyssal_tera.py', 'test_joint_q_tera_actor.py',
    'test_joint_q_tera_pipeline.py', 'test_joint_q_tera_outputs.py',
    'test_joint_q_tera_probes.py',
    'test_joint_q_tera_inputs.py',
    'test_joint_q_tera_recovery.py',
    'test_joint_q.py', 'test_branch_rollout_policy.py',
    'test_branch_simulator.py', 'test_branch_rollout_common.py',
)
BROWSER_CHECKER = 'integration/pokechamp/tests/tera_viewer_browser_check.py'


def browser(directory):
    """Check the sealed export in an existing, separate offline browser env."""
    directory=Path(directory)
    source=verify(directory)
    export=read(directory/'final/viewer-export.json')
    report=read(directory/'final/report.json')
    viewer=Path(export['viewer']).parent
    target=directory/'final/browser-verification.json'
    if target.exists():
        receipt=read(target)
    else:
        evidence=directory/'verification'/f'browser-{time.time_ns()}.json'
        command=['/tmp/ep037/tools/bin/python','-m',
                 'integration.pokechamp.tests.tera_viewer_browser_check',
                 '--source',str(viewer),'--output',str(evidence)]
        completed=subprocess.run(command,cwd=ROOT,env=dict(os.environ),
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if completed.returncode:
            raise RuntimeError('offline browser check failed: '+str(evidence)+'; '+completed.stderr[-2000:])
        receipt=read(evidence)
        receipt.update(source_id=source,evidence=str(evidence.relative_to(directory)),
                       evidence_sha256=sha(evidence))
    if (not receipt['passed'] or receipt['source_id']!=source or
            receipt['checker_sha256']!=sha(ROOT/BROWSER_CHECKER) or
            receipt['export_checksums_sha256']!=export['checksums_sha256'] or
            receipt['games']!=80 or receipt['observations']!=report['observations'] or
            receipt['candidates']!=report['candidates'] or
            sha(directory/receipt['evidence'])!=receipt['evidence_sha256']):
        raise ValueError('offline browser receipt incomplete or stale')
    if not target.exists():
        atomic(target,receipt,immutable=True)
    return receipt


def preserve_ex066(directory, *, final=False):
    directory=Path(directory)
    prepared=ROOT/'.pokechamp-data/experiments/ex066-joint-q-training/prepared/manifest.json'
    frozen=read(prepared)
    sources={name:sha(ROOT/name) for name in frozen['sources']}
    if sources != frozen['sources']:
        raise ValueError('EX-066 sealed source changed')
    data=Path('/mnt/digicap/combined/hyna/backup/pokechamp')
    data_files={name:sha(data/name) for name in frozen['data_files']}
    if data_files != frozen['data_files']:
        raise ValueError('EX-066 sealed input changed')
    # Query installed metadata without importing any tensor/model code or GPUs.
    python=ROOT/'.tools/eve-rlcd/worktrees/pokemon-training/.venv-eve-rlcd/bin/python'
    script='import importlib.metadata,json; print(json.dumps({p:importlib.metadata.version(p) for p in '+repr(list(frozen['packages']))+'}))'
    packages=json.loads(subprocess.check_output([str(python),'-c',script],text=True))
    if packages != frozen['packages']:
        raise ValueError('EX-066 sealed environment changed')
    value=dict(passed=True,at=time.time(),prepared_manifest_sha256=sha(prepared),
               sources=sources,data_files=data_files,packages=packages)
    target=directory/'verification'/('ex066-after.json' if final else 'ex066-before.json')
    if target.exists():
        old=read(target)
        if any(old[k]!=value[k] for k in ('sources','data_files','packages','prepared_manifest_sha256')):
            raise ValueError('EX-066 preservation evidence changed')
        return old
    atomic(target,value,immutable=True)
    return value


def preflight(directory):
    directory=Path(directory)
    source=verify(directory)
    manifest=validate_manifest(read(directory/'manifest.json'))
    if manifest.get('recovery'):
        from .tera_recovery import validate_prepared
        validate_prepared(directory)
    preserve_ex066(directory)
    target=directory/'verification/cpu-tests.json'
    if target.exists():
        receipt=read(target)
        if not receipt['passed'] or receipt['source_id']!=source:
            raise ValueError('CPU test receipt missing or stale')
        for name,checksum in receipt['files'].items():
            if sha(directory/name)!=checksum:
                raise ValueError('CPU test evidence changed')
        for name,checksum in receipt['test_sources'].items():
            if sha(ROOT/name)!=checksum:
                raise ValueError('CPU regression source changed')
        return receipt
    folder=directory/'verification'/f'tests-{time.time_ns()}'
    folder.mkdir(parents=True)
    paths=[ROOT/'integration/pokechamp/tests'/name for name in TEST_FILES]
    if not all(p.is_file() for p in paths):
        raise ValueError('required EX-067 regression file missing')
    command=[str(ROOT/'pokechamp/.venv/bin/python'),'-m','pytest','-q',*[str(p) for p in paths],
             '--junitxml='+str(folder/'junit.xml')]
    env=dict(os.environ,PYTHONPATH=str(ROOT)+':'+str(ROOT/'pokechamp'),CUDA_VISIBLE_DEVICES='',
             PYTHONHASHSEED='20260930')
    with (folder/'tests.log').open('w') as log:
        result=subprocess.run(command,cwd=ROOT/'pokechamp',env=env,stdout=log,stderr=subprocess.STDOUT)
    tree=ET.parse(folder/'junit.xml')
    suites=list(tree.getroot().iter('testsuite'))
    counts={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','errors','failures','skipped')}
    value=dict(passed=result.returncode==0 and counts['tests']>0 and not any(counts[k] for k in ('errors','failures','skipped')),
        source_id=source,command=command,exit_code=result.returncode,counts=counts,
        test_sources={str(p.relative_to(ROOT)):sha(p) for p in paths},
        files={str(p.relative_to(directory)):sha(p) for p in folder.iterdir()},at=time.time())
    atomic(folder/'receipt.json',value,immutable=True)
    if not value['passed']:
        raise ValueError('required CPU tests failed or skipped: '+str(folder))
    atomic(target,value,immutable=True)
    return value


def input_isolation(directory):
    from .serializer import JointInput, render
    from .data import TrainingRecord
    directory=Path(directory)
    source=verify(directory)
    count=0
    forbidden={'policy_audits','policy_audit','last_policy_audit','policy_config_hash',
               'reason','future_rng','opponent_original_set'}
    def inspect(value):
        if isinstance(value,dict):
            # Public candidate unsupported reasons are legitimate. Only explicit
            # policy audit metadata is forbidden; arbitrary text is not a leak.
            if any(k in forbidden-{'reason'} for k in value):
                raise ValueError('policy/private audit leaked into JointInput')
            for v in value.values():
                inspect(v)
        elif isinstance(value,list):
            for v in value:
                inspect(v)
    for path in sorted((directory/'input-records').glob('*.json')):
        row=read(path)
        value=JointInput(row['model_input'])
        inspect(value.payload)
        prompt=render(value)
        # The public loader and renderer boundary are independent of q and all
        # record/provenance IDs. No private container is accepted by render.
        first=TrainingRecord('private-A',value,tuple(0. for _ in value.action_ids))
        second=TrainingRecord('private-B',value,tuple(1. for _ in value.action_ids))
        if render(first.input)!=prompt or render(second.input)!=prompt:
            raise ValueError('targets changed model rendering')
        try:
            render(first)
        except TypeError:
            pass
        else:
            raise ValueError('TrainingRecord accepted at model boundary')
        count+=1
    result=dict(passed=count>0,source_id=source,observations=count,typed_boundary=True,
                target_extremes_byte_equal=True,policy_audit_fields_absent=True)
    atomic(directory/'verification'/f'input-isolation-{count}.json',result,immutable=True)
    return result


def verification(directory):
    directory=Path(directory)
    source=verify(directory)
    cpu=preflight(directory)
    invariance=read(directory/'invariance.json')
    recovery=read(directory/'recovery-verification.json')
    for item in (invariance,recovery):
        if not item['passed'] or item['source_id']!=source:
            raise ValueError('real branch invariance or recovery evidence stale')
    if set(invariance['tested_workers'])!={1,16} or invariance['logical_tasks']!=32:
        raise ValueError('EX-067 real candidate order/worker comparison missing')
    outcomes=[]
    for workers in (1,16):
        measurement=read(directory/f'benchmarks/workers-{workers}/receipt.json')
        if (not measurement['passed'] or measurement['source_id']!=source
                or measurement['finished']!=32 or not measurement['resources']
                or any(min(sample['available_memory'],sample['free_disk'])<24*1024**3
                       for sample in measurement['resources'])):
            raise ValueError('unsafe or stale real worker probe')
        outcomes.append(measurement['outcomes'])
    if outcomes[0]!=outcomes[1]:
        raise ValueError('candidate order/worker outcomes differ')
    isolation=input_isolation(directory)
    value=dict(passed=True,source_id=source,policy=policy_spec(),cpu_tests=cpu['counts']['tests'],
               cpu_sha256=sha(directory/'verification/cpu-tests.json'),
               invariance_sha256=sha(directory/'invariance.json'),
               recovery_sha256=sha(directory/'recovery-verification.json'),
               input_isolation=isolation,at=time.time())
    target=directory/'verification.json'
    if target.exists():
        old=read(target)
        if any(old[k]!=value[k] for k in ('source_id','policy','cpu_sha256','invariance_sha256','recovery_sha256')):
            raise ValueError('verification identity changed')
        return old
    atomic(target,value,immutable=True)
    return value


def cohort_gate(directory, cohort):
    directory=Path(directory)
    source=verify(directory)
    manifest=validate_manifest(read(directory/'manifest.json'))
    result=read(directory/'audit.json')
    evidence=read(directory/'verification.json')
    token=read(directory/'token-summary.json')
    if not all(item['passed'] and item['source_id']==source for item in (result,evidence)):
        raise ValueError('audit/verification missing or stale')
    expected_games=({'train':10} if cohort=='pilot' else {'train':50,'validation':10}
                    if cohort=='rest' else {'train':50,'validation':10,'test':20})
    if result['games']!=expected_games or result['valid_rollouts']!=result['planned_rollouts']:
        raise ValueError('cohort game/32-rollout denominator incomplete')
    if result['incomplete_observations'] or result['duplicates']['quarantined_games']:
        raise ValueError('incomplete or cross-split contaminated observations')
    if token['observations']!=result['observations'] or token['inputs_sha256']!=sha(directory/'inputs.jsonl'):
        raise ValueError('token evidence stale')
    if cohort=='pilot':
        if manifest.get('recovery'):
            from .tera_recovery import compare_pilot
            compare_pilot(directory)
        captures=[read(p) for p in (directory/'games').glob('*/capture.json')]
        expected={g['game_id'] for g in manifest['games'] if g['pilot']}
        if {c['game']['game_id'] for c in captures}!=expected:
            raise ValueError('pilot must contain exactly first ten training seeds')
        # Independent public protocol establishes actual use and a later actor
        # observation, beyond the policy's proposed command/audit.
        sides={s:dict(uses=0,post_observations=0) for s in ('p1','p2')}
        for captured in captures:
            used=set()
            for step in captured['steps']:
                for side,command in step['choices'].items():
                    if side in used:
                        sides[side]['post_observations']+=1
                    if 'terastallize' in command:
                        used.add(side)
            for side in used:
                if not any(line.startswith('|-terastallize|'+side) for line in captured['public_log']):
                    raise ValueError('Tera command missing public event')
                sides[side]['uses']+=1
        if not all(s['uses']>0 and s['post_observations']>0 for s in sides.values()):
            raise ValueError('pilot lacks voluntary original Tera and post-Tera observations on both sides')
        if not all(result['branch_tera'][s]['voluntary_uses']>0 and
                   result['branch_tera'][s]['post_voluntary_observations']>0 for s in ('p1','p2')):
            raise ValueError('pilot lacks voluntary continuation Tera and later observations on both sides')
    else:
        sides=None
    # Later exports replace the root aggregates. Retain the exact admitted
    # cohort bytes so every historical gate hash remains independently usable.
    preserved={}
    names=('audit.json','token-summary.json','tokens.jsonl','summary.json','duplicates.json',
           'inputs.jsonl','targets.jsonl','candidate-records.jsonl','incomplete.jsonl')
    for name in names:
        source_path=directory/name
        destination=directory/'cohorts'/cohort/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        checksum=sha(source_path)
        if destination.exists():
            if sha(destination)!=checksum:
                raise ValueError('cohort evidence changed: '+str(destination))
        else:
            # All subsequent aggregate writers use rename, never edit in place.
            # An immutable hard link preserves this inode without needless IO.
            try:
                os.link(source_path,destination)
            except OSError:
                shutil.copyfile(source_path,destination)
            if sha(destination)!=checksum:
                raise ValueError('cohort evidence copy mismatch')
        preserved[name]=dict(path=str(destination.relative_to(directory)),sha256=checksum,
                             bytes=destination.stat().st_size)
    value=dict(passed=True,source_id=source,cohort=cohort,workers=16,
               audit_sha256=sha(directory/'audit.json'),verification_sha256=sha(directory/'verification.json'),
               token_summary_sha256=sha(directory/'token-summary.json'),original_tera=sides,
               preserved_evidence=preserved,freeze_test_serializer=True,at=time.time())
    if cohort=='pilot' and manifest.get('recovery'):
        value['paired_pilot_sha256']=sha(directory/'verification/paired-pilot-v1-v2.json')
    target=directory/(cohort+'-gate.json')
    if target.exists():
        old=read(target)
        if old['source_id']!=source or not old['passed']:
            raise ValueError('stale cohort gate')
        return old
    atomic(target,value,immutable=True)
    return value
