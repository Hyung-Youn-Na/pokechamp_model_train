"""User-selected team schedule and verifiable immutable code/data identities."""
from __future__ import annotations
import itertools
import json
import shutil
import subprocess
import time
from pathlib import Path
from .storage import ROOT, VERSION, MASTER, atomic, digest, read, seed, sha

TEAMS = {'train': [20985,21254,50982,87706,101245,107610,18712,113171,1540,36810],
         'validation': [26893,27448,35809,2838,47268],
         'test': [100817,7627,38229,48494,5742]}
REPEATS = {'train': 5, 'validation': 2, 'test': 4}


def normalize(entries):
    result = subprocess.run(['node', str(Path(__file__).with_name('teams.cjs'))],
                            input=json.dumps(entries), text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def classify(sets):
    recovery = {'recover','roost','slackoff','softboiled','wish','rest','synthesis','moonlight',
                'morningsun','strengthsap','shoreup','healorder','milkdrink'}
    mons = []
    for s in sets:
        ev = s.get('evs', {})
        mons.append(dict(species=s['species'], recovery_moves=sorted(recovery & {''.join(c for c in m.lower() if c.isalnum()) for m in s['moves']}),
                         regenerative_ability=s['ability'] in ('Regenerator','Poison Heal'),
                         offensive_evs=sum(ev.get(x, 0) for x in ('atk','spa','spe')),
                         defensive_evs=sum(ev.get(x, 0) for x in ('hp','def','spd'))))
    count = sum(bool(m['recovery_moves']) or m['regenerative_ability'] for m in mons)
    offense = sum(m['offensive_evs'] for m in mons)
    return dict(label='defensive' if count >= 4 else 'offensive' if count <= 1 and offense >= 1800 else 'mixed_balanced',
                evidence=mons, rule='recovery>=4 defensive; recovery<=1 and offensive EV>=1800 offensive; else mixed',
                competitive_strength_validated=False)


def prepare(directory, *, experiment='EX-065'):
    directory = Path(directory)
    if (directory / 'manifest.json').exists():
        raise FileExistsError('schedule is immutable; use resume, not prepare')
    if experiment not in ('EX-065', 'EX-067'):
        raise ValueError('unregistered collection experiment')
    tera = experiment == 'EX-067'
    seed_fn, namespace, master, version = seed, 'EX065', MASTER, VERSION
    if tera:
        from . import tera_config as tc
        seed_fn, namespace, master, version = tc.seed, tc.NAMESPACE, tc.MASTER, tc.VERSION
    reviewed_path = ROOT / 'export/teams/gen9ou_reviewed108_teams.json'
    reviewed = read(reviewed_path)
    approved = {r['path']: r for r in reviewed['teams']}
    source = ROOT / '.pokechamp-data/rollouts/ex058-b19-rollout-v1/manifest.json'
    old = read(source)
    own_wire = old['simulator_teams']['p2']['team']
    entries = [dict(text=own_wire, packed=True, hash=digest(own_wire)),
               dict(text=old['simulator_teams']['p1']['team'], packed=True, hash='development')]
    chosen = []
    for split, ids in TEAMS.items():
        for number in ids:
            name = f'team_{number}.gen9ou_team'
            info = approved[name]
            path = Path(reviewed['default_team_root']) / name
            if sha(path) != info['sha256']:
                raise ValueError('reviewed team hash mismatch: ' + name)
            text = path.read_text()
            entries.append(dict(text=text, packed=False, hash=info['sha256']))
            chosen.append(dict(split=split, number=number, original=text, original_sha256=info['sha256'], source=str(path)))
    normalized = normalize(entries)
    own, development = normalized[:2]
    # Validator's representation may add defaults; preserve the exact own wire.
    own['packed'] = own_wire
    own['source_manifest_sha256'] = sha(source)
    own['sha256'] = digest(own_wire)
    for entry, value in zip(chosen, normalized[2:], strict=True):
        entry.update(value, group_id=digest(sorted(value['species'])),
                     team_sha256=digest(value['packed']), style=classify(value['sets']))
        if len(set(value['species']) & set(development['species'])) >= 5:
            raise ValueError('development opponent overlap')
    for a, b in itertools.combinations(chosen, 2):
        if len(set(a['species']) & set(b['species'])) >= 5:
            raise ValueError('selected team overlap')
    games = []
    for entry in chosen:
        for index in range(REPEATS[entry['split']]):
            identity = f"{entry['split']}-t{entry['number']}-s{index}"
            if tera:
                identity = namespace + '-' + identity
            args = (entry['split'], entry['team_sha256'], index)
            games.append(dict(game_id=identity, split=entry['split'], team_number=entry['number'],
                group_id=entry['group_id'], seed_index=index, pilot=entry['split']=='train' and index==0,
                simulator_seed=seed_fn(*args, 'simulator', simulator=True),
                actor_seeds={s: seed_fn(*args, s) for s in ('p1','p2')}))
    manifest = dict(experiment=experiment, version=version, created_at=time.time(), master_seed=master,
        namespace=namespace, actor='p2', own=own, opponents=chosen, games=games, repetitions=32,
        original_policy=dict(name='Abyssal', actor_initialization='fresh independent actors per game'),
        continuation_policy=dict(name='Abyssal', own_initialization='observed-prefix without policy calls',
                                 opponent_initialization='original actor at decision barrier',
                                 hidden_sets='fixed actual state', general_policy_tera=False),
        reviewed_sha256=sha(reviewed_path), split_games={'train':50,'validation':10,'test':20},
        limits=dict(initial_workers=32, memory_reserve_gib=24, native_threads=1, attempts_per_rollout=3,
                    wall_clock_cap=None, extra_turn_cap=None),
        q='(W+0.5D)/32', model_calls=0, api_calls=0)
    if tera:
        manifest['policy'] = tc.policy_spec()
        manifest['python_hash_seed'] = tc.MASTER
        manifest['original_policy']['name'] = manifest['policy']['policy_id']
        manifest['continuation_policy'].update(name=manifest['policy']['policy_id'], general_policy_tera=True)
        manifest['limits'].update(initial_workers=tc.WORKERS, disk_reserve_gib=24,
                                  capture_workers=tc.CAPTURE_WORKERS, input_workers=tc.INPUT_WORKERS)
    directory.mkdir(parents=True, exist_ok=True)
    atomic(directory / 'manifest.json', manifest, immutable=True)
    return dict(games=len(games), teams=len(chosen), pilot=sum(g['pilot'] for g in games), manifest_sha256=sha(directory/'manifest.json'), python_hash_seed=master)


def paths():
    # Include imports, knowledge and compiled engines, not training weights.
    roots = ['integration/pokechamp', 'pokechamp/poke_env', 'pokechamp/pokechamp',
             'pokemon-showdown/dist', 'pokemon-showdown/config', 'data']
    selected = set()
    for name in roots:
        for p in (ROOT / name).rglob('*'):
            if p.is_file() and p.suffix in {'.py','.cjs','.js','.json','.txt','.ts','.md'} and not any(
                    x in p.parts for x in ('__pycache__','node_modules','.pytest_cache','tests')):
                selected.add(p)
    from ..observation.build import DEFAULT_BUILD
    from ..diagnostics.damage_sets import SetSnapshot, SNAPSHOT
    from ..diagnostics.jev_offline import RoleDB
    # Runtime assets can reside outside source roots; discover their identities.
    selected.update(p for p in DEFAULT_BUILD.rglob('*') if p.is_file())
    selected.update(p for p in SNAPSHOT.rglob('*.json') if p.is_file())
    selected.update(p for p in (ROOT/'integration/pokechamp/improved_io/calculator/node_modules/@smogon/calc').rglob('*') if p.is_file())
    selected.add(ROOT/'export/docs/gen9ou_team_pool_role_db.json')
    selected.add(ROOT/'export/teams/gen9ou_reviewed108_teams.json')
    if (ROOT/'scripts/pokechamp-joint-q-tera').exists():
        selected.add(ROOT/'scripts/pokechamp-joint-q-tera')
    selected.update(p for p in (ROOT/'pokechamp').glob('*.py'))
    return sorted(p for p in selected if p.exists())


def freeze(directory, label=None):
    directory=Path(directory)
    label=label or (read(directory/'active-source.json')['label'] if (directory/'active-source.json').exists() else 'collection')
    target=directory/f'frozen-{label}.json'
    if target.exists():
        verify(directory, label)
        return read(target)
    selected=paths()
    if read(directory/'manifest.json').get('namespace')=='EX067':
        from .tera_verify import TEST_FILES, BROWSER_CHECKER
        selected += [ROOT/'integration/pokechamp/tests'/name for name in TEST_FILES]
        selected.append(ROOT/BROWSER_CHECKER)
    files={str(p.relative_to(ROOT)):sha(p) for p in selected}
    for name in files:
        dest=directory/'frozen'/label/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, dest)
    subs={name:subprocess.check_output(['git','-C',str(ROOT/name),'rev-parse','HEAD'],text=True).strip()
          for name in ('pokechamp','pokemon-showdown')}
    value=dict(files=files, source_id=digest(files), submodules=subs, at=time.time(),
               manifest_sha256=sha(directory/'manifest.json'),
               python_hash_seed=read(directory/'manifest.json').get('python_hash_seed',20260929))
    atomic(target,value,immutable=True)
    return value


def verify(directory, label=None):
    directory=Path(directory)
    label=label or (read(directory/'active-source.json')['label'] if (directory/'active-source.json').exists() else 'collection')
    frozen=read(directory/f'frozen-{label}.json')
    if frozen['manifest_sha256']!=sha(directory/'manifest.json'):
        raise ValueError('frozen manifest changed')
    for name, expected in frozen['files'].items():
        if sha(ROOT/name)!=expected or sha(directory/'frozen'/label/name)!=expected:
            raise ValueError('frozen source/data changed: '+name)
    return frozen['source_id']
