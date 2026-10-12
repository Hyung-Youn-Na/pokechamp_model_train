"""EX-067 policy identity, private audit, public hook and resume boundaries."""
from __future__ import annotations

import copy
import importlib
import json
import pickle
import random
from pathlib import Path

import numpy as np
import pytest

from integration.pokechamp.abyssal_tera import AbyssalTeraPlayer, POLICY_ID
from integration.pokechamp.battle_adapter import BattleEnvironmentError
from integration.pokechamp.joint_q.actor import Actor, BASE_POLICY_ID, normalize_policy
from integration.pokechamp.joint_q.engine import pack_actor, unpack_actor, teams_for
from integration.pokechamp.joint_q.storage import atomic, digest, read, sha
from integration.pokechamp.joint_q.tera_config import policy_spec
from integration.pokechamp.tests.test_branch_rollout_policy import (
    fixture_actor as legacy_actor, request, numpy_state_equal,
)
from poke_env.player.baselines import AbyssalPlayer


@pytest.fixture(autouse=True)
def canonical_directory(monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parents[3] / 'pokechamp')


def configured_actor(seed=138, *, preview=False):
    spec=policy_spec()
    actor=Actor('p1','Alice',seed,policy_id=spec['policy_id'],
                policy_config=spec['config'],policy_config_hash=spec['config_hash'])
    actor.feed([
        '|init|battle','|player|p1|Alice|1|','|player|p2|Bob|2|',
        '|teamsize|p1|2','|teamsize|p2|2','|gametype|singles','|gen|9',
        '|tier|[Gen 9] OU','|clearpoke','|poke|p1|Pikachu, M|',
        '|poke|p1|Charizard, M|','|poke|p2|Squirtle, M|','|poke|p2|Venusaur, M|',
        '|request|'+json.dumps(request(preview=True)),
    ])
    if not preview:
        actor.feed([
            '|start','|switch|p1a: Spark|Pikachu, M|211/211',
            '|switch|p2a: Shell|Squirtle, M|100/100','|turn|1',
            '|request|'+json.dumps(request()),
        ])
    return actor


def test_legacy_snapshot_defaults_to_unmodified_abyssal(tmp_path):
    old=legacy_actor(101,preview=True)
    restored=Actor.restore(old.snapshot())
    assert type(restored.player) is AbyssalPlayer
    assert restored.policy_metadata==normalize_policy()
    assert restored.choose()==old.choose()
    assert restored._python_rng==old._python_rng
    packed=pack_actor(tmp_path,old)
    assert packed['version']==2 and 'policy_metadata' not in packed
    restored=unpack_actor(tmp_path,packed)
    assert type(restored.player) is AbyssalPlayer
    assert restored.policy_metadata['policy_id']==BASE_POLICY_ID


def test_selected_policy_initializes_once_without_extra_avatar_rng():
    host_python,host_numpy=random.getstate(),np.random.get_state()
    old,new=legacy_actor(429,preview=True),configured_actor(429,preview=True)
    assert isinstance(new.player,AbyssalTeraPlayer)
    assert new.policy_metadata==policy_spec()
    assert new._python_rng==old._python_rng
    assert numpy_state_equal(new._numpy_rng,old._numpy_rng)
    assert new.choose()==old.choose()
    assert new.decision_audit()['reason']=='team_preview'
    assert random.getstate()==host_python
    assert numpy_state_equal(np.random.get_state(),host_numpy)


@pytest.mark.parametrize('codec',['snapshot','blobs'])
def test_policy_and_public_move_memory_roundtrip(tmp_path,codec):
    actor=configured_actor()
    actor.feed(['|move|p2a: Shell|Seismic Toss|p1a: Spark'])
    if codec=='snapshot':
        restored=Actor.restore(actor.snapshot())
    else:
        packed=pack_actor(tmp_path,actor)
        assert packed['version']==3 and packed['policy_metadata']==policy_spec()
        restored=unpack_actor(tmp_path,packed)
    assert restored.policy_metadata==policy_spec()
    assert type(restored.player) is AbyssalTeraPlayer
    assert restored.player._tera_public_moves['p2: Shell']=={'seismictoss'}
    restored.player.observe_public_move('p2a: Shell','Surf')
    assert actor.player._tera_public_moves['p2: Shell']=={'seismictoss'}
    # Compare the unmodified saved observation and its policy/RNG, not the probe.
    restored=(Actor.restore(actor.snapshot()) if codec=='snapshot' else unpack_actor(tmp_path,packed))
    assert restored.choose()==actor.choose()
    assert restored.decision_audit()==actor.decision_audit()
    assert restored._python_rng==actor._python_rng
    assert numpy_state_equal(restored._numpy_rng,actor._numpy_rng)
    again=Actor.restore(restored.snapshot())
    assert again.decision_audit()==restored.decision_audit()


