"""Original games, full deterministic replay and every root's next-boundary gate."""
from __future__ import annotations
import copy
import time
import traceback
from pathlib import Path
from .engine import (Actor, Simulator, feed, pack_actors, pack_actor, unpack_actor, unpack_actors,
                     boundary_signature, teams_for, policy_for_manifest, actor_for,
                     validate_actor_policies, validate_record_policy, decision_audits)
from .actor import BASE_POLICY_ID
from .storage import atomic, digest, read, sha


def capture(directory, game):
    from ..observation.runtime import OfficialClient
    directory=Path(directory)
    folder=directory/'games'/game['game_id']
    target=folder/'capture.json'
    manifest=read(directory/'manifest.json')
    policy=policy_for_manifest(manifest)
    uses_policy=policy['policy_id']!=BASE_POLICY_ID
    if target.exists():
        record=read(target)
        validate_record_policy(record,policy)
        if not record['passed'] or record['game']!=game:
            raise ValueError('failed game requires explicit versioned recovery')
        for root in record['roots']:
            if sha(directory/root['path'])!=root['sha256']:
                raise ValueError('stored root changed')
        return record
    folder.mkdir(parents=True,exist_ok=True)
    teams=teams_for(manifest,game)
    actors={s:actor_for(s,teams[s],game['actor_seeds'][s],policy) for s in teams}
    follower=actor_for('p2',teams['p2'],game['actor_seeds']['p2'],policy)
    histories={s:['|init|battle'] for s in teams}
    cursors={s:0 for s in teams}
    roots=[]
    steps=[]
    started=time.time()
    try:
        with Simulator(timeout=120) as sim, OfficialClient('p2') as official:
            checkpoint_path=folder/'checkpoint.json.gz'
            if checkpoint_path.exists():
                checkpoint=read(checkpoint_path)
                if checkpoint['game']!=game:
                    raise ValueError('original checkpoint game/seed mismatch')
                validate_record_policy(checkpoint,policy)
                actors=unpack_actors(directory,checkpoint['actors'])
                follower=unpack_actor(directory,checkpoint['follower'])
                validate_actor_policies({**actors,'follower':follower},policy)
                histories,cursors=checkpoint['histories'],checkpoint['cursors']
                roots,steps=checkpoint['roots'],checkpoint['steps']
                started,initial=checkpoint['started_at'],checkpoint['initial']
                response=sim.restore(checkpoint['simulator'])
                if 'boundary' in checkpoint and boundary_signature(response)!=checkpoint['boundary']:
                    raise ValueError('original checkpoint boundary mismatch')
            else:
                response=sim.init(teams,game['simulator_seed'])
                feed(response,actors,histories,cursors,follower)
                initial=boundary_signature(response)
            def checkpoint_original():
                atomic(checkpoint_path,dict(game=game,policy=policy,simulator=sim.snapshot(),
                    actors=pack_actors(directory,actors),follower=pack_actor(directory,follower),
                    histories=histories,cursors=cursors,roots=roots,steps=steps,
                    started_at=started,initial=initial,boundary=boundary_signature(response)))
            checkpoint_original()
            while not response['ended']:
                if uses_policy:
                    from .pipeline import admission, ResourceReserveError
                    if (directory/'STOP').exists():
                        checkpoint_original()
                        raise ResourceReserveError('cooperative stop at original decision boundary')
                    if len(steps)%10==0:
                        try:
                            admission(directory)
                        except ResourceReserveError:
                            checkpoint_original()
                            raise
                if not response['needs_choice']:
                    raise ValueError('nonterminal game has no choice')
                pending=None
                if 'p2' in response['needs_choice']:
                    oid=game['game_id']+f'-o{len(roots):04d}'
                    prefix=[dict(event_seq=1,protocol='\n'.join(histories['p2']))]
                    observed=official.snapshot(prefix,game['game_id'],replay=False)
                    candidates=observed['candidates']
                    actions=[dict(action_id=c['wire'].replace(' ','_'),command=c['wire']) for c in candidates]
                    if not actions or len({a['command'] for a in actions})!=len(actions):
                        raise ValueError('empty/duplicate official candidates')
                    # Official team candidates specify lead slot; preserve full
                    # original policy permutation separately, never relabel it.
                    for a in actions:
                        if a['command'].startswith('team '):
                            slot=int(a['command'].split()[1])
                            a['command']='team '+''.join(map(str,[slot]+[x for x in range(1,7) if x!=slot]))
                    root=dict(observation_id=oid,game_id=game['game_id'],split=game['split'],policy=policy,
                        step_index=len(steps),turn=response['turn'],official=observed,prefix=prefix,actions=actions,
                        simulator=sim.snapshot(),actors=pack_actors(directory,{'p1':actors['p1'],'p2':follower}),
                        original_actors=pack_actors(directory,actors),cursors=dict(cursors),
                        needs_choice=list(response['needs_choice']),boundary=boundary_signature(response),
                        initialization='p2 observed-prefix only; original actor separate')
                    pending=dict(path=f'private/roots/{oid}.json.gz',root=root)
                choices={s:actors[s].choose() for s in response['needs_choice']}
                audits=decision_audits(actors,choices)
                before=boundary_signature(response)
                response=sim.step(choices)
                feed(response,actors,histories,cursors,follower)
                after=boundary_signature(response)
                step=dict(index=len(steps),before=before,after=after,choices=choices,turn=response['turn'])
                if audits:
                    step['policy_audits']=audits
                steps.append(step)
                if pending:
                    root=pending['root']
                    root.update(original_choices=choices,next_boundary=after)
                    if audits:
                        root['original_policy_audits']=audits
                    checksum=atomic(directory/pending['path'],root,immutable=True)
                    roots.append(dict(observation_id=root['observation_id'],path=pending['path'],sha256=checksum,
                                      actions=root['actions'],turn=root['turn'],
                                      kind='lead' if root['official']['request'].get('teamPreview') else
                                           'forced_switch' if any(root['official']['request'].get('forceSwitch',[])) else 'turn_action'))
                checkpoint_original()
            record=dict(passed=True,game=game,policy=policy,initial=initial,roots=roots,steps=steps,
                        public_log=response['public_log'],turns=response['turn'],winner=response['winner'],
                        started_at=started,elapsed_seconds=time.time()-started)
            atomic(target,record,immutable=True)
            return record
    except BaseException as error:
        atomic(folder/f'failure-{time.time_ns()}.json',dict(error=repr(error),traceback=traceback.format_exc(),
               started_at=started,roots=roots,steps=steps),immutable=True)
        raise


