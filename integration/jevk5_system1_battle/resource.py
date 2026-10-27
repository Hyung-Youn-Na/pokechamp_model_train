"""Own only GPU2 and the EX123 temporary server; preserve user's GPU1 server."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import urllib.request
import psutil
from integration.jev27b.resource import gpu_facts
from integration.jev27b.study import file_hash,write_json
from .core import ROOT,RUN,MODEL_DIR,REVISION,ENDPOINT,MODEL,MAX_CONTEXT,ADAPTER,BASE_MODEL_NAME,SERVER_PORT,GPU_INDEX


def ticks(pid):return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
def models():
    with urllib.request.urlopen(ENDPOINT+'/models',timeout=5) as response:data=json.load(response)
    return [{k:r.get(k) for k in ('id','root','max_model_len','parent')} for r in data['data']]


def capture():
    owner=json.loads((RUN/'owned-server.json').read_text())
    server=psutil.Process(owner['pid'])
    assert ticks(server.pid)==owner['ticks']
    args=server.cmdline()
    expected={'--served-model-name':BASE_MODEL_NAME,'--host':'127.0.0.1','--port':str(SERVER_PORT),
        '--dtype':'bfloat16','--lora-dtype':'bfloat16','--tensor-parallel-size':'1',
        '--max-model-len':str(MAX_CONTEXT),'--max-num-seqs':'1',
        '--lora-modules':MODEL+'='+str(ADAPTER),'--max-lora-rank':'16','--max-loras':'1',
        '--logprobs-mode':'raw_logprobs','--max-logprobs':'256','--generation-config':'vllm',
        '--gpu-memory-utilization':'0.80','--tokenizer':str(ADAPTER/'tokenizer')}
    for key,value in expected.items():assert key in args and args[args.index(key)+1]==value,key
    assert str(MODEL_DIR) in args and all(x in args for x in ['--enable-lora','--enforce-eager','--no-enable-prefix-caching'])
    gpu=gpu_facts()[GPU_INDEX]
    assert server.environ()['CUDA_VISIBLE_DEVICES']==gpu['uuid']==owner['gpu_uuid']
    expected_models=[dict(id=BASE_MODEL_NAME,root=str(MODEL_DIR),max_model_len=MAX_CONTEXT,parent=None),
                     dict(id=MODEL,root=str(ADAPTER),max_model_len=None,parent=BASE_MODEL_NAME)]
    assert models()==expected_models
    completed=json.loads((ADAPTER.parent/'completion.json').read_text());assert completed['completed']
    selected=json.loads((ADAPTER.parent/'selection.json').read_text());assert selected['epoch']==2
    seal=json.loads((ADAPTER.parent/'seal.json').read_text())
    adapter_files={str(p.relative_to(ADAPTER)):file_hash(p) for p in ADAPTER.rglob('*') if p.is_file()}
    for name,digest in adapter_files.items():assert digest==seal['adapter-selected/'+name],name
    model_files={p.name:file_hash(p) for p in MODEL_DIR.iterdir() if p.is_file()}
    assert model_files['model.safetensors']=='7060dee98993bb70865817007870d557e3dd42700d36b0e7c367c847bcfd2e8a'
    return dict(server_pid=server.pid,server_ticks=ticks(server.pid),command=args,models=expected_models,
        gpu_uuid=gpu['uuid'],physical_gpu=GPU_INDEX,revision=REVISION,files=model_files,
        adapter_files=adapter_files,adapter_path=str(ADAPTER),controller_pid=owner['controller_pid'],
        server_owned_by_experiment=True,user_server_preserved=True,at=time.time())


def verify(receipt,health=False):
    if ticks(receipt['server_pid'])!=receipt['server_ticks']:raise ValueError('temporary server identity changed')
    if psutil.Process(receipt['server_pid']).cmdline()!=receipt['command']:raise ValueError('server command changed')
    if health and models()!=receipt['models']:raise ValueError('server model registration changed')


def sample(receipt,directory,phase):
    verify(receipt)
    processes={}
    for pid in (os.getpid(),receipt['server_pid']):
        p=psutil.Process(pid)
        for child in [p,*p.children(recursive=True)]:
            try:processes[child.pid]=child.memory_info().rss
            except psutil.NoSuchProcess:pass
    gpu=gpu_facts()[GPU_INDEX];errors=[]
    if gpu['uuid']!=receipt['gpu_uuid']:errors.append(f'GPU{GPU_INDEX} identity changed')
    if gpu['memory_used_mib']>=44*1024:errors.append(f'GPU{GPU_INDEX} exceeds 44GiB')
    if sum(processes.values())>32*1024**3:errors.append('owned host process trees exceed 32GiB')
    row=dict(at=time.time(),phase=phase,gpu=gpu,host_rss_bytes=sum(processes.values()),processes=processes,errors=errors)
    with (Path(directory)/'resources.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
    if errors:raise RuntimeError('; '.join(errors))
    return row


@contextmanager
def borrowed_gpu(directory):
    # OwnedServer already holds the shared lock across gate and collection stages.
    owner=json.loads((RUN/'owned-server.json').read_text())
    if owner['controller_pid']!=os.getpid():raise RuntimeError('GPU stage requires the owning pipeline')
    assert psutil.pid_exists(owner['pid']) and ticks(owner['pid'])==owner['ticks']
    write_json(Path(directory)/'gpu-borrow.json',dict(at=time.time(),controller_pid=os.getpid(),physical_gpu=GPU_INDEX,outer_lock_held=True))
    yield
    write_json(Path(directory)/'gpu-borrow-release.json',dict(at=time.time(),outer_lock_held_until_server_cleanup=True))


class OwnedServer:
    def __init__(self):
        self.process=None;self.lock=None;self.log=None;self.thread=None
        self.stop=threading.Event();self.error=None;self.gpu=None
    def _sample(self):
        processes={}
        for child in [psutil.Process(os.getpid()),*psutil.Process(os.getpid()).children(recursive=True)]:
            try:processes[child.pid]=child.memory_info().rss
            except psutil.NoSuchProcess:pass
        gpu=gpu_facts()[GPU_INDEX]
        row=dict(at=time.time(),gpu=gpu,host_rss_bytes=sum(processes.values()),processes=processes)
        with (RUN/'owned-resources.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        if gpu['uuid']!=self.gpu['uuid'] or gpu['memory_used_mib']>=44*1024 or sum(processes.values())>32*1024**3:
            raise RuntimeError('owned server resource/identity limit exceeded')
    def _watch(self):
        while not self.stop.wait(2):
            try:self._sample()
            except BaseException as exc:
                self.error=repr(exc);write_json(RUN/'owned-resource-failure.json',dict(error=self.error,at=time.time()))
                if self.process and self.process.poll() is None:os.killpg(self.process.pid,signal.SIGTERM)
                return
    def __enter__(self):
        try:
            RUN.mkdir(parents=True,exist_ok=True)
            if (RUN/'owned-server.json').exists():raise FileExistsError('temporary server already attempted')
            self.lock=(ROOT/f'.pokechamp-data/locks/gpu{GPU_INDEX}.lock').open('a+')
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.gpu=gpu_facts()[GPU_INDEX]
            if self.gpu['memory_used_mib']>100:raise RuntimeError(f'GPU{GPU_INDEX} is not idle')
            import socket
            with socket.socket() as check:check.bind(('127.0.0.1',SERVER_PORT))
            args=[str(ROOT/'.pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/vllm'),'serve',str(MODEL_DIR),
                '--tokenizer',str(ADAPTER/'tokenizer'),'--served-model-name',BASE_MODEL_NAME,
                '--enable-lora','--lora-modules',MODEL+'='+str(ADAPTER),'--max-lora-rank','16','--max-loras','1',
                '--lora-dtype','bfloat16','--dtype','bfloat16','--tensor-parallel-size','1',
                '--gpu-memory-utilization','0.80','--max-model-len',str(MAX_CONTEXT),'--max-num-seqs','1',
                '--enforce-eager','--no-enable-prefix-caching','--logprobs-mode','raw_logprobs','--max-logprobs','256',
                '--generation-config','vllm','--host','127.0.0.1','--port',str(SERVER_PORT)]
            self.log=(RUN/'server.log').open('x')
            env=dict(os.environ,CUDA_VISIBLE_DEVICES=self.gpu['uuid'],HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
                     PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4')
            self.process=subprocess.Popen(args,cwd=ROOT,env=env,stdout=self.log,stderr=subprocess.STDOUT,start_new_session=True)
            write_json(RUN/'owned-server.json',dict(pid=self.process.pid,ticks=ticks(self.process.pid),controller_pid=os.getpid(),
                gpu_uuid=self.gpu['uuid'],physical_gpu=GPU_INDEX,command=args,started=time.time()))
            self.thread=threading.Thread(target=self._watch,daemon=True);self.thread.start()
            deadline=time.monotonic()+600
            while time.monotonic()<deadline:
                if self.error:raise RuntimeError(self.error)
                if self.process.poll() is not None:raise RuntimeError('temporary vLLM exited; see server.log')
                try:
                    with urllib.request.urlopen(ENDPOINT.removesuffix('/v1')+'/health',timeout=2) as response:
                        if response.status==200:return self
                except (OSError,TimeoutError):pass
                time.sleep(2)
            raise TimeoutError('temporary vLLM startup exceeded 600 seconds')
        except BaseException:
            self.__exit__(None,None,None);raise
    def __exit__(self,*exc):
        self.stop.set()
        if self.thread:self.thread.join(15)
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid,signal.SIGTERM)
            try:self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:os.killpg(self.process.pid,signal.SIGKILL);self.process.wait()
        if self.log:self.log.close()
        released=False
        if self.process:
            for _ in range(30):
                if gpu_facts()[GPU_INDEX]['memory_used_mib']<=256:released=True;break
                time.sleep(1)
        if self.lock:fcntl.flock(self.lock,fcntl.LOCK_UN);self.lock.close()
        write_json(RUN/'owned-server-cleanup.json',dict(at=time.time(),stopped=self.process is None or self.process.poll() is not None,
            gpu_released=released,lock_released=True,resource_error=self.error,user_server_preserved=True))
