"""Synthetic durable probe tests; no collection games or rollout RNG are consumed."""
from __future__ import annotations
import concurrent.futures
import json
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from integration.pokechamp.joint_q import benchmark as bm, recovery_probe as recovery
from integration.pokechamp.joint_q.pipeline import ResourceReserveError
from integration.pokechamp.joint_q.storage import atomic, digest, read, sha

SOURCE='fixed-source'
SAFE=dict(available_memory=32*1024**3,free_disk=40*1024**3,at=1)


@pytest.fixture
def probe(tmp_path,monkeypatch):
    directory=tmp_path/'experiment'
    (directory/'private/roots').mkdir(parents=True)
    (directory/'private/blobs').mkdir()
    tasks=[]
    for index in range(2):
        root=dict(boundary={'turn':index+1},actions=[dict(action_id='move',command='move 1')])
        path=directory/'private/roots'/f'root-{index}.json.gz'
        atomic(path,root,immutable=True)
        tasks.append(dict(id=f'job-{index}',observation_id=f'observation-{index}',action_id='move',
            replicate=0,source_id=SOURCE,root_path=str(path.relative_to(directory)),root_sha256=sha(path),
            seeds=json.dumps(dict(simulator=[1,2,3,4],actors=dict(p1=11,p2=22)))))
    class DB:
        def execute(self,query,params=None):
            if params:
                return SimpleNamespace(fetchone=lambda:next(t for t in tasks if t['id']==params[0]))
            return tasks
    class Ledger:
        def __init__(self,*args): self.db=DB()
        def close(self): pass
    for module in (bm,recovery):
        monkeypatch.setattr(module,'verify',lambda _:SOURCE)
        monkeypatch.setattr(module,'Ledger',Ledger)
    monkeypatch.setattr(bm,'resources',lambda _:dict(SAFE))
    monkeypatch.setattr(bm,'admission',lambda _:None)
    return directory,tasks


def write_result(folder,task,attempt=1,*,status='win',error=None,resumed=False):
    row={k:v for k,v in bm.task_identity(task,SOURCE).items() if k!='root_path'}
    root=read(Path(folder)/task['root_path'])
    trace=[dict(turn=root['boundary']['turn'],choices=dict(p1='move 2',p2='move 1'))]
    row.update(attempt=attempt,status=status,terminal=status in {'win','draw','loss'},resumed=resumed,
        trace=trace,trace_sha256=digest(trace),start_boundary=root['boundary'],
        final_boundary={'turn':99},elapsed_seconds=1)
    if row['terminal']:
        row['score']={'win':1,'draw':.5,'loss':0}[status]
    if error is not None:
        row['error']=error
    path=bm.result_path(folder,task,attempt)
    atomic(path,row,immutable=True)
    return row,path


def fake_pool(monkeypatch,behavior):
    calls=[]
    class Pool:
        def __init__(self,*,max_workers,initializer,initargs,**kwargs):
            self.folder=Path(initargs[0])
            self.workers=max_workers
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def submit(self,function,task):
            calls.append((self.workers,dict(task)))
            future=concurrent.futures.Future()
            try:
                row,path=behavior(self.folder,task)
                future.set_result(dict(path=str(path),status=row['status']))
            except Exception as error:
                future.set_exception(error)
            return future
    monkeypatch.setattr(bm.futures,'ProcessPoolExecutor',Pool)
    return calls


def test_partial_stage_reuses_completion_and_retries_same_task_seed(probe,monkeypatch):
    directory,tasks=probe
    folder=directory/'benchmarks/workers-1'
    bm.materialize_roots(directory,folder)
    bm.begin_attempt(folder,SOURCE,tasks[0])
    _,first=write_result(folder,tasks[0])
    first_hash=sha(first)
    bm.begin_attempt(folder,SOURCE,tasks[1])
    write_result(folder,tasks[1],status='error',error='simulator timed out')
    calls=fake_pool(monkeypatch,lambda folder,task:write_result(folder,task,task['attempt']))
    result=bm.run(directory,worker_counts=(1,2),task_count=2)
    assert [(workers,t['id'],t['attempt']) for workers,t in calls]==[
        (1,'job-1',2),(2,'job-1',1),(2,'job-0',1)]
    assert all(t['seeds']==tasks[int(t['id'][-1])]['seeds'] for _,t in calls)
    assert sha(first)==first_hash
    assert result['passed'] and result['logical_tasks']==2
    assert bm.run(directory,worker_counts=(1,2),task_count=2)==result
    assert len(calls)==3
    assert not list(directory.rglob('*.copy'))
    assert not any(path.is_symlink() for path in directory.rglob('*'))


