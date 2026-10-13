"""Physical GPU ownership and profile-specific memory/disk fail-closed monitoring."""
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
from uuid import UUID

from .config import (CONTINUATION_RUN, EVIDENCE, ROOT, RUN, RUNTIME,
                     runtime_profile)
from .storage import read, write


def canonical_gpu_uuid(value):
    """Compare the full 128-bit ID across PyTorch's bare UUID and NVML's GPU- form."""
    text = str(value).lower()
    if text.startswith('gpu-'):
        text = text[4:]
    try:
        return str(UUID(text))
    except (ValueError, AttributeError, TypeError) as error:
        raise RuntimeError('invalid full CUDA/NVML GPU UUID') from error


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


def wait_owned_gpu_release(directory, previous_pid, *, profile='ex082'):
    """After a reaped model child, wait for its CUDA/NVML release to settle.

    Keep the original idle thresholds. A foreign lock, process, or changed GPU
    identity is an error rather than a reason to wait. No elapsed stage cap applies.
    """
    directory = Path(directory)
    settings = runtime_profile(profile)
    indices = settings.physical_gpus
    acquired = read(directory / f'gpu-acquire-{previous_pid}.json')
    if (acquired['pid'] != previous_pid
            or acquired.get('profile', 'ex082') != settings.name
            or tuple(acquired.get('physical_gpus', (0, 1))) != indices):
        raise RuntimeError('GPU release wait has no matching owned process receipt')
    expected = {i: acquired['gpus'][str(i)]['uuid'] for i in indices}
    handles = []
    started = time.monotonic()
    samples = 0
    try:
        for index in indices:
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
            if any(i not in facts or facts[i]['uuid'] != expected[i] for i in indices):
                raise RuntimeError('physical GPU identity changed during owned release')
            selected = [row for row in gpu_compute_processes() if row['uuid'] in expected.values()]
            sample = dict(at=time.time(), previous_pid=previous_pid,
                          gpus={i: facts[i] for i in indices}, compute_processes=selected)
            with (directory / f'gpu-release-wait-{previous_pid}.jsonl').open('a') as output:
                output.write(json.dumps(sample) + '\n')
            samples += 1
            if any(row['pid'] != previous_pid for row in selected):
                raise RuntimeError('foreign compute process appeared during owned GPU release')
            if not selected and all(facts[i]['memory_used_mib'] <= 256
                                    and facts[i]['utilization_percent'] <= 5 for i in indices):
                receipt = dict(passed=True, previous_pid=previous_pid, at=time.time(),
                               seconds=time.monotonic()-started, samples=samples,
                               idle_memory_mib=256, idle_utilization_percent=5,
                               profile=settings.name, physical_gpus=list(indices),
                               gpus={i: facts[i] for i in indices})
                write(directory / f'gpu-settled-{previous_pid}.json', receipt)
                return receipt
            time.sleep(.5)
    finally:
        for handle in reversed(handles):
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()


def disk_roots(*, profile='ex082', budget_root=None, extra_roots=()):
    """Count preserved assets and new evidence together, without nested-root doubles."""
    settings = runtime_profile(profile)
    paths = [RUNTIME, RUN, EVIDENCE, ROOT / 'exports/battle_viewers/ex082']
    if settings.name == 'ex083':
        paths.extend([Path(budget_root) if budget_root is not None else CONTINUATION_RUN,
                      ROOT / 'exports/battle_viewers/ex083'])
    elif budget_root is not None:
        paths.append(Path(budget_root))
    paths.extend(Path(path) for path in extra_roots)
    roots = []
    for path in sorted({path.resolve() for path in paths}, key=lambda path: len(path.parts)):
        if not any(path == parent or parent in path.parents for parent in roots):
            roots.append(path)
    return tuple(roots)


def disk_bytes(*, profile='ex082', budget_root=None, extra_roots=()):
    total = 0
    for root in disk_roots(profile=profile, budget_root=budget_root, extra_roots=extra_roots):
        if not root.exists():
            continue
        for directory, _, files in os.walk(root, followlinks=False):
            for name in files:
                try:
                    total += (Path(directory) / name).lstat().st_size
                except FileNotFoundError:
                    pass
    return total


