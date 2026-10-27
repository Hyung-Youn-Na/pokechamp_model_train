"""Three-rank worker; controller owns UUID locks and enforces process RSS."""
import argparse
import contextlib
import datetime
import json
import math
import os
from pathlib import Path
import random
import time
import traceback
import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from transformers import AutoTokenizer
from .config import CONFIG
from .data import TokenStore,epoch_batches,microbatches,dump,sha,rows
from .model import load_model,frozen_fingerprint,ChoiceReadout,collate,forward,weighted_numerator
from .prepare import verify
from .metrics import prediction,summarize,select


def seed(value):random.seed(value);np.random.seed(value);torch.manual_seed(value);torch.cuda.manual_seed(value)
def rng():return dict(python=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state(),cuda=torch.cuda.get_rng_state())
def restore_rng(s):random.setstate(s['python']);np.random.set_state(s['numpy']);torch.set_rng_state(s['torch']);torch.cuda.set_rng_state(s['cuda'])
def read(p):return json.loads(Path(p).read_text())


def serial_load(device,adapter=None,trainable=False):
    import gc
    model=None
    for owner in range(3):
        if dist.get_rank()==owner:model=load_model(device,adapter=adapter,trainable=trainable);gc.collect()
        dist.barrier()
    return model


def usage():
    torch.cuda.synchronize();a=torch.cuda.max_memory_allocated();r=torch.cuda.max_memory_reserved()
    if max(a,r)>=CONFIG['memory_limit_bytes']:raise RuntimeError('GPU memory budget')
    return dict(allocated_peak=a,reserved_peak=r)


def optimizer_for(model):
    opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=CONFIG['learning_rate'],
           betas=CONFIG['betas'],eps=CONFIG['eps'],weight_decay=0.)
    def schedule(s):
        if s<CONFIG['warmup']:return (s+1)/CONFIG['warmup']
        return .5*(1+math.cos(math.pi*(s-CONFIG['warmup'])/(CONFIG['steps']-CONFIG['warmup'])))
    return opt,torch.optim.lr_scheduler.LambdaLR(opt,schedule)


def checkpoint(model,opt,scheduler,output,step,rank,cap,root='checkpoints'):
    path=output/root/f'step-{step:04d}'
    if rank==0:path.mkdir(parents=True,exist_ok=False)
    dist.barrier();torch.save(rng(),path/f'rng-{rank}.pt');dist.barrier()
    if rank==0:
        model.save_pretrained(path/'adapter')
        epoch,update=divmod(step,CONFIG['steps_per_epoch'])
        torch.save(dict(optimizer=opt.state_dict(),scheduler=scheduler.state_dict(),step=step,epoch=epoch,next_update=update,
            config=CONFIG,microbatch=cap,prepared_sha=sha(output/'prepared.json')),path/'training.pt')
        dump(path/'complete.json',dict(step=step,files={str(p.relative_to(path)):sha(p) for p in path.rglob('*') if p.is_file()}))
    dist.barrier();return path


def restore_checkpoint(path,model,opt,scheduler,output,rank,cap):
    for name,h in read(path/'complete.json')['files'].items():assert sha(path/name)==h
    saved=torch.load(path/'training.pt',map_location='cpu',weights_only=False)
    assert saved['config']==CONFIG and saved['prepared_sha']==sha(output/'prepared.json') and saved['microbatch']==cap
    assert (saved['epoch'],saved['next_update'])==divmod(saved['step'],1356)
    # Loading into the existing PEFT instance keeps the DDP parameter identities.
    from peft import set_peft_model_state_dict
    from safetensors.torch import load_file
    result=set_peft_model_state_dict(model,load_file(str(path/'adapter/adapter_model.safetensors')))
    assert not result.unexpected_keys
    opt.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler'])
    actual=opt.state_dict();assert actual['param_groups']==saved['optimizer']['param_groups']
    for key,state in saved['optimizer']['state'].items():
        for field,value in state.items():
            restored=actual['state'][key][field]
            if isinstance(value,torch.Tensor):assert torch.equal(value.cpu(),restored.cpu()),('optimizer restore',key,field)
            else:assert value==restored
    assert scheduler.state_dict()==saved['scheduler']
    restore_rng(torch.load(path/f'rng-{rank}.pt',map_location='cpu',weights_only=False));return saved['step']


