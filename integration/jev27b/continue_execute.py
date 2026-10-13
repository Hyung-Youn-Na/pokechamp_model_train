"""One-shot EX-083 controller: validate, qualify four GPUs, collect nine, close."""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import time

from .config import BASELINE, ENDPOINT, EVIDENCE, MODEL_DIR, PYTHON, ROOT
from .execute import child_environment, install_signal_handlers, stop_owned_process
from .storage import file_hash, read, write

EXPORT = ROOT / 'exports/battle_viewers/ex083'
ACTOR_PYTHON = ROOT / 'pokechamp/.venv/bin/python'
BROWSER_PYTHON = Path('/tmp/ep037/tools/bin/python')


def run_stage(command, name, evidence, *, gpu_directory=None, extra_env=None):
    """Always reap the owned group, including failures and controller cancellation."""
    from .resource import wait_owned_gpu_release
    process = None
    error = None
    started = time.time()
    log = Path(evidence) / (name + '.log')
    print(json.dumps(dict(stage=name, state='started', at=started)), flush=True)
    try:
        with log.open('x') as output:
            environment = child_environment()
            environment.update(extra_env or {})
            process = subprocess.Popen(command, cwd=ROOT, env=environment,
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            write(Path(evidence) / (name + '-process.json'),
                  dict(pid=process.pid, at=started, command=[str(value) for value in command]))
            process.wait()
    except BaseException as exc:
        error = exc
    finally:
        if process is not None:
            stop_owned_process(process)
            write(Path(evidence) / (name + '-exit.json'),
                  dict(pid=process.pid, exit=process.returncode, at=time.time(), seconds=time.time()-started))
            if gpu_directory is not None and (Path(gpu_directory) / f'gpu-acquire-{process.pid}.json').exists():
                wait_owned_gpu_release(gpu_directory, process.pid, profile='ex083')
    if error is not None:
        raise error
    if process is None or process.returncode:
        raise RuntimeError(f'{name} failed (exit {None if process is None else process.returncode}); see {log}')
    print(json.dumps(dict(stage=name, state='passed', seconds=time.time()-started)), flush=True)
    return process.pid


def assert_free_port(port):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))


def resource_closure():
    from .resource import gpu_compute_processes, gpu_facts
    facts = gpu_facts()
    locks = {}
    for index in range(4):
        path = ROOT / f'.pokechamp-data/locks/gpu{index}.lock'
        with path.open('a+') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locks[index] = True
                fcntl.flock(handle, fcntl.LOCK_UN)
            except BlockingIOError:
                locks[index] = False
    ports = {}
    for port in (18782, 8109):
        try:
            assert_free_port(port)
            ports[port] = True
        except OSError:
            ports[port] = False
    processes = gpu_compute_processes()
    selected = [row for row in processes if row['uuid'] in {facts[i]['uuid'] for i in range(4)}]
    passed = (all(locks.values()) and all(ports.values()) and not selected
              and all(facts[i]['memory_used_mib'] <= 256 for i in range(4)))
    return dict(passed=passed, at=time.time(), gpus=facts, gpu_locks_released=locks,
                owned_ports_released=ports, remaining_selected_gpu_processes=selected)


def _source_receipt(evidence, sources):
    branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()
    if branch != 'research/model-training':
        raise ValueError('EX-083 must run in the registered model-training checkout')
    write(Path(evidence) / 'source.json', dict(branch=branch,
          commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          working_changes=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
          source=sources, checkout=str(ROOT), actor_python=str(ACTOR_PYTHON), model_python=str(PYTHON)))
    protocol = Path(evidence).parent / 'protocol'
    protocol.mkdir()
    for name in ('CHARTER.md', 'RESEARCH_DESIGN.md', 'CONTRACTS.md',
                 'decisions/D-132-jev27b-four-gpu-continuation.md',
                 'exec-plans/active/EP-137-jev27b-four-gpu-continuation.md',
                 'experiments/EX-083-jev27b-four-gpu-continuation.md'):
        target = protocol / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'project_context' / name, target)