def limit_errors(sample, *, profile='ex082'):
    settings = runtime_profile(profile)
    errors = []
    if sample['rss_bytes'] > settings.host_bytes:
        errors.append('host_memory_exceeded')
    if sample['disk_bytes'] > settings.disk_bytes:
        errors.append('disk_budget_exceeded')
    for gpu in settings.physical_gpus:
        if sample['gpus'][gpu]['memory_used_mib'] * 1024**2 > settings.gpu_bytes:
            errors.append(f'gpu{gpu}_memory_exceeded')
    for kind in ('gpu_allocated_bytes', 'gpu_reserved_bytes', 'gpu_peak_allocated_bytes'):
        if kind in sample:
            if len(sample[kind]) != len(settings.physical_gpus):
                raise ValueError('allocator sample does not cover the owned GPU set')
            for gpu, value in zip(settings.physical_gpus, sample[kind], strict=True):
                if value > settings.allocator_bytes:
                    errors.append(f'gpu{gpu}_{kind.removeprefix("gpu_")}_exceeded')
    return errors


class ResourceMonitor:
    def __init__(self, directory, *, profile='ex082', budget_root=None, extra_roots=(),
                 expected_uuids=None):
        self.directory = Path(directory)
        self.settings = runtime_profile(profile)
        self.budget_root = budget_root
        self.roots = disk_roots(profile=profile, budget_root=budget_root,
                               extra_roots=(*extra_roots, self.directory))
        self.expected_uuids = dict(expected_uuids or {})
        if self.expected_uuids and set(self.expected_uuids) != set(self.settings.physical_gpus):
            raise ValueError('UUID monitoring must cover exactly the owned GPU set')
        self.stop = threading.Event()
        self._record_lock = threading.RLock()
        self._closing = False
        self.thread = None
        self._compute_host_pid = None

    def _disk_bytes(self):
        return disk_bytes(profile=self.settings.name, budget_root=self.budget_root,
                          extra_roots=self.roots)

    def _watch(self):
        try:
            import psutil
            process = psutil.Process()
        except Exception as error:
            self._abort(['resource_monitor_failed'], {'exception_type': type(error).__name__})
            return
        samples = self.directory / f'resources-{os.getpid()}.jsonl'
        disk, next_disk = None, 0
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
                    disk, next_disk = self._disk_bytes(), time.monotonic() + 15
                facts = gpu_facts()
                sample = dict(at=time.time(), pid=os.getpid(), rss_bytes=rss, disk_bytes=disk,
                              profile=self.settings.name,
                              gpus={index: facts[index] for index in self.settings.physical_gpus})
                errors = limit_errors(sample, profile=self.settings.name)
                if self.expected_uuids:
                    if any(facts[index]['uuid'] != uuid for index, uuid in self.expected_uuids.items()):
                        errors.append('gpu_identity_changed')
                    selected = [row for row in gpu_compute_processes()
                                if row['uuid'] in self.expected_uuids.values()]
                    sample['compute_processes'] = selected
                    # NVML reports host PIDs even inside a PID namespace. Never
                    # compare those numbers to psutil's container PIDs. This
                    # profile owns one CUDA process across its locked GPU set.
                    sample['compute_pid_namespace'] = 'nvml-host'
                    host_pids = {row['pid'] for row in selected}
                    if len(host_pids) > 1:
                        errors.append('multiple_gpu_compute_processes')
                    elif host_pids:
                        host_pid = next(iter(host_pids))
                        if self._compute_host_pid is None:
                            self._compute_host_pid = host_pid
                        elif host_pid != self._compute_host_pid:
                            errors.append('gpu_compute_pid_changed')
                    sample['initial_compute_host_pid'] = self._compute_host_pid
                with self._record_lock:
                    # A slow NVML/disk query may finish after context shutdown. It
                    # cannot write behind a seal or signal the next CPU stage.
                    if self._closing:
                        return
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
        with self._record_lock:
            if self._closing:
                return
            self.stop.set()
            try:
                write(self.directory / f'resource-stop-{os.getpid()}.json',
                      dict(at=time.time(), errors=errors, sample=sample))
            except Exception:
                try:
                    sys.stderr.write(f'{self.settings.name.upper()} resource stop: evidence write failed\n')
                    sys.stderr.flush()
                except Exception:
                    pass
            finally:
                # Evidence I/O failure must not leave the model running unmonitored.
                os.kill(os.getpid(), signal.SIGTERM)

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        self.thread = threading.Thread(target=self._watch, daemon=True,
                                       name=f'{self.settings.name}-resource-monitor')
        self.thread.start()
        return self

    def __exit__(self, *args):
        with self._record_lock:
            self._closing = True
            self.stop.set()
        if self.thread:
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                raise RuntimeError('resource monitor did not stop; refuse successful shutdown')