def test_abandoned_attempts_advance_monotonically_and_stop_at_three(probe):
    directory,tasks=probe
    folder=directory/'probe'
    bm.materialize_roots(directory,folder)
    for number in (1,2,3):
        completed,task=bm.begin_attempt(folder,SOURCE,tasks[0])
        assert completed is None and task['attempt']==number
        assert task['seeds']==tasks[0]['seeds']
    with pytest.raises(RuntimeError,match='three attempts'):
        bm.begin_attempt(folder,SOURCE,tasks[0])
    assert read(folder/'probe-attempts/job-0/attempt-1-finish.json')['interrupted']


def test_nontransient_failure_is_not_retried(probe):
    directory,tasks=probe
    folder=directory/'probe'
    bm.materialize_roots(directory,folder)
    bm.begin_attempt(folder,SOURCE,tasks[0])
    write_result(folder,tasks[0],status='error',error='ValueError: wrong action boundary')
    with pytest.raises(ValueError,match='versioned recovery'):
        bm.begin_attempt(folder,SOURCE,tasks[0])
    assert not (folder/'probe-attempts/job-0/attempt-2-start.json').exists()


@pytest.mark.parametrize('field,value',[
    ('source_id','another-source'),('root_sha256','changed'),
    ('seeds',{'simulator':[9,9,9,9]}),('trace_sha256','changed'),('terminal',False),
])
def test_result_reuse_validates_source_root_seed_trace_and_terminal(probe,field,value):
    directory,tasks=probe
    folder=directory/'probe'
    bm.materialize_roots(directory,folder)
    row,path=write_result(folder,tasks[0])
    row[field]=value
    atomic(path,row)
    with pytest.raises(ValueError):
        bm.inspect_task(folder,SOURCE,tasks[0])


@pytest.mark.parametrize('change',['source','hash','resources','outcome'])
def test_measurement_receipt_rejects_stale_or_unsafe_evidence(probe,monkeypatch,change):
    directory,tasks=probe
    fake_pool(monkeypatch,lambda folder,task:write_result(folder,task,task['attempt']))
    bm.run(directory,worker_counts=(1,),task_count=2)
    folder=directory/'benchmarks/workers-1'
    value=read(folder/'receipt.json')
    if change=='source': value['source_id']='stale'
    elif change=='hash': value['result_refs']['job-0']['sha256']='changed'
    elif change=='resources': value['resources'][0]['free_disk']=1
    else: value['outcomes']['job-0']['trace_sha256']='changed'
    atomic(folder/'receipt.json',value)
    with pytest.raises(ValueError):
        bm.run(directory,worker_counts=(1,),task_count=2)


def test_resource_stop_propagates_and_only_resumes_after_parent_cleared(probe,monkeypatch):
    directory,_=probe
    folder=directory/'probe'
    monkeypatch.setattr(bm,'resources',lambda _:dict(SAFE,available_memory=1))
    with pytest.raises(ResourceReserveError): bm.check_resources(directory,folder)
    assert read(directory/'STOP')['reason']==read(folder/'STOP')['reason']=='resources'
    with pytest.raises(ResourceReserveError): bm.resume_local_pause(directory,folder)
    (directory/'STOP').unlink()
    bm.resume_local_pause(directory,folder)
    assert not (folder/'STOP').exists()
    assert list((folder/'resource-pauses').glob('resumed-*.json'))


