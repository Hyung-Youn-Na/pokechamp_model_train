"""EX-065 input isolation, loss semantics and durable rollout accounting."""
import copy
import json
import math
from pathlib import Path
import pytest
from integration.pokechamp.joint_q import serializer as s
from integration.pokechamp.joint_q.data import TrainingRecord,collate,masked_mse,masked_argmax
from integration.pokechamp.joint_q.storage import atomic,digest,read,rollout_seeds,sha
from integration.pokechamp.joint_q.ledger import Ledger
from integration.pokechamp.joint_q.engine import regular_warning


def simple(ids=('move_1','switch_2')):
    return s.JointInput(json.dumps(dict(version=s.VERSION,instructions='unknown is not zero',
        state=dict(request_id=3,turn=2),actions=[dict(action_id=k,name=k) for k in ids])))


def test_model_boundary_and_metadata_independence():
    value=simple()
    original=s.render(value)
    record=TrainingRecord('obs',value,(0,1))
    with pytest.raises(TypeError):
        s.render(record)
    for key in s.FORBIDDEN:
        raw=value.payload
        raw['state'][key]={'sentinel':'secret'}
        with pytest.raises(ValueError):
            s.JointInput(json.dumps(raw))
    assert s.render(TrainingRecord('different',value,(1,0)).input)==original


def test_reorder_single_tie_zero_padding_loss_and_gradient():
    torch=pytest.importorskip('torch')
    a=TrainingRecord('a',simple(),(.25,.75))
    b=TrainingRecord('b',simple(('team_1',)),(0,))
    reordered=a.reordered(('switch_2','move_1'))
    assert reordered.q==(.75,.25)
    batch=collate([a,b])
    p=torch.tensor([[.5,.5],[.5,float('nan')]],requires_grad=True)
    loss=masked_mse(p,batch['q_targets'],batch['action_mask'])
    assert loss.item()==pytest.approx((.0625+.25)/2)
    loss.backward()
    assert p.grad[1,1].item()==0 and torch.isfinite(p.grad).all()
    assert masked_argmax(torch.zeros((2,2)),batch['action_mask']).tolist()==[0,0]
    assert masked_argmax(torch.tensor([[0.,0.],[0.,99.]]),batch['action_mask']).tolist()==[0,0]
    with pytest.raises(ValueError):
        a.reordered(('move_1','move_1'))


def registered(tmp_path):
    root=dict(observation_id='obs',path='root',sha256='a'*64,actions=[dict(action_id='move_1')])
    ledger=Ledger(tmp_path,'source')
    ledger.register(root,'game')
    return ledger,root


def result(tmp_path,task,status='win'):
    path=tmp_path/'private/results'/f"{task['id']}-a{task['attempt']}.json.gz"
    atomic(path,dict(job_id=task['id'],attempt=task['attempt'],source_id='source',root_sha256=task['root_sha256'],
                    seeds=json.loads(task['seeds']),status=status,terminal=True,score=1,trace=[],trace_sha256=digest([])),immutable=True)
    return path


def test_transaction_duplicate_submit_and_resume_after_atomic_result(tmp_path):
    ledger,root=registered(tmp_path)
    ledger.register(root,'game')
    assert ledger.counts()=={'pending':32}
    task=ledger.claim()
    assert ledger.claim(task['id']) is None
    path=result(tmp_path,task)
    # Simulate process death after rename, before SQLite commit.
    ledger.close()
    ledger=Ledger(tmp_path,'source')
    ledger.recover()
    assert ledger.counts()=={'complete':1,'pending':31}
    ledger.finish(task['id'],task['attempt'],path)
    assert ledger.counts()['complete']==1
    ledger.close()


