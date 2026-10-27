"""GPU / port ownership (GPU0·8107 for EP-208..210, GPU1·8109 for EP-212, GPU2·8108 for EP-213): flock files, UUID
identity, idle checks."""
from __future__ import annotations
from contextlib import contextmanager
import fcntl
import subprocess

from . import config as c


def gpus():
    out = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,memory.used',
                                   '--format=csv,noheader,nounits'], text=True)
    return [dict(index=int(a), uuid=b.strip(), memory_mib=int(m))
            for a, b, m in (line.split(',') for line in out.strip().splitlines())]


def gpu_processes():
    out = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid',
                                   '--format=csv,noheader,nounits'], text=True)
    return [(int(p), u.strip()) for p, u in (line.split(',') for line in out.strip().splitlines() if line.strip())]


@contextmanager
def lock(name):
    """Exclusive non-blocking hold of `.pokechamp-data/locks/<name>.lock`; raises if taken."""
    with open(c.LOCKS / (name + '.lock'), 'a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(name + ' lock is held by another process') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def gpu(index, uuid, require_idle=True):
    """Hold GPU `index`, check it is the pinned device and (optionally) idle; yields the child env."""
    with lock('gpu%d' % index):
        device = next(g for g in gpus() if g['index'] == index)
        if device['uuid'] != uuid:
            raise RuntimeError('GPU%d UUID changed: %s' % (index, device['uuid']))
        if require_idle and (device['memory_mib'] >= 100 or any(u == uuid for _, u in gpu_processes())):
            raise RuntimeError('GPU%d is not idle: %s' % (index, device))
        yield dict(CUDA_VISIBLE_DEVICES=uuid, CUDA_DEVICE_ORDER='PCI_BUS_ID'), device


def gpu0(require_idle=True):
    return gpu(c.GPU_INDEX, c.GPU_UUID, require_idle)


@contextmanager
def port(number=c.PORT):
    with lock('port%d' % number):
        yield number
