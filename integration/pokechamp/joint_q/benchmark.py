"""Same-seed worker/order probes with durable attempts, isolated from labels."""
from __future__ import annotations
import concurrent.futures as futures
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import time
from .storage import atomic, digest, read, sha
from .manifest import verify
from .ledger import Ledger
from .pipeline import resources, admission, ResourceReserveError, stop, transient_error
from .rollout import initialize, execute

OUTCOME_FIELDS = ('status','score','trace_sha256','start_boundary','final_boundary','seeds')
_TERMINAL = {'win','draw','loss'}
_RESERVE = 24 * 1024**3


def task_identity(task, source):
    if task.get('source_id',source)!=source:
        raise ValueError('probe task source mismatch')
    return dict(job_id=task['id'],observation_id=task['observation_id'],
        action_id=task['action_id'],replicate=task['replicate'],root_path=task['root_path'],
        root_sha256=task['root_sha256'],source_id=source,seeds=json.loads(task['seeds']))


def result_path(folder, task, attempt):
    return Path(folder)/'private/results'/f"{task['id']}-a{attempt}.json.gz"


def validate_result(folder, source, task, path, *, checksum=None):
    """Validate a probe result independently before reuse or comparison."""
    folder,path=Path(folder),Path(path)
    if checksum is not None and sha(path)!=checksum:
        raise ValueError('probe result checksum changed')
    row=read(path)
    identity=task_identity(task,source)
    if any(row.get(k)!=v for k,v in identity.items() if k!='root_path'):
        raise ValueError('probe result identity/source/root/seed mismatch')
    attempt=row.get('attempt')
    if type(attempt) is not int or not 1<=attempt<=3 or path!=result_path(folder,task,attempt):
        raise ValueError('probe result attempt/path mismatch')
    if digest(row.get('trace'))!=row.get('trace_sha256'):
        raise ValueError('probe result trace hash mismatch')
    if row.get('status') not in _TERMINAL|{'error','interrupted'}:
        raise ValueError('unknown probe outcome')
    root_path=folder/task['root_path']
    if sha(root_path)!=task['root_sha256']:
        raise ValueError('probe root changed')
    root=read(root_path)
    if row.get('start_boundary') is not None and row['start_boundary']!=root['boundary']:
        raise ValueError('probe start boundary mismatch')
    from .actor import normalize_policy
    if normalize_policy(row.get('policy'))!=normalize_policy(root.get('policy')):
        raise ValueError('probe result policy mismatch')
    if row['trace']:
        action=next((a['command'] for a in root['actions'] if a['action_id']==task['action_id']),None)
        if action is None or row['trace'][0]['choices'].get('p2')!=action:
            raise ValueError('probe forced candidate mismatch')
    if row['status'] in _TERMINAL:
        if not row.get('terminal') or row.get('score')!={'win':1,'draw':.5,'loss':0}[row['status']]:
            raise ValueError('nonterminal probe result cannot be reused')
        if not row['trace'] or not row.get('final_boundary') or row.get('start_boundary')!=root['boundary']:
            raise ValueError('completed probe omitted a decision boundary')
    return row


def _attempt_folder(folder, task):
    return Path(folder)/'probe-attempts'/task['id']


def _record_failure(folder, source, task, attempt, error, *, interrupted=False):
    value=dict(identity=task_identity(task,source),attempt=attempt,error=str(error),
               transient=transient_error(error),interrupted=interrupted,at=time.time())
    path=_attempt_folder(folder,task)/f'attempt-{attempt}-finish.json'
    if path.exists():
        old=read(path)
        if old['identity']!=value['identity'] or old['attempt']!=attempt:
            raise ValueError('probe attempt failure identity mismatch')
        return old
    atomic(path,value,immutable=True)
    return value


