"""One-shot v6 cohort controller, sequential admission and immutable closure."""
from __future__ import annotations

from integration.project_context.registry import freeze_document

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
from .config import (ACTOR_PYTHON, BROWSER_PYTHON, EXPERIMENTS, NO_DAMAGE_VERSION, PORT,
                     PYTHON, ROOT, experiment)
from .failures import (ModelFailure, RecordedFailure, SharedFailure, error_record,
                       may_continue_other_model, resource_scope)
from .storage import file_hash, read, write


def child_environment():
    return inherited_environment()


def reject_environment_overrides(config):
    # Reject at ingress, before the child environment intentionally removes
    # unrelated variables. Otherwise a prohibited override would disappear
    # before the model loader could report it.
    if experiment(config).is_minicpm:
        from integration.minicpm5_jev.model import reject_overrides
        reject_overrides()


def command_stage(config, command, name, *, env=None):
    cfg = experiment(config)
    process = None
    started = time.time()
    try:
        with (cfg.evidence / (name + '.log')).open('x') as output:
            process = subprocess.Popen(command, cwd=ROOT, env=env or child_environment(),
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            process.wait()
    finally:
        if process is not None:
            stop_owned_process(process)
    receipt = dict(passed=process is not None and process.returncode == 0,
                   command=[str(c) for c in command], started=started, seconds=time.time() - started,
                   exit_code=None if process is None else process.returncode)
    write(cfg.evidence / (name + '-process.json'), receipt)
    if not receipt['passed']:
        raise RuntimeError(name + ' failed; see evidence log')
    return receipt


def verify_cpu(config, sources):
    cfg = experiment(config)
    path = cfg.evidence/'cpu.json'
    if path.exists():
        receipt = read(path)
        if receipt.get('passed') is not True or receipt.get('source') != sources:
            raise ValueError('CPU validation does not cover the frozen collection source')
        return receipt
    first = EXPERIMENTS[cfg.cohort.first].evidence / 'cpu.json'
    if cfg.predecessor is not None and first.is_file():
        earlier = read(first)
        if earlier.get('passed') is True and earlier.get('source') == sources:
            receipt = dict(earlier, reused_from=str(first), reused_sha256=file_hash(first))
            write(path, receipt)
            return receipt
    cpu = command_stage(cfg, [str(ACTOR_PYTHON), '-m', 'pytest', '--import-mode=importlib',
        'integration/jev_eval/tests', 'integration/pokechamp/tests/test_jev_v6.py',
        *(['integration/pokechamp/tests/test_jev_v6_no_damage.py',
           'integration/pokechamp/tests/test_jev_offline.py',
           'integration/pokechamp/tests/test_jev_damage_samples.py']
          if cfg.input_version == NO_DAMAGE_VERSION else []),
        'integration/jev27b/tests/test_transport.py',
        'integration/jev27b/tests/test_formatting.py', 'integration/jev27b/tests/test_four_gpu.py',
        'integration/jev27b/tests/test_resource.py', 'integration/jev27b/tests/test_battle.py',
        'integration/jev27b/tests/test_input_adapter.py', '-q'],
        'cpu', env=dict(child_environment(), CUDA_VISIBLE_DEVICES=''))
    receipt = dict(cpu, source=sources)
    if cfg.is_minicpm:
        # Official MiniCPM code imports PEFT. Keep those CPU formula/token tests
        # in the already-pinned model environment, without changing the actor env.
        receipt['model_cpu'] = command_stage(cfg, [str(PYTHON), '-m', 'pytest',
            '--import-mode=importlib', 'integration/minicpm5_jev/tests', '-q'],
            'model-cpu', env=dict(child_environment(), CUDA_VISIBLE_DEVICES=''))
    write(path, receipt)
    return receipt


def source_snapshot(config, sources):
    cfg = experiment(config)
    from .study import snapshot_sources
    snapshot_sources(cfg.run, sources)
    branch = subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
    if branch != 'research/model-training':
        raise ValueError('wrong research checkout')
    write(cfg.evidence / 'source.json',dict(branch=branch,checkout=str(ROOT),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        working_changes=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),source=sources,
        model_python=str(PYTHON),actor_python=str(ACTOR_PYTHON)))
    for name in ('CHARTER.md','RESEARCH_DESIGN.md','CONTRACTS.md', *cfg.cohort.protocol_files):
        target=cfg.run/'protocol'/name;target.parent.mkdir(parents=True,exist_ok=True)
        freeze_document(ROOT/'project_context'/name, target)


