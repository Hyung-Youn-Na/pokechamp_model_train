import copy
import json
from pathlib import Path
import random
from types import SimpleNamespace
import numpy as np
import pytest
import torch
from torch import nn
from integration.pokechamp.joint_q.data import TrainingRecord, collate, masked_argmax, masked_mse
from integration.pokechamp.joint_q.serializer import JointInput, VERSION, FORBIDDEN
from integration.pokechamp.joint_q.storage import sha
from integration.pokechamp.joint_q.learning.artifacts import (
    save_checkpoint, validate_checkpoint, restore_training, shuffled, set_latest, latest)
from integration.pokechamp.joint_q.learning.config import CACHE, REVISION
from integration.pokechamp.joint_q.learning.metrics import observation, report, paired_bootstrap
from integration.pokechamp.joint_q.learning.model import JointValuePolicy, fingerprints, tokenizer
from integration.pokechamp.joint_q.learning.render import EncodedInput, check_length, render
from integration.pokechamp.joint_q.learning.runtime import backward_batch


def value(count=3):
    return JointInput(json.dumps(dict(version=VERSION,instructions='Use the supplied public observation.',
        state={'visible':'Pikachu'},actions=[dict(action_id=f'move_{i}',kind='move') for i in range(count)])))


@pytest.fixture(scope='module')
def tok():
    return tokenizer(CACHE/'models--Qwen--Qwen3.5-4B-Base'/'snapshots'/REVISION)


@pytest.mark.parametrize('count',[1,13])
def test_official_readout_positions_and_target_private_invariance(tok,count):
    source=value(count)
    record=TrainingRecord('record',source,tuple(i/max(count-1,1) for i in range(count)))
    encoded=render(source,tok)
    mutated=TrainingRecord('private-changed',source,tuple(1-q for q in record.q))
    assert render(mutated.input,tok)==encoded
    assert encoded.action_ids==source.action_ids
    assert len(encoded.readout_positions)==count
    prompt=tok.decode(encoded.input_ids,skip_special_tokens=False)
    for aid,pos in zip(encoded.action_ids,encoded.readout_positions,strict=True):
        prefix=tok.decode(encoded.input_ids[:pos+1],skip_special_tokens=False)
        assert prefix.endswith('ACTION_ID='+json.dumps(aid)+'\nQ_VALUE=')
        assert tok.decode([encoded.input_ids[pos]])=='='
    assert source.payload_json in prompt
    with pytest.raises(TypeError):
        render(record,tok)
    altered_payload=source.payload
    altered_payload['state']['private']={'q_values':[.9]*count}
    with pytest.raises(ValueError,match='teacher/private'):
        JointInput(json.dumps(altered_payload))


@pytest.mark.parametrize('field',sorted(FORBIDDEN))
def test_teacher_field_rejected_at_any_depth(field):
    payload=value().payload
    payload['state']['visible']=[{'nested':{field:'secret'}}]
    with pytest.raises(ValueError,match='teacher/private'):
        JointInput(json.dumps(payload))


def test_candidate_permutation_binds_ids_targets_and_positions(tok):
    r=TrainingRecord('example',value(),(.0,.25,1.))
    changed=r.reordered(('move_2','move_0','move_1'))
    assert changed.q==(1.,.0,.25)
    e=render(changed.input,tok)
    assert e.action_ids==('move_2','move_0','move_1')
    cached=EncodedInput.from_row(json.loads(json.dumps(e.to_row('example'))))
    assert cached==e
    row=e.to_row('example')
    row['input_ids']=list(e.input_ids)
    row['input_ids'][0]+=1
    with pytest.raises(ValueError,match='identity'):
        EncodedInput.from_row(row)
    with pytest.raises(ValueError):
        r.reordered(('move_0','move_0','move_1'))


def test_shuffle_reproducible_with_exact_observation_and_candidate_coverage():
    records=[TrainingRecord(str(i),value(13),tuple(k/12 for k in range(13))) for i in range(30)]
    a,b,c=list(shuffled(records,1)),list(shuffled(records,1)),list(shuffled(records,2))
    assert a==b and a!=c
    assert {r.observation_id for r in a}=={r.observation_id for r in records}
    for r in a:
        assert dict(zip(r.input.action_ids,r.q))==dict(zip(records[0].input.action_ids,records[0].q))


def test_padding_nan_inf_ignored_and_observations_equal_weighted():
    p=torch.tensor([[.2,.5,float('nan')],[.8,float('inf'),float('-inf')]],requires_grad=True)
    target=torch.tensor([[0.,1.,float('inf')],[1.,float('nan'),float('nan')]])
    mask=torch.tensor([[True,True,False],[True,False,False]])
    result=masked_mse(p,target,mask)
    assert result.item()==pytest.approx(.0925)
    result.backward()
    np.testing.assert_allclose(p.grad.numpy(),[[.1,-.25,0.],[-.2,0.,0.]],rtol=1e-6,atol=1e-8)
    assert masked_argmax(p,mask).tolist()==[1,0]
    assert masked_argmax(torch.zeros_like(p),mask).tolist()==[0,0]


class PositionBackbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.calls=0

    def forward(self,input_ids,**kwargs):
        self.calls+=1
        self.last_input_ids=input_ids.detach().clone()
        hidden=torch.arange(input_ids.shape[-1],device=input_ids.device).float()/1000
        return SimpleNamespace(last_hidden_state=hidden[None,:,None].expand(1,-1,2560))


def tiny_policy(tok):
    policy=JointValuePolicy.__new__(JointValuePolicy)
    nn.Module.__init__(policy)
    policy.backbone=PositionBackbone()
    policy.head=nn.Linear(2560,1,dtype=torch.float32)
    with torch.no_grad():
        policy.head.weight.zero_()
        policy.head.weight[0,0]=1.
        policy.head.bias.zero_()
    policy.tokenizer,policy.device_name=tok,'cpu'
    return policy


def test_predict_one_forward_independent_q_and_token_padding(tok):
    policy=tiny_policy(tok)
    source=value(13)
    q=policy.predict(source)
    assert list(q)==list(source.action_ids)
    assert policy.backbone.calls==1
    assert all(0<p<1 for p in q.values()) and sum(q.values())>1
    encoded=render(source,tok)
    expected=torch.sigmoid(torch.tensor(encoded.readout_positions)/1000).tolist()
    assert list(q.values())==pytest.approx(expected)
    assert torch.equal(policy.values(encoded),policy.values(encoded,padding=17))
    assert policy.backbone.last_input_ids.tolist()==[list(encoded.input_ids)]


def test_progress_preserves_prior_attempt_cost_and_failure_evidence(tmp_path):
    from integration.pokechamp.joint_q.learning.runtime import Progress
    from integration.pokechamp.joint_q.storage import atomic,read
    previous=dict(phase='interrupted',elapsed_seconds=12.5,gpu_seconds=8.5,forwards=7,
                  max_allocated_bytes=100,max_reserved_bytes=200)
    atomic(tmp_path/'progress.json',previous)
    progress=Progress(tmp_path,'train')
    progress.update(phase='resumed')
    current=read(tmp_path/'progress.json')
    assert current['elapsed_seconds']>=12.5 and current['gpu_seconds']==8.5 and current['forwards']==7
    preserved=list(tmp_path.glob('previous-progress-*.json'))
    assert len(preserved)==1 and read(preserved[0])==previous


@pytest.mark.parametrize('physical',[1,2])
def test_gpu_owner_routes_only_to_frozen_physical_gpu(tmp_path,monkeypatch,physical):
    from integration.pokechamp.joint_q.learning import runtime
    from integration.pokechamp.joint_q.storage import read
    monkeypatch.setattr(runtime,'ROOT',tmp_path)
    monkeypatch.setattr(runtime,'CONFIG',dict(runtime.CONFIG,physical_gpu=physical))
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES',str(physical))
    monkeypatch.setattr(runtime.torch.cuda,'device_count',lambda:1)
    calls=[]
    def facts(command,**kwargs):
        calls.append(command)
        return 'NVIDIA RTX A6000, GPU-test, 49140, 3, 0'
    monkeypatch.setattr(runtime.subprocess,'check_output',facts)
    with runtime.gpu_owner(tmp_path/'out','train'):
        receipt=read(tmp_path/'out/train-gpu.json')
        assert receipt['physical_gpu']==physical and receipt['visible_devices']==str(physical)
        assert (tmp_path/f'.pokechamp-data/locks/gpu{physical}.lock').exists()
        assert not (tmp_path/'.pokechamp-data/locks/gpu3.lock').exists()
    assert len(calls)==1 and f'--id={physical}' in calls[0]
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES','3')
    with pytest.raises(ValueError,match=f'physical GPU{physical}'):
        with runtime.gpu_owner(tmp_path/'out','wrong_gpu'):
            pytest.fail('incorrect GPU was accepted')
    assert len(calls)==1


@pytest.mark.parametrize('target,bias',[(0.,-100.),(1.,100.)])
def test_finite_zero_gradient_is_valid_at_zero_mse(tok,target,bias):
    from integration.pokechamp.joint_q.learning.runtime import check_gradients
    policy=tiny_policy(tok)
    with torch.no_grad():
        policy.head.weight.zero_()
        policy.head.bias.fill_(bias)
    record=TrainingRecord('zero-mse',value(13),tuple([target]*13))
    mse=backward_batch(policy,[(record,render(record.input,tok))])
    assert mse==0 and all(torch.isfinite(p.grad).all() and not torch.count_nonzero(p.grad)
                         for p in policy.parameters() if p.requires_grad)
    assert check_gradients(policy)==0
    assert torch.nn.utils.clip_grad_norm_(policy.parameters(),1,error_if_nonfinite=True)==0


