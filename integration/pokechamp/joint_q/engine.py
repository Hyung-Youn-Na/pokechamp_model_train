"""Pinned simulator and Abyssal lifecycle; all objects here are private evidence."""
from __future__ import annotations
import base64
import copy
from functools import lru_cache
import gzip
import hashlib
import json
import io
import pickle
import re
from pathlib import Path
from .storage import atomic, digest, read, sha
from ..branch_rollouts.policy import _LIFECYCLE_FIELDS
from .actor import Actor, BASE_POLICY_ID, normalize_policy
from ..branch_rollouts.simulator import Simulator
from ..branch_rollouts.common import gameplay_lines

WARNING=re.compile(r"^\|bigerror\|You will auto-tie if the battle doesn't end in (\d+) (turns?) \(on turn 1000\)\.$")


def regular_warning(line, turn):
    match=WARNING.fullmatch(line)
    return bool(match and int(match[1])==1000-turn and match[2]==('turn' if turn==999 else 'turns') and
                (500<=turn<1000 and (turn%100==0 or turn>=900 and turn%10==0 or turn>=990)))


def feed(response, actors, histories, cursors, follower=None):
    for side, actor in actors.items():
        logs=response['actor_logs'][side]
        old=cursors.get(side,0)
        if old>len(logs):
            raise ValueError('simulator log regressed')
        new=logs[old:]
        safe=[line for line in new if not regular_warning(line,response['turn'])]
        actor.feed(safe)
        if follower is not None and side=='p2':
            follower.feed(safe)
        if histories is not None:
            histories[side].extend(new)
        cursors[side]=len(logs)
    requests={}
    for event in response['messages']:
        if event['type']!='sideupdate':
            continue
        side,payload=event['data'].split('\n',1)
        for line in payload.splitlines():
            if line.startswith(('|error|','|bigerror|')) and not regular_warning(line,response['turn']):
                raise ValueError('simulator rejected action: '+line)
            if line.startswith('|request|'):
                requests[side]=line
    for side,line in requests.items():
        actors[side].feed([line])
        if follower is not None and side=='p2':
            follower.feed([line])
        if histories is not None:
            histories[side].append('|request|'+json.dumps(actors[side].request,separators=(',',':')))
    if response.get('errors'):
        raise ValueError('simulator error: '+str(response['errors']))


def put_blob(directory, raw):
    identity=hashlib.sha256(raw).hexdigest()
    path=Path(directory)/'private/blobs'/f'{identity}.json.gz'
    if not path.exists():
        atomic(path,dict(sha256=identity,pickle=base64.b64encode(raw).decode()),immutable=True)
    return identity


@lru_cache(maxsize=24)
def _blob(directory, identity):
    row=read(Path(directory)/'private/blobs'/f'{identity}.json.gz')
    raw=base64.b64decode(row['pickle'])
    if row['sha256']!=identity or hashlib.sha256(raw).hexdigest()!=identity:
        raise ValueError('actor policy blob corrupted')
    return raw


def pack_actor(directory, actor):
    from poke_env.data.gen_data import GenData
    from poke_env.environment.pokemon import Pokemon
    from poke_env.environment.move import Move
    if hasattr(actor,'validate_policy'):
        actor.validate_policy()
    policy={k:v for k,v in actor.player.__dict__.items() if k not in _LIFECYCLE_FIELDS}
    state=dict(version=2,side=actor.side,username=actor.username,battle=actor.battle,
               request=actor.request,rqid=actor._rqid,python_rng=actor._python_rng,
               numpy_rng=actor._numpy_rng,policy=policy)
    metadata=normalize_policy(getattr(actor,'policy_metadata',None))
    if metadata['policy_id']!=BASE_POLICY_ID:
        state.update(version=3,policy_metadata=metadata,
                     last_decision_audit=getattr(actor,'_last_decision_audit',None))
    cache_ids={id(policy[k]) for k in ('gen','move_effect','ability_effect','item_effect') if k in policy}
    references={}
    class Writer(pickle.Pickler):
        def persistent_id(self, obj):
            if isinstance(obj,Pokemon):
                cache_ids.add(id(obj._sets))
            if isinstance(obj,Move):
                cache_ids.add(id(obj._moves_dict))
            if id(obj) in cache_ids or isinstance(obj,GenData):
                if id(obj) not in references:
                    blob=getattr(obj,'_joint_blob_id',None) or put_blob(directory,pickle.dumps(obj,protocol=pickle.HIGHEST_PROTOCOL))
                    references[id(obj)]=(blob,len(references))
                return references[id(obj)]
            return None
    buffer=io.BytesIO()
    Writer(buffer,protocol=pickle.HIGHEST_PROTOCOL).dump(state)
    packed=dict(version=state['version'],pickle=base64.b64encode(buffer.getvalue()).decode())
    if state['version']==3:
        packed['policy_metadata']=metadata
    return packed


