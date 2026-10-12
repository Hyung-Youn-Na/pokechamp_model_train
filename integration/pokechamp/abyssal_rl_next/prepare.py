"""CPU-only EX-075 inherited teams, fresh test and continuation schedule freeze.

The complete raw replay inventory is an exclusion source, including replays that
were ineligible for imitation. No replay outcome is used to choose new teams or
BC samples. This module imports no model, tokenizer or GPU runtime.
"""
from __future__ import annotations

from collections import Counter
import heapq
import json
from pathlib import Path

from ..imitation.dataset import TeamValidatorClient, existing_teams, read_replay, signature
from ..imitation.schema import ImitationInput
from ..imitation.storage import atomic, digest, jsonl, read, sha, write_jsonl


ROOT = Path(__file__).resolve().parents[3]
SEED = 20261006
OUTPUT = ROOT / '.pokechamp-data/experiments/ex075-abyssal-rl-next'
EX071 = ROOT / '.pokechamp-data/experiments/ex071-qwen-replay-imitation'
REGISTRY = ROOT / 'export/teams/gen9ou_reviewed108_teams.json'
REPLAY_MANIFEST = ROOT / 'exports/replay-eligibility/gen9ou-local-v1/manifest.json'
SPLIT_COUNTS = {'train': 256, 'dev': 32, 'test': 128}
EVALUATION_OPPONENTS = ('abyssal',)
MAX_BC_SAMPLES = 768 * 4


def ranked(namespace, identity):
    return digest([SEED, namespace, identity])


def _source(path, expected=None):
    path = Path(path)
    actual = sha(path)
    if expected is not None and actual != expected:
        raise ValueError('source changed: ' + str(path))
    return {'path': str(path.resolve()), 'sha256': actual}


def replay_compositions(manifest_path=REPLAY_MANIFEST, root=ROOT):
    """Audit every original raw file and extract all complete preview families."""
    root = Path(root)
    manifest = read(manifest_path)
    expected = manifest['raw_file_sha256']
    inventory = {str(p.relative_to(root)) for p in (root / 'data/showdown-replays/raw').rglob('*')
                 if p.is_file()}
    if inventory != set(expected):
        raise ValueError('original raw replay inventory differs from its frozen manifest')
    rows = []
    for relative in sorted(expected):
        path = root / relative
        source = _source(path, expected[relative])
        replay = read_replay(path)
        if not isinstance(replay.get('log'), str):
            raise ValueError('replay has no public log: ' + relative)
        teams = {'p1': [], 'p2': []}
        for line in replay['log'].splitlines():
            fields = line.split('|')
            if len(fields) > 3 and fields[1] == 'poke' and fields[2] in teams:
                teams[fields[2]].append(fields[3].split(',')[0])
            if len(fields) > 1 and fields[1] == 'start':
                break
        compositions, incomplete = {}, {}
        for side, species in teams.items():
            try:
                compositions[side] = signature(species)
            except ValueError:
                # A non-six preview cannot be identical to a selected legal OU
                # six-species composition; preserve this evidence explicitly.
                incomplete[side] = species
        rows.append({'replay_id': replay.get('id'), 'source': source,
                     'signatures': compositions, 'non_six_distinct_previews': incomplete})
    return rows


def historical_compositions(ex071=EX071):
    """Read legacy reserved teams and the later EX-071 evaluation teams."""
    ex071 = Path(ex071)
    rows = existing_teams()
    historical_path = ex071 / 'preparation/historical-teams.json'
    inputs = read(ex071 / 'preparation/inputs.json')
    _source(historical_path, inputs['files']['preparation/historical-teams.json'])
    if rows != read(historical_path):
        raise ValueError('historical evaluation team sources changed since EX-071')
    source = _source(ex071 / 'schedule.json')
    prepared = read(ex071 / 'prepared/manifest.json')
    if source['sha256'] != prepared['schedule_sha256']:
        raise ValueError('EX-071 frozen evaluation schedule changed')
    seen = set()
    for slot in read(source['path']):
        for team in slot['teams'].values():
            sig = signature(team['species'])
            if team['signature'] != sig:
                raise ValueError('historical team composition mismatch')
            if sig not in seen:
                seen.add(sig)
                rows.append({'source': dict(source, role='ex071_evaluation_team'),
                             'species': team['species'], 'signature': sig})
    return rows


