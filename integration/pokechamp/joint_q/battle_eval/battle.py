"""EX081 native CPU battle workers and one-attempt, owned Showdown harness."""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import random
import signal
import subprocess
import time

from ...kev_battle import record_sends, team_submission
from . import client, protocol
from .config import ROOT, NATIVE, LIMITS
from .storage import atomic, read, sha

MODULE = 'integration.pokechamp.joint_q.battle_eval.battle'


def error_record(error):
    return dict(type=type(error).__name__, detail=str(error))


def verify_sources(plan):
    sources = plan.get('source')
    if not isinstance(sources, dict) or not sources:
        raise client.IdentityError('registered source hashes are required')
    for name, checksum in sources.items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != checksum:
            raise client.IdentityError('EX081 registered source changed: ' + name)


def reserve_port(directory, preferred=None):
    """Own one available launcher-supported loopback port, never a foreign listener."""
    from ...parallel_server import check_ports
    if preferred is not None and (type(preferred) is not int or not 8100 <= preferred <= 8109):
        raise ValueError('Showdown port must be in 8100..8109')
    locks = ROOT / '.pokechamp-data/locks'
    locks.mkdir(parents=True, exist_ok=True)
    for port in ([preferred] if preferred is not None else range(8100, 8110)):
        stream = (locks / f'joint-q-showdown-{port}.lock').open('a+')
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            check_ports([port])
        except (OSError, BlockingIOError):
            stream.close()
            continue
        stream.seek(0)
        stream.truncate()
        json.dump(dict(pid=os.getpid(), directory=str(directory), port=port), stream)
        stream.flush()
        os.fsync(stream.fileno())
        return port, stream
    raise RuntimeError('no unused owned loopback Showdown port available')


def actor_failure(results):
    """A peer noticing p2's unusable output must not turn it into a shared defect."""
    failed = [value for value in results.values() if value.get('error')]
    if not failed:
        return None
    model = results.get('p2', {})
    isolated = (model.get('failure_scope') == 'battle' and
                model.get('error', {}).get('type') == 'UnusableChoice')
    independent = []
    for value in failed:
        error = value['error']
        peer_notice = (value.get('actor') == 'p1' and error.get('type') == 'RuntimeError' and
                       error.get('detail') == 'opponent technical failure: UnusableChoice')
        if value is not model and not (isolated and peer_notice):
            independent.append(value)
    original = independent[0] if independent else model if isolated else failed[0]
    return original['error'], 'battle' if isolated and not independent else 'collection'


def validate_terminals(results, row):
    if set(results) != {'p1', 'p2'}:
        raise ValueError('both actor terminal results required')
    model, opponent = results['p2'], results['p1']
    complement = dict(player_won='player_lost', player_lost='player_won', tied='tied')
    if (any(not value.get('completed') or value.get('error') for value in results.values()) or
            model.get('outcome') not in complement or opponent.get('outcome') != complement[model['outcome']] or
            model.get('turns') != opponent.get('turns') or model.get('battle_tag') != opponent.get('battle_tag')):
        raise ValueError('actor terminal mismatch')
    for actor, result in results.items():
        seed = row['actor_seeds'][int(actor[-1]) - 1]
        if (result.get('python_random_seed') != seed or result.get('numpy_random_seed') != seed or
                result.get('python_hash_seed') != str(seed) or result.get('actor') != actor):
            raise client.IdentityError('actor seed or role mismatch')
    return model


async def worker(attempt, role):
    import numpy as np
    from poke_env.player.baselines import AbyssalPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from ... import cli, jev_battle as j
    from ...battle_adapter import guard_parser, install_identity_adapter
    from ...jev_study import play
    from .player import Session, player_class

    install_identity_adapter()
    attempt = Path(attempt)
    request = read(attempt / 'request.json')
    seed = request['slot']['actor_seeds'][int(role[-1]) - 1]
    random.seed(seed)
    np.random.seed(seed)
    session, player = None, None
    result = dict(completed=False, pid=os.getpid(), actor=role,
        kind='joint_q' if role == 'p2' else 'abyssal', python_random_seed=seed,
        numpy_random_seed=seed, python_hash_seed=os.environ.get('PYTHONHASHSEED'))
    try:
        if request['profile'] != protocol.PROFILE or request['slot']['joint_actor'] != 'p2':
            raise ValueError('unexpected joint q battle profile or actor')
        if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
            raise ValueError('native battle workers must have no CUDA devices')
        if role == 'p2':
            session = Session(attempt.parent, endpoint=request['endpoint'], identity=request['server'],
                timeout=request['request_seconds'], deadline_monotonic=request['deadline_monotonic'])
        team = request['teams'][request['slot']['teams'][int(role[-1]) - 1]]
        common = dict(team=team_submission(team), battle_format='gen9ou', max_concurrent_battles=1,
            start_timer_on_battle_start=False,
            account_configuration=AccountConfiguration(request['names'][role], None),
            server_configuration=ServerConfiguration(f'localhost:{request["port"]}',
                'https://play.pokemonshowdown.com/action.php?'))
        if session is not None:
            player = player_class()(session=session, expected_actor=role, **common)
            player.submitted_team = team['showdown_team']
            record_sends(player, session)
        else:
            player = AbyssalPlayer(**common)
            guard_parser(player)
        result.update(await play(player, role, request['names'], attempt, session=session,
                                 deadline=request['deadline_monotonic']))
    except j.UnusableChoice as exc:
        result.update(error=error_record(exc), failure_scope='battle')
    except BaseException as exc:
        result.update(error=error_record(exc), failure_scope='collection')
    finally:
        cleanup_errors = []
        if player is not None:
            try:
                await cli._close_players([player])
                if getattr(player, 'official', None):
                    player.official.close()
            except BaseException as exc:
                cleanup_errors.append(error_record(exc))
        if session is not None:
            try:
                await asyncio.to_thread(session.close)
            except BaseException as exc:
                cleanup_errors.append(error_record(exc))
        if cleanup_errors:
            result.update(cleanup_errors=cleanup_errors, prior_error=result.get('error'),
                error=dict(type='CleanupError', detail='native worker cleanup failed'), failure_scope='collection')
        atomic(attempt / f'{role}.result.json', result)
    return result


