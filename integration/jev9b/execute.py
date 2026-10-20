"""One-shot EX-085 preparation, eight-request single-server qualification, collection and closure."""
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
                     ROOT, RUN)
from .storage import file_hash, read, write


def child_environment():
    return inherited_environment()


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
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if not read(EVIDENCE / 'download.json')['passed']:
        raise ValueError('official model download incomplete')
    command_stage([str(PYTHON), '-m', 'integration.jev9b.gates', 'prepare'], 'lengths-prepare',
                  env=dict(child_environment(), CUDA_VISIBLE_DEVICES=''))
    return read(EVIDENCE / 'lengths.json')


def verify_cpu(sources):
    path = EVIDENCE/'cpu.json'
    if path.exists():
        receipt = read(path)
        if receipt.get('passed') is not True or receipt.get('source') != sources:
            raise ValueError('CPU validation does not cover the frozen collection source')
        return receipt
    cpu = command_stage([str(ACTOR_PYTHON), '-m', 'pytest', '--import-mode=importlib',
        'integration/jev9b/tests', 'integration/jev27b/tests/test_transport.py',
        'integration/jev27b/tests/test_formatting.py', 'integration/jev27b/tests/test_four_gpu.py',
        'integration/jev27b/tests/test_resource.py', 'integration/jev27b/tests/test_battle.py', '-q'],
        'cpu', env=dict(child_environment(), CUDA_VISIBLE_DEVICES=''))
    receipt = dict(cpu, source=sources)
    write(path, receipt)
    return receipt


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
                 'decisions/D-134-jev9b-single-choice.md',
                 'exec-plans/active/EP-139-jev9b-single-choice.md',
                 'experiments/EX-085-jev9b-single-choice.md'):
        target=RUN/'protocol'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'project_context'/name,target)


def closure():
    from .resource import gpu_facts,gpu_compute_processes
    facts=gpu_facts();locks={};ports={}
    for index in range(4):
        with (ROOT/f'.pokechamp-data/locks/gpu{index}.lock').open('a+') as handle:
            try:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);locks[index]=True
                fcntl.flock(handle,fcntl.LOCK_UN)
            except BlockingIOError:locks[index]=False
    for port in (18785,8109):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
    gate_path = EVIDENCE/'entry-gates.json'
    gate_end = read(gate_path)['at'] if gate_path.exists() else float('inf')
    result['phases'] = {name: dict(samples=0, gpu_max_mib={str(i): 0 for i in range(4)},
        host_rss_max_bytes=0, allocator_peak_bytes=0, reserved_peak_bytes=0)
        for name in ('preflight', 'collection_and_finalization')}
    for path in RUN.rglob('resources-*.jsonl'):
        for line in path.open():
            row=json.loads(line);result['samples']+=1
            result['host_rss_max_bytes']=max(result['host_rss_max_bytes'],row['rss_bytes'])
            result['observed_disk_max_bytes']=max(result['observed_disk_max_bytes'],row['disk_bytes'])
            for i,gpu in row['gpus'].items():result['gpu_max_mib'][i]=max(result['gpu_max_mib'][i],gpu['memory_used_mib'])
            result['errors'].extend(row['errors'])
            phase = result['phases']['preflight' if row['at'] <= gate_end else 'collection_and_finalization']
            phase['samples'] += 1
            phase['host_rss_max_bytes'] = max(phase['host_rss_max_bytes'], row['rss_bytes'])
            for i, gpu in row['gpus'].items():
                phase['gpu_max_mib'][i] = max(phase['gpu_max_mib'][i], gpu['memory_used_mib'])
    # Responses contain synchronized allocator measurements from each physical inference.
    dbpath=RUN/'serving/server/requests.sqlite3'
    if dbpath.exists():
        import sqlite3
        db=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True)
        try:
            for request_id, raw in db.execute("SELECT request_id,response_body FROM requests WHERE state='completed'"):
                memory=json.loads(raw)['metadata']
                result['allocator_peak_bytes']=max(result['allocator_peak_bytes'],*memory['gpu_peak_allocated_bytes'])
                result['reserved_peak_bytes']=max(result['reserved_peak_bytes'],*memory['gpu_reserved_bytes'])
                phase = result['phases']['preflight' if request_id.startswith('ex085-gate-') else 'collection_and_finalization']
                # CUDA peak is cumulative since the one load; NVML/RSS above are phase samples.
                phase['allocator_peak_bytes'] = max(phase['allocator_peak_bytes'], *memory['gpu_peak_allocated_bytes'])
                phase['reserved_peak_bytes'] = max(phase['reserved_peak_bytes'], *memory['gpu_reserved_bytes'])
        finally:db.close()
    result['final_disk_bytes']=disk_bytes()
    return result


