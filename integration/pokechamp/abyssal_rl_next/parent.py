"""EX-074 global82 출처와 optimizer/RNG를 CPU 검사 후 명시적으로 계승한다."""
from pathlib import Path

from .config import PARENT, PARENT_CHECKPOINT, PARENT_SNAPSHOT, PARENT_ROUND, PARENT_UPDATES, PARENT_LOCAL_ROUND, PARENT_LOCAL_UPDATES
from .storage import read, sha


def _source(path):
    return {'path': str(Path(path).resolve()), 'sha256': sha(path)}


def validate_payload(payload, snapshot, manifest_sha256, recovery_sha256):
    """Pure CPU validation, without initializing CUDA or a model."""
    import torch
    from .execution import weights_digest, buffer_digest
    state = payload['state']
    trainer = state['trainer']
    if (state['round'] != PARENT_LOCAL_ROUND or state['last_completed_round'] != PARENT_LOCAL_ROUND
            or state['active_model'] != 'round-25' or state['phase'] != 'train'
            or state['previous_rounds'] + state['last_completed_round'] != PARENT_ROUND
            or state['previous_updates'] + trainer['global_updates'] != PARENT_UPDATES
            or trainer['stage'] != 'policy' or not trainer['complete']
            or trainer['global_updates'] != PARENT_LOCAL_UPDATES):
        raise ValueError('parent must be completed global82 policy state, before selection/calibration')
    if (payload['manifest_sha256'] != manifest_sha256
            or payload['recovery_sha256'] != recovery_sha256):
        raise ValueError('parent manifest/recovery provenance differs')
    weights = payload['weights']
    if (set(weights) != set(snapshot['weights']) or len(weights) != 504
            or any(not torch.equal(value, snapshot['weights'][name]) for name, value in weights.items())
            or weights_digest(weights) != payload['weights_sha256']):
        raise ValueError('parent weights do not exactly match global82 snapshot')
    if buffer_digest(payload['frozen_buffer']) != payload['buffer_sha256']:
        raise ValueError('parent buffer provenance changed')
    optimizer = payload['optimizer']
    ids = [identity for group in optimizer['param_groups'] for identity in group['params']]
    if len(ids) != 504 or len(set(ids)) != 504 or set(ids) != set(optimizer['state']):
        raise ValueError('parent optimizer must contain all 504 states')
    for group in optimizer['param_groups']:
        if (group['lr'] != 1e-5 or tuple(group['betas']) != (0.9, 0.999)
                or group['weight_decay'] != 0.01 or group['eps'] != 1e-8):
            raise ValueError('parent optimizer settings differ')
    for saved in optimizer['state'].values():
        if set(saved) != {'step', 'exp_avg', 'exp_avg_sq'} or saved['step'].item() != PARENT_UPDATES:
            raise ValueError('parent optimizer step/state differs')
        if any(not torch.isfinite(value).all().item() for value in saved.values()):
            raise ValueError('nonfinite parent optimizer state')
    ranks = payload['ranks']
    if len(ranks) != 4 or [row['rank'] for row in ranks] != list(range(4)):
        raise ValueError('parent needs four ordered rank RNG states')
    for row in ranks:
        if (row['state'] != state or row['weights_sha256'] != payload['weights_sha256']
                or row['buffer_sha256'] != payload['buffer_sha256']
                or set(row['rng']) != {'python', 'numpy', 'torch', 'cuda'}
                or row['rng']['cuda'] is None or not row.get('sampling_rng')):
            raise ValueError('parent rank state or RNG provenance differs')
    return dict(passed=True, weights_sha256=payload['weights_sha256'], weight_tensors=504,
                optimizer_states=504, ranks=4, prior_round=PARENT_ROUND,
                prior_updates=PARENT_UPDATES, prior_buffer_reused=False,
                snapshot_exact_match=True, gpu_operations=0)


def parent_provenance():
    manifest = read(PARENT / 'manifest.json')
    pointer = read(PARENT / 'training-parent-ready.json')
    completed = read(PARENT / 'completed.json')
    result = read(completed['result_path'])
    if (manifest['experiment_id'] != 'EX-074' or result['experiment_id'] != 'EX-074'
            or not completed['experiment_complete'] or not completed['closed']
            or sha(completed['result_path']) != completed['result_sha256']):
        raise ValueError('unexpected or incomplete parent experiment provenance')
    if (pointer['local_round'] != PARENT_LOCAL_ROUND or pointer['historical_round'] != PARENT_ROUND
            or pointer['additional_updates'] != PARENT_LOCAL_UPDATES
            or pointer['previous_updates'] + pointer['additional_updates'] != PARENT_UPDATES):
        raise ValueError('parent training pointer identity differs')
    for key, path in (('checkpoint', PARENT_CHECKPOINT), ('snapshot', PARENT_SNAPSHOT)):
        source = pointer[key]
        if Path(source['path']).resolve() != path.resolve() or sha(path) != source['sha256']:
            raise ValueError('parent training pointer source differs: ' + key)
    if result['training_restart_checkpoint'] != pointer:
        raise ValueError('parent final report training checkpoint differs')
    return pointer, completed, result