def update(reader,model,opt,scheduler,store,indices,rank,device,pad,cap):
    opt.zero_grad(set_to_none=True);denominator=float(store.weights[indices].sum())
    local=indices[rank::3];batches=list(microbatches(local,store.lengths,cap));num=0.;real=0;padded=0
    started=time.monotonic()
    for j,ix in enumerate(batches):
        b=collate([store[i] for i in ix],pad,device)
        with reader.no_sync() if j<len(batches)-1 else contextlib.nullcontext():
            z=forward(reader,b);n=weighted_numerator(z,b['targets'],b['weights'])
            (n*(3/denominator)).backward();num+=float(n.detach())
        real+=int(b['attention_mask'].sum());padded+=b['input_ids'].numel()
    params=[p for p in model.parameters() if p.requires_grad]
    grad=torch.nn.utils.clip_grad_norm_(params,CONFIG['clip'],error_if_nonfinite=True)
    opt.step();scheduler.step()
    assert all(p.grad is None for p in model.parameters() if not p.requires_grad)
    assert all(v.dtype==torch.float32 for s in opt.state.values() for k,v in s.items() if k in ['exp_avg','exp_avg_sq'])
    totals=torch.tensor([num,real,padded],dtype=torch.float64,device=device);dist.all_reduce(totals)
    return dict(loss=float(totals[0])/denominator,weight_denominator=denominator,examples=len(indices),
                input_tokens=int(totals[1]),padded_tokens=int(totals[2]),gradient_norm=float(grad),
                seconds=time.monotonic()-started,learning_rate=scheduler.get_last_lr()[0],**usage())


def evaluate(model,store,output,name,rank,device,pad,cap,base=False):
    destination=output/'predictions'/name;destination.mkdir(parents=True,exist_ok=True)
    path=destination/f'rank-{rank}.jsonl';model.eval();reader=ChoiceReadout(model)
    with model.disable_adapter() if base else contextlib.nullcontext(),torch.inference_mode(),path.open('x') as f:
        for ix in microbatches(list(range(rank,len(store),3)),store.lengths,cap):
            rs=[store[i] for i in ix];z=forward(reader,collate(rs,pad,device)).cpu().tolist()
            for r,logits in zip(rs,z):f.write(json.dumps(prediction(r,logits[:len(r['label_ids'])]),allow_nan=False)+'\n')
            f.flush();usage()
    dist.barrier();metric=None
    if rank==0:
        results=sum((list(rows(destination/f'rank-{r}.jsonl')) for r in range(3)),[])
        assert len(results)==len(store) and {r['id'] for r in results}=={m['id'] for m in store.metadata}
        metric=summarize(results);dump(destination/'metrics.json',metric)
        print(json.dumps(dict(event='evaluation',name=name,metrics=metric)),flush=True)
    dist.barrier();model.train();return metric


def equivalence(model,store,rank,device,pad,cap):
    model.eval();reader=ChoiceReadout(model)
    # Diverse short examples exercise real padding and 2/11 candidate masks.
    selected=[]
    for count in [2,11,3,6]:
        matches=[i for i in range(len(store)) if int((store.labels[i]>=0).sum())==count and store.lengths[i]<=500]
        selected.extend(matches[rank:rank+2])
    selected=selected[:8];batches=list(microbatches(selected,store.lengths,cap));worst=0.;gradient_error=0.
    for ix in batches:
        rs=[store[i] for i in ix];batch=collate(rs,pad,device)
        with torch.no_grad():
            together=forward(reader,batch).softmax(-1)
            for i,r in enumerate(rs):
                single=forward(reader,collate([r],pad,device)).softmax(-1)[0]
                difference=float((single-together[i,:len(single)]).abs().max());worst=max(worst,difference)
                if difference>0.002 or int(single.argmax())!=int(together[i,:len(single)].argmax()):
                    raise ArithmeticError(f'batch readout inequivalent: probability delta {difference}')
        model.zero_grad(set_to_none=True);z=forward(reader,batch)
        (weighted_numerator(z,batch['targets'],batch['weights'])/batch['weights'].sum()).backward()
        expected={n:p.grad.detach().clone() for n,p in model.named_parameters() if p.requires_grad and p.grad is not None}
        model.zero_grad(set_to_none=True)
        for r in rs:
            one=collate([r],pad,device);z=forward(reader,one)
            (weighted_numerator(z,one['targets'],one['weights'])/batch['weights'].sum()).backward()
        numer=sum(float((p.grad-expected[n]).square().sum()) for n,p in model.named_parameters() if n in expected)
        denom=sum(float(v.square().sum()) for v in expected.values())
        error=math.sqrt(numer/max(denom,1e-30));gradient_error=max(gradient_error,error)
        if error>0.02:raise ArithmeticError(f'batch gradient inequivalent: relative L2 {error}')
        del expected
    model.zero_grad(set_to_none=True);model.train();return dict(probability_max_error=worst,gradient_relative_l2=gradient_error)