def choose_teams(registry, excluded, normalize, *, count=416):
    """Pick at most one legal set variant per composition in seeded hash order."""
    chosen, rejected, selected_signatures = [], [], set()
    reviewed = set(registry['reviewed_species_ids'])
    aliases = {}
    for entry in registry['teams']:
        aliases.setdefault(signature(entry['species']), []).append(entry['path'])
    for entry in sorted(registry['teams'], key=lambda row: (ranked('team_order', row['path']), row['path'])):
        sig = signature(entry['species'])
        if sig in excluded or sig in selected_signatures:
            continue
        path = Path(registry['default_team_root']) / entry['path']
        source = _source(path, entry['sha256'])
        # The unmodified pinned validator supplies a deterministic gender when
        # missing. Its entropy input here is explicitly derived from EX-073's seed.
        normalization_seed = ranked('team_normalization', source['sha256'])
        values = normalize([{'text': path.read_text(), 'sha256': normalization_seed}])
        if len(values) != 1:
            raise ValueError('team validator lost an entry')
        team = values[0]
        if not team.get('legal'):
            rejected.append({'source': source, 'signature': sig, 'reason': 'illegal_team', 'validation': team})
            continue
        actual = signature(team['species'])
        if set(actual.split('|')) - reviewed:
            rejected.append({'source': source, 'signature': sig,
                             'reason': 'normalized_form_outside_reviewed108', 'validation': team})
            continue
        if actual != sig:
            raise ValueError('team normalization changed preview composition: ' + str(path))
        chosen.append(dict(team, signature=sig, team_id='team-' + digest(sig)[:16],
                           source=source['path'], source_sha256=source['sha256'],
                           normalization_seed_sha256=normalization_seed,
                           registry_variants=sorted(aliases[sig])))
        selected_signatures.add(sig)
        if len(chosen) == count:
            break
    if len(chosen) != count:
        raise ValueError(f'need {count} new legal compositions; only {len(chosen)} passed')
    return chosen, rejected


def split_teams(teams):
    if len(teams) != sum(SPLIT_COUNTS.values()):
        raise ValueError('exactly 416 new legal teams are required')
    signatures = [team['signature'] for team in teams]
    if len(set(signatures)) != len(signatures):
        raise ValueError('duplicate team composition cannot cross splits')
    ordered = sorted(teams, key=lambda row: (ranked('team_split', row['signature']), row['signature']))
    start, result = 0, {}
    for name, count in SPLIT_COUNTS.items():
        result[name] = [dict(team, split=name) for team in ordered[start:start + count]]
        start += count
    return result


def _seeds(identity):
    raw = bytes.fromhex(ranked('battle_rng', identity))
    return {'simulator_seed': [int.from_bytes(raw[i:i + 2], 'big') for i in range(0, 8, 2)],
            'model_seed': int.from_bytes(raw[8:12], 'big'),
            'opponent_seed': int.from_bytes(raw[12:16], 'big')}


def _slot(stage, model, round_index, pair, side, opponent, teams, rng_identity,
          opponent_snapshot_index=None):
    learner, other = teams
    pair_id = f'{stage}-pair{pair + 1:02d}'
    slot_id = f'ex075-{stage}-{model}-r{round_index}-pair{pair + 1:02d}-{side}-{opponent}'
    side_teams = {'p1': learner, 'p2': other} if side == 'p1' else {'p1': other, 'p2': learner}
    seeds = _seeds(rng_identity)
    return dict(slot_id=slot_id, stage=stage, model=model, round=round_index,
                pair_id=pair_id, model_side=side, learner_side=side,
                opponent=opponent, opponent_kind=opponent,
                opponent_snapshot_index=opponent_snapshot_index, teams=side_teams,
                learner_team=learner, opponent_team=other,
                sampling_seed=seeds['model_seed'], **seeds)


def make_schedule(teams):
    """모든 후보 dev를 사전 예약하며 실제 시도는 최대34회로 제한한다."""
    if {name: len(rows) for name, rows in teams.items()} != SPLIT_COUNTS:
        raise ValueError('invalid train/dev/test team counts')
    signatures = [row['signature'] for rows in teams.values() for row in rows]
    if len(set(signatures)) != 416:
        raise ValueError('team composition overlap between splits')
    schedule = []
    for r in range(1, 129):
        global_round = r + 82
        block, offset = (global_round - 1) // 4, ((global_round - 1) % 4) * 64
        train = sorted(teams['train'], key=lambda row: digest([20261003, 'train_block', [block, row['signature']]]))
        for i in range(64):
            index = offset + i
            row = _slot('train', 'initial' if r == 1 else f'round-{r-1}', r, i,
                        'p1' if i % 2 == 0 else 'p2', 'abyssal',
                        [train[index], train[(index + 128) % 256]], ['train', r, i])
            schedule.append(dict(row, assignment=0, global_round=global_round))
    def evaluation(stage, model, r, split, pairs):
        for pair in range(pairs):
            for assignment in (0, 1):
                pair_teams = teams[split][2*pair:2*pair+2]
                if assignment:
                    pair_teams = list(reversed(pair_teams))
                for side in ('p1', 'p2'):
                    row = _slot(stage, model, r, pair, side, 'abyssal', pair_teams,
                                [stage, pair, assignment, side])
                    row['slot_id'] += f'-a{assignment}'
                    schedule.append(dict(row, assignment=assignment))
    for candidate in range(129):
        evaluation('dev', 'initial' if candidate == 0 else f'round-{candidate}', candidate, 'dev', 16)
    evaluation('calibration', 'selected', 0, 'train', 16)
    evaluation('calibration_dev', 'selected', 0, 'dev', 6)
    for model in ('initial', 'selected'):
        evaluation('test', model, 0, 'test', 64)
    if len(schedule) != 17048 or len({row['slot_id'] for row in schedule}) != len(schedule):
        raise AssertionError('schedule denominator or identity changed')
    return schedule