def test_resume_before_save_retains_failed_attempt_three_attempt_limit(tmp_path):
    ledger,_=registered(tmp_path)
    first=ledger.claim()
    for n in (1,2,3):
        if n>1:
            task=ledger.claim(first['id'])
            assert task['attempt']==n and task['seeds']==first['seeds']
        ledger.recover()
    assert ledger.claim(first['id']) is None
    assert ledger.counts()['failed']==1
    assert ledger.db.execute('SELECT count(*) FROM attempts WHERE job_id=?',(first['id'],)).fetchone()[0]==3
    ledger.close()


def test_corruption_conflicting_result_and_version_fail_closed(tmp_path):
    ledger,_=registered(tmp_path)
    task=ledger.claim()
    path=result(tmp_path,task)
    ledger.finish(task['id'],task['attempt'],path)
    path.write_bytes(b'corrupt')
    with pytest.raises(ValueError):
        ledger.recover()
    ledger.close()
    with pytest.raises(ValueError):
        Ledger(tmp_path,'new-source')


def test_only_exact_regular_long_battle_warning_allowed():
    for turn in (500,600,700,800,900,910,980,990,998,999):
        left=1000-turn
        line=f"|bigerror|You will auto-tie if the battle doesn't end in {left} {'turn' if left==1 else 'turns'} (on turn 1000)."
        assert regular_warning(line,turn)
        assert not regular_warning(line,turn-1)
    assert not regular_warning('|bigerror|Warning: invalid team EVs',500)


def test_fingerprint_ignores_candidate_order_request_id_but_not_state():
    value=simple()
    other=s.reorder(value,tuple(reversed(value.action_ids)))
    raw=other.payload
    raw['state']['request_id']=345
    assert s.fingerprint(s.JointInput(json.dumps(raw)))==s.fingerprint(value)
    raw['state']['turn']=3
    assert s.fingerprint(s.JointInput(json.dumps(raw)))!=s.fingerprint(value)


def test_seed_identity_common_across_candidates():
    assert rollout_seeds('obs',4)==rollout_seeds('obs',4)
    assert rollout_seeds('obs',4)!=rollout_seeds('obs',5)
    assert len(rollout_seeds('obs',4)['simulator'])==4


def test_c3_flattening_tera_unknown_and_quantity_targets():
    from integration.pokechamp.diagnostics.candidate_state import TURN_COLUMNS
    p=dict(state=dict(decision_kind='turn_action',self_team=[dict(slot=1,species='Zapdos',active=True)],
        opponent_team=[dict(species='Cinderace',active=True)],candidate_assumptions=[],
        candidate_evaluations={
            'move_1':dict(kind='move',status='unknown',scenario_rows=[],unsupported=['not_supported']),
            'move_1_terastallize':dict(kind='move',status='unknown',scenario_rows=[],
                same_outcomes_as_action_id='move_1',tera_comparison=dict(non_tera_action_id='move_1',benefit='stale'))},
        candidate_scenario_columns=TURN_COLUMNS,candidate_switch_columns=[]),questions=dict(action=dict(criteria={
            'move_1':dict(kind='move',name='Roost',user='Zapdos',evaluation_ref='move_1'),
            'move_1_terastallize':dict(kind='move',name='Roost',user='Zapdos',terastallize=True,evaluation_ref='move_1_terastallize')})))
    value=s.project(p)
    raw=value.payload
    assert 'candidate_evaluations' not in raw['state']
    text=value.payload_json
    assert 'scenario_rows' not in text and 'same_outcomes_as_action_id' not in text
    a=raw['actions'][1]
    assert a['evaluation']['tera_comparison']['benefit'].startswith('unknown')
    assert a['evaluation']['quantities']['incoming_damage_pct']['target']=='Zapdos'
    assert 'Choose exactly one' not in text


