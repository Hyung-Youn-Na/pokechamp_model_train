"""Unchanged EX066 readout with explicit, recorded execution settings."""
from contextlib import contextmanager
import fcntl
import importlib.metadata
import os
from pathlib import Path
import subprocess
import threading
import time

from . import config as c, protocol as p, storage as s


def sources():
    names = ('__init__.py', 'config.py', 'storage.py', 'protocol.py', 'model_io.py', 'server.py', 'diagnose.py')
    paths = [Path(__file__).with_name(name) for name in names if Path(__file__).with_name(name).exists()]
    paths += [c.ROOT / name for name in s.read(c.ORIGINAL / 'prepared/manifest.json')['sources']]
    return {str(path.relative_to(c.ROOT)): s.sha(path) for path in sorted(set(paths))}


def gpu_facts():
    raw = subprocess.check_output(['nvidia-smi', '--id=0',
        '--query-gpu=index,uuid,name,memory.total,memory.used', '--format=csv,noheader,nounits'],
        text=True, timeout=15).strip()
    index, uuid, name, total, used = [x.strip() for x in raw.split(',')]
    return dict(physical_gpu=int(index), gpu_uuid=uuid, name=name,
                total_mib=int(total), used_mib=int(used))


@contextmanager
def gpu_owner(directory):
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '0':
        raise ValueError('EX081 requires physical GPU0 only')
    path = c.ROOT / '.pokechamp-data/locks/gpu0.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as lock:
        acquired = False
        try:
            while True:
                if s.clock(directory) and s.remaining(directory) <= c.LIMITS['cleanup_reserve_seconds']:
                    raise TimeoutError('GPU0 wait reached finalization reserve')
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    s.atomic(Path(directory) / 'gpu-wait.json', dict(at=s.now(), reason='repository_owner'))
                    time.sleep(5)
                    continue
                facts = gpu_facts()
                if facts['physical_gpu'] != 0 or facts['total_mib'] < 48000:
                    raise RuntimeError('unexpected physical GPU0: ' + str(facts))
                if facts['used_mib'] <= 512:
                    break
                fcntl.flock(lock, fcntl.LOCK_UN)
                acquired = False
                s.atomic(Path(directory) / 'gpu-wait.json', dict(at=s.now(), reason='other_work', facts=facts))
                time.sleep(5)
            s.clock(directory, start=True)
            if s.remaining(directory) <= c.LIMITS['cleanup_reserve_seconds']:
                raise TimeoutError('EX081 cumulative budget exhausted')
            yield facts
        finally:
            if acquired:
                fcntl.flock(lock, fcntl.LOCK_UN)


