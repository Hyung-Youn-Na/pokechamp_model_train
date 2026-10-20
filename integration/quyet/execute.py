"""One-shot EX-084 preparation, single-server qualification, collection and closure."""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time

from integration.jev27b.execute import child_environment as inherited_environment, stop_owned_process
from .config import (ACTOR_PYTHON, EVIDENCE, ENDPOINT, EXPORT, MODEL_DIR, PYTHON,
                     QUYET_SOURCE, ROOT, RUN)
from .storage import file_hash, read, write


def child_environment():
    env = inherited_environment()
    env['PYTHONPATH'] += ':' + str(QUYET_SOURCE / 'src')
    return env


def command_stage(command, name, *, env=None):
    process = None
    started = time.time()
    try:
        with (EVIDENCE / (name + '.log')).open('x') as output:
            process = subprocess.Popen(command, cwd=ROOT, env=env or child_environment(),
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            process.wait()
    finally:
        if process is not None:
            stop_owned_process(process)
    receipt = dict(passed=process is not None and process.returncode == 0,
                   command=[str(c) for c in command], started=started, seconds=time.time() - started,
                   exit_code=None if process is None else process.returncode)
    write(EVIDENCE / (name + '-process.json'), receipt)
    if not receipt['passed']:
        raise RuntimeError(name + ' failed; see evidence log')
    return receipt


def prepare():
    """Verify the official manifest using the one-time download hashes, then tokenize nine cases."""
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    download = read(EVIDENCE / 'download.json')
    if not download['passed']:
        raise ValueError('model download incomplete')
    declared = {}
    for line in (MODEL_DIR / 'MANIFEST.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1);declared[name] = digest
    actual = {row['path']: row['sha256'] for row in download['files']}
    if any(actual.get(name) != digest for name, digest in declared.items()):
        raise ValueError('official MANIFEST.sha256 differs from downloaded files')
    write(EVIDENCE / 'official-manifest.json', dict(passed=True, files=len(declared),
        manifest_sha256=actual['MANIFEST.sha256'], verification='download hashes compared once; no second weight hash pass'))
    command_stage([str(PYTHON), '-m', 'integration.quyet.gates', 'prepare'], 'lengths-prepare')
    return read(EVIDENCE / 'lengths.json')


def source_snapshot(sources):
    from .study import snapshot_sources
    snapshot_sources(RUN, sources)
    branch = subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    if branch != 'research/model-training':
        raise ValueError('wrong research checkout')
    write(EVIDENCE / 'source.json',dict(branch=branch,checkout=str(ROOT),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        working_changes=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),source=sources,
        model_python=str(PYTHON),actor_python=str(ACTOR_PYTHON)))
    for name in ('CHARTER.md','RESEARCH_DESIGN.md','CONTRACTS.md',
                 'decisions/D-133-quyet-medium-two-stage.md',
                 'exec-plans/active/EP-138-quyet-medium-two-stage.md',
                 'experiments/EX-084-quyet-medium-two-stage.md'):
        target=RUN/'protocol'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'project_context'/name,target)
    shutil.copytree(QUYET_SOURCE/'src/quyet',RUN/'source/external/quyet',
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('LICENSE', 'NOTICE'):
        shutil.copyfile(QUYET_SOURCE/name, RUN/'source/external'/('quyet-' + name))


def closure():
    from .resource import gpu_facts,gpu_compute_processes
    facts=gpu_facts();locks={};ports={}
    for index in range(4):
        with (ROOT/f'.pokechamp-data/locks/gpu{index}.lock').open('a+') as handle:
            try:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);locks[index]=True
                fcntl.flock(handle,fcntl.LOCK_UN)
            except BlockingIOError:locks[index]=False
    for port in (18784,8109):
        with socket.socket() as probe:
            try:probe.bind(('127.0.0.1',port));ports[port]=True
            except OSError:ports[port]=False
    selected=[row for row in gpu_compute_processes() if row['uuid'] in {f['uuid'] for f in facts.values()}]
    return dict(passed=all(locks.values()) and all(ports.values()) and not selected
                and all(facts[i]['memory_used_mib']<=256 for i in range(4)),
                gpus=facts,gpu_locks_released=locks,ports_released=ports,gpu_processes=selected,at=time.time())


def resource_summary():
    from .resource import disk_bytes
    result=dict(samples=0,gpu_max_mib={str(i):0 for i in range(4)},host_rss_max_bytes=0,
                observed_disk_max_bytes=0,errors=[],allocator_peak_bytes=0,reserved_peak_bytes=0)
    for path in RUN.rglob('resources-*.jsonl'):
        for line in path.open():
            row=json.loads(line);result['samples']+=1
            result['host_rss_max_bytes']=max(result['host_rss_max_bytes'],row['rss_bytes'])
            result['observed_disk_max_bytes']=max(result['observed_disk_max_bytes'],row['disk_bytes'])
            for i,gpu in row['gpus'].items():result['gpu_max_mib'][i]=max(result['gpu_max_mib'][i],gpu['memory_used_mib'])
            result['errors'].extend(row['errors'])
    # Responses contain synchronized allocator measurements from each physical inference.
    dbpath=RUN/'serving/server/requests.sqlite3'
    if dbpath.exists():
        import sqlite3
        db=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True)
        try:
            for (raw,) in db.execute("SELECT response_body FROM requests WHERE state='completed'"):
                memory=json.loads(raw)['metadata']['memory_after']
                result['allocator_peak_bytes']=max(result['allocator_peak_bytes'],*memory['peak_allocated'])
                result['reserved_peak_bytes']=max(result['reserved_peak_bytes'],*memory['peak_reserved'])
        finally:db.close()
    result['final_disk_bytes']=disk_bytes()
    return result


