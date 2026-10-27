"""EX-069: one pass over the original EX-065 test20 battle metadata."""
from __future__ import annotations

from integration.project_context.registry import record_aliases, record_relative

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from . import kev_control as control
from .branch_rollouts.common import file_hash, read, write

ROOT = control.ROOT
SOURCE = control.SOURCE
OUTPUT = ROOT / '.pokechamp-data/kev/ex069'
ADMISSION = ROOT / '.pokechamp-data/kev/ex069-battle-admission.json'
PREVIOUS = ROOT / '.pokechamp-data/kev/ex068-v3'
QUALIFICATION = ROOT / 'project_context/exec-plans/evidence/ep111-fused/verification-final.json'
PROTOCOL = record_relative('EX-069', prefix=True)
DECISION = record_relative('D-110', prefix=True)
MANIFEST_SHA256 = 'e1d1f15a64746e0ce5888de42846cf3f16eb25638f64183cbdae1ed6a5ea71ef'
TEST_TEAMS = (100817, 7627, 38229, 48494, 5742)
LIMITS = dict(games=20, request_seconds=600, battle_seconds=1800, total_seconds=14400,
              no_new_match_remaining_seconds=600, cleanup_reserve_seconds=60,
              concurrency=1, retries=0, fallback=0, recollection=0)
PRECHECKS = dict(unit_tests='skipped_by_user', validation_replay='skipped_by_user',
                 validation_predictions='skipped_by_user', smoke='skipped_by_user')


class ProvenanceError(ValueError):
    pass


def configuration():
    """Read only the registered manifest's teams and game/seed metadata."""
    manifest_path = SOURCE / 'manifest.json'
    if file_hash(manifest_path) != MANIFEST_SHA256:
        raise ProvenanceError('registered EX-065 metadata manifest changed')
    manifest = read(manifest_path)
    games = [(index, row) for index, row in enumerate(manifest['games']) if row['split'] == 'test']
    expected = [(team, seed) for team in TEST_TEAMS for seed in range(4)]
    if (manifest['actor'] != 'p2' or len(games) != 20 or
            [(row['team_number'], row['seed_index']) for _, row in games] != expected or
            len({row['game_id'] for _, row in games}) != 20):
        raise ProvenanceError('EX-065 test20 order, teams, seeds or actor changed')
    own = manifest['own']
    teams = dict(own=dict(showdown_team=own['text'], packed=own['packed'],
        source=str(manifest_path), sha256=MANIFEST_SHA256))
    opponents = {row['number']: row for row in manifest['opponents'] if row['split'] == 'test'}
    if set(opponents) != set(TEST_TEAMS):
        raise ProvenanceError('EX-065 test opponent metadata changed')
    for number in TEST_TEAMS:
        row = opponents[number]
        if not row['legal'] or file_hash(row['source']) != row['original_sha256']:
            raise ProvenanceError('EX-065 opponent source changed: ' + str(number))
        teams['opponent' + str(number)] = dict(number=number, showdown_team=row['text'], packed=row['packed'],
            source=row['source'], sha256=row['original_sha256'], group_id=row['group_id'],
            ex065_packed_sha256=hashlib.sha256(row['packed'].encode()).hexdigest())
    schedule = []
    for slot, (source_index, game) in enumerate(games, 1):
        game_id = game['game_id']
        if game_id != f'test-t{game["team_number"]}-s{game["seed_index"]}':
            raise ProvenanceError('unexpected original game_id')
        relative = f'games/{slot:03}-{game_id}'
        schedule.append(dict(slot=slot, global_slot=slot, slot_id=game_id, game_id=game_id,
            directory=relative, live_directory=relative + '/live', source_manifest_index=source_index,
            split='test', team_number=game['team_number'], seed_index=game['seed_index'],
            group_id=game['group_id'], teams=['opponent' + str(game['team_number']), 'own'],
            kev_actor='p2', simulator_seed=game['simulator_seed'],
            battle_seed=','.join(map(str, game['simulator_seed'])),
            actor_seeds=[game['actor_seeds']['p1'], game['actor_seeds']['p2']]))
    return dict(experiment_id='EX-069', execution_version='ex069-v1', profile='kev-joint-noul-v1',
        schema_version='pokemon-joint-q-input-v1', teams=teams, schedule=schedule,
        ex065_manifest_sha256=MANIFEST_SHA256, serving=control.SERVING,
        tera_allowed=True, timer_enabled=False, limits=LIMITS, prechecks=PRECHECKS,
        baseline_access='analysis_only_after_configuration_freeze',
        test_access='manifest_team_and_seed_metadata_only', explanation_review='미평가(기본 제외)')


