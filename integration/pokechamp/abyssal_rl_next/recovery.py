"""C-018의 단일 deterministic backend 교정 receipt를 엄격히 검증한다."""
from __future__ import annotations

from pathlib import Path
from . import config
from .storage import read, sha

SCHEMA = 'ex075-deterministic-recovery-v1'
BACKEND = {
    'deterministic_algorithms': True,
    'cudnn_deterministic': True,
    'cublas_workspace_config': ':4096:8',
}
ALLOWED_CHANGES = frozenset('integration/pokechamp/abyssal_rl_next/' + name for name in (
    'model.py', 'execution.py', 'recovery.py', 'verification.py', 'finalize.py'))


def confined(directory, relative):
    """Receipts cannot authorize reading or publishing unrelated filesystem files."""
    directory = Path(directory).resolve()
    part = Path(relative)
    if part.is_absolute() or '..' in part.parts:
        raise ValueError('recovery path must be relative to the original experiment')
    path = (directory / part).resolve()
    if not path.is_relative_to(directory):
        raise ValueError('recovery path escapes the experiment')
    return path


def verified_reference(directory, reference):
    path = confined(directory, reference['path'])
    if not path.is_file() or sha(path) != reference['sha256']:
        raise ValueError('recovery evidence missing or changed: ' + reference['path'])
    return path


def validate(directory, *, current_sources=None, receipt=None):
    """No receipt means original frozen execution; a malformed receipt never falls back."""
    directory = Path(directory)
    path = directory / 'recovery.json'
    if receipt is None:
        if not path.exists():
            return None
        receipt = read(path)
    if receipt.get('schema') != SCHEMA or receipt.get('backend') != BACKEND:
        raise ValueError('unregistered recovery schema or backend configuration')
    manifest = read(directory / 'manifest.json')
    if manifest.get('experiment_id') != 'EX-075' or manifest['protocol'] != config.PROTOCOL:
        raise ValueError('recovery cannot change protocol or numerical tolerances')
    fixed = {
        'manifest.json': 'original_manifest_sha256',
        'clock.json': 'clock_sha256',
        'prepared/manifest.json': 'prepared_sha256',
        'resource.json': 'resource_sha256',
        'verification/cpu.json': 'original_cpu_sha256',
    }
    for name, key in fixed.items():
        if sha(directory / name) != receipt[key]:
            raise ValueError('recovery changed original artifact: ' + name)
    if (receipt['prepared_sha256'] != manifest['prepared_sha256'] or
            receipt['resource_sha256'] != manifest['resource_sha256'] or
            receipt['original_cpu_sha256'] != manifest['cpu_sha256'] or
            receipt['initial_checkpoint_sha256'] != manifest['initial_checkpoint_sha256'] or
            sha(config.INITIAL / 'files.json') != receipt['initial_checkpoint_sha256']):
        raise ValueError('recovery initial model, prepared data or GPU identity differs')
    clock = read(directory / 'clock.json')
    if clock['limits'] != config.PROTOCOL['seconds'] or clock['deadline_at'] != clock['started_at'] + config.PROTOCOL['seconds']['total']:
        raise ValueError('recovery cannot restart or extend the original clock')
    previous, effective = manifest['source'], receipt['source']
    changed = {name for name in previous.keys() | effective.keys() if previous.get(name) != effective.get(name)}
    if not previous.keys() <= effective.keys() or not changed or not changed <= ALLOWED_CHANGES:
        raise ValueError('recovery modifies a source outside the narrow allowlist')
    expected_changes = {name: {'before': previous.get(name), 'after': effective[name]} for name in changed}
    if receipt['changes'] != expected_changes:
        raise ValueError('recovery source delta declaration differs')
    if current_sources is None:
        from .execution import source_files
        current_sources = source_files()
    if effective != current_sources:
        raise ValueError('runtime differs from the CPU-verified recovery source')
    for name, digest in previous.items():
        if sha(directory / 'source' / name) != digest:
            raise ValueError('original source evidence changed: ' + name)
    root = confined(directory, receipt['source_root'])
    for name, digest in effective.items():
        if not (root / name).is_file() or sha(root / name) != digest:
            raise ValueError('recovery source copy missing or changed: ' + name)
    cpu = read(verified_reference(directory, receipt['cpu']))
    if (cpu.get('passed') is not True or cpu.get('source') != effective or
            cpu.get('prepared_sha256') != receipt['prepared_sha256'] or cpu.get('gpu_operations') != 0 or
            not cpu.get('tests') or any(item['returncode'] != 0 for item in cpu['tests'])):
        raise ValueError('recovery lacks passing CPU evidence bound to its source')
    for test in cpu['tests']:
        if 'log' not in test or 'sha256' not in test:
            # Browser dependency checks originally lacked their log identity.
            # New recovery CPU receipts must bind every verification log.
            raise ValueError('recovery CPU test lacks its log hash')
        log = Path(test['log']).resolve()
        if not log.is_relative_to(directory.resolve()) or not log.is_file() or sha(log) != test['sha256']:
            raise ValueError('recovery CPU test log missing or changed')
    # Validate the unchanged bootstrap even after latest.json advances to newer steps.
    verified_reference(directory, receipt['bootstrap_checkpoint'])
    proof = read(verified_reference(directory, receipt['proof']))
    expected = {
        'passed': True, 'world_size': 4,
        'original_manifest_sha256': receipt['original_manifest_sha256'],
        'bootstrap_checkpoint_sha256': receipt['bootstrap_checkpoint']['sha256'],
        'backend': BACKEND, 'tolerances': config.PROTOCOL['numeric_tolerances'],
        'weights_restored': True, 'rng_restored': True, 'forward_unchanged': True,
    }
    if any(proof.get(key) != value for key, value in expected.items()):
        raise ValueError('independent deterministic-backend proof did not pass unchanged gates')
    references = proof.get('independent_reports', [])
    if not references:
        raise ValueError('independent proof has no original evidence')
    ranks = []
    for reference in references:
        evidence = verified_reference(directory, reference)
        if evidence.name.startswith('report-rank-') and evidence.suffix == '.json':
            report = read(evidence)
            numeric = config.PROTOCOL['numeric_tolerances']
            rank_tolerances = {
                'logp_wdl_atol': numeric['predictions_atol'],
                'gradient_atol': numeric['gradient_atol'], 'gradient_rtol': numeric['gradient_rtol'],
                'update_atol': numeric['parameter_atol'], 'update_rtol': numeric['parameter_rtol'],
            }
            if (report.get('passed') is not True or report.get('world_size') != 4 or
                    report.get('weights_restored') is not True or report.get('rng_restored') is not True or
                    report.get('optimizer_updates') != 0 or report.get('tolerances') != rank_tolerances or
                    report.get('deterministic') is not True or
                    report.get('cublas_workspace_config') != BACKEND['cublas_workspace_config']):
                raise ValueError('a rank failed its original numerical/restoration gate')
            ranks.append(report['rank'])
    if sorted(ranks) != [0, 1, 2, 3]:
        raise ValueError('independent proof must include exactly four rank reports')
    diagnostic_resources = receipt.get('diagnostic_resources', [])
    if len(diagnostic_resources) < 3 or len({item['path'] for item in diagnostic_resources}) != len(diagnostic_resources):
        raise ValueError('all independent diagnostic reservation receipts are required')
    for reference in diagnostic_resources:
        resource = read(verified_reference(directory, reference))
        if (resource['original_start'] != clock['started_at'] or
                resource['absolute_deadline'] != clock['deadline_at'] or
                resource['gpu_uuids'] != [item['uuid'] for item in read(directory / 'resource.json')['gpus']]):
            raise ValueError('diagnostic resource receipt changed original clock or GPU identities')
        import math
        intervals = resource.get('results', [resource])
        for item in intervals:
            start, seconds = item['started'], item['seconds']
            if (not math.isfinite(start) or not math.isfinite(seconds) or seconds < 0 or
                    start < clock['started_at'] or start + seconds > clock['deadline_at']):
                raise ValueError('diagnostic resource interval violates the original budget')
    return receipt


