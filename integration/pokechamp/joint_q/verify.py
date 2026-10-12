"""Independent artifact arithmetic, completeness and pilot admission evidence."""
from __future__ import annotations
from collections import Counter,defaultdict
import json
import os
from pathlib import Path
import subprocess
import time
from .storage import ROOT,atomic,digest,read,rows,sha,rollout_seeds
from .manifest import verify
from .ledger import Ledger


def tokens(directory):
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    python=ROOT/'.tools/eve-rlcd/worktrees/pokemon-training/.venv-eve-rlcd/bin/python'
    result=subprocess.run([str(python),'-m','integration.pokechamp.joint_q.tokenize',str(directory)],
                          env=env,text=True,capture_output=True,check=True)
    return json.loads(result.stdout)


def audit(directory):
    from .serializer import JointInput,VERSION,fingerprint
    directory=Path(directory)
    source=verify(directory)
    manifest=read(directory/'manifest.json')
    from .tera_config import seed_function
    seeds_for = seed_function(manifest)
    names = {side: manifest.get('namespace','EX065') + side for side in ('p1','p2')}
    captures={p.parent.name:read(p) for p in (directory/'games').glob('*/capture.json')}
    inputs=rows(directory/'inputs.jsonl')
    targets=rows(directory/'targets.jsonl')
    individual=rows(directory/'candidate-records.jsonl')
    expected={r['observation_id']:r for c in captures.values() for r in c['roots']}
    if len(expected)!=len(inputs) or len({r['observation_id'] for r in inputs})!=len(inputs):
        raise ValueError('captured/input observation denominator mismatch')
    if set(expected)!={r['observation_id'] for r in inputs}:
        raise ValueError('missing captured input')
    by_id={r['observation_id']:r for r in targets}
    if len(by_id)!=len(targets) or set(expected)!=set(by_id):
        raise ValueError('target observation coverage mismatch')
    candidate_map={(r['input_ref'],r['action_id']):r for r in individual}
    ledger=Ledger(directory,source)
    ledger.recover()
    coverage=Counter()
    phases=Counter()
    wdl=Counter()
    branch_tera={s:dict(voluntary_uses=0,post_voluntary_observations=0) for s in ('p1','p2')}
    expected_jobs=0
    ncomplete=0
    values=[]
    gaps=[]
    for row in inputs:
        oid=row['observation_id']
        value=JointInput(row['model_input'])
        if row['serializer_version']!=VERSION or digest(value.payload)!=row['input_sha256'] or fingerprint(value)!=row['fingerprint']:
            raise ValueError('input identity/fingerprint mismatch')
        root=expected[oid]
        if sha(directory/root['path'])!=root['sha256']:
            raise ValueError('root checksum mismatch')
        rootdata=read(directory/root['path'])
        ids=[a['action_id'] for a in root['actions']]
        if list(value.action_ids)!=ids or row['action_ids']!=ids or by_id[oid]['action_ids']!=ids:
            raise ValueError('official candidate coverage mismatch')
        target=by_id[oid]
        phases[value.payload['state']['decision_kind']]+=1
        for index,action in enumerate(root['actions']):
            aid=action['action_id']
            coverage[aid.split('_')[0]+('_tera' if aid.endswith('_terastallize') else '')]+=1
            expected_jobs+=32
            jobs=ledger.db.execute('SELECT * FROM jobs WHERE observation_id=? AND action_id=? ORDER BY replicate',(oid,aid)).fetchall()
            if len(jobs)!=32 or [j['replicate'] for j in jobs]!=list(range(32)):
                raise ValueError('logical rollout coverage mismatch')
            counts=Counter()
            for job in jobs:
                if job['status']!='complete':
                    continue
                result=read(directory/job['result_path'])
                if result['source_id']!=source or result['root_sha256']!=root['sha256'] or result['seeds']!=seeds_for(oid,job['replicate']):
                    raise ValueError('rollout provenance mismatch')
                if digest(result['trace'])!=result['trace_sha256'] or result['trace'][0]['choices']['p2']!=action['command']:
                    raise ValueError('trace/action mismatch')
                log=result['public_log']
                expected_outcome='draw' if '|tie|' in log or '|tie' in log else 'win' if '|win|'+names['p2'] in log else 'loss' if '|win|'+names['p1'] in log else None
                if result['status']!=expected_outcome or not result['terminal']:
                    raise ValueError('terminal protocol/outcome mismatch')
                if manifest.get('namespace')=='EX067':
                    if result.get('policy')!=manifest['policy']:
                        raise ValueError('branch policy identity differs from frozen manifest')
                    used=set()
                    for step_index,step in enumerate(result['trace']):
                        for side,choice in step['choices'].items():
                            if side in used:
                                branch_tera[side]['post_voluntary_observations']+=1
                            if 'terastallize' in choice and not (step_index==0 and side=='p2'):
                                if side in used:
                                    raise ValueError('duplicate voluntary Tera on same side')
                                used.add(side)
                                branch_tera[side]['voluntary_uses']+=1
                                if not any(line.startswith('|-terastallize|'+side) for line in log):
                                    raise ValueError('voluntary Tera lacks public simulator event')
                counts[result['status']]+=1
                wdl[result['status']]+=1
                ncomplete+=1
            n=sum(counts.values())
            c={k:counts[k] for k in ('win','draw','loss')}|dict(n=n)
            q=(counts['win']+.5*counts['draw'])/32 if n==32 else None
            if c!=target['counts'][index] or q!=target['q'][index]:
                raise ValueError('ledger -> WDL -> q mismatch')
            single=candidate_map[(oid,aid)]
            if single['counts']!=c or single['target_probabilities']!=([q,1-q] if q is not None else None):
                raise ValueError('candidate vs joint target mismatch')
        if target['complete']:
            if row.get('quarantined') or any(q is None for q in target['q']):
                raise ValueError('incomplete observation admitted')
            values.extend(target['q'])
            gaps.append(max(target['q'])-min(target['q']))
    if len(individual)!=sum(len(r['action_ids']) for r in inputs):
        raise ValueError('candidate export coverage mismatch')
    # All source game IDs and opponent species groups retain their declared split.
    declared={g['game_id']:g for g in manifest['games']}
    split_groups=defaultdict(set)
    for game in manifest['games']:
        split_groups[game['group_id']].add(game['split'])
    if any(len(v)>1 for v in split_groups.values()):
        raise ValueError('opponent group split leakage')
    for gid,capture in captures.items():
        if capture['game']!=declared[gid]:
            raise ValueError('original game split/seed identity mismatch')
        validated=read(directory/'games'/gid/'validated.json')
        if not validated['passed'] or validated['roots']!=[r['observation_id'] for r in capture['roots']]:
            raise ValueError('incomplete root restoration gate')
    duplicate=read(directory/'duplicates.json')
    counts=ledger.counts()
    result=dict(passed=True,source_id=source,games=dict(Counter(c['game']['split'] for c in captures.values())),
        observations=len(inputs),candidates=len(individual),planned_rollouts=expected_jobs,valid_rollouts=ncomplete,
        ledger=counts,wdl=dict(wdl),decision_kinds=dict(phases),candidate_kinds=dict(coverage),
        complete_observations=sum(t['complete'] for t in targets),incomplete_observations=sum(not t['complete'] for t in targets),
        q_mean=sum(values)/len(values) if values else None,q_min=min(values,default=None),q_max=max(values,default=None),
        all_zero_observations=sum(t['complete'] and all(q==0 for q in t['q']) for t in targets),
        value_gap_mean=sum(gaps)/len(gaps) if gaps else None,duplicates=duplicate,
        elapsed_since_ledger_seconds=time.time()-float(ledger.db.execute("SELECT value FROM metadata WHERE key='started_at'").fetchone()[0]),
        artifact_bytes=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()),
        model_calls=0,api_calls=0,viewer='required' if manifest.get('namespace')=='EX067' else 'omitted_by_user',
        complete=len(captures)==80 and ncomplete==expected_jobs and all(t['complete'] for t in targets),
        limitation='actual hidden state and fixed '+manifest['continuation_policy']['name']+' continuation; not independent situation count or model performance')
    if manifest.get('namespace')=='EX067':
        result['branch_tera']=branch_tera
        result['policy']=manifest['policy']
    atomic(directory/'audit.json',result)
    ledger.close()
    return result


