"""EX-070: one prompt-only diagnostic, including an owned GPU3 server lifecycle."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from . import kev_control as control, kev_main as main_run, kev_value as value
from .branch_rollouts.common import file_hash, read, write

ROOT = control.ROOT
BASELINE = ROOT / '.pokechamp-data/kev/ex069'
OUTPUT = ROOT / '.pokechamp-data/kev/ex070'
EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep113'
ADMISSION = ROOT / '.pokechamp-data/kev/ex070-admission.json'
COLLECT_ADMISSION = ROOT / '.pokechamp-data/kev/ex070-battle-admission.json'
PROTOCOL = 'project_context/experiments/EX-070-kev-continuation-question.md'
DECISION = 'project_context/decisions/D-111-kev-continuation-question.md'
BASELINE_CONFIG_SHA256 = '0e1bee32c1495e7acad2d8cc8460290bef016852583450f50015e53a4055d4b5'
GAME = 'test-t100817-s0'
LIMITS = dict(games=1, request_seconds=600, battle_seconds=1800, total_seconds=3600,
              cleanup_reserve_seconds=60, concurrency=1, retries=0, fallback=0, recollection=0)
PRECHECKS = dict(cpu='required', validation_predictions='skipped_by_user', smoke='skipped_by_user')
CHANGED_SOURCES = {
    'integration/pokechamp/' + name for name in ('kev_value.py', 'kev_player.py', 'kev_battle.py',
    'kev_main.py', 'kev_audit.py', 'kev_viewer.py', 'tests/test_kev_player.py',
    'tests/test_kev_audit_viewer.py')
}
ADDED_SOURCES = {'integration/pokechamp/kev_continuation.py',
    'integration/pokechamp/tests/test_kev_continuation.py', 'scripts/pokechamp-kev-continuation',
    PROTOCOL, DECISION}


def sources():
    result = main_run.sources()
    for name in ('scripts/pokechamp-kev-continuation', PROTOCOL, DECISION):
        result[name] = file_hash(ROOT / name)
    return result


def configuration():
    """Use the frozen live configuration, never the locked training/eval suite."""
    if file_hash(BASELINE / 'configuration.json') != BASELINE_CONFIG_SHA256:
        raise ValueError('EX-069 baseline configuration changed')
    baseline = read(BASELINE / 'configuration.json')
    sealed = dict(line.split('  ', 1)[::-1] for line in (BASELINE / 'checksums.sha256').read_text().splitlines())
    if file_hash(BASELINE / 'server-owner.json') != sealed['server-owner.json']:
        raise ValueError('EX-069 serving settings changed')
    row = baseline['schedule'][0]
    if row['game_id'] != GAME or row['kev_actor'] != 'p2' or row['slot'] != 1:
        raise ValueError('registered first matchup changed')
    plan = {key: copy.deepcopy(baseline[key]) for key in
            ('schema_version', 'serving', 'tera_allowed', 'timer_enabled', 'ex065_manifest_sha256')}
    plan.update(experiment_id='EX-070', execution_version='ex070-v1',
        profile=value.CONTINUATION_PROFILE, question_template=value.CONTINUATION_QUESTION,
        question_sha256=hashlib.sha256(value.CONTINUATION_QUESTION.encode()).hexdigest(),
        teams={key: copy.deepcopy(baseline['teams'][key]) for key in row['teams']},
        server_settings=read(BASELINE / 'server-owner.json')['settings'],
        schedule=[copy.deepcopy(row)], limits=LIMITS, prechecks=PRECHECKS,
        baseline=dict(directory=str(BASELINE), configuration_sha256=BASELINE_CONFIG_SHA256,
            seal_sha256=file_hash(BASELINE / 'checksums.sha256'),
            live_seal_sha256=file_hash(BASELINE / row['live_directory'] / 'checksums.sha256')),
        explanation_review='미평가(기본 제외)', test_access='EX-069 live evidence only; locked suite excluded')
    return plan


def compare_identity(plan):
    baseline = read(BASELINE / 'configuration.json')
    for key in ('checkpoint', 'data_identity', 'serving', 'worker_assets'):
        if plan[key] != baseline[key]:
            raise ValueError('unchanged EX-069 identity differs: ' + key)
    before, after = baseline['source'], plan['source']
    changed = {name for name in before.keys() & after.keys() if before[name] != after[name]}
    if before.keys() - after.keys() or not after.keys() - before.keys() <= ADDED_SOURCES:
        raise ValueError('EX-070 source additions/removals exceed scope')
    # Historical EX status text was finalized after its execution freeze.
    documents = {main_run.PROTOCOL, 'project_context/experiments/EX-068-kev-battle.md'}
    if not changed <= CHANGED_SOURCES | documents:
        raise ValueError('EX-070 unrelated runtime changed: ' + repr(sorted(changed - CHANGED_SOURCES - documents)))
    for team in plan['teams'].values():
        if file_hash(team['source']) != team['sha256']:
            raise ValueError('frozen team source changed')
    assets = ROOT / 'pokechamp/poke_env/data/static/gen9/ou/sets_1500.json'
    if file_hash(assets) != plan['worker_assets']['sha256']:
        raise ValueError('worker assets changed')
    return dict(passed=True, changed_sources=sorted(changed), added_sources=sorted(after.keys() - before.keys()))


def prepare(directory=OUTPUT):
    from . import cli
    directory = Path(directory).resolve()
    if directory.exists():
        raise FileExistsError('preserve existing EX-070 preparation')
    cli._assert_submodule_pins(require_clean=True)
    checks = read(EVIDENCE / 'cpu-verification.json')
    if not checks.get('passed') or checks['source'] != sources():
        raise ValueError('passing CPU verification of the final source required')
    baseline = read(BASELINE / 'configuration.json')
    plan = dict(configuration(), source=sources(), data_identity=control.data_identity(),
        checkpoint=control.model_identity(), worker_assets=baseline['worker_assets'],
        prior_qualification=main_run.prior_qualification(), created_at=time.time(),
        cpu_verification_sha256=file_hash(EVIDENCE / 'cpu-verification.json'))
    comparison = compare_identity(plan)
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / 'configuration.json', plan)
    for name, checksum in plan['source'].items():
        target = directory / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
        if file_hash(target) != checksum:
            raise ValueError('source changed during freeze')
    write(directory / 'identity-comparison.json', comparison)
    receipt = dict(passed=True, configuration_sha256=file_hash(directory / 'configuration.json'),
        cpu_verification_sha256=plan['cpu_verification_sha256'], planned=1,
        model_requests=0, battle_attempts=0, gpu_jobs_started=0)
    write(directory / 'prepared.json', receipt)
    return receipt


def verify_prepared(directory):
    directory = Path(directory)
    receipt, plan = read(directory / 'prepared.json'), read(directory / 'configuration.json')
    if not receipt.get('passed') or receipt['configuration_sha256'] != file_hash(directory / 'configuration.json'):
        raise ValueError('EX-070 prepared configuration changed')
    if any(plan.get(key) != item for key, item in configuration().items()):
        raise ValueError('EX-070 registered prompt, matchup or limits changed')
    if plan['source'] != sources() or plan['data_identity'] != control.data_identity():
        raise ValueError('EX-070 source/data drift')
    if plan['cpu_verification_sha256'] != file_hash(EVIDENCE / 'cpu-verification.json'):
        raise ValueError('EX-070 CPU receipt changed')
    for name, checksum in plan['source'].items():
        if file_hash(directory / 'source' / name) != checksum:
            raise ValueError('frozen source copy changed: ' + name)
    if plan['prior_qualification'] != main_run.prior_qualification():
        raise ValueError('prior acceptance changed')
    compare_identity(plan)
    return plan


def gpu_snapshot():
    gpus = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,memory.used', '--format=csv,noheader'], text=True)
    apps = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader'], text=True)
    uuid = next(line.split(',')[1].strip() for line in gpus.splitlines() if line.split(',')[0].strip() == '3')
    return dict(gpus=gpus, apps=apps, gpu3_uuid=uuid,
                gpu3_apps=[line for line in apps.splitlines() if line.split(',')[0].strip() == uuid])


def port_open():
    with socket.socket() as sock:
        sock.settimeout(.2)
        return sock.connect_ex(('127.0.0.1', 8019)) == 0


def claim(directory):
    admission = dict(experiment_id='EX-070', decision='D-111', planned=1, game_id=GAME,
        directory=str(Path(directory).resolve()), at=time.time(), monotonic=time.monotonic(),
        coordinator_pid=os.getpid(), configuration_sha256=file_hash(Path(directory) / 'configuration.json'),
        limits=LIMITS)
    # Global execution admission includes startup; no restart after a failed attempt.
    control.exclusive_json(ADMISSION, admission)
    return admission


def collection_deadline(admission):
    return admission['monotonic'] + LIMITS['total_seconds'] - LIMITS['cleanup_reserve_seconds']


def collect(directory):
    """Private supervised child; the persisted parent and one-shot admission are mandatory."""
    directory = Path(directory).resolve()
    admission = read(ADMISSION)
    if (admission['directory'] != str(directory) or admission['coordinator_pid'] != os.getppid() or
            admission['configuration_sha256'] != file_hash(directory / 'configuration.json') or
            time.monotonic() >= collection_deadline(admission)):
        raise ValueError('EX-070 active owner admission required')
    control.exclusive_json(COLLECT_ADMISSION, dict(admission, collected_at=time.time()))
    plan = verify_prepared(directory)
    serving = control.server_identity()
    if serving['checkpoint'] != plan['checkpoint']:
        raise ValueError('running checkpoint differs from frozen EX-069 model')
    owner = read(directory / 'server-owner.json')
    if serving['identity']['pid'] != owner['pid'] or serving['identity']['start_ticks'] != owner['start_ticks']:
        raise ValueError('serving process differs from owned server')
    write(directory / 'server-before.json', serving)

    def interrupted(signum, _frame):
        raise InterruptedError('EX-070 collection stopped by supervisor: ' + str(signum))

    signal.signal(signal.SIGTERM, interrupted)
    write(directory / 'battle-started.json', dict(at=time.time(), monotonic=time.monotonic(), game_id=GAME))
    result = main_run._match(directory, plan, plan['schedule'][0], serving,
        admission['monotonic'] + LIMITS['total_seconds'], source_provider=sources)
    try:
        verify_prepared(directory)
        final = control.server_identity()
        write(directory / 'server-after.json', final)
        if final['identity'] != serving['identity'] or final['checkpoint'] != plan['checkpoint']:
            raise ValueError('server/model changed during EX-070')
        result['postrun_provenance_passed'] = True
    except Exception as exc:
        result.update(passed=False, postrun_provenance_passed=False, postrun_error=main_run._error(exc), valid_completed=0)
        for outcome in result['outcomes']:
            outcome.update(valid=False, invalid=bool(outcome['completed']))
    write(directory / 'collection-result.json', result)
    return result


def _stop_owned(processes):
    """psutil handles include creation times, guarding against PID reuse."""
    import psutil
    live = []
    for process in processes:
        try:
            if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                process.terminate()
                live.append(process)
        except psutil.NoSuchProcess:
            pass
    _, pending = psutil.wait_procs(live, timeout=8)
    for process in pending:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    _, pending = psutil.wait_procs(pending, timeout=5)
    return [process.pid for process in pending if process.is_running()]


def run(directory=OUTPUT):
    import psutil
    from . import cli
    directory = Path(directory).resolve()
    plan = verify_prepared(directory)
    snapshot = gpu_snapshot()
    if snapshot['gpu3_apps'] or port_open():
        raise ValueError('GPU3 and port 8019 must be free')
    admission = claim(directory)
    write(directory / 'execution-started.json', admission)
    server = collector = None
    owned, logs, error = {}, [], None
    previous = {}

    def interrupted(signum, _frame):
        raise InterruptedError('EX-070 owner received signal ' + str(signum))

    for sig in (signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.signal(sig, interrupted)
    try:
        settings = plan['server_settings']
        args = ['/ref/kev/.venv/bin/python', '-m', 'kev.serve', '--run',
                'runs/pokechamp-r1/4b-kev4b-delta', '--host', '127.0.0.1', '--port', '8019']
        write(directory / 'server-start-intent.json', dict(admission=admission, args=args,
            settings=settings, cwd='/ref/kev', gpu_before=snapshot))
        log = (directory / 'server.log').open('xb')
        logs.append(log)
        server = subprocess.Popen(args, cwd=control.KEV, env=dict(os.environ, **settings),
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        owned[server.pid] = psutil.Process(server.pid)
        ticks = Path(f'/proc/{server.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
        write(directory / 'server-owner.json', dict(pid=server.pid, start_ticks=ticks,
            started_at=time.time(), settings=settings, args=args, admission=admission))
        while not port_open():
            if server.poll() is not None:
                raise RuntimeError('owned Kev server exited before readiness')
            if time.monotonic() >= collection_deadline(admission):
                raise TimeoutError('EX-070 startup exhausted collection budget')
            time.sleep(.2)
        env = cli._child_environment(PYTHONPATH=f'{ROOT}:{ROOT / "pokechamp"}', CUDA_VISIBLE_DEVICES='',
            OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
        log = (directory / 'collection.log').open('xb')
        logs.append(log)
        collector = subprocess.Popen([sys.executable, '-m', 'integration.pokechamp.kev_continuation',
            'collect', '--output', str(directory)], cwd=ROOT / 'pokechamp', env=env,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        owned[collector.pid] = psutil.Process(collector.pid)
        write(directory / 'collector-owner.json', dict(pid=collector.pid, at=time.time()))
        while collector.poll() is None:
            for process in list(owned.values()):
                try:
                    owned.update({child.pid: child for child in process.children(recursive=True)})
                except psutil.NoSuchProcess:
                    pass
            if server.poll() is not None:
                raise RuntimeError('owned Kev server exited during collection')
            if time.monotonic() >= collection_deadline(admission):
                raise TimeoutError('EX-070 cumulative budget; final 60 seconds reserved for cleanup')
            time.sleep(.5)
        if collector.returncode != 0:
            raise RuntimeError('EX-070 collection process failed; see preserved collection.log')
    except BaseException as exc:
        error = main_run._error(exc)
    finally:
        cleanup_started = time.monotonic()
        # Let the collector run its own worker/Showdown finally block first.
        if collector is not None and collector.poll() is None:
            collector.terminate()
            try:
                collector.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        pending = _stop_owned(list(owned.values()))
        for process in (collector, server):
            if process is not None:
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pending.append(process.pid)
        for log in logs:
            log.close()
        worktree = directory / plan['schedule'][0]['live_directory'] / 'battle-1/showdown-worktree'
        worktree_error = None
        if worktree.exists():
            try:
                subprocess.run(['git', 'worktree', 'remove', '--force', str(worktree)], cwd=cli.SHOWDOWN_ROOT,
                    check=True, capture_output=True, timeout=10)
            except Exception as exc:
                worktree_error = main_run._error(exc)
        after = gpu_snapshot()
        elapsed = time.monotonic() - admission['monotonic']
        cleanup = dict(passed=not pending and not after['gpu3_apps'] and not port_open() and not worktree.exists()
                       and elapsed <= LIMITS['total_seconds'], owned_pids=sorted(owned), pending_pids=pending,
            gpu_before=snapshot, gpu_after=after, port_closed=not port_open(), worktree_removed=not worktree.exists(),
            worktree_error=worktree_error, elapsed_seconds=elapsed, cleanup_seconds=time.monotonic()-cleanup_started)
        write(directory / 'cleanup.json', cleanup)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    attempted = int((directory / 'battle-started.json').exists())
    result = read(directory / 'collection-result.json') if (directory / 'collection-result.json').exists() else dict(
        completed=0, valid_completed=0, outcomes=[], passed=False)
    result.update(experiment_id='EX-070', planned=1, attempted=attempted, unattempted=1-attempted,
        failed=attempted-int(bool(result['completed'])), invalid=int(bool(result['completed']) and not result['valid_completed']),
        execution_error=error, admission=admission, cleanup=cleanup, elapsed_seconds=elapsed)
    result['passed'] = bool(result['passed'] and error is None and cleanup['passed'])
    write(directory / 'result.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'collect'))
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    result = dict(prepare=prepare, run=run, collect=collect)[args.command](args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if not result.get('passed'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
