"""Evidence-gated one-time EX-067 public-resource input recovery.

The original directory and STOP remain intact. A new directory repeats the
whole pilot with the original game/branch seeds and first experiment clock.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time

from .storage import ROOT, atomic, canonical, digest, read, sha
from .tera_config import policy_spec, validate_manifest
from .tera_inputs import VERSION as INPUT_VERSION

ORIGINAL_SOURCE = '96bfb374a404e9ea964f461685af4b1905efdc129c8f534d92a88f17e843d3df'
ALLOWED_CHANGED = frozenset({
    'integration/pokechamp/joint_q/tera_config.py',
    'integration/pokechamp/joint_q/pipeline.py',
    'integration/pokechamp/joint_q/tera_outputs.py',
    'integration/pokechamp/joint_q/tera_verify.py',
    'integration/pokechamp/joint_q/tera.py',
    'integration/pokechamp/joint_q/TERA.md',
    'integration/pokechamp/tests/test_joint_q_tera_outputs.py',
})
ADDED = (
    'integration/pokechamp/joint_q/tera_inputs.py',
    'integration/pokechamp/joint_q/tera_recovery.py',
    'integration/pokechamp/tests/test_joint_q_tera_inputs.py',
    'integration/pokechamp/tests/test_joint_q_tera_recovery.py',
)


def repair_sources(parent):
    parent=Path(parent)
    frozen=read(parent/'frozen-collection.json')
    if frozen['source_id']!=ORIGINAL_SOURCE or digest(frozen['files'])!=ORIGINAL_SOURCE:
        raise ValueError('unexpected recovery source version')
    if sha(parent/'manifest.json')!=frozen['manifest_sha256']:
        raise ValueError('original manifest changed')
    changed={}
    for name, checksum in frozen['files'].items():
        if sha(parent/'frozen/collection'/name)!=checksum:
            raise ValueError('preserved original source changed: '+name)
        current=sha(ROOT/name)
        if current!=checksum:
            if name not in ALLOWED_CHANGED:
                raise ValueError('recovery changed policy/core/EX-066 source: '+name)
            changed[name]=dict(before=checksum,after=current)
    if not changed:
        raise ValueError('recovery has no input correction')
    files={name:sha(ROOT/name) for name in sorted(ALLOWED_CHANGED|set(ADDED))}
    return dict(changed=changed,files=files,
                unchanged_original_sources=len(frozen['files'])-len(changed))


def _seal_parent(parent):
    from .tera_outputs import _files, _copy
    inventory=parent/'verification/parent-v1-files.jsonl'
    seal_path=parent/'verification/parent-v1-seal.json'
    if seal_path.exists():
        seal=read(seal_path)
        if sha(inventory)!=seal['inventory_sha256']:
            raise ValueError('preserved parent inventory changed')
        return seal
    count=total=0
    with tempfile.TemporaryDirectory(prefix='ex067-parent-seal-') as temporary:
        staged=Path(temporary)/'files.jsonl'
        with staged.open('wb') as stream:
            for path in _files(parent):
                name=str(path.relative_to(parent))
                if (name.startswith('versions/') or path.name=='coordinator.lock'
                        or path.name.endswith(('.sqlite-wal','.sqlite-shm','.lock'))
                        or name in ('verification/parent-v1-files.jsonl','verification/parent-v1-seal.json')):
                    continue
                info=dict(path=name,sha256=sha(path),bytes=path.stat().st_size)
                stream.write(canonical(info)+b'\n')
                count+=1
                total+=info['bytes']
        _copy(staged,inventory)
    seal=dict(source_id=ORIGINAL_SOURCE,inventory=str(inventory.relative_to(parent)),
              inventory_sha256=sha(inventory),files=count,bytes=total,
              excluded=['versions/','coordinator.lock','*.lock','*.sqlite-wal','*.sqlite-shm',
                        'verification/parent-v1-files.jsonl','verification/parent-v1-seal.json'])
    atomic(seal_path,seal,immutable=True)
    return seal


def matching_schedule(old):
    """Regenerate the actual manifest, not the preparation command's summary."""
    from .manifest import prepare as schedule
    with tempfile.TemporaryDirectory(prefix='ex067-new-schedule-') as temporary:
        schedule(Path(temporary),experiment='EX-067')
        fresh=read(Path(temporary)/'manifest.json')
    difference={k for k in set(old)|set(fresh) if old.get(k)!=fresh.get(k)}
    if difference-{'version','created_at'} or fresh['games']!=old['games']:
        raise ValueError('recovery changed schedule, seeds, policy or limits')
    fresh['created_at']=old['created_at']
    return fresh