def sources():
    result = control.sources()
    for name in ('scripts/pokechamp-kev-main', PROTOCOL, DECISION):
        result[name] = file_hash(ROOT / name)
    return result


def prior_qualification():
    """Reference completed acceptance; never repeat a validation or model request."""
    accepted = read(QUALIFICATION)
    if accepted.get('passed') is not True or accepted.get('full_acceptance') is not True:
        raise ProvenanceError('completed EX-068 v3 acceptance receipt required')
    seal = PREVIOUS / 'checksums.sha256'
    expected = accepted['seal_receipts']['.pokechamp-data/kev/ex068-v3']['sha256']
    if file_hash(seal) != expected:
        raise ProvenanceError('EX-068 v3 acceptance seal changed')
    entries = dict(line.split('  ', 1)[::-1] for line in seal.read_text().splitlines())
    names = ('configuration.json', 'probe.json', 'live/result.json')
    files = {name: file_hash(PREVIOUS / name) for name in names}
    if any(entries.get(name) != checksum for name, checksum in files.items()):
        raise ProvenanceError('EX-068 v3 acceptance metadata changed')
    live_seal = file_hash(PREVIOUS / 'live/checksums.sha256')
    if live_seal != accepted['seal_receipts']['.pokechamp-data/kev/ex068-v3/live']['sha256']:
        raise ProvenanceError('EX-068 v3 live acceptance seal changed')
    return dict(directory=str(PREVIOUS), verification=dict(path=str(QUALIFICATION),
        sha256=file_hash(QUALIFICATION)), seal_sha256=expected, live_seal_sha256=live_seal, files=files)


def _reuse_identity(plan):
    previous = read(PREVIOUS / 'configuration.json')
    for key in ('checkpoint', 'data_identity', 'serving', 'worker_assets'):
        if plan[key] != previous[key]:
            raise ProvenanceError('accepted EX-068 v3 identity differs: ' + key)
    if plan['teams']['own'] != previous['teams']['own']:
        raise ProvenanceError('EX-065 own packed team/text changed')
    for name, checksum in previous['source'].items():
        # Its completed status was updated after the sealed EX-068 execution.
        if name in record_aliases('EX-068', prefix=True):
            continue
        if plan['source'].get(name) != checksum:
            raise ProvenanceError('accepted runtime source changed: ' + name)
    assets = ROOT / 'pokechamp/poke_env/data/static/gen9/ou/sets_1500.json'
    if file_hash(assets) != plan['worker_assets']['sha256']:
        raise ProvenanceError('accepted worker static assets changed')


def prepare(directory=OUTPUT):
    """Metadata/source/model freeze only; all additional prechecks remain skipped."""
    from . import cli
    directory = Path(directory).resolve()
    if directory.exists():
        raise FileExistsError('preserve the existing EX-069 preparation')
    cli._assert_submodule_pins(require_clean=True)
    previous = read(PREVIOUS / 'configuration.json')
    plan = dict(configuration(), source=sources(), data_identity=control.data_identity(),
        checkpoint=control.model_identity(), worker_assets=previous['worker_assets'],
        prior_qualification=prior_qualification(), created_at=time.time(),
        authorization=dict(decision='D-110', path=DECISION, sha256=file_hash(ROOT / DECISION),
            protocol=PROTOCOL, protocol_sha256=file_hash(ROOT / PROTOCOL)))
    _reuse_identity(plan)
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / 'configuration.json', plan)
    for relative in plan['source']:
        target = directory / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
        if file_hash(target) != plan['source'][relative]:
            raise ProvenanceError('source changed while copying: ' + relative)
    receipt = dict(passed=True, configuration_sha256=file_hash(directory / 'configuration.json'),
        preparation='metadata_source_model_identity_freeze_only', prechecks=PRECHECKS,
        prior_qualification=plan['prior_qualification'], planned=20,
        model_requests=0, battle_attempts=0, gpu_jobs_started=0)
    write(directory / 'prepared.json', receipt)
    return receipt


