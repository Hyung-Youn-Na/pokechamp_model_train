"""Physical GPU ownership, retaining the original resource across resume."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import subprocess
import time

from . import config as c
from .storage import atomic, read


def gpu_facts():
    raw = subprocess.check_output(['nvidia-smi',
        '--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu',
        '--format=csv,noheader,nounits'], text=True)
    result = {}
    for line in raw.strip().splitlines():
        index, uuid, name, total, used, utilization = (x.strip() for x in line.split(','))
        result[int(index)] = dict(index=int(index), uuid=uuid, name=name, memory_total_mib=int(total),
                                  memory_used_mib=int(used), utilization_percent=int(utilization))
    return result


@contextmanager
def own_gpu(directory, stage):
    directory = Path(directory)
    saved = read(directory/'resource.json') if (directory/'resource.json').exists() else None
    order = [saved['physical_gpu']] if saved else c.GPU_ORDER
    if any(gpu not in c.GPU_ORDER for gpu in order):
        raise ValueError('EX-071 must never use GPU1')
    handle = None
    selected = None
    facts = gpu_facts()
    try:
        for gpu in order:
            lock = c.ROOT / f'.pokechamp-data/locks/gpu{gpu}.lock'
            lock.parent.mkdir(parents=True,exist_ok=True)
            candidate = lock.open('a+')
            try:
                fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                candidate.close()
                continue
            fact = gpu_facts().get(gpu)
            if not fact or fact['memory_used_mib']>256 or fact['utilization_percent']>5:
                fcntl.flock(candidate,fcntl.LOCK_UN)
                candidate.close()
                continue
            handle, selected = candidate, fact
            break
        if handle is None:
            raise RuntimeError('no idle permitted GPU; preserve current workers and retry only when idle')
        if saved and selected['uuid']!=saved['uuid']:
            raise ValueError('frozen GPU identity changed')
        if not saved:
            saved = dict(physical_gpu=selected['index'], uuid=selected['uuid'],name=selected['name'],
                         selection_order=list(c.GPU_ORDER),observed=facts,selected_at=time.time(),
                         memory_total_mib=selected['memory_total_mib'])
            atomic(directory/'resource.json',saved,immutable=True)
        os.environ['CUDA_VISIBLE_DEVICES'] = str(selected['index'])
        os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
        atomic(directory/'resource-events'/f'{time.time_ns()}-{stage}-acquire.json',
               dict(stage=stage,pid=os.getpid(),selected=selected,at=time.time()),immutable=True)
        yield saved
    finally:
        if handle is not None:
            atomic(directory/'resource-events'/f'{time.time_ns()}-{stage}-release.json',
                   dict(stage=stage,pid=os.getpid(),physical_gpu=selected['index'],at=time.time()),immutable=True)
            fcntl.flock(handle,fcntl.LOCK_UN)
            handle.close()


@contextmanager
def own_run(directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'controller.lock').open('a+') as handle:
        try:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('another EX-071 controller owns this artifact directory') from None
        try:
            yield
        finally:
            fcntl.flock(handle,fcntl.LOCK_UN)
