"""CPU-only, replay/team-disjoint preparation and exhaustive data audit for EX-071."""
from __future__ import annotations
from collections import Counter, defaultdict, deque
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

from . import config as c
from .schema import ImitationInput, from_snapshot, permute
from .storage import atomic, canonical, digest, jsonl, read, sha, write_jsonl


def to_id(value):
    return re.sub('[^a-z0-9]', '', str(value).lower())


def signature(species):
    # Pinned sim/pokemon.ts getDetails deliberately hides the Bond forme.
    # This is the same preview composition, including the Greninja original set.
    values = sorted('greninja' if to_id(x)=='greninjabond' else to_id(x) for x in species)
    if len(values) != 6 or len(set(values)) != 6:
        raise ValueError('expected six distinct species')
    return '|'.join(values)


def ranked(namespace, identity):
    return digest([c.SEED, namespace, identity])


def normalize(entries):
    process = subprocess.run(['node', str(Path(__file__).with_name('teams.cjs'))],
                             input=json.dumps(entries), text=True, capture_output=True, check=True)
    results = json.loads(process.stdout)
    if len(results) != len(entries):
        raise ValueError('team validator lost entries')
    return results


class TeamValidatorClient:
    """Persistent CPU validator for all post-imputation team combinations."""
    def __init__(self):
        self.process = subprocess.Popen(['node',str(Path(__file__).with_name('teams.cjs')),'--jsonl'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)

    def normalize(self,entries):
        self.process.stdin.write(json.dumps(entries)+'\n');self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:
            raise RuntimeError('team validator exited: '+self.process.stderr.read()[-1000:])
        response=json.loads(line)
        if not response['ok'] or len(response['results'])!=len(entries):
            raise RuntimeError('team validator protocol failed: '+str(response.get('error')))
        return response['results']

    def __enter__(self):return self

    def __exit__(self,*args):
        self.process.stdin.close()
        try:self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate();self.process.wait(timeout=10)
        self.process.stdout.close();self.process.stderr.close()


def read_replay(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def preview(log):
    result = {'p1': [], 'p2': []}
    for line in log.splitlines():
        fields = line.split('|')
        if len(fields) > 3 and fields[1] == 'poke' and fields[2] in result:
            result[fields[2]].append(to_id(fields[3].split(',')[0]))
        if len(fields) > 1 and fields[1] == 'start':
            break
    for values in result.values():
        signature(values)
    return result


def existing_teams():
    """Freeze all historical team families, including held-out planned teams.

    Legacy experiments reused the fixed thirteen teams. EX-065/067 added twenty
    reviewed teams and their fixed own team; EX-068 added one smoke opponent.
    New Kev EX-069/070 reused those teams. Read only team definitions, no outcomes.
    """
    sources, entries = [], []
    for path in sorted((c.ROOT / 'pokechamp/poke_env/data/static/teams/gen9ou').glob('gen9ou*.txt')):
        entries.append(dict(text=path.read_text(), sha256=sha(path), parse_only=True))
        sources.append(dict(path=str(path), sha256=sha(path), role='historical_fixed_team'))
    manifest = c.ROOT / '.pokechamp-data/experiments/ex065-joint-q/versions/collection-v5/manifest.json'
    value = read(manifest)
    for row in [value['own'], *value['opponents']]:
        entries.append(dict(text=row['packed'], packed=True, sha256=digest(row['packed']), parse_only=True))
        sources.append(dict(path=str(manifest), sha256=sha(manifest), role='ex065_reserved_team',
                            packed_sha256=digest(row['packed'])))
    smoke = c.ROOT / '.pokechamp-data/kev/ex068-v3/configuration.json'
    value = read(smoke)
    for row in value['teams'].values():
        entries.append(dict(text=row['showdown_team'], sha256=digest(row['showdown_team']), parse_only=True))
        sources.append(dict(path=str(smoke), sha256=sha(smoke), role='ex068_reserved_team'))
    normalized = normalize(entries)
    return [dict(source=source, species=team['species'], signature=signature(team['species']))
            for source, team in zip(sources, normalized, strict=True)]


def replay_index():
    identifiers = c.ELIGIBLE.read_text().splitlines()
    if len(identifiers) != 2793 or len(set(identifiers)) != 2793:
        raise ValueError('EX-071 requires the registered 2,793 unique replay IDs')
    source_rows = {row['replay_id']:row for row in jsonl(c.ELIGIBLE.parent / 'classification.jsonl')
                   if row['replay_id'] in set(identifiers)}
    rows = []
    for replay_id in identifiers:
        source = source_rows[replay_id]
        path = c.ROOT / source['raw_path']
        if sha(path) != source['raw_file_sha256']:
            raise ValueError('replay source changed: ' + str(path))
        raw = read_replay(path)
        if raw['id'] != replay_id:
            raise ValueError('replay ID/file mismatch')
        teams = preview(raw['log'])
        # Same teams already connect duplicate games. A semantic log key additionally
        # identifies duplicate IDs while excluding irrelevant wall clocks and chatter.
        public = [line for line in raw['log'].splitlines()
                  if len(line.split('|')) > 1 and line.split('|')[1]
                  not in ('t:','j','l','c','c:','chat','inactive','inactiveoff','player','rated','raw','html')]
        rows.append(dict(replay_id=replay_id, raw_path=str(path), raw_sha256=sha(path),
                         teams=teams, signatures=[signature(teams[p]) for p in ('p1','p2')],
                         duplicate_key=digest(public), source=source.get('sources', [])))
    return rows


def connected_split(rows):
    """Group first, then greedy occupancy ratios. No labels/outcomes are read."""
    rows = sorted(rows, key=lambda row: row['replay_id'])
    parent = {row['replay_id']:row['replay_id'] for row in rows}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    seen = {}
    for row in rows:
        for key in [('match',row['duplicate_key']), *(('team',x) for x in row['signatures'])]:
            if key in seen:
                union(row['replay_id'], seen[key])
            seen[key] = row['replay_id']
    components = defaultdict(list)
    for row in rows:
        components[find(row['replay_id'])].append(row['replay_id'])
    groups = [dict(group_id=digest(sorted(ids)), replay_ids=sorted(ids), size=len(ids))
              for ids in components.values()]
    groups.sort(key=lambda group: (-group['size'], ranked('group_order', group['group_id'])))
    counts = {split:0 for split in c.PROTOCOL['split']}
    assignment = {}
    for group in groups:
        split = min(counts, key=lambda name: (counts[name] / (len(rows) * c.PROTOCOL['split'][name]),
                                             ranked('split_tie', [group['group_id'], name])))
        group['split'] = split
        counts[split] += group['size']
        for replay_id in group['replay_ids']:
            assignment[replay_id] = dict(group_id=group['group_id'], split=split)
    return dict(groups=groups, assignment=assignment, counts=counts,
                target=c.PROTOCOL['split'], unit='replay', algorithm='descending_size_min_fill_ratio_hash_tie')


def balanced(rows, limit, namespace):
    groups = defaultdict(list)
    for row in rows:
        groups[row['group_id']].append(row)
    queues = {key: deque(sorted(group, key=lambda row: ranked(namespace, row['sample_id'])))
              for key, group in groups.items()}
    keys = sorted(queues, key=lambda key: ranked(namespace + '_groups', key))
    result = []
    while len(result) < limit:
        advanced = False
        for key in keys:
            if queues[key]:
                result.append(queues[key].popleft())
                advanced = True
                if len(result) == limit:
                    break
        if not advanced:
            break
    return result


def choose_battle_teams(registry, excluded):
    selected, rejected, signatures = [], [], set()
    for entry in sorted(registry['teams'], key=lambda entry: ranked('battle_team', entry['path'])):
        sig = signature(entry['species'])
        if sig in excluded or sig in signatures:
            continue
        path = Path(registry['default_team_root']) / entry['path']
        if sha(path) != entry['sha256']:
            raise ValueError('reviewed team changed: ' + str(path))
        checked = normalize([dict(text=path.read_text(), sha256=entry['sha256'])])[0]
        if not checked.get('legal'):
            rejected.append(dict(path=str(path), sha256=entry['sha256'], reason=checked))
            continue
        actual_species = set(signature(checked['species']).split('|'))
        if actual_species - set(registry['reviewed_species_ids']):
            rejected.append(dict(path=str(path), sha256=entry['sha256'],
                                 reason='normalized_form_outside_reviewed108', species=checked['species']))
            continue
        if signature(checked['species']) != sig:
            raise ValueError('team normalization changed species signature')
        selected.append(dict(**checked, signature=sig, source=str(path), source_sha256=entry['sha256']))
        signatures.add(sig)
        if len(selected) == 10:
            break
    if len(selected) != 10:
        raise ValueError('fewer than ten legal disjoint battle teams')
    return selected, rejected


def make_schedule(teams):
    if len(teams) != 10 or len({team['signature'] for team in teams}) != 10:
        raise ValueError('ten distinct team signatures required')
    schedule = []
    for model in ('initial','selected'):
        for pair in range(5):
            a, b = teams[2*pair:2*pair+2]
            for model_side in ('p1','p2'):
                for opponent in ('abyssal','abyssal-tera-v1'):
                    identity = [pair, model_side, opponent]
                    raw = bytes.fromhex(ranked('battle_seeds', identity))
                    # The model always uses team a; swapping sides preserves its team.
                    side_teams = {'p1':a,'p2':b} if model_side == 'p1' else {'p1':b,'p2':a}
                    schedule.append(dict(slot_id=f'{model}-pair{pair+1}-{model_side}-{opponent}',
                        pair_id=f'pair{pair+1}', model=model, model_side=model_side, opponent=opponent,
                        teams=side_teams, simulator_seed=[int.from_bytes(raw[i:i+2], 'big') for i in range(0,8,2)],
                        opponent_seed=int.from_bytes(raw[8:12], 'big'), model_seed=int.from_bytes(raw[12:16], 'big')))
    return schedule


def make_corpus(registry, excluded, directory):
    selected = [entry for entry in registry['teams'] if signature(entry['species']) not in excluded]
    collapsed, rejected = {}, []
    for start in range(0, len(selected), 200):
        chunk = selected[start:start+200]
        entries = []
        for entry in chunk:
            path = Path(registry['default_team_root']) / entry['path']
            if sha(path) != entry['sha256']:
                raise ValueError('imputation source changed: ' + str(path))
            entries.append(dict(text=path.read_text(), sha256=entry['sha256']))
        for entry, team in zip(chunk, normalize(entries), strict=True):
            if 'individual' not in team:
                rejected.append(dict(source=entry, slot=None, problems=team))
                continue
            actual_species = set(signature(team['species']).split('|'))
            if actual_species - set(registry['reviewed_species_ids']):
                rejected.append(dict(source=entry, slot=None, reason='normalized_form_outside_reviewed108',
                                     problems=sorted(actual_species - set(registry['reviewed_species_ids']))))
                continue
            if signature(team['species']) != signature(entry['species']):
                raise ValueError('registry/corpus species mismatch')
            for slot, row in enumerate(team['individual'], 1):
                if row['problems']:
                    rejected.append(dict(source=entry, slot=slot, problems=row['problems']))
                    continue
                normalized = dict(row['set'])
                normalized.pop('name', None)
                key = digest(normalized)
                aggregate = collapsed.setdefault(key, dict(set=normalized, count=0, sources=[]))
                aggregate['count'] += 1
                aggregate['sources'].append(dict(path=entry['path'], sha256=entry['sha256'], slot=slot,
                                                  signature=signature(entry['species'])))
        atomic(directory / 'team-progress.json', dict(processed=min(start+200,len(selected)), total=len(selected),
                                                     unique_sets=len(collapsed), rejected=len(rejected)))
    corpus = [collapsed[key] for key in sorted(collapsed)]
    write_jsonl(directory / 'corpus.jsonl', corpus, immutable=True)
    write_jsonl(directory / 'corpus-exclusions.jsonl', rejected, immutable=True)
    return dict(source_teams=len(selected), excluded_teams=len(registry['teams'])-len(selected),
                unique_sets=len(corpus), set_occurrences=sum(row['count'] for row in corpus),
                rejected_entries=len(rejected), quarantined_teams=sum(r['slot'] is None for r in rejected),
                rejected_sets=sum(6 if r['slot'] is None else 1 for r in rejected),
                excluded_signatures=sorted(excluded))


def prepare_inputs(directory):
    """Freeze grouping, imputation sources and battle schedule before model use."""
    directory = Path(directory)
    stage = directory / 'preparation'
    stage.mkdir(parents=True, exist_ok=True)
    receipt = stage / 'inputs.json'
    if receipt.exists():
        value = read(receipt)
        for relative, expected in value['files'].items():
            if sha(directory / relative) != expected:
                raise ValueError('prepared input changed: ' + relative)
        return value
    registry = read(c.REGISTRY)
    historical = existing_teams()
    old_signatures = {team['signature'] for team in historical}
    replay_rows = replay_index()
    all_replay_signatures = {sig for row in replay_rows for sig in row['signatures']}
    excluded = [dict(replay_id=row['replay_id'], reason='existing_evaluation_team',
                     signatures=sorted(set(row['signatures']) & old_signatures)) for row in replay_rows
                if set(row['signatures']) & old_signatures]
    excluded_ids = {row['replay_id'] for row in excluded}
    eligible = [row for row in replay_rows if row['replay_id'] not in excluded_ids]
    groups = connected_split(eligible)
    battle_teams, rejected_teams = choose_battle_teams(registry, old_signatures | all_replay_signatures)
    schedule = make_schedule(battle_teams)
    corpus = make_corpus(registry, old_signatures | {team['signature'] for team in battle_teams}, stage)
    atomic(directory / 'protocol.json', c.PROTOCOL, immutable=True)
    atomic(directory / 'schedule.json', schedule, immutable=True)
    atomic(stage / 'historical-teams.json', historical, immutable=True)
    atomic(stage / 'groups.json', groups, immutable=True)
    atomic(stage / 'battle-team-exclusions.json', rejected_teams, immutable=True)
    write_jsonl(stage / 'replays.jsonl', replay_rows, immutable=True)
    write_jsonl(stage / 'replay-exclusions.jsonl', excluded, immutable=True)
    names = ['protocol.json','schedule.json', *('preparation/' + name for name in (
        'historical-teams.json','groups.json','battle-team-exclusions.json','replays.jsonl',
        'replay-exclusions.jsonl','corpus.jsonl','corpus-exclusions.jsonl'))]
    value = dict(experiment=c.EXPERIMENT, created_at=time.time(), source_replays=len(replay_rows),
                 eligible_replays=len(eligible), excluded_replays=len(excluded), split_counts=groups['counts'],
                 groups=len(groups['groups']), largest_group=max(g['size'] for g in groups['groups']),
                 corpus=corpus, registry_sha256=sha(c.REGISTRY), eligibility_sha256=sha(c.ELIGIBLE),
                 files={name:sha(directory/name) for name in names})
    atomic(receipt, value, immutable=True)
    return value


def _label_kind(record):
    kind = record['decision_kind']
    if kind != 'turn_action':
        return kind
    if record['label'] is None:
        return 'unknown'
    return 'voluntary_switch' if record['label'].startswith('switch:') else 'move'


def prepare(directory):
    from .metamon_bridge import BridgeClient
    from .model import load_tokenizer, encode_input, provenance, _kev
    directory = Path(directory)
    if (directory / 'prepared/manifest.json').exists():
        raise FileExistsError('dataset is frozen; use audit')
    inputs = prepare_inputs(directory)
    stage = directory / 'preparation'
    groups = read(stage / 'groups.json')
    corpus = list(jsonl(stage / 'corpus.jsonl'))
    records, exclusions, imputation, quarantined = [], [], [], []
    source_identity = {p.name:sha(p) for p in sorted(Path(__file__).parent.iterdir())
                       if p.name in ('replay.py','metamon_bridge.py','impute.py','schema.py','dataset.py','config.py','teams.cjs','model.py')}
    if (stage/'recovery-source.json').exists():
        if read(stage/'recovery-source.json')!=source_identity:
            raise ValueError('CPU recovery source changed; preserve the earlier version before correction')
    else:
        atomic(stage / 'recovery-source.json', source_identity, immutable=True)
    for name in source_identity:
        target=stage/'source'/name
        if target.exists():
            if sha(target)!=source_identity[name]:raise ValueError('frozen CPU recovery source differs')
        else:atomic(target,(Path(__file__).parent/name).read_bytes(),immutable=True)
    tokenizer = load_tokenizer()
    _, kev = _kev()
    with BridgeClient(corpus_sets=corpus) as bridge, TeamValidatorClient() as validator:
        source_rows = list(jsonl(stage / 'replays.jsonl'))
        for index, source in enumerate(source_rows):
            replay_id = source['replay_id']
            if replay_id not in groups['assignment']:
                continue
            if sha(source['raw_path']) != source['raw_sha256']:
                raise ValueError('replay changed after grouping')
            cache=stage/'recovered'/(replay_id+'.json.gz')
            if cache.exists():
                cached=read_replay(cache)
                if cached['source_sha256']!=source['raw_sha256'] or cached['recovery_source']!=source_identity:
                    raise ValueError('recovery cache identity differs')
                result=cached['result']
            else:
                result = bridge.recover(read_replay(source['raw_path']), replay_id)
                cached=dict(source_sha256=source['raw_sha256'],recovery_source=source_identity,result=result)
                atomic(cache,gzip.compress(json.dumps(cached,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),
                                           compresslevel=1,mtime=0),immutable=True)
            assignment = groups['assignment'][replay_id]
            original_sets=result['original_sets']
            validation=validator.normalize([dict(sets=sets,sha256=digest(sets)) for sets in original_sets.values()])
            legal=dict(zip(original_sets,validation,strict=True))
            invalid_sides={side for side,value in legal.items() if not value.get('legal')}
            for side in invalid_sides:
                exclusions.append(dict(replay_id=replay_id,perspective=side,
                    reason='imputed_team_illegal',details=legal[side]))
            imputation.append(dict(replay_id=replay_id, value=result.get('imputation'),team_validation=legal))
            for exclusion in result['exclusions']:
                exclusions.append(dict(replay_id=replay_id, **exclusion))
            for recovered in result['records']:
                if recovered['perspective'] in invalid_sides or recovered.get('audit',{}).get('quarantined_perspective'):
                    quarantined.append(dict(replay_id=replay_id,**assignment,**recovered))
                    continue
                if not recovered['actions']:
                    reason = recovered.get('audit',{}).get('mask_reason') or 'no_proven_legal_candidates'
                    quarantined.append(dict(replay_id=replay_id,**assignment,**recovered))
                    exclusions.append(dict(replay_id=replay_id,perspective=recovered['perspective'],
                        cutoff_line=recovered['cutoff_line'],reason=reason,
                        automatic_event=reason.startswith('automatic_continuation:')))
                    continue
                value = from_snapshot(recovered['snapshot'], recovered['actions'])
                label = recovered['label']
                if label is not None and label not in value.action_ids:
                    raise ValueError('restored label absent from candidates')
                sample_id = f"{replay_id}:{recovered['perspective']}:{recovered['cutoff_line']}:{recovered['decision_kind']}"
                row = dict(sample_id=sample_id, replay_id=replay_id, **assignment,
                    perspective=recovered['perspective'], cutoff_line=recovered['cutoff_line'],
                    decision_kind=recovered['decision_kind'], label_kind=_label_kind(recovered),
                    tera_used=not recovered['snapshot']['can_tera'], label=label, input=value.body,
                    audit=dict(**recovered.get('audit', {}), source_sha256=source['raw_sha256']))
                try:
                    encoded = encode_input(value, tokenizer)
                except kev.ContextOverflow as exc:
                    row.update(eligible=False, exclusion_reason='state_tokens_exceeded', token_error=str(exc))
                    exclusions.append(dict(replay_id=replay_id, sample_id=sample_id,
                                           reason='state_tokens_exceeded', detail=str(exc)))
                else:
                    row.update(token_count=encoded.tokens, state_tokens=encoded.state_tokens,
                        input_sha256=encoded.input_sha256, eligible=label is not None and len(value.action_ids)>1,
                        exclusion_reason=('unknown_selection' if label is None else
                                          'single_candidate' if len(value.action_ids)==1 else None))
                records.append(row)
            if index % 25 == 0 or index + 1 == len(source_rows):
                atomic(stage / 'recovery-progress.json', dict(processed=index+1, source=len(source_rows),
                    records=len(records), exclusions=len(exclusions), updated_at=time.time()))
    for name, expected in source_identity.items():
        if sha(Path(__file__).parent/name) != expected:
            raise ValueError('recovery source changed while preparing')
    grouped = {split:[row for row in records if row['eligible'] and row['split']==split]
               for split in c.PROTOCOL['split']}
    selected = dict(train=sorted(grouped['train'],key=lambda row:ranked('train_order',row['sample_id'])),
                    validation=balanced(grouped['validation'],512,'validation_samples'),
                    test=balanced(grouped['test'],1024,'test_samples'))
    if not all(selected.values()):
        # Preserve denominators even when first training is impossible.
        atomic(stage / 'insufficient-data.json', dict(counts={key:len(rows) for key,rows in grouped.items()},
                                                     source_inputs_sha256=sha(stage/'inputs.json')))
    prepared = directory/'prepared'
    prepared.mkdir(exist_ok=True)
    write_jsonl(stage/'records.jsonl', records, immutable=True)
    write_jsonl(stage/'recovery-exclusions.jsonl', exclusions, immutable=True)
    write_jsonl(stage/'imputation.jsonl', imputation, immutable=True)
    write_jsonl(stage/'quarantined-decisions.jsonl',quarantined,immutable=True)
    for split, rows in selected.items():
        write_jsonl(prepared/(split+'.jsonl'), rows, immutable=True)
    counts = dict(source_replays=inputs['source_replays'], excluded_replays=inputs['excluded_replays'],
                  source_perspectives=2*inputs['source_replays'], eligible_source_perspectives=2*inputs['eligible_replays'],
                  recovered_perspectives=len({(r['replay_id'],r['perspective']) for r in records}),
                  recovered_decisions=len(records), eligible_decisions=sum(r['eligible'] for r in records),
                  unknown_selection=sum(r['label'] is None for r in records),
                  single_candidate=sum(len(ImitationInput.from_body(r['input']).action_ids)==1 for r in records),
                  quarantined_records=len(quarantined),
                  automatic_events=sum(e.get('automatic_event',False) for e in exclusions),
                  reasons=dict(Counter(r['reason'] for r in exclusions)),
                  reasons_by_unit={unit:dict(Counter(e['reason'] for e in exclusions
                       if ('decision' if 'cutoff_line' in e or 'sample_id' in e else
                           'perspective' if 'perspective' in e else 'replay')==unit))
                       for unit in ('replay','perspective','decision')},
                  full_split={key:len(rows) for key,rows in grouped.items()},
                  selected_split={key:len(rows) for key,rows in selected.items()})
    files = {f'{split}.jsonl':sha(prepared/(split+'.jsonl')) for split in selected}
    manifest = dict(experiment=c.EXPERIMENT, created_at=time.time(), seed=c.SEED, counts=counts, files=files,
                    inputs_sha256=sha(stage/'inputs.json'), schedule_sha256=sha(directory/'schedule.json'),
                    recovery_source_sha256=sha(stage/'recovery-source.json'), model=provenance(verify_weights=True),
                    records_sha256=sha(stage/'records.jsonl'), eligible=all(bool(x) for x in selected.values()))
    atomic(prepared/'manifest.json', manifest, immutable=True)
    return manifest


def audit(directory):
    directory = Path(directory)
    inputs = prepare_inputs(directory)
    stage = directory/'preparation'
    manifest = read(directory/'prepared/manifest.json')
    groups = read(stage/'groups.json')
    records = list(jsonl(stage/'records.jsonl'))
    if sha(stage/'records.jsonl') != manifest['records_sha256']:
        raise ValueError('records changed')
    group_splits, team_splits, game_splits, sample_ids = {}, {}, {}, set()
    sources = {row['replay_id']:row for row in jsonl(stage/'replays.jsonl')}
    eligible = []
    for row in records:
        if row['sample_id'] in sample_ids:
            raise ValueError('duplicate sample ID')
        sample_ids.add(row['sample_id'])
        for table, keys in ((group_splits,[row['group_id']]), (team_splits,sources[row['replay_id']]['signatures']),
                            (game_splits,[sources[row['replay_id']]['duplicate_key']])):
            for key in keys:
                previous = table.setdefault(key,row['split'])
                if previous != row['split']:
                    raise ValueError('cross-split group/team/game leakage')
        if {key:row[key] for key in ('group_id','split')} != groups['assignment'][row['replay_id']]:
            raise ValueError('split assignment changed')
        value = ImitationInput.from_body(row['input'])
        if row['label'] is not None and row['label'] not in value.action_ids:
            raise ValueError('label/ID mismatch')
        reverse = permute(value,list(reversed(range(len(value.action_ids)))))
        if set(reverse.action_ids) != set(value.action_ids):
            raise ValueError('candidate permutation lost ID')
        if row['label'] is not None:
            before = value.body['questions']['action']['criteria'][row['label']]
            after = reverse.body['questions']['action']['criteria'][row['label']]
            if before != after:
                raise ValueError('candidate permutation changed target semantics')
        if row.get('input_sha256') and value.sha256 != row['input_sha256']:
            raise ValueError('input bytes changed')
        if row['eligible']:
            if row['label'] is None or len(value.action_ids)<=1 or row['state_tokens']>c.STATE_TOKENS:
                raise ValueError('ineligible training record')
            eligible.append(row)
    selected = dict(train=sorted([r for r in eligible if r['split']=='train'],key=lambda r:ranked('train_order',r['sample_id'])),
                    validation=balanced([r for r in eligible if r['split']=='validation'],512,'validation_samples'),
                    test=balanced([r for r in eligible if r['split']=='test'],1024,'test_samples'))
    for split, expected in selected.items():
        path = directory/'prepared'/(split+'.jsonl')
        if sha(path) != manifest['files'][split+'.jsonl'] or list(jsonl(path)) != expected:
            raise ValueError('selected population changed: '+split)
    schedule = read(directory/'schedule.json')
    if len(schedule)!=40 or sha(directory/'schedule.json')!=manifest['schedule_sha256']:
        raise ValueError('battle schedule changed')
    banned = {sig for r in sources.values() for sig in r['signatures']}
    banned |= {r['signature'] for r in read(stage/'historical-teams.json')}
    if any(team['signature'] in banned for game in schedule for team in game['teams'].values()):
        raise ValueError('battle team leakage')
    model_pairs = defaultdict(dict)
    for game in schedule:
        model_pairs[(game['pair_id'],game['model_side'],game['opponent'])][game['model']] = game
    for pair in model_pairs.values():
        a, b = pair['initial'],pair['selected']
        if any(a[key]!=b[key] for key in ('teams','simulator_seed','opponent_seed','model_seed')):
            raise ValueError('pre/post schedule not paired')
    for source in sources.values():
        if sha(source['raw_path'])!=source['raw_sha256']:
            raise ValueError('raw source changed')
    result = dict(passed=bool(manifest['eligible']), audited_records=len(records),
        sample_ids=len(sample_ids), groups=len(group_splits), team_signatures=len(team_splits),
        permutations_checked=len(records), locked_battles=40,
        prepared_manifest_sha256=sha(directory/'prepared/manifest.json'), inputs=inputs['files'],
        counts=manifest['counts'], timestamp=time.time())
    atomic(directory/'audit.json',result,immutable=True)
    return result
