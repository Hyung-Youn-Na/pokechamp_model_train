"""One registered Kev-p2 smoke, with isolated Abyssal and owned Showdown."""
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

from . import kev_control as control
from . import kev_value
from .branch_rollouts.common import file_hash, read, write


def team_submission(record):
    # poke-env's text parser changes regional-form nicknames. Preserve EX-065's
    # actual wire team, while the model generator continues to receive own.text.
    return record.get('packed', record['showdown_team'])


def record_sends(player, session):
    """Observe every transport action, independently of the Kev decision handler."""
    original = player.ps_client.send_message

    async def send(message, room='', message_2=None):
        result = await original(message, room, message_2)
        if message.startswith(('/choose ', '/team ')):
            session.record(dict(type='ps_send', username=player.username, battle=room,
                                command=message, request_id=message_2))
        elif message.startswith('/utm '):
            session.record(dict(type='team_submission', username=player.username,
                                packed_team=message.removeprefix('/utm ')))
        return result

    player.ps_client.send_message = send


def session_options(request):
    """Legacy requests retain their default; explicit declarations must be valid."""
    profile = request.get('profile', kev_value.PROFILE)
    kev_value.question_template(profile)
    return dict(profile=profile, timeout=request.get('request_seconds', kev_value.TIMEOUT))


async def worker(attempt, role):
    import numpy as np
    from poke_env.player.baselines import AbyssalPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from . import cli, jev_battle as j
    from .battle_adapter import guard_parser, install_identity_adapter
    from .jev_study import play
    from .kev_player import Session, player_class
    install_identity_adapter()
    request = read(attempt / 'request.json')
    seed = request['slot']['actor_seeds'][int(role[-1]) - 1]
    random.seed(seed)
    np.random.seed(seed)
    session = Session(attempt.parent, **session_options(request)) if role == 'p2' else None
    player = None
    result = dict(completed=False, pid=os.getpid(), actor=role, kind='kev' if session else 'abyssal',
                  python_random_seed=seed, numpy_random_seed=seed,
                  python_hash_seed=os.environ.get('PYTHONHASHSEED'))
    try:
        team = request['teams'][request['slot']['teams'][int(role[-1]) - 1]]
        common = dict(team=team_submission(team),
            battle_format='gen9ou', max_concurrent_battles=1, start_timer_on_battle_start=False,
            account_configuration=AccountConfiguration(request['names'][role], None),
            server_configuration=ServerConfiguration('localhost:8109', 'https://play.pokemonshowdown.com/action.php?'))
        if session:
            player = player_class()(session=session, expected_actor=role, **common)
            player.submitted_team = team['showdown_team']
            record_sends(player, session)
        else:
            player = AbyssalPlayer(**common)
            guard_parser(player)
        result.update(await play(player, role, request['names'], attempt, session=session,
                                 deadline=request['deadline_monotonic']))
    except j.UnusableChoice as exc:
        result.update(error=dict(type=type(exc).__name__, detail=str(exc)), failure_scope='battle')
    except BaseException as exc:
        result.update(error=dict(type=type(exc).__name__, detail=str(exc)), failure_scope='collection')
    finally:
        try:
            if player is not None:
                await cli._close_players([player])
                if getattr(player, 'official', None):
                    player.official.close()
            if session:
                await asyncio.to_thread(session.close)
        finally:
            write(attempt / f'{role}.result.json', result)
    return result


def admit(directory):
    directory = Path(directory)
    plan = control.verify_prepared(directory)
    probe = read(directory / 'probe.json')
    if (not probe['passed'] or probe['configuration_sha256'] != file_hash(directory / 'configuration.json') or
            probe['acceptance_sha256'] != file_hash(directory / 'validation/server-probe.json')):
        raise ValueError('passing immutable validation prediction gate required')
    current = control.server_identity()
    if (current['identity'] != probe['server']['identity'] or
            current['checkpoint'] != plan['checkpoint']):
        raise ValueError('server changed since validation probe')
    if len(plan['schedule']) != 1 or plan['schedule'][0]['kev_actor'] != 'p2':
        raise ValueError('only registered one-match Kev-p2 smoke is admitted')
    return plan, current