@contextmanager
def own_gpus(directory, *, profile='ex082', budget_root=None, extra_roots=()):
    directory = Path(directory)
    settings = runtime_profile(profile)
    indices = settings.physical_gpus
    directory.mkdir(parents=True, exist_ok=True)
    handles = []
    facts = None
    try:
        for index in indices:
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
        for index in indices:
            if index not in facts:
                raise RuntimeError(f'owned physical GPU{index} is unavailable')
            if facts[index]['memory_used_mib'] > 256 or facts[index]['utilization_percent'] > 5:
                raise RuntimeError(f'GPU{index} is not idle')
        expected = {index: facts[index]['uuid'] for index in indices}
        if any(not uuid for uuid in expected.values()) or len(set(expected.values())) != len(indices):
            raise RuntimeError('physical GPU UUIDs are missing or duplicated')
        selected = [row for row in gpu_compute_processes() if row['uuid'] in expected.values()]
        if selected:
            raise RuntimeError('owned GPUs have an existing compute process')
        _stop_on_parent_exit()
        os.environ.update(CUDA_VISIBLE_DEVICES=','.join(expected[i] for i in indices),
                          CUDA_DEVICE_ORDER='PCI_BUS_ID', CUBLAS_WORKSPACE_CONFIG=':4096:8',
                          TOKENIZERS_PARALLELISM='false', PYTHONDONTWRITEBYTECODE='1',
                          HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                          TRITON_CACHE_DIR=str(RUNTIME / 'cache/triton'),
                          TORCHINDUCTOR_CACHE_DIR=str(RUNTIME / 'cache/inductor'),
                          TORCHINDUCTOR_COMPILE_THREADS='1', OMP_NUM_THREADS='4')
        write(directory / f'gpu-acquire-{os.getpid()}.json', dict(pid=os.getpid(), at=time.time(),
              profile=settings.name, physical_gpus=list(indices),
              allocator_bytes=settings.allocator_bytes, gpu_bytes=settings.gpu_bytes,
              gpus={i: facts[i] for i in indices}, compute_processes=selected,
              disk_roots=[str(path) for path in disk_roots(profile=profile, budget_root=budget_root,
                                                         extra_roots=(*extra_roots, directory))]))
        with ResourceMonitor(directory, profile=profile, budget_root=budget_root,
                             extra_roots=extra_roots, expected_uuids=expected):
            import torch
            if torch.cuda.is_initialized():
                raise RuntimeError('CUDA was initialized before GPU ownership')
            if torch.cuda.device_count() != len(indices):
                raise RuntimeError('visible CUDA device count differs from owned GPU set')
            for local, physical in enumerate(indices):
                properties = torch.cuda.get_device_properties(local)
                actual_uuid = canonical_gpu_uuid(properties.uuid)
                expected_uuid = canonical_gpu_uuid(expected[physical])
                write(directory / f'cuda-identity-{os.getpid()}-gpu{physical}.json',
                      dict(local_device=local, physical_device=physical,
                           cuda_uuid=str(properties.uuid), nvml_uuid=expected[physical],
                           cuda_uuid_canonical=actual_uuid, nvml_uuid_canonical=expected_uuid,
                           passed=actual_uuid == expected_uuid))
                if actual_uuid != expected_uuid:
                    raise RuntimeError(f'CUDA device {local} does not match physical GPU{physical} UUID')
                torch.cuda.set_per_process_memory_fraction(
                    min(1., settings.allocator_bytes / properties.total_memory), local)
            yield {i: facts[i] for i in indices}
    finally:
        for handle in reversed(handles):
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()
        if facts:
            write(directory / f'gpu-release-{os.getpid()}.json', dict(pid=os.getpid(), at=time.time(),
                  profile=settings.name, physical_gpus=list(indices)))


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