class Runtime:
    def __init__(self, output, *, facts, variant='original'):
        import torch
        from ..learning import model as m
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.started_at = time.time()
        self.variant = variant
        self.failed = None
        self.lock = threading.Lock()
        self.requests = 0
        self.gpu_seconds = 0.0
        self.facts = facts
        self.identity = s.checkpoint_identity()
        self.source = sources()
        self.source_sha256 = s.digest(self.source)
        packages = {name: importlib.metadata.version(name) for name in
                    s.read(c.ORIGINAL / 'prepared/manifest.json')['packages']}
        if packages != s.read(c.ORIGINAL / 'prepared/manifest.json')['packages']:
            raise ValueError('EVE environment differs from original EX066')
        if torch.cuda.device_count() != 1:
            raise ValueError('exactly one CUDA device must be visible')
        cuda_uuid = str(torch.cuda.get_device_properties(0).uuid)
        if cuda_uuid.removeprefix('GPU-').lower() != facts['gpu_uuid'].removeprefix('GPU-').lower():
            raise ValueError('visible CUDA device UUID is not physical GPU0')
        m.seed_all()
        if variant == 'original':
            pass
        elif variant == 'deterministic':
            # Same parameters/dtypes/inputs; disallow nondeterministic CUDA kernels.
            torch.use_deterministic_algorithms(True)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        else:
            raise ValueError('unknown diagnostic execution variant')
        s.atomic(self.output / 'startup.json', dict(at=s.now(), pid=os.getpid(),
            facts=facts, cuda_uuid=cuda_uuid, variant=variant, packages=packages, source=self.source,
            source_sha256=self.source_sha256, started_at=self.started_at,
            execution=dict(cuda_visible_devices=os.environ['CUDA_VISIBLE_DEVICES'],
                deterministic=torch.are_deterministic_algorithms_enabled(),
                cudnn_deterministic=torch.backends.cudnn.deterministic,
                cudnn_benchmark=torch.backends.cudnn.benchmark,
                matmul_tf32=torch.backends.cuda.matmul.allow_tf32,
                cudnn_tf32=torch.backends.cudnn.allow_tf32,
                bf16_reduced_precision=torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction)),
            immutable=True)
        self.policy = m.JointValuePolicy(m.load_base(self.output / 'loading.json'),
                                         m.tokenizer(c.ORIGINAL / 'prepared/tokenizer'), c.CHECKPOINT)
        self.policy.eval()
        self.before_trainable = self.policy.trainable_fingerprints()
        self.before_base = self.policy.base_fingerprints()
        meta = s.read(c.CHECKPOINT / 'metadata.json')
        if (self.before_trainable != meta['trainable_fingerprints']
                or self.before_base != meta['base_fingerprints']):
            raise ValueError('loaded checkpoint tensor fingerprints differ')
        s.atomic(self.output / 'weights-before.json', dict(base=self.before_base,
                                                         trainable=self.before_trainable), immutable=True)
        self.progress()

    def health(self):
        return dict(ready=self.failed is None, profile=c.PROFILE, model=c.MODEL,
            revision=c.REVISION, checkpoint_sha256=self.identity['checkpoint_sha256'],
            head_sha256=self.identity['head_sha256'], server_pid=os.getpid(),
            server_started_at=self.started_at, physical_gpu=0, gpu_uuid=self.facts['gpu_uuid'],
            source_sha256=self.source_sha256, variant=self.variant, requests=self.requests,
            gpu_seconds=self.gpu_seconds, error=self.failed)

    def progress(self):
        import torch
        s.atomic(self.output / 'progress.json', dict(**self.health(), at=s.now(),
            elapsed_seconds=time.time() - self.started_at,
            max_allocated_bytes=torch.cuda.max_memory_allocated(),
            max_reserved_bytes=torch.cuda.max_memory_reserved()))

    def evaluate(self, body, *, deadline=None):
        import torch
        from ..learning.render import render
        from ..storage import digest as token_digest
        started = time.monotonic()
        if self.failed:
            raise RuntimeError('model runtime stopped')
        if deadline is None:
            deadline = started + c.LIMITS['request_seconds']
        value = p.validate_request(body)
        encoded = render(value, self.policy.tokenizer)
        if time.monotonic() >= deadline:
            raise TimeoutError('request expired before forward')
        number = self.requests + 1
        self.requests = number
        s.atomic(self.output / 'requests' / f'{number:06d}-input.json',
                 dict(body=body, input_sha256=p.input_sha256(value), encoded=encoded.to_row(str(number))),
                 immutable=True)
        begin, end = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        begin.record()
        with torch.no_grad():
            values = self.policy.values(encoded).cpu().tolist()
        end.record()
        torch.cuda.synchronize()
        seconds = begin.elapsed_time(end) / 1000
        self.gpu_seconds += seconds
        result = dict(profile=c.PROFILE, model=c.MODEL, revision=c.REVISION,
            checkpoint_sha256=self.identity['checkpoint_sha256'], head_sha256=self.identity['head_sha256'],
            server_pid=os.getpid(), server_started_at=self.started_at, source_sha256=self.source_sha256,
            input_sha256=p.input_sha256(value), q_values=dict(zip(encoded.action_ids, values, strict=True)),
            choice=encoded.action_ids[max(range(len(values)), key=values.__getitem__)],
            prompt_sha256=encoded.prompt_sha256, token_sha256=token_digest(encoded.input_ids),
            tokens=len(encoded.input_ids), readout_positions=list(encoded.readout_positions),
            elapsed_seconds=time.monotonic() - started, gpu_seconds=seconds)
        p.validate_response(result, encoded.action_ids)
        expired = time.monotonic() >= deadline
        s.atomic(self.output / 'requests' / f'{number:06d}-output.json',
                 dict(response=result, expired=expired), immutable=True)
        self.progress()
        if expired:
            raise TimeoutError('late response must not be sent to battle')
        return result

    def close(self):
        trainable = self.policy.trainable_fingerprints()
        base = self.policy.base_fingerprints()
        same_checkpoint = s.checkpoint_identity() == self.identity
        source_now = {name: s.sha(c.ROOT / name) for name in self.source}
        receipt = dict(at=s.now(), **self.health(), weights_unchanged=trainable == self.before_trainable,
            base_unchanged=base == self.before_base, checkpoint_files_unchanged=same_checkpoint,
            source_unchanged=source_now == self.source, optimizer_updates=0,
            elapsed_seconds=time.time() - self.started_at)
        s.atomic(self.output / 'closure.json', receipt, immutable=True)
        if not all(receipt[k] for k in ('weights_unchanged', 'base_unchanged',
                                      'checkpoint_files_unchanged', 'source_unchanged')):
            raise ValueError('model closure integrity failure')
        return receipt