def inspect_task(folder, source, task):
    """Recover durable attempts; call only while this task has no active worker."""
    folder=Path(folder)
    identity=task_identity(task,source)
    attempts=set()
    completed=[]
    for attempt in range(1,4):
        base=_attempt_folder(folder,task)
        start,finish=base/f'attempt-{attempt}-start.json',base/f'attempt-{attempt}-finish.json'
        path=result_path(folder,task,attempt)
        if start.exists():
            saved=read(start)
            if saved['identity']!=identity or saved['attempt']!=attempt:
                raise ValueError('probe attempt source/identity changed')
            attempts.add(attempt)
        if finish.exists():
            saved=read(finish)
            if saved['identity']!=identity or saved['attempt']!=attempt:
                raise ValueError('probe failure source/identity changed')
            attempts.add(attempt)
            if not saved.get('transient') and not saved.get('interrupted'):
                raise ValueError('probe technical failure requires versioned recovery: '+saved['error'])
        if path.exists():
            row=validate_result(folder,source,task,path)
            attempts.add(attempt)
            if row['status'] in _TERMINAL:
                completed.append((row,path))
            elif row['status']=='error' and not transient_error(row.get('error','')):
                raise ValueError('probe technical failure requires versioned recovery: '+str(row.get('error')))
        elif start.exists() and not finish.exists():
            _record_failure(folder,source,task,attempt,
                            'coordinator/worker interrupted before atomic result',interrupted=True)
    if attempts and attempts!=set(range(1,max(attempts)+1)):
        raise ValueError('probe attempt sequence has a gap')
    if completed:
        baseline={key:completed[0][0][key] for key in OUTCOME_FIELDS}
        if any({key:row[key] for key in OUTCOME_FIELDS}!=baseline for row,_ in completed[1:]):
            raise ValueError('conflicting completed probe trajectories')
        return completed[-1],max(attempts)
    return None,max(attempts,default=0)


def begin_attempt(folder, source, task):
    completed,used=inspect_task(folder,source,task)
    if completed:
        return completed,None
    if used>=3:
        raise RuntimeError('probe exhausted three attempts: '+task['id'])
    attempt=used+1
    atomic(_attempt_folder(folder,task)/f'attempt-{attempt}-start.json',
           dict(identity=task_identity(task,source),attempt=attempt,at=time.time()),immutable=True)
    return None,dict(task,attempt=attempt)


def propagate_stop(directory, folder):
    directory,folder=Path(directory),Path(folder)
    path=directory/'STOP'
    if not path.exists():
        return
    stopped=read(path)
    local=folder/'STOP'
    if not local.exists():
        atomic(local,dict(stopped,parent_stop_sha256=sha(path)),immutable=True)
    if stopped.get('reason')=='resources':
        raise ResourceReserveError('parent resource pause propagated to probe checkpoint')
    raise RuntimeError('parent STOP propagated to probe checkpoint: '+str(stopped.get('reason')))


def check_resources(directory, folder):
    propagate_stop(directory,folder)
    sample=resources(directory)
    if sample['available_memory']<_RESERVE or sample['free_disk']<_RESERVE:
        error=ResourceReserveError('probe resource reserve below 24 GiB')
        atomic(Path(directory)/'resource-stop.json',sample)
        stop(directory,'resources',error)
        atomic(Path(folder)/'resource-pauses'/f'{time.time_ns()}.json',sample,immutable=True)
        propagate_stop(directory,folder)
        raise error
    return sample


def resume_local_pause(directory, folder):
    folder=Path(folder)
    propagate_stop(directory,folder)
    if not (folder/'STOP').exists():
        return
    stopped=read(folder/'STOP')
    if stopped.get('reason')!='resources':
        raise ValueError('probe technical STOP requires versioned recovery')
    admission(directory)
    atomic(folder/'resource-pauses'/f'resumed-{time.time_ns()}.json',stopped,immutable=True)
    (folder/'STOP').unlink()


