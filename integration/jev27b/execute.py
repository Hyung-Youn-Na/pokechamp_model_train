"""Run the registered EX-082 gates and collection once, retaining every failure."""
import asyncio
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

from .config import BASELINE, ENDPOINT, EVIDENCE, MODEL_DIR, PYTHON, ROOT, RUN
from .storage import file_hash, read, write


def child_environment():
    # Local evaluation requires no inherited provider credentials or mutable .env.
    keys = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'LD_LIBRARY_PATH')
    environment = {key: os.environ[key] for key in keys if key in os.environ}
    environment.update(PYTHONPATH=f'{ROOT}:{ROOT / "pokechamp"}',
        PYTHONDONTWRITEBYTECODE='1', TOKENIZERS_PARALLELISM='false',
        OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4')
    return environment


def stop_owned_process(process):
    """Terminate the process group created by this controller, then reap its child."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def install_signal_handlers():
    def terminate(signum, frame):
        raise KeyboardInterrupt(f'owned EX-082 controller received signal {signum}')
    signal.signal(signal.SIGTERM, terminate)


def stage(command, log):
    process = None
    with Path(log).open('x') as output:
        try:
            process = subprocess.Popen(command, cwd=ROOT, env=child_environment(),
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True)
            process.wait()
        finally:
            if process is not None:
                stop_owned_process(process)
    if process.returncode:
        raise RuntimeError(f'stage failed (exit {process.returncode}); see {log}')
    return process.pid


def execute():
    from .client import LocalClient
    from . import battle, preflight, study

    for name in ('download.json', 'environment.json', 'lengths/report.json', 'cpu.json'):
        if read(EVIDENCE / name).get('passed') is not True:
            raise RuntimeError('required preparation gate failed: ' + name)
    census = read(EVIDENCE / 'lengths/report.json')
    if (census['requests'] != 1073 or census['max_tokens'] != 32768
            or census['above_limit'] != 0 or census['max_input_tokens'] > 32768
            or census['formatting_sha256'] != file_hash(Path(__file__).with_name('formatting.py'))
            or census['tokenizer_sha256'] != file_hash(MODEL_DIR / 'tokenizer.json')
            or census['source_events_sha256'] != file_hash(BASELINE / 'events.jsonl')
            or census['rows_sha256'] != file_hash(EVIDENCE / 'lengths/requests.jsonl')):
        raise ValueError('archived length gate is stale or incomplete')
    if RUN.exists():
        raise FileExistsError('EX-082 cannot resume or overwrite an existing battle run')
    sources = study.source_identity()
    cpu = read(EVIDENCE / 'cpu.json')
    if cpu['source'] != sources:
        raise ValueError('CPU verification source changed before GPU gates')
    start = dict(at=time.time(), source=sources, time_limits=None,
                 model_download_sha256=file_hash(EVIDENCE / 'download.json'))
    recovery_path = EVIDENCE / 'preflight-recovery.json'
    if recovery_path.is_file():
        recovery = read(recovery_path)
        original = EVIDENCE / 'preflight-attempt1/execution-start.json'
        if file_hash(original) != recovery['original_execution_start_sha256']:
            raise ValueError('preserved original preflight clock changed')
        start.update(first_execution_at=read(original)['at'],
                     preflight_recovery_sha256=file_hash(recovery_path),
                     previous_gpu_gate_calls=recovery['previous_gpu_gate_calls'])
    write(EVIDENCE / 'execution-start.json', start)
    server = server_log = None
    server_dir = EVIDENCE / 'serving'
    result = None
    try:
        from .resource import wait_owned_gpu_release
        for name in ('reload-a', 'reload-b'):
            stage_pid = stage([str(PYTHON), '-B', '-m', 'integration.jev27b.preflight', 'infer',
                               str(EVIDENCE / name)], EVIDENCE / f'{name}.log')
            wait_owned_gpu_release(EVIDENCE / name, stage_pid)
        preflight.compare(EVIDENCE / 'reload-a', EVIDENCE / 'reload-b', EVIDENCE / 'reload-comparison.json')
        first = read(EVIDENCE / 'reload-a/result.json')['metadata']['serving_identity']
        second = read(EVIDENCE / 'reload-b/result.json')['metadata']['serving_identity']
        if first != second:
            raise ValueError('independent reload serving identities differ')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 18782))
        server_dir.mkdir(exist_ok=False)
        server_log = (EVIDENCE / 'serving.log').open('x')
        server = subprocess.Popen([str(PYTHON), '-B', '-m', 'integration.jev27b.server',
            '--model-dir', str(MODEL_DIR), '--run-dir', str(server_dir)],
            cwd=ROOT, env=child_environment(), stdin=subprocess.DEVNULL,
            stdout=server_log, stderr=subprocess.STDOUT, start_new_session=True)
        # Model loading has no elapsed-time deadline. A process exit is a failure.
        while True:
            if server.poll() is not None:
                raise RuntimeError('owned model server exited before becoming ready')
            try:
                with socket.create_connection(('127.0.0.1', 18782), timeout=1):
                    break
            except OSError:
                time.sleep(1)
        with LocalClient(ENDPOINT, expected_identity=first) as client:
            health = client.health()
            if health['server_pid'] != server.pid:
                raise ValueError('loopback service is not the owned model process')
            write(EVIDENCE / 'serving-health.json', health)
            case = next(case for case in read(EVIDENCE / 'lengths/cases.json')
                        if case['name'] == 'turn-sample-01')
            at = time.time()
            request_id = 'ex082-ordinary-preflight-v1'
            response = client.evaluate(case['body'], request_id=request_id, retries=0)
            from integration.pokechamp.jev_battle import validate_answer
            choice = validate_answer(response, case['body']['questions']['action']['criteria'])
            write(EVIDENCE / 'ordinary-preflight.json', dict(passed=True, at=at,
                seconds=time.time()-at, request_id=request_id, request=case['body'], response=response,
                choice=choice, transport=client.last_transport, new_battles=0, retries=0))
        if study.source_identity() != sources:
            raise ValueError('source changed during GPU gates')
        baseline = study.load_baseline(full_seal=True)
        gates = dict(passed=True, cpu_passed=True, length_passed=True, reload_passed=True,
            preflight_passed=True, serving_identity=first, source=sources,
            input_data_identity=baseline['input_data_identity'],
            baseline_manifest_sha256=file_hash(BASELINE / 'manifest.json'),
            server_journal=str(server_dir / 'server/requests.sqlite3'),
            evidence={name: file_hash(EVIDENCE / name) for name in (
                'cpu.json', 'lengths/report.json', 'reload-comparison.json',
                'ordinary-preflight.json', 'download.json', 'environment.json')})
        write(EVIDENCE / 'entry-gates.json', gates)
        previous_directory = Path.cwd()
        try:
            os.chdir(ROOT / 'pokechamp')
            result = asyncio.run(battle.run(RUN, expected_identity=first, gate_receipt=gates,
                                           endpoint=ENDPOINT))
        finally:
            os.chdir(previous_directory)
    except BaseException as error:
        write(EVIDENCE / 'execution-failure.json', dict(at=time.time(),
              type=type(error).__name__, detail=str(error), battle_collection_started=RUN.exists()))
        raise
    finally:
        if server is not None:
            stop_owned_process(server)
        if server_log is not None:
            server_log.close()
        from .resource import disk_bytes, gpu_facts
        write(EVIDENCE / 'execution-cleanup.json', dict(at=time.time(),
              server_pid=None if server is None else server.pid,
              server_exit=None if server is None else server.returncode,
              gpus=gpu_facts(), additional_disk_bytes=disk_bytes()))
    if result is not None:
        final = study.finalize(RUN, evidence=EVIDENCE)
        write(EVIDENCE / 'finalization.json', final)
        stage(['/tmp/ep037/tools/bin/python', '-B', '-m', 'integration.jev27b.study',
               'verify-browser'], EVIDENCE / 'viewer-browser.log')
    return result


if __name__ == '__main__':
    install_signal_handlers()
    execute()