def test_public_hook_never_receives_request_or_rejected_split(monkeypatch):
    actor=configured_actor()
    seen=[]
    monkeypatch.setattr(actor.player,'observe_public_line',seen.append)
    actor.feed(['|request|'+json.dumps(request()),'|move|p2a: Shell|Seismic Toss|p1a: Spark'])
    assert seen==['|move|p2a: Shell|Seismic Toss|p1a: Spark']
    with pytest.raises(BattleEnvironmentError):
        actor.feed(['|split|p1'])
    assert len(seen)==1
    actor.feed(['|-transform|p2a: Shell|p1a: Spark'])
    assert seen[-1].startswith('|-transform|')


@pytest.mark.parametrize('mutation',['hash','id','config','remove','downgrade'])
def test_snapshot_metadata_tampering_fails_closed(mutation):
    state=pickle.loads(configured_actor().snapshot())
    if mutation=='hash':
        state['policy_metadata']['config_hash']='0'*64
    elif mutation=='id':
        state['policy_metadata']['policy_id']='unknown'
    elif mutation=='config':
        state['policy']['policy_config']['speed_margin']=99
    elif mutation=='remove':
        del state['policy_metadata']
    else:
        state['version']=1
        del state['policy_metadata']
    with pytest.raises(ValueError):
        Actor.restore(pickle.dumps(state))


def test_packed_envelope_tampering_fails_closed(tmp_path):
    packed=pack_actor(tmp_path,configured_actor())
    for field,value in [('config_hash','0'*64),('policy_id','unknown')]:
        changed=copy.deepcopy(packed)
        changed['policy_metadata'][field]=value
        with pytest.raises(ValueError):
            unpack_actor(tmp_path,changed)
    changed=copy.deepcopy(packed)
    changed['version']=2
    changed.pop('policy_metadata')
    with pytest.raises(ValueError):
        unpack_actor(tmp_path,changed)


class StubActor:
    """Deterministic lifecycle stub; no experimental battles are collected."""
    def __init__(self,side,username,policy,calls=0):
        self.side,self.username=side,username
        self.policy_metadata=copy.deepcopy(policy)
        self.calls=calls
        self.request={}
        self.seed=None

    def choose(self):
        self.calls+=1
        return 'move 1'

    def reseed(self,seed):
        self.seed=seed

    def decision_audit(self,*,command=None,forced=False,compact=False):
        return dict(turn=1,reason='forced_candidate' if forced else 'baseline_preserved',
                    command=command or 'move 1',terastallize=False,already_tera=False,tera_used=False)


def stub_pack(_directory,actor):
    return dict(side=actor.side,username=actor.username,policy=actor.policy_metadata,calls=actor.calls)


def stub_unpack(_directory,state):
    return StubActor(state['side'],state['username'],state['policy'],state['calls'])


def stub_pack_all(directory,actors):
    return {side:stub_pack(directory,actor) for side,actor in actors.items()}


def stub_unpack_all(directory,states):
    return {side:stub_unpack(directory,state) for side,state in states.items()}


class StubSimulator:
    def __init__(self,*,steps=1,after_step=None,**_kwargs):
        self.index=0
        self.steps=steps
        self.after_step=after_step

    def response(self):
        ended=self.index>=self.steps
        return dict(ended=ended,needs_choice=[] if ended else ['p1','p2'],
                    turn=self.index+1,winner='EX067p2' if ended else '',public_log=[])

    def __enter__(self):
        return self

    def __exit__(self,*_args):
        pass

    def init(self,_teams,_seed):
        self.index=0
        return self.response()

    def step(self,_choices):
        self.index+=1
        if self.after_step:
            self.after_step(self.index)
        return self.response()

    def snapshot(self):
        return dict(index=self.index)

    def restore(self,snapshot):
        self.index=snapshot['index']
        return self.response()

    def reseed(self,_seed):
        pass


