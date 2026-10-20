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
    if not (output/"clock.json").exists():write_json(output/"clock.json",dict(first_started=time.time()))
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
                 HF_DEACTIVATE_ASYNC_LOAD='1',OMP_NUM_THREADS='4',PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
        command=[PYTHON,'-m','torch.distributed.run','--standalone','--nproc_per_node=3',
                 '-m','integration.jevk5_ruleqa_training.worker',action,'--output',str(output)]
        if resume:command+=['--resume',str(resume)]
        logpath=output/f'{action}-{time.time_ns()}.log'
        with logpath.open('x') as log:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            receipt.update(pid=child.pid,log=str(logpath))
            write_json(output/'active.json',receipt)
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
        write_json(output/f'{action}-receipt-{time.time_ns()}.json',receipt)
        write_json(output/'active.json',dict(running=False,last=receipt))



def prediction_rows(output,name):
    return sum((read_rows(output/'predictions'/name/f'rank-{r}.jsonl') for r in range(3)),[])


def calibrate(output):
    from .metrics import fit_temperature
    from .data import sha
    verify_prepared(output)
    if (output/'calibration.json').exists():raise FileExistsError('calibration locked')
    selected=read_json(output/'selection.json')
    result={key:fit_temperature(prediction_rows(output,name)) for key,name in
            [('base','validation-base'),('selected',f'validation-epoch-{selected["epoch"]}')]}
    result['selection_sha']=sha(output/'selection.json')
    write_json(output/'calibration.json',result)


def report(output):
    from .metrics import bootstrap,summarize
    base=prediction_rows(output,'test-base');tuned=prediction_rows(output,'test-selected')
    calibration=read_json(output/'calibration.json')
    interval=bootstrap(base,tuned)
    results={k:dict(raw=summarize(rows),calibrated=summarize(rows,calibration[k]['temperature']))
             for k,rows in [('base',base),('selected',tuned)]}
    write_json(output/'results.json',dict(models=results,bootstrap=interval))
    lines=['# JevK5 規則選択型 LoRA 評価'.replace('規則選択型','규칙 선택형').replace('評価','평가'),'',
        f"선택 epoch: {read_json(output/'selection.json')['epoch']}",'',
        '| 모델 | 정답/192 | 정확도 | T | NLL | Brier | ECE | 두 상황 정답/96 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for key,result in results.items():
        for mode,m in result.items():
            lines.append(f"| {key}/{mode} | {m['correct']} | {m['accuracy']:.6f} | {m['temperature']:.6f} | {m['nll']:.6f} | {m['brier']:.6f} | {m['ece']:.6f} | {m['paired']['both_correct']} |")
    lines+=['',f"정확도 차이 {interval['difference']*100:.3f}%p, 82성분 paired bootstrap 95% 구간 {[round(x*100,3) for x in interval['ci95']]}%p.",
        '동일 템플릿 규칙 QA 개선 근거가 있다.' if interval['ci95'][0]>0 else '개선은 입증되지 않았다. 음의 차이는 악화로 보고한다.',
        '', '기존 test 재사용·제어된 소규모 장면·동일 템플릿 평가다. 배틀 승률·미지 템플릿 일반화·학습 방식 자체의 우월성은 평가하지 않았다. 보정은 규칙 QA에만 적용한다.',
        '', '실험 수행 완료는 별도 completion.json의 검증·봉인·자원 반환 결과로 판정한다.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    table=['rule,base_correct,selected_correct,n']
    for rule,x in results['base']['raw']['rules'].items():
        y=results['selected']['raw']['rules'][rule];table.append(f"{rule},{x['correct']},{y['correct']},{x['n']}")
    (output/'rules.csv').write_text('\n'.join(table)+'\n')


def export(output):
    from .config import MODEL
    from .data import sha
    verify_prepared(output)
    selected=read_json(output/'selection.json')
    source=output/'checkpoints'/f'step-{selected["epoch"]*64:04d}'/'adapter'
    for name in ['test-base','test-selected']:
        assert read_json(output/'predictions'/name/'metrics.json')['n']==192
    shutil.copytree(source,output/'adapter')
    shutil.copytree(output/'tokenizer',output/'adapter/tokenizer')
    write_json(output/'adapter/base-model.json',dict(model=CONFIG['model'],revision=CONFIG['revision'],local_path=str(MODEL)))
    write_json(output/'adapter/training-config.json',CONFIG)
    from .data import INSTRUCTION
    write_json(output/'adapter/readout.json',dict(position='last_input_token',
        choices='original_QA_order',labels='ABCD',normalization='softmax_over_valid_choice_logits',
        selection='first_argmax',instruction=INSTRUCTION,enable_thinking=False,
        loss='one_hot_cross_entropy',temperature_scope='rule_qa_only'))
    shutil.copy2(output/'calibration.json',output/'adapter/calibration.json')
    shutil.copy2(ROOT/'integration/jevk5_ruleqa_training/loading.py',output/'adapter/loading.py')
    launch('reload',output)
    report(output)
    assert sum(len(read_json(output/f'reload-rank-{r}.json')['rows']) for r in range(3))==24
    checkpoints=sorted((output/'checkpoints').glob('step-*'))
    assert [int(p.name[5:]) for p in checkpoints]==list(range(0,193,16))
    for path in checkpoints:
        for name,digest in read_json(path/'complete.json')['files'].items():assert sha(path/name)==digest
    receipts=[read_json(p) for p in output.glob('*-receipt-*.json')]
    write_json(output/'usage.json',dict(first_started=read_json(output/'clock.json')['first_started'],
        gpu_stage_seconds=sum(r['ended']-r['started'] for r in receipts),receipts=receipts))
    # The launcher has joined its workers and released all three locks before this seal.
    write_json(output/'seal.json',{str(p.relative_to(output)):sha(p) for p in output.rglob('*')
                                 if p.is_file() and p.name not in ['seal.json','completion.json']})
    write_json(output/'completion.json',dict(completed=True,steps=192,reload_rows=24,
        workers_joined=True,locks_released=True,improvement_supported=read_json(output/'results.json')['bootstrap']['ci95'][0]>0))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','preflight','train','calibrate','evaluate','export','status'])
    parser.add_argument('--resume',type=Path)
    args=parser.parse_args();output=OUTPUT
    if args.resume and args.action!='train':parser.error('--resume only applies to train')
    if args.action=='status':
        for name in ['progress.json','selection.json','calibration.json','active.json','completion.json']:
            if (output/name).exists():print(name,json.dumps(read_json(output/name),ensure_ascii=False))
        return
    output.mkdir(parents=True,exist_ok=True)
    with (output/'controller.lock').open('a+') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='prepare':prepare(output)
        elif args.action=='calibrate':calibrate(output)
        elif args.action=='export':export(output)
        else:launch(args.action,output,args.resume)


if __name__=='__main__':main()