def pilot_gate(directory):
    directory=Path(directory)
    result=audit(directory)
    required=read(directory/'verification.json')
    if not required.get('passed') or required['source_id']!=result['source_id']:
        raise ValueError('independent regression/invariance/interruption verification missing')
    captures=[read(p) for p in (directory/'games').glob('*/capture.json')]
    pilots={g['game_id'] for g in read(directory/'manifest.json')['games'] if g['pilot']}
    if pilots!={c['game']['game_id'] for c in captures} or not all(c['game']['pilot'] for c in captures):
        raise ValueError('pilot must contain exactly ten approved original games')
    if result['valid_rollouts']!=result['planned_rollouts'] or result['incomplete_observations'] or result['duplicates']['quarantined_games']:
        raise ValueError('pilot incomplete or cross-split collision')
    token=read(directory/'token-summary.json')
    if token['observations']!=result['observations'] or token['inputs_sha256']!=sha(directory/'inputs.jsonl'):
        raise ValueError('token evidence stale')
    measurements=[read(p) for p in (directory/'measurements').glob('*.json')]
    safe=[m for m in measurements if m['passed'] and m.get('count_as_labels') is False and m['resources'] and
          min(r['available_memory'] for r in m['resources'])>=24*1024**3]
    if not {16,32,48}<={m['workers'] for m in safe}:
        raise ValueError('16/32/48 pilot throughput comparison missing')
    choice=max(safe,key=lambda m:m['rollouts_per_second'])['workers']
    gate=dict(passed=True,source_id=result['source_id'],workers=choice,audit_sha256=sha(directory/'audit.json'),
              verification_sha256=sha(directory/'verification.json'),at=time.time(),
              freeze_test_serializer=True)
    atomic(directory/'pilot-gate.json',gate,immutable=True)
    return gate
