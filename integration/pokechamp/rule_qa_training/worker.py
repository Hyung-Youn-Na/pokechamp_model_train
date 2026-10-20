"""Three-rank worker. Launcher owns physical GPU locks before importing Torch."""
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
from torch.nn.parallel import DistributedDataParallel
from transformers import AutoTokenizer

from .config import CONFIG
from .data import read_json, read_rows, write_json, verify_prepared, sha
from .metrics import score, summarize, choose
from .model import load_model, assistant_loss, frozen_fingerprint


def rng_state():
    return dict(python=random.getstate(), numpy=np.random.get_state(), torch=torch.get_rng_state(),
                cuda=torch.cuda.get_rng_state())


def restore_rng(state):
    random.setstate(state['python']); np.random.set_state(state['numpy'])
    torch.set_rng_state(state['torch']); torch.cuda.set_rng_state(state['cuda'])


def seed(value):
    random.seed(value); np.random.seed(value); torch.manual_seed(value); torch.cuda.manual_seed(value)


def memory(device):
    torch.cuda.synchronize(device)
    peak = torch.cuda.max_memory_allocated(device)
    reserved = torch.cuda.max_memory_reserved(device)
    if max(peak,reserved) >= CONFIG['memory_limit_bytes']:
        raise RuntimeError('GPU memory limit reached')
    return dict(peak_allocated=peak, peak_reserved=reserved)


def checkpoint(model, optimizer, scheduler, output, step, rank):
    path = output/'checkpoints'/f'step-{step:04d}'
    if rank == 0:
        path.mkdir(parents=True, exist_ok=False)
    dist.barrier()
    torch.save(rng_state(), path/f'rng-{rank}.pt')
    dist.barrier()
    if rank == 0:
        model.save_pretrained(path/'adapter')
        torch.save(dict(optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict(),step=step,
                        epoch=step//192, next_update=step%192, config=CONFIG,
                        prepared_sha=sha(output/'prepared.json')), path/'training.pt')
        write_json(path/'complete.json',dict(step=step, ranks=3,
                   files={str(p.relative_to(path)):sha(p) for p in path.rglob('*') if p.is_file()}))
    dist.barrier()


def evaluate(model, rows, tokenizer, output, name, rank, device, base=False):
    model.eval()
    path = output/'predictions'/name
    path.mkdir(parents=True, exist_ok=True)
    destination = path/f'rank-{rank}.jsonl'
    if destination.exists():
        raise FileExistsError(f'evaluation cannot be repeated: {destination}')
    context = model.disable_adapter() if base else contextlib.nullcontext()
    with context, torch.inference_mode(), destination.open('x') as stream:
        for row in rows[rank::3]:
            nll = float(assistant_loss(model,row,device))
            if not math.isfinite(nll):
                raise FloatingPointError('non-finite evaluation NLL')
            ids = torch.tensor([row['input_ids'][:row['prefix_length']]],device=device)
            with torch.autocast('cuda',dtype=torch.bfloat16):
                generated = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids),
                    do_sample=False,max_new_tokens=CONFIG['max_new_tokens'],use_cache=True,
                    pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id,
                    logits_to_keep=1)
            answer = generated[0,ids.shape[1]:].tolist()
            text = tokenizer.decode(answer,skip_special_tokens=True)
            result = {k:row[k] for k in ['id','rule_id','group_id','scenario_id','representation','component','answer','answer_id']}
            result.update(score(row,text), raw_response=text, generated_ids=answer, nll=nll,
                          capped=len(answer)==CONFIG['max_new_tokens'] and answer[-1]!=tokenizer.eos_token_id)
            stream.write(json.dumps(result,ensure_ascii=False)+'\n'); stream.flush()
            memory(device)
    dist.barrier()
    metrics = None
    if rank == 0:
        all_rows = sum((read_rows(path/f'rank-{r}.jsonl') for r in range(3)),[])
        assert {r['id'] for r in all_rows} == {r['id'] for r in rows} and len(all_rows)==len(rows)
        metrics = summarize(all_rows)
        write_json(path/'metrics.json', metrics)
        print(json.dumps(dict(event='evaluation',name=name,metrics=metrics['forms'])),flush=True)
    dist.barrier()
    model.train()
    return metrics


