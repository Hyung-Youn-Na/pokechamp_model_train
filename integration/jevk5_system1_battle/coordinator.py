"""Three independent GPU replicas, disjoint paired schedules, one global budget and report."""
import argparse,fcntl,json,os,signal,subprocess,time
from pathlib import Path
import psutil
from .core import ROOT,ROOT_RUN,EXPORT_ROOT,BASELINE,ADAPTER
from .study import source_identity,partition_schedule
from integration.jev27b.study import write_json,file_hash,seal
from integration.project_context.registry import freeze_document,resolve_record


def read(p):return json.loads(Path(p).read_text())
def environment(gpu):return dict(os.environ,EX123_GPU=str(gpu),PYTHONPATH=f'{ROOT}:{ROOT}/pokechamp',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
def command(stage):return [str(ROOT/'pokechamp/.venv/bin/python'),'-B','-m','integration.jevk5_system1_battle.execute',stage]


def global_manifest():
    from .study import prepare_manifest
    m=prepare_manifest();full=read(BASELINE/'manifest.json')['schedule'];parts=partition_schedule(full)
    m['schedule']=full;m['shards']=parts;m['limits'].update(games=32,concurrency=3,calls=20000)
    m['model']['physical_gpus']=[1,2,3];m['model'].pop('physical_gpu',None);m['model'].pop('endpoint',None)
    m['model']['endpoints']={g:f'http://127.0.0.1:{18850+g}/v1' for g in (1,2,3)}
    m['model']['serving_lora_dtype']='bfloat16';m['model']['training_lora_dtype']='float32'
    return m


def prepare_mock():
    ROOT_RUN.mkdir(parents=True,exist_ok=True)
    if (ROOT_RUN/'cpu-check.json').exists():raise FileExistsError('CPU/mock stage already attempted')
    # Behavioral tests for policy/transport/resources/paired split and shared UI.
    tests=[str(ROOT/'pokechamp/.venv/bin/python'),'-B','-m','pytest','integration/jevk5_system1_battle/test_core.py','integration/jevk5_system1_battle/test_profile.py','integration/jevk5_system1_battle/test_parallel.py','-q']
    with (ROOT_RUN/'cpu-tests.log').open('x') as f:subprocess.run(tests,cwd=ROOT,env=environment(1),stdout=f,stderr=subprocess.STDOUT,check=True)
    with (ROOT_RUN/'ui-tests.log').open('x') as f:subprocess.run(['/tmp/ep037/tools/bin/python','-B','-m','pytest','integration/jevk5_system1_battle/test_viewer.py','-q'],cwd=ROOT,env=environment(1),stdout=f,stderr=subprocess.STDOUT,check=True)
    receipt=dict(passed=True,source=source_identity(),actual_model_calls=0)
    write_json(ROOT_RUN/'cpu-check.json',receipt)
    children=[]
    try:
        for gpu in (1,2,3):
            run=ROOT_RUN/'shards'/f'gpu{gpu}';run.mkdir(parents=True,exist_ok=True);write_json(run/'cpu-check.json',receipt)
            log=(run/'mock-console.log').open('x');p=subprocess.Popen(command('mock'),cwd=ROOT,env=environment(gpu),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            children.append((gpu,p,log))
        for gpu,p,log in children:
            if p.wait()!=0:raise RuntimeError(f'GPU{gpu} mock failed')
            log.close()
            run=ROOT_RUN/'shards'/f'gpu{gpu}';assert read(run/'mock/result.json')['passed']
        # Export separately to keep GPU-specific slot identities and raw events intact.
        for gpu in (1,2,3):
            run=ROOT_RUN/'shards'/f'gpu{gpu}'
            code="from integration.jevk5_system1_battle.viewer import export;from integration.jevk5_system1_battle.core import RUN;export(RUN/'mock',RUN/'mock-viewer')"
            subprocess.run([str(ROOT/'pokechamp/.venv/bin/python'),'-B','-c',code],cwd=ROOT,env=environment(gpu),check=True)
            subprocess.run(['/tmp/ep037/tools/bin/python','-B','-m','integration.jevk5_system1_battle.browser_check',str(run/'mock-viewer'),str(run/'mock-browser.json')],cwd=ROOT,env=environment(gpu),check=True)
        assert receipt['source']==source_identity()
        write_json(ROOT_RUN/'mock-complete.json',dict(passed=True,games=6,source=source_identity(),actual_model_calls=0))
    finally:
        for gpu,p,log in children:
            if p.poll() is None:
                os.killpg(p.pid,signal.SIGTERM)
                try:p.wait(timeout=20)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
            if not log.closed:log.close()


def resource_sample():
    parent=psutil.Process(os.getpid());values={}
    for child in [parent,*parent.children(recursive=True)]:
        try:values[child.pid]=child.memory_info().rss
        except psutil.NoSuchProcess:pass
    row=dict(at=time.time(),owned_host_rss=sum(values.values()),processes=values)
    with (ROOT_RUN/'global-resources.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    if row['owned_host_rss']>64*1024**3:raise RuntimeError('aggregate owned host RSS exceeds 64GiB')
    return row


def stop_owned_servers():
    for gpu in (1,2,3):
        path=ROOT_RUN/'shards'/f'gpu{gpu}'/'owned-server.json'
        if not path.exists():continue
        owner=read(path)
        try:
            tick=Path(f'/proc/{owner["pid"]}/stat').read_text().rsplit(')',1)[1].split()[19]
            if tick==owner['ticks']:os.killpg(owner['pid'],signal.SIGTERM)
        except (FileNotFoundError,ProcessLookupError):pass


def write_progress():
    parts={}
    for gpu in (1,2,3):
        directory=ROOT_RUN/'shards'/f'gpu{gpu}'/'collection'
        f=directory/'result.json' if (directory/'result.json').exists() else directory/'progress.json'
        if f.exists():
            try:r=read(f)
            except json.JSONDecodeError:continue
            parts[gpu]={k:r[k] for k in ['planned','attempted','completed','failed','invalid','unattempted','completed_pairs','overall','requests','error']}
            error=r.get('error')
            if error and any(word in str(error).lower() for word in ['identity','source changed','audit','input']):
                write_json(ROOT_RUN/'halt.json',dict(at=time.time(),gpu=gpu,error=error,scope='shared integrity'))
    write_json(ROOT_RUN/'progress.json',dict(at=time.time(),planned=32,completed=sum(r['completed'] for r in parts.values()),shards=parts))


def finish_documents(summary):
    done=read(ROOT_RUN/'completion.json')['completed'];state='Completed' if done else 'Blocked'
    ep=ROOT/'project_context/research/rule-learning/plans/EP-211-jevk5-system1-battle32.md'
    ex=ROOT/'project_context/research/rule-learning/experiments/EX-123-jevk5-system1-battle32.md'
    s=summary['overall'];body=f"\n## 실행 결과\n\n정상 {summary['completed']}/32, {s['wins']}승{s['draws']}무{s['losses']}패, 완전{summary['completed_pairs']}/16쌍. 실패{summary['failed']}·무효{summary['invalid']}·미실행{summary['unattempted']}. [최종 보고]({ROOT_RUN}/evidence/report.md) · [뷰어]({EXPORT_ROOT}/index.html). 과거 비교와 전이 한계는 보고서를 따른다.\n"
    text=ep.read_text().replace('- 상태: Active',f'- 상태: {state}')
    if done:text=text.replace('- [ ]','- [x]')
    ep.write_text(text+body);ex.write_text(ex.read_text().replace('- 상태: Running','- 상태: '+('Completed' if done else 'Stopped'))+body)
    status=ROOT/'project_context/STATUS.md';text=status.read_text().replace('에서 EX116 선택epoch2의 GPU1·2·3 병렬32경기 평가를 준비한다. GPU0/8107의 EP210과 분리한다.',f'에 EX116 선택epoch2의 GPU1·2·3 실전32 평가 결과를 기록했다(정상{summary["completed"]}/32). GPU0/8107의 EP210과 분리했다.');status.write_text(text)
    for stage in ['build','check']:subprocess.run([str(ROOT/'scripts/context-catalog'),stage],cwd=ROOT,check=True)


def run():
    for name in ['cpu-check.json','mock-complete.json']:assert read(ROOT_RUN/name)['passed'] and read(ROOT_RUN/name)['source']==source_identity()
    if (ROOT_RUN/'run-start.json').exists():raise FileExistsError('new32 already attempted; no automatic restart')
    write_json(ROOT_RUN/'run-start.json',dict(at=time.time(),pid=os.getpid(),gpus=[1,2,3],recollection=0))
    manifest=global_manifest();write_json(ROOT_RUN/'manifest.json',manifest)
    for key in ['EX-123','EP-211','D-186']:freeze_document(resolve_record(key),ROOT_RUN/'protocol'/f'{key}.md')
    children=[];failure=None
    try:
        for gpu in (1,2,3):
            shard=ROOT_RUN/'shards'/f'gpu{gpu}';log=(shard/'live-console.log').open('x')
            p=subprocess.Popen(command('run'),cwd=ROOT,env=environment(gpu),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            children.append((gpu,p,log))
            # Sequential model loading avoids simultaneous host staging. Each server stays live.
            while not (shard/'ready.json').exists():
                if p.poll() is not None:raise RuntimeError(f'GPU{gpu} qualification exited {p.returncode}')
                resource_sample();time.sleep(2)
        assert source_identity()==manifest['source']
        gates=[read(ROOT_RUN/'shards'/f'gpu{g}'/'preflight/complete.json') for g in (1,2,3)]
        comparisons=[]
        for i in range(6):
            base=gates[0]['results'][i]['body']['answers']['action']
            for gpu in (2,3):
                other=gates[gpu-1]['results'][i]['body']['answers']['action']
                comparisons.append(dict(gpu=gpu,kind=gates[0]['results'][i]['kind'],repeat=gates[0]['results'][i]['repeat'],same_choice=base['choice']==other['choice'],max_probability_delta=max(abs(base['probabilities'][k]-other['probabilities'][k]) for k in base['probabilities'])))
        write_json(ROOT_RUN/'replica-diagnostics.json',dict(passed_technical_gates=True,comparisons=comparisons,numerical_equality_required=False))
        write_json(ROOT_RUN/'start-collection.json',dict(at=time.time(),games=32,first_request_at=read(ROOT_RUN/'first-request.json')['first_request_at']))
        ex=ROOT/'project_context/research/rule-learning/experiments/EX-123-jevk5-system1-battle32.md';ex.write_text(ex.read_text().replace('- 상태: Planned','- 상태: Running'))
        while any(p.poll() is None for _,p,_ in children):
            resource_sample();write_progress();time.sleep(3)
        write_progress()
        if any(p.returncode for _,p,_ in children):raise RuntimeError('one or more shards failed; partial evidence preserved')
        from .report import finalize
        summary=finalize();finish_documents(summary)
        write_json(ROOT_RUN/'coordinator-result.json',dict(passed=read(ROOT_RUN/'completion.json')['completed'],at=time.time(),summary=summary))
    except BaseException as exc:
        failure=repr(exc);write_json(ROOT_RUN/'halt.json',dict(at=time.time(),error=failure));stop_owned_servers()
        write_json(ROOT_RUN/'coordinator-failure.json',dict(at=time.time(),error=failure))
        raise
    finally:
        for gpu,p,log in children:
            if p.poll() is None:
                try:p.wait(timeout=150)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid,signal.SIGTERM)
                    try:p.wait(timeout=20)
                    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
            log.close()
        if failure is None:
            # All three server/actor/browser trees are joined before sealing root evidence.
            seal(ROOT_RUN)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['prepare','run','status']);a=p.parse_args()
    if a.stage=='status':
        for name in ['progress.json','completion.json','coordinator-failure.json']:
            if (ROOT_RUN/name).exists():print(name,(ROOT_RUN/name).read_text())
        return
    ROOT_RUN.mkdir(parents=True,exist_ok=True)
    with (ROOT_RUN/'coordinator.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.stage=='prepare':prepare_mock()
        else:run()
if __name__=='__main__':main()
