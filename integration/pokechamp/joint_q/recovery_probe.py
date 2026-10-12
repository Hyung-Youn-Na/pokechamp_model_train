"""Interrupt an owned real rollout at a committed boundary and resume its RNG."""
from __future__ import annotations
import multiprocessing
import os
from pathlib import Path
import signal
import time
from .storage import atomic, read, sha
from .manifest import verify
from .ledger import Ledger
from . import rollout
from .benchmark import (OUTCOME_FIELDS, _record_failure, begin_attempt, check_resources,
    inspect_task, materialize_roots, propagate_stop, result_path, resume_local_pause,
    task_identity, validate_measurement, validate_result)
from .pipeline import transient_error


def _child(directory, source, task, control=None, minimum_steps=0):
    os.setsid()
    rollout.initialize(directory,source)
    if control is not None:
        original=rollout.atomic
        checkpoint=Path(directory)/'private/checkpoints'/f"{task['id']}.json.gz"
        def committed(path, value, **kwargs):
            result=original(path,value,**kwargs)
            if Path(path)==checkpoint and len(value['trace'])>=minimum_steps:
                # Hold only after the exact ordinary checkpoint is committed;
                # this hook consumes no actor or simulator RNG.
                control.send(dict(checkpoint_steps=len(value['trace']),checkpoint_sha256=sha(path)))
                try:
                    control.recv()
                except EOFError:
                    rollout.close()
                    os._exit(125)
            return result
        rollout.atomic=committed
    try:
        rollout.execute(task)
    finally:
        rollout.close()


