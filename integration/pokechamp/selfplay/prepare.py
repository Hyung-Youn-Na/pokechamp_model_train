"""CPU-only team, schedule and EX-071 train-data freeze for EX-072.

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
SEED = 20261002
OUTPUT = ROOT / '.pokechamp-data/experiments/ex072-selfplay-rlcd'
EX071 = ROOT / '.pokechamp-data/experiments/ex071-qwen-replay-imitation'
REGISTRY = ROOT / 'export/teams/gen9ou_reviewed108_teams.json'
REPLAY_MANIFEST = ROOT / 'exports/replay-eligibility/gen9ou-local-v1/manifest.json'
SPLIT_COUNTS = {'train': 64, 'dev': 8, 'test': 20}
EVALUATION_OPPONENTS = ('initial', 'abyssal', 'abyssal-tera-v1')
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


def choose_teams(registry, excluded, normalize, *, count=92):
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
        # missing. Its entropy input here is explicitly derived from EX-072's seed.
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
        raise ValueError('exactly 92 new legal teams are required')
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
    slot_id = f'{stage}-{model}-r{round_index}-pair{pair + 1:02d}-{side}-{opponent}'
    side_teams = {'p1': learner, 'p2': other} if side == 'p1' else {'p1': other, 'p2': learner}
    seeds = _seeds(rng_identity)
    return dict(slot_id=slot_id, stage=stage, model=model, round=round_index,
                pair_id=pair_id, model_side=side, learner_side=side,
                opponent=opponent, opponent_kind=opponent,
                opponent_snapshot_index=opponent_snapshot_index, teams=side_teams,
                learner_team=learner, opponent_team=other,
                sampling_seed=seeds['model_seed'], **seeds)


def make_schedule(teams):
    """Freeze all 584 possible slots, including model-independent test pairs."""
    if {name: len(rows) for name, rows in teams.items()} != SPLIT_COUNTS:
        raise ValueError('invalid train/dev/test team counts')
    all_signatures = [row['signature'] for rows in teams.values() for row in rows]
    if len(set(all_signatures)) != 92:
        raise ValueError('team composition overlap between splits')
    schedule = []
    for round_index in range(1, 5):
        train = sorted(teams['train'], key=lambda row: ranked('round_teams', [round_index, row['signature']]))
        opponents = ['current'] * 16 + ['snapshot'] * 8 + ['abyssal'] * 4 + ['abyssal-tera-v1'] * 4
        # The opponent category order and per-pair past model are frozen before
        # any update, and the two side-swapped games share their opponent model.
        opponents = [opponents[i] for i in sorted(range(32), key=lambda i: ranked('round_opponents', [round_index, i]))]
        model = 'initial' if round_index == 1 else f'round-{round_index - 1}'
        for pair, opponent in enumerate(opponents):
            snapshot = None
            if opponent == 'current':
                snapshot = round_index - 1
            elif opponent == 'snapshot':
                pool = list(range(max(1, round_index - 1)))
                # Rejection sampling avoids modulo bias even for a three-item pool.
                nonce = 0
                while True:
                    value = int(ranked('past_snapshot', [round_index, pair, nonce]), 16)
                    bound = (1 << 256) - (1 << 256) % len(pool)
                    if value < bound:
                        snapshot = pool[value % len(pool)]
                        break
                    nonce += 1
            for side in ('p1', 'p2'):
                schedule.append(_slot('train', model, round_index, pair, side, opponent,
                                      train[2 * pair:2 * pair + 2], ['train', round_index, pair, side], snapshot))

    for candidate in range(5):
        model = 'initial' if candidate == 0 else f'round-{candidate}'
        for pair in range(4):
            for side in ('p1', 'p2'):
                for opponent in EVALUATION_OPPONENTS:
                    schedule.append(_slot('dev', model, candidate, pair, side, opponent,
                        teams['dev'][2 * pair:2 * pair + 2], ['dev', pair, side, opponent],
                        0 if opponent == 'initial' else None))

    train = sorted(teams['train'], key=lambda row: ranked('calibration_teams', row['signature']))
    opponents = ['initial'] * 24 + ['abyssal'] * 4 + ['abyssal-tera-v1'] * 4
    opponents = [opponents[i] for i in sorted(range(32), key=lambda i: ranked('calibration_opponents', i))]
    for pair, opponent in enumerate(opponents):
        for side in ('p1', 'p2'):
            schedule.append(_slot('calibration', 'selected', 0, pair, side, opponent,
                                  train[2 * pair:2 * pair + 2], ['calibration', pair, side],
                                  0 if opponent == 'initial' else None))

    for stage, names, split in [('calibration_dev', ('selected',), 'dev'),
                                ('test', ('initial', 'selected'), 'test')]:
        for model in names:
            for pair in range(len(teams[split]) // 2):
                for side in ('p1', 'p2'):
                    for opponent in EVALUATION_OPPONENTS:
                        schedule.append(_slot(stage, model, 0, pair, side, opponent,
                            teams[split][2 * pair:2 * pair + 2], [stage, pair, side, opponent],
                            0 if opponent == 'initial' else None))
    if len(schedule) != 584 or len({row['slot_id'] for row in schedule}) != 584:
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


def freeze_bc(prepared, ex071=EX071):
    ex071, prepared = Path(ex071), Path(prepared)
    manifest_path = ex071 / 'prepared/manifest.json'
    manifest = read(manifest_path)
    groups_path = ex071 / 'preparation/groups.json'
    groups = read(groups_path)
    inputs_path = ex071 / 'preparation/inputs.json'
    inputs = read(inputs_path)
    if sha(inputs_path) != manifest['inputs_sha256']:
        raise ValueError('EX-071 preparation identity changed')
    _source(groups_path, inputs['files']['preparation/groups.json'])
    path = ex071 / 'prepared/train.jsonl'
    source = _source(path, manifest['files']['train.jsonl'])
    rows, count = choose_bc(jsonl(path), groups['assignment'])
    if count != manifest['counts']['selected_split']['train']:
        raise ValueError('EX-071 train count changed')
    _source(path, source['sha256'])
    write_jsonl(prepared / 'bc.jsonl', rows, immutable=True)
    receipt = dict(source=source, source_manifest=_source(manifest_path),
                   groups=_source(groups_path), source_inputs=_source(inputs_path),
                   source_split='train', source_samples=count, selected_samples=len(rows),
                   selection='lowest_sha256_seed_namespace_sample_id', seed=SEED,
                   sample_ids=[row['sample_id'] for row in rows],
                   sample_ids_sha256=digest([row['sample_id'] for row in rows]),
                   candidate_order_preserved=True, output_sha256=sha(prepared / 'bc.jsonl'))
    atomic(prepared / 'bc-manifest.json', receipt, immutable=True)
    return receipt


def verify(directory=OUTPUT, *, check_sources=True):
    prepared = Path(directory) / 'prepared'
    manifest = read(prepared / 'manifest.json')
    if manifest['seed'] != SEED or manifest['experiment'] != 'EX-072':
        raise ValueError('prepared experiment identity differs')
    for name, expected in manifest['files'].items():
        _source(prepared / name, expected)
    if check_sources:
        for path, expected in manifest['source_files'].items():
            _source(path, expected)
    teams, schedule = read(prepared / 'teams.json'), read(prepared / 'schedule.json')
    if make_schedule(teams) != schedule:
        raise ValueError('frozen schedule is not reproducible')
    exclusions = read(prepared / 'exclusions.json')
    if any(team['signature'] in exclusions['signatures'] for rows in teams.values() for team in rows):
        raise ValueError('new team leaked from a replay or historical evaluation')
    return manifest


def prepare(directory=OUTPUT):
    """Prepare once; a completed freeze is audited without rewriting artifacts."""
    prepared = Path(directory) / 'prepared'
    if (prepared / 'manifest.json').exists():
        return verify(directory)
    prepared.mkdir(parents=True, exist_ok=True)
    if any(prepared.iterdir()):
        raise FileExistsError('partial preparation exists; preserve and diagnose before a new attempt')
    registry = read(REGISTRY)
    replays = replay_compositions()
    historical = historical_compositions()
    replay_signatures = {sig for row in replays for sig in row['signatures'].values()}
    historical_signatures = {row['signature'] for row in historical}
    excluded = replay_signatures | historical_signatures
    with TeamValidatorClient() as validator:
        chosen, rejected = choose_teams(registry, excluded, validator.normalize)
    teams = split_teams(chosen)
    schedule = make_schedule(teams)
    write_jsonl(prepared / 'replay-compositions.jsonl', replays, immutable=True)
    atomic(prepared / 'historical-teams.json', historical, immutable=True)
    atomic(prepared / 'team-rejections.json', rejected, immutable=True)
    atomic(prepared / 'exclusions.json', dict(signatures=sorted(excluded),
        replay_compositions=len(replay_signatures), historical_compositions=len(historical_signatures),
        raw_replay_files=len(replays), non_six_distinct_previews=sum(len(row['non_six_distinct_previews']) for row in replays)),
        immutable=True)
    atomic(prepared / 'teams.json', teams, immutable=True)
    atomic(prepared / 'schedule.json', schedule, immutable=True)
    bc = freeze_bc(prepared)
    sources = [_source(REGISTRY), _source(REPLAY_MANIFEST), bc['source'], bc['source_manifest'],
               bc['groups'], bc['source_inputs'], _source(Path(__file__).parent.parent / 'imitation/teams.cjs')]
    sources.extend(row['source'] for row in replays)
    sources.extend(row['source'] for row in historical)
    sources.extend(_source(team['source'], team['source_sha256']) for team in chosen)
    sources.extend(row['source'] for row in rejected)
    files = sorted(path.name for path in prepared.iterdir() if path.is_file())
    manifest = dict(experiment='EX-072', version='ex072-prepared-v1', seed=SEED,
        team_counts={name: len(rows) for name, rows in teams.items()}, unique_compositions=len(chosen),
        schedule_counts=dict(Counter(row['stage'] for row in schedule)), slots=len(schedule),
        bc_samples=bc['selected_samples'], excluded_compositions=len(excluded),
        registry_entries=len(registry['teams']), rejected_team_candidates=len(rejected),
        contamination_interpretation='새 자기대국/팀 구성 holdout이며 기존 모방 학습 세트 통계 중복 가능',
        normalization='pinned imitation/teams.cjs, EX-072-seeded sha256 entropy input',
        previous_snapshot_pool='round r: initial and rounds 1..r-2; round 1 uses initial',
        source_files={row['path']: row['sha256'] for row in sources},
        files={name: sha(prepared / name) for name in files},
        prepare_source_sha256=sha(__file__))
    atomic(prepared / 'manifest.json', manifest, immutable=True)
    return verify(directory)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=OUTPUT)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = verify(args.directory) if args.verify else prepare(args.directory)
    print(json.dumps({key: result[key] for key in ('experiment', 'team_counts', 'schedule_counts', 'slots', 'bc_samples')},
                     ensure_ascii=False))