def identity(directory):
    path = Path(directory) / 'recovery.json'
    return sha(path) if path.exists() else None


def checkpoint_compatible(directory, pointer, payload):
    """Only the committed original step0 may cross the one-time source boundary."""
    path = Path(directory) / 'recovery.json'
    current = identity(directory)
    recorded = payload.get('recovery_sha256')
    if current is not None:
        validate(directory)
    if recorded == current:
        return
    if recorded is not None or current is None:
        raise ValueError('checkpoint recovery provenance differs')
    receipt = validate(directory)
    bootstrap = receipt['bootstrap_checkpoint']
    if (pointer['sha256'] != bootstrap['sha256'] or
            Path(pointer['path']).resolve() != confined(directory, bootstrap['path']) or
            payload['state'].get('phase') != 'preflight' or
            (payload['state'].get('trainer') or {}).get('global_updates', 0) != 0 or
            payload['manifest_sha256'] != receipt['original_manifest_sha256']):
        raise ValueError('only the exact original preflight checkpoint may enter recovery')


def evidence_paths(directory, receipt):
    """All old and new evidence is included in the final artifact manifest."""
    directory = Path(directory)
    result = [directory / 'recovery.json']
    for field in ('cpu', 'proof', 'bootstrap_checkpoint'):
        result.append(verified_reference(directory, receipt[field]))
    proof = read(result[2])
    result.extend(verified_reference(directory, item) for item in proof['independent_reports'])
    result.extend(verified_reference(directory, item) for item in receipt.get('diagnostic_resources', []))
    root = confined(directory, receipt['source_root'])
    result.extend(root / name for name in receipt['source'])
    cpu = read(verified_reference(directory, receipt['cpu']))
    for test in cpu['tests']:
        if 'log' in test:
            path = Path(test['log']).resolve()
            if not path.is_relative_to(directory.resolve()) or sha(path) != test['sha256']:
                raise ValueError('recovery CPU test log changed or escaped experiment')
            result.append(path)
    return sorted(set(result))


def resource_accounting(directory):
    """Recorded worker reservations are separate from elapsed-budget upper bounds."""
    directory = Path(directory)
    path = directory / 'recovery.json'
    if not path.exists():
        return dict(diagnostic_gpu_hours=0.0, diagnostic_resources=[])
    receipt = read(path)
    total, details = 0.0, []
    for reference in receipt.get('diagnostic_resources', []):
        value = read(verified_reference(directory, reference))
        intervals = value.get('results', [value])
        seconds = sum(float(item['seconds']) for item in intervals)
        hours = len(value['gpu_uuids']) * seconds / 3600
        total += hours
        details.append(dict(reference=reference, seconds=seconds, gpu_hours=hours))
    return dict(diagnostic_gpu_hours=total, diagnostic_resources=details)
