"""CPU controller owns locks and UUID visibility before spawning Torch workers."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from .config import CONFIG, OUTPUT, ROOT, PYTHON, DATA
from .data import prepare, read_json, read_rows, write_json, write_rows, verify_prepared


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


def launch(action, output, resume=None):
    verify_prepared(output)
    locks=[]; child=None
    started=time.time();max_memory={str(i):0 for i in [1,2,3]}
    receipt=dict(action=action,started=started)
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
        env=dict(os.environ,CUDA_VISIBLE_DEVICES=','.join(uuids),CUDA_DEVICE_ORDER='PCI_BUS_ID',
                 HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',
                 OMP_NUM_THREADS='4',PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
        command=[PYTHON,'-m','torch.distributed.run','--standalone','--nproc_per_node=3',
                 '-m','integration.pokechamp.rule_qa_training.worker',action,'--output',str(output)]
        if resume:command+=['--resume',str(resume)]
        logpath=output/f'{action}-{time.time_ns()}.log'
        with logpath.open('x') as log:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            receipt.update(pid=child.pid,log=str(logpath))
            write_json(output/'active.json',receipt)
            while child.poll() is None:
                owned=descendants(child.pid)
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
        write_json(output/f'{action}-receipt-{time.time_ns()}.json',receipt)
        write_json(output/'active.json',dict(running=False,last=receipt))


def report(output):
    from .metrics import bootstrap
    base=sum((read_rows(output/'predictions/test-base'/f'rank-{r}.jsonl') for r in range(3)),[])
    tuned=sum((read_rows(output/'predictions/test-selected'/f'rank-{r}.jsonl') for r in range(3)),[])
    interval=bootstrap(base,tuned)
    assert interval['components']==82
    write_json(output/'bootstrap.json',interval)
    # Deterministic ID-only sample selection; review labels reveal no model identity.
    groups={}
    for row in base:
        if row['representation']=='state_qa':groups.setdefault(row['rule_id'],set()).add(row['group_id'])
    chosen={min(v) for v in groups.values()}
    canonical={r['id']:r for r in read_rows(DATA/'test.jsonl')}
    b={r['id']:r for r in base};t={r['id']:r for r in tuned}
    import random
    rng=random.Random(CONFIG['seed']);review=[];key={}
    for ident in sorted(b):
        row=b[ident]
        if row['representation']!='state_qa' or row['group_id'] not in chosen:continue
        swap=bool(rng.randrange(2))
        left,right=(t[ident],b[ident]) if swap else (b[ident],t[ident])
        review.append(dict(id=ident,question=canonical[ident],A=left['raw_response'],B=right['raw_response']))
        key[ident]=dict(A='selected' if swap else 'base', B='base' if swap else 'selected')
    assert len(review)==48
    write_rows(output/'blind-review.jsonl',review)
    write_json(output/'blind-key.json',key)
    bm=read_json(output/'predictions/test-base/metrics.json')
    tm=read_json(output/'predictions/test-selected/metrics.json')
    lines=['# Tacit 규칙 Q&A LoRA 결과','',f"선택 epoch: {read_json(output/'selection.json')['epoch']}",'',
           '| 표현 | 기반 | 선택 모델 |','|---|---:|---:|']
    for form in bm['forms']:
        x,y=bm['forms'][form],tm['forms'][form]
        lines.append(f"| {form} | {x['correct']}/{x['n']} | {y['correct']}/{y['n']} |")
    lines+=['',f"State MC 차이 {interval['difference']:.4f}, 연결 성분 bootstrap95% 구간 {interval['ci95']}.",
            '', '자유형은 정규화 문자열 일치율이며 의미 정확도와 다르다. 같은 템플릿의 제어 장면 평가로 실제 배틀·긴 Thinking·미지 형식 일반화는 미평가다.',
            '', '블라인드 의미 검토와 재로딩 검사는 별도 결과 파일을 확인한다.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    table=['rule,base_mc,selected_mc,base_state_qa_exact,selected_state_qa_exact']
    for rule in bm['rules']:
        x,y=bm['rules'][rule],tm['rules'][rule]
        table.append(f"{rule},{x['state_mc']['accuracy']},{y['state_mc']['accuracy']},{x['state_qa']['accuracy']},{y['state_qa']['accuracy']}")
    (output/'rules.csv').write_text('\n'.join(table)+'\n')


def export(output):
    selected=read_json(output/'selection.json')
    source=output/'checkpoints'/f'step-{selected["epoch"]*192:04d}'/'adapter'
    shutil.copytree(source,output/'adapter')
    shutil.copytree(output/'tokenizer',output/'adapter/tokenizer')
    write_json(output/'adapter/base-model.json',dict(model=CONFIG['model'],revision=CONFIG['revision'],
               local_path=str(ROOT/'.pokechamp-data/tacit9b-runtime/model')))
    write_json(output/'adapter/training-config.json',CONFIG)
    (output/'adapter/loading.py').write_text('''from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch
# CUDA_VISIBLE_DEVICES는 실행 전 사용할 GPU UUID로 설정한다.
base = AutoModelForCausalLM.from_pretrained(
    "morriszjm/Tacit-9B", revision="884838f1698d1fd746625b3c20c8ec2be077a183",
    dtype=torch.bfloat16, attn_implementation="sdpa")
model = PeftModel.from_pretrained(base, ".").eval()
tokenizer = AutoTokenizer.from_pretrained("./tokenizer")
# apply_chat_template(..., add_generation_prompt=True, enable_thinking=False)
''')
    launch('reload',output)
    report(output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','preflight','train','evaluate','export','status'])
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--resume',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output)
    elif args.action=='status':
        for name in ['prepared.json','preflight.json','progress.json','selection.json','active.json']:
            if (args.output/name).exists():print(name,json.dumps(read_json(args.output/name),ensure_ascii=False))
    elif args.action=='export':export(args.output)
    else:launch(args.action,args.output,args.resume)


if __name__=='__main__':main()