def validate_game(directory, game):
    directory=Path(directory)
    folder=directory/'games'/game['game_id']
    captured=read(folder/'capture.json')
    manifest=read(directory/'manifest.json')
    policy=policy_for_manifest(manifest)
    validate_record_policy(captured,policy)
    target=folder/'validated.json'
    if target.exists():
        receipt=read(target)
        if receipt['capture_sha256']!=sha(folder/'capture.json') or not receipt['passed']:
            raise ValueError('validation receipt mismatch')
        validate_record_policy(receipt,policy)
        return receipt
    teams=teams_for(manifest,game)
    actors={s:actor_for(s,teams[s],game['actor_seeds'][s],policy) for s in teams}
    cursors={s:0 for s in teams}
    started=time.time()
    with Simulator(timeout=120) as sim:
        response=sim.init(teams,game['simulator_seed'])
        feed(response,actors,None,cursors)
        if boundary_signature(response)!=captured['initial']:
            raise ValueError('original initial replay mismatch')
        for step in captured['steps']:
            choices={s:actors[s].choose() for s in response['needs_choice']}
            if choices!=step['choices'] or boundary_signature(response)!=step['before']:
                raise ValueError('original policy/request replay mismatch')
            if decision_audits(actors,choices)!=step.get('policy_audits',{}):
                raise ValueError('original policy decision audit replay mismatch')
            response=sim.step(choices)
            feed(response,actors,None,cursors)
            if boundary_signature(response)!=step['after']:
                raise ValueError('original full replay diverged')
        if not response['ended']:
            raise ValueError('original replay did not terminate')
        checked=[]
        for entry in captured['roots']:
            if sha(directory/entry['path'])!=entry['sha256']:
                raise ValueError('root hash mismatch')
            root=read(directory/entry['path'])
            validate_record_policy(root,policy)
            validate_actor_policies(unpack_actors(directory,root['actors']),policy)
            actors=unpack_actors(directory,root['original_actors'])
            validate_actor_policies(actors,policy)
            response=sim.restore(root['simulator'])
            if sim.snapshot()!=root['simulator'] or boundary_signature(response)!=root['boundary']:
                raise ValueError('snapshot round trip changed state/queue')
            choices={s:actors[s].choose() for s in response['needs_choice']}
            if choices!=root['original_choices']:
                raise ValueError('restored actor RNG or policy differs')
            if decision_audits(actors,choices)!=root.get('original_policy_audits',{}):
                raise ValueError('restored policy decision audit differs')
            response=sim.step(choices)
            feed(response,actors,None,dict(root['cursors']))
            if boundary_signature(response)!=root['next_boundary']:
                raise ValueError('snapshot next decision boundary diverged')
            checked.append(entry['observation_id'])
    value=dict(passed=True,game_id=game['game_id'],policy=policy,capture_sha256=sha(folder/'capture.json'),
               original_steps=len(captured['steps']),roots=checked,elapsed_seconds=time.time()-started)
    atomic(target,value,immutable=True)
    return value