def stub_boundary(response):
    return digest(response)


def capture_fixture(tmp_path,monkeypatch):
    capture=importlib.import_module('integration.pokechamp.joint_q.capture')
    runtime=importlib.import_module('integration.pokechamp.observation.runtime')
    pipeline=importlib.import_module('integration.pokechamp.joint_q.pipeline')
    manifest=dict(namespace='EX067',policy=policy_spec(),own={'packed':'own'},
                  opponents=[{'number':1,'packed':'opponent'}])
    game=dict(game_id='EX067-test',split='train',team_number=1,
              actor_seeds={'p1':1,'p2':2},simulator_seed=[1,2,3,4])
    atomic(tmp_path/'manifest.json',manifest)
    initialized=[]
    def actor_for(side,team,seed,policy):
        actor=StubActor(side,team['name'],policy)
        initialized.append((side,seed,copy.deepcopy(policy)))
        return actor
    class Official:
        def __init__(self,_side):
            pass
        def __enter__(self):
            return self
        def __exit__(self,*_args):
            pass
        def snapshot(self,*_args,**_kwargs):
            return dict(candidates=[dict(wire='move 1')],request={})
    monkeypatch.setattr(capture,'actor_for',actor_for)
    monkeypatch.setattr(capture,'Simulator',StubSimulator)
    monkeypatch.setattr(capture,'feed',lambda *_args,**_kwargs:None)
    monkeypatch.setattr(capture,'boundary_signature',stub_boundary)
    monkeypatch.setattr(capture,'pack_actor',stub_pack)
    monkeypatch.setattr(capture,'pack_actors',stub_pack_all)
    monkeypatch.setattr(capture,'unpack_actor',stub_unpack)
    monkeypatch.setattr(capture,'unpack_actors',stub_unpack_all)
    monkeypatch.setattr(runtime,'OfficialClient',Official)
    monkeypatch.setattr(pipeline,'admission',lambda _directory:None)
    return capture,game,initialized


def test_original_follower_replay_and_root_preserve_frozen_policy(tmp_path,monkeypatch):
    capture,game,initialized=capture_fixture(tmp_path,monkeypatch)
    record=capture.capture(tmp_path,game)
    assert [side for side,_seed,_policy in initialized]==['p1','p2','p2']
    assert all(policy==policy_spec() for _side,_seed,policy in initialized)
    assert record['policy']==policy_spec()
    assert set(record['steps'][0]['policy_audits'])=={'p1','p2'}
    root=read(tmp_path/record['roots'][0]['path'])
    assert root['policy']==policy_spec()
    assert root['actors']['p2']['calls']==0
    validated=capture.validate_game(tmp_path,game)
    assert validated['passed'] and validated['policy']==policy_spec()
    assert len(initialized)==5 and all(p==policy_spec() for _s,_seed,p in initialized)
    # Existing immutable artifacts cannot silently be reused under another policy.
    manifest=read(tmp_path/'manifest.json')
    manifest.pop('policy')
    atomic(tmp_path/'manifest.json',manifest)
    with pytest.raises(ValueError,match='policy'):
        capture.capture(tmp_path,game)


def test_original_stop_saves_same_policy_checkpoint_and_resumes(tmp_path,monkeypatch):
    capture,game,_initialized=capture_fixture(tmp_path,monkeypatch)
    from integration.pokechamp.joint_q.pipeline import ResourceReserveError
    (tmp_path/'STOP').touch()
    with pytest.raises(ResourceReserveError):
        capture.capture(tmp_path,game)
    checkpoint=read(tmp_path/'games'/game['game_id']/'checkpoint.json.gz')
    assert checkpoint['policy']==policy_spec()
    assert checkpoint['steps']==[] and checkpoint['actors']['p2']['calls']==0
    (tmp_path/'STOP').unlink()
    resumed=capture.capture(tmp_path,game)
    assert resumed['passed'] and len(resumed['steps'])==1
    assert resumed['started_at']==checkpoint['started_at']
    assert capture.validate_game(tmp_path,game)['passed']