def train_updates(ddp, model, optimizer, scheduler, rows, output, rank, device, start=0, preflight=False):
    model.train()
    steps = 1 if preflight else CONFIG['steps']
    initial = frozen_fingerprint(model) if preflight else None
    before = {n:p.detach().clone() for n,p in model.named_parameters() if p.requires_grad} if preflight else {}
    curve = (output/f'{"preflight" if preflight else "train"}-rank-{rank}.jsonl').open('a')
    started = time.monotonic()
    for step in range(start,steps):
        epoch, update = divmod(step,192)
        order = list(range(len(rows)))
        if not preflight:
            random.Random(CONFIG['seed']+epoch).shuffle(order)
        batch = [rows[i] for i in order[update*24:(update+1)*24]][rank::3]
        assert len(batch)==8
        optimizer.zero_grad(set_to_none=True)
        total = 0
        for micro,row in enumerate(batch):
            sync = ddp.no_sync() if micro<7 else contextlib.nullcontext()
            with sync:
                loss = assistant_loss(ddp,row,device)
                if not torch.isfinite(loss):
                    raise FloatingPointError('non-finite train loss')
                (loss/8).backward()
                total += float(loss.detach())/8
        grad = torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],CONFIG['clip'],error_if_nonfinite=True)
        optimizer.step(); scheduler.step()
        assert all(value.dtype==torch.float32 for state in optimizer.state.values()
                   for key,value in state.items() if key in ('exp_avg','exp_avg_sq'))
        assert all(p.grad is None for p in model.parameters() if not p.requires_grad)
        usage = memory(device)
        result = dict(step=step+1, epoch=epoch+1, loss=total, gradient_norm=float(grad),
                      learning_rate=scheduler.get_last_lr()[0], elapsed=time.monotonic()-started, **usage)
        curve.write(json.dumps(result)+'\n');curve.flush()
        if rank==0:
            print(json.dumps(dict(event='step',**result)),flush=True)
            write_json(output/'progress.json',result)
        if preflight:
            assert frozen_fingerprint(model)==initial, 'base weights changed'
            assert any(not torch.equal(before[n],p) for n,p in model.named_parameters() if p.requires_grad), 'LoRA unchanged'
            write_json(output/f'preflight-rank-{rank}.json',dict(passed=True,base_frozen=True,lora_updated=True,**result))
        else:
            if (step+1)%48==0:
                checkpoint(model,optimizer,scheduler,output,step+1,rank)
            if (step+1)%192==0:
                yield epoch+1
    curve.close()