def materialize_roots(directory, folder):
    """Private immutable copies avoid symlink traversal in the sealed inventory."""
    directory,folder=Path(directory),Path(folder)
    for name in ('roots','blobs'):
        source=directory/'private'/name
        target=folder/'private'/name
        if target.is_symlink():
            if target.resolve()!=source.resolve():
                raise ValueError('probe root/blob link points to another collection')
            target.unlink()
        target.mkdir(parents=True,exist_ok=True)
        for original in source.rglob('*'):
            if original.is_symlink():
                raise ValueError('source root/blob tree contains a symlink')
            destination=target/original.relative_to(source)
            if original.is_dir():
                destination.mkdir(parents=True,exist_ok=True)
                continue
            destination.parent.mkdir(parents=True,exist_ok=True)
            if destination.exists():
                if destination.is_symlink() or sha(destination)!=sha(original):
                    raise ValueError('probe root/blob copy changed')
            else:
                try:
                    os.link(original,destination)
                except OSError:
                    # Copy via a staging file so an interrupted fallback cannot
                    # leave an apparently completed, truncated immutable input.
                    staging=destination.with_name('.'+destination.name+'.copy')
                    shutil.copyfile(original,staging)
                    os.replace(staging,destination)


def validate_measurement(folder, source, tasks, workers):
    folder=Path(folder)
    value=read(folder/'receipt.json')
    ids=[t['id'] for t in tasks]
    if (not value.get('passed') or value.get('source_id')!=source or value.get('workers')!=workers
            or value.get('logical_task_ids')!=ids or value.get('finished')!=len(tasks)
            or value.get('count_as_labels') is not False or set(value.get('outcomes',{}))!=set(ids)
            or set(value.get('result_refs',{}))!=set(ids)):
        raise ValueError('probe measurement source/task/worker mismatch')
    samples=value.get('resources')
    if not samples or any(s['available_memory']<_RESERVE or s['free_disk']<_RESERVE for s in samples):
        raise ValueError('unsafe probe resource measurement')
    for task in tasks:
        completed,_=inspect_task(folder,source,task)
        if completed is None:
            raise ValueError('probe receipt has no completed task result')
        row,path=completed
        ref=value['result_refs'][task['id']]
        if str(path.relative_to(folder))!=ref['path'] or sha(path)!=ref['sha256']:
            raise ValueError('probe receipt/result checksum mismatch')
        if {k:row[k] for k in OUTCOME_FIELDS}!=value['outcomes'][task['id']]:
            raise ValueError('probe receipt/trace mismatch')
    return value