def run(directory=control.OUTPUT):
    from . import cli
    from .benchmark import terminate
    from .parallel_server import BattleServer
    from .kev_audit import audit
    from .qwen_viewer import seal
    directory = Path(directory).resolve()
    plan, serving = admit(directory)
    # Exclusive persistent admission prevents a new output directory from repeating this run.
    control.BATTLE_ADMISSION.parent.mkdir(parents=True, exist_ok=True)
    admission = dict(at=time.time(), monotonic=time.monotonic(), planned=1, directory=str(directory),
                     configuration_sha256=file_hash(directory / 'configuration.json'))
    with control.BATTLE_ADMISSION.open('x') as stream:
        json.dump(admission, stream)
        stream.flush()
        os.fsync(stream.fileno())
    write(directory / 'battle-started.json', admission)
    live = directory / 'live'
    live.mkdir(exist_ok=False)
    manifest = dict(plan, model=serving['models'], server=serving,
                    validation_probe_sha256=file_hash(directory / 'probe.json'), port=8109)
    write(live / 'manifest.json', manifest)
    (live / 'events.jsonl').touch(exist_ok=False)
    row = plan['schedule'][0]
    attempt = live / 'battle-1'
    attempt.mkdir()
    identity = hashlib.sha256(f'{directory}:{row["slot_id"]}'.encode()).hexdigest()[:12]
    names = dict(p1='aby' + identity, p2='kev' + identity)
    started = time.monotonic()
    deadline = started + plan['limits']['total_seconds']
    write(attempt / 'request.json', dict(slot=row, teams=plan['teams'], names=names, profile=plan['profile'],
                                       request_seconds=plan['limits']['request_seconds'],
                                       deadline_monotonic=deadline))
    server = BattleServer(attempt, 8109, row['battle_seed'])
    outcome = dict(slot=1, **row, username=names['p2'], completed=False, audit_passed=False)
    error, cleanup_errors, processes, logs = None, [], {}, []
    try:
        server.start()
        for actor in ('p1', 'p2'):
            log = (attempt / f'{actor}.log').open('xb')
            logs.append(log)
            env = cli._child_environment(PYTHONPATH=f'{control.ROOT}:{control.ROOT / "pokechamp"}',
                PYTHONHASHSEED=str(row['actor_seeds'][int(actor[-1]) - 1]), CUDA_VISIBLE_DEVICES='',
                OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
            env.pop('KEV_API_KEY', None)
            if actor == 'p2' and os.environ.get('KEV_API_KEY'):
                env['KEV_API_KEY'] = os.environ['KEV_API_KEY']
            processes[actor] = subprocess.Popen([sys.executable, '-m', 'integration.pokechamp.kev_battle',
                'worker', '--attempt', str(attempt), '--role', actor], cwd=control.ROOT / 'pokechamp',
                env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('EX-068 cumulative battle limit exceeded')
            results = {actor: read(attempt / f'{actor}.result.json') for actor in processes
                       if (attempt / f'{actor}.result.json').exists()}
            failed = [r for r in results.values() if r.get('error')]
            if failed:
                original = results.get('p2', failed[0])
                if not original.get('error'):
                    original = failed[0]
                outcome.update(error=original['error'], failure_scope=original.get('failure_scope'),
                               outcome='output_failure' if original.get('failure_scope') == 'battle' else 'technical_failure')
                error = original['error']
                break
            if len(results) == 2:
                a, b = results['p2'], results['p1']
                complement = dict(player_won='player_lost', player_lost='player_won', tied='tied')
                if (not all(r['completed'] for r in results.values()) or
                        b['outcome'] != complement[a['outcome']] or a['turns'] != b['turns']):
                    raise ValueError('actor terminal mismatch')
                for actor, result in results.items():
                    seed = row['actor_seeds'][int(actor[-1]) - 1]
                    if (result['python_random_seed'] != seed or result['numpy_random_seed'] != seed or
                            result['python_hash_seed'] != str(seed) or result['actor'] != actor):
                        raise ValueError('actor seed or role mismatch')
                outcome.update(completed=True, outcome=a['outcome'], turns=a['turns'],
                               battle_tag=a['battle_tag'], actor_results=results)
                break
            for actor, process in processes.items():
                if process.poll() is not None and actor not in results:
                    raise RuntimeError('worker exited without result: ' + actor)
            time.sleep(.2)
    except BaseException as exc:
        error = dict(type=type(exc).__name__, detail=str(exc))
        outcome.update(error=error, failure_scope='collection')
    finally:
        write(attempt / 'cancel.json', dict(reason='attempt ended'))
        for process in processes.values():
            try:
                terminate(process)
            except Exception as exc:
                cleanup_errors.append(type(exc).__name__)
        for log in logs:
            log.close()
        try:
            server.close()
        except Exception as exc:
            cleanup_errors.append(type(exc).__name__)
        outcome.update(server_cleaned=not server.created and (server.process is None or server.process.poll() is not None),
                       actors_cleaned=all(p.poll() is not None for p in processes.values()))
        write(attempt / 'outcome.json', outcome)
    result = dict(planned=1, attempted=1, completed=int(outcome['completed']),
                  failed=int(not outcome['completed']), unattempted=0, outcomes=[outcome],
                  error=error, cleanup_errors=cleanup_errors, elapsed_seconds=time.monotonic() - started,
                  efficacy_evidence=False, explanation_review='미평가(기본 제외)')
    try:
        check = audit(live, result)
        write(attempt / 'audit.json', check)
        outcome['audit_passed'] = check['passed']
        if not check['passed']:
            raise ValueError('Kev per-decision audit failed')
        control.verify_prepared(directory)
        final_server = control.server_identity()
        if final_server['identity'] != serving['identity'] or final_server['checkpoint'] != serving['checkpoint']:
            raise ValueError('server/checkpoint changed during battle')
    except Exception as exc:
        result['error'] = dict(type=type(exc).__name__, detail=str(exc), prior_error=result['error'])
    valid = outcome['completed'] and outcome['audit_passed'] and not result['error'] and not cleanup_errors
    result.update(passed=bool(valid), valid_completed=int(bool(valid)),
                  wins=int(outcome.get('outcome') == 'player_won'), draws=int(outcome.get('outcome') == 'tied'),
                  losses=int(outcome.get('outcome') == 'player_lost'))
    write(attempt / 'outcome.json', outcome)
    write(live / 'result.json', result)
    seal(live)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['worker'])
    p.add_argument('--attempt', type=Path, required=True)
    p.add_argument('--role', choices=['p1', 'p2'], required=True)
    args = p.parse_args()
    result = asyncio.run(worker(args.attempt, args.role))
    print(json.dumps(result, ensure_ascii=False))
    if result.get('error'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