def prepare(parent, directory):
    """Prepare only the registered v1 -> public-tera-v2 recovery, never relabel."""
    from .tera_verify import preserve_ex066
    parent,directory=Path(parent).resolve(),Path(directory).resolve()
    if directory!=parent/'versions/public-tera-v2':
        raise ValueError('recovery must use the registered separate version directory')
    directory.mkdir(parents=True,exist_ok=True)
    if (directory/'recovery-receipt.json').exists():
        return validate_prepared(directory)
    if any(p.name not in {'coordinator.lock','manifest.json','verification'} for p in directory.iterdir()):
        raise ValueError('recovery destination is not empty')
    if (directory/'verification').exists() and any(p.name!='ex066-before.json' for p in (directory/'verification').iterdir()):
        raise ValueError('recovery destination has unexpected verification evidence')
    old=read(parent/'manifest.json')
    if old.get('version')!='ex067-abyssal-tera-rollout-v1' or old.get('recovery'):
        raise ValueError('one recovery from the original pilot is permitted')
    if old['policy']!=policy_spec() or read(parent/'STOP')['reason']!='technical-input':
        raise ValueError('policy changed or original technical stop missing')
    sources=repair_sources(parent)
    fresh=matching_schedule(old)
    proof_path=parent/'verification/tera-resource-correction.json'
    diagnosis_path=parent/'verification/tera-resource-diagnosis.json'
    proof=read(proof_path)
    if (not proof['passed'] or proof['observations']!=314 or proof['original_source_id']!=ORIGINAL_SOURCE
            or proof['diagnosis_sha256']!=sha(diagnosis_path)):
        raise ValueError('independent input correction evidence missing')
    for name,checksum in proof['files'].items():
        if sha(ROOT/name)!=checksum:
            raise ValueError('independent correction source changed: '+name)
    audit=read(parent/'audit.json')
    if (not audit['passed'] or audit['source_id']!=ORIGINAL_SOURCE or audit['games']!={'train':10}
            or audit['observations']!=314 or audit['candidates']!=2835
            or audit['valid_rollouts']!=90720 or audit['planned_rollouts']!=90720):
        raise ValueError('original pilot denominator differs from recovered unit')
    with sqlite3.connect((parent/'rollouts.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        jobs=dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status'))
        attempts=db.execute('SELECT count(*),sum(finished-started) FROM attempts').fetchone()
    if jobs!={'complete':90720} or attempts[0]!=90720:
        raise ValueError('original pilot completion/attempt evidence differs')
    measurements=[read(p) for p in (parent/'measurements').glob('workers-16-*.json')]
    if len(measurements)!=1 or not measurements[0]['passed'] or measurements[0]['counts']!=jobs:
        raise ValueError('original pilot collection timing evidence differs')
    value=dict(reason='public Tera resource lost after bearer fainted',scope='uniform corrected pilot input version',
        directly_defective_game_count=5,superseded_original_games=10,superseded_observations=314,
        superseded_candidates=2835,superseded_rollouts=90720,prior_physical_attempts=attempts[0],
        prior_branch_wall_seconds=measurements[0]['elapsed_seconds'],prior_branch_attempt_wall_seconds=attempts[1],
        valid_for_final_training=False,original_source_id=ORIGINAL_SOURCE,
        parent=str(parent),parent_manifest_sha256=sha(parent/'manifest.json'),
        first_created_at=old['created_at'],policy_unchanged=True,seeds_unchanged=True,
        recollections_per_pilot_game=1,maximum_recollections_per_affected_game=1,
        diagnosis_sha256=sha(diagnosis_path),correction_sha256=sha(proof_path),
        input_observation_version=INPUT_VERSION)
    atomic(parent/'invalidation.json',value,immutable=True)
    stop=read(parent/'STOP')
    stopped=read(stop['runner_state'])
    atomic(parent/'verification/runner-stopped.json',stopped,immutable=True)
    from .tera_outputs import _copy
    _copy(Path(stopped['log']),parent/'verification/pilot-report-failure.log')
    parent_seal=_seal_parent(parent)
    value['parent_seal_sha256']=sha(parent/'verification/parent-v1-seal.json')
    value['parent_inventory_sha256']=parent_seal['inventory_sha256']
    fresh['recovery']=value
    fresh['input_observation_version']=INPUT_VERSION
    validate_manifest(fresh)
    atomic(directory/'manifest.json',fresh,immutable=True)
    preserve_ex066(directory)
    receipt=dict(passed=True,parent=str(parent),directory=str(directory),
        manifest_sha256=sha(directory/'manifest.json'),original_source_id=ORIGINAL_SOURCE,
        parent_seal_sha256=value['parent_seal_sha256'],parent_inventory_sha256=value['parent_inventory_sha256'],
        correction_sha256=value['correction_sha256'],repair_sources=sources,at=time.time())
    atomic(directory/'recovery-receipt.json',receipt,immutable=True)
    return validate_prepared(directory)