def _validate_game(directory, plan, row, deadline_at):
    if (plan.get('experiment_id') != 'EX-081' or plan.get('profile') != protocol.PROFILE or
            plan.get('limits') != LIMITS or row.get('joint_actor') != 'p2' or
            row not in plan.get('schedule', [])):
        raise ValueError('unregistered EX081 game or limits')
    if type(deadline_at) not in (int, float) or not math.isfinite(deadline_at):
        raise ValueError('absolute cumulative deadline required')
    if deadline_at - time.time() < LIMITS['battle_seconds'] + LIMITS['cleanup_reserve_seconds']:
        raise TimeoutError('full battle cap plus finalization reserve required before admission')
    game = (directory / row['directory']).resolve()
    live = (directory / row['live_directory']).resolve()
    if not game.is_relative_to(directory) or live != game / 'live' or game == directory:
        raise ValueError('game artifact paths must stay in their own directory')
    if game.exists():
        raise FileExistsError('game was already admitted; recollection is forbidden: ' + row['game_id'])
    return game, live


def run_game(directory, plan, row, endpoint, deadline_at):
    """Run one registered row; ``directory`` is the experiment root, deadline UNIX seconds."""
    from ... import cli
    from ...benchmark import terminate
    from ...parallel_server import BattleServer
    from ...qwen_viewer import seal
    from .audit import audit

    directory = Path(directory).resolve()
    endpoint = client.base_url(endpoint)
    game, live = _validate_game(directory, plan, row, deadline_at)
    verify_sources(plan)
    health = client.health(endpoint, plan['server'])
    game.mkdir(parents=True, exist_ok=False)
    live.mkdir()
    (live / 'events.jsonl').touch(exist_ok=False)
    attempt = live / 'battle-1'
    attempt.mkdir()
    local = dict(row, slot=1)
    started, started_at = time.monotonic(), time.time()
    deadline = started + min(LIMITS['battle_seconds'], deadline_at - started_at - LIMITS['cleanup_reserve_seconds'])
    identity = hashlib.sha256(f'{directory}:{row["game_id"]}'.encode()).hexdigest()[:12]
    names = dict(p1='aby' + identity, p2='jq' + identity)
    outcome = dict(local, actor='p2', username=names['p2'], started_at=started_at,
                   status='running', completed=False, valid=False, audit_passed=False)
    error, cleanup_errors, processes, logs = None, [], {}, []
    server, port_lock = None, None

    def interrupted(signum, _frame):
        raise InterruptedError('EX081 battle coordinator received signal ' + str(signum))

    previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        port, port_lock = reserve_port(attempt, plan.get('showdown_port'))
        manifest = dict(plan, schedule=[local], teams={key: plan['teams'][key] for key in row['teams']},
            global_planned=LIMITS['games'], global_slot=row['global_slot'], game_id=row['game_id'],
            model=plan['server'], port=port, endpoint=endpoint, server_endpoint=endpoint + '/evaluate',
            configuration_sha256=sha(directory / 'configuration.json'))
        atomic(live / 'manifest.json', manifest, immutable=True)
        atomic(attempt / 'request.json', dict(slot=local, teams=manifest['teams'], names=names,
            deadline_monotonic=deadline, deadline_at=started_at + (deadline - started),
            started_at=started_at, cumulative_deadline_at=deadline_at, profile=protocol.PROFILE,
            request_seconds=LIMITS['request_seconds'], port=port, endpoint=endpoint,
            server=plan['server']), immutable=True)
        atomic(attempt / 'server-before.json', health)
        server = BattleServer(attempt, port, row['battle_seed'])
        server.start()
        for actor in ('p1', 'p2'):
            log = (attempt / f'{actor}.log').open('xb')
            logs.append(log)
            env = cli._child_environment(PYTHONPATH=f'{ROOT}:{ROOT / "pokechamp"}',
                PYTHONHASHSEED=str(row['actor_seeds'][int(actor[-1]) - 1]), CUDA_VISIBLE_DEVICES='',
                OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
            processes[actor] = subprocess.Popen([str(NATIVE), '-m', MODULE, 'worker',
                '--attempt', str(attempt), '--role', actor], cwd=ROOT / 'pokechamp', env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        next_guard = time.monotonic() + 30
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('EX081 individual/cumulative battle deadline')
            if time.monotonic() >= next_guard:
                atomic(attempt / 'server-latest.json', client.health(endpoint, plan['server']))
                verify_sources(plan)
                next_guard = time.monotonic() + 30
            results = {actor: read(attempt / f'{actor}.result.json') for actor in processes
                       if (attempt / f'{actor}.result.json').exists()}
            failure = actor_failure(results)
            if failure is not None:
                error, scope = failure
                outcome.update(error=error, failure_scope=scope, actor_results=results,
                    outcome='output_failure' if scope == 'battle' else 'technical_failure')
                break
            if len(results) == 2:
                model = validate_terminals(results, row)
                outcome.update(completed=True, outcome=model['outcome'], turns=model['turns'],
                               battle_tag=model['battle_tag'], actor_results=results)
                break
            for actor, process in processes.items():
                if process.poll() is not None and actor not in results:
                    raise RuntimeError('worker exited without result: ' + actor)
            time.sleep(.2)
    except BaseException as exc:
        error = error_record(exc)
        outcome.update(error=error, failure_scope='collection', outcome='technical_failure')
    finally:
        # This process owns each Popen process group and only its detached worktree.
        atomic(attempt / 'cancel.json', dict(reason='attempt ended'))
        for process in processes.values():
            try:
                terminate(process)
            except BaseException as exc:
                cleanup_errors.append(error_record(exc))
        for log in logs:
            log.close()
        if server is not None:
            try:
                server.close()
            except BaseException as exc:
                cleanup_errors.append(error_record(exc))
        if port_lock is not None:
            port_lock.close()
        outcome.update(server_cleaned=server is None or (not server.created and
            (server.process is None or server.process.poll() is not None)),
            actors_cleaned=all(process.poll() is not None for process in processes.values()))
        atomic(attempt / 'outcome.json', outcome)
        signal.signal(signal.SIGTERM, previous_handler)
    result = dict(planned=1, attempted=1, completed=int(outcome['completed']),
        failed=int(not outcome['completed']), unattempted=0, outcomes=[outcome], error=error,
        cleanup_errors=cleanup_errors, elapsed_seconds=time.monotonic() - started,
        explanation_review='미평가(기본 제외)', live_directory=row['live_directory'])
    try:
        check = audit(live, result)
        atomic(attempt / 'audit.json', check)
        outcome['audit_passed'] = check['passed']
        if not check['passed']:
            raise client.IdentityError('joint q per-decision evidence audit failed')
        verify_sources(plan)
        atomic(attempt / 'server-after.json', client.health(endpoint, plan['server']))
    except BaseException as exc:
        result['postprocessing_error'] = error_record(exc)
        outcome['failure_scope'] = 'collection'
    valid = (outcome['completed'] and outcome['audit_passed'] and not error and
             not cleanup_errors and not result.get('postprocessing_error'))
    isolated = (outcome.get('failure_scope') == 'battle' and outcome['audit_passed'] and
                not cleanup_errors and not result.get('postprocessing_error'))
    outcome.update(valid=bool(valid), invalid=bool(outcome['completed'] and not valid),
        status='complete' if valid else 'failed', elapsed_seconds=time.monotonic() - started)
    result.update(passed=bool(valid), valid=bool(valid), valid_completed=int(bool(valid)),
        failure_scope=outcome.get('failure_scope'),
        wins=int(bool(valid) and outcome.get('outcome') == 'player_won'),
        draws=int(bool(valid) and outcome.get('outcome') == 'tied'),
        losses=int(bool(valid) and outcome.get('outcome') == 'player_lost'),
        continue_allowed=bool(valid or isolated))
    atomic(attempt / 'outcome.json', outcome)
    atomic(live / 'result.json', result)
    seal(live)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    worker_parser = sub.add_parser('worker')
    worker_parser.add_argument('--attempt', type=Path, required=True)
    worker_parser.add_argument('--role', choices=('p1', 'p2'), required=True)
    game_parser = sub.add_parser('game')
    game_parser.add_argument('--directory', type=Path, required=True)
    game_parser.add_argument('--plan', type=Path, required=True)
    game_parser.add_argument('--game-id', required=True)
    game_parser.add_argument('--endpoint', required=True)
    game_parser.add_argument('--deadline-at', type=float, required=True)
    args = parser.parse_args(argv)
    if args.command == 'worker':
        result = asyncio.run(worker(args.attempt, args.role))
        success = not result.get('error')
    else:
        plan = read(args.plan)
        matches = [row for row in plan['schedule'] if row['game_id'] == args.game_id]
        if len(matches) != 1:
            raise ValueError('exactly one registered game ID required')
        result = run_game(args.directory, plan, matches[0], args.endpoint, args.deadline_at)
        success = result['continue_allowed']
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if not success:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