def verify_prepared(directory, *, model=False):
    directory = Path(directory)
    receipt, plan = read(directory / 'prepared.json'), read(directory / 'configuration.json')
    if not receipt.get('passed') or receipt['configuration_sha256'] != file_hash(directory / 'configuration.json'):
        raise ProvenanceError('EX-069 prepared configuration changed')
    if any(plan.get(key) != value for key, value in configuration().items()):
        raise ProvenanceError('EX-069 team/seed schedule or runtime limits changed')
    if plan['source'] != sources() or plan['data_identity'] != control.data_identity():
        raise ProvenanceError('EX-069 source/data changed after preparation')
    for relative, checksum in plan['source'].items():
        if file_hash(directory / 'source' / relative) != checksum:
            raise ProvenanceError('EX-069 frozen source copy changed: ' + relative)
    if plan['prior_qualification'] != prior_qualification():
        raise ProvenanceError('EX-068 acceptance reference changed')
    _reuse_identity(plan)
    if model and plan['checkpoint'] != control.model_identity():
        raise ProvenanceError('EX-069 checkpoint/server source changed')
    return plan


def process_guard(serving):
    """Cheap runtime ownership/GPU checks; does not send a model request."""
    process = control._server_process()
    identity = serving['identity']
    if any(identity.get(key) != value for key, value in process.items()):
        raise ProvenanceError('Kev process or serving options changed during EX-069')
    if control._listener_owned(process['pid']) != identity['listener_inode']:
        raise ProvenanceError('Kev HTTP listener changed during EX-069')
    rows = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
                                    '--format=csv,noheader'], text=True)
    gpu = control._gpu_process_identity(process, identity['gpu_uuid'], rows)
    if any(identity.get(key) != value for key, value in gpu.items()):
        raise ProvenanceError('GPU3 process ownership changed during EX-069')
    return dict(passed=True, at=time.time(), process=process, gpu=gpu)


def _error(error):
    return dict(type=type(error).__name__, detail=str(error))