def inference_accounting(collection):
    """Count physical starts separately from logical decisions and HTTP attempts."""
    import sqlite3
    from .study import event_rows
    requests = ({e['request_id'] for e in event_rows(collection) if e['type'] == 'transport'}
                if (collection/'events.jsonl').is_file() else set())
    path = RUN/'serving/server/requests.sqlite3'
    result = dict(collection_inferences=0, preflight_inferences=0, total_server_inferences=0,
        requests_not_accepted=len(requests), duplicate_inferences=0,
        preflight_received_usage=dict(input_tokens=0, output_tokens=0),
        preflight_inference_seconds=0, preflight_usage_unknown_requests=0,
        confirmed_server_loads=int((RUN/'serving/loaded.json').is_file()))
    if not path.exists():
        return result
    db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)
    try:
        starts = dict(db.execute("SELECT request_id,COUNT(*) FROM events WHERE kind='inference_started' GROUP BY request_id"))
        if any(n != 1 for n in starts.values()):
            raise ValueError('duplicate model inference')
        result.update(collection_inferences=sum(starts.get(k, 0) for k in requests),
                    preflight_inferences=sum(n for k,n in starts.items() if k.startswith('ex085-gate-')),
                    total_server_inferences=sum(starts.values()),
                    requests_not_accepted=sum(k not in starts for k in requests), duplicate_inferences=0)
        answered = set()
        for request_id, raw in db.execute("SELECT request_id,response_body FROM requests WHERE state='completed'"):
            if not request_id.startswith('ex085-gate-'):
                continue
            body = json.loads(raw)
            if all(k in body.get('usage', {}) for k in ('input_tokens', 'output_tokens')):
                answered.add(request_id)
                for key in result['preflight_received_usage']:
                    result['preflight_received_usage'][key] += body['usage'][key]
            result['preflight_inference_seconds'] += body.get('metadata', {}).get('elapsed_seconds', 0)
        result['preflight_usage_unknown_requests'] = sum(
            k.startswith('ex085-gate-') and k not in answered for k in starts)
        return result
    finally:
        db.close()


def finalize(*, accounting=None):
    from . import study,viewer
    collection=RUN/'collection'
    if not (collection/'result.json').exists():
        return dict(passed=False,reason='collection_not_started')
    result=read(collection/'result.json');manifest=read(collection/'manifest.json')
    compared=study.comparison(manifest,result)
    write(EVIDENCE/'comparison.json',compared)
    calls=accounting if accounting is not None else inference_accounting(collection)
    exported=viewer.export(collection,EXPORT,compared=compared)
    command_stage(['/tmp/ep037/tools/bin/python','-m','integration.jev9b.viewer','verify-browser',
        '--output',str(EXPORT),'--receipt',str(EVIDENCE/'browser.json')],'browser')
    final=dict(passed=result.get('final_audit_passed') is True and exported['passed'] and read(EVIDENCE/'browser.json')['passed'],
        export=exported,browser=read(EVIDENCE/'browser.json'),comparison=compared,inference_accounting=calls)
    write(EVIDENCE/'finalization.json',final)
    return final


