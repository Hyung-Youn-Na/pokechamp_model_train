"""Four-device ownership, complete-step distributed persistence and supervision."""
from __future__ import annotations

from integration.project_context.registry import authority_paths, record_relative
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
from . import config
from .storage import atomic, append, read, sha, Clock
from ..imitation.resource import gpu_facts, own_run
from ..selfplay.execution import cleanup_owned
from .recovery import BACKEND, identity as recovery_identity


@contextmanager
def own_gpus(directory):
    """Take all shared physical locks or release all; never evict another job."""
    directory = Path(directory)
    handles = []
    sockets = []
    try:
        for index in range(4):
            path = config.ROOT / f'.pokechamp-data/locks/gpu{index}.lock'
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open('a+')
            handles.append(handle)
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        facts = gpu_facts()
        chosen = [facts.get(i) for i in range(4)]
        if any(not f or f['memory_used_mib'] > 256 or f['utilization_percent'] > 5 for f in chosen):
            raise RuntimeError('all physical GPU0–3 must be idle; no workers terminated')
        if any('A6000' not in f['name'] or f['memory_total_mib'] < 47000 for f in chosen):
            raise ValueError('four RTX A6000 48GB devices required')
        for port in [*range(8100, 8108), *range(8030, 8034)]:
            handle = (config.ROOT / f'.pokechamp-data/locks/port{port}.lock').open('a+')
            handles.append(handle)
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            sock = socket.socket()
            sockets.append(sock)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
        record = {'gpus': chosen, 'selected_at': time.time(), 'ports': [*range(8100,8108), *range(8030,8034)]}
        path = directory / 'resource.json'
        if path.exists():
            saved = read(path)
            if [f['uuid'] for f in saved['gpus']] != [f['uuid'] for f in chosen]:
                raise ValueError('original physical GPU identities changed')
            record = saved
        else:
            atomic(path, record, immutable=True)
        for sock in sockets:
            sock.close()
        yield record
    finally:
        for sock in sockets:
            sock.close()
        for handle in reversed(handles):
            fcntl.flock(handle, fcntl.LOCK_UN)
            handle.close()


