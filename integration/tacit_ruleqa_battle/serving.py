"""Owned model process, resource monitor, and exactly-once local requests."""
import json
import os
import selectors
import subprocess
import threading
import time
import psutil
from .core import MODEL_PY, ROOT, RUN
from .storage import write


class Server:
    def __init__(self):
        self.process = None
        self.stop = threading.Event()
        self.failure = None
        self.calls = 0
        self.seen = set()
        self.lock = threading.Lock()
        self.started = time.time()
        self.log = None
        self.gpu_lock = None
        self.thread = None
        self.peak_rss = 0
        self.peak_gpu = 0

    def start(self):
        write(RUN/'clock.json', dict(first_gpu_preflight=self.started, deadline=self.started+43200, calls_limit=20000))
        from integration.jev27b.resource import gpu_facts, gpu_compute_processes
        import fcntl
        path = ROOT/'.pokechamp-data/locks/gpu1.lock'
        path.parent.mkdir(parents=True, exist_ok=True)
        self.gpu_lock = path.open('a+')
        fcntl.flock(self.gpu_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        facts = gpu_facts()
        gpu = facts[1]
        write(RUN/'gpu-before.json', dict(gpus=facts, processes=gpu_compute_processes()))
        # GPU is shared hardware: refuse foreign allocation; never reclaim it.
        if gpu['memory_used_mib'] > 0:
            raise RuntimeError('GPU1 is occupied')
        self.log = (RUN/'model.stderr.log').open('x')
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu['uuid'], PYTHONPATH=str(ROOT),
            TOKENIZERS_PARALLELISM='false', HF_HUB_OFFLINE='1', OMP_NUM_THREADS='4',
            PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='42')
        self.process = subprocess.Popen([str(MODEL_PY), '-m', 'integration.tacit_ruleqa_battle.model'],
            cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.log, text=True, bufsize=1, start_new_session=True)
        write(RUN/'model-owner.json', dict(pid=self.process.pid, gpu=1))
        self.thread = threading.Thread(target=self.monitor, daemon=True)
        self.thread.start()
        self.ready = self.receive(180)
        if not self.ready.get('ready'):
            raise RuntimeError('model not ready: '+repr(self.ready))
        from integration.jev27b.resource import canonical_gpu_uuid
        if canonical_gpu_uuid(self.ready['physical_uuid']) != canonical_gpu_uuid(gpu['uuid']):
            raise RuntimeError('model GPU UUID differs from owned physical GPU1')
        write(RUN/'model-ready.json', self.ready)
        return self

    def monitor(self):
        from integration.jev27b.resource import gpu_facts
        while not self.stop.wait(1):
            try:
                root = psutil.Process(os.getpid())
                processes = [root]+root.children(recursive=True)
                rss = 0
                for p in processes:
                    try:
                        rss += p.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
                gpu = gpu_facts()[1]
                memory = gpu['memory_used_mib']*1024**2
                self.peak_rss=max(self.peak_rss,rss); self.peak_gpu=max(self.peak_gpu,memory)
                with (RUN/'resources.jsonl').open('a') as stream:
                    stream.write(json.dumps(dict(at=time.time(), host_rss=rss, gpu_bytes=memory))+'\n')
                if rss > 32*1024**3 or memory > 44*1024**3 or time.time()-self.started >= 43200:
                    raise RuntimeError('resource/time limit exceeded')
            except Exception as exc:
                self.failure = exc
                if self.process and self.process.poll() is None:
                    self.process.terminate()
                return

    def receive(self, timeout):
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout):
                raise TimeoutError('model response timeout')
            line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('model server exited')
        return json.loads(line)

    def call(self, messages, decision):
        with self.lock:
            if self.failure:
                raise self.failure
            if decision in self.seen or self.calls >= 20000 or time.time()-self.started >= 43200:
                raise RuntimeError('duplicate request or budget exhausted')
            self.seen.add(decision)
            self.calls += 1
            write(RUN/'usage.json', dict(calls=self.calls, first_gpu_preflight=self.started))
            request = dict(id=decision, messages=messages)
            with (RUN/'model-requests.jsonl').open('a') as stream:
                stream.write(json.dumps(request)+'\n');stream.flush();os.fsync(stream.fileno())
            self.process.stdin.write(json.dumps(request)+'\n');self.process.stdin.flush()
            try:
                response = self.receive(180)
            except Exception:
                self.process.terminate()
                raise
            with (RUN/'model-responses.jsonl').open('a') as stream:
                stream.write(json.dumps(response)+'\n');stream.flush();os.fsync(stream.fileno())
            if response.get('id') != decision or 'error' in response:
                raise RuntimeError('model server error: '+repr(response))
            if self.failure:
                raise self.failure
            return response

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(15)
            except subprocess.TimeoutExpired:
                self.process.kill();self.process.wait(15)
        self.stop.set()
        if self.thread:
            self.thread.join(10)
        if self.log:
            self.log.close()
        if self.gpu_lock:
            self.gpu_lock.close()
        write(RUN/'model-cleanup.json', dict(pid=self.process.pid if self.process else None,
            stopped=self.process is None or self.process.poll() is not None, calls=self.calls,
            peak_host_rss=self.peak_rss, peak_gpu_bytes=self.peak_gpu,
            error=str(self.failure) if self.failure else None))