def preflight(model,store,output,rank,device,pad,cap):
    before=frozen_fingerprint(model);initial={n:p.detach().clone() for n,p in model.named_parameters() if p.requires_grad}
    result=equivalence(model,store,rank,device,pad,cap);dist.barrier()
    opt,scheduler=optimizer_for(model);reader=DDP(ChoiceReadout(model),device_ids=[rank],broadcast_buffers=False)
    seed(CONFIG['seed']+rank)
    indices=list(np.argsort(store.lengths)[-3:][::-1])
    for count in [2,11]:indices.extend([i for i in range(len(store)) if (store.labels[i]>=0).sum()==count][:3])
    for i in next(epoch_batches(len(store),0)):
        if i not in indices:indices.append(i)
        if len(indices)==96:break
    assert len(indices)==96 and max(store.lengths[indices])==max(store.lengths)
    run=update(reader,model,opt,scheduler,store,indices,rank,device,pad,cap)
    assert frozen_fingerprint(model)==before
    assert any(not torch.equal(initial[n],p) for n,p in model.named_parameters() if n in initial);del initial
    dump(output/f'preflight-v2-{cap}-update-rank-{rank}.json',dict(stage='stress_update_passed',microbatch=cap,**result,**run))
    path=checkpoint(model,opt,scheduler,output,1,rank,cap,root=f'{CONFIG["preflight_checkpoint_prefix"]}-{cap}-checkpoints')
    # Exercise exact adapter/optimizer/scheduler/RNG restoration in the GPU process.
    saved={n:p.detach().clone() for n,p in model.named_parameters() if p.requires_grad};saved_rng=rng()
    reference={n:p.detach().clone() for n,p in model.named_parameters() if p.requires_grad}
    follow=next(epoch_batches(len(store),1))[-69:]
    update(reader,model,opt,scheduler,store,follow,rank,device,pad,cap)
    expected={n:p.detach().clone() for n,p in model.named_parameters() if p.requires_grad}
    restore_checkpoint(path,model,opt,scheduler,output,rank,cap)
    assert all(torch.equal(saved[n],p) for n,p in model.named_parameters() if n in saved)
    assert torch.equal(rng()['torch'],saved_rng['torch']) and torch.equal(rng()['cuda'],saved_rng['cuda'])
    update(reader,model,opt,scheduler,store,follow,rank,device,pad,cap)
    maxdelta=max(float((p-expected[n]).abs().max()) for n,p in model.named_parameters() if n in expected)
    assert maxdelta<=1e-7,('checkpoint continuation differs',maxdelta)
    assert frozen_fingerprint(model)==before
    dump(output/f'preflight-{cap}-rank-{rank}.json',dict(passed=True,microbatch=cap,base_frozen=True,lora_updated=True,
            checkpoint_resume_max_delta=maxdelta,**result,**run))
    dist.barrier()
    if rank==0:
        results=[read(output/f'preflight-{cap}-rank-{r}.json') for r in range(3)]
        dump(output/f'preflight-{cap}.json',dict(passed=True,microbatch=cap,ranks=results,
             conservative_training_seconds=max(r['seconds'] for r in results)*4068,
             note='96-row stress update includes longest inputs; evaluation/loading/checkpoint overhead excluded'))


