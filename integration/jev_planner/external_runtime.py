"""EX-105 read-only external vLLM identity and owned-controller resource guard.

No signal is ever sent to the external server. Monitoring starts synchronously
before the CPU front and ends after that front is reaped.
"""
from pathlib import Path
import json
import os
import signal
import subprocess
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
ENDPOINT = 'http://127.0.0.1:18847/v1'
MODEL_DIR = ROOT / '.pokechamp-data/tacit9b-runtime/model'
REVISION = '884838f1698d1fd746625b3c20c8ec2be077a183'
GPU_UUID = 'GPU-c7e2d577-573f-0412-1ed6-ad6648efa454'


def start_ticks(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def get_models():
    with urllib.request.urlopen(ENDPOINT + '/models', timeout=5) as response:
        return json.load(response)


def _normalized_models(value):
    # API ModelCard.created is response-time metadata, not serving identity.
    return [{k: row[k] for k in ('id', 'root', 'max_model_len')}
            for row in value['data']]


def capture_identity():
    import psutil
    candidates = []
    for process in psutil.process_iter(['pid', 'cmdline']):
        args = process.info['cmdline'] or []
        if (any(Path(a).name == 'vllm' for a in args) and 'serve' in args
                and '--port' in args and args[args.index('--port') + 1] == '18847'):
            candidates.append(process)
    if len(candidates) != 1:
        raise ValueError('expected exactly one existing external vLLM server')
    server = candidates[0]
    args = server.cmdline()
    executable_root = ROOT / '.pokechamp-data/jev35b-nvfp4-runtime/.venv/bin'
    if args[:2] != [str(executable_root/'python3'), str(executable_root/'vllm')]:
        raise ValueError('external server interpreter does not match package probe')
    expected = {'--served-model-name':'tacit9b', '--host':'127.0.0.1', '--port':'18847',
        '--dtype':'bfloat16', '--tensor-parallel-size':'1', '--gpu-memory-utilization':'0.80',
        '--max-model-len':'49152', '--max-num-seqs':'1', '--mamba-cache-mode':'align',
        '--logprobs-mode':'raw_logprobs', '--max-logprobs':'256'}
    for key, value in expected.items():
        if key not in args or args[args.index(key)+1] != value:
            raise ValueError('external vLLM flag differs: ' + key)
    if str(MODEL_DIR) not in args or not {'--enable-prefix-caching','--language-model-only'} <= set(args):
        raise ValueError('external vLLM model/cache configuration differs')
    engines = [p for p in server.children(recursive=True) if 'VLLM::EngineCore' in p.name()]
    if len(engines) != 1:
        raise ValueError('expected exactly one live external EngineCore')
    # Never persist unselected environment values (credentials may exist there).
    environment = {k:v for k,v in server.environ().items() if k in
        ('CUDA_VISIBLE_DEVICES','VLLM_USE_FLASHINFER_SAMPLER','HF_HUB_OFFLINE',
         'TRANSFORMERS_OFFLINE','VLLM_CACHE_ROOT','TMPDIR')}
    if environment.get('CUDA_VISIBLE_DEVICES') != GPU_UUID or environment.get('VLLM_USE_FLASHINFER_SAMPLER') != '0':
        raise ValueError('external GPU/sampler environment differs')
    models = _normalized_models(get_models())
    if models != [dict(id='tacit9b',root=str(MODEL_DIR),max_model_len=49152)]:
        raise ValueError('external model endpoint differs')
    py = ROOT / '.pokechamp-data/jev35b-nvfp4-runtime/.venv/bin/python'
    packages = json.loads(subprocess.check_output([str(py), '-B', '-c',
        "import json;from importlib.metadata import version;print(json.dumps({k:version(k) for k in ('vllm','torch','transformers')}))"],text=True))
    if packages != {'vllm':'0.31.0+cu129','torch':'2.13.0+cu129','transformers':'5.17.0'}:
        raise ValueError('external package identity differs')
    return dict(endpoint=ENDPOINT,model='tacit9b',model_dir=str(MODEL_DIR),model_revision=REVISION,
        max_model_len=49152,server_pid=server.pid,server_start_ticks=start_ticks(server.pid),
        engine_pid=engines[0].pid,engine_start_ticks=start_ticks(engines[0].pid),
        gpu_uuid=GPU_UUID,physical_gpus=[1],server_command=args,environment=environment,
        packages=packages,models_response=models)


def verify_identity(receipt, *, health=True):
    for role in ('server','engine'):
        if start_ticks(receipt[role+'_pid']) != receipt[role+'_start_ticks']:
            raise ValueError('external process identity changed: '+role)
    args = Path(f'/proc/{receipt["server_pid"]}/cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
    if args != receipt['server_command']:
        raise ValueError('external command identity changed')
    if health and _normalized_models(get_models()) != receipt['models_response']:
        raise ValueError('external model endpoint identity changed')
    return True


class ExternalMonitor:
    def __init__(self,directory,receipt,*,budget_root):
        self.directory=Path(directory);self.receipt=receipt;self.budget_root=Path(budget_root)
        self.stop=threading.Event();self.thread=None;self.failure=None
        self.owner_pid=os.getpid();self.owner_ticks=start_ticks(self.owner_pid)
        self.next_disk=0;self.disk=0

    def sample(self,phase):
        import psutil
        from integration.jev27b.resource import gpu_facts
        verify_identity(self.receipt,health=phase!='poll')
        members={}
        for root_pid in (self.owner_pid,self.receipt['server_pid']):
            parent=psutil.Process(root_pid)
            for member in [parent,*parent.children(recursive=True)]:
                try:
                    members[member.pid]=dict(pid=member.pid,start_ticks=start_ticks(member.pid),
                        rss_bytes=member.memory_info().rss)
                except (psutil.NoSuchProcess,FileNotFoundError):
                    pass
        gpu=gpu_facts()[1]
        errors=[]
        rss=sum(p['rss_bytes'] for p in members.values())
        if gpu['uuid']!=self.receipt['gpu_uuid']:errors.append('gpu_identity_changed')
        if gpu['memory_used_mib']*1024**2>44*1024**3:errors.append('gpu1_memory_exceeded')
        if rss>32*1024**3:errors.append('host_memory_exceeded')
        if time.monotonic()>=self.next_disk or phase!='poll':
            self.disk=0
            for root in (self.budget_root,ROOT/'project_context/exec-plans/evidence/ep164'):
                for directory,_,files in os.walk(root):
                    for name in files:
                        try:self.disk+=(Path(directory)/name).lstat().st_size
                        except FileNotFoundError:pass
            self.next_disk=time.monotonic()+15
        result=dict(at=time.time(),phase=phase,rss_bytes=rss,members=list(members.values()),
            gpu=gpu,disk_bytes=self.disk,errors=errors,external_identity_verified=True)
        with (self.directory/'external-resources.jsonl').open('a') as out:
            out.write(json.dumps(result)+'\n')
        if errors:raise RuntimeError('external resource limit: '+','.join(errors))
        return result

    def _watch(self):
        while not self.stop.wait(.5):
            try:self.sample('poll')
            except BaseException as error:
                self.failure=dict(type=type(error).__name__,detail=str(error),at=time.time())
                (self.directory/'external-resource-stop.json').write_text(json.dumps(self.failure))
                if start_ticks(self.owner_pid)==self.owner_ticks:
                    os.kill(self.owner_pid,signal.SIGTERM)
                return

    def __enter__(self):
        self.directory.mkdir(parents=True,exist_ok=True)
        self.sample('begin')
        self.thread=threading.Thread(target=self._watch,name='external-resource-monitor',daemon=True)
        self.thread.start()
        return self

    def __exit__(self,*args):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=10)
            if self.thread.is_alive():raise RuntimeError('external monitor failed to stop')
        self.sample('end')
        if self.failure:raise RuntimeError('external resource monitor failed: '+str(self.failure))