def closure(config=None):
    from .resource import gpu_facts,gpu_compute_processes
    cfg = experiment(config) if config is not None else None
    indices = cfg.runtime.physical_gpus if cfg is not None else tuple(range(4))
    all_facts=gpu_facts();locks={};ports={}
    if any(index not in all_facts for index in indices):
        raise SharedFailure('required physical GPU is missing during closure')
    facts = {index: all_facts[index] for index in indices}
    for index in indices:
        lock = ROOT/f'.pokechamp-data/locks/gpu{index}.lock'
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open('a+') as handle:
            try:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);locks[index]=True
                fcntl.flock(handle,fcntl.LOCK_UN)
            except BlockingIOError:locks[index]=False
    required_ports = ({PORT, cfg.server_port} if cfg is not None else
                      {PORT, *(item.server_port for item in EXPERIMENTS.values()
                               if not item.is_minicpm)})
    for port in sorted(required_ports):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:probe.bind(('127.0.0.1',port));ports[port]=True
            except OSError:ports[port]=False
    selected=[row for row in gpu_compute_processes() if row['uuid'] in {f['uuid'] for f in facts.values()}]
    return dict(passed=all(locks.values()) and all(ports.values()) and not selected
                and all(facts[i]['memory_used_mib']<=256 for i in indices),
                gpus=facts,gpu_locks_released=locks,ports_released=ports,gpu_processes=selected,at=time.time())


