from contextlib import contextmanager
from contextlib import nullcontext
import fcntl
import os
from pathlib import Path
import subprocess
import time
import torch
from ..storage import ROOT, atomic, read
from .artifacts import now
from .config import CONFIG


@contextmanager
def gpu_owner(out, stage):
    physical=CONFIG['physical_gpu']
    lock = ROOT/f'.pokechamp-data/locks/gpu{physical}.lock'
    lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a+') as f:
        try:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f'GPU{physical} has another repository owner') from None
        try:
            if os.environ.get('CUDA_VISIBLE_DEVICES')!=str(physical) or torch.cuda.device_count()!=1:
                raise ValueError(f'exactly physical GPU{physical} must be visible')
            facts=subprocess.check_output(['nvidia-smi',f'--id={physical}',
                '--query-gpu=name,uuid,memory.total,memory.used,utilization.gpu',
                '--format=csv,noheader,nounits'],text=True).strip()
            fields=[s.strip() for s in facts.split(',')]
            if fields[0]!='NVIDIA RTX A6000' or int(fields[2])<48000 or int(fields[3])>512:
                raise RuntimeError(f'GPU{physical} unavailable: '+facts)
            atomic(Path(out)/f'{stage}-gpu.json',dict(at=now(),physical_gpu=physical,
                gpu_name=fields[0],total_mib=int(fields[2]),used_mib_before=int(fields[3]),
                visible_devices=str(physical),device_count=1,pid=os.getpid()))
            yield
        finally:
            fcntl.flock(f,fcntl.LOCK_UN)


class Progress:
    def __init__(self, directory, stage):
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        previous={}
        if (self.directory/'progress.json').exists():
            previous=read(self.directory/'progress.json')
            atomic(self.directory/f'previous-progress-{time.time_ns()}.json',previous,immutable=True)
        self.stage,self.start=stage,time.perf_counter()
        self.previous_elapsed=previous.get('elapsed_seconds',0.)
        self.gpu_seconds,self.forwards=previous.get('gpu_seconds',0.),previous.get('forwards',0)
        self.peak_allocated,self.peak_reserved=previous.get('max_allocated_bytes',0),previous.get('max_reserved_bytes',0)
        self.extra={}
        self.update(phase='initialize')

    def update(self, **extra):
        self.extra.update(extra)
        self.peak_allocated=max(self.peak_allocated,torch.cuda.max_memory_allocated() if torch.cuda.is_initialized() else 0)
        self.peak_reserved=max(self.peak_reserved,torch.cuda.max_memory_reserved() if torch.cuda.is_initialized() else 0)
        elapsed=time.perf_counter()-self.start
        atomic(self.directory/'progress.json',dict(self.extra,stage=self.stage,pid=os.getpid(),at=now(),
            elapsed_seconds=self.previous_elapsed+elapsed,attempt_elapsed_seconds=elapsed,
            gpu_seconds=self.gpu_seconds,forwards=self.forwards,max_allocated_bytes=self.peak_allocated,
            max_reserved_bytes=self.peak_reserved))

    @contextmanager
    def timed(self):
        start,end=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
        start.record()
        try:
            yield
        finally:
            end.record()
            torch.cuda.synchronize()
            self.gpu_seconds+=start.elapsed_time(end)/1000
            self.forwards+=1
            self.update()


def loss(q, targets):
    target=torch.tensor(targets,device=q.device,dtype=torch.float32)
    if q.shape!=target.shape:
        raise ValueError('candidate target shape mismatch')
    value=(q.float()-target).square().mean()
    if not bool(torch.isfinite(value)):
        raise FloatingPointError('nonfinite loss')
    return value


def check_gradients(policy):
    squares=0.
    for name,p in policy.named_parameters():
        if not p.requires_grad:
            if p.grad is not None:
                raise ValueError('frozen base has gradient: '+name)
            continue
        if p.grad is None or not bool(torch.isfinite(p.grad).all()):
            raise FloatingPointError('missing/nonfinite gradient: '+name)
        squares+=float(p.grad.detach().float().square().sum())
    return squares**.5


def backward_batch(policy, batch, progress=None, on_observation=None):
    if not batch:
        raise ValueError('empty optimizer batch')
    averaged=0.
    for r,e in batch:
        if on_observation is not None:
            on_observation(r,e)
        with progress.timed() if progress is not None else nullcontext():
            value=loss(policy.values(e),r.q)
            (value/len(batch)).backward()
        averaged+=float(value.detach())/len(batch)
    return averaged