@pytest.mark.parametrize('bad',[None,float('nan'),float('inf')])
def test_missing_and_nonfinite_gradients_remain_rejected(bad):
    from integration.pokechamp.joint_q.learning.runtime import check_gradients
    model=nn.Linear(1,1)
    for p in model.parameters():
        p.grad=None if bad is None else torch.full_like(p,bad)
    with pytest.raises(FloatingPointError,match='missing/nonfinite'):
        check_gradients(model)


@pytest.mark.parametrize('n',[1,3,7,8])
def test_last_accumulation_batch_averages_actual_observations(tok,n):
    policy=tiny_policy(tok)
    with torch.no_grad():
        policy.head.weight.zero_()
    records=[TrainingRecord(str(i),value(1 if i%2 else 13),tuple([i/max(n,1)]*(1 if i%2 else 13))) for i in range(n)]
    batch=[(r,render(r.input,tok)) for r in records]
    result=backward_batch(policy,batch)
    targets=[i/max(n,1) for i in range(n)]
    assert result==pytest.approx(np.mean([(.5-q)**2 for q in targets]))
    assert policy.head.bias.grad.item()==pytest.approx(np.mean([.5*(.5-q) for q in targets]))


def test_exact_length_boundary_and_invalid_readout_binding():
    check_length(32768)
    for invalid in (0,32769):
        with pytest.raises(ValueError,match='truncation forbidden'):
            check_length(invalid)
    EncodedInput(('action',),tuple([1]*32768),(32767,),'test')
    with pytest.raises(ValueError,match='binding'):
        EncodedInput(('a','b'),(1,2),(1,1),'test')
    with pytest.raises(ValueError,match='binding'):
        EncodedInput(('a',),(1,2),(2,),'test')


@pytest.mark.parametrize('targets',[[0,0,0],[1,1,1],[.8,.8,.2]])
def test_metric_ties_all_zero_and_all_one(targets):
    row=dict(action_ids=['a','b','c'],target_q=targets,predicted_q=[.5,.5,.4])
    score=observation(row)
    assert score['chosen_id']=='a' and score['regret']==0 and score['best_action_rate']==1
    assert score['soft_target_brier']==2*score['mse']


def test_paired_cluster_bootstrap_and_duplicate_sensitivity():
    selected,baseline=[],[]
    for g in range(5):
        for i in range(g+1):
            row=dict(observation_id=f'{g}-{i}',action_ids=['a','b'],target_q=[0.,1.],
                group_id=str(g),team_number=g,game_id=f'game{g}',fingerprint=f'finger{g}')
            selected.append({**row,'predicted_q':[0.,1.]})
            baseline.append({**row,'predicted_q':[.5,.5]})
    result=paired_bootstrap(selected,baseline)
    assert result['all']['observations']==15 and result['all']['groups']==5
    assert result['all']['contrasts']['mse']['selected_minus_baseline']==-.25
    assert result['all']['contrasts']['mse']['percentile_95_ci']==[-.25,-.25]
    assert report(selected)['all']['duplicates']['first_observation']['observations']==5
    with pytest.raises(ValueError,match='paired'):
        paired_bootstrap(selected,list(reversed(baseline)))


class SaveLinear(nn.Linear):
    def save_pretrained(self,path,**kwargs):
        path=Path(path)
        path.mkdir()
        torch.save(self.state_dict(),path/'weights.pt')


class CheckpointPolicy(nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone=SaveLinear(2,2)
        self.head=nn.Linear(2,1)
        self.target_modules=['toy']

    def trainable_fingerprints(self):
        return fingerprints(self)

    def forward(self,x):
        return self.head(self.backbone(x))


def test_complete_checkpoint_restores_optimizer_and_all_rng_without_extra_update(tmp_path):
    random.seed(17)
    np.random.seed(17)
    torch.manual_seed(17)
    policy=CheckpointPolicy()
    opt=torch.optim.AdamW(policy.parameters(),lr=.001)
    def update(model,optimizer):
        optimizer.zero_grad()
        x=torch.randn(3,2)+random.random()+float(np.random.random())
        model(x).square().mean().backward()
        optimizer.step()
    update(policy,opt)
    frozen=dict(sources={},data_files={},base_files={},tokenizer_files={})
    cp=save_checkpoint(policy,opt,tmp_path/'update-000001',cursor={'epoch':1,'index':8,'updates':1},
        frozen=frozen,initial_base_hashes={})
    set_latest(tmp_path,cp)
    assert latest(tmp_path)==cp
    update(policy,opt)
    expected=policy.trainable_fingerprints()
    restored=CheckpointPolicy()
    restored.backbone.load_state_dict(torch.load(cp/'adapter/weights.pt',weights_only=True))
    restored.head.load_state_dict(torch.load(cp/'value_head.pt',weights_only=True))
    restored_opt=torch.optim.AdamW(restored.parameters(),lr=.001)
    assert restore_training(restored_opt,cp)=={'epoch':1,'index':8,'updates':1}
    update(restored,restored_opt)
    assert restored.trainable_fingerprints()==expected
    with (cp/'value_head.pt').open('ab') as handle:
        handle.write(b'corrupt')
    with pytest.raises(ValueError,match='integrity'):
        validate_checkpoint(cp)
