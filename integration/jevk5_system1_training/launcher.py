"""Physical GPU 1/2/3 controller; preserve foreign processes and prior receipts."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from .config import CONFIG, ROOT, PYTHON
from .data import dump, sha
from .prepare import verify

def read(path):return json.loads(Path(path).read_text())

def gpu_facts():
    result = subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used','--format=csv,noheader,nounits'],text=True)
    return [dict(index=int(a),uuid=b.strip(),memory_bytes=int(c)*1024**2)
            for a,b,c in (line.split(',') for line in result.strip().splitlines())]


def processes():
    result=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True)
    return [(int(a),b.strip()) for a,b in (line.split(',') for line in result.strip().splitlines())] if result.strip() else []


def descendants(pid):
    children = {pid}
    for _ in range(4):
        for path in Path('/proc').glob('[0-9]*/stat'):
            try:
                tail = path.read_text().rsplit(')',1)[1].split()
                if int(tail[1]) in children:children.add(int(path.parent.name))
            except (OSError,ValueError):pass
    return children


def launch(action, output, resume=None, microbatch=8):
    verify(output)
    if not (output/"clock.json").exists():dump(output/"clock.json",dict(first_started=time.time()))
    locks=[]; child=None
    started=time.time();max_memory={str(i):0 for i in [1,2,3]}
    receipt=dict(action=action,started=started,prepared_sha=sha(output/'prepared.json'),config=CONFIG)
    try:
        for index in [1,2,3]:
            path=ROOT/f'.pokechamp-data/locks/gpu{index}.lock'
            path.parent.mkdir(parents=True,exist_ok=True)
            handle=path.open('a+')
            locks.append(handle)
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        facts=gpu_facts()
        selected=[next(g for g in facts if g['index']==i) for i in [1,2,3]]
        assert all(g['memory_bytes']<100*1024**2 for g in selected),'assigned GPU not idle'
        uuids=[g['uuid'] for g in selected]
        assert not any(uuid in uuids for _,uuid in processes()),'assigned GPU has a process'
        receipt['gpus']=selected
        if (output/'gpu-identity.json').exists():
            assert read(output/'gpu-identity.json')==uuids,'GPU UUID identity changed'
        else:dump(output/'gpu-identity.json',uuids)
        env=dict(os.environ,CUBLAS_WORKSPACE_CONFIG=CONFIG['cublas_workspace_config'],CUDA_VISIBLE_DEVICES=','.join(uuids),CUDA_DEVICE_ORDER='PCI_BUS_ID',
                 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',
                 HF_DEACTIVATE_ASYNC_LOAD='1',OMP_NUM_THREADS='4',PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
        command=[PYTHON,'-m','torch.distributed.run','--standalone','--nproc_per_node=3',
                 '-m','integration.jevk5_system1_training.worker',action,'--output',str(output),'--microbatch',str(microbatch)]
        if resume:command+=['--resume',str(resume)]
        logpath=output/f'{action}-{time.time_ns()}.log'
        with logpath.open('x') as log:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            receipt.update(pid=child.pid,log=str(logpath))
            dump(output/'active.json',receipt)
            while child.poll() is None:
                owned=descendants(child.pid)|{os.getpid()}
                rss=0
                for pid in owned:
                    try:rss+=int(Path(f'/proc/{pid}/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                    except (FileNotFoundError,ProcessLookupError):pass
                receipt['max_host_rss']=max(receipt.get('max_host_rss',0),rss)
                if rss>CONFIG['host_limit_bytes']:raise RuntimeError('owned host RSS exceeds 64 GiB')
                for pid,uuid in processes():
                    if pid in owned and uuid not in uuids:
                        raise RuntimeError('owned process allocated outside physical GPUs 1,2,3')
                for fact in gpu_facts():
                    if fact['index'] in [1,2,3]:
                        key=str(fact['index']);max_memory[key]=max(max_memory[key],fact['memory_bytes'])
                        if fact['memory_bytes']>=CONFIG['memory_limit_bytes']:
                            raise RuntimeError('physical GPU memory exceeds 44 GiB')
                time.sleep(2)
        if child.returncode:
            raise RuntimeError(f'{action} failed ({child.returncode}); see {logpath}')
        receipt['passed']=True
    except BaseException as exc:
        receipt.update(passed=False,error=repr(exc))
        raise
    finally:
        if child and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL);child.wait()
        receipt.update(ended=time.time(),max_physical_memory=max_memory)
        for handle in reversed(locks):
            fcntl.flock(handle,fcntl.LOCK_UN);handle.close()
        dump(output/f'{action}-receipt-{time.time_ns()}.json',receipt)
        dump(output/'active.json',dict(running=False,last=receipt))