def inference_accounting(collection):
    """Resolve real server starts independently of HTTP attempts and response counts."""
    import sqlite3
    from .study import event_rows
    requests={e['request_id']:e['stage'] for e in event_rows(collection) if e['type']=='transport'}
    db=sqlite3.connect((RUN/'serving/server/requests.sqlite3').as_uri()+'?mode=ro',uri=True)
    try:
        starts=dict(db.execute("SELECT request_id,COUNT(*) FROM events WHERE kind='inference_started' GROUP BY request_id"))
        if any(n!=1 for n in starts.values()):raise ValueError('duplicate model inference')
        return dict(stage_inference_attempts={s:sum(starts.get(k,0) for k,v in requests.items() if v==s)
                    for s in ('action_type','action_detail')},
                    preflight_inferences=sum(n for k,n in starts.items() if k.startswith('ex084-gate-')),
                    total_server_inferences=sum(starts.values()),
                    requests_not_accepted=sum(k not in starts for k in requests),duplicate_inferences=0)
    finally:db.close()


def finalize():
    from . import study,viewer
    collection=RUN/'collection'
    if not (collection/'result.json').exists():
        return dict(passed=False,reason='collection_not_started')
    result=read(collection/'result.json');manifest=read(collection/'manifest.json')
    compared=study.comparison(manifest,result)
    write(EVIDENCE/'comparison.json',compared)
    calls=inference_accounting(collection);write(EVIDENCE/'inference-accounting.json',calls)
    exported=viewer.export(collection,EXPORT,compared=compared)
    command_stage(['/tmp/ep037/tools/bin/python','-m','integration.quyet.viewer','verify-browser',
        '--output',str(EXPORT),'--receipt',str(EVIDENCE/'browser.json')],'browser')
    final=dict(passed=result.get('final_audit_passed') is True and exported['passed'] and read(EVIDENCE/'browser.json')['passed'],
        export=exported,browser=read(EVIDENCE/'browser.json'),comparison=compared,inference_accounting=calls)
    write(EVIDENCE/'finalization.json',final)
    return final


def report(completion):
    result=completion.get('result') or dict(planned=32,attempted=0,completed=0,failed=0,invalid=0,unattempted=32,
        completed_pairs=0,overall=dict(wins=0,draws=0,losses=0),decisions=0,requests=0,tokens=None,
        received_usage={},stages={},usage_unknown_requests=0)
    final=completion.get('finalization') or {};compare=final.get('comparison',{});calls=final.get('inference_accounting',{})
    outcome=result['overall'];resource=completion['resources']
    text=f'''# EX-084 Quyet-Medium 2단계 고정 대진 평가

- 종결: {'Completed' if completion['passed'] else 'Incomplete / Stopped'}
- 새 경기: 예정32·시도{result['attempted']}·유효{result['completed']}·실패{result['failed']}·무효{result['invalid']}·미실행{result['unattempted']}
- 성적: {outcome['wins']}승 {outcome['draws']}무 {outcome['losses']}패, 완료쌍{result['completed_pairs']}/16
- 행동 결정{result['decisions']}·HTTP 시도{result['requests']}·단계별 추론 시도{calls.get('stage_inference_attempts')}
- 합산 토큰: {result['tokens']}; 확인된 usage {result['received_usage']}; 미확정 요청{result['usage_unknown_requests']}
- 단계별 지연 합(초): {result.get('stage_latency_seconds')}; 결정 지연 합{result.get('decision_latency_seconds')}
- EX-083 공통 유효쌍{compare.get('common_completed_pairs',0)}·점수 차이{compare.get('mean_pair_score_delta')}
- GPU 최대MiB: {resource['gpu_max_mib']}; allocator peak{resource['allocator_peak_bytes']}B; host RSS{resource['host_rss_max_bytes']}B
- 자원 반환: {completion['closure']['passed']}; 오류: {completion['error']}; 정리 오류: {completion['cleanup_errors']}

결과는 **Quyet-Medium + 2단계 정책 + 긴 입력 확장의 고정 대진 탐색 평가**다.
공식6000/8000토큰 범위와 선택 정책을 함께 변경했으므로 모델 가중치만의 효과를 주장하지 않는다.
GPU 사전9요청은 실행 가능성 검증이며 일반 성능이나 모든 길이의 안정성 보장이 아니다.
실패는 패배로 바꾸지 않았고 기존 EX-083 성적은 신규 분모에 계승하지 않았다.

원자료: `{RUN}/collection`; 단계별 집계·검증·봉인은 `evidence/completion.json`과
`evidence/finalization.json`에서 연결한다. [뷰어](/workspace/exports/battle_viewers/ex084/index.html).
'''
    (RUN/'report.md').write_text(text)