def completion_passed(result, final, browser_result, closure, error, cleanup_errors):
    """Collection success alone never overrides a failed final audit/export/browser."""
    return bool(result and result.get('passed') is True and final and final.get('passed') is True
                and final.get('export', {}).get('passed') is True
                and browser_result and browser_result.get('passed') is True
                and closure.get('passed') is True and not error and not cleanup_errors)


def final_report(directory, completion):
    from .resource import disk_bytes
    directory = Path(directory)
    evidence = directory / 'evidence'
    resources = dict(samples=0, gpu_max_mib={i: 0 for i in range(4)},
                     process_tree_rss_max_bytes=0, observed_disk_max_bytes=0, errors=[], historical_errors=[])
    for path in sorted(directory.rglob('resources-*.jsonl')):
        for line in path.open():
            sample = json.loads(line)
            resources['samples'] += 1
            resources['process_tree_rss_max_bytes'] = max(resources['process_tree_rss_max_bytes'], sample['rss_bytes'])
            resources['observed_disk_max_bytes'] = max(resources['observed_disk_max_bytes'], sample['disk_bytes'])
            for key, gpu in sample['gpus'].items():
                index = int(key)
                resources['gpu_max_mib'][index] = max(resources['gpu_max_mib'][index], gpu['memory_used_mib'])
            if sample.get('errors'):
                relative = path.relative_to(directory)
                key = 'historical_errors' if relative.parts[0] in ('preflight-attempt1', 'recovery-evidence') else 'errors'
                resources[key].append(dict(path=str(relative), at=sample['at'], errors=sample['errors']))
    resources['final_disk_bytes'] = disk_bytes(profile='ex083', budget_root=directory)
    resources['scope'] = 'EX-083 controller, reloads, continuous validation/collection, finalization; preserved assets included in disk'
    write(evidence / 'resource-summary.json', resources)
    from .config import DISK_BYTES
    if resources['errors'] or resources['final_disk_bytes'] > DISK_BYTES:
        completion.update(status='Blocked', experiment_target_achieved=False,
                          error=completion['error'] or dict(phase='closure', type='ResourceLimit', detail='final resource gate failed'))
    combined_path = evidence / 'combined-result.json'
    combined = read(combined_path) if combined_path.exists() else None
    compared_path = evidence / 'comparison.json'
    compared = read(compared_path) if compared_path.exists() else {}
    reload_path, replay_path, memory_path = (directory / 'gates' / name for name in
        ('reload-comparison.json', 'parent-replay/result.json', 'memory/result.json'))
    lines = ['# EX-083 — JEV-27B 4GPU 계승 평가', '',
             f'- 상태: **{completion["status"]}**; 목표 달성: {completion["experiment_target_achieved"]}.',
             '- 부모 EX-082 원자료·봉인·원실패·Blocked를 보존했다.',
             '- 조건: protocol/experiments/EX-083-jev27b-four-gpu-continuation.md.',
             '- 진입/종결: evidence/entry-gates.json, evidence/completion.json.', '']
    if combined:
        confirmed = combined.get('final_audit_passed') is True
        lines += [combined['interpretation'] + '.', '']
        if not confirmed:
            lines += ['**최종 기술 감사 미통과: 유효성·성적 확정을 보류한다. 아래 수치는 경기별 원기록이며 확정 평가 성적이 아니다.**', '']
        lines += [f'| 고유 예정 | 고유 시도 | {"유효" if confirmed else "경기별 완료 기록"} | 실패 | 무효 | 미실행 | 완료쌍 기록 | 전체 배틀 시도 |',
            '|---:|---:|---:|---:|---:|---:|---:|---:|',
            f'| {combined["planned"]} | {combined["attempted"]} | {combined["completed"]} | '
            f'{combined["failed"]} | {combined["invalid"]} | {combined["unattempted"]} | '
            f'{combined["completed_pairs"]}/16 | {combined["total_battle_attempts"]}/33 |', '',
            f'{"유효 성적" if confirmed else "경기별 승패 원기록"}은 {combined["actual_wins"]}승 {combined["actual_draws"]}무 '
            f'{combined["actual_losses"]}패다. 원 실패1회는 전체 시도/실패 이력에 포함하며 패배로 바꾸지 않는다.',
            f'원 실패 경기의 정상 부분응답 {combined["original_failed_partial_responses"]}건과 미응답1건을 보존한다. '
            f'확인된 누적 usage는 {combined["received_usage"]}, 전체 usage는 {combined["tokens"]}이다.', '',
            '## 구간별 호출·지연', '',
            '| 구간 | 유효 경기 | 논리 요청 | 정상 응답 | 미응답 | 수집 시간(초) | 응답 지연 중앙(초) |',
            '|---|---:|---:|---:|---:|---:|---:|']
        import statistics
        for name, segment in combined['segments'].items():
            latencies = segment.get('latency_seconds') or []
            median = f'{statistics.median(latencies):.3f}' if latencies else '미측정'
            lines.append(f'| {name} | {segment["completed"]} | {segment["logical_requests"]} | '
                f'{segment["received_responses"]} | {segment["unanswered_requests"]} | '
                f'{segment["elapsed_collection_seconds"]:.3f} | {median} |')
        if confirmed and compared.get('mean_pair_score_delta') is not None:
            lines += ['', f'EX-058과 공통 유효 {compared["common_completed_pairs"]}쌍을 동일 가중한 점수차는 '
                f'{compared["mean_pair_score_delta"] * 100:+.6f}%p다. 상세는 evidence/comparison.json이다.']
        lines += ['', '최종 전수 감사는 evidence/continuation-audit.json, 오프라인 검사는 evidence/viewer-browser.json을 참조한다.',
                  f'뷰어: {EXPORT / "index.html"}. 부모 원실패 이력은 뷰어 안 상대링크로 연결했다.']
    elif not completion['new_battles_started']:
        lines += ['본 수집0. 부모 정상23·원실패1·미실행8이며 지정 잔여9경기는 시작하지 않았다.',
                  '수치 계승 평가 자체의 진입이 성립하지 않았으므로 새 비교 성적을 산출하지 않는다.']
    else:
        lines += ['본 수집에 진입했으나 최종 집계·감사를 완료하지 못했다. 유효성·성적·확정 분모를 보류한다.',
                  'collection/의 경기별 outcome·events·result 기록을 보존했으며 미기록 경기수를0으로 추정하지 않는다.']
    lines += ['', '## 진입·자원·중단', '']
    if (evidence / 'preflight-recovery.json').exists():
        lines += ['모델 적재 전 UUID 표현/PID namespace 대조의 구현 결함을 교정했다. 최초 실패의 source·시계·CPU검사·',
                  '자원/종료 증거는 preflight-attempt1에, 별도 진단은 recovery-evidence에 보존했다.',
                  '당시 모델 적재·추론·신규 경기0이며 수치·메모리 기준 변경 없이 새 독립 검증을 수행했다.', '']
    for label, path in (('독립 재로딩', reload_path), ('원591응답 재생', replay_path), ('연속 메모리', memory_path)):
        if path.exists():
            record = read(path)
            lines.append(f'- {label}: passed={record["passed"]}; '
                         f'최대 확률차이={record.get("max_probability_difference", "해당 없음")}.')
        else:
            lines.append(f'- {label}: 완료 receipt 없음.')
    lines += [f'- 4GPU 전체 사용량 관측 최대(MiB): {resources["gpu_max_mib"]}.',
              f'- 소유 프로세스 트리 RSS 관측 최대: {resources["process_tree_rss_max_bytes"] / 1024**3:.6f}GiB.',
              f'- 보존 모델/환경/원자료와 새 출력·뷰어 합산: {resources["final_disk_bytes"] / 1024**3:.6f}GiB.',
              '- 2GPU 구간 자원은 부모 evidence/ep134/resource-summary.json·final-metrics.json에서 별도 참조한다.',
              f'- 자원 반환: {completion["cleanup_passed"]}; 오류: {completion["error"]}.', '',
              '단일4GPU32경기 실험이나 추가 학습 효과로 해석하지 않는다. 고정 대진의 소규모 탐색 비교이며',
              '일반 성능 우위·입력 단독 효과·L1–L5 효능을 주장하지 않는다. 실패/미실행은 실제 분모로 남긴다.', '']
    (directory / 'report.md').write_text('\n'.join(lines))
    return resources