def rollout_fixture(tmp_path,monkeypatch,*,interrupt=False):
    rollout=importlib.import_module('integration.pokechamp.joint_q.rollout')
    tmp_path.mkdir(parents=True,exist_ok=True)
    restored=[]
    def unpack_all(directory,states):
        actors=stub_unpack_all(directory,states)
        restored.append(actors)
        return actors
    def after_step(index):
        if interrupt and index==1:
            (tmp_path/'STOP').touch()
    sim=StubSimulator(steps=2,after_step=after_step)
    root=dict(policy=policy_spec(),cursors={'p1':0,'p2':0},simulator=sim.snapshot(),
        actors=stub_pack_all(tmp_path,{s:StubActor(s,'EX067'+s,policy_spec()) for s in ('p1','p2')}),
        boundary=stub_boundary(sim.response()),actions=[dict(action_id='move_1',command='move 1'),
                                                     dict(action_id='move_2',command='move 2')])
    root_path='private/roots/root.json.gz'
    atomic(tmp_path/root_path,root)
    task=dict(id='job',attempt=1,observation_id='root',action_id='move_2',replicate=0,
        root_path=root_path,root_sha256=sha(tmp_path/root_path),
        seeds=json.dumps(dict(actors={'p1':34,'p2':35},simulator=[1,2,3,4])))
    monkeypatch.setattr(rollout,'_DIRECTORY',tmp_path)
    monkeypatch.setattr(rollout,'_SOURCE','source')
    monkeypatch.setattr(rollout,'simulator',lambda:sim)
    monkeypatch.setattr(rollout,'feed',lambda *_args,**_kwargs:None)
    monkeypatch.setattr(rollout,'boundary_signature',stub_boundary)
    monkeypatch.setattr(rollout,'pack_actors',stub_pack_all)
    monkeypatch.setattr(rollout,'unpack_actors',unpack_all)
    rollout.get_root.cache_clear()
    return rollout,task,restored


def test_forced_first_candidate_skips_policy_and_resume_keeps_audits(tmp_path,monkeypatch):
    rollout,task,restored=rollout_fixture(tmp_path/'resumed',monkeypatch,interrupt=True)
    interrupted=rollout.execute(task)
    assert interrupted['status']=='interrupted'
    assert restored[0]['p1'].calls==1 and restored[0]['p2'].calls==0
    saved=read(tmp_path/'resumed/private/checkpoints/job.json.gz')
    first=copy.deepcopy(saved['trace'][0])
    assert saved['policy']==policy_spec() and not saved['first_pending']
    assert first['choices']['p2']=='move 2'
    assert first['policy_audits']['p2']['reason']=='forced_candidate'
    (tmp_path/'resumed/STOP').unlink()
    completed=rollout.execute(dict(task,attempt=2))
    assert completed['status']=='win'
    resumed=read(completed['path'])
    assert resumed['resumed'] and resumed['policy']==policy_spec()
    assert resumed['trace'][0]==first
    assert restored[-1]['p2'].calls==1 and restored[-1]['p1'].calls==2
    rollout,task,_restored=rollout_fixture(tmp_path/'whole',monkeypatch)
    whole=read(rollout.execute(task)['path'])
    assert whole['trace']==resumed['trace']
    assert whole['trace_sha256']==resumed['trace_sha256']
    assert whole['root_opponent_choice']==resumed['root_opponent_choice']


def test_checkpoint_cannot_resume_under_changed_policy(tmp_path,monkeypatch):
    rollout,task,_restored=rollout_fixture(tmp_path,monkeypatch,interrupt=True)
    assert rollout.execute(task)['status']=='interrupted'
    checkpoint=read(tmp_path/'private/checkpoints/job.json.gz')
    checkpoint['policy']['config_hash']='0'*64
    atomic(tmp_path/'private/checkpoints/job.json.gz',checkpoint)
    (tmp_path/'STOP').unlink()
    result=read(rollout.execute(dict(task,attempt=2))['path'])
    assert result['status']=='error' and 'policy' in result['error']


def test_actor_names_follow_manifest_namespace_and_legacy_default():
    manifest=dict(own={'packed':'own'},opponents=[{'number':1,'packed':'opponent'}])
    game={'team_number':1}
    assert teams_for(manifest,game)['p1']['name']=='EX065p1'
    manifest['namespace']='EX067'
    assert teams_for(manifest,game)['p2']['name']=='EX067p2'
