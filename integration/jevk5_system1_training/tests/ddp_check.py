"""Actual three-process Gloo check against a full-batch gradient."""
import contextlib
import os
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

def main():
    torch.set_num_threads(1);dist.init_process_group('gloo');rank=dist.get_rank()
    torch.manual_seed(12);model=torch.nn.Linear(5,3,bias=False).double();reference=torch.nn.Linear(5,3,bias=False).double();reference.load_state_dict(model.state_dict())
    reader=DDP(model,broadcast_buffers=False);x=torch.randn(69,5,dtype=torch.float64);w=torch.linspace(.01,3,69,dtype=torch.float64);y=torch.arange(69)%3
    target=(torch.nn.functional.cross_entropy(reference(x),y,reduction='none')*w).sum()/w.sum();target.backward()
    local=list(range(rank,69,3));cap=[1,4,8][rank];parts=[local[i:i+cap] for i in range(0,len(local),cap)]
    for j,ix in enumerate(parts):
        with reader.no_sync() if j<len(parts)-1 else contextlib.nullcontext():
            loss=(torch.nn.functional.cross_entropy(reader(x[ix]),y[ix],reduction='none')*w[ix]).sum()*3/w.sum();loss.backward()
    torch.testing.assert_close(model.weight.grad,reference.weight.grad,atol=1e-12,rtol=1e-12)
    if rank==0:print('PASS: actual Gloo3 weighted gradient, unequal microbatch counts, final69',flush=True)
    dist.destroy_process_group()
if __name__=='__main__':main()