def update_viewer_catalog(combined):
    catalog = ROOT / 'exports/battle_viewers/index.html'
    original = catalog.read_text()
    if 'href="ex083/index.html"' in original:
        raise ValueError('EX-083 catalog entry already exists')
    if combined.get('final_audit_passed') is True:
        summary = (f'유효{combined["completed"]}/32 · 완료{combined["completed_pairs"]}/16쌍 · '
                   f'{combined["actual_wins"]}승{combined["actual_draws"]}무{combined["actual_losses"]}패')
    else:
        summary = '최종 기술 감사 실패·유효성/성적 확정 보류'
    entry = ('<li><a href="ex083/index.html">EX-083 — JEV-27B 2GPU/4GPU 계승 평가</a> · '
             f'{summary} · 전체{combined["total_battle_attempts"]}시도(원실패 포함)</li>')
    if '<ul>' not in original:
        raise ValueError('viewer catalog structure changed')
    catalog.write_text(original.replace('<ul>', '<ul>' + entry, 1))


def execute(parent, directory, *, recover_uuid_preflight=False, uuid_diagnostic=None):
    from . import continuation, continuation_gates as gates, study
    from .client import LocalClient
    from .resource import ResourceMonitor, disk_bytes, wait_owned_gpu_release

    parent, directory = Path(parent).resolve(), Path(directory).resolve()
    if directory == parent or directory.is_relative_to(parent) or parent.is_relative_to(directory):
        raise ValueError('parent and new output must be disjoint')
    if EXPORT.exists():
        raise FileExistsError('EX-083 viewer already exists; refuse an additional execution')
    recovery = None
    if recover_uuid_preflight:
        from .preflight_recovery import prepare_uuid_recovery
        recovery = prepare_uuid_recovery(directory, parent, uuid_diagnostic=uuid_diagnostic)
    else:
        if uuid_diagnostic is not None:
            raise ValueError('UUID diagnostic applies only to the single qualified pre-load repair')
        if directory.exists():
            raise FileExistsError('EX-083 cannot resume or overwrite an existing execution directory')
        directory.mkdir(parents=True, exist_ok=False)
    evidence = directory / 'evidence'
    evidence.mkdir()
    if recovery is not None:
        write(evidence / 'preflight-recovery.json', recovery)
        diagnostics = directory / 'recovery-evidence'
        diagnostics.mkdir()
        shutil.copytree(uuid_diagnostic, diagnostics / 'uuid-diagnostic-passed')
    stages = directory / 'gates'
    stages.mkdir()
    server = server_log = None
    server_dir = directory / 'serving'
    phase = 'parent-validation'
    error = None
    cleanup_errors = []
    result = final = browser_result = None
    parent_info = None
    started = time.time()
    sources = study.source_identity()
    write(evidence / 'execution-start.json', dict(at=started, parent=str(parent), directory=str(directory),
          first_execution_at=read(directory / 'preflight-attempt1/evidence/execution-start.json')['at'] if recovery else started,
          experiment_id='EX-083', source=sources, time_limits=None, profile='ex083', controller_pid=os.getpid()))
    try:
        _source_receipt(evidence, sources)
        study.snapshot_sources(directory, sources)
        parent_info = continuation.validate_parent(parent)
        write(evidence / 'parent-validation.json', parent_info)
        write(evidence / 'continuation-plan.json', dict(planned_unique_games=32, maximum_battle_attempts=33,
              slots=continuation.attempt_plan(parent_info)))
        write(evidence / 'preserved-preparation.json', gates.preserved_preparation())
        baseline = study.load_baseline(full_seal=True)
        write(evidence / 'clock-link.json', dict(parent_execution_start=read(EVIDENCE / 'execution-start.json'),
              parent_first_request_at=read(parent / 'result.json')['first_request_at'], current_execution_at=started,
              reset_cumulative_resource_limits=False, elapsed_limits=None))
        with ResourceMonitor(evidence, profile='ex083', budget_root=directory):
            try:
                phase = 'cpu'
                cpu_started = time.time()
                run_stage([str(ACTOR_PYTHON), '-B', '-m', 'pytest', '-q',
                           str(ROOT / 'integration/jev27b/tests')], 'cpu', evidence)
                if study.source_identity() != sources:
                    raise ValueError('source changed during CPU verification')
                write(evidence / 'cpu.json', dict(passed=True, source=sources, started_at=cpu_started,
                      ended_at=time.time(), test_log_sha256=file_hash(evidence / 'cpu.log')))
                for name in ('reload-a', 'reload-b'):
                    phase = name
                    run_stage([str(PYTHON), '-B', '-m', 'integration.jev27b.preflight', 'infer',
                               str(stages / name), '--profile', 'ex083', '--evidence', str(EVIDENCE),
                               '--budget-root', str(directory)], name, evidence, gpu_directory=stages / name)
                phase = 'reload-comparison'
                reloaded = gates.compare_reloads(stages)
                identity = reloaded['serving_identity']
                assert_free_port(18782)
                assert_free_port(8109)
                phase = 'serving-load'
                server_dir.mkdir(exist_ok=False)
                server_log = (evidence / 'serving.log').open('x')
                server = subprocess.Popen([str(PYTHON), '-B', '-m', 'integration.jev27b.server',
                    '--model-dir', str(MODEL_DIR), '--run-dir', str(server_dir),
                    '--profile', 'ex083', '--budget-root', str(directory)],
                    cwd=ROOT, env=child_environment(), stdin=subprocess.DEVNULL,
                    stdout=server_log, stderr=subprocess.STDOUT, start_new_session=True)
                write(evidence / 'server-process.json', dict(pid=server.pid, started_at=time.time()))
                while True:
                    if server.poll() is not None:
                        raise RuntimeError('owned EX-083 server exited before becoming ready')
                    try:
                        with socket.create_connection(('127.0.0.1', 18782), timeout=1):
                            break
                    except OSError:
                        time.sleep(1)
                journal = server_dir / 'server/requests.sqlite3'
                with LocalClient(ENDPOINT, expected_identity=identity) as client:
                    health = client.health()
                    if health['server_pid'] != server.pid:
                        raise ValueError('service is not the owned EX-083 process')
                    write(evidence / 'serving-health.json', health)
                    acquired = read(server_dir / f'gpu-acquire-{server.pid}.json')
                    expected_gpus = {int(key): value for key, value in acquired['gpus'].items()}
                    phase = 'parent-replay'
                    replay, stopped, shortest = gates.replay_parent(client, parent, stages / 'parent-replay', journal)
                    phase = 'continuous-memory'
                    memory = gates.memory_gate(client, stopped, shortest, stages / 'memory', journal,
                                               server_pid=server.pid, expected_gpus=expected_gpus)
                    phase = 'ordinary-preflight'
                    gates.ordinary_gate(client, stages, journal)
                    health = client.health()
                    if health['server_pid'] != server.pid or health['requests'] != {'completed': 597}:
                        raise ValueError('continuous serving process or validation request denominator changed')
                    write(evidence / 'post-gates-health.json', health)
                if study.source_identity() != sources:
                    raise ValueError('source changed during GPU gates')
                continuation.validate_parent(parent)
                gate_receipt = dict(passed=True, cpu_passed=True, length_passed=True,
                    reload_passed=True, replay_passed=replay['passed'], memory_passed=memory['passed'],
                    preflight_passed=True, serving_identity=identity, source=sources,
                    input_data_identity=baseline['input_data_identity'],
                    baseline_manifest_sha256=file_hash(BASELINE / 'manifest.json'),
                    parent_seal_sha256=file_hash(parent / 'checksums.sha256'), server_journal=str(journal),
                    continuous_server_pid=server.pid,
                    evidence={str(path.relative_to(directory)): file_hash(path) for path in (
                        evidence / 'cpu.json', evidence / 'parent-validation.json',
                        evidence / 'preserved-preparation.json', stages / 'reload-comparison.json',
                        stages / 'parent-replay/result.json', stages / 'memory/result.json',
                        stages / 'ordinary-preflight.json', evidence / 'post-gates-health.json')})
                write(evidence / 'entry-gates.json', gate_receipt)
                print(json.dumps(dict(stage='entry-gates', state='passed', new_battles=0,
                                      serving_pid=server.pid, validation_requests=597)), flush=True)
                phase = 'collection'
                previous = Path.cwd()
                try:
                    os.chdir(ROOT / 'pokechamp')
                    result = asyncio.run(continuation.run(directory / 'collection', parent=parent,
                        expected_identity=identity, gate_receipt=gate_receipt, endpoint=ENDPOINT))
                finally:
                    os.chdir(previous)
            finally:
                if server is not None:
                    try:
                        stop_owned_process(server)
                        if (server_dir / f'gpu-acquire-{server.pid}.json').exists():
                            wait_owned_gpu_release(server_dir, server.pid, profile='ex083')
                    except BaseException as exc:
                        cleanup_errors.append(dict(type=type(exc).__name__, detail=str(exc)))
                if server_log is not None:
                    server_log.close()
    except BaseException as exc:
        error = dict(at=time.time(), phase=phase, type=type(exc).__name__, detail=str(exc),
                     battle_collection_started=(directory / 'collection').exists())
        write(evidence / 'execution-failure.json', error)
    finally:
        try:
            closure = resource_closure()
        except BaseException as exc:
            closure = dict(passed=False, error=dict(type=type(exc).__name__, detail=str(exc)))
        write(evidence / 'execution-cleanup.json', dict(closure,
              server_pid=None if server is None else server.pid,
              server_exit=None if server is None else server.returncode, errors=cleanup_errors,
              additional_disk_bytes=disk_bytes(profile='ex083', budget_root=directory)))
    # Resource release precedes CPU final auditing/portable-browser verification.
    try:
        with ResourceMonitor(evidence / 'final-resources', profile='ex083', budget_root=directory):
            if (directory / 'collection/result.json').exists():
                final = continuation.finalize(directory / 'collection', parent=parent,
                                              output=EXPORT, evidence=evidence, browser=False)
                write(evidence / 'finalization.json', final)
                browser_temp = directory / 'browser-temp'
                browser_temp.mkdir()
                run_stage([str(BROWSER_PYTHON), '-B', '-m', 'integration.jev27b.continuation',
                           'verify-browser', '--output', str(EXPORT), '--evidence', str(evidence)],
                          'viewer-browser', evidence, extra_env={'TMPDIR': str(browser_temp)})
                browser_result = read(evidence / 'viewer-browser.json')
                if final.get('passed') is not True:
                    error = error or dict(phase='finalization', type='FinalCriteriaNotMet',
                                         detail=final.get('result', {}).get('error'))
                if final.get('export', {}).get('passed') is True and browser_result.get('passed') is True:
                    update_viewer_catalog(final['result'])
            if parent_info is not None:
                continuation.validate_parent(parent)
                if file_hash(EVIDENCE / 'checksums.sha256') != gates.PARENT_EVIDENCE_SEAL:
                    raise ValueError('parent evidence seal changed during continuation')
                study.verify_seal(EVIDENCE)
    except BaseException as exc:
        final_error = dict(at=time.time(), type=type(exc).__name__, detail=str(exc))
        write(evidence / 'finalization-failure.json', final_error)
        error = error or dict(phase='finalization', **final_error)
    achieved = completion_passed(result, final, browser_result, closure, error, cleanup_errors)
    completion = dict(experiment_id='EX-083', at=time.time(), execution_started_at=started,
        status='Completed' if achieved else 'Blocked', experiment_target_achieved=achieved,
        error=error, cleanup_passed=closure.get('passed') and not cleanup_errors,
        new_battles_started=(directory / 'collection').exists(),
        parent=str(parent), parent_original_status='Blocked', parent_modified=False,
        serving_pid=None if server is None else server.pid,
        viewer=str(EXPORT / 'index.html') if EXPORT.exists() else None)
    final_report(directory, completion)
    write(evidence / 'completion.json', completion)
    study.seal(directory)
    study.verify_seal(directory)
    print(json.dumps(completion, ensure_ascii=False), flush=True)
    return completion


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', required=True, type=Path)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--recover-uuid-preflight', action='store_true',
                        help='repair only the pinned model-unloaded UUID preflight failure; never resume collection')
    parser.add_argument('--uuid-diagnostic', type=Path)
    args = parser.parse_args(argv)
    install_signal_handlers()
    result = execute(args.parent, args.directory, recover_uuid_preflight=args.recover_uuid_preflight,
                     uuid_diagnostic=args.uuid_diagnostic)
    if not result['experiment_target_achieved']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
