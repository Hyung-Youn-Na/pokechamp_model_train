"""One owned, bounded EX-064 collection; never starts a battle or repairs outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

from . import qwen_control as control, qwen_state_study as study, qwen_value as v
from .branch_rollouts.common import file_hash, rows


def freeze(output):
    output = Path(output)
    if (output / 'frozen-inputs.json').exists():
        study.verify_frozen_inputs(output)
        return study.read(output / 'frozen-inputs.json')
    if not study.read(output / 'preflight-tokens.json')['passed']:
        raise ValueError('successful no-truncation preflight is required')
    paths = set(output.rglob('*'))
    paths.update(p for p in (v.ROOT / 'integration/pokechamp').rglob('*')
                 if p.suffix in ('.py', '.txt', '.cjs', '.js', '.json') and
                 'node_modules' not in p.parts and '__pycache__' not in p.parts)
    paths.update([v.EVE / 'rlcd/pokemon_data.py', v.EVE / 'rlcd/pokemon_value.py',
                  v.ROOT / 'scripts/pokechamp-qwen'])
    # Calculation audits retain the exact engine/set receipts; additionally seal
    # the recommendation files which supplied the evaluated conditional sets.
    from .diagnostics.damage_sets import SNAPSHOT
    paths.update(SNAPSHOT.glob('*.json'))
    manifest = dict(created_at=time.time(), experiment='EX-064',
        model=v.MODEL, revision=v.REVISION, adapter_sha256=v.ADAPTER_SHA,
        files={str(p.resolve()): file_hash(p) for p in sorted(paths) if p.is_file()})
    study.write_new(output / 'frozen-inputs.json', manifest)
    study.verify_frozen_inputs(output)
    return manifest


def gpu_sample():
    result = subprocess.run(['nvidia-smi', '-i', '1',
        '--query-gpu=uuid,memory.used,utilization.gpu', '--format=csv,noheader,nounits'],
        capture_output=True, text=True, timeout=10)
    return dict(at=time.time(), physical_gpu=1, returncode=result.returncode,
                values=result.stdout.strip())


def integrity(output, body, phase, deadline):
    started = time.perf_counter()
    receipt = study.http_call(v.ENDPOINT, '/evaluate', body, timeout=study._timeout(deadline))
    record = dict(phase=phase, input=body, http=receipt,
                  roundtrip_seconds=time.perf_counter() - started)
    study.write_new(output / ('diagnostic-q-' + phase + '.json'), record)
    if receipt['status_code'] != 200:
        raise RuntimeError('diagnostic integrity q HTTP failure')
    v.validate_response(receipt['body'], body['actions'])
    return receipt['body']


def run(output):
    output = Path(output)
    frozen = freeze(output)
    before = control.status()
    if before['owned_running'] or before['health'] is not None:
        raise ValueError('EX-064 requires a new owned server; existing server left untouched')
    started = time.time()
    owner_token = uuid.uuid4().hex
    captured_owner = None
    deadline = started + 7200
    result = dict(experiment='EX-064', started_at=started, deadline_at=deadline,
        frozen_manifest_sha256=file_hash(output / 'frozen-inputs.json'),
        frozen_files=len(frozen['files']), gpu_before=gpu_sample(), passed=False,
        optimizer_updates=0, retries=0, battle_transmissions=0)
    study.write_new(output / 'run-start.json', result)
    try:
        owner = control.start(candidate_state=True, diagnostics=True, deadline_at=deadline,
                              owner_token=owner_token)
        captured_owner = owner['owner']
        if captured_owner['owner'] != owner_token:
            raise RuntimeError('collection did not receive its own server identity')
        result['owner'] = owner['owner']
        study.write_new(output / 'owned-server.json', owner)
        study.verify_frozen_inputs(output)
        result['q'] = study.evaluate(output, deadline_at=deadline)
        if not result['q']['passed']:
            raise RuntimeError('main q comparison incomplete; separate diagnostics not collected')
        saved = next(r for r in rows(output / 'C1/inputs.jsonl')
                     if r['body']['observation']['state']['turn'] in (3, 4, 5, 6, 8) and
                     r['body']['observation']['state']['decision_kind'] == 'turn_action' and
                     2 * len(r['body']['actions']) <= 24)
        body = saved['body']
        if 2 * len(body['actions']) > 24:
            raise ValueError('diagnostic integrity forward budget exceeded')
        q_before = integrity(output, body, 'before', deadline)
        result['diagnostics'] = study.diagnose(output, deadline_at=deadline)
        if not result['diagnostics']['passed']:
            raise RuntimeError('separate diagnostics have a technical serving failure')
        q_after = integrity(output, body, 'after', deadline)
        same_tokens = all(all(a[k] == b[k] for k in
            ('action_id', 'tokens', 'prompt_sha256', 'token_sha256'))
            for a, b in zip(q_before['candidates'], q_after['candidates'], strict=True))
        delta = max(abs(q_before['q_values'][k] - q_after['q_values'][k]) for k in q_before['q_values'])
        result['diagnostic_q_integrity'] = dict(passed=same_tokens and delta <= 1e-4,
            max_q_difference=delta, prompt_and_token_hashes_exact=same_tokens,
            extra_forwards=2 * len(body['actions']), decision=saved['decision'],
            input_version=body['observation']['state']['version'])
        if not result['diagnostic_q_integrity']['passed']:
            raise RuntimeError('q changed across separate diagnostics')
        study.verify_frozen_inputs(output)
        result['passed'] = True
    except Exception as exc:
        result['error'] = dict(type=type(exc).__name__, detail=str(exc))
    finally:
        # Only the server started in this run is eligible for cleanup.
        record = study.read(control.STATE) if control.STATE.exists() else None
        if record and record['owner'] == owner_token:
            try:
                cleanup = control.stop(timeout=60, expected_owner=captured_owner or record)
                study.write_new(output / 'cleanup.json', cleanup)
                result['cleanup'] = cleanup
                closure = cleanup.get('closure') or {}
                if not (closure.get('weights_unchanged') and closure.get('adapter_files_unchanged') and
                        closure.get('model_config_unchanged') and closure.get('generation_config_unchanged') and
                        closure.get('all_parameters_frozen') and closure.get('eval_unchanged')):
                    result['passed'] = False
                    result['closure_error'] = 'incomplete weight/config/eval closure evidence'
            except Exception as exc:
                result['passed'] = False
                result['cleanup_error'] = dict(type=type(exc).__name__, detail=str(exc))
        result['gpu_after'] = gpu_sample()
        result['elapsed_seconds'] = time.time() - started
        if result['elapsed_seconds'] > 7200:
            result['passed'] = False
            result['deadline_exceeded'] = True
        study.write_new(output / 'run-result.json', result)
        study.report(output)
        with (output / 'checksums.sha256').open('x') as stream:
            for path in sorted(output.rglob('*')):
                if path.is_file() and path.name != 'checksums.sha256':
                    stream.write(file_hash(path) + '  ' + str(path.relative_to(output)) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({k: result.get(k) for k in
        ('passed', 'elapsed_seconds', 'diagnostic_q_integrity', 'error', 'closure_error', 'cleanup_error')},
        ensure_ascii=False), flush=True)
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