def choose_bc(rows, assignments, *, limit=MAX_BC_SAMPLES):
    """Outcome-independent bounded sample of original EX-071 train rows only."""
    heap, seen = [], set()
    for count, row in enumerate(rows, 1):
        identity = row['sample_id']
        if identity in seen:
            raise ValueError('duplicate EX-071 train sample')
        seen.add(identity)
        assignment = assignments.get(row['replay_id'])
        if (row.get('split') != 'train' or not row.get('eligible') or assignment is None
                or assignment.get('split') != 'train' or assignment.get('group_id') != row.get('group_id')):
            raise ValueError('BC source is not exclusively eligible EX-071 train data')
        criteria = row['input']['questions']['action']['criteria']
        if len(criteria) < 2 or row.get('label') not in criteria:
            raise ValueError('BC target/candidate binding failed')
        rank = int(ranked('bc_samples', identity), 16)
        item = (-rank, identity, row)
        if len(heap) < limit:
            heapq.heappush(heap, item)
        elif item[:2] > heap[0][:2]:
            heapq.heapreplace(heap, item)
    if not seen:
        raise ValueError('EX-071 train set is empty')
    if len(heap) != limit:
        raise ValueError(f'need {limit} BC rows; only {len(heap)} eligible train rows')
    selected = [item[2] for item in sorted(heap, key=lambda item: (-item[0], item[1]))]
    for row in selected:
        value = ImitationInput.from_body(row['input'])
        if tuple(row['input']['questions']['action']['criteria']) != value.action_ids:
            raise ValueError('BC candidate order changed')
    return selected, len(seen)


EX072 = ROOT / '.pokechamp-data/experiments/ex072-selfplay-rlcd'


def freeze_bc(prepared, ex071=EX071, ex072=EX072):
    """EX-072의 동결 BC3072를 바이트 그대로 재사용한다."""
    import shutil
    source_dir = Path(ex072) / 'prepared'
    manifest = read(source_dir / 'manifest.json')
    path = source_dir / 'bc.jsonl'
    source = _source(path, manifest['files']['bc.jsonl'])
    receipt_path = source_dir / 'bc-manifest.json'
    _source(receipt_path, manifest['files']['bc-manifest.json'])
    original = read(receipt_path)
    rows = list(jsonl(path))
    groups_path = Path(ex071) / 'preparation/groups.json'
    groups = read(groups_path)
    _source(groups_path, original['groups']['sha256'])
    # Validation only: never reselect under EX-073's seed.
    choose_bc(rows, groups['assignment'], limit=3072)
    ids = [row['sample_id'] for row in rows]
    if ids != original['sample_ids'] or digest(ids) != original['sample_ids_sha256']:
        raise ValueError('EX-072 BC sample identity changed')
    destination = Path(prepared) / 'bc.jsonl'
    if destination.exists():
        raise FileExistsError(destination)
    shutil.copyfile(path, destination)
    receipt = dict(original, source=source, source_manifest=_source(source_dir / 'manifest.json'),
                   reused_receipt=_source(receipt_path), selection='exact_ex072_frozen_bc_bytes',
                   output_sha256=sha(destination))
    if receipt['output_sha256'] != source['sha256']:
        raise ValueError('BC copy differs')
    atomic(Path(prepared) / 'bc-manifest.json', receipt, immutable=True)
    return receipt


