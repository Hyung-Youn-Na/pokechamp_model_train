"""CPU-only stage orchestration. Pilot gates are explicit durable artifacts."""
from __future__ import annotations
import concurrent.futures as futures
from collections import Counter,defaultdict
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import time
from .storage import atomic, canonical, digest, jsonl, read, rows, sha
from .manifest import verify
from .ledger import Ledger


class ResourceReserveError(RuntimeError):
    """An operational pause, never a completed or invalid battle outcome."""


def resources(directory):
    memory={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
    disk=shutil.disk_usage(directory)
    return dict(available_memory=memory['MemAvailable'],free_disk=disk.free,at=time.time())


def admission(directory):
    info=resources(directory)
    if info['available_memory']<24*1024**3 or info['free_disk']<24*1024**3:
        atomic(Path(directory)/'resource-stop.json',info)
        raise ResourceReserveError('resource reserve below 24 GiB; new submissions stopped, resumable artifacts retained')


def transient_error(error):
    return any(token in str(error) for token in (
        'deadline exceeded', 'exited before a response', 'Broken pipe',
        'Connection reset by peer', 'timed out'))


def stop(directory, reason, error):
    path = Path(directory)/'STOP'
    if not path.exists():
        atomic(path,dict(reason=reason,error=str(error),at=time.time()),immutable=True)


def check_stop(directory):
    path=Path(directory)/'STOP'
    if path.exists():
        try:
            reason=read(path).get('reason')
        except (ValueError,TypeError):
            reason=None
        if reason=='resources':
            raise ResourceReserveError('cooperative resource stop before next observation')
        raise RuntimeError('cooperative technical stop before next observation')


def select_games(directory,stage):
    manifest=read(Path(directory)/'manifest.json')
    if stage not in ('pilot','rest','test','all'):
        raise ValueError('invalid collection cohort')
    if stage!='pilot':
        gate=read(Path(directory)/'pilot-gate.json')
        if not gate['passed'] or gate['source_id']!=verify(directory):
            raise ValueError('pilot gate missing or stale')
    if manifest.get('namespace') == 'EX067' and stage in ('test','all'):
        if stage == 'all':
            raise ValueError('EX-067 requires pilot, rest, test in that order')
        gate = read(Path(directory)/'rest-gate.json')
        if not gate['passed'] or gate['source_id'] != verify(directory):
            raise ValueError('train/validation completion gate missing or stale')
    return [g for g in manifest['games'] if (g['pilot'] if stage=='pilot' else
            g['split']=='test' if stage=='test' else not g['pilot'] and g['split']!='test' if stage=='rest' else True)]


def capture_one(args):
    from .capture import capture,validate_game
    directory,game=args
    folder=Path(directory)/'games'/game['game_id']
    existing=folder/'validated.json'
    if existing.exists():
        record=capture(directory,game)
        receipt=validate_game(directory,game)
        return dict(game_id=game['game_id'],roots=len(record['roots']),turns=record['turns'],validated=receipt['passed'])
    attempts=len(list(folder.glob('attempt-*-start.json')))
    if attempts and (folder/f'attempt-{attempts}-finish.json').exists():
        previous=read(folder/f'attempt-{attempts}-finish.json')
        if 'error' in previous and not previous.get('transient') and not previous.get('resumable_pause'):
            raise ValueError('original technical failure requires explicit versioned recovery')
    while True:
        if attempts>=3:
            raise RuntimeError('original game exhausted three attempts: '+game['game_id'])
        attempts+=1
        atomic(folder/f'attempt-{attempts}-start.json',dict(at=time.time(),game=game),immutable=True)
        try:
            record=capture(directory,game)
            receipt=validate_game(directory,game)
        except Exception as error:
            atomic(folder/f'attempt-{attempts}-finish.json',dict(at=time.time(),error=repr(error),
                   transient=transient_error(error),resumable_pause=isinstance(error,ResourceReserveError)),immutable=True)
            if isinstance(error,ResourceReserveError) or not transient_error(error) or attempts>=3:
                raise
        else:
            atomic(folder/f'attempt-{attempts}-finish.json',dict(at=time.time(),passed=True),immutable=True)
            break
    return dict(game_id=game['game_id'],roots=len(record['roots']),turns=record['turns'],validated=receipt['passed'])


def capture_games(directory,games,workers=4):
    return _map_stage(directory,games,workers,capture_one,'capture')


def _map_stage(directory,games,workers,worker,stage):
    verify(directory)
    admission(directory)
    if (Path(directory)/'STOP').exists():
        raise RuntimeError('STOP present; explicit same-checkpoint resume required')
    results=[]
    remaining=iter(games)
    failure=None
    with futures.ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        pending={}
        def fill():
            while failure is None and len(pending)<workers:
                admission(directory)
                game=next(remaining,None)
                if game is None:
                    break
                pending[pool.submit(worker,(str(directory),game))]=game
        try:
            fill()
        except Exception as error:
            failure=error
            stop(directory,'resources' if isinstance(error,ResourceReserveError) else 'technical',error)
        while pending:
            done,_=futures.wait(pending,timeout=10,return_when=futures.FIRST_COMPLETED)
            for future in done:
                pending.pop(future)
                try:
                    results.append(future.result())
                except Exception as error:
                    failure=failure or error
                    stop(directory,'resources' if isinstance(error,ResourceReserveError) else 'technical',error)
            atomic(Path(directory)/(stage+'-progress.json'),dict(completed=results,planned=len(games),at=time.time()))
            try:
                if failure is None:
                    admission(directory)
                fill()
            except Exception as error:
                failure=failure or error
                stop(directory,'resources' if isinstance(error,ResourceReserveError) else 'technical',error)
    if failure is not None:
        raise failure
    verify(directory)
    return results


def input_one(args):
    from .serializer import generate,VERSION,fingerprint
    from ..diagnostics.jev_damage import Engine
    from ..diagnostics.jev_offline import RoleDB
    from ..diagnostics.damage_sets import SetSnapshot
    from ..observation.build import DEFAULT_BUILD
    directory,game=args
    directory=Path(directory)
    check_stop(directory)
    manifest=read(directory/'manifest.json')
    capture=read(directory/'games'/game['game_id']/'capture.json')
    validated=read(directory/'games'/game['game_id']/'validated.json')
    if not validated['passed']:
        raise ValueError('unvalidated original game')
    dex=read(DEFAULT_BUILD/'dex.json')
    sets=SetSnapshot()
    roles=RoleDB()
    count=0
    with Engine() as engine:
        for info in capture['roots']:
            check_stop(directory)
            admission(directory)
            target=directory/'input-records'/f"{info['observation_id']}.json"
            if target.exists():
                count+=1
                continue
            if sha(directory/info['path'])!=info['sha256']:
                raise ValueError('input root checksum mismatch')
            root=read(directory/info['path'])
            started=time.time()
            value,commands,audit=generate(root['official'],root['prefix'],manifest['own']['text'],
                                         dex=dex,engine=engine,snapshot=sets,roles=roles)
            if manifest.get('namespace')=='EX067':
                from .tera_config import describe_continuation
                from .tera_inputs import with_public_tera
                value=describe_continuation(value)
                value=with_public_tera(value,root['prefix'])
            if tuple(commands)!=tuple(a['action_id'] for a in root['actions']):
                raise ValueError('official/generation candidate mismatch')
            from ..branch_rollouts.common import command
            if [command(c) for c in commands.values()]!=[a['command'] for a in root['actions']]:
                raise ValueError('candidate command mapping mismatch')
            atomic(directory/'private/input-audits'/f"{info['observation_id']}.json.gz",audit,immutable=True)
            record=dict(observation_id=info['observation_id'],game_id=game['game_id'],split=game['split'],
                        serializer_version=VERSION,model_input=value.payload_json,action_ids=list(value.action_ids),
                        fingerprint=fingerprint(value),input_sha256=digest(value.payload),
                        elapsed_seconds=time.time()-started)
            atomic(target,record,immutable=True)
            count+=1
    return dict(game_id=game['game_id'],inputs=count)


def generate_inputs(directory,games,workers=4):
    return _map_stage(directory,games,workers,input_with_retry,'input')


def input_with_retry(args):
    directory,game=args
    folder=Path(directory)/'private/input-attempts'/game['game_id']
    attempts=len(list(folder.glob('attempt-*-start.json')))
    if attempts and (folder/f'attempt-{attempts}-finish.json').exists():
        previous=read(folder/f'attempt-{attempts}-finish.json')
        if previous.get('passed'):
            return input_one(args)
        if not previous.get('transient') and not previous.get('resumable_pause'):
            raise ValueError('input technical failure requires explicit versioned recovery')
    while attempts<3:
        attempts+=1
        atomic(folder/f'attempt-{attempts}-start.json',dict(at=time.time(),game=game),immutable=True)
        try:
            result=input_one(args)
        except Exception as error:
            atomic(folder/f'attempt-{attempts}-finish.json',dict(at=time.time(),error=repr(error),
                   transient=transient_error(error),resumable_pause=isinstance(error,ResourceReserveError)),immutable=True)
            if isinstance(error,ResourceReserveError) or not transient_error(error) or attempts==3:
                raise
        else:
            atomic(folder/f'attempt-{attempts}-finish.json',dict(at=time.time(),passed=True),immutable=True)
            return result
    raise RuntimeError('input generation exhausted three attempts: '+game['game_id'])


def register(directory,games,source):
    ledger=Ledger(directory,source)
    try:
        ledger.recover()
        for game in games:
            capture=read(Path(directory)/'games'/game['game_id']/'capture.json')
            valid=read(Path(directory)/'games'/game['game_id']/'validated.json')
            if not valid['passed'] or valid['capture_sha256']!=sha(Path(directory)/'games'/game['game_id']/'capture.json'):
                raise ValueError('unvalidated game roots')
            for root in capture['roots']:
                ledger.register(root,game['game_id'])
        return ledger.counts()
    finally:
        ledger.close()


def collect(directory,workers=32,limit=None):
    from .rollout import initialize,execute
    directory=Path(directory)
    source=verify(directory)
    admission(directory)
    ledger=Ledger(directory,source)
    ledger.recover()
    if (directory/'STOP').exists():
        raise RuntimeError('STOP present; inspect and remove only to resume same experiment')
    started=time.time()
    finished=0
    submitted=0
    pending={}
    resource_samples=[]
    failed=False
    paused=None
    ctx=multiprocessing.get_context('spawn')
    try:
        with futures.ProcessPoolExecutor(max_workers=workers,mp_context=ctx,initializer=initialize,
                                        initargs=(str(directory),source)) as pool:
            def fill():
                nonlocal submitted,paused
                while not failed and paused is None and len(pending)<workers and (limit is None or submitted<limit):
                    try:
                        admission(directory)
                    except ResourceReserveError as error:
                        paused=error
                        stop(directory,'resources',error)
                        break
                    task=ledger.claim()
                    if task is None:
                        break
                    pending[pool.submit(execute,task)]=task
                    submitted+=1
            fill()
            last_progress=0
            while pending:
                done,_=futures.wait(pending,timeout=10,return_when=futures.FIRST_COMPLETED)
                for future in done:
                    task=pending.pop(future)
                    try:
                        result=future.result()
                    except Exception as error:
                        failed=True
                        atomic(directory/'collection-worker-failure.json',dict(job_id=task['id'],
                               attempt=task['attempt'],error=repr(error),at=time.time()))
                        stop(directory,'technical',error)
                        continue
                    ledger.finish(result['job_id'],result['attempt'],result['path'])
                    finished+=1
                    if result['status'] in ('error','interrupted'):
                        detail=read(result['path'])
                        # Simulator transport is transient; malformed state,
                        # illegal command, parser/schema errors affect integrity.
                        transient=transient_error(detail.get('error',''))
                        cooperative=result['status']=='interrupted' and (directory/'STOP').exists()
                        if not transient and not cooperative:
                            failed=True
                            atomic(directory/'collection-failure.json',detail)
                            stop(directory,'technical',detail.get('error','unknown failure'))
                    elif (directory/'private/checkpoints'/f"{task['id']}.json.gz").exists():
                        (directory/'private/checkpoints'/f"{task['id']}.json.gz").unlink()
                now=time.time()
                if paused is None and not failed:
                    try:
                        admission(directory)
                    except ResourceReserveError as error:
                        paused=error
                        stop(directory,'resources',error)
                if now-last_progress>10:
                    resource_samples.append(resources(directory))
                    atomic(directory/'progress.json',dict(workers=workers,counts=ledger.counts(),
                           pending=len(pending),elapsed_seconds=now-started,at=now))
                    last_progress=now
                if not (directory/'STOP').exists():
                    fill()
        result=dict(workers=workers,finished=finished,submitted=submitted,elapsed_seconds=time.time()-started,
                    rollouts_per_second=finished/(time.time()-started),counts=ledger.counts(),
                    resources=resource_samples,passed=not failed)
        atomic(directory/'measurements'/f'workers-{workers}-{time.time_ns()}.json',result,immutable=True)
        if failed:
            raise RuntimeError('shared integrity failure; collection stopped with checkpoint evidence')
        if paused:
            raise paused
        if (directory/'STOP').exists():
            raise RuntimeError('collection paused with checkpoint evidence')
        if result['counts'].get('failed',0):
            raise RuntimeError('rollouts exhausted three attempts; incomplete labels retained')
        verify(directory)
        return result
    finally:
        ledger.close()


def export(directory):
    from .serializer import JointInput,fingerprint
    from .data import TARGET_VERSION
    directory=Path(directory)
    source=verify(directory)
    ledger=Ledger(directory,source)
    ledger.recover()
    inputs=[read(p) for p in sorted((directory/'input-records').glob('*.json'))]
    groups=defaultdict(list)
    for row in inputs:
        row['fingerprint']=fingerprint(JointInput(row['model_input']))
        row['fingerprint_version']='semantic-joint-v1'
        groups[row['fingerprint']].append(row)
    collisions=[v for v in groups.values() if len({r['split'] for r in v})>1]
    quarantined={r['game_id'] for group in collisions for r in group}
    atomic(directory/'duplicates.json',dict(cross_split_collisions=[[(r['observation_id'],r['split']) for r in g] for g in collisions],
                                           quarantined_games=sorted(quarantined),
                                           within_split_duplicate_observations=sum(len(v)-1 for v in groups.values() if len(v)>1)))
    targets=[]
    individual=[]
    incomplete=[]
    for row in inputs:
        row['quarantined']=row['game_id'] in quarantined
        counts=[]
        qs=[]
        for aid in row['action_ids']:
            jobs=ledger.db.execute('SELECT * FROM jobs WHERE observation_id=? AND action_id=? ORDER BY replicate',
                                  (row['observation_id'],aid)).fetchall()
            counter=Counter()
            for job in jobs:
                if job['status']=='complete':
                    record=read(directory/job['result_path'])
                    counter[record['status']]+=1
            count={k:counter[k] for k in ('win','draw','loss')}
            count['n']=sum(count.values())
            if count['n']>32 or len(jobs)>32:
                raise ValueError('duplicate rollout denominator')
            q=(count['win']+.5*count['draw'])/32 if count['n']==32 else None
            counts.append(count)
            qs.append(q)
            individual.append(dict(schema='pokemon-action-value-v1',input_ref=row['observation_id'],
                action_id=aid,evaluated_action=next(a for a in JointInput(row['model_input']).payload['actions'] if a['action_id']==aid),
                target_probabilities=[q,1-q] if q is not None else None,counts=count,complete=q is not None))
        complete=all(q is not None for q in qs) and not row['quarantined']
        target=dict(observation_id=row['observation_id'],action_ids=row['action_ids'],q=qs,counts=counts,
                    complete=complete,target_version=TARGET_VERSION,source_id=source)
        targets.append(target)
        if not complete:
            incomplete.append(dict(observation_id=row['observation_id'],counts=counts,quarantined=row['quarantined']))
    jsonl(directory/'inputs.jsonl',inputs)
    jsonl(directory/'targets.jsonl',targets)
    jsonl(directory/'candidate-records.jsonl',individual)
    jsonl(directory/'incomplete.jsonl',incomplete)
    result=dict(observations=len(inputs),candidates=sum(len(r['action_ids']) for r in inputs),
                complete_observations=sum(r['complete'] for r in targets),quarantined_games=sorted(quarantined),
                ledger=ledger.counts(),source_id=source)
    atomic(directory/'summary.json',result)
    ledger.close()
    return result