def report(completion):
    from statistics import median
    result = completion.get('result') or dict(planned=32, attempted=0, completed=0, failed=0,
        invalid=0, unattempted=32, completed_pairs=0, overall=dict(wins=0, draws=0, losses=0),
        decisions=0, requests=0, tokens=None, received_usage={}, usage_unknown_requests=0)
    final = completion.get('finalization') or {}
    compare = final.get('comparison', {})
    calls = completion.get('inference_accounting') or final.get('inference_accounting', {})
    outcome = result['overall']
    resource = completion['resources']
    latencies = sorted(result.get('latency_seconds', []))
    text = f"""# EX-085 JEV-9B 단일 Choice 고정 대진 평가

- 종결: {'Completed' if completion['passed'] else 'Incomplete / Stopped'}
- 새 경기: 예정32·시도{result['attempted']}·유효{result['completed']}·실패{result['failed']}·무효{result['invalid']}·미실행{result['unattempted']}
- 성적: {outcome['wins']}승 {outcome['draws']}무 {outcome['losses']}패; 완료율{result['completed']/32:.2%}; 유효쌍{result['completed_pairs']}/16
- 행동 결정{result['decisions']}·실제 본수집 추론{calls.get('collection_inferences')}·HTTP POST시도{result['requests']}·재전송{result.get('retry_attempts')}
- 자동 선택{result.get('automatic_actions')}·실제 명령{result.get('sent_actions')}·중복 추론{calls.get('duplicate_inferences')}
- 본수집 토큰: {result['tokens']}; 확인된 usage {result['received_usage']}; 미확정 요청{result['usage_unknown_requests']}
- 응답 지연 중앙값(초): {median(latencies) if latencies else None}; 실제 추론 지연 합{result.get('inference_latency_seconds')}; 결정 지연 합{result.get('decision_latency_seconds')}
- EX-083 공통 유효쌍{compare.get('common_completed_pairs',0)}·기준 점수{compare.get('before_pair_score')}·새 점수{compare.get('after_pair_score')}·점수 차이{compare.get('mean_pair_score_delta')}
- 사전검증: 확인된 서버 적재{calls.get('confirmed_server_loads')}·실제 추론{calls.get('preflight_inferences')}·확인된 usage{calls.get('preflight_received_usage')}·미확정 요청{calls.get('preflight_usage_unknown_requests')}·추론 지연{calls.get('preflight_inference_seconds')}초; 본수집 성적/비용에서 분리
- GPU 최대MiB: {resource['gpu_max_mib']}; allocator peak{resource['allocator_peak_bytes']}B·reserved peak{resource['reserved_peak_bytes']}B; host RSS{resource['host_rss_max_bytes']}B; 디스크 최대{resource['observed_disk_max_bytes']}B
- 자원 반환: {completion['closure']['passed']}; 오류: {completion['error']}; 정리 오류: {completion['cleanup_errors']}

결과는 **동일 입력·단일 선택 정책에서 공식 JEV-9B와 JEV-27B 패키지를 비교한 고정 대진 탐색 평가**다.
EX-083은2GPU 완료23경기·4GPU 완료9경기의 계승 구성이다. 공식 모델 가중치·결정 head·보정값·장치 배치 차이가 함께 있으므로 일반 성능 우위나 모델 크기만의 효과를 주장하지 않는다.
GPU 사전8요청은 관측한 길이에서의 실행 가능성 근거이며 모든 입력 길이 안정성 보장이 아니다.
실패를 패배로 바꾸지 않았고 기존 EX-083 성적을 새 분모에 계승하지 않았다. 설명 정확성은 미평가다.

원자료: `{RUN}/collection`; 감사·사용량·비교·뷰어·자원·봉인 연결은 `evidence/completion.json`과 `evidence/finalization.json`을 따른다.
[뷰어](/workspace/exports/battle_viewers/ex085/index.html).
"""
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
        raise FileExistsError('EX-085 execution cannot overwrite or resume')
    for name in ('download.json','model-ready.json','lengths.json'):
        if read(EVIDENCE/name).get('passed') is not True:raise ValueError('preparation incomplete: '+name)
    def interrupted(signum,frame):raise KeyboardInterrupt(f'EX-085 received signal {signum}')
    signal.signal(signal.SIGTERM,interrupted)
    model_process=log=client=None;error=None;cleanup=[];result=final=None;calls=None
    started=time.time()
    write(RUN/'execution.json',dict(started=started,pid=os.getpid(),maximum_gpu_preflight_inferences=8,maximum_server_loads=1))
    try:
        sources=study.source_identity();source_snapshot(sources)
        verify_cpu(sources)
        if not closure()['passed']:raise RuntimeError('required GPU/lock/ports are not idle')
        (RUN/'serving').mkdir()
        log=(RUN/'serving/server.log').open('x')
        model_process=subprocess.Popen([str(PYTHON),'-m','integration.jev9b.server',
            '--model-dir',str(MODEL_DIR),'--run-dir',str(RUN/'serving'),'--budget-root',str(RUN),
            '--profile','ex085'],cwd=ROOT,env=child_environment(),stdin=subprocess.DEVNULL,
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
    # An interrupt can unwind asyncio.run after the runner saved its partial result.
    # Preserve that attempted/failed denominator even when no value was returned.
    if result is None and (RUN/'collection/result.json').is_file():
        result = read(RUN/'collection/result.json')
    try:
        calls=inference_accounting(RUN/'collection')
        write(EVIDENCE/'inference-accounting.json',calls)
        with ResourceMonitor(EVIDENCE,budget_root=RUN):
            final=finalize(accounting=calls)
    except BaseException as exc:
        error=error or dict(type=type(exc).__name__,detail=str(exc))
        write(EVIDENCE/'finalization-failure.json',dict(type=type(exc).__name__,detail=str(exc)))
    closed=closure();resources=resource_summary()
    completion=dict(passed=bool(result and result['passed'] and final and final['passed']
                    and closed['passed'] and not error and not cleanup),
                    result=result,finalization=final,inference_accounting=calls,
                    closure=closed,resources=resources,error=error,
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