def _measure(directory, folder, source, tasks, workers, *, reverse=False):
    resume_local_pause(directory,folder)
    started_path=folder/'started.json'
    if started_path.exists():
        initial=read(started_path)
        if initial['source_id']!=source or initial['logical_task_ids']!=[t['id'] for t in tasks]:
            raise ValueError('probe schedule changed during resume')
    else:
        initial=dict(source_id=source,logical_task_ids=[t['id'] for t in tasks],at=time.time())
        atomic(started_path,initial,immutable=True)
    samples=[check_resources(directory,folder)]
    outputs={}
    refs={}
    queue=list(reversed(tasks)) if reverse else list(tasks)
    pending={}
    failure=None
    def completed(task,row,path):
        outputs[task['id']]={k:row[k] for k in OUTCOME_FIELDS}
        refs[task['id']]=dict(path=str(path.relative_to(folder)),sha256=sha(path))
        (folder/'private/checkpoints'/f"{task['id']}.json.gz").unlink(missing_ok=True)
    with futures.ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn'),
            initializer=initialize,initargs=(str(folder),source)) as pool:
        def fill():
            while queue and len(pending)<workers and failure is None:
                samples.append(check_resources(directory,folder))
                task=queue.pop(0)
                saved,attempt=begin_attempt(folder,source,task)
                if saved:
                    completed(task,*saved)
                else:
                    pending[pool.submit(execute,attempt)]=attempt
        try:
            fill()
        except Exception as error:
            failure=error
            if not isinstance(error,ResourceReserveError):
                stop(directory,'technical',error)
                stop(folder,'technical',error)
        last_poll=time.monotonic()
        while pending:
            done,_=futures.wait(pending,timeout=5,return_when=futures.FIRST_COMPLETED)
            if failure is None and (time.monotonic()-last_poll>=5 or (directory/'STOP').exists()):
                try:
                    samples.append(check_resources(directory,folder))
                except Exception as error:
                    failure=error
                last_poll=time.monotonic()
            for future in done:
                task=pending.pop(future)
                try:
                    returned=future.result()
                    path=Path(returned['path'])
                    if path!=result_path(folder,task,task['attempt']):
                        raise ValueError('probe worker returned another attempt')
                    row=validate_result(folder,source,task,path)
                    if row['status'] in _TERMINAL:
                        completed(task,row,path)
                    elif row['status']=='interrupted' or transient_error(row.get('error','')):
                        if failure is None:
                            queue.append(task)
                    else:
                        raise ValueError('probe technical failure: '+str(row.get('error')))
                except Exception as error:
                    _record_failure(folder,source,task,task['attempt'],error)
                    if transient_error(error) and failure is None:
                        queue.append(task)
                    else:
                        failure=failure or error
                        if not isinstance(error,ResourceReserveError):
                            stop(directory,'technical',error)
                            stop(folder,'technical',error)
            if failure is None:
                try:
                    fill()
                except Exception as error:
                    failure=error
                    if not isinstance(error,ResourceReserveError):
                        stop(directory,'technical',error)
                        stop(folder,'technical',error)
    if failure is not None:
        atomic(folder/'stage-failures'/f'{time.time_ns()}.json',dict(source_id=source,
               error=repr(failure),completed=sorted(outputs),resources=samples,at=time.time()),immutable=True)
        raise failure
    samples.append(check_resources(directory,folder))
    if len(outputs)!=len(tasks):
        raise ValueError('probe task coverage incomplete')
    elapsed=time.time()-initial['at']
    measurement=dict(workers=workers,finished=len(tasks),elapsed_seconds=elapsed,
        rollouts_per_second=len(tasks)/elapsed,resources=samples,passed=True,
        source_id=source,logical_task_ids=[t['id'] for t in tasks],outcomes=outputs,
        result_refs=refs,count_as_labels=False)
    atomic(folder/'receipt.json',measurement,immutable=True)
    return measurement


def run(directory, *, worker_counts=(32,16,48), task_count=96):
    directory=Path(directory)
    source=verify(directory)
    ledger=Ledger(directory,source)
    try:
        all_jobs=[dict(row) for row in ledger.db.execute('SELECT * FROM jobs WHERE replicate=0 ORDER BY observation_id,action_id')]
    finally:
        ledger.close()
    if task_count<2 or len(all_jobs)<task_count:
        raise ValueError('insufficient real pilot candidates for worker comparison')
    indices=sorted({int(i*(len(all_jobs)-1)/(task_count-1)) for i in range(task_count)})
    tasks=[all_jobs[i] for i in indices]
    baselines=None
    measurements=[]
    for index,workers in enumerate(worker_counts):
        folder=directory/'benchmarks'/f'workers-{workers}'
        propagate_stop(directory,folder)
        materialize_roots(directory,folder)
        if (folder/'receipt.json').exists():
            measurement=validate_measurement(folder,source,tasks,workers)
        else:
            measurement=_measure(directory,folder,source,tasks,workers,reverse=bool(index%2))
        atomic(directory/'measurements'/f'benchmark-workers-{workers}.json',measurement,immutable=True)
        outputs=measurement['outcomes']
        if baselines is None:
            baselines=outputs
        elif outputs!=baselines:
            raise ValueError('candidate order or worker count changed seeded outcome/trace/root')
        measurements.append({k:v for k,v in measurement.items() if k not in ('outcomes','resources')})
    result=dict(passed=True,source_id=source,logical_tasks=len(tasks),executions=len(tasks)*len(worker_counts),
                tested_workers=list(worker_counts),measurements=measurements)
    atomic(directory/'invariance.json',result,immutable=True)
    return result
