"""Frozen Qwen experiment schedules; actors and owned Showdown are isolated."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

from . import jev_battle as j, jev_v4, qwen_value as v
from .branch_rollouts.common import write, file_hash

SEED = '18280,52471,51036,2470'
ACTOR_SEEDS = [20260930, 20260931]
WORKER_CWD = v.ROOT / 'pokechamp'


def verify_worker_assets():
    code = ("import json,hashlib; from pathlib import Path; "
            "from poke_env.environment.pokemon import Pokemon; "
            "p=Pokemon(gen=9,species='pikachu'); "
            "raw=Path('poke_env/data/static/gen9/ou/sets_1500.json').read_bytes(); "
            "print('__QWEN_ASSETS__'+json.dumps(dict(cwd=str(Path.cwd()),sets=len(p._sets), "
            "sha256=hashlib.sha256(raw).hexdigest())))")
    result = subprocess.run([sys.executable, '-c', code], cwd=WORKER_CWD,
                            capture_output=True, text=True, check=True)
    lines = [line.removeprefix('__QWEN_ASSETS__') for line in result.stdout.splitlines()
             if line.startswith('__QWEN_ASSETS__')]
    if len(lines) != 1:
        raise RuntimeError('missing worker asset preflight result')
    return json.loads(lines[0])


def source_identity():
    return dict(j.source_identity(), **{str(p.relative_to(v.ROOT)): file_hash(p) for p in
        [v.ROOT / 'scripts/pokechamp-qwen',
         Path(__file__).with_name('viewer_assets') / 'qwen-local.html',
         v.ROOT / 'export/teams/gen9ou_reviewed108_teams.txt',
         v.ROOT / 'export/teams/gen9ou_reviewed108_teams.json',
         v.EVE / 'rlcd/pokemon_data.py', v.EVE / 'rlcd/pokemon_value.py', v.EVE / 'uv.lock']})


def teams():
    reviewed = (v.ROOT / 'export/teams/gen9ou_reviewed108_teams.txt').read_text().splitlines()
    registry = {r['path']: r for r in json.loads(
        (v.ROOT / 'export/teams/gen9ou_reviewed108_teams.json').read_text())['teams']}
    result = {}
    for key in ('1', '10'):
        path = Path('/tmp/metamon_cache/teams/modern_replays/gen9ou') / f'team_{key}.gen9ou_team'
        if path.name not in reviewed:
            raise ValueError('team not in reviewed list')
        if file_hash(path) != registry[path.name]['sha256']:
            raise ValueError('reviewed team source hash changed')
        result[key] = dict(source=str(path), sha256=file_hash(path),
                           showdown_team=path.read_text())
    return result


def configuration(experiment):
    if experiment == 'EX-062':
        schedule = [dict(slot_id=f'ex062-s{swap}', teams=['1', '10'], qwen_actor=f'p{swap + 1}',
                         battle_seed=SEED, actor_seeds=ACTOR_SEEDS) for swap in (0, 1)]
        return teams(), schedule, {}, v.EVIDENCE / 'gpu-probe'
    if experiment != 'EX-063':
        raise ValueError('unregistered experiment')
    from poke_env.teambuilder.constant_teambuilder import ConstantTeambuilder
    from .branch_rollouts.common import SOURCE, verify_source, simulator_teams, rows, digest
    seals = verify_source()
    request = json.loads((SOURCE / 'battle-19/request.json').read_text())
    outcome = json.loads((SOURCE / 'battle-19/outcome.json').read_text())
    slot = request['slot']
    assert slot['teams'] == ['6', '2'] and slot['jev_actor'] == 'p2'
    assert slot['battle_seed'] == '64650,46273,35382,36029'
    assert slot['actor_seeds'] == [964798779, 2142274391]
    assert outcome['completed'] and outcome['outcome'] == 'player_lost' and outcome['turns'] == 12
    user = request['names']['p2']
    events = [row for row in rows(SOURCE / 'events.jsonl') if row.get('username') == user]
    packed = {side: dict(team=ConstantTeambuilder(request['teams'][key]['showdown_team']).yield_team())
              for side, key in zip(('p1', 'p2'), slot['teams'])}
    reconstructed = simulator_teams(packed, events)
    process = subprocess.run(['node', str(Path(__file__).with_name('qwen_training_teams.cjs'))],
        input=json.dumps(reconstructed), text=True, capture_output=True, check=True)
    submitted = json.loads(process.stdout)
    records = {}
    for side, key in zip(('p1', 'p2'), slot['teams']):
        original = request['teams'][key]
        path = v.ROOT / original['source']
        if file_hash(path) != original['sha256'] or path.read_text() != original['showdown_team']:
            raise ValueError('original team source changed')
        text = submitted[side]
        if ConstantTeambuilder(text).yield_team() != reconstructed[side]['team']:
            raise ValueError('submitted text changes reconstructed packed team')
        records[key] = dict(source=str(path), sha256=original['sha256'],
            original_showdown_team=original['showdown_team'], showdown_team=text,
            submitted_sha256=hashlib.sha256(text.encode()).hexdigest(),
            original_packed=packed[side]['team'], submitted_packed=reconstructed[side]['team'])
    schedule = [dict(slot_id='ex063-b02-r3-s0', source_slot_id=slot['slot_id'], teams=slot['teams'],
                     qwen_actor='p2', battle_seed=slot['battle_seed'], actor_seeds=slot['actor_seeds'])]
    provenance = dict(source_experiment='EX-058', source_battle=19, source_directory=str(SOURCE),
        source_hashes=seals, original_outcome=outcome, split='development_only',
        reconstruction='public-preview gender assignments only', reconstruction_sha256=digest(reconstructed))
    return records, schedule, provenance, v.ROOT / 'project_context/exec-plans/evidence/ep104/gpu-probe'


async def worker(attempt, role, kind):
    import numpy as np
    from poke_env.player.baselines import AbyssalPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from .battle_adapter import guard_parser, install_identity_adapter
    from .jev_study import play
    from . import cli
    from .qwen_player import Session, player_class
    install_identity_adapter()
    request = json.loads((attempt / 'request.json').read_text())
    seed = request['slot']['actor_seeds'][int(role[-1]) - 1]
    random.seed(seed)
    np.random.seed(seed)
    session = Session(attempt.parent) if kind == 'qwen' else None
    common = dict(team=request['teams'][request['slot']['teams'][int(role[-1]) - 1]]['showdown_team'],
        battle_format='gen9ou', max_concurrent_battles=1, start_timer_on_battle_start=False,
        account_configuration=AccountConfiguration(request['names'][role], None),
        server_configuration=ServerConfiguration('localhost:8109', 'https://play.pokemonshowdown.com/action.php?'))
    player = player_class()(session=session, expected_actor=role, **common) if session else AbyssalPlayer(**common)
    if not session:
        guard_parser(player)
    result = dict(completed=False, pid=os.getpid(), actor=role, kind=kind,
                  python_random_seed=seed, numpy_random_seed=seed,
                  python_hash_seed=os.environ.get('PYTHONHASHSEED'))
    try:
        result.update(await play(player, role, request['names'], attempt,
                                 session=session, deadline=float('inf')))
    except j.UnusableChoice as exc:
        result.update(error=dict(type=type(exc).__name__, detail=str(exc)), failure_scope='battle')
    except BaseException as exc:
        result.update(error=dict(type=type(exc).__name__, detail=str(exc)), failure_scope='collection')
    finally:
        await cli._close_players([player])
        if getattr(player, 'official', None):
            player.official.close()
        if session and getattr(session, 'v4_adapter', None):
            await asyncio.to_thread(session.v4_adapter.close)
        write(attempt / f'{role}.result.json', result)
    return result


def verify_teams(team_records):
    process = subprocess.run(['node', str(Path(__file__).with_name('qwen_teams.cjs'))],
        input=json.dumps(team_records), text=True, capture_output=True, check=True)
    return json.loads(process.stdout)


def run(directory, experiment='EX-062'):
    from .parallel_server import BattleServer
    from .benchmark import terminate
    from . import cli
    from .qwen_audit import audit
    directory = directory.resolve()
    team_records, schedule, provenance, probe_directory = configuration(experiment)
    planned = len(schedule)
    worker_assets = verify_worker_assets()
    health = v.request('/health')
    from .qwen_control import status
    ownership = status()
    if not ownership['owned_running']:
        raise ValueError('owned local server required for frozen run')
    server_output = Path(ownership['owner']['output'])
    for relative, digest in json.loads((server_output / 'source-hashes.json').read_text()).items():
        if file_hash(v.ROOT / relative) != digest:
            raise ValueError('loaded server source differs from current source')
    probe = json.loads((probe_directory / 'verification.json').read_text())
    if (not health['ready'] or health['adapter_sha256'] != v.ADAPTER_SHA or
            not probe['passed'] or probe['health']['adapter_sha256'] != health['adapter_sha256']):
        raise ValueError('healthy pinned server and GPU replay verification required')
    # A receipt from an earlier process cannot admit a freshly loaded server.
    data = v.data_module()
    for index, root in enumerate(data.jsonl(v.TRAINING / 'data/inputs.jsonl'), 1):
        replay = json.loads((probe_directory / (root['anchor_id'] + '.json')).read_text())
        actual = data.jsonl(server_output / f'request-{index:05d}.jsonl')
        if actual != [replay]:
            raise ValueError('GPU replay receipt does not bind to current server')
    team_check = verify_teams(team_records)
    sources = source_identity()
    input_identity = jev_v4.data_identity()
    directory.mkdir(parents=True, exist_ok=False)
    manifest = dict(experiment_id=experiment, profile=v.PROFILE, schema_version='jev-choice-v4',
        source=sources, data_identity=input_identity, schedule=schedule, teams=team_records,
        team_validation=team_check, model=health, timer_enabled=False, max_len=v.MAX_LEN,
        server_owner=ownership['owner'],
        submodules={name: dict(sha=config['sha']) for name, config in cli.SUBMODULES.items()},
        port=8109, observation_build=json.loads((Path(__file__).with_name('observation') / 'build-identity.json').read_text()),
        worker_assets=worker_assets,
        limits=dict(games=planned, request_seconds=v.TIMEOUT, total_seconds=None, retries=0, fallback=0, recollection=0),
        matchup_provenance=provenance,
        efficacy_evidence=False, probe_sha256=file_hash(probe_directory / 'verification.json'),
        eve_source={str(p.relative_to(v.ROOT)): file_hash(p) for p in
                    [v.EVE / 'rlcd/pokemon_data.py', v.EVE / 'rlcd/pokemon_value.py']},
        created_at=time.time())
    write(directory / 'manifest.json', manifest)
    for relative in sources:
        target = directory / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((v.ROOT / relative).read_bytes())
    outcomes, error = [], None
    started = time.monotonic()
    try:
        for number, row in enumerate(schedule, 1):
            if source_identity() != sources or jev_v4.data_identity() != input_identity:
                raise ValueError('source or input data changed before admission')
            if any(file_hash(Path(team['source'])) != team['sha256'] for team in team_records.values()):
                raise ValueError('team source changed before admission')
            attempt = directory / f'battle-{number}'
            attempt.mkdir()
            server = BattleServer(attempt, 8109, row['battle_seed'])
            role = row['qwen_actor']
            identity = hashlib.sha256(f'{directory}:{number}'.encode()).hexdigest()[:12]
            names = {f'p{i}': ('qv' if f'p{i}' == role else 'aby') + identity for i in (1, 2)}
            write(attempt / 'request.json', dict(slot=row, teams=team_records, names=names))
            outcome = dict(slot=number, **row, username=names[role], completed=False, audit_passed=False)
            outcomes.append(outcome)
            processes, logs = {}, []
            try:
                server.start()
                for actor in ('p1', 'p2'):
                    kind = 'qwen' if actor == role else 'abyssal'
                    log = (attempt / f'{actor}.log').open('xb')
                    logs.append(log)
                    env = cli._child_environment(PYTHONPATH=f'{v.ROOT}:{v.ROOT / "pokechamp"}',
                        PYTHONHASHSEED=str(row['actor_seeds'][int(actor[-1]) - 1]),
                        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
                    processes[actor] = subprocess.Popen([sys.executable, '-m',
                        'integration.pokechamp.qwen_battle', 'worker', '--attempt', str(attempt),
                        '--role', actor, '--kind', kind], cwd=WORKER_CWD, env=env,
                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                while True:
                    results = {actor: json.loads((attempt / f'{actor}.result.json').read_text())
                               for actor in processes if (attempt / f'{actor}.result.json').exists()}
                    failed = [r for r in results.values() if r.get('error')]
                    if failed:
                        original = results.get(role, failed[0])
                        if original.get('failure_scope') == 'battle':
                            outcome.update(error=original['error'], failure_scope='battle', outcome='output_failure')
                            break
                        raise RuntimeError('actor failure: ' + json.dumps(failed, ensure_ascii=False))
                    if len(results) == 2:
                        complement = {'player_won': 'player_lost', 'player_lost': 'player_won', 'tied': 'tied'}
                        a, b = results[role], results['p2' if role == 'p1' else 'p1']
                        if not all(r['completed'] for r in results.values()) or b['outcome'] != complement[a['outcome']] or a['turns'] != b['turns']:
                            raise ValueError('actor terminal mismatch')
                        for actor, result in results.items():
                            seed = row['actor_seeds'][int(actor[-1]) - 1]
                            if result['python_random_seed'] != seed or result['numpy_random_seed'] != seed or result['python_hash_seed'] != str(seed):
                                raise ValueError('actor seed mismatch')
                        outcome.update(completed=True, outcome=a['outcome'], turns=a['turns'],
                                       battle_tag=a['battle_tag'], actor_results=results)
                        break
                    for actor, process in processes.items():
                        if process.poll() is not None and actor not in results:
                            raise RuntimeError('worker exited without result: ' + actor)
                    time.sleep(.2)
            finally:
                write(attempt / 'cancel.json', dict(reason='attempt ended'))
                for process in processes.values():
                    terminate(process)
                for log in logs:
                    log.close()
                server.close()
                outcome.update(server_cleaned=not server.created and (server.process is None or server.process.poll() is not None),
                               actors_cleaned=all(p.poll() is not None for p in processes.values()))
                write(attempt / 'outcome.json', outcome)
            result = dict(planned=planned, outcomes=outcomes)
            check = audit(directory, result)
            outcome['audit_passed'] = check['passed']
            write(attempt / 'audit.json', check)
            write(attempt / 'outcome.json', outcome)
            if not check['passed']:
                raise ValueError('per-match input/selection/wire audit failed')
            print(json.dumps(outcome, ensure_ascii=False), flush=True)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, detail=str(exc))
    if source_identity() != sources or jev_v4.data_identity() != input_identity:
        error = dict(type='SourceChanged', detail='source or input changed during collection')
    completed = [o for o in outcomes if o['completed'] and o['audit_passed']]
    result = dict(passed=error is None and len(completed) == planned, planned=planned, completed=len(completed),
        failed=sum(not o['completed'] for o in outcomes), unattempted=planned-len(outcomes),
        wins=sum(o['outcome'] == 'player_won' for o in completed),
        draws=sum(o['outcome'] == 'tied' for o in completed),
        losses=sum(o['outcome'] == 'player_lost' for o in completed), outcomes=outcomes,
        error=error, elapsed_seconds=time.monotonic()-started, efficacy_evidence=False)
    write(directory / 'result.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', nargs='?', default='run', choices=['run', 'worker'])
    p.add_argument('--output', type=Path, default=v.LIVE)
    p.add_argument('--experiment', choices=['EX-062', 'EX-063'], default='EX-062')
    p.add_argument('--attempt', type=Path)
    p.add_argument('--role', choices=['p1', 'p2'])
    p.add_argument('--kind', choices=['qwen', 'abyssal'])
    args = p.parse_args()
    if args.command == 'run' and args.experiment == 'EX-063' and args.output == v.LIVE:
        args.output = v.ROOT / '.pokechamp-data/qwen/ex063-live'
    result = asyncio.run(worker(args.attempt, args.role, args.kind)) if args.command == 'worker' else run(args.output, args.experiment)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if result.get('error'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