def _kill_owned(process):
    if process.is_alive():
        try:
            if os.getpgid(process.pid)==process.pid:
                os.killpg(process.pid,signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
    process.join(10)
    if process.is_alive():
        raise RuntimeError('owned recovery worker did not stop')


def _execute(directory, folder, source, task, reference, *, interrupt=False):
    samples=[check_resources(directory,folder)]
    context=multiprocessing.get_context('spawn')
    parent,child=context.Pipe() if interrupt else (None,None)
    process=context.Process(target=_child,args=(str(folder),source,task,child,
        20 if len(reference['trace'])>20 else 0))
    process.start()
    if child is not None:
        child.close()
    started=last_poll=time.monotonic()
    try:
        while process.is_alive():
            if parent is not None and parent.poll(.05):
                marker=parent.recv()
                _kill_owned(process)
                cp=folder/'private/checkpoints'/f"{task['id']}.json.gz"
                if sha(cp)!=marker['checkpoint_sha256']:
                    raise ValueError('held recovery checkpoint changed before interruption')
                saved=folder/'private'/f"interruption-checkpoint-a{task['attempt']}.json.gz"
                atomic(saved,read(cp),immutable=True)
                evidence=dict(identity=task_identity(task,source),attempt=task['attempt'],
                    killed_pid=process.pid,checkpoint_steps=marker['checkpoint_steps'],
                    checkpoint_ref=dict(path=str(saved.relative_to(folder)),sha256=sha(saved)),
                    resources=samples,at=time.time())
                atomic(folder/'interruption.json',evidence,immutable=True)
                _record_failure(folder,source,task,task['attempt'],
                                'controlled interruption at committed checkpoint',interrupted=True)
                return None,evidence,samples
            if time.monotonic()-last_poll>=5 or (directory/'STOP').exists():
                samples.append(check_resources(directory,folder))
                last_poll=time.monotonic()
            if interrupt and time.monotonic()-started>=120:
                raise ValueError('did not reach a committed checkpoint within 120 seconds')
            if parent is None:
                process.join(.1)
        process.join()
        path=result_path(folder,task,task['attempt'])
        if not path.exists():
            raise RuntimeError('recovery worker exited before a response')
        row=validate_result(folder,source,task,path)
        if row['status']=='error' and not transient_error(row.get('error','')):
            raise ValueError('recovery technical failure: '+str(row.get('error')))
        if interrupt and row['status'] in {'win','draw','loss'}:
            raise ValueError('recovery worker completed without the required controlled interruption')
        return (row,path),None,samples
    finally:
        if process.is_alive():
            # Resource pauses first allow the worker to save at its next boundary.
            process.join(5 if (folder/'STOP').exists() else 0)
            _kill_owned(process)
        if parent is not None:
            parent.close()


def _interruption(folder, source, task, reference):
    evidence=read(folder/'interruption.json')
    if evidence['identity']!=task_identity(task,source):
        raise ValueError('recovery interruption source/task mismatch')
    ref=evidence['checkpoint_ref']
    path=folder/ref['path']
    if sha(path)!=ref['sha256']:
        raise ValueError('recovery interruption checkpoint changed')
    checkpoint=read(path)
    identity=task_identity(task,source)
    if any(checkpoint[k]!=identity[k] for k in ('job_id','source_id','root_sha256','seeds')):
        raise ValueError('recovery checkpoint source/root/seed mismatch')
    steps=evidence['checkpoint_steps']
    if checkpoint['trace']!=reference['trace'][:steps] or len(checkpoint['trace'])!=steps:
        raise ValueError('recovery checkpoint diverged from the baseline prefix')
    return evidence


def _compare(reference, resumed):
    if not resumed.get('resumed') or any(reference[k]!=resumed.get(k) for k in OUTCOME_FIELDS):
        raise ValueError('same-RNG checkpoint resume changed trajectory or terminal result')


def run(directory, *, baseline_workers=32):
    directory=Path(directory)
    source=verify(directory)
    benchmark=directory/f'benchmarks/workers-{baseline_workers}'
    baseline=read(benchmark/'receipt.json')
    ledger=Ledger(directory,source)
    try:
        tasks=[dict(ledger.db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
               for jid in baseline['logical_task_ids']]
    finally:
        ledger.close()
    validate_measurement(benchmark,source,tasks,baseline_workers)
    references=[(task,inspect_task(benchmark,source,task)[0]) for task in tasks]
    task,(reference,reference_path)=max(references,key=lambda pair:len(pair[1][0]['trace']))
    folder=directory/'verification/interrupted-rollout'
    propagate_stop(directory,folder)
    materialize_roots(directory,folder)
    resume_local_pause(directory,folder)
    target=directory/'recovery-verification.json'
    reference_ref=dict(path=str(reference_path.relative_to(directory)),sha256=sha(reference_path))
    if target.exists():
        receipt=read(target)
        if (not receipt.get('passed') or receipt.get('source_id')!=source
                or receipt.get('job_id')!=task['id'] or receipt.get('baseline_workers')!=baseline_workers
                or receipt.get('reference_ref')!=reference_ref):
            raise ValueError('recovery receipt source/reference mismatch')
        evidence=_interruption(folder,source,task,reference)
        ref=receipt['result_ref']
        resumed=validate_result(folder,source,task,folder/ref['path'],checksum=ref['sha256'])
        _compare(reference,resumed)
        expected=dict(killed_pid=evidence['killed_pid'],checkpoint_steps=evidence['checkpoint_steps'],
            full_steps=len(reference['trace']),compared_fields=list(OUTCOME_FIELDS),
            reference_trace_sha256=reference['trace_sha256'],resumed_trace_sha256=resumed['trace_sha256'])
        if any(receipt.get(k)!=v for k,v in expected.items()):
            raise ValueError('recovery receipt trajectory mismatch')
        if not receipt.get('resources') or any(min(s['available_memory'],s['free_disk'])<24*1024**3
                                             for s in receipt['resources']):
            raise ValueError('unsafe recovery resource measurement')
        return receipt
    samples=[]
    while not (folder/'interruption.json').exists():
        propagate_stop(directory,folder)
        completed,attempt=begin_attempt(folder,source,task)
        if completed:
            raise ValueError('recovery result has no controlled interruption evidence')
        try:
            _,evidence,measured=_execute(directory,folder,source,attempt,reference,interrupt=True)
            samples.extend(measured)
        except Exception as error:
            _record_failure(folder,source,attempt,attempt['attempt'],error,
                            interrupted=(folder/'STOP').exists())
            if (folder/'STOP').exists() or not transient_error(error):
                raise
    evidence=_interruption(folder,source,task,reference)
    samples=evidence['resources']+samples
    while True:
        propagate_stop(directory,folder)
        completed,attempt=begin_attempt(folder,source,task)
        if completed:
            resumed,path=completed
            break
        try:
            result,_,measured=_execute(directory,folder,source,attempt,reference)
            samples.extend(measured)
            resumed,path=result
            if resumed['status'] in {'win','draw','loss'}:
                break
        except Exception as error:
            _record_failure(folder,source,attempt,attempt['attempt'],error,
                            interrupted=(folder/'STOP').exists())
            if (folder/'STOP').exists() or not transient_error(error):
                raise
    _compare(reference,resumed)
    samples.append(check_resources(directory,folder))
    result=dict(passed=True,source_id=source,job_id=task['id'],baseline_workers=baseline_workers,
        killed_pid=evidence['killed_pid'],checkpoint_steps=evidence['checkpoint_steps'],
        full_steps=len(reference['trace']),compared_fields=list(OUTCOME_FIELDS),
        reference_trace_sha256=reference['trace_sha256'],resumed_trace_sha256=resumed['trace_sha256'],
        reference_ref=reference_ref,result_ref=dict(path=str(path.relative_to(folder)),sha256=sha(path)),
        resources=samples,count_as_labels=False)
    atomic(target,result,immutable=True)
    return result
