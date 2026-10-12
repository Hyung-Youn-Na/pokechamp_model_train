"""Cumulative-budget qualification and one-pass battle controller."""
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback

from . import config as c, protocol as p, storage as s
from .diagnose import start_server, stop_server, request, validation_inputs, compare, process_identity


def verified_closure(closed):
    flags = ('weights_unchanged', 'base_unchanged', 'checkpoint_files_unchanged', 'source_unchanged')
    return (closed['returncode'] == 0 and isinstance(closed.get('closure'), dict)
            and all(closed['closure'].get(k) is True for k in flags)
            and closed['closure'].get('optimizer_updates') == 0)


def status(directory, phase, **extra):
    value = dict(phase=phase, at=s.now(), controller_pid=os.getpid(),
                 remaining_seconds=s.remaining(directory) if s.clock(directory) else None)
    value.update(extra)
    s.atomic(Path(directory) / 'status.json', value)


def verify_configuration(directory):
    from .battle import verify_sources
    from ...kev_control import data_identity
    from ... import cli
    directory = Path(directory)
    plan = s.read(directory / 'configuration.json')
    if (plan['limits'] != c.LIMITS or plan['physical_gpu'] != 0 or plan['profile'] != c.PROFILE
            or plan['model'] != s.checkpoint_identity()
            or s.sha(directory / 'configuration.json') != s.read(directory / 'prepared.json')['configuration_sha256']):
        raise ValueError('frozen EX081 configuration changed')
    verify_sources(plan)
    if data_identity() != plan['data_identity']:
        raise ValueError('frozen official input/static asset identity changed')
    cli._assert_submodule_pins(require_clean=True)
    return plan


def qualify(directory=c.OUTPUT):
    directory = Path(directory)
    verify_configuration(directory)
    if (directory / 'qualification/passed.json').exists():
        raise FileExistsError('qualification receipt already exists; validate its live process instead')
    inputs = validation_inputs()
    attempt = 'original-' + str(time.time_ns())
    output = directory / 'qualification' / attempt
    output.mkdir(parents=True, exist_ok=False)
    results, summaries = [], []
    process = None
    server_output = None
    retained = False
    try:
        for name in ('a', 'b'):
            label = 'qualification-' + attempt + '-' + name
            process, server_output, health = start_server(directory, label)
            plan = s.read(directory / 'configuration.json')
            if health['source_sha256'] != plan['serving_source_sha256']:
                raise ValueError('model server source differs from frozen serving source')
            observed, maximum = [], 0.0
            process_output = output / name
            process_output.mkdir()
            for index, (expected, joint) in enumerate(inputs):
                if s.remaining(directory) <= c.LIMITS['cleanup_reserve_seconds']:
                    raise TimeoutError('qualification reached finalization reserve')
                response = request(health['endpoint'], '/evaluate', p.request_payload(joint))
                from .client import validate_identity
                validate_identity(response, health)
                result = compare(response, expected, joint)
                observed.append(result)
                maximum = max(maximum, result['maximum_q_difference'])
                s.append(process_output / 'predictions.jsonl', result)
                if (index + 1) % 10 == 0 or index + 1 == len(inputs):
                    status(directory, 'qualification', process=name, observations=index + 1,
                           total_observations=len(inputs), maximum_q_difference=maximum,
                           server_pid=process.pid, server_output=str(server_output))
            summary = dict(passed=maximum <= c.TOLERANCE, at=s.now(), process=name,
                observations=len(observed), candidates=2991, maximum_q_difference=maximum,
                selected_changes=sum(row['selected_changed'] for row in observed), server=health,
                predictions_sha256=s.sha(process_output / 'predictions.jsonl'))
            s.atomic(process_output / 'report.json', summary, immutable=True)
            summaries.append(summary)
            results.append(observed)
            if not summary['passed']:
                raise ValueError('original validation q difference exceeds 1e-4 in process ' + name)
            if name == 'a':
                closed = stop_server(process, server_output)
                process = None
                s.atomic(process_output / 'closure.json', closed, immutable=True)
                if not verified_closure(closed):
                    raise ValueError('first qualification process integrity closure failed')
        maximum_pair = max(abs(a-b) for first, second in zip(results[0], results[1], strict=True)
                           for a, b in zip(first['predicted_q'], second['predicted_q'], strict=True))
        if maximum_pair > c.TOLERANCE:
            raise ValueError('cross-process q difference exceeds 1e-4')
        from .client import health as check_health
        check_health(health['endpoint'], health)
        verify_configuration(directory)
        receipt = dict(passed=True, at=s.now(), tolerance=c.TOLERANCE,
            process_reports=[str(output / name / 'report.json') for name in ('a', 'b')],
            maximum_q_difference=max(row['maximum_q_difference'] for row in summaries),
            maximum_process_difference=maximum_pair, observations_per_process=320,
            candidates_per_process=2991, server=health, endpoint=health['endpoint'],
            server_output=str(server_output), configuration_sha256=s.sha(directory / 'configuration.json'),
            historical_reload_cause='unconfirmed; original failure and predictions preserved')
        s.atomic(directory / 'qualification/passed.json', receipt, immutable=True)
        retained = True
        status(directory, 'qualified', server_pid=process.pid, observations=640,
               maximum_q_difference=receipt['maximum_q_difference'], maximum_process_difference=maximum_pair)
        return process, server_output, receipt
    except BaseException as exc:
        error = dict(error=str(exc), traceback=traceback.format_exc(), at=s.now())
        s.atomic(output / 'failure.json', error, immutable=True)
        status(directory, 'qualification_failed', **error)
        raise
    finally:
        if not retained and process is not None:
            closed = stop_server(process, server_output)
            s.atomic(output / ('cleanup-' + str(process.pid) + '.json'), closed, immutable=True)


