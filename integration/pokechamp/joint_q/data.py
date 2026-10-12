"""Observation batches and masked loss, independent of a model architecture."""
from __future__ import annotations
from dataclasses import dataclass
import math
from pathlib import Path
from .serializer import JointInput, reorder
from .storage import rows

TARGET_VERSION='pokemon-joint-q-target-v1'


@dataclass(frozen=True)
class TrainingRecord:
    observation_id:str
    input:JointInput
    q:tuple[float,...]

    def __post_init__(self):
        if len(self.q)!=len(self.input.action_ids) or any(not math.isfinite(q) or not 0<=q<=1 for q in self.q):
            raise ValueError('invalid q vector')

    def reordered(self, action_ids):
        q=dict(zip(self.input.action_ids,self.q,strict=True))
        return TrainingRecord(self.observation_id,reorder(self.input,action_ids),tuple(q[k] for k in action_ids))


def load(directory, split=None):
    directory=Path(directory)
    inputs=rows(directory/'inputs.jsonl')
    targets=rows(directory/'targets.jsonl')
    if len({r['observation_id'] for r in inputs})!=len(inputs) or len({r['observation_id'] for r in targets})!=len(targets):
        raise ValueError('duplicate observation')
    by_id={r['observation_id']:r for r in targets}
    if set(by_id)!={r['observation_id'] for r in inputs}:
        raise ValueError('input/target observation coverage differs')
    for row in inputs:
        if split is not None and row['split']!=split:
            continue
        target=by_id[row['observation_id']]
        if target['target_version']!=TARGET_VERSION:
            raise ValueError('target version mismatch')
        if not target['complete'] or row.get('quarantined',False):
            continue
        value=JointInput(row['model_input'])
        if list(value.action_ids)!=row['action_ids'] or target['action_ids']!=row['action_ids']:
            raise ValueError('action ID order mismatch')
        for q,c in zip(target['q'],target['counts'],strict=True):
            if c['n']!=32 or sum(c[k] for k in ('win','draw','loss'))!=32 or q!=(c['win']+.5*c['draw'])/32:
                raise ValueError('q/count mismatch')
        yield TrainingRecord(row['observation_id'],value,tuple(target['q']))


def collate(records):
    import torch
    if not records:
        raise ValueError('empty batch')
    maximum=max(len(r.q) for r in records)
    q=torch.zeros((len(records),maximum),dtype=torch.float32)
    mask=torch.zeros_like(q,dtype=torch.bool)
    for i,r in enumerate(records):
        q[i,:len(r.q)]=torch.tensor(r.q)
        mask[i,:len(r.q)]=True
    return dict(observation_ids=[r.observation_id for r in records],inputs=[r.input for r in records],
                action_ids=[r.input.action_ids for r in records],q_targets=q,action_mask=mask)


def masked_mse(prediction,q_targets,action_mask):
    import torch
    if prediction.shape!=q_targets.shape or action_mask.shape!=prediction.shape or action_mask.dtype!=torch.bool:
        raise ValueError('invalid batch shapes/mask')
    count=action_mask.sum(dim=1)
    if not bool((count>0).all()):
        raise ValueError('observation without valid actions')
    # Mask BEFORE arithmetic so even NaN/inf padding cannot contaminate loss.
    error=prediction.masked_fill(~action_mask,0)-q_targets.masked_fill(~action_mask,0)
    return ((error.square().sum(dim=1))/count).mean()


def masked_argmax(prediction,action_mask):
    import torch
    if prediction.shape!=action_mask.shape or action_mask.dtype!=torch.bool or not bool(action_mask.any(dim=1).all()):
        raise ValueError('invalid selection mask')
    if not bool(torch.isfinite(prediction[action_mask]).all()):
        raise ValueError('nonfinite valid candidate value')
    return prediction.masked_fill(~action_mask,float('-inf')).argmax(dim=1)


def candidate_records(record):
    for aid,q in zip(record.input.action_ids,record.q,strict=True):
        yield dict(schema='pokemon-action-value-v1',input_ref=record.observation_id,
                   action_id=aid,target_probabilities=[q,1-q])