def verify(directory=OUTPUT, *, check_sources=True):
    from .config import PARENT
    prepared = Path(directory) / 'prepared'
    manifest = read(prepared / 'manifest.json')
    if manifest['seed'] != SEED or manifest['experiment'] != 'EX-075':
        raise ValueError('prepared experiment identity differs')
    for name, expected in manifest['files'].items():
        _source(prepared / name, expected)
    if check_sources:
        for path, expected in manifest['source_files'].items():
            _source(path, expected)
    teams = read(prepared / 'teams.json')
    if make_schedule(teams) != read(prepared / 'schedule.json'):
        raise ValueError('frozen schedule is not reproducible')
    parent_teams = read(PARENT / 'prepared/teams.json')
    if any(teams[name] != parent_teams[name] for name in ('train', 'dev')):
        raise ValueError('inherited train/dev teams changed')
    excluded = set(read(prepared / 'exclusions.json')['signatures'])
    if any(team['signature'] in excluded for team in teams['test']):
        raise ValueError('new test composition overlaps prior data')
    if sha(prepared / 'bc.jsonl') != sha(PARENT / 'prepared/bc.jsonl'):
        raise ValueError('inherited BC bytes changed')
    from .parent import verify_receipt
    verify_receipt(read(prepared / 'parent.json'))
    return manifest


def prepare(directory=OUTPUT):
    """CPU-only inherited training freeze and independently held-out test128."""
    import shutil
    from .config import PARENT, PROTOCOL
    from .parent import inspect_parent
    prepared = Path(directory) / 'prepared'
    if (prepared / 'manifest.json').exists():
        return verify(directory)
    prepared.mkdir(parents=True, exist_ok=True)
    if any(prepared.iterdir()):
        raise FileExistsError('partial preparation exists; preserve and diagnose before a new attempt')
    from ..abyssal_rl_continue.prepare import verify as verify_original
    original = verify_original(PARENT)
    previous = read(PARENT / 'prepared/teams.json')
    original_exclusions = read(PARENT / 'prepared/exclusions.json')
    excluded = set(original_exclusions['signatures'])
    excluded.update(team['signature'] for rows in previous.values() for team in rows)
    registry = read(REGISTRY)
    with TeamValidatorClient() as validator:
        chosen, rejected = choose_teams(registry, excluded, validator.normalize, count=128)
    teams = {name: previous[name] for name in ('train', 'dev')}
    teams['test'] = [dict(row, split='test') for row in sorted(chosen,
        key=lambda row: (ranked('team_split', row['signature']), row['signature']))]
    parent = inspect_parent()
    schedule = make_schedule(teams)
    atomic(prepared / 'parent.json', parent, immutable=True)
    atomic(prepared / 'teams.json', teams, immutable=True)
    atomic(prepared / 'schedule.json', schedule, immutable=True)
    atomic(prepared / 'team-rejections.json', rejected, immutable=True)
    atomic(prepared / 'exclusions.json', dict(signatures=sorted(excluded),
        selection_scope='test_only', parent_exclusions_sha256=sha(PARENT / 'prepared/exclusions.json'),
        parent_all_splits_sha256=sha(PARENT / 'prepared/teams.json')), immutable=True)
    shutil.copyfile(PARENT / 'prepared/bc.jsonl', prepared / 'bc.jsonl')
    bc = read(PARENT / 'prepared/bc-manifest.json')
    atomic(prepared / 'bc-manifest.json', dict(bc,
        inherited_ex074_sha256=sha(PARENT / 'prepared/bc.jsonl')), immutable=True)
    sources = dict(original['source_files'])
    for path in [REGISTRY, PARENT / 'prepared/manifest.json',
                 *[PARENT / 'prepared' / name for name in original['files']],
                 *[Path(parent[key]['path']) for key in ('checkpoint', 'snapshot', 'manifest', 'training_pointer', 'completed', 'result')]]:
        sources[str(path.resolve())] = sha(path)
    for team in chosen:
        sources[team['source']] = team['source_sha256']
    files = sorted(path.name for path in prepared.iterdir() if path.is_file())
    manifest = dict(experiment='EX-075', version='ex075-prepared-v1', seed=SEED,
        protocol=PROTOCOL, parent=parent,
        team_counts={name: len(rows) for name, rows in teams.items()}, unique_compositions=416,
        inherited_train_dev=True, new_test_compositions=128,
        schedule_counts=dict(Counter(row['stage'] for row in schedule)), slots=len(schedule),
        bc_samples=3072, excluded_compositions=len(excluded),
        registry_entries=len(registry['teams']), rejected_team_candidates=len(rejected),
        dev_reserved_candidates=129, max_dev_evaluations=34,
        source_files=sources, files={name: sha(prepared / name) for name in files},
        prepare_source_sha256=sha(__file__), gpu_operations=0)
    atomic(prepared / 'manifest.json', manifest, immutable=True)
    return verify(directory)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=OUTPUT)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = verify(args.directory) if args.verify else prepare(args.directory)
    print(json.dumps({key: result[key] for key in ('experiment', 'team_counts', 'schedule_counts', 'slots', 'bc_samples')}, ensure_ascii=False))