def resource_summary(config):
    cfg = experiment(config)
    from .resource import disk_bytes
    result=dict(samples=0,gpu_max_mib={str(i):0 for i in cfg.runtime.physical_gpus},host_rss_max_bytes=0,
                observed_disk_max_bytes=0,errors=[],allocator_peak_bytes=0,reserved_peak_bytes=0)
    gate_path = cfg.evidence/'entry-gates.json'
    gate_end = read(gate_path)['at'] if gate_path.exists() else float('inf')
    result['phases'] = {name: dict(samples=0, gpu_max_mib={str(i): 0 for i in cfg.runtime.physical_gpus},
        host_rss_max_bytes=0, allocator_peak_bytes=0, reserved_peak_bytes=0)
        for name in ('preflight', 'collection_and_finalization')}
    for path in cfg.run.rglob('resources-*.jsonl'):
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
    dbpath=cfg.run/'serving/server/requests.sqlite3'
    if dbpath.exists():
        import sqlite3
        db=sqlite3.connect(dbpath.as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            for request_id, raw in db.execute("SELECT request_id,response_body FROM requests WHERE state='completed'"):
                memory=json.loads(raw).get('metadata')
                if not isinstance(memory, dict):
                    continue
                result['allocator_peak_bytes']=max(result['allocator_peak_bytes'],*memory['gpu_peak_allocated_bytes'])
                result['reserved_peak_bytes']=max(result['reserved_peak_bytes'],*memory['gpu_reserved_bytes'])
                phase = result['phases']['preflight' if request_id.startswith(cfg.namespace + '-gate-') else 'collection_and_finalization']
                # CUDA peak is cumulative since the one load; NVML/RSS above are phase samples.
                phase['allocator_peak_bytes'] = max(phase['allocator_peak_bytes'], *memory['gpu_peak_allocated_bytes'])
                phase['reserved_peak_bytes'] = max(phase['reserved_peak_bytes'], *memory['gpu_reserved_bytes'])
        finally:db.close()
    result['final_disk_bytes']=disk_bytes(cfg)
    result['disk_limit_bytes'] = cfg.disk_limit_bytes
    if cfg.is_minicpm and (cfg.evidence / 'browser.json').is_file():
        browser = read(cfg.evidence / 'browser.json')
        result['browser_temporary_copy_bytes'] = browser['relocated_copy_bytes']
        result['browser_disk_peak_bytes'] = browser['disk_bytes_with_temporary_copy']
        result['observed_disk_max_bytes'] = max(result['observed_disk_max_bytes'],
                                               result['browser_disk_peak_bytes'])
    return result


def inference_accounting(config, collection):
    """Count physical starts separately from logical decisions and HTTP attempts."""
    cfg = experiment(config)
    collection = Path(collection)
    import sqlite3
    from .study import event_rows
    requests = ({e['request_id'] for e in event_rows(collection) if e['type'] == 'transport'}
                if (collection/'events.jsonl').is_file() else set())
    database_path = cfg.run/'serving/server/requests.sqlite3'
    result = dict(collection_inferences=0, preflight_inferences=0, total_server_inferences=0,
        requests_not_accepted=len(requests), duplicate_inferences=0,
        server_load_attempts=int((cfg.evidence / 'server-process.json').is_file()),
        preflight_received_usage=dict(input_tokens=0, output_tokens=0),
        preflight_inference_seconds=0, preflight_usage_unknown_requests=0,
        confirmed_server_loads=int((cfg.run/'serving/model-loaded.json').is_file()
                                   or (cfg.run/'serving/loaded.json').is_file()),
        preflight_http_attempts=0, preflight_http_responses=0, preflight_http_errors=0,
        preflight_http_no_response=0)
    for transport_path in (cfg.run / 'gates').glob('*-transport.json'):
        row = read(transport_path)
        if (not isinstance(row, dict) or row.get('type') != 'transport'
                or not str(row.get('request_id', '')).startswith(cfg.namespace + '-gate-')):
            continue
        result['preflight_http_attempts'] += 1
        status = row.get('status_code')
        result['preflight_http_responses'] += status is not None
        result['preflight_http_no_response'] += status is None
        result['preflight_http_errors'] += isinstance(status, int) and status >= 400
    if not database_path.exists():
        return result
    # The model process has closed its journal before postprocessing. Immutable
    # reads inspect the preserved database without creating WAL/SHM sidecars.
    db = sqlite3.connect(database_path.as_uri()+'?mode=ro&immutable=1', uri=True)
    try:
        starts = dict(db.execute("SELECT request_id,COUNT(*) FROM events WHERE kind='inference_started' GROUP BY request_id"))
        if any(n != 1 for n in starts.values()):
            raise ValueError('duplicate model inference')
        if any(k not in requests and not k.startswith(cfg.namespace + '-gate-') for k in starts):
            raise ValueError('unaccounted server inference')
        result.update(collection_inferences=sum(starts.get(k, 0) for k in requests),
                    preflight_inferences=sum(n for k,n in starts.items() if k.startswith(cfg.namespace + '-gate-')),
                    total_server_inferences=sum(starts.values()),
                    requests_not_accepted=sum(k not in starts for k in requests), duplicate_inferences=0)
        if result['preflight_inferences'] > 8:
            raise ValueError('GPU qualification exceeded eight inferences')
        answered = set()
        for request_id, raw in db.execute("SELECT request_id,response_body FROM requests WHERE state='completed'"):
            if not request_id.startswith(cfg.namespace + '-gate-'):
                continue
            body = json.loads(raw)
            if all(k in body.get('usage', {}) for k in ('input_tokens', 'output_tokens')):
                answered.add(request_id)
                for key in result['preflight_received_usage']:
                    result['preflight_received_usage'][key] += body['usage'][key]
            result['preflight_inference_seconds'] += body.get('metadata', {}).get('elapsed_seconds', 0)
        result['preflight_usage_unknown_requests'] = sum(
            k.startswith(cfg.namespace + '-gate-') and k not in answered for k in starts)
        return result
    finally:
        db.close()


def finalize(config, *, accounting=None):
    cfg = experiment(config)
    from . import study,viewer
    collection=cfg.run/'collection'
    if not (collection/'result.json').exists():
        return dict(passed=False,reason='collection_not_started')
    result=read(collection/'result.json');manifest=read(collection/'manifest.json')
    compared=study.comparison(manifest,result)
    cross=study.cross_comparison(cfg,manifest,result)
    write(cfg.evidence/'cross-comparison.json',cross)
    write(cfg.evidence/'comparison.json',compared)
    calls=accounting if accounting is not None else inference_accounting(cfg, collection)
    exported=viewer.export(collection,cfg.export,compared=compared)
    command_stage(cfg, [str(BROWSER_PYTHON),'-m','integration.jev_eval.viewer','verify-browser',
        '--output',str(cfg.export),'--receipt',str(cfg.evidence/'browser.json')],'browser')
    final=dict(passed=result.get('final_audit_passed') is True and exported['passed'] and read(cfg.evidence/'browser.json')['passed'],
        export=exported,browser=read(cfg.evidence/'browser.json'),comparison=compared,cross_comparison=cross,inference_accounting=calls)
    write(cfg.evidence/'finalization.json',final)
    return final


def report(config, completion):
    cfg = experiment(config)
    from . import study
    from statistics import median
    result = completion.get('result') or dict(planned=32, attempted=0, completed=0, failed=0,
        invalid=0, unattempted=32, completed_pairs=0, overall=dict(wins=0, draws=0, losses=0),
        decisions=0, requests=0, tokens=None, received_usage={}, usage_unknown_requests=0)
    final = completion.get('finalization') or {}
    compare = final.get('comparison', {})
    cross = final.get('cross_comparison', {})
    prior = completion.get('prior_execution')
    calls = completion.get('inference_accounting') or final.get('inference_accounting', {})
    outcome = result['overall']
    resource = completion['resources']
    latencies = sorted(result.get('latency_seconds', []))
    lengths = study.collection_metrics(result)
    text = f"""# {cfg.experiment} {cfg.model_id} {study.interpretation(cfg)}

- 종결: {'Completed' if completion['passed'] else 'Incomplete / Stopped'}
- 새 경기: 예정32·시도{result['attempted']}·유효{result['completed']}·실패{result['failed']}·무효{result['invalid']}·미실행{result['unattempted']}
- 성적: {outcome['wins']}승 {outcome['draws']}무 {outcome['losses']}패; 완료율{result['completed']/32:.2%}; 유효쌍{result['completed_pairs']}/16
- 행동 결정{result['decisions']}·실제 본수집 추론{calls.get('collection_inferences')}·HTTP POST시도{result['requests']}·재전송{result.get('retry_attempts')}
- 자동 선택{result.get('automatic_actions')}·실제 명령{result.get('sent_actions')}·중복 추론{calls.get('duplicate_inferences')}
- 본수집 토큰: {result['tokens']}; 확인된 usage {result['received_usage']}; 미확정 요청{result['usage_unknown_requests']}
- 입력 토큰 길이: {lengths['input_tokens']}; 입력 생성 시간(초): {lengths['input_generation_seconds']}
- 응답 지연 중앙값(초): {median(latencies) if latencies else None}; 실제 추론 지연 합{result.get('inference_latency_seconds')}; 결정 지연 합{result.get('decision_latency_seconds')}
- {cfg.baseline} 공통 유효쌍{compare.get('common_completed_pairs',0)}·기준 점수{compare.get('before_pair_score')}·새 점수{compare.get('after_pair_score')}·점수 차이{compare.get('mean_pair_score_delta')}
- 쌍별 변화: {compare.get('pair_changes')}; 완료 경기 턴수: {lengths['completed_game_turns']}
- 사전검증: 서버 적재 시도{calls.get('server_load_attempts')}·확인된 적재{calls.get('confirmed_server_loads')}·실제 추론{calls.get('preflight_inferences')}·HTTP POST시도{calls.get('preflight_http_attempts')}·확인된 usage{calls.get('preflight_received_usage')}·미확정 요청{calls.get('preflight_usage_unknown_requests')}·추론 지연{calls.get('preflight_inference_seconds')}초; 본수집 성적/비용에서 분리
- GPU 최대MiB: {resource['gpu_max_mib']}; allocator peak{resource['allocator_peak_bytes']}B·reserved peak{resource['reserved_peak_bytes']}B; host RSS{resource['host_rss_max_bytes']}B; 디스크 최대{resource['observed_disk_max_bytes']}B
- 자원 반환: {completion['closure']['passed']}; 오류: {completion['error']}; 정리 오류: {completion['cleanup_errors']}

결과는 **{study.interpretation(cfg)}**다. {study.reference_interpretation(cfg)}.
GPU 사전8요청은 관측한 길이에서의 실행 가능성 근거이며 모든 입력 길이 안정성 보장이 아니다.
실패를 패배로 바꾸지 않았고 기존 {cfg.baseline} 성적을 새 분모에 계승하지 않았다. 설명 정확성은 미평가다.

원자료: `{cfg.run}/collection`; 감사·사용량·비교·뷰어·자원·봉인 연결은 `evidence/completion.json`과 `evidence/finalization.json`을 따른다.
[뷰어]({cfg.export}/index.html).
"""
    if cfg.input_version == NO_DAMAGE_VERSION:
        costs = completion.get('cost_comparison', {})
        text += ("\n피해 예측 비활성화·스피드 비교 유지를 적용했다. 입력 길이와 경기 진행 변화가 포함되므로 "
                 "일반 성능 개선·동등성이나 정보 제거와 길이 변화의 독립 효과를 주장하지 않는다. "
                 "기준선/새 실행의 호출·토큰·입력 생성/추론/결정 지연·턴수·자원과 사전 비용은 "
                 "`evidence/cost-comparison.json`에 각 실제 분모로 구분했다.\n")
        before = costs.get('before', {})
        text += (f"\n기준선 비용: 입력토큰 {before.get('collection', {}).get('usage')}; "
                 f"입력 생성 {before.get('collection', {}).get('input_generation_seconds')}; "
                 f"추론 {before.get('collection', {}).get('inference_latency_seconds')}초; "
                 f"결정 {before.get('collection', {}).get('decision_latency_seconds')}초.\n")
    elif cfg.is_minicpm:
        text += ("\nEX-089와 입력 정보·프롬프트·후보/명령/순서를 유지했다. "
                 "모델 가중치·결정 헤드·보정값·토크나이저·모델 전용 포맷·GPU 배치가 함께 다르며 "
                 "공식 기본 서버를 그대로 재현한 결과가 아니다. "
                 "일반 성능 우위·동등성이나 모델 크기만의 효과를 주장하지 않는다. "
                 "기준선/새 실행의 실제 분모와 사전/본수집 비용은 `evidence/cost-comparison.json`에, "
                 "디스크 상한null과 실제 사용량은 자원 증거에 보존했다.\n")
    else:
        text += (f"\n{cfg.cohort.first} 대 {cfg.cohort.second}: 공통 유효쌍 "
                 f"{cross.get('common_completed_pairs')}·{cfg.cohort.second}−{cfg.cohort.first} 차이 "
                 f"{cross.get('mean_pair_score_delta')}; 산출 상태 {cross.get('available', False)}. "
                 "공식 모델 가중치·결정 head·보정값·장치 배치 차이가 함께 있으므로 "
                 "일반 성능 우위나 모델 크기만의 효과를 주장하지 않는다.\n")
    if prior is not None:
        old = prior['accounting']
        text += (f"\n이전 중단 평가(EX-086/087)는 별도 보존했다. 이전 추론은 사전{old['preflight_inferences']}·"
                 f"본수집{old['collection_inferences']}·합계{old['total_server_inferences']}회이며 "
                 f"이번 성적/추론 합계에 넣지 않았다. 원 실행 시계 {prior['execution_started']}–"
                 f"{prior['execution_ended']}와 사후 집계는 `{prior['accounting_source']}`에 연결된다.\n")
    (cfg.run/'report.md').write_text(text)


def finish_completion(config, completion):
    """Flush the terminal log before sealing a controller whose stdout is in RUN."""
    cfg = experiment(config)
    from . import study
    if cfg.input_version == NO_DAMAGE_VERSION or cfg.is_minicpm:
        baseline = study.sealed_document(EXPERIMENTS[cfg.baseline].run, 'evidence/completion.json')
        costs = dict(before_experiment=cfg.baseline, after_experiment=cfg.experiment,
            scope='각 실행의 실제 분모; 사전 비용과 본수집 비용 분리; 기준선 재계산 없음',
            before=dict(collection=study.collection_metrics(baseline.get('result') or {}),
                        inference_accounting=baseline['inference_accounting'],
                        resources=baseline['resources']),
            after=dict(collection=study.collection_metrics(completion.get('result') or {}),
                       inference_accounting=completion.get('inference_accounting'),
                       resources=completion['resources']))
        write(cfg.evidence / 'cost-comparison.json', costs)
        completion['cost_comparison'] = costs
    write(cfg.evidence/'completion.json', completion)
    report(cfg, completion)
    result = completion.get('result')
    print(json.dumps(dict(passed=completion['passed'], error=completion['error'],
        completed=result['completed'] if result else 0, report=str(cfg.run/'report.md')),
        ensure_ascii=False), flush=True)
    study.seal(cfg.run)


def check_disk(config):
    from .resource import disk_bytes, disk_roots
    cfg = experiment(config)
    total = disk_bytes(cfg)
    limit = cfg.disk_limit_bytes
    receipt = dict(bytes=total, limit_bytes=limit,
                   roots=[str(path) for path in disk_roots(cfg)])
    if limit is not None and total > limit:
        raise SharedFailure(f'combined initial disk budget exceeds {limit / 1024**3:g} GiB')
    return receipt


def prepare(config):
    """Regenerate v6 on the actor CPU, then tokenize in the preserved model environment."""
    from . import gates, study
    from .resource import ResourceMonitor
    cfg = experiment(config)
    reject_environment_overrides(cfg)
    if cfg.run.exists() or cfg.export.exists():
        raise FileExistsError('evaluation preparation cannot overwrite an existing output')
    disk = check_disk(cfg)
    cfg.evidence.mkdir(parents=True, exist_ok=False)
    started = time.time()
    write(cfg.run / 'preparation.json', dict(experiment_id=cfg.experiment, started=started,
        model=cfg.model_id, revision=cfg.revision, initial_disk=disk, gpu_loads=0, inferences=0))
    try:
        sources = study.source_identity()
        source_snapshot(cfg, sources)
        with ResourceMonitor(cfg.evidence, config=cfg):
            verify_cpu(cfg, sources)
            baseline_verification = None
            actor_tokenization_verification = None
            if cfg.input_version == NO_DAMAGE_VERSION:
                from .no_damage_verify import verify_baseline
                receipt = verify_baseline(cfg, sources)
                baseline_verification = dict(path='evidence/no-damage-baseline.json',
                    sha256=file_hash(cfg.evidence / 'no-damage-baseline.json'),
                    checked_inputs=receipt['checked_inputs'])
            regenerated = gates.regenerate_requests(cfg)
            command_stage(cfg, [str(PYTHON), '-m', 'integration.jev_eval.gates', 'prepare',
                '--experiment', cfg.experiment], 'lengths-prepare',
                env=dict(child_environment(), CUDA_VISIBLE_DEVICES=''))
            if cfg.is_minicpm:
                from integration.minicpm5_jev.verify import validate_receipt, verify_actor_tokenization
                receipt = validate_receipt(cfg, sources)
                baseline_verification = dict(path='evidence/minicpm-baseline.json',
                    sha256=file_hash(cfg.evidence / 'minicpm-baseline.json'),
                    checked_inputs=receipt['checked_inputs'])
                regenerated = dict(passed=True, deferred=False, requests=8,
                    gpu_inferences=0, baseline_recalculations=0,
                    prepared_by='minicpm_baseline_verifier')
                actor_receipt = verify_actor_tokenization(cfg, sources)
                actor_tokenization_verification = dict(path='evidence/minicpm-actor-tokenization.json',
                    sha256=file_hash(cfg.evidence / 'minicpm-actor-tokenization.json'),
                    checked_inputs=actor_receipt['checked_inputs'])
        if sources != study.source_identity():
            raise SharedFailure('source changed during preparation')
        for name in ('model-ready.json', 'lengths.json'):
            if read(cfg.evidence / name).get('passed') is not True:
                raise SharedFailure('preparation incomplete: ' + name)
        result = dict(passed=True, experiment_id=cfg.experiment, source=sources,
            evaluation_cohort=dict(first=cfg.cohort.first, second=cfg.cohort.second,
                                   predecessor=cfg.predecessor),
            prior_execution=study.prior_execution(cfg),
            generated=regenerated, lengths=read(cfg.evidence / 'lengths.json'),
            gpu_loads=0, inferences=0, started=started, ended=time.time(),
            combined_disk=check_disk(cfg))
        if baseline_verification is not None:
            result['baseline_verification'] = baseline_verification
        if actor_tokenization_verification is not None:
            result['actor_tokenization_verification'] = actor_tokenization_verification
        write(cfg.evidence / 'prepared.json', result)
        return result
    except BaseException as exc:
        write(cfg.evidence / 'preparation-failure.json', dict(at=time.time(), error=error_record(exc)))
        raise


def verify_preparation(config):
    from . import study
    cfg = experiment(config)
    prepared = read(cfg.evidence / 'prepared.json')
    if (prepared.get('passed') is not True or prepared.get('experiment_id') != cfg.experiment
            or prepared.get('source') != study.source_identity()):
        raise SharedFailure('preparation source/experiment identity differs')
    for name in ('model-ready.json', 'lengths.json', 'cpu.json'):
        if read(cfg.evidence / name).get('passed') is not True:
            raise SharedFailure('preparation incomplete: ' + name)
    if read(cfg.evidence / 'cpu.json').get('source') != prepared['source']:
        raise SharedFailure('CPU validation source identity differs')
    lengths = read(cfg.evidence / 'lengths.json')
    if file_hash(cfg.run / 'gates/requests.json') != lengths['requests_sha256']:
        raise SharedFailure('prepared qualification requests changed')
    if cfg.input_version == NO_DAMAGE_VERSION:
        from .no_damage_verify import validate_receipt
        validate_receipt(cfg, prepared['source'])
        link = prepared.get('baseline_verification', {})
        if (link.get('path') != 'evidence/no-damage-baseline.json'
                or link.get('checked_inputs') != 1139
                or link.get('sha256') != file_hash(cfg.evidence / 'no-damage-baseline.json')):
            raise SharedFailure('prepared no-damage baseline verification differs')
    elif cfg.is_minicpm:
        from integration.minicpm5_jev.verify import validate_actor_receipt
        validate_actor_receipt(cfg, prepared['source'])
        link = prepared.get('baseline_verification', {})
        actor_link = prepared.get('actor_tokenization_verification', {})
        if (link.get('path') != 'evidence/minicpm-baseline.json'
                or link.get('checked_inputs') != 1139
                or link.get('sha256') != file_hash(cfg.evidence / 'minicpm-baseline.json')
                or lengths.get('format') != cfg.format_version
                or lengths.get('tokenizer_sha256') != file_hash(cfg.tokenizer_dir / 'tokenizer.json')):
            raise SharedFailure('prepared MiniCPM baseline/tokenizer verification differs')
        if (actor_link.get('path') != 'evidence/minicpm-actor-tokenization.json'
                or actor_link.get('checked_inputs') != 1139
                or actor_link.get('sha256') != file_hash(cfg.evidence / 'minicpm-actor-tokenization.json')):
            raise SharedFailure('prepared MiniCPM actor tokenization verification differs')
    return prepared


def require_previous_experiment(config):
    cfg = experiment(config)
    if cfg.predecessor is None:
        return
    first = EXPERIMENTS[cfg.predecessor]
    path = first.evidence / 'completion.json'
    if not path.is_file():
        raise SharedFailure(f'{cfg.experiment} requires the completed {cfg.predecessor} cleanup before GPU admission')
    from .study import sealed_document
    completion = sealed_document(first.run, 'evidence/completion.json')
    if completion.get('experiment_id') != cfg.predecessor or not may_continue_other_model(completion):
        raise SharedFailure(f'{cfg.predecessor} shared defect or incomplete cleanup prohibits {cfg.experiment}')


def server_failure(config):
    cfg = experiment(config)
    stopped = [read(path) for path in (cfg.run / 'serving').glob('resource-stop-*.json')]
    scope = resource_scope(stopped)
    if scope is not None:
        return dict(type='ResourceFailure', detail='model resource monitor stopped the process', scope=scope)
    path = cfg.run / 'serving/process-failure.json'
    return read(path) if path.is_file() else error_record(ModelFailure('model server exited during load'))


def shared_integrity(config, result, error):
    """Evidence needed before an isolated model failure may release the next experiment."""
    cfg = experiment(config)
    try:
        verify_preparation(cfg)
        if result is not None and result.get('final_audit_passed') is not True:
            return False
        if error is not None and error.get('scope') != 'model':
            return False
        stops = [read(path) for path in cfg.run.rglob('resource-stop-*.json')]
        return resource_scope(stops) != 'shared'
    except Exception:
        return False


def execute(config):
    from . import battle, gates
    from .client import LocalClient
    from .resource import ResourceMonitor, wait_owned_gpu_release
    cfg = experiment(config)
    reject_environment_overrides(cfg)
    if ((cfg.run / 'execution.json').exists() or (cfg.run / 'collection').exists()
            or (cfg.evidence / 'completion.json').exists() or cfg.export.exists()):
        raise FileExistsError('evaluation execution cannot overwrite or resume')
    prepared = verify_preparation(cfg)
    require_previous_experiment(cfg)
    check_disk(cfg)

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'{cfg.experiment} received signal {signum}')

    signal.signal(signal.SIGTERM, interrupted)
    model_process = log = client = None
    error, cleanup, result, final, calls = None, [], None, None, None
    started = time.time()
    write(cfg.run / 'execution.json', dict(experiment_id=cfg.experiment, started=started,
        pid=os.getpid(), maximum_gpu_preflight_inferences=8, maximum_server_loads=1))
    try:
        if not (closure(cfg) if cfg.is_minicpm else closure())['passed']:
            raise SharedFailure('required GPU/lock/ports are not idle')
        (cfg.run / 'serving').mkdir()
        log = (cfg.run / 'serving/server.log').open('x')
        # The controller monitor includes its model child and the battle actors,
        # enforcing one combined host-RSS budget across the entire owned tree.
        with ResourceMonitor(cfg.evidence, config=cfg):
            model_process = subprocess.Popen([str(PYTHON), '-m', 'integration.jev_eval.server',
                '--experiment', cfg.experiment], cwd=ROOT, env=child_environment(),
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            write(cfg.evidence / 'server-process.json', dict(pid=model_process.pid, at=time.time()))
            import httpx
            while True:
                if model_process.poll() is not None:
                    raise RecordedFailure(server_failure(cfg))
                try:
                    response = httpx.get(cfg.endpoint + '/health', timeout=2, trust_env=False)
                    if response.status_code == 200:
                        break
                except httpx.RequestError:
                    pass
                time.sleep(0.5)
            client = LocalClient(cfg)
            receipt = gates.qualify(client, prepared['source'], config=cfg)
            original = Path.cwd()
            collection_error = None
            try:
                os.chdir(ROOT / 'pokechamp')
                result = asyncio.run(battle.run(cfg.run / 'collection', config=cfg,
                    expected_identity=receipt['serving_identity'], gate_receipt=receipt,
                    endpoint=cfg.endpoint))
            except BaseException as exc:
                collection_error = error_record(exc)
                raise
            finally:
                os.chdir(original)
                if (cfg.run / 'collection').is_dir():
                    write(cfg.evidence / 'collection-ended.json', dict(
                        experiment_id=cfg.experiment, stage='collection_ended', at=time.time(),
                        returned=result is not None,
                        result_available=(cfg.run / 'collection/result.json').is_file(),
                        passed=result.get('passed') is True if result is not None else False,
                        error=result.get('error') if result is not None else collection_error))
            if result.get('error'):
                error = dict(result['error'])
    except BaseException as exc:
        error = error_record(exc)
        write(cfg.evidence / 'failure.json', dict(at=time.time(), error=error))
    finally:
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                cleanup.append(str(exc))
        if model_process is not None:
            try:
                stop_owned_process(model_process)
                if (cfg.run / 'serving' / f'gpu-acquire-{model_process.pid}.json').exists():
                    wait_owned_gpu_release(cfg.run / 'serving', model_process.pid, config=cfg)
            except Exception as exc:
                cleanup.append(str(exc))
        if log is not None:
            log.close()
    if result is None and (cfg.run / 'collection/result.json').is_file():
        result = read(cfg.run / 'collection/result.json')
    stops = [read(path) for path in cfg.run.rglob('resource-stop-*.json')]
    stop_scope = resource_scope(stops)
    if stop_scope is not None:
        error = dict(type='ResourceFailure', detail='owned resource monitor stopped execution',
                     scope=stop_scope, original_error=error, resource_stops=stops)
    try:
        calls = inference_accounting(cfg, cfg.run / 'collection')
        write(cfg.evidence / 'inference-accounting.json', calls)
        with ResourceMonitor(cfg.evidence, config=cfg):
            final = finalize(cfg, accounting=calls)
    except BaseException as exc:
        final_error = error_record(exc)
        # Any final audit/export/integrity defect blocks both dependents even
        # when an earlier, model-local serving failure initiated shutdown.
        error = dict(final_error, previous_error=error)
        write(cfg.evidence / 'finalization-failure.json', final_error)
    try:
        closed = closure(cfg) if cfg.is_minicpm else closure()
    except Exception as exc:
        closed = dict(passed=False, error=error_record(exc))
        cleanup.append(str(exc))
    resources = resource_summary(cfg)
    intact = shared_integrity(cfg, result, error)
    completion = dict(experiment_id=cfg.experiment,
        prior_execution=prepared.get('prior_execution'),
        passed=bool(result and result['passed'] and final and final['passed']
                    and closed['passed'] and intact and not error and not cleanup),
        result=result, finalization=final, inference_accounting=calls,
        closure=closed, resources=resources, error=error, shared_integrity_passed=intact,
        cleanup_errors=cleanup, started=started, ended=time.time(), elapsed_seconds=time.time()-started)
    finish_completion(cfg, completion)
    return completion


def status(config):
    cfg = experiment(config)
    for path in (cfg.evidence / 'completion.json', cfg.run / 'collection/progress.json',
                 cfg.evidence / 'prepared.json', cfg.evidence / 'preparation-failure.json'):
        if path.is_file():
            return read(path)
    return dict(experiment_id=cfg.experiment, status='not_prepared')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('download', 'prepare', 'execute', 'status', 'reexport'))
    parser.add_argument('--experiment', required=True, choices=EXPERIMENTS)
    args = parser.parse_args(argv)
    cfg = experiment(args.experiment)
    if args.command == 'download':
        if not cfg.is_minicpm:
            raise ValueError('jev-eval download is registered only for EX-091')
        reject_environment_overrides(cfg)
        completed = subprocess.run([str(PYTHON), '-m', 'integration.minicpm5_jev.download'],
            cwd=ROOT, env=child_environment(), check=False)
        return completed.returncode
    if args.command == 'reexport':
        from .reexport import reexport
        value = reexport(cfg)
    else:
        value = {'prepare': prepare, 'execute': execute, 'status': status}[args.command](cfg)
    if args.command != 'execute':
        print(json.dumps(value, ensure_ascii=False))
    return 0 if args.command != 'execute' or value['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