def train(model,store,output,rank,device,pad,cap,resume):
    opt,scheduler=optimizer_for(model);reader=DDP(ChoiceReadout(model),device_ids=[rank],broadcast_buffers=False)
    validation=TokenStore(output/'validation');epochs=read(output/'epochs.json') if (output/'epochs.json').exists() else []
    start=restore_checkpoint(Path(resume),model,opt,scheduler,output,rank,cap) if resume else 0
    if not resume:
        seed(CONFIG['seed']+rank);checkpoint(model,opt,scheduler,output,0,rank,cap)
        state=rng();evaluate(model,validation,output,'validation-base',rank,device,pad,cap,base=True);restore_rng(state)
    else:
        # Refuse replay of partial updates or partial evaluations. Only an exact complete frontier can resume.
        for r in range(3):
            p=output/f'train-rank-{r}.jsonl'
            if p.exists():assert max([0]+[v['step'] for v in rows(p)])==start,'updates beyond checkpoint cannot be replayed'
        assert (output/'predictions/validation-base/metrics.json').exists()
        if start and start%1356==0 and not any(e['epoch']==start//1356 for e in epochs):
            state=rng();m=evaluate(model,validation,output,f'validation-epoch-{start//1356}',rank,device,pad,cap);restore_rng(state)
            if rank==0:epochs.append(dict(epoch=start//1356,metrics=m));dump(output/'epochs.json',epochs)
    with (output/f'train-rank-{rank}.jsonl').open('a') as curve:
        for epoch in range(start//1356,3):
            for update_index,indices in enumerate(epoch_batches(len(store),epoch)):
                step=epoch*1356+update_index+1
                if step<=start:continue
                result=update(reader,model,opt,scheduler,store,indices,rank,device,pad,cap)
                result.update(step=step,epoch=epoch+1);curve.write(json.dumps(result)+'\n');curve.flush()
                if rank==0:dump(output/'progress.json',result);print(json.dumps(dict(event='update',**result)),flush=True)
                if step%128==0 or step%1356==0:checkpoint(model,opt,scheduler,output,step,rank,cap)
            state=rng();m=evaluate(model,validation,output,f'validation-epoch-{epoch+1}',rank,device,pad,cap);restore_rng(state)
            if rank==0:epochs.append(dict(epoch=epoch+1,metrics=m));dump(output/'epochs.json',epochs)
    if rank==0:dump(output/'selection.json',select(epochs))
    dist.barrier()


def run(args):
    output=Path(args.output);verify(output);rank=int(os.environ['LOCAL_RANK']);assert int(os.environ['WORLD_SIZE'])==3
    assert os.environ.get('CUBLAS_WORKSPACE_CONFIG')==CONFIG['cublas_workspace_config']
    torch.use_deterministic_algorithms(CONFIG['deterministic_algorithms'])
    torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=CONFIG['cudnn_benchmark']
    torch.set_num_threads(4);torch.cuda.set_device(rank);device=torch.device(f'cuda:{rank}')
    dist.init_process_group('nccl',timeout=datetime.timedelta(hours=4));seed(CONFIG['seed'])
    tok=AutoTokenizer.from_pretrained(output/'tokenizer',local_files_only=True);pad=tok.pad_token_id
    assert pad is not None
    try:
        cap=args.microbatch if args.action=='preflight' else read(output/'preflight-selected.json')['microbatch']
        if args.action in ['preflight','train']:
            model=serial_load(device,trainable=True);store=TokenStore(output/'train')
            if args.action=='preflight':preflight(model,store,output,rank,device,pad,cap)
            else:train(model,store,output,rank,device,pad,cap,args.resume)
        elif args.action=='evaluate':
            chosen=read(output/'selection.json')['epoch'];adapter=output/'checkpoints'/f'step-{chosen*1356:04d}'/'adapter'
            model=serial_load(device,adapter=adapter);store=TokenStore(output/'test')
            evaluate(model,store,output,'test-base',rank,device,pad,cap,base=True)
            evaluate(model,store,output,'test-selected',rank,device,pad,cap)
        elif args.action=='diagnose':
            chosen=read(output/'selection.json')['epoch'];adapter=output/'checkpoints'/f'step-{chosen*1356:04d}'/'adapter'
            model=serial_load(device,adapter=adapter);store=TokenStore(output/'diagnostic')
            evaluate(model,store,output,'diagnostic-base',rank,device,pad,cap,base=True)
            evaluate(model,store,output,'diagnostic-selected',rank,device,pad,cap)
        elif args.action=='reload':
            model=serial_load(device,adapter=output/'adapter-selected');model.eval();reader=ChoiceReadout(model)
            store=TokenStore(output/'validation');chosen=read(output/'selection.json')['epoch']
            ref={r['id']:r for q in range(3) for r in rows(output/'predictions'/f'validation-epoch-{chosen}'/f'rank-{q}.jsonl')}
            selected={}
            for i,m in enumerate(store.metadata):selected.setdefault(m['domain'],[]).append(i)
            chosen_indices=set(sum((v[:3] for v in selected.values()),[]));results=[]
            with torch.inference_mode():
                for ix in microbatches(list(range(rank,len(store),3)),store.lengths,cap):
                    if not chosen_indices.intersection(ix):continue
                    rs=[store[i] for i in ix];zs=forward(reader,collate(rs,pad,device)).double()
                    for i,row,z in zip(ix,rs,zs):
                        if i not in chosen_indices:continue
                        p=z[:len(row['label_ids'])].softmax(-1).cpu().numpy();r=ref[row['id']]
                        error=float(np.max(abs(p-np.array(r['probabilities']))));assert error<=1e-5 and int(p.argmax())==r['choice']
                        results.append(dict(id=row['id'],probability_max_error=error))
            dump(output/f'reload-rank-{rank}.json',dict(passed=True,rows=results))
        else:raise ValueError(args.action)
        dist.barrier()
    except BaseException as exc:
        dump(output/f'failure-{args.action}-{args.microbatch}-rank-{rank}-{time.time_ns()}.json',dict(error=repr(exc),traceback=traceback.format_exc()))
        raise
    finally:dist.destroy_process_group()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','train','evaluate','diagnose','reload']);p.add_argument('--output',required=True)
    p.add_argument('--microbatch',type=int,default=8);p.add_argument('--resume');run(p.parse_args())