def _match(directory, plan, row, serving, cumulative_deadline, *, source_provider=sources):
    """Reuse the accepted workers unchanged; every game has one private Session."""
    from . import cli
    from .benchmark import terminate
    from .parallel_server import BattleServer
    from .kev_audit import audit
    from .qwen_viewer import seal

    limits = plan['limits']
    live = directory / row['live_directory']
    live.mkdir(parents=True, exist_ok=False)
    local = dict(row, slot=1)
    manifest = dict(plan, schedule=[local], teams={key: plan['teams'][key] for key in row['teams']},
        global_planned=limits['games'], global_slot=row['global_slot'], game_id=row['game_id'],
        model=serving['models'], server=serving, port=8109,
        configuration_sha256=file_hash(directory / 'configuration.json'))
    write(live / 'manifest.json', manifest)
    (live / 'events.jsonl').touch(exist_ok=False)
    attempt = live / 'battle-1'
    attempt.mkdir()
    identity = hashlib.sha256(f'{directory}:{row["game_id"]}'.encode()).hexdigest()[:12]
    names = dict(p1='aby' + identity, p2='kev' + identity)
    started, started_at = time.monotonic(), time.time()
    deadline = min(started + limits['battle_seconds'], cumulative_deadline - limits['cleanup_reserve_seconds'])
    write(attempt / 'request.json', dict(slot=local, teams=manifest['teams'], names=names,
        deadline_monotonic=deadline, started_at=started_at, cumulative_deadline_monotonic=cumulative_deadline,
        profile=plan['profile'], request_seconds=limits['request_seconds']))
    server = BattleServer(attempt, 8109, row['battle_seed'])
    outcome = dict(local, username=names['p2'], completed=False, audit_passed=False,
                   started_at=started_at, status='running')
    error, cleanup_errors, processes, logs = None, [], {}, []
    try:
        write(attempt / 'server-before.json', process_guard(serving))
        server.start()
        for actor in ('p1', 'p2'):
            log = (attempt / f'{actor}.log').open('xb')
            logs.append(log)
            env = cli._child_environment(PYTHONPATH=f'{ROOT}:{ROOT / "pokechamp"}',
                PYTHONHASHSEED=str(row['actor_seeds'][int(actor[-1]) - 1]), CUDA_VISIBLE_DEVICES='',
                OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
            env.pop('KEV_API_KEY', None)
            if actor == 'p2' and os.environ.get('KEV_API_KEY'):
                env['KEV_API_KEY'] = os.environ['KEV_API_KEY']
            processes[actor] = subprocess.Popen([sys.executable, '-m', 'integration.pokechamp.kev_battle',
                'worker', '--attempt', str(attempt), '--role', actor], cwd=ROOT / 'pokechamp',
                env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        next_guard = time.monotonic() + 30
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError(plan['experiment_id'] + ' individual/cumulative battle deadline')
            if time.monotonic() >= next_guard:
                write(attempt / 'server-latest.json', process_guard(serving))
                if source_provider() != plan['source']:
                    raise ProvenanceError(plan['experiment_id'] + ' runtime source changed during a battle')
                next_guard = time.monotonic() + 30
            results = {actor: read(attempt / f'{actor}.result.json') for actor in processes
                       if (attempt / f'{actor}.result.json').exists()}
            failed = [result for result in results.values() if result.get('error')]
            if failed:
                shared = [result for result in failed if result.get('actor') != 'p2' or
                          result.get('failure_scope') != 'battle' or result['error'].get('type') != 'UnusableChoice']
                original = (shared or failed)[0]
                isolated = not shared
                error = original['error']
                outcome.update(error=error, failure_scope='battle' if isolated else 'collection',
                    outcome='output_failure' if isolated else 'technical_failure', actor_results=results)
                break
            if len(results) == 2:
                kev, opponent = results['p2'], results['p1']
                complement = dict(player_won='player_lost', player_lost='player_won', tied='tied')
                if (not all(result['completed'] for result in results.values()) or
                        opponent['outcome'] != complement[kev['outcome']] or kev['turns'] != opponent['turns']):
                    raise ValueError('actor terminal mismatch')
                for actor, result in results.items():
                    seed = row['actor_seeds'][int(actor[-1]) - 1]
                    if (result['python_random_seed'] != seed or result['numpy_random_seed'] != seed or
                            result['python_hash_seed'] != str(seed) or result['actor'] != actor):
                        raise ProvenanceError('actor seed or role mismatch')
                outcome.update(completed=True, outcome=kev['outcome'], turns=kev['turns'],
                               battle_tag=kev['battle_tag'], actor_results=results)
                break
            for actor, process in processes.items():
                if process.poll() is not None and actor not in results:
                    raise RuntimeError('worker exited without result: ' + actor)
            time.sleep(.2)
    except BaseException as exc:
        error = _error(exc)
        outcome.update(error=error, failure_scope='collection', outcome='technical_failure')
    finally:
        write(attempt / 'cancel.json', dict(reason='attempt ended'))
        for process in processes.values():
            try:
                terminate(process)
            except Exception as exc:
                cleanup_errors.append(_error(exc))
        for log in logs:
            log.close()
        try:
            server.close()
        except Exception as exc:
            cleanup_errors.append(_error(exc))
        outcome.update(server_cleaned=not server.created and (server.process is None or server.process.poll() is not None),
                       actors_cleaned=all(process.poll() is not None for process in processes.values()))
        write(attempt / 'outcome.json', outcome)
    result = dict(planned=1, attempted=1, completed=int(outcome['completed']),
        failed=int(not outcome['completed']), unattempted=0, outcomes=[outcome], error=error,
        cleanup_errors=cleanup_errors, elapsed_seconds=time.monotonic() - started,
        explanation_review='미평가(기본 제외)', prechecks=plan['prechecks'])
    try:
        check = audit(live, result)
        write(attempt / 'audit.json', check)
        outcome['audit_passed'] = check['passed']
        if not check['passed']:
            raise ProvenanceError('Kev per-decision evidence audit failed')
        write(attempt / 'server-after.json', process_guard(serving))
    except Exception as exc:
        result['postprocessing_error'] = _error(exc)
        outcome['failure_scope'] = 'collection'
    valid = outcome['completed'] and outcome['audit_passed'] and not error and not cleanup_errors and not result.get('postprocessing_error')
    isolated = (outcome.get('failure_scope') == 'battle' and outcome['audit_passed'] and
                not cleanup_errors and not result.get('postprocessing_error'))
    outcome.update(status='complete' if valid else 'failed', valid=bool(valid), invalid=bool(outcome['completed'] and not valid),
                   elapsed_seconds=time.monotonic() - started)
    result.update(passed=bool(valid), valid_completed=int(bool(valid)),
        wins=int(bool(valid) and outcome.get('outcome') == 'player_won'),
        draws=int(bool(valid) and outcome.get('outcome') == 'tied'),
        losses=int(bool(valid) and outcome.get('outcome') == 'player_lost'),
        continue_allowed=bool(valid or isolated))
    write(attempt / 'outcome.json', outcome)
    write(live / 'result.json', result)
    seal(live)
    return result


def _persist(directory, state):
    outcomes = state['outcomes']
    valid = [row for row in outcomes if row.get('valid')]
    state.update(attempted=len(outcomes), completed=sum(bool(row.get('completed')) for row in outcomes),
        valid_completed=len(valid), failed=sum(row.get('status') == 'failed' and not row.get('completed') for row in outcomes),
        invalid=sum(bool(row.get('invalid')) for row in outcomes),
        in_progress=sum(row.get('status') == 'running' for row in outcomes), unattempted=20 - len(outcomes),
        wins=sum(row.get('outcome') == 'player_won' for row in valid),
        draws=sum(row.get('outcome') == 'tied' for row in valid),
        losses=sum(row.get('outcome') == 'player_lost' for row in valid), updated_at=time.time())
    state['score'] = (state['wins'] + .5 * state['draws']) / len(valid) if valid else None
    state['elapsed_seconds'] = time.monotonic() - state['admission']['monotonic']
    write(directory / 'result.json', state)


def run(directory=OUTPUT):
    directory = Path(directory).resolve()
    plan = verify_prepared(directory)
    serving = control.server_identity()
    if serving['checkpoint'] != plan['checkpoint']:
        raise ProvenanceError('running Kev model differs from accepted frozen checkpoint')
    admission = dict(experiment_id='EX-069', decision='D-110', at=time.time(), monotonic=time.monotonic(),
        planned=20, directory=str(directory), configuration_sha256=file_hash(directory / 'configuration.json'),
        game_ids=[row['game_id'] for row in plan['schedule']], limits=LIMITS, prechecks=PRECHECKS,
        prior_qualification=plan['prior_qualification'])
    control.exclusive_json(ADMISSION, admission)
    write(directory / 'battle-started.json', admission)
    write(directory / 'server-before.json', serving)
    deadline = admission['monotonic'] + LIMITS['total_seconds']
    state = dict(experiment_id='EX-069', planned=20, passed=False, status='running', outcomes=[],
        admission=admission, prechecks=PRECHECKS, error=None, stop_reason=None,
        source_configuration_sha256=admission['configuration_sha256'],
        explanation_review='미평가(기본 제외)')
    _persist(directory, state)

    def interrupted(signum, frame):
        raise InterruptedError('EX-069 coordinator received signal ' + str(signum))

    previous_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        for row in plan['schedule']:
            if deadline - time.monotonic() <= LIMITS['no_new_match_remaining_seconds']:
                state['stop_reason'] = 'cumulative_budget_no_new_match_guard'
                break
            verify_prepared(directory)
            process_guard(serving)
            state['outcomes'].append(dict(row, status='running', completed=False, valid=False, invalid=False))
            _persist(directory, state)
            try:
                result = _match(directory, plan, row, serving, deadline)
            except BaseException as exc:
                state['outcomes'][-1].update(status='failed', error=_error(exc), failure_scope='collection')
                raise
            outcome = dict(result['outcomes'][0], slot=row['global_slot'], local_slot=1,
                live_result_sha256=file_hash(directory / row['live_directory'] / 'result.json'),
                live_seal_sha256=file_hash(directory / row['live_directory'] / 'checksums.sha256'))
            state['outcomes'][-1] = outcome
            _persist(directory, state)
            print(json.dumps(dict(game_id=row['game_id'], global_slot=row['global_slot'],
                completed=outcome['completed'], valid=outcome['valid'], outcome=outcome.get('outcome'),
                attempted=state['attempted'], valid_completed=state['valid_completed']), ensure_ascii=False), flush=True)
            if not result['continue_allowed']:
                state['error'] = result.get('postprocessing_error') or result['error'] or dict(
                    type='CleanupError', detail='owned resource cleanup did not complete')
                state['stop_reason'] = 'shared_technical_failure'
                break
    except BaseException as exc:
        state.update(error=_error(exc), stop_reason='shared_technical_failure')
    finally:
        try:
            verify_prepared(directory)
            after = control.server_identity()
            write(directory / 'server-after.json', after)
            if after['identity'] != serving['identity'] or after['checkpoint'] != plan['checkpoint']:
                raise ProvenanceError('server/checkpoint changed during EX-069')
            state['postrun_provenance_passed'] = True
        except BaseException as exc:
            state.update(postrun_provenance_passed=False, postrun_error=_error(exc))
            # Preserve each sealed local result; this final ledger records the
            # unresolved shared provenance instead of rewriting raw attempts.
            for outcome in state['outcomes']:
                if outcome.get('completed'):
                    outcome.update(valid=False, invalid=True, invalidation='unresolved_shared_final_provenance')
        state['passed'] = (len(state['outcomes']) == 20 and all(row.get('valid') for row in state['outcomes'])
                           and state.get('postrun_provenance_passed') and state['error'] is None)
        state['status'] = 'complete' if state['passed'] else 'incomplete'
        _persist(directory, state)
        signal.signal(signal.SIGTERM, previous_handler)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run'))
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    result = prepare(args.output) if args.command == 'prepare' else run(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get('passed'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
