from pathlib import Path
import time
import torch
from ..storage import atomic, read, rows, jsonl
from .artifacts import (assert_frozen, latest, now, restore_training, save_checkpoint,
                        set_latest, validate_checkpoint)
from .config import CONFIG
from .metrics import report
from .model import JointValuePolicy, load_base, seed_all, tokenizer
from .prepare import aligned_records, encoded_rows
from .runtime import Progress, backward_batch, check_gradients, loss


def optimizer(policy):
    return torch.optim.AdamW([p for p in policy.parameters() if p.requires_grad],lr=CONFIG['lr'],
        betas=tuple(CONFIG['betas']),weight_decay=0)


def prediction_rows(policy, pairs, metadata, progress, *, phase):
    result=[]
    policy.eval()
    for i,(r,e) in enumerate(pairs):
        start=time.perf_counter()
        with torch.no_grad(),progress.timed():
            q=policy.values(e).cpu().tolist()
        result.append(dict(observation_id=r.observation_id,action_ids=list(e.action_ids),
            predicted_q=q,target_q=list(r.q),tokens=len(e.input_ids),
            prompt_sha256=e.prompt_sha256,readout_positions=list(e.readout_positions),
            seconds=time.perf_counter()-start,**metadata[r.observation_id]))
        if (i+1)%10==0 or i+1==len(pairs):
            progress.update(phase=phase,observations=i+1,total_observations=len(pairs))
    return result


def metadata(out):
    return {r['observation_id']:{k:v for k,v in r.items() if k!='observation_id'}
            for r in rows(Path(out)/'prepared/metadata.jsonl')}


def preflight(data, out):
    frozen=assert_frozen(out,data)
    directory=Path(out)/'preflight'
    if (directory/'report.json').exists():
        raise FileExistsError('preflight already completed')
    progress=Progress(directory,'preflight')
    seed_all()
    policy=JointValuePolicy(load_base(directory/'loading.json'),tokenizer(Path(out)/'prepared/tokenizer'))
    initial_base,initial_trainable=policy.base_fingerprints(),policy.trainable_fingerprints()
    pairs=aligned_records(data,encoded_rows(out,'train'),'train')
    longest_name=max((name for name in frozen['token_summary'] if name.startswith('train-epoch')),
                     key=lambda name:frozen['token_summary'][name]['maximum'])
    longest_epoch=int(longest_name.removeprefix('train-epoch').removesuffix('.jsonl'))
    longest_pairs=pairs if longest_epoch==0 else aligned_records(data,encoded_rows(out,'train',longest_epoch),'train')
    chosen=[max(longest_pairs,key=lambda x:len(x[1].input_ids)),
            min(pairs,key=lambda x:len(x[0].q)),max(pairs,key=lambda x:len(x[0].q))]
    unique={r.observation_id:(r,e) for r,e in chosen}
    checks=[]
    policy.train()
    for r,e in unique.values():
        policy.zero_grad(set_to_none=True)
        torch.cuda.reset_peak_memory_stats()
        progress.update(phase='forward_backward',observation_id=r.observation_id,tokens=len(e.input_ids))
        start=time.perf_counter()
        with progress.timed():
            q=policy.values(e)
            value=loss(q,r.q)
            value.backward()
            norm=check_gradients(policy)
        checks.append(dict(observation_id=r.observation_id,tokens=len(e.input_ids),candidates=len(r.q),
            loss=float(value.detach()),gradient_norm=norm,seconds=time.perf_counter()-start,
            allocated_bytes=torch.cuda.max_memory_allocated(),reserved_bytes=torch.cuda.max_memory_reserved()))
    # Production is microbatch1 with no token padding. The explicit masked probe
    # proves that adding right padding cannot affect any readout.
    short_r,short_e=min(pairs,key=lambda x:len(x[1].input_ids))
    policy.eval()
    policy.zero_grad(set_to_none=True)
    with torch.no_grad():
        with progress.timed():
            raw=policy.values(short_e)
        with progress.timed():
            padded=policy.values(short_e,padding=17)
    padding_difference=float((raw-padded).abs().max())
    atomic(directory/'padding-check.json',dict(observation_id=short_r.observation_id,
        raw_q=raw.cpu().tolist(),padded_q=padded.cpu().tolist(),maximum_difference=padding_difference))
    if padding_difference>1e-4:
        raise ValueError('padding changed valid candidate q')
    if initial_base!=policy.base_fingerprints() or initial_trainable!=policy.trainable_fingerprints():
        raise ValueError('preflight unexpectedly updated parameters')
    seconds_per_token=sum(c['seconds'] for c in checks)/sum(c['tokens'] for c in checks)
    training_tokens=sum(frozen['token_summary'][f'train-epoch{e}.jsonl']['tokens'] for e in (1,2,3))
    result=dict(passed=True,at=now(),checks=checks,optimizer_updates=0,
        padding_max_q_difference=padding_difference,base_unchanged=True,trainable_unchanged=True,
        initial_base_fingerprints=initial_base,initial_trainable_fingerprints=initial_trainable,
        estimated_train_forward_backward_seconds=seconds_per_token*training_tokens,
        estimate_method='boundary-case seconds/token; excludes validation/checkpoint overhead',
        config=CONFIG,frozen_manifest=frozen)
    atomic(directory/'report.json',result,immutable=True)
    progress.update(phase='complete')
    return result


