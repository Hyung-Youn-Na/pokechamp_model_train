"""Process-reused rollouts with immutable roots and same-RNG boundary checkpoints."""
from __future__ import annotations
import atexit
import copy
from functools import lru_cache
import json
import os
from pathlib import Path
import signal
import time
import traceback
from .engine import (Simulator, feed, pack_actors, unpack_actors, boundary_signature,
                     validate_actor_policies, validate_record_policy, decision_audits)
from .actor import normalize_policy
from .storage import atomic, digest, read, sha

_SIM=None
_DIRECTORY=None
_SOURCE=None


def initialize(directory,source):
    global _DIRECTORY,_SOURCE
    _DIRECTORY=Path(directory)
    _SOURCE=source
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key]='1'
    atexit.register(close)


def close():
    global _SIM
    if _SIM is not None:
        _SIM.close()
        _SIM=None


def simulator():
    global _SIM
    if _SIM is None or _SIM.closed:
        _SIM=Simulator(timeout=120)
    return _SIM


@lru_cache(maxsize=2)
def get_root(path,checksum):
    full=_DIRECTORY/path
    if sha(full)!=checksum:
        raise ValueError('immutable root checksum mismatch')
    return read(full)


def execute(task):
    started=time.time()
    jid,attempt=task['id'],task['attempt']
    result=dict(job_id=jid,attempt=attempt,observation_id=task['observation_id'],action_id=task['action_id'],
                replicate=task['replicate'],source_id=_SOURCE,root_sha256=task['root_sha256'],
                seeds=json.loads(task['seeds']),status='error',terminal=False,resumed=False)
    cp=_DIRECTORY/'private/checkpoints'/f'{jid}.json.gz'
    path=_DIRECTORY/'private/results'/f'{jid}-a{attempt}.json.gz'
    trace=[]
    actors=None
    response=None
    cursor=None
    root=None
    choices=None
    def save_checkpoint():
        if response is None or response['ended']:
            return
        atomic(cp,dict(job_id=jid,source_id=_SOURCE,root_sha256=task['root_sha256'],
            seeds=result['seeds'],policy=result['policy'],simulator=sim.snapshot(),actors=pack_actors(_DIRECTORY,actors),
            cursors=cursor,trace=trace,first_pending=not trace,boundary=boundary_signature(response)))
    try:
        root=get_root(task['root_path'],task['root_sha256'])
        result['policy']=normalize_policy(root.get('policy'))
        sim=simulator()
        if cp.exists():
            checkpoint=read(cp)
            if any(checkpoint[k]!=result[k] for k in ('job_id','source_id','root_sha256','seeds')):
                raise ValueError('checkpoint version/root/seed mismatch')
            validate_record_policy(checkpoint,result['policy'])
            actors=unpack_actors(_DIRECTORY,checkpoint['actors'])
            validate_actor_policies(actors,result['policy'])
            cursor=dict(checkpoint['cursors'])
            response=sim.restore(checkpoint['simulator'])
            trace=checkpoint['trace']
            if bool(checkpoint['first_pending'])!=(not trace):
                raise ValueError('checkpoint forced-candidate position mismatch')
            if trace:
                result['root_opponent_choice']=trace[0]['choices'].get('p1')
            if boundary_signature(response)!=checkpoint['boundary']:
                raise ValueError('checkpoint boundary mismatch')
            result['resumed']=True
        else:
            actors=unpack_actors(_DIRECTORY,root['actors'])
            validate_actor_policies(actors,result['policy'])
            cursor=dict(root['cursors'])
            response=sim.restore(root['simulator'])
            if boundary_signature(response)!=root['boundary']:
                raise ValueError('restored branch root differs')
            for side,actor in actors.items():
                actor.reseed(result['seeds']['actors'][side])
            sim.reseed(result['seeds']['simulator'])
            save_checkpoint()
        result['start_boundary']=root['boundary']
        while not response['ended']:
            if (_DIRECTORY/'STOP').exists():
                save_checkpoint()
                result['status']='interrupted'
                result['error']='cooperative stop at decision boundary'
                break
            if not response['needs_choice']:
                raise ValueError('nonterminal rollout has no choice')
            # Root forced action must not call our continuation policy first.
            choices={s:a.choose() for s,a in actors.items() if s in response['needs_choice'] and (trace or s!='p2')}
            if not trace:
                choices['p2']=next(a['command'] for a in root['actions'] if a['action_id']==task['action_id'])
                result['root_opponent_choice']=choices.get('p1')
            audits=decision_audits(actors,choices,forced_side='p2' if not trace else None,compact=True)
            before_turn=response['turn']
            response=sim.step(choices)
            feed(response,actors,None,cursor)
            step=dict(turn=before_turn,choices=choices)
            if audits:
                step['policy_audits']=audits
            trace.append(step)
            if len(trace)%20==0 and not response['ended']:
                save_checkpoint()
        if response['ended']:
            winner=response['winner']
            if winner not in ('',actors['p1'].username,actors['p2'].username):
                raise ValueError('unknown terminal winner')
            status='draw' if not winner else 'win' if winner==actors['p2'].username else 'loss'
            result.update(status=status,score={'win':1,'draw':.5,'loss':0}[status],terminal=True,
                terminal_turn=response['turn'],winner=winner,public_log=response['public_log'],
                final_boundary=boundary_signature(response))
    except BaseException as error:
        # The previous checkpoint is always a fully applied, actor-fed boundary.
        # Never save a partly consumed failed transition. Replay its exact RNG.
        result.update(status='error',error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
        close()
    result.update(trace=trace,trace_sha256=digest(trace),elapsed_seconds=time.time()-started,
                  checkpoint_path=str(cp.relative_to(_DIRECTORY)) if cp.exists() else None)
    atomic(path,result,immutable=True)
    return dict(job_id=jid,attempt=attempt,path=str(path),status=result['status'],
                elapsed_seconds=result['elapsed_seconds'])