def run(action, output, resume=None):
    rank = int(os.environ['LOCAL_RANK'])
    assert int(os.environ['WORLD_SIZE'])==3
    assert len(os.environ['CUDA_VISIBLE_DEVICES'].split(','))==3
    output = Path(output)
    verify_prepared(output)
    torch.set_num_threads(4)
    torch.cuda.set_device(rank)
    device = torch.device(f'cuda:{rank}')
    dist.init_process_group('nccl',timeout=datetime.timedelta(hours=4))
    seed(CONFIG['seed'])
    tokenizer = AutoTokenizer.from_pretrained(output/'tokenizer',local_files_only=True)
    try:
        if action=='evaluate':
            selected = read_json(output/'selection.json')
            adapter = output/'checkpoints'/f'step-{selected["epoch"]*192:04d}'/'adapter'
            model = load_model(device,adapter=adapter)
            rows = read_rows(output/'test.jsonl')
            evaluate(model,rows,tokenizer,output,'test-base',rank,device,base=True)
            evaluate(model,rows,tokenizer,output,'test-selected',rank,device)
        elif action=='reload':
            model = load_model(device,adapter=output/'adapter')
            model.eval()
            rows = read_rows(output/'validation.jsonl')[rank:rank+1]
            with torch.inference_mode():
                nll = float(assistant_loss(model,rows[0],device))
            reference = {r['id']:r for r in sum((read_rows(output/'predictions'/f'validation-epoch-{read_json(output/"selection.json")["epoch"]}'/f'rank-{r}.jsonl') for r in range(3)),[])}
            assert abs(nll-reference[rows[0]['id']]['nll'])<1e-5
            write_json(output/f'reload-rank-{rank}.json',dict(passed=True,id=rows[0]['id'],nll=nll))
        else:
            if action=='train':
                assert read_json(output/'preflight.json')['passed']
                if (output/'selection.json').exists():
                    raise RuntimeError('training already selected')
            adapter = Path(resume)/'adapter' if resume else None
            model = load_model(device,adapter=adapter,trainable=True)
            optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                lr=CONFIG['learning_rate'],betas=tuple(CONFIG['betas']),weight_decay=CONFIG['weight_decay'])
            def schedule(step):
                return step/18 if step<18 else .5*(1+math.cos(math.pi*(step-18)/(576-18)))
            scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer,schedule)
            # Preflight must actually update LoRA; use the first nonzero warmup LR.
            if action=='preflight':
                for group in optimizer.param_groups:group['lr']=CONFIG['learning_rate']/18
            ddp = DistributedDataParallel(model,device_ids=[rank],broadcast_buffers=False,find_unused_parameters=False)
            start = 0
            if resume:
                assert (Path(resume)/'complete.json').exists()
                saved = torch.load(Path(resume)/'training.pt',map_location='cpu',weights_only=False)
                assert saved['config']==CONFIG and saved['prepared_sha']==sha(output/'prepared.json')
                for name,digest in read_json(Path(resume)/'complete.json')['files'].items():
                    assert sha(Path(resume)/name)==digest, 'incomplete/corrupt checkpoint'
                optimizer.load_state_dict(saved['optimizer']);scheduler.load_state_dict(saved['scheduler'])
                start = saved['step']
                restore_rng(torch.load(Path(resume)/f'rng-{rank}.pt',weights_only=False,map_location='cpu'))
            else:
                seed(CONFIG['seed']+rank)
            rows = read_rows(output/'train.jsonl')
            if action=='preflight':
                # Eight longest examples of each form, interleaved across ranks.
                by_form = [[r for r in sorted(rows,key=lambda r:-len(r['input_ids'])) if r['representation']==form][:8]
                           for form in ['short_qa','state_qa','state_mc']]
                rows = [by_form[(i+i//3)%3][i//3] for i in range(24)]
                assert len({r['id'] for r in rows})==24
                list(train_updates(ddp,model,optimizer,scheduler,rows,output,rank,device,preflight=True))
                dist.barrier()
                if rank==0:
                    results = [read_json(output/f'preflight-rank-{r}.json') for r in range(3)]
                    write_json(output/'preflight.json',dict(passed=True,ranks=results,
                        estimated_training_seconds=max(r['elapsed'] for r in results)*576,
                        note='longest-example update; evaluation and loading excluded'))
            else:
                validation = read_rows(output/'validation.jsonl')
                epochs = read_json(output/'epochs.json') if (output/'epochs.json').exists() else []
                if not resume:
                    evaluate(model,validation,tokenizer,output,'validation-base',rank,device,base=True)
                if resume and start % 192 == 0 and start:
                    epoch = start // 192
                    if not any(item['epoch']==epoch for item in epochs):
                        destination = output/'predictions'/f'validation-epoch-{epoch}'
                        state = rng_state()
                        if (destination/'metrics.json').exists():
                            metrics = read_json(destination/'metrics.json')
                        else:
                            metrics = evaluate(model,validation,tokenizer,output,f'validation-epoch-{epoch}',rank,device)
                        restore_rng(state)
                        if rank==0:
                            epochs.append(dict(epoch=epoch,metrics=metrics))
                            write_json(output/'epochs.json',epochs)
                # Evaluation consumes no dropout; still preserve training RNG explicitly.
                for epoch in train_updates(ddp,model,optimizer,scheduler,rows,output,rank,device,start=start):
                    state = rng_state()
                    metrics = evaluate(model,validation,tokenizer,output,f'validation-epoch-{epoch}',rank,device)
                    restore_rng(state)
                    if rank==0:
                        epochs.append(dict(epoch=epoch,metrics=metrics))
                        write_json(output/'epochs.json',epochs)
                if rank==0:
                    assert len(epochs)==3
                    write_json(output/'selection.json',choose(epochs))
        dist.barrier()
    except BaseException:
        write_json(output/f'failure-{action}-rank-{rank}-{time.time_ns()}.json',dict(traceback=traceback.format_exc()))
        raise
    finally:
        dist.destroy_process_group()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('action');parser.add_argument('--output',required=True);parser.add_argument('--resume')
    args=parser.parse_args();run(args.action,args.output,args.resume)
