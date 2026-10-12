"""EX-067 schedule, isolation from sealed EX-066, and operational gates."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from integration.pokechamp.joint_q import tera_config as tc
from integration.pokechamp.joint_q import pipeline
from integration.pokechamp.joint_q.storage import atomic,canonical,read,rollout_seeds as old_seeds
from integration.pokechamp.joint_q.ledger import Ledger


def minimal_manifest():
    return dict(experiment=tc.EXPERIMENT,namespace=tc.NAMESPACE,master_seed=tc.MASTER,
                version=tc.VERSION,policy=tc.policy_spec())


def test_new_seed_namespace_matches_independent_sha256_and_keeps_old():
    raw=hashlib.sha256(canonical(['EX067',20260930,'state',7,'simulator'])).digest()
    assert tc.rollout_seeds('state',7)['simulator']==[
        int.from_bytes(raw[i:i+2],'big') for i in (0,2,4,6)]
    assert tc.rollout_seeds('state',7)!=old_seeds('state',7)
    assert tc.rollout_seeds('state',7)!=tc.rollout_seeds('state',8)
    # The generic storage module must retain EX-065's original identities.
    from integration.pokechamp.joint_q import storage
    assert storage.MASTER==20260929 and storage.VERSION=='ex065-rollout-v1'


def test_global_continuation_description_preserves_model_schema_and_actions():
    from integration.pokechamp.joint_q.serializer import JointInput,VERSION
    value=JointInput(json.dumps(dict(version=VERSION,instructions='public',state={},
                                    actions=[dict(action_id='move_1')])) )
    described=tc.describe_continuation(value)
    assert described.action_ids==value.action_ids
    assert described.payload['state']==value.payload['state']
    assert set(described.payload)==set(value.payload)
    assert 'abyssal-tera-v1' in described.payload['instructions']
    assert value.payload['instructions']=='public'


def test_80_new_games_exact_teams_splits_seeds_and_policy(tmp_path):
    from integration.pokechamp.joint_q.manifest import prepare
    from integration.pokechamp.joint_q.storage import DEFAULT
    prepare(tmp_path,experiment='EX-067')
    new=read(tmp_path/'manifest.json')
    old=read(DEFAULT/'manifest.json')
    assert Counter(g['split'] for g in new['games'])=={'train':50,'validation':10,'test':20}
    assert sum(g['pilot'] for g in new['games'])==10
    assert new['own']['packed']==old['own']['packed']
    assert [(t['number'],t['team_sha256'],t['group_id'],t['split']) for t in new['opponents']]==[
        (t['number'],t['team_sha256'],t['group_id'],t['split']) for t in old['opponents']]
    assert not {tuple(g['simulator_seed']) for g in new['games']} & {tuple(g['simulator_seed']) for g in old['games']}
    assert all(g['game_id'].startswith('EX067-') for g in new['games'])
    assert new['policy']==tc.policy_spec()
    assert new['limits']['initial_workers']==16 and new['limits']['wall_clock_cap'] is None
    with pytest.raises(FileExistsError):
        prepare(tmp_path,experiment='EX-067')


def test_ledger_uses_new_seeds_and_same_rng_after_interruption(tmp_path):
    atomic(tmp_path/'manifest.json',minimal_manifest())
    ledger=Ledger(tmp_path,'source')
    root=dict(observation_id='EX067-observation',path='root',sha256='a'*64,
              actions=[dict(action_id='move_1'),dict(action_id='move_2')])
    ledger.register(root,'game')
    first=ledger.claim()
    assert json.loads(first['seeds'])==tc.rollout_seeds(first['observation_id'],first['replicate'])
    ledger.recover()
    second=ledger.claim(first['id'])
    assert second['seeds']==first['seeds'] and second['attempt']==2
    ledger.close()


@pytest.mark.parametrize('field,value',[('namespace','EX999'),('master_seed',123),('version','later')])
def test_manifest_drift_fails_closed(field,value):
    manifest=minimal_manifest()
    manifest[field]=value
    with pytest.raises(ValueError):
        tc.validate_manifest(manifest)


def test_holdout_requires_both_gates(tmp_path,monkeypatch):
    manifest=minimal_manifest()|dict(games=[dict(game_id='train',split='train',pilot=True),
                                          dict(game_id='test',split='test',pilot=False)])
    atomic(tmp_path/'manifest.json',manifest)
    monkeypatch.setattr(pipeline,'verify',lambda _: 'source')
    assert len(pipeline.select_games(tmp_path,'pilot'))==1
    with pytest.raises(FileNotFoundError):
        pipeline.select_games(tmp_path,'test')
    atomic(tmp_path/'pilot-gate.json',dict(passed=True,source_id='source'))
    with pytest.raises(FileNotFoundError):
        pipeline.select_games(tmp_path,'test')
    atomic(tmp_path/'rest-gate.json',dict(passed=True,source_id='source'))
    assert pipeline.select_games(tmp_path,'test')[0]['game_id']=='test'
    with pytest.raises(ValueError):
        pipeline.select_games(tmp_path,'all')


def test_original_transient_retry_keeps_game_seed_and_three_attempts(tmp_path,monkeypatch):
    from integration.pokechamp.joint_q import capture as module
    calls=[]
    game=dict(game_id='same-game',simulator_seed=[1,2,3,4])
    def failing(directory,same):
        calls.append(same.copy())
        raise TimeoutError('simulator deadline exceeded')
    monkeypatch.setattr(module,'capture',failing)
    with pytest.raises(TimeoutError):
        pipeline.capture_one((str(tmp_path),game))
    assert calls==[game]*3
    with pytest.raises(RuntimeError,match='exhausted'):
        pipeline.capture_one((str(tmp_path),game))
    assert len(calls)==3
    assert len(list((tmp_path/'games/same-game').glob('attempt-*-finish.json')))==3


def test_original_technical_defect_does_not_retry(tmp_path,monkeypatch):
    from integration.pokechamp.joint_q import capture as module
    calls=[]
    def failing(*args):
        calls.append(1)
        raise ValueError('illegal request')
    monkeypatch.setattr(module,'capture',failing)
    with pytest.raises(ValueError,match='illegal request'):
        pipeline.capture_one((str(tmp_path),dict(game_id='bad')))
    with pytest.raises(ValueError,match='versioned recovery'):
        pipeline.capture_one((str(tmp_path),dict(game_id='bad')))
    assert calls==[1]


def test_input_transport_retries_same_observation_source(tmp_path,monkeypatch):
    calls=[]
    args=(str(tmp_path),dict(game_id='same-input',simulator_seed=[1,2,3,4]))
    def retry(value):
        calls.append(value)
        if len(calls)==1:
            raise TimeoutError('engine deadline exceeded')
        return dict(game_id='same-input',inputs=8)
    monkeypatch.setattr(pipeline,'input_one',retry)
    assert pipeline.input_with_retry(args)==dict(game_id='same-input',inputs=8)
    assert calls==[args,args]


def test_cooperative_input_resource_stop_remains_resumable(tmp_path,monkeypatch):
    atomic(tmp_path/'STOP',dict(reason='resources'))
    args=(str(tmp_path),dict(game_id='resource'))
    with pytest.raises(pipeline.ResourceReserveError):
        pipeline.input_with_retry(args)
    finish=read(tmp_path/'private/input-attempts/resource/attempt-1-finish.json')
    assert finish['resumable_pause'] and not finish['transient']
    (tmp_path/'STOP').unlink()
    monkeypatch.setattr(pipeline,'input_one',lambda _:dict(game_id='resource',inputs=1))
    assert pipeline.input_with_retry(args)['inputs']==1


def test_resource_reserve_pauses_before_submission(tmp_path,monkeypatch):
    monkeypatch.setattr(pipeline,'resources',lambda _:dict(available_memory=23*1024**3,free_disk=30*1024**3))
    with pytest.raises(pipeline.ResourceReserveError):
        pipeline.admission(tmp_path)
    assert read(tmp_path/'resource-stop.json')['available_memory']==23*1024**3


def test_runner_never_enables_test_before_complete_train_validation():
    from integration.pokechamp.joint_q.tera import stages
    schedule=stages()
    assert schedule.index(('gate','pilot'))<schedule.index(('capture','rest'))
    assert schedule.index(('gate','rest'))<schedule.index(('capture','test'))
    assert schedule[-3:]==[('viewer','test'),('browser','test'),('seal-copy','test')]
