"""Owner-controlled saved-validation diagnostics, never test inputs or labels."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
import urllib.request

from . import config as c, protocol as p, storage as s
from ..serializer import JointInput

SUSPECT = 'validation-t47268-s0-o0017'


def validation_inputs():
    expected = s.rows(c.ORIGINAL / 'training/validation-epoch3.jsonl')
    from ..storage import digest as token_digest
    cached = {row['observation_id']: row for row in s.rows(c.ORIGINAL / 'prepared/validation-epoch0.jsonl')}
    for row in expected:
        tokens = cached[row['observation_id']]
        if (tokens['token_sha256'] != token_digest(tokens['input_ids'])
                or tokens['action_ids'] != row['action_ids']
                or tokens['readout_positions'] != row['readout_positions']
                or tokens['prompt_sha256'] != row['prompt_sha256'] or tokens['tokens'] != row['tokens']):
            raise ValueError('saved validation tokens disagree with original predictions')
        row['token_sha256'] = tokens['token_sha256']
    ids = [row['observation_id'] for row in expected]
    selected = {}
    # Inputs are split-tagged in the public export. No targets/private root is opened.
    with (c.DATA / 'inputs.jsonl').open() as stream:
        for line in stream:
            row = json.loads(line)
            if row['split'] != 'validation':
                continue
            if row['observation_id'] in selected:
                raise ValueError('duplicate validation input')
            selected[row['observation_id']] = JointInput(row['model_input'])
    if len(expected) != 320 or set(selected) != set(ids):
        raise ValueError('validation population differs')
    if sum(len(value.action_ids) for value in selected.values()) != 2991:
        raise ValueError('validation candidate denominator differs')
    return [(row, selected[row['observation_id']]) for row in expected]


def request(endpoint, route, body=None, *, timeout=600):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_):
            raise ValueError('local inference redirects forbidden')
    if not endpoint.startswith('http://127.0.0.1:'):
        raise ValueError('loopback endpoint required')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    data = None if body is None else json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
    req = urllib.request.Request(endpoint + route, data=data, headers={'Content-Type': 'application/json'})
    with opener.open(req, timeout=timeout) as response:
        return json.loads(response.read())


def start_server(directory, label, *, variant='original'):
    directory = Path(directory)
    output = directory / 'server' / label
    if output.exists():
        raise FileExistsError('preserve the previous model process: ' + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.parent / (label + '.log')
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='0', HF_HUB_OFFLINE='1',
               HF_HUB_DISABLE_IMPLICIT_TOKEN='1', PYTHONDONTWRITEBYTECODE='1',
               PYTHONHASHSEED='20260930', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false',
               HF_HOME=str(c.ROOT / '.tools/eve-rlcd/worktrees/pokemon-training/.cache/huggingface'))
    if variant == 'deterministic':
        env['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    with log_path.open('xb') as log:
        process = subprocess.Popen([str(c.EVE), '-u', '-m',
            'integration.pokechamp.joint_q.battle_eval.server', '--directory', str(directory),
            '--output', str(output), '--variant', variant], cwd=c.ROOT, env=env,
            stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    s.atomic(directory / 'server' / (label + '-owner.json'),
             dict(pid=process.pid, label=label, log=str(log_path), started_at=time.time(),
                  process_identity=process_identity(process.pid)), immutable=True)
    try:
        until = None
        while until is None or time.monotonic() < until:
            if process.poll() is not None:
                raise RuntimeError('model startup failed; see ' + str(log_path))
            if (output / 'ready.json').exists():
                health = s.read(output / 'ready.json')
                if not health['ready'] or health['server_pid'] != process.pid or health['physical_gpu'] != 0:
                    raise ValueError('unexpected owned model service identity')
                return process, output, health
            if until is None and (output / 'gpu-admitted.json').exists():
                until = time.monotonic() + 600
            if s.clock(directory) and s.remaining(directory) <= c.LIMITS['cleanup_reserve_seconds']:
                raise TimeoutError('model startup or GPU wait reached finalization reserve')
            time.sleep(1)
        raise TimeoutError('model service startup timeout')
    except BaseException:
        stop_server(process, output)
        raise


def process_identity(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
    return dict(pid=pid, start_ticks=fields[19],
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                command=Path(f'/proc/{pid}/cmdline').read_bytes().decode().split('\0')[:-1])


def stop_server(process, output):
    if process.poll() is None:
        # Only this exact live Popen child is signalled; no global process matching.
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=30)
    return dict(pid=process.pid, returncode=process.returncode,
                closure=s.read(Path(output) / 'closure.json') if (Path(output) / 'closure.json').exists() else None)


def compare(response, expected, joint):
    p.validate_response(response, joint.action_ids)
    if (tuple(expected['action_ids']) != joint.action_ids
            or response['input_sha256'] != p.input_sha256(joint)
            or response['prompt_sha256'] != expected['prompt_sha256']
            or response['token_sha256'] != expected['token_sha256']
            or response['readout_positions'] != expected['readout_positions']
            or response['tokens'] != expected['tokens']):
        raise ValueError('exact validation input/token/readout identity differs')
    predicted = [response['q_values'][aid] for aid in joint.action_ids]
    maximum = max(abs(a-b) for a, b in zip(predicted, expected['predicted_q'], strict=True))
    old_choice = expected['action_ids'][max(range(len(expected['predicted_q'])),
                                           key=expected['predicted_q'].__getitem__)]
    return dict(observation_id=expected['observation_id'], maximum_q_difference=maximum,
                selected_changed=response['choice'] != old_choice,
                predicted_q=predicted, reference_q=expected['predicted_q'], response=response)


def diagnose(directory=c.OUTPUT, *, variant='original', repetitions=5):
    directory = Path(directory)
    label = f'diagnostic-{variant}-{time.time_ns()}'
    output = directory / 'diagnostics' / label
    output.mkdir(parents=True, exist_ok=False)
    inputs = validation_inputs()
    suspect = next(pair for pair in inputs if pair[0]['observation_id'] == SUSPECT)
    neighboring = [pair for pair in inputs if pair[0]['observation_id'] in
                   ('validation-t47268-s0-o0016', 'validation-t47268-s0-o0018')]
    sequence = [suspect] * repetitions + neighboring + [suspect] * repetitions
    model = None
    rows = []
    failure = None
    try:
        model, server_output, health = start_server(directory, label, variant=variant)
        for index, (expected, joint) in enumerate(sequence):
            if s.remaining(directory) <= c.LIMITS['cleanup_reserve_seconds']:
                raise TimeoutError('EX081 diagnostic budget exhausted')
            response = request(health['endpoint'], '/evaluate', p.request_payload(joint))
            result = dict(index=index, **compare(response, expected, joint))
            rows.append(result)
            s.append(output / 'predictions.jsonl', result)
            s.atomic(output / 'progress.json', dict(observations=len(rows), planned=len(sequence),
                      last_observation=expected['observation_id'], maximum_q_difference=result['maximum_q_difference']))
    except BaseException as exc:
        failure = dict(error=str(exc), traceback=traceback.format_exc())
        s.atomic(output / 'failure.json', failure, immutable=True)
        raise
    finally:
        closed = stop_server(model, server_output) if model else None
        summary = dict(at=s.now(), variant=variant, observations=len(rows), planned=len(sequence),
            maximum_q_difference=max((r['maximum_q_difference'] for r in rows), default=None),
            exceeded=sum(r['maximum_q_difference'] > c.TOLERANCE for r in rows),
            selected_changed=sum(r['selected_changed'] for r in rows), failure=failure, closure=closed)
        s.atomic(output / 'report.json', summary, immutable=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=c.OUTPUT)
    parser.add_argument('--variant', choices=['original', 'deterministic'], default='original')
    args = parser.parse_args()
    print(json.dumps(diagnose(args.directory, variant=args.variant), ensure_ascii=False))
