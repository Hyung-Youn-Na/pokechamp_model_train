"""CPU-only EX-079 admission preserving the complete sealed EX-078 round one."""
import io
import math
from pathlib import Path
import shutil

from . import artifacts, first_round
from .config import ROOT
from .day import _check, _seal
from .finalize import audit_game
from .first_round_recovery import _same
from .prepare import prepare
from .storage import atomic, atomic_bytes, digest, read, sha

PARENT_IDENTITY = '22d0be412e4d4f1532009cc6391e7f905ba62eda25c0f1b3cf30be34ed99eb38'
PARENT_DIRECTORY = ROOT / '.pokechamp-data/experiments/ex078-fixed-matchup-first-round-untimed'
CRITICAL_SOURCES = tuple('integration/pokechamp/fixed_matchup/' + n for n in
    ('config.py', 'model.py', 'search.py', 'battle.py', 'actor_rpc.py', 'simulator.py',
     'simulator.cjs', 'observation.cjs', 'public_state.cjs'))


def _finite(value):
    import torch
    if torch.is_tensor(value):
        return bool(torch.isfinite(value).all())
    if isinstance(value, dict):
        return all(_finite(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return all(_finite(v) for v in value)
    return not isinstance(value, float) or math.isfinite(value)


def prepare_stopping(parent, directory):
    """Require sealed normal32/update44 state before creating the separate run."""
    import torch
    from . import stopping
    parent, directory = Path(parent).resolve(), Path(directory).resolve()
    if parent != PARENT_DIRECTORY.resolve():
        raise ValueError('only the approved EX-078 parent directory may be inherited')
    if parent == directory or directory.is_relative_to(parent) or parent.is_relative_to(directory):
        raise ValueError('continuation requires a separate directory')
    if directory.exists():
        raise FileExistsError('continuation requires a new directory')
    manifest = read(parent / 'manifest.json')
    if (manifest['identity'] != PARENT_IDENTITY
            or digest({k: v for k, v in manifest.items() if k != 'identity'}) != PARENT_IDENTITY
            or manifest['protocol'] != first_round.PROTOCOL):
        raise ValueError('unapproved parent identity/protocol')
    for name, checksum in manifest['sources'].items():
        _check(parent, 'source/' + name, checksum)
    for name, checksum in manifest['files'].items():
        _check(parent, name, checksum)
    for team in manifest['teams'].values():
        _check(parent, 'teams/' + team['file'], team['sha256'])
    for name in CRITICAL_SOURCES:
        if name not in manifest['sources'] or sha(ROOT / name) != manifest['sources'][name]:
            raise ValueError('numerical implementation changed: ' + name)
    for name, checksum in manifest['sources'].items():
        if name.startswith(('pokemon-showdown/', 'pokechamp/poke_env/')) and sha(ROOT / name) != checksum:
            raise ValueError('simulator/opponent implementation changed: ' + name)
    sealed, closure = _seal(parent, 'evidence.sha256'), _seal(parent, 'closure.sha256')
    if any(n in sealed and sealed[n] != v for n, v in closure.items()):
        raise ValueError('parent seals disagree')
    sealed.update(closure)
    required = {'manifest.json', 'completed.json', 'checkpoint-validation.json', 'clock.json',
        'catalog.json', 'schedule.json', 'settings.json', 'latest.json', 'models/P0.pt',
        'models/P0.identity.json', 'models/round-001.pt', 'training/round-001.json'}
    completed, validation = read(parent / 'completed.json'), read(parent / 'checkpoint-validation.json')
    if (completed.get('identity') != PARENT_IDENTITY or not completed.get('procedure_complete')
            or not completed.get('diagnostic_complete') or not completed.get('audit', {}).get('passed')
            or completed['audit'].get('normal_games') != 32 or completed['audit'].get('games') != 32
            or completed['audit'].get('decisions') != 5436 or (parent / 'incomplete.json').exists()
            or (parent / 'evaluation-lock.json').exists()):
        raise ValueError('parent must be the completed normal32 first round')
    if (read(parent / 'schedule.json') != first_round.schedule()
            or read(parent / 'settings.json') != first_round.SETTING):
        raise ValueError('parent schedule/settings changed')
    if (sorted(p.name for p in (parent / 'checkpoints').iterdir()) !=
            ['round-000.json', 'round-000.pt', 'round-001.json', 'round-001.pt']
            or sorted(p.name for p in (parent / 'models').glob('*.pt')) != ['P0.pt', 'round-001.pt']):
        raise ValueError('unexpected parent checkpoints/models')
    clock = read(parent / 'clock.json')
    if clock.get('total') is not None or not isinstance(clock.get('start'), (int, float)) or not _finite(clock):
        raise ValueError('parent original unlimited clock required')
    p0_hash, model_hash = sha(parent / 'models/P0.pt'), sha(parent / 'models/round-001.pt')
    if read(parent / 'models/P0.identity.json') != dict(identity=PARENT_IDENTITY, sha256=p0_hash):
        raise ValueError('parent P0 identity mismatch')
    p0 = torch.load(parent / 'models/P0.pt', map_location='cpu', weights_only=True)
    model = torch.load(parent / 'models/round-001.pt', map_location='cpu', weights_only=True)
    payloads, pointers = [], []
    for number in (0, 1):
        name = f'checkpoints/round-{number:03d}'
        pointer = dict(file=name + '.pt', round=number, sha256=sha(parent / (name + '.pt')))
        if read(parent / (name + '.json')) != pointer:
            raise ValueError('parent checkpoint pointer changed')
        payload = torch.load(parent / pointer['file'], map_location='cpu', weights_only=True)
        if (not {'generator', 'torch_rng', 'python_rng', 'cuda_rng', 'learning'} <= payload.keys()
                or payload['identity'] != PARENT_IDENTITY or payload['round'] != number
                or payload['clock'] != clock or not _finite(payload)
                or not _same(payload['model'], model if number else p0)):
            raise ValueError('parent complete checkpoint state invalid')
        if number == 0 and (payload['updates'] != 0 or payload['replay_ids'] or payload['optimizer']['state']):
            raise ValueError('parent checkpoint0 is not untrained')
        if number == 1 and (payload['updates'] != 44 or len(payload['optimizer']['state']) != 59
                or payload['learning']['steps'] != 44
                or read(parent / 'training/round-001.json') != payload['learning']):
            raise ValueError('parent round1 optimizer/update state invalid')
        required.update([name + '.pt', name + '.json'])
        pointers.append(pointer)
        payloads.append(payload)
    if read(parent / 'latest.json') != pointers[1]:
        raise ValueError('parent latest must be round1')
    if (len(model['weights']) != 59 or model['weights'].keys() != p0['weights'].keys()
            or sum(not torch.equal(v, p0['weights'][k]) for k, v in model['weights'].items()) != 59):
        raise ValueError('parent must have all59 changed trained tensors')
    jobs = first_round.schedule()['train'][0]
    slots = {j['slot_id'] for j in jobs}
    if ({p.name for p in (parent / 'games').iterdir()} != slots
            or {p.name for p in (parent / 'claims').iterdir()} != {s + '.json' for s in slots}):
        raise ValueError('parent must contain exactly32 game/claim slots')
    copied = []
    for job in jobs:
        base = parent / 'games' / job['slot_id']
        claim = 'claims/' + job['slot_id'] + '.json'
        row = artifacts.load_result(base)
        if (row['job'] != job or read(parent / claim)['job'] != job
                or row['status'] != 'completed' or row.get('model_hashes') != {'current': p0_hash}):
            raise ValueError('parent game/claim/model invalid: ' + job['slot_id'])
        audit_game(base)
        copied.extend([str(p.relative_to(parent)) for p in base.rglob('*') if p.is_file()] + [claim])
    replay_ids = [r['id'] for r in artifacts.replay_rows(parent, 1)]
    if len(replay_ids) != 5436 or len(set(replay_ids)) != 5436 or payloads[1]['replay_ids'] != replay_ids:
        raise ValueError('parent replay identity/order changed')
    expected_validation = dict(identity=PARENT_IDENTITY, passed=True, finite=True, round=1,
        updates=44, changed_tensors=59, optimizer_states=59, observations=5436,
        checkpoint=pointers[1], p0_sha256=p0_hash, model_sha256=model_hash,
        replay_ids_sha256=digest(replay_ids), learning=payloads[1]['learning'])
    if any(validation.get(k) != v for k, v in expected_validation.items()):
        raise ValueError('parent checkpoint validation mismatch')
    required.update(copied)
    if not required <= sealed.keys():
        raise ValueError('parent seal omitted required inheritance evidence')
    copied.extend(['models/P0.pt', 'models/round-001.pt', 'settings.json', 'clock.json', 'training/round-001.json'])
    if (parent / 'resource.json').exists():
        if 'resource.json' not in sealed or read(parent / 'resource.json').get('index') != 0:
            raise ValueError('parent resource must be the sealed physical GPU0')
        # Child selects its own idle GPU; parent resource provenance stays in its seal.
    current = prepare(directory, protocol=stopping.PROTOCOL, schedule=stopping.schedule())
    if current['teams'] != manifest['teams'] or sha(directory / 'catalog.json') != sha(parent / 'catalog.json'):
        raise ValueError('inherited teams/vocabulary changed')
    for name in copied:
        destination = directory / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(parent / name, destination)
        _check(directory, name, sealed[name])
    linkage = dict(approval='D-126', parent=str(parent), parent_identity=PARENT_IDENTITY,
        parent_manifest_sha256=sha(parent / 'manifest.json'), parent_sources=manifest['sources'],
        parent_files=manifest['files'], parent_evidence=sealed, parent_protocol=manifest['protocol'],
        parent_seals={n: sha(parent / n) for n in ('evidence.sha256', 'closure.sha256')},
        parent_checkpoint=pointers[1], parent_checkpoints=pointers, parent_clock=clock,
        inherited_games=sorted(slots), inherited_round=1, inherited_updates=44, inherited_decisions=5436,
        p0_sha256=p0_hash, model_sha256=model_hash, replay_ids_sha256=digest(replay_ids),
        retries=0, checkpoint_changes=['identity'], clock_policy='preserve_original_start_no_wallclock_limit',
        state_validation=expected_validation)
    atomic(directory / 'inheritance.json', linkage, exclusive=True)
    current.pop('identity')
    current['files'].update({n: sha(directory / n) for n in copied + ['inheritance.json']})
    current['inheritance'] = linkage
    current['identity'] = digest(current)
    atomic(directory / 'manifest.json', current)
    rebound_pointers = []
    for payload, pointer in zip(payloads, pointers):
        rebound = dict(payload, identity=current['identity'])
        stream = io.BytesIO()
        torch.save(rebound, stream)
        atomic_bytes(directory / pointer['file'], stream.getvalue(), exclusive=True)
        if not _same(torch.load(directory / pointer['file'], map_location='cpu', weights_only=True), rebound):
            raise ValueError('rebound checkpoint serialization changed state')
        new_pointer = dict(pointer, sha256=sha(directory / pointer['file']))
        atomic(directory / f"checkpoints/round-{pointer['round']:03d}.json", new_pointer, exclusive=True)
        rebound_pointers.append(new_pointer)
    atomic(directory / 'latest.json', rebound_pointers[1], exclusive=True)
    atomic(directory / 'models/P0.identity.json', dict(identity=current['identity'], sha256=p0_hash), exclusive=True)
    atomic(directory / 'checkpoint-inheritance.json', dict(parent=pointers, rebound=rebound_pointers,
        identity=current['identity'], preserved_all_other_state=True), exclusive=True)
    return current