def buffer_digest(records):
    import hashlib
    import json
    raw = json.dumps(records, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def weights_digest(weights):
    import hashlib
    import torch
    digest = hashlib.sha256()
    for name, tensor in sorted(weights.items()):
        value = tensor.detach().cpu().contiguous()
        digest.update(repr((name, tuple(value.shape), str(value.dtype))).encode())
        digest.update(value.view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def save_checkpoint(directory, policy, optimizer, state, clock, *, weights=None,
                    calibration_optimizer=None, frozen_buffer=None):
    """Called by every rank only at the same completed optimizer-step boundary."""
    import torch
    import torch.distributed as dist
    from .trainer import rng_state
    rank = dist.get_rank()
    ranks = [None] * 4
    saved_weights = policy.snapshot_weights() if weights is None else weights
    weight_hash = weights_digest(saved_weights)
    buffer_hash = buffer_digest(frozen_buffer)
    local = {'rank': rank, 'rng': rng_state(), 'sampling_rng': policy.sampling_generator.getstate(),
             'state': state, 'weights_sha256': weight_hash, 'buffer_sha256': buffer_hash}
    dist.all_gather_object(ranks, local)
    if any(item['state'] != state for item in ranks):
        raise ValueError('checkpoint ranks disagree about completed cursor/state')
    if any(item['weights_sha256'] != weight_hash or item['buffer_sha256'] != buffer_hash for item in ranks):
        raise ValueError('checkpoint ranks disagree about weights or frozen buffer')
    record = None
    if rank == 0:
        directory = Path(directory)
        folder = directory / 'checkpoints'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'checkpoint-{time.time_ns()}.pt'
        payload = {'weights': saved_weights, 'weights_sha256': weight_hash,
                   'frozen_buffer': frozen_buffer, 'buffer_sha256': buffer_hash,
                   'optimizer': optimizer.state_dict() if optimizer else None,
                   'calibration_optimizer': calibration_optimizer.state_dict() if calibration_optimizer else None,
                   'state': state, 'ranks': ranks, 'clock': clock.record,
                   'manifest_sha256': sha(directory / 'manifest.json'),
                   'recovery_sha256': recovery_identity(directory)}
        fd, temporary = tempfile.mkstemp(prefix='.checkpoint-', dir=folder)
        try:
            with os.fdopen(fd, 'wb') as stream:
                torch.save(payload, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            fd = os.open(folder, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        record = {'path': str(path), 'sha256': sha(path), 'phase': state['phase'],
                  'global_updates': (state.get('trainer') or {}).get('global_updates', 0), 'saved_at': time.time()}
        atomic(directory / 'latest.json', record)
        atomic(directory / 'state.json', state)
        append(directory / 'checkpoint-events.jsonl', record)
    shared = [record]
    dist.broadcast_object_list(shared, src=0)
    return shared[0]


def load_checkpoint(directory, policy, optimizer, clock):
    import torch
    import torch.distributed as dist
    from .trainer import restore_rng
    directory = Path(directory)
    pointer = read(directory / 'latest.json')
    path = Path(pointer['path'])
    if sha(path) != pointer['sha256']:
        raise ValueError('checkpoint digest mismatch')
    payload = torch.load(path, map_location='cpu', weights_only=False)
    if payload['clock'] != clock.record or payload['manifest_sha256'] != sha(directory / 'manifest.json'):
        raise ValueError('original clock or manifest mismatch')
    if len(payload['ranks']) != 4:
        raise ValueError('missing rank RNG state')
    if (weights_digest(payload['weights']) != payload['weights_sha256'] or
            buffer_digest(payload['frozen_buffer']) != payload['buffer_sha256']):
        raise ValueError('checkpoint weights or frozen buffer content mismatch')
    from .recovery import checkpoint_compatible
    checkpoint_compatible(directory, pointer, payload)
    policy.load_weights(payload['weights'])
    if payload['optimizer'] is not None:
        optimizer.load_state_dict(payload['optimizer'])
    local = payload['ranks'][dist.get_rank()]
    restore_rng(local['rng'])
    policy.sampling_generator.setstate(local['sampling_rng'])
    dist.barrier()
    return payload


def source_files():
    from ..selfplay.execution import source_files as shared_sources
    result = shared_sources()
    path = config.ROOT / 'scripts/pokechamp-abyssal-rl'
    result[str(path.relative_to(config.ROOT))] = sha(path)
    return result


def freeze(directory):
    import shutil
    from .prepare import verify
    directory = Path(directory)
    verify(directory)
    if (directory / 'manifest.json').exists() and (directory / 'recovery.json').exists():
        assert_frozen(directory)
        return read(directory / 'manifest.json')
    validation = read(directory / 'verification/cpu.json')
    if not validation['passed']:
        raise ValueError('CPU validation required before GPU admission')
    from ..imitation.model import provenance, verify_checkpoint
    verify_checkpoint(config.INITIAL)
    sources = source_files()
    if validation.get('source') != sources:
        raise ValueError('CPU verification source differs from current execution')
    expected = {'experiment_id': 'EX-073', 'protocol': config.PROTOCOL, 'source': sources,
                'prepared_sha256': sha(directory / 'prepared/manifest.json'),
                'resource_sha256': sha(directory / 'resource.json'),
                'cpu_sha256': sha(directory / 'verification/cpu.json')}
    path = directory / 'manifest.json'
    if path.exists():
        manifest = read(path)
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError('frozen execution changed')
        return manifest
    documents = [
        'project_context/INDEX.md', 'project_context/CHARTER.md',
        'project_context/RESEARCH_DESIGN.md', 'project_context/CONTRACTS.md',
        record_relative('D-116', prefix=True),
        record_relative('EX-073', prefix=True),
        record_relative('EP-119', prefix=True),
    ]
    documents += [str(p.relative_to(config.ROOT)) for p in authority_paths(root=config.ROOT)]
    protocol_docs = {name: sha(config.ROOT / name) for name in documents}
    manifest = dict(expected, protocol_docs=protocol_docs, environment=provenance(verify_weights=True), frozen_at=time.time(),
                    initial_checkpoint_sha256=sha(config.INITIAL / 'files.json'))
    for name, digest in {**sources, **protocol_docs}.items():
        target = directory / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config.ROOT / name, target)
        if sha(target) != digest:
            raise ValueError('source changed during freeze')
    atomic(path, manifest, immutable=True)
    return manifest


def assert_frozen(directory):
    from .prepare import verify
    directory = Path(directory)
    manifest = read(directory / 'manifest.json')
    from .recovery import validate
    recovery = validate(directory, current_sources=source_files())
    if recovery is None and source_files() != manifest['source']:
        raise ValueError('runtime source differs from frozen execution')
    for name, key in [('prepared/manifest.json','prepared_sha256'), ('resource.json','resource_sha256'),
                      ('verification/cpu.json','cpu_sha256')]:
        if sha(directory / name) != manifest[key]:
            raise ValueError('frozen artifact changed: ' + name)
    for name, digest in manifest['protocol_docs'].items():
        if sha(directory / 'source' / name) != digest:
            raise ValueError('frozen protocol document changed: ' + name)
    verify(directory)


def progress_counts(directory):
    """CPU-only durable completed-game counts; failures never become results."""
    from collections import Counter
    counts = Counter()
    elapsed = 0.0
    for path in (Path(directory) / 'games').glob('*/outcome.json'):
        row = read(path)
        counts[row['status']] += 1
        counts['attempted'] += row['status'] != 'unattempted'
        if row['status'] == 'completed':
            counts[row['result']] += 1
        elapsed += row.get('elapsed_seconds', 0)
    return dict(counts=counts, summed_battle_seconds=elapsed)


def worker_environment(resource):
    """Verified deterministic backend applies before CUDA initialization on every launch."""
    uuids = [item['uuid'] for item in resource['gpus']]
    if len(uuids) != 4 or len(set(uuids)) != 4:
        raise ValueError('worker environment requires four distinct owned GPU UUIDs')
    return dict(os.environ, CUDA_VISIBLE_DEVICES=','.join(uuids),
                CUDA_DEVICE_ORDER='PCI_BUS_ID', OMP_NUM_THREADS='1',
                CUBLAS_WORKSPACE_CONFIG=BACKEND['cublas_workspace_config'],
                TORCH_NCCL_ASYNC_ERROR_HANDLING='1')


def supervisor(directory, resume=False):
    """torchrun terminates sibling ranks on any failure; restart once by receipt."""
    directory = Path(directory).resolve()
    with own_run(directory):
        if (directory / 'completed.json').exists():
            raise ValueError('closed experiment cannot run again')
        if (directory / 'manifest.json').exists() and not resume:
            raise ValueError('existing experiment requires --resume')
        with own_gpus(directory) as resource:
            freeze(directory)
            clock = Clock(directory, start=True)
            env = worker_environment(resource)
            from .recovery import validate
            recovery = validate(directory, current_sources=source_files())
            if recovery is not None:
                env['CUBLAS_WORKSPACE_CONFIG'] = recovery['backend']['cublas_workspace_config']
            attempts = 0
            while True:
                attempts += 1
                stream = (directory / f'worker-{time.time_ns()}.log').open('xb')
                command = [str(config.PYTHON), '-m', 'torch.distributed.run', '--standalone',
                           '--nnodes=1', '--nproc-per-node=4', '--max-restarts=0', '-m',
                           'integration.pokechamp.abyssal_rl', 'worker', '--output', str(directory)]
                historical_failures = {p.name: sha(p) for p in directory.glob('failure-rank-*.json')}
                process = subprocess.Popen(command, cwd=config.ROOT, env=env, stdin=subprocess.DEVNULL,
                                           stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                append(directory / 'process-events.jsonl', {'kind':'workers_start','pid':process.pid,'at':time.time()})
                heartbeat = 0
                viewer_process = viewer_stream = None
                terminated = False
                restart_sent = False
                failure_at = None
                try:
                    while process.poll() is None:
                        now = time.time()
                        if now - heartbeat >= 300:
                            state = read(directory / 'state.json') if (directory / 'state.json').exists() else {}
                            atomic(directory / 'supervisor.json', {'pid':os.getpid(),'worker_pid':process.pid,
                                   'at':now,'state':state,'attempt':attempts,'remaining_seconds':clock.remaining(),
                                   'gpus':gpu_facts(),'progress':progress_counts(directory),
                                   'gpu_hours_upper_bound':4 * (now - clock.record['started_at']) / 3600})
                            if viewer_process is None or viewer_process.poll() is not None:
                                if viewer_stream is not None:
                                    viewer_stream.close()
                                viewer_stream = (directory / f'viewer-worker-{time.time_ns()}.log').open('xb')
                                viewer_process = subprocess.Popen(
                                    ['/tmp/ep037/tools/bin/python', '-m', 'integration.pokechamp.abyssal_rl.viewer',
                                     '--incremental', str(directory)], cwd=config.ROOT,
                                    env=dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1'),
                                    stdin=subprocess.DEVNULL, stdout=viewer_stream, stderr=subprocess.STDOUT,
                                    start_new_session=True)
                                append(directory / 'process-events.jsonl', {'kind':'viewer_start',
                                       'pid':viewer_process.pid,'at':now})
                            heartbeat = now
                        new_failures = [p.name for p in directory.glob('failure-rank-*.json')
                                        if historical_failures.get(p.name) != sha(p)]
                        if new_failures and failure_at is None:
                            failure_at = now
                            os.killpg(process.pid, signal.SIGTERM)
                            atomic(directory / 'worker-failure-stop.json', {
                                'at': now, 'pid': process.pid, 'failures': new_failures})
                        if failure_at is not None and now - failure_at >= 30:
                            os.killpg(process.pid, signal.SIGKILL)
                        pending = directory / 'restart-pending.json'
                        if pending.exists() and not (directory / 'restart-complete.json').exists() and not restart_sent and failure_at is None:
                            receipt = read(pending)
                            if receipt.get('checkpoint_sha256') != read(directory / 'latest.json')['sha256']:
                                raise ValueError('restart request does not identify latest completed step')
                            os.killpg(process.pid, signal.SIGTERM)
                            restart_sent = True
                            atomic(directory / 'restart-signal.json', {'at':now,'pid':process.pid,
                                   'checkpoint_sha256':receipt['checkpoint_sha256']})
                        if clock.remaining() <= 60 and not terminated:
                            os.killpg(process.pid, signal.SIGTERM)
                            terminated = True
                        if clock.remaining() <= 0:
                            os.killpg(process.pid, signal.SIGKILL)
                        time.sleep(0.5)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    stream.close()
                    if viewer_process is not None:
                        from ..benchmark import terminate
                        terminate(viewer_process)
                        append(directory / 'process-events.jsonl', {'kind':'viewer_exit',
                               'pid':viewer_process.pid,'returncode':viewer_process.returncode,'at':time.time()})
                    if viewer_stream is not None:
                        viewer_stream.close()
                    cleanup_owned(directory)
                append(directory / 'process-events.jsonl', {'kind':'workers_exit','pid':process.pid,
                       'returncode':process.returncode,'at':time.time()})
                if restart_sent and not terminated and failure_at is None:
                    receipts = [read(directory / f'restart-rank-{rank}.json') for rank in range(4)]
                    expected = read(directory / 'restart-signal.json')['checkpoint_sha256']
                    if any(not r.get('signal_received') or r.get('checkpoint_sha256') != expected for r in receipts):
                        raise ValueError('actual SIGTERM receipt missing from a rank')
                    atomic(directory / 'restart-complete.json', {'at':time.time(),'receipts':receipts}, immutable=True)
                    continue
                atomic(directory / 'supervisor-exit.json', {'returncode':process.returncode,'at':time.time(),
                       'attempts':attempts,'reason':'budget' if terminated else 'worker_failure' if failure_at is not None else 'worker_exit'})
                return 1 if failure_at is not None else process.returncode