def test_actor_codec_preserves_rng_policy_and_mutable_isolation(tmp_path):
    import base64
    import gzip
    from integration.pokechamp.branch_rollouts.policy import Actor
    from integration.pokechamp.joint_q.engine import pack_actor,unpack_actor
    root=Path('/workspace/.pokechamp-data/rollouts/ex058-b19-rollout-v1/private/a004.json.gz')
    state=json.load(gzip.open(root,'rt'))
    actor=Actor.restore(base64.b64decode(state['actors']['p1']))
    canonical_actor=Actor.restore(actor.snapshot())
    packed=pack_actor(tmp_path,actor)
    restored=unpack_actor(tmp_path,packed)
    assert restored.request==canonical_actor.request
    assert restored.choose()==canonical_actor.choose()
    assert restored._python_rng==canonical_actor._python_rng
    second=unpack_actor(tmp_path,packed)
    second.player.pokemon_move_dict.clear()
    assert actor.player.pokemon_move_dict
    # Shared static tables are stored once while every branch owns fresh objects.
    assert len(packed['pickle'])<100_000
    assert restored.player.gen is second.player.gen
    with pytest.raises(TypeError):
        second.player.gen.moves.clear()
    with pytest.raises(TypeError):
        next(iter(second.battle.team.values()))._sets.clear()


def test_nonterminal_simulator_can_omit_winner():
    from integration.pokechamp.joint_q.engine import boundary_signature,Simulator
    from integration.pokechamp.joint_q.storage import DEFAULT,read
    from integration.pokechamp.joint_q.engine import teams_for
    manifest=read(DEFAULT/'manifest.json')
    game=manifest['games'][0]
    with Simulator() as sim:
        response=sim.init(teams_for(manifest,game),game['simulator_seed'])
    original=boundary_signature(response)
    assert not response['ended'] and 'winner' not in response
    response['winner']=''
    assert boundary_signature(response)==original


def test_cosmetic_keldeo_exact_request_binding():
    from integration.pokechamp.joint_q.actor import Actor
    from integration.pokechamp.joint_q.engine import Simulator,feed,teams_for
    from integration.pokechamp.joint_q.storage import DEFAULT,read
    manifest=read(DEFAULT/'manifest.json')
    game=next(g for g in manifest['games'] if g['team_number']==21254 and g['pilot'])
    teams=teams_for(manifest,game)
    actors={s:Actor(s,teams[s]['name'],game['actor_seeds'][s],team=teams[s]['team']) for s in teams}
    with Simulator() as sim:
        response=sim.init(teams,game['simulator_seed'])
        assert any('|poke|p1|Keldeo-Resolute' in line for line in response['public_log'])
        feed(response,actors,None,dict(p1=0,p2=0))
        assert len(actors['p1'].battle.team)==6
        assert sum(p._species=='keldeoresolute' for p in actors['p1'].battle.team.values())==1
        # Canonical species alias remains intact on the opponent public preview.
        assert any(p.species=='keldeo' for p in actors['p2'].battle._teampreview_opponent_team)
        sim.step({s:a.choose() for s,a in actors.items()})


def test_semantic_fingerprint_ignores_team_and_move_display_order():
    value=simple()
    raw=value.payload
    raw['state']['self_team']=[dict(slot=1,species='A',current_move_slots=[dict(slot=1,id='tackle'),dict(slot=2,id='rest')]),dict(slot=2,species='B')]
    a=s.JointInput(json.dumps(raw))
    raw['state']['self_team'].reverse()
    raw['state']['self_team'][1]['current_move_slots'].reverse()
    raw['state']['request_id']=100
    for m in raw['state']['self_team']:
        m['slot']+=100
    assert s.fingerprint(a)==s.fingerprint(s.JointInput(json.dumps(raw)))


def test_style_classification_uses_normalized_move_names():
    from integration.pokechamp.joint_q.manifest import classify
    rows=[dict(species=str(i),moves=['Recover'],ability='Pressure',evs={'hp':252,'def':252}) for i in range(6)]
    assert classify(rows)['label']=='defensive'
    assert all(r['recovery_moves']==['recover'] for r in classify(rows)['evidence'])