class RecordedProcess:
    """Attach only to the exact retained server identity, never a recycled PID."""
    def __init__(self, receipt):
        self.pid = receipt['server']['server_pid']
        self.receipt = receipt
        self.returncode = None
        self.output = Path(receipt['server_output'])
        self.identity = s.read(self.output.parent / (self.output.name + '-owner.json'))['process_identity']
        self._verify()
        from .client import health as check_health
        check_health(self.receipt['endpoint'], self.receipt['server'])

    def _verify(self):
        command = Path(f'/proc/{self.pid}/cmdline').read_bytes().split(b'\0')
        if (b'integration.pokechamp.joint_q.battle_eval.server' not in command
                or str(self.output).encode() not in command):
            raise RuntimeError('retained server PID no longer belongs to EX081')
        if process_identity(self.pid) != self.identity:
            raise RuntimeError('retained server process identity changed')

    def poll(self):
        try:
            stat = Path(f'/proc/{self.pid}/stat').read_text().split(') ', 1)[1].split()[0]
            if stat != 'Z' and process_identity(self.pid) == self.identity:
                return None
        except FileNotFoundError:
            pass
        self.returncode = 0 if (self.output / 'closure.json').exists() and not (self.output / 'failure.json').exists() else 1
        return self.returncode

    def send_signal(self, sig):
        self._verify()
        os.kill(self.pid, sig)

    def wait(self, timeout=None):
        until = time.monotonic() + (timeout or 300)
        while self.poll() is None:
            if time.monotonic() >= until:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            time.sleep(.2)
        return self.returncode

    def kill(self):
        # A nonresponsive server is never killed using an unchecked reused PID.
        self._verify()
        os.kill(self.pid, signal.SIGKILL)


