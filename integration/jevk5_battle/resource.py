"""Read-only external server identity; never terminate the user's vLLM."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import urllib.request

import psutil

from integration.jev27b.resource import gpu_facts
from integration.jev27b.study import file_hash, write_json
from .core import ROOT, RUN, MODEL_DIR, REVISION, ENDPOINT, MODEL, MODEL_ID, MAX_CONTEXT


def ticks(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def models():
    with urllib.request.urlopen(ENDPOINT + '/models', timeout=5) as response:
        data = json.load(response)
    return [{k:r[k] for k in ('id', 'root', 'max_model_len')} for r in data['data']]


def capture():
    candidates = []
    for p in psutil.process_iter(['pid', 'cmdline']):
        args = p.info['cmdline'] or []
        if any(Path(x).name == 'vllm' for x in args) and 'serve' in args and '--port' in args:
            if args[args.index('--port') + 1] == '18847':
                candidates.append(p)
    if len(candidates) != 1:
        raise ValueError('expected one external server')
    server, = candidates
    args = server.cmdline()
    expected = {'--served-model-name':MODEL, '--host':'127.0.0.1', '--port':'18847',
        '--dtype':'bfloat16', '--tensor-parallel-size':'1', '--gpu-memory-utilization':'0.80',
        '--max-model-len':str(MAX_CONTEXT), '--max-num-seqs':'1', '--mamba-cache-mode':'align',
        '--logprobs-mode':'raw_logprobs', '--max-logprobs':'256', '--generation-config':'vllm'}
    for key, value in expected.items():
        if key not in args or args[args.index(key)+1] != value:
            raise ValueError('external flag differs: ' + key)
    if MODEL_ID not in args or '--enable-prefix-caching' not in args:
        raise ValueError('external model/cache differs')
    engines = [p for p in server.children(recursive=True) if 'VLLM::EngineCore' in p.name()]
    if len(engines) != 1:
        raise ValueError('expected one external engine')
    env = {k:v for k,v in server.environ().items() if k in
           ('CUDA_VISIBLE_DEVICES', 'VLLM_USE_FLASHINFER_SAMPLER', 'VLLM_CACHE_ROOT')}
    gpu = gpu_facts()[0]
    if env.get('CUDA_VISIBLE_DEVICES') not in ('0', gpu['uuid']):
        raise ValueError('external server must use GPU0')
    expected_models = [dict(id=MODEL, root=MODEL_ID, max_model_len=MAX_CONTEXT)]
    if models() != expected_models:
        raise ValueError('unexpected model endpoint')
    revision = (MODEL_DIR.parent.parent/'refs/main').read_text().strip()
    if revision != REVISION:
        raise ValueError('cached main revision changed since startup')
    files = {p.name:file_hash(p) for p in MODEL_DIR.iterdir() if p.is_file()}
    # HF Hub's global CAS path may be a cache object hash, not the LFS SHA256.
    # Compare the actual bytes to the pinned revision's official LFS metadata.
    expected_lfs = '7060dee98993bb70865817007870d557e3dd42700d36b0e7c367c847bcfd2e8a'
    if files.get('model.safetensors') != expected_lfs:
        raise ValueError('model artifact LFS identity mismatch')
    return dict(server_pid=server.pid, server_ticks=ticks(server.pid),
        engine_pid=engines[0].pid, engine_ticks=ticks(engines[0].pid), command=args,
        environment=env, models=expected_models, gpu_uuid=gpu['uuid'], revision=REVISION,
        files=files, artifact_metadata_source='https://huggingface.co/api/models/' + MODEL_ID +
        '/revision/' + REVISION + '?blobs=true', expected_weight_sha256=expected_lfs,
        external_server_owned_by_user=True, at=time.time())


def verify(receipt, health=False):
    for role in ('server', 'engine'):
        if ticks(receipt[role+'_pid']) != receipt[role+'_ticks']:
            raise ValueError('external process identity changed')
    if psutil.Process(receipt['server_pid']).cmdline() != receipt['command']:
        raise ValueError('external command changed')
    if health and models() != receipt['models']:
        raise ValueError('external model endpoint changed')


def sample(receipt, directory, phase):
    verify(receipt)
    processes = {}
    for pid in (os.getpid(), receipt['server_pid']):
        p = psutil.Process(pid)
        for child in [p, *p.children(recursive=True)]:
            try:
                processes[child.pid] = child.memory_info().rss
            except psutil.NoSuchProcess:
                pass
    gpu = gpu_facts()[0]
    errors = []
    if gpu['uuid'] != receipt['gpu_uuid']:
        errors.append('gpu identity changed')
    if gpu['memory_used_mib'] > 44*1024:
        errors.append('GPU0 exceeds 44GiB')
    if sum(processes.values()) > 32*1024**3:
        errors.append('host process trees exceed 32GiB')
    row = dict(at=time.time(), phase=phase, gpu=gpu, host_rss_bytes=sum(processes.values()),
               processes=processes, errors=errors)
    with (Path(directory)/'resources.jsonl').open('a') as stream:
        stream.write(json.dumps(row)+'\n')
    if errors:
        raise RuntimeError('; '.join(errors))
    return row


@contextmanager
def borrowed_gpu(directory):
    path = ROOT/'.pokechamp-data/locks/gpu0.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        write_json(Path(directory)/'gpu-borrow.json',dict(at=time.time(), controller_pid=os.getpid(),
            external_server_preserved=True, physical_gpu=0))
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            write_json(Path(directory)/'gpu-borrow-release.json',dict(at=time.time(),
                controller_lock_released=True, external_server_preserved=True))