def inspect_parent():
    import torch
    pointer, completed, result = parent_provenance()
    payload = torch.load(PARENT_CHECKPOINT, map_location='cpu', weights_only=False)
    snapshot = torch.load(PARENT_SNAPSHOT, map_location='cpu', weights_only=False)
    receipt = validate_payload(payload, snapshot, sha(PARENT / 'manifest.json'), None)
    ancestor = read(PARENT / 'prepared/parent.json')
    receipt.update(experiment='EX-075', parent_experiment='EX-074',
        checkpoint=_source(PARENT_CHECKPOINT), snapshot=_source(PARENT_SNAPSHOT),
        manifest=_source(PARENT / 'manifest.json'), recovery=None,
        training_pointer=_source(PARENT / 'training-parent-ready.json'),
        completed=_source(PARENT / 'completed.json'), result=_source(completed['result_path']),
        parent_local_round=PARENT_LOCAL_ROUND, parent_local_updates=PARENT_LOCAL_UPDATES,
        parent_clock=payload['clock'], prior_resource_report=_source(PARENT / 'final/report.md'),
        prior_worker_gpu_hours=result['operations']['recorded_production_gpu_hours'],
        prior_diagnostic_gpu_hours=result['operations']['diagnostic_gpu_hours'],
        prior_total_gpu_hours=result['operations']['recorded_reserved_gpu_hours'],
        ancestor_resources=[dict(experiment='EX-073', gpu_hours=ancestor['prior_total_gpu_hours'],
                                 resource_report=ancestor['prior_resource_report'])])
    return receipt


def verify_receipt(receipt):
    if (receipt['experiment'] != 'EX-075' or receipt['parent_experiment'] != 'EX-074'
            or Path(receipt['checkpoint']['path']).resolve() != PARENT_CHECKPOINT.resolve()
            or Path(receipt['snapshot']['path']).resolve() != PARENT_SNAPSHOT.resolve()
            or receipt['prior_updates'] != PARENT_UPDATES or receipt['prior_round'] != PARENT_ROUND
            or receipt['recovery'] is not None):
        raise ValueError('parent receipt identity differs')
    for key in ('checkpoint', 'snapshot', 'manifest', 'training_pointer', 'completed', 'result', 'prior_resource_report'):
        source = receipt[key]
        if sha(source['path']) != source['sha256']:
            raise ValueError('parent source changed: ' + key)
    return receipt


def restore_parent(policy, optimizer, rank, directory):
    """Only a fresh EX-075 import; EX-075 resume must use its own checkpoint."""
    import torch
    from .trainer import restore_rng, rng_state, _validate_optimizer
    from .execution import weights_digest
    if rank not in range(4):
        raise ValueError('unexpected rank')
    receipt = verify_receipt(read(Path(directory) / 'prepared/parent.json'))
    payload = torch.load(receipt['checkpoint']['path'], map_location='cpu', weights_only=False)
    snapshot = torch.load(receipt['snapshot']['path'], map_location='cpu', weights_only=False)
    validate_payload(payload, snapshot, receipt['manifest']['sha256'], None)
    policy.set_stage('policy')
    policy.load_weights(payload['weights'])
    optimizer.load_state_dict(payload['optimizer'])
    _validate_optimizer(policy, optimizer)
    optimizer.zero_grad(set_to_none=True)
    if weights_digest(policy.snapshot_weights()) != receipt['weights_sha256']:
        raise ValueError('parent restored weights differ')
    restore_rng(payload['ranks'][rank]['rng'])
    policy.sampling_generator.setstate(payload['ranks'][rank]['sampling_rng'])
    if (not state_equal(optimizer.state_dict(), payload['optimizer'])
            or not state_equal(rng_state(), payload['ranks'][rank]['rng'])
            or not state_equal(policy.sampling_generator.getstate(), payload['ranks'][rank]['sampling_rng'])):
        raise ValueError('parent optimizer or rank RNG restoration differs')
    return dict(receipt, passed=True, restored_rank=rank, fresh_buffer=True, additional_updates=0)


def state_equal(left, right):
    """Compare optimizer/RNG nested state exactly across CPU/CUDA placement."""
    import numpy as np
    import torch
    if isinstance(left, torch.Tensor):
        return (isinstance(right, torch.Tensor) and left.dtype == right.dtype
                and left.shape == right.shape and torch.equal(left.detach().cpu(), right.detach().cpu()))
    if isinstance(left, np.ndarray):
        return isinstance(right, np.ndarray) and left.dtype == right.dtype and np.array_equal(left, right)
    if isinstance(left, dict):
        return (isinstance(right, dict) and left.keys() == right.keys()
                and all(state_equal(value, right[key]) for key, value in left.items()))
    if isinstance(left, (list, tuple)):
        return (type(left) is type(right) and len(left) == len(right)
                and all(state_equal(a, b) for a, b in zip(left, right, strict=True)))
    return type(left) is type(right) and left == right