def unpack_actor(directory, value):
    if value['version'] not in (2,3):
        raise ValueError('actor version mismatch')
    if value['version']==3 and 'policy_metadata' not in value:
        raise ValueError('actor envelope omitted policy metadata')
    metadata=normalize_policy(value['policy_metadata'] if value['version']==3 else None)
    references={}
    class Reader(pickle.Unpickler):
        def persistent_load(self, identity):
            identity=tuple(identity)
            if identity not in references:
                from .immutable import lookup
                references[identity]=lookup(str(directory),identity[0])
            return references[identity]
    state=Reader(io.BytesIO(base64.b64decode(value['pickle']))).load()
    if state['version']!=value['version']:
        raise ValueError('actor envelope/snapshot version mismatch')
    if value['version']==3 and normalize_policy(state['policy_metadata'])!=metadata:
        raise ValueError('actor envelope/snapshot policy mismatch')
    a=object.__new__(Actor)
    a._policy_metadata=metadata
    a.side,a.username=state['side'],state['username']
    a.battle,a.request,a._rqid=state['battle'],state['request'],state['rqid']
    a._python_rng,a._numpy_rng=state['python_rng'],state['numpy_rng']
    a._last_decision_audit=copy.deepcopy(state.get('last_decision_audit'))
    a._set_policy(state['policy'])
    return a


def policy_for_manifest(manifest):
    return normalize_policy(manifest.get('policy'))


def actor_for(side, team, seed, policy):
    policy=normalize_policy(policy)
    return Actor(side,team['name'],seed,team=team['team'],policy_id=policy['policy_id'],
                 policy_config=policy['config'],policy_config_hash=policy['config_hash'])


def validate_actor_policies(actors, policy):
    policy=normalize_policy(policy)
    if any(normalize_policy(getattr(actor,'policy_metadata',None))!=policy for actor in actors.values()):
        raise ValueError('restored actor policy differs from frozen policy')


def validate_record_policy(record, policy):
    if normalize_policy(record.get('policy'))!=normalize_policy(policy):
        raise ValueError('record policy differs from frozen policy')


def decision_audits(actors, choices, *, forced_side=None, compact=False):
    return {side:actor.decision_audit(command=choices[side],forced=side==forced_side,compact=compact)
            for side,actor in actors.items() if side in choices
            and actor.policy_metadata['policy_id']!=BASE_POLICY_ID}


def pack_actors(directory, actors):
    return {s:pack_actor(directory,a) for s,a in actors.items()}


def unpack_actors(directory, data):
    return {s:unpack_actor(directory,v) for s,v in data.items()}


def boundary_signature(response):
    return digest({k:response.get(k,'') if k=='winner' else response[k] for k in ('requests','needs_choice','choices_done','choices','ended','winner',
                                         'turn','request_state','mid_turn','queue_length')} | {
        'actor_logs':{s:gameplay_lines(v) for s,v in response['actor_logs'].items()},
        'public_log':gameplay_lines(response['public_log'])})


def teams_for(manifest, game):
    opponent=next(t for t in manifest['opponents'] if t['number']==game['team_number'])
    namespace=manifest.get('namespace','EX065')
    return dict(p1=dict(name=f'{namespace}p1',team=opponent['packed']),
                p2=dict(name=f'{namespace}p2',team=manifest['own']['packed']))