def finish_completion(completion):
    """Flush the terminal log before sealing a controller whose stdout is in RUN."""
    from . import study
    write(EVIDENCE/'completion.json', completion)
    report(completion)
    result = completion.get('result')
    print(json.dumps(dict(passed=completion['passed'], error=completion['error'],
        completed=result['completed'] if result else 0, report=str(RUN/'report.md')),
        ensure_ascii=False), flush=True)
    study.seal(RUN)


def execute():
    from . import battle,gates,study
    from .client import LocalClient
    from .resource import ResourceMonitor,wait_owned_gpu_release
    if (RUN/'execution.json').exists() or (RUN/'collection').exists() or EXPORT.exists():
        raise FileExistsError('EX-084 execution cannot overwrite or resume')
    for name in ('download.json','official-manifest.json','lengths.json'):
        if read(EVIDENCE/name).get('passed') is not True:raise ValueError('preparation incomplete: '+name)
    def interrupted(signum,frame):raise KeyboardInterrupt(f'EX-084 received signal {signum}')
    signal.signal(signal.SIGTERM,interrupted)
    model_process=log=client=None;error=None;cleanup=[];result=final=None
    started=time.time()
    write(RUN/'execution.json',dict(started=started,pid=os.getpid(),maximum_gpu_preflight_inferences=9,maximum_server_loads=1))
    try:
        sources=study.source_identity();source_snapshot(sources)
        cpu=command_stage([str(ACTOR_PYTHON),'-m','pytest','integration/quyet/tests','-q'],'cpu',
                          env=dict(child_environment(),CUDA_VISIBLE_DEVICES=''))
        write(EVIDENCE/'cpu.json',dict(cpu,source=sources))
        if not closure()['passed']:raise RuntimeError('required GPU/lock/ports are not idle')
        (RUN/'serving').mkdir()
        log=(RUN/'serving/server.log').open('x')
        model_process=subprocess.Popen([str(PYTHON),'-m','integration.quyet.server',
            '--model-dir',str(MODEL_DIR),'--run-dir',str(RUN/'serving'),'--budget-root',str(RUN),
            '--profile','ex084'],cwd=ROOT,env=child_environment(),stdin=subprocess.DEVNULL,
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        write(EVIDENCE/'server-process.json',dict(pid=model_process.pid,at=time.time()))
        with ResourceMonitor(EVIDENCE,budget_root=RUN):
            import httpx
            while True:
                if model_process.poll() is not None:raise RuntimeError('model server exited during load')
                try:
                    response=httpx.get(ENDPOINT+'/health',timeout=2,trust_env=False)
                    if response.status_code==200:break
                except httpx.RequestError:pass
                time.sleep(0.5)
            client=LocalClient(ENDPOINT);receipt=gates.qualify(client,sources)
            original=Path.cwd()
            try:
                os.chdir(ROOT/'pokechamp')
                result=asyncio.run(battle.run(RUN/'collection',expected_identity=receipt['serving_identity'],
                    gate_receipt=receipt,endpoint=ENDPOINT))
            finally:os.chdir(original)
    except BaseException as exc:
        error=dict(type=type(exc).__name__,detail=str(exc))
        write(EVIDENCE/'failure.json',dict(at=time.time(),error=error))
    finally:
        if client is not None:
            try:client.close()
            except Exception as exc:cleanup.append(str(exc))
        if model_process is not None:
            try:
                stop_owned_process(model_process)
                if (RUN/'serving'/f'gpu-acquire-{model_process.pid}.json').exists():
                    wait_owned_gpu_release(RUN/'serving',model_process.pid)
            except Exception as exc:cleanup.append(str(exc))
        if log is not None:log.close()
    try:
        with ResourceMonitor(EVIDENCE,budget_root=RUN):
            final=finalize()
    except BaseException as exc:
        error=error or dict(type=type(exc).__name__,detail=str(exc))
        write(EVIDENCE/'finalization-failure.json',dict(type=type(exc).__name__,detail=str(exc)))
    closed=closure();resources=resource_summary()
    completion=dict(passed=bool(result and result['passed'] and final and final['passed']
                    and closed['passed'] and not error and not cleanup),
                    result=result,finalization=final,closure=closed,resources=resources,error=error,
                    cleanup_errors=cleanup,started=started,ended=time.time(),elapsed_seconds=time.time()-started)
    finish_completion(completion)
    return completion


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','execute','finalize','status'])
    args=parser.parse_args()
    if args.command=='prepare':value=prepare()
    elif args.command=='execute':value=execute()
    elif args.command=='finalize':value=finalize()
    else:
        path=EVIDENCE/'completion.json'
        if not path.exists():path=RUN/'collection/progress.json'
        value=read(path) if path.exists() else dict(status='not_collected')
    if args.command!='execute':print(json.dumps(value,ensure_ascii=False))


if __name__=='__main__':main()