def train(data,out,resume=False):
    frozen=assert_frozen(out,data)
    if not read(Path(out)/'preflight/report.json')['passed']:
        raise ValueError('preflight must pass before training')
    directory=Path(out)/'training'
    if (directory/'selection.json').exists():
        return read(directory/'selection.json')
    progress=Progress(directory,'train')
    tok=tokenizer(Path(out)/'prepared/tokenizer')
    seed_all()
    checkpoint=latest(directory) if resume else None
    if not resume and (directory/'latest.json').exists():
        raise FileExistsError('use --resume for complete checkpoint continuation')
    policy=JointValuePolicy(load_base(directory/f'loading-{time.time_ns()}.json'),tok,checkpoint)
    opt=optimizer(policy)
    base_hashes=policy.base_fingerprints()
    preflight_report=read(Path(out)/'preflight/report.json')
    if base_hashes!=preflight_report['initial_base_fingerprints']:
        raise ValueError('training base differs from verified preflight')
    cursor=dict(epoch=1,index=0,updates=0)
    if resume:
        cursor=restore_training(opt,checkpoint)
        if policy.trainable_fingerprints()!=validate_checkpoint(checkpoint)['trainable_fingerprints']:
            raise ValueError('restored trainable tensors differ')
    else:
        if policy.trainable_fingerprints()!=preflight_report['initial_trainable_fingerprints']:
            raise ValueError('initial head/LoRA initialization is not reproducible')
        cp=save_checkpoint(policy,opt,directory/'initial',cursor=cursor,frozen=frozen,initial_base_hashes=base_hashes)
        set_latest(directory,cp)
    meta=metadata(out)
    validation=aligned_records(data,encoded_rows(out,'validation'),'validation')
    if not (directory/'validation-initial.jsonl').exists():
        if checkpoint is not None and checkpoint.name!='initial':
            raise ValueError('initial validation evidence missing after training updates')
        initial_prediction=prediction_rows(policy,validation,meta,progress,phase='validation_initial')
        jsonl(directory/'validation-initial.jsonl',initial_prediction)
        atomic(directory/'metrics-initial.json',report(initial_prediction),immutable=True)
    for epoch in range(cursor['epoch'],CONFIG['epochs']+1):
        pairs=aligned_records(data,encoded_rows(out,'train',epoch),'train')
        offset=cursor['index'] if epoch==cursor['epoch'] else 0
        if offset%CONFIG['accumulation'] and offset!=len(pairs):
            raise ValueError('resume cursor is inside a partial optimizer batch')
        policy.train()
        for begin in range(offset,len(pairs),CONFIG['accumulation']):
            batch=pairs[begin:begin+CONFIG['accumulation']]
            opt.zero_grad(set_to_none=True)
            def on_observation(r,e):
                progress.update(phase='train',epoch=epoch,updates=cursor['updates'],
                    observation_id=r.observation_id,index=begin,tokens=len(e.input_ids))
            accumulated=backward_batch(policy,batch,progress,on_observation)
            norm=check_gradients(policy)
            clipped=torch.nn.utils.clip_grad_norm_([p for p in policy.parameters() if p.requires_grad],
                                                   CONFIG['gradient_clip'],error_if_nonfinite=True)
            opt.step()
            if any(not bool(torch.isfinite(p).all()) for p in policy.parameters() if p.requires_grad):
                raise FloatingPointError('nonfinite parameter after optimizer update')
            cursor=dict(epoch=epoch,index=begin+len(batch),updates=cursor['updates']+1)
            cp=save_checkpoint(policy,opt,directory/f'update-{cursor["updates"]:06d}',cursor=cursor,
                               frozen=frozen,initial_base_hashes=base_hashes)
            set_latest(directory,cp)
            event=dict(at=now(),cursor=cursor,observations=len(batch),loss=accumulated,
                       gradient_norm=norm,pre_clip_norm=float(clipped))
            with (directory/'updates.jsonl').open('a') as handle:
                import json
                handle.write(json.dumps(event)+'\n')
            progress.update(phase='optimizer_complete',**cursor,loss=accumulated)
        if policy.base_fingerprints()!=base_hashes:
            raise ValueError('frozen base changed during training')
        prediction=prediction_rows(policy,validation,meta,progress,phase=f'validation_epoch{epoch}')
        jsonl(directory/f'validation-epoch{epoch}.jsonl',prediction)
        atomic(directory/f'metrics-epoch{epoch}.json',report(prediction),immutable=True)
        cursor=dict(epoch=epoch+1,index=0,updates=cursor['updates'])
        cp=save_checkpoint(policy,opt,directory/f'epoch-{epoch}',cursor=cursor,frozen=frozen,initial_base_hashes=base_hashes)
        set_latest(directory,cp)
    if cursor['updates']!=CONFIG['updates']:
        raise ValueError('optimizer update denominator mismatch')
    initial=validate_checkpoint(directory/'initial')['trainable_fingerprints']
    final=policy.trainable_fingerprints()
    if not any(initial[k]!=final[k] for k in initial if 'lora_' in k) or not any(initial[k]!=final[k] for k in initial if k.startswith('head.')):
        raise ValueError('LoRA/value head did not both change')
    candidates=[(read(directory/f'metrics-epoch{e}.json')['all']['metrics']['mse'],e) for e in (1,2,3)]
    mse,epoch=min(candidates)
    selection=dict(selected_epoch=epoch,validation_mse=mse,checkpoint=str((directory/f'epoch-{epoch}').resolve()),
        epoch_validation_mse={str(e):m for m,e in candidates},updates=cursor['updates'],
        base_unchanged=True,lora_changed=True,head_changed=True,at=now())
    atomic(directory/'selection.json',selection,immutable=True)
    progress.update(phase='complete',**selection)
    return selection