def run(directory=c.OUTPUT):
    directory = Path(directory)
    plan = verify_configuration(directory)
    admission = directory / 'battle-admission.json'
    if admission.exists():
        raise FileExistsError('battle execution already admitted; automatic replay forbidden')
    process = None
    server_output = None
    game_process = None
    results = []
    error = None
    owned_close = None
    try:
        if (directory / 'qualification/passed.json').exists():
            receipt = s.read(directory / 'qualification/passed.json')
            if not receipt['passed'] or receipt['configuration_sha256'] != s.sha(directory / 'configuration.json'):
                raise ValueError('qualification does not bind this configuration')
            process = RecordedProcess(receipt)
            server_output = Path(receipt['server_output'])
        else:
            process, server_output, receipt = qualify(directory)
        execution = dict(plan, server=receipt['server'], endpoint=receipt['endpoint'])
        s.atomic(directory / 'execution-plan.json', execution, immutable=True)
        s.atomic(admission, dict(at=s.now(), maximum=20, recollection=0,
                 qualification_sha256=s.sha(directory / 'qualification/passed.json')),
                 immutable=True)
        for row in plan['schedule']:
            if s.remaining(directory) < c.LIMITS['battle_seconds'] + c.LIMITS['cleanup_reserve_seconds']:
                raise TimeoutError('insufficient time for another complete game plus finalization reserve')
            verify_configuration(directory)
            status(directory, 'battle', game_id=row['game_id'], slot=row['global_slot'],
                   completed=sum(r['valid'] for r in results), planned=20)
            log_path = directory / 'battle-logs' / (row['game_id'] + '.log')
            log_path.parent.mkdir(exist_ok=True)
            env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1',
                       OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
            with log_path.open('xb') as log:
                game_process = subprocess.Popen([str(c.NATIVE), '-u', '-m',
                    'integration.pokechamp.joint_q.battle_eval.battle', 'game',
                    '--directory', str(directory), '--plan', str(directory / 'execution-plan.json'),
                    '--game-id', row['game_id'], '--endpoint', receipt['endpoint'],
                    '--deadline-at', str(s.clock(directory)['deadline_at'])],
                    cwd=c.ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True)
            next_status = time.monotonic() + 15
            while game_process.poll() is None:
                if s.remaining(directory) <= c.LIMITS['cleanup_reserve_seconds']:
                    raise TimeoutError('battle reached finalization reserve')
                if time.monotonic() >= next_status:
                    status(directory, 'battle', game_id=row['game_id'], slot=row['global_slot'],
                           completed=sum(r['valid'] for r in results), planned=20,
                           battle_controller_pid=game_process.pid, model_server_pid=process.pid)
                    next_status = time.monotonic() + 15
                time.sleep(1)
            result_path = directory / row['live_directory'] / 'result.json'
            if not result_path.exists():
                raise RuntimeError('battle worker left no result: ' + str(log_path))
            result = s.read(result_path)
            results.append(dict(game_id=row['game_id'], slot=row['global_slot'],
                                result_path=str(result_path), **result))
            s.atomic(directory / 'result.json', dict(planned=20, attempted=len(results),
                     game_results=results, completed=sum(r['valid'] for r in results), stopped=False))
            if game_process.returncode != 0 or not result['continue_allowed']:
                raise RuntimeError('battle technical failure: ' + row['game_id'])
            game_process = None
    except BaseException as exc:
        error = dict(error=str(exc), type=type(exc).__name__, traceback=traceback.format_exc(), at=s.now())
        s.atomic(directory / 'failures' / (str(time.time_ns()) + '.json'), error, immutable=True)
    finally:
        cleanup_errors = []
        if game_process is not None and game_process.poll() is None:
            try:
                game_process.send_signal(signal.SIGTERM)
                try:
                    game_process.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    os.killpg(game_process.pid, signal.SIGKILL)
                    game_process.wait(timeout=30)
            except BaseException as exc:
                cleanup_errors.append(dict(error=str(exc), resource='battle', type=type(exc).__name__))
        if process is not None:
            try:
                owned_close = stop_server(process, server_output)
                s.atomic(directory / 'model-closure.json', owned_close, immutable=True)
                if not verified_closure(owned_close):
                    error = error or dict(error='model integrity closure failed', type='IntegrityError')
            except BaseException as exc:
                cleanup_errors.append(dict(error=str(exc), resource='model', type=type(exc).__name__))
        if cleanup_errors:
            error = error or dict(error='owned resource cleanup failed', type='CleanupError')
        admitted = sum((directory / row['directory']).exists() for row in plan['schedule'])
        final = dict(planned=20, attempted=admitted, game_results=results,
            completed=sum(r['valid'] for r in results), stopped=error is not None, error=error,
            model_closure=owned_close, cleanup_errors=cleanup_errors, at=s.now(), clock=s.clock(directory))
        s.atomic(directory / 'result.json', final)
        status(directory, 'collected' if error is None else 'stopped', error=error,
               attempted=admitted, completed=final['completed'], planned=20)
    return final


def finalize(directory=c.OUTPUT):
    from .outputs import finalize as finalize_outputs
    from .viewer import export
    directory = Path(directory)
    current = s.preservation(full=True)
    before = s.read(directory / 'preservation-before.json')
    passed = (before['sources'] == current['sources'] and before['checkpoint'] == current['checkpoint']
              and all(current['original_files'].get(k) == v for k, v in before['original_files'].items()))
    s.atomic(directory / 'preservation-after.json', dict(passed=passed, **current))
    if not passed:
        raise ValueError('original EX066 preservation check failed')
    metrics = finalize_outputs(directory)
    exported = export(directory, c.ROOT / 'exports/battle_viewers/ex081', metrics=metrics)
    s.atomic(directory / 'final/export.json', exported)
    return dict(metrics=metrics, export=exported)