def validate_prepared(directory):
    directory=Path(directory)
    receipt=read(directory/'recovery-receipt.json')
    manifest=validate_manifest(read(directory/'manifest.json'))
    parent=Path(receipt['parent'])
    if (not receipt['passed'] or manifest['input_observation_version']!=INPUT_VERSION
            or sha(directory/'manifest.json')!=receipt['manifest_sha256']
            or manifest['created_at']!=read(parent/'manifest.json')['created_at']
            or manifest['recovery']['recollections_per_pilot_game']!=1):
        raise ValueError('recovery manifest/first-clock identity differs')
    for name,checksum in receipt['repair_sources']['files'].items():
        if sha(ROOT/name)!=checksum:
            raise ValueError('prepared correction source changed: '+name)
    if (sha(parent/'verification/parent-v1-seal.json')!=receipt['parent_seal_sha256'] or
            sha(parent/'verification/parent-v1-files.jsonl')!=receipt['parent_inventory_sha256'] or
            sha(parent/'verification/tera-resource-correction.json')!=receipt['correction_sha256']):
        raise ValueError('preserved recovery evidence changed')
    return receipt


def compare_pilot(directory):
    """The input-only repair must preserve every same-seed original trajectory."""
    directory=Path(directory)
    receipt=validate_prepared(directory)
    parent=Path(receipt['parent'])
    source=read(directory/'frozen-collection.json')['source_id']
    target=directory/'verification/paired-pilot-v1-v2.json'
    if target.exists():
        result=read(target)
        if not result['passed'] or result['source_id']!=source or result['compared_rollouts']!=90720:
            raise ValueError('stale paired-pilot validation')
        return result
    fields=('status','score','trace_sha256','seeds','start_boundary','final_boundary')
    query=('SELECT observation_id,action_id,replicate,result_path FROM jobs '
           "WHERE status='complete' ORDER BY observation_id,action_id,replicate")
    count=0
    observed=set()
    candidates=set()
    with sqlite3.connect((parent/'rollouts.sqlite').as_uri()+'?mode=ro',uri=True) as old_db, \
            sqlite3.connect((directory/'rollouts.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as new_db:
        for before,after in zip(old_db.execute(query),new_db.execute(query),strict=True):
            if before[:3]!=after[:3]:
                raise ValueError('paired pilot changed observation/action/replicate identities')
            old=read(parent/before[3])
            new=read(directory/after[3])
            if any(old[key]!=new[key] for key in fields):
                raise ValueError('input-only repair changed a same-seed trajectory: '+str(before[:3]))
            observed.add(before[0])
            candidates.add(before[:2])
            count+=1
    if (count,len(observed),len(candidates))!=(90720,314,2835):
        raise ValueError('paired pilot denominator incomplete')
    result=dict(passed=True,source_id=source,original_source_id=ORIGINAL_SOURCE,
        compared_rollouts=count,compared_observations=len(observed),compared_candidates=len(candidates),
        compared_fields=list(fields),trajectory_differences=0,policy_unchanged=True,
        parent_seal_sha256=receipt['parent_seal_sha256'],at=time.time())
    atomic(target,result,immutable=True)
    return result