def test_running_measurement_polls_resources_and_retains_interrupted_result(probe,monkeypatch):
    directory,tasks=probe
    folder=directory/'probe'
    bm.materialize_roots(directory,folder)
    fake_pool(monkeypatch,lambda folder,task:write_result(folder,task,task['attempt'],status='interrupted'))
    measurements=iter([dict(SAFE),dict(SAFE),dict(SAFE,free_disk=1)])
    monkeypatch.setattr(bm,'resources',lambda _:next(measurements))
    first=[True]
    def wait(pending,**kwargs):
        if first.pop() if first else False: return set(),set(pending)
        return set(pending),set()
    monkeypatch.setattr(bm.futures,'wait',wait)
    clock=iter([0,6,6])
    monkeypatch.setattr(bm,'time',SimpleNamespace(time=time.time,time_ns=time.time_ns,monotonic=lambda:next(clock)))
    with pytest.raises(ResourceReserveError):
        bm._measure(directory,folder,SOURCE,tasks[:1],1)
    assert read(folder/'STOP')['reason']=='resources'
    assert bm.result_path(folder,tasks[0],1).exists()
    assert not (folder/'receipt.json').exists()
    assert not (folder/'probe-attempts/job-0/attempt-2-start.json').exists()


def test_materialized_input_tree_supports_partial_rerun_and_copy_fallback(probe,monkeypatch):
    directory,_=probe
    folder=directory/'probe'
    bm.materialize_roots(directory,folder)
    original=next((directory/'private/roots').iterdir())
    copied=folder/'private/roots'/original.name
    assert original.stat().st_ino==copied.stat().st_ino
    extra=directory/'private/blobs'/'extra'
    extra.write_bytes(b'new immutable blob')
    def no_link(*args): raise OSError('cross-device link')
    monkeypatch.setattr(bm.os,'link',no_link)
    bm.materialize_roots(directory,folder)
    assert (folder/'private/blobs/extra').read_bytes()==extra.read_bytes()
    bm.materialize_roots(directory,folder)
    assert not any(path.is_symlink() for path in folder.rglob('*'))


def completed_recovery(probe,monkeypatch):
    directory,tasks=probe
    fake_pool(monkeypatch,lambda folder,task:write_result(folder,task,task['attempt']))
    bm.run(directory,worker_counts=(1,),task_count=2)
    folder=directory/'verification/interrupted-rollout'
    bm.materialize_roots(directory,folder)
    task=tasks[0]
    bm.begin_attempt(folder,SOURCE,task)
    checkpoint={k:v for k,v in bm.task_identity(task,SOURCE).items()
                if k in ('job_id','source_id','root_sha256','seeds')}
    checkpoint['trace']=[]
    cp=folder/'private/interruption-checkpoint-a1.json.gz'
    atomic(cp,checkpoint,immutable=True)
    evidence=dict(identity=bm.task_identity(task,SOURCE),attempt=1,killed_pid=123,
        checkpoint_steps=0,checkpoint_ref=dict(path=str(cp.relative_to(folder)),sha256=sha(cp)),
        resources=[dict(SAFE)],at=1)
    atomic(folder/'interruption.json',evidence,immutable=True)
    bm._record_failure(folder,SOURCE,task,1,'controlled interruption',interrupted=True)
    _,attempt=bm.begin_attempt(folder,SOURCE,task)
    write_result(folder,task,attempt['attempt'],resumed=True)
    def no_execute(*args,**kwargs): raise AssertionError('completed task must not execute again')
    monkeypatch.setattr(recovery,'_execute',no_execute)
    return directory,folder


def test_recovery_reuses_completed_attempt_and_receipt_without_new_process(probe,monkeypatch):
    directory,_=completed_recovery(probe,monkeypatch)
    result=recovery.run(directory,baseline_workers=1)
    assert result['passed'] and result['checkpoint_steps']==0
    assert result['result_ref']['path'].endswith('job-0-a2.json.gz')
    assert recovery.run(directory,baseline_workers=1)==result


@pytest.mark.parametrize('change',['source','result','trace','checkpoint'])
def test_recovery_receipt_reuse_rejects_changed_evidence(probe,monkeypatch,change):
    directory,folder=completed_recovery(probe,monkeypatch)
    value=recovery.run(directory,baseline_workers=1)
    if change=='source': value['source_id']='stale'
    elif change=='result': value['result_ref']['sha256']='changed'
    elif change=='trace': value['resumed_trace_sha256']='changed'
    else:
        cp=folder/'private/interruption-checkpoint-a1.json.gz'
        checkpoint=read(cp)
        checkpoint['seeds']={'wrong':True}
        atomic(cp,checkpoint)
    atomic(directory/'recovery-verification.json',value)
    with pytest.raises(ValueError): recovery.run(directory,baseline_workers=1)
