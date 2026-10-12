"""Physical GPU ownership and EX-082 memory/disk fail-closed monitoring."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from .config import DISK_BYTES, EVIDENCE, GPU_BYTES, HOST_BYTES, ROOT, RUN, RUNTIME
from .storage import read, write


def gpu_facts():
    output = subprocess.check_output([
        'nvidia-smi', '--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu',
        '--format=csv,noheader,nounits'], text=True)
    facts = {}
    for line in output.strip().splitlines():
        index, uuid, name, total, used, utilization = [s.strip() for s in line.split(',')]
        facts[int(index)] = dict(index=int(index), uuid=uuid, name=name,
            memory_total_mib=int(total), memory_used_mib=int(used), utilization_percent=int(utilization))
    return facts


def gpu_compute_processes():
    output = subprocess.check_output([
        'nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
        '--format=csv,noheader,nounits'], text=True)
    rows = []
    for line in output.strip().splitlines():
        uuid, pid = [part.strip() for part in line.split(',')]
        rows.append(dict(uuid=uuid, pid=int(pid)))
    return rows


def wait_owned_gpu_release(directory, previous_pid):
    """After a reaped model child, wait for its CUDA/NVML release to settle.

    Keep the original idle thresholds. A foreign lock, process, or changed GPU
    identity is an error rather than a reason to wait. No elapsed stage cap applies.
    """
    directory = Path(directory)
    acquired = read(directory / f'gpu-acquire-{previous_pid}.json')
    if acquired['pid'] != previous_pid:
        raise RuntimeError('GPU release wait has no matching owned process receipt')
    expected = {i: acquired['gpus'][str(i)]['uuid'] for i in (0, 1)}
    handles = []
    started = time.monotonic()
    samples = 0
    try:
        for index in (0, 1):
            handle = (ROOT / f'.pokechamp-data/locks/gpu{index}.lock').open('a+')
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                handle.close()
                raise RuntimeError(f'GPU{index} is owned by another run during release') from None
            handles.append(handle)
        while True:
            if Path(f'/proc/{previous_pid}').exists():
                raise RuntimeError('model PID is still alive or has been reused during GPU release')
            facts = gpu_facts()
            if any(facts[i]['uuid'] != expected[i] for i in (0, 1)):
                raise RuntimeError('physical GPU identity changed during owned release')
            selected = [row for row in gpu_compute_processes() if row['uuid'] in expected.values()]
            sample = dict(at=time.time(), previous_pid=previous_pid,
                          gpus={i: facts[i] for i in (0, 1)}, compute_processes=selected)
            with (directory / f'gpu-release-wait-{previous_pid}.jsonl').open('a') as output:
                output.write(json.dumps(sample) + '\n')
            samples += 1
            if any(row['pid'] != previous_pid for row in selected):
                raise RuntimeError('foreign compute process appeared during owned GPU release')
            if not selected and all(facts[i]['memory_used_mib'] <= 256
                                    and facts[i]['utilization_percent'] <= 5 for i in (0, 1)):
                receipt = dict(passed=True, previous_pid=previous_pid, at=time.time(),
                               seconds=time.monotonic()-started, samples=samples,
                               idle_memory_mib=256, idle_utilization_percent=5,
                               gpus={i: facts[i] for i in (0, 1)})
                write(directory / f'gpu-settled-{previous_pid}.json', receipt)
                return receipt
            time.sleep(.5)
    finally:
        for handle in reversed(handles):
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()


def disk_bytes():
    total = 0
    paths = (RUNTIME, RUN, EVIDENCE, ROOT / 'exports/battle_viewers/ex082')
    for root in paths:
        if not root.exists():
            continue
        for directory, _, files in os.walk(root, followlinks=False):
            for name in files:
                try:
                    total += (Path(directory) / name).lstat().st_size
                except FileNotFoundError:
                    pass
    return total


def limit_errors(sample):
    errors = []
    if sample['rss_bytes'] > HOST_BYTES:
        errors.append('host_memory_exceeded')
    if sample['disk_bytes'] > DISK_BYTES:
        errors.append('disk_budget_exceeded')
    for gpu in (0, 1):
        if sample['gpus'][gpu]['memory_used_mib'] * 1024**2 > GPU_BYTES:
            errors.append(f'gpu{gpu}_memory_exceeded')
    return errors


class ResourceMonitor:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.stop = threading.Event()
        self.thread = None

    def _watch(self):
        import psutil
        process = psutil.Process()
        disk = disk_bytes()
        next_disk = time.monotonic() + 15
        samples = self.directory / f'resources-{os.getpid()}.jsonl'
        while not self.stop.is_set():
            try:
                members = [process] + process.children(recursive=True)
                rss = 0
                for member in members:
                    try:
                        rss += member.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
                if time.monotonic() >= next_disk:
                    disk, next_disk = disk_bytes(), time.monotonic() + 15
                facts = gpu_facts()
                sample = dict(at=time.time(), pid=os.getpid(), rss_bytes=rss, disk_bytes=disk,
                              gpus={index: facts[index] for index in (0, 1)})
                errors = limit_errors(sample)
                with samples.open('a') as output:
                    output.write(json.dumps(dict(sample, errors=errors)) + '\n')
                if errors:
                    self._abort(errors, sample)
                    return
            except Exception as error:
                self._abort(['resource_monitor_failed'], {'exception_type': type(error).__name__})
                return
            self.stop.wait(0.5)

    def _abort(self, errors, sample):
        self.stop.set()
        try:
            write(self.directory / f'resource-stop-{os.getpid()}.json',
                  dict(at=time.time(), errors=errors, sample=sample))
        except Exception:
            try:
                sys.stderr.write('EX-082 resource stop: evidence write failed\n')
                sys.stderr.flush()
            except Exception:
                pass
        finally:
            # Evidence I/O failure must not leave the model running unmonitored.
            os.kill(os.getpid(), signal.SIGTERM)

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.thread = threading.Thread(target=self._watch, daemon=True, name='ex082-resource-monitor')
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=10)


@contextmanager
def own_gpus(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    handles = []
    facts = None
    try:
        for index in (0, 1):
            path = ROOT / f'.pokechamp-data/locks/gpu{index}.lock'
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open('a+')
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                handle.close()
                raise RuntimeError(f'GPU{index} is owned by another run') from None
            handles.append(handle)
        facts = gpu_facts()
        for index in (0, 1):
            if facts[index]['memory_used_mib'] > 256 or facts[index]['utilization_percent'] > 5:
                raise RuntimeError(f'GPU{index} is not idle')
        _stop_on_parent_exit()
        os.environ.update(CUDA_VISIBLE_DEVICES=','.join(facts[i]['uuid'] for i in (0, 1)),
                          CUDA_DEVICE_ORDER='PCI_BUS_ID', CUBLAS_WORKSPACE_CONFIG=':4096:8',
                          TOKENIZERS_PARALLELISM='false', PYTHONDONTWRITEBYTECODE='1',
                          HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                          TRITON_CACHE_DIR=str(RUNTIME / 'cache/triton'),
                          TORCHINDUCTOR_CACHE_DIR=str(RUNTIME / 'cache/inductor'),
                          TORCHINDUCTOR_COMPILE_THREADS='1', OMP_NUM_THREADS='4')
        write(directory / f'gpu-acquire-{os.getpid()}.json', dict(pid=os.getpid(), at=time.time(), gpus=facts))
        with ResourceMonitor(directory):
            import torch
            if torch.cuda.is_initialized():
                raise RuntimeError('CUDA was initialized before GPU ownership')
            for local in (0, 1):
                total = torch.cuda.get_device_properties(local).total_memory
                torch.cuda.set_per_process_memory_fraction(min(1., GPU_BYTES / total), local)
            yield {i: facts[i] for i in (0, 1)}
    finally:
        for handle in reversed(handles):
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()
        if facts:
            write(directory / f'gpu-release-{os.getpid()}.json', dict(pid=os.getpid(), at=time.time(),
                  physical_gpus=[0, 1]))


def _stop_on_parent_exit():
    """The model must not outlive the controller that authorized its GPU ownership."""
    import ctypes
    parent = os.getppid()
    if parent == 1:
        raise RuntimeError('model process has no live supervising parent')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, int(signal.SIGTERM), 0, 0, 0) != 0:  # Linux PR_SET_PDEATHSIG.
        raise OSError(ctypes.get_errno(), 'cannot install model parent-death signal')
    if os.getppid() != parent:
        os.kill(os.getpid(), signal.SIGTERM)
