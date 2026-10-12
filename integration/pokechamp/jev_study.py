"""One-shot EX-052/053/054/056/057 schedules: JEV versus isolated Abyssal."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

from . import jev_battle as j

ROOT = j.ROOT
ORIGIN = ROOT / '.pokechamp-data/b2-lead/ex046-cloud/plan.json'
LIVE = ROOT / '.pokechamp-data/jev/ex052-live'
EVIDENCE = ROOT / 'project_context/exec-plans/evidence/ep073'
RECEIPT = EVIDENCE / 'verification-live.json'
PROFILE = 'jev-abyssal32-v1'
PORT = 8109
COLLECTION_SECONDS = 20100
TOTAL_SECONDS = 21600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def origin_schedule(path=ORIGIN):
    path = Path(path)
    if sha(path) != path.with_suffix('.json.sha256').read_text().strip().split()[0]:
        raise ValueError('EX-046 plan seal mismatch')
    origin = json.loads(path.read_text())
    if origin['registered_experiment'] != 'EX-046':
        raise ValueError('wrong schedule origin')
    rows = []
    for row in origin['schedule']:
        policies = [s['team_preview_policy'] for s in row['actor_settings']]
        if sorted(policies) != ['llm_lead', 'seeded_random']:
            raise ValueError('ambiguous original role mapping')
        rows.append(dict(
            **{k: row[k] for k in ('slot_id', 'paired_slot_id', 'block_id', 'repetition',
                                  'swap', 'teams', 'battle_seed', 'actor_seeds', 'submission_order')},
            origin_provider=row['provider_id'], jev_actor=f'p{policies.index("llm_lead") + 1}',
        ))
    validate_schedule(rows)
    teams = {}
    for key, record in origin['teams'].items():
        p = ROOT / record['source']
        if sha(p) != record['sha256']:
            raise ValueError('sealed team differs from EX-046')
        teams[key] = dict(record, showdown_team=p.read_text())
    return rows, teams, dict(experiment='EX-046', path=str(path.relative_to(ROOT)), sha256=sha(path))


def validate_schedule(rows):
    if len(rows) != 32 or [r['submission_order'] for r in rows] != list(range(1, 33)):
        raise ValueError('expected original ordered 32 slots')
    if len({r['slot_id'] for r in rows}) != 32:
        raise ValueError('duplicate slot')
    blocks = {'b01': ['1', '2'], 'b02': ['6', '2'], 'b03': ['2', '6'], 'b04': ['6', '12']}
    pairs = {}
    for row in rows:
        if row['teams'] != blocks[row['block_id']]:
            raise ValueError('team mismatch')
        if row['repetition'] not in range(1, 5) or row['swap'] not in (0, 1):
            raise ValueError('invalid repeat or swap')
        if row['jev_actor'] != ('p1' if row['swap'] else 'p2'):
            raise ValueError('incorrect JEV role')
        if len(row['actor_seeds']) != 2 or any(type(v) is not int or not 0 <= v < 2**32 for v in row['actor_seeds']):
            raise ValueError('invalid actor seeds')
        parts = row['battle_seed'].split(',')
        if len(parts) != 4 or any(not v.isdecimal() or not 0 <= int(v) < 65536 for v in parts):
            raise ValueError('invalid game seed')
        if row['paired_slot_id'] != f"{row['block_id']}-r{row['repetition']}" or row['slot_id'] != f"{row['paired_slot_id']}-s{row['swap']}":
            raise ValueError('invalid slot identity')
        pairs.setdefault(row['paired_slot_id'], []).append(row)
    if len(pairs) != 16:
        raise ValueError('expected 16 pairs')
    for pair in pairs.values():
        if len(pair) != 2 or {r['jev_actor'] for r in pair} != {'p1', 'p2'}:
            raise ValueError('missing swapped pair')
        if any(pair[0][k] != pair[1][k] for k in ('teams', 'battle_seed', 'actor_seeds')):
            raise ValueError('pair settings differ')


def baseline_manifest(path=None):
    path = Path(path or LIVE / 'manifest.json')
    seals = dict(line.split('  ', 1)[::-1] for line in (path.parent / 'checksums.sha256').read_text().splitlines())
    if seals.get(path.name) != sha(path):
        raise ValueError('EX-052 manifest seal mismatch')
    manifest = json.loads(path.read_text())
    if manifest['experiment_id'] != 'EX-052' or manifest['schema_version'] != j.V2_INPUT_VERSION:
        raise ValueError('wrong v2 baseline identity')
    validate_schedule(manifest['schedule'])
    if j.digest(manifest['schedule']) != manifest['schedule_sha256']:
        raise ValueError('baseline schedule hash mismatch')
    for team in manifest['teams'].values():
        if hashlib.sha256(team['showdown_team'].encode()).hexdigest() != team['sha256'] or sha(ROOT / team['source']) != team['sha256']:
            raise ValueError('baseline team hash mismatch')
    return manifest


def experiment_settings(experiment):
    if experiment == 'EX-052':
        return LIVE, RECEIPT, 'EP-073', j.V2_INPUT_VERSION
    if experiment == 'EX-053':
        return (ROOT / '.pokechamp-data/jev/ex053-live',
                ROOT / 'project_context/exec-plans/evidence/ep075/verification-live.json',
                'EP-075', 'jev-choice-v3')
    if experiment == 'EX-054':
        return (ROOT / '.pokechamp-data/jev/ex054-live',
                ROOT / 'project_context/exec-plans/evidence/ep077/verification-live.json',
                'EP-077', 'jev-choice-v3')
    if experiment == 'EX-056':
        return (ROOT / '.pokechamp-data/jev/ex056-live',
                ROOT / 'project_context/exec-plans/evidence/ep080/entry-record.json',
                'EP-080', 'jev-choice-v3')
    if experiment == 'EX-057':
        return (ROOT / '.pokechamp-data/jev/ex057-live',
                ROOT / 'project_context/exec-plans/evidence/ep081/entry-record.json',
                'EP-081', 'jev-choice-v3')
    if experiment == 'EX-058':
        return (ROOT / '.pokechamp-data/jev/ex058-live',
                ROOT / 'project_context/exec-plans/evidence/ep094/local-verification.json',
                'EP-094', 'jev-choice-v4')
    if experiment == 'EX-059':
        return (ROOT / '.pokechamp-data/jev/ex059-live',
                ROOT / 'project_context/exec-plans/evidence/ep095/local-verification.json',
                'EP-095', 'jev-choice-v5')
    raise ValueError('unknown JEV experiment')


def v3_identity(rows, teams, origin, config, sources, experiment="EX-053"):
    from .observation.build import verify
    identity = dict(experiment_id=experiment, schema_version='jev-choice-v3',
                validation_version=j.VALIDATION_VERSION, initial_pp_policy=j.INITIAL_PP_POLICY,
                prompt_sha256=sha(j.PROMPT.with_name('jev-choice-v3.txt')),
                effect_reference_identity=j.effects.identity(), source=sources,
                observation_build=verify(), schedule_sha256=j.digest(rows),
                teams_sha256=j.digest(teams), schedule_origin=origin, model=config,
                limits=dict(games=32, calls=None, collection_seconds=COLLECTION_SECONDS,
                            total_seconds=TOTAL_SECONDS, concurrency=1, retries=3 if experiment in ('EX-054', 'EX-056', 'EX-057') else 0, recollection=0))
    if experiment == 'EX-054':
        identity.update(transport_policy=j.jev_retry.V1, retry_delays_seconds=list(j.jev_retry.delays_for(j.jev_retry.V1)),
                        repeat_source_sha256=sha(ROOT / '.pokechamp-data/jev/ex053-live/manifest.json'))
    if experiment in ('EX-056', 'EX-057'):
        identity.update(transport_policy=j.jev_retry.CURRENT,
                        retry_delays_seconds=list(j.jev_retry.delays_for(j.jev_retry.CURRENT)),
                        repeat_source_sha256=sha(ROOT / ('.pokechamp-data/jev/ex056-live/manifest.json' if experiment == 'EX-057' else '.pokechamp-data/jev/ex054-live/manifest.json')))
    return identity


def study_schedule(experiment):
    if experiment == 'EX-052':
        return origin_schedule()
    experiment_settings(experiment)
    baseline = baseline_manifest()
    if experiment in ('EX-054', 'EX-056', 'EX-057', 'EX-058', 'EX-059'):
        previous_id = {'EX-054': 'EX-053', 'EX-056': 'EX-054', 'EX-057': 'EX-056', 'EX-058': 'EX-057', 'EX-059': 'EX-058'}[experiment]
        path = ROOT / f'.pokechamp-data/jev/{previous_id.lower().replace("-", "")}-live/manifest.json'
        seals = dict(line.split('  ', 1)[::-1] for line in (path.parent / 'checksums.sha256').read_text().splitlines())
        if sha(path) != seals['manifest.json']:
            raise ValueError(previous_id + ' manifest seal mismatch')
        previous = json.loads(path.read_text())
        if previous['experiment_id'] != previous_id or previous['schema_version'] != ('jev-choice-v4' if experiment == 'EX-059' else 'jev-choice-v3'):
            raise ValueError('wrong repeat origin')
        for key in ('schedule', 'teams', 'model'):
            expected = dict(baseline[key], model='jev-1.13.0') if key == 'model' and experiment in ('EX-058', 'EX-059') else baseline[key]
            if previous[key] != expected:
                raise ValueError('EX-053/052 baseline mismatch: ' + key)
        if previous['prompt'] != j.PROMPT.with_name('jev-choice-v4.txt' if experiment == 'EX-059' else 'jev-choice-v3.txt').read_text() or previous['effect_reference_identity'] != j.effects.identity():
            raise ValueError('EX-053 v3 treatment drift')
        return previous['schedule'], previous['teams'], dict(experiment=previous_id, path=str(path.relative_to(ROOT)), sha256=sha(path))
    return baseline['schedule'], baseline['teams'], dict(
        experiment='EX-052', path=str((LIVE / 'manifest.json').relative_to(ROOT)),
        sha256=sha(LIVE / 'manifest.json'))


def configuration(experiment='EX-052'):
    from .jev import JevClient
    from .dotenv import load_workspace_credential
    env = dict(os.environ)
    load_workspace_credential(environ=env)
    with JevClient.from_env(environ=env) as client:
        config = dict(model=client.model, endpoint=client.endpoint)
    previous = (baseline_manifest()['model'] if experiment in ('EX-053', 'EX-054', 'EX-056', 'EX-057', 'EX-058', 'EX-059') else
                json.loads((ROOT / '.pokechamp-data/jev/ex051-live/manifest.json').read_text())['model'])
    if experiment in ('EX-057', 'EX-058', 'EX-059'):
        previous = dict(previous, model='jev-1.13.0')
    if config != previous:
        raise ValueError('JEV provider settings differ from sealed baseline')
    env.update(TYPESAFE_MODEL=config['model'], TYPESAFE_BASE_URL=config['endpoint'].removesuffix('/systemone'))
    return config, env


class StudySession(j.Session):
    def __init__(self, directory, *, fake=False, environ=None, retry_policy=j.jev_retry.CURRENT):
        super().__init__(directory, fake=fake, environ=environ, call_limit=None,
                         collection_seconds=COLLECTION_SECONDS, retry_policy=retry_policy)

    async def evaluate(self, payload, *, decision=None):
        if self.fake and self.retry_policy == j.jev_retry.LEGACY:
            self.record(dict(type='transport', endpoint='mock://local/systemone', model='jev-latest',
                             decision=decision, request_number=self.calls + 1, timeout=min(60, self.remaining())))
        return await super().evaluate(payload, decision=decision)


def summarize(session, outcomes, schedule, error=None):
    inputs = {e['decision']: e for e in session.records if e['type'] == 'input'}
    selected = {e['decision']: e for e in session.records if e['type'] == 'selection'}
    responses = [e for e in session.records if e['type'] == 'response']
    wires = [e for e in session.records if e['type'] == 'wire']
    transports = [e for e in session.records if e['type'] == 'transport']
    action_audit = all(w['decision'] in selected and selected[w['decision']]['command'] == w['command']
                       == inputs[w['decision']]['commands'][selected[w['decision']]['choice']] for w in wires)
    valid = [o for o in outcomes if o.get('completed') and o.get('audit_passed')]
    points = {'player_won': 1., 'tied': .5, 'player_lost': 0.}
    paired = {}
    for o in valid:
        paired.setdefault(o['paired_slot_id'], []).append(points[o['outcome']])
    pair_scores = {k: sum(v) / 2 for k, v in paired.items() if len(v) == 2}
    def scores(items):
        return dict(games=len(items), wins=sum(o['outcome'] == 'player_won' for o in items),
                    draws=sum(o['outcome'] == 'tied' for o in items), losses=sum(o['outcome'] == 'player_lost' for o in items),
                    score=sum(points[o['outcome']] for o in items) / len(items) if items else None)
    result = dict(planned=len(schedule), attempted=len(outcomes), completed=len(valid),
                  failed=sum(not o.get('completed') for o in outcomes),
                  invalid=sum(o.get('completed', False) and not o.get('audit_passed', False) for o in outcomes),
                  unattempted=len(schedule) - len(outcomes), outcomes=outcomes,
                  requests=session.calls, external_requests=0 if session.fake else session.calls,
                  received_responses=len(responses), unanswered_requests=session.calls - len(responses),
                  sent_actions=len(wires), action_audit_passed=action_audit,
                  automatic_actions=sum(e['automatic'] for e in selected.values()),
                  tokens={k: sum(r['body'].get('usage', {}).get(k, 0) for r in responses) for k in ('input_tokens', 'output_tokens')},
                  missing_usage_responses=sum(not isinstance(r['body'].get('usage'), dict) or any(k not in r['body']['usage'] for k in ('input_tokens', 'output_tokens')) for r in responses),
                  latency_seconds=[r['elapsed_seconds'] for r in responses],
                  actual_models=sorted({r['body']['model'] for r in responses}),
                  judgment_diagnostics=[e for e in session.records if e['type'] == 'judgment_diagnostics' and e['diagnostics']],
                  elapsed_collection_seconds=0 if session.started is None else session.collection_seconds - session.remaining(),
                  first_request_at=session.started, collection_deadline=None if session.started is None else session.started + COLLECTION_SECONDS,
                  cleanup_deadline=None if session.started is None else session.started + TOTAL_SECONDS,
                  completed_pairs=len(pair_scores), pair_scores=pair_scores,
                  mean_pair_score=sum(pair_scores.values()) / len(pair_scores) if pair_scores else None,
                  overall=scores(valid),
                  by_block={b: scores([o for o in valid if o['block_id'] == b]) for b in sorted({r['block_id'] for r in schedule})},
                  by_actor={a: scores([o for o in valid if o['jev_actor'] == a]) for a in ('p1', 'p2')},
                  error=error, efficacy_evidence=False, explanation_review='미평가(기본 제외)')
    if getattr(session, 'retry_policy', None) in j.jev_retry.RETRY_POLICIES:
        logical = {e['decision'] for e in transports}
        raw_responses = [e for e in session.records if e['type'] == 'http_response']
        failures = [e for e in session.records if e['type'] == 'attempt_failure']
        failed_decisions = {e['decision'] for e in failures}
        successful_decisions = {e['decision'] for e in responses}
        result.update(logical_requests=len(logical), retry_attempts=len(transports) - len(logical),
                      http_responses=len(raw_responses), http_errors=sum(e['status_code'] >= 400 for e in raw_responses),
                      http_no_response=len(transports) - len(raw_responses),
                      provider_failed_attempts=len(failures),
                      recovered_requests=len(failed_decisions & successful_decisions),
                      unsuccessful_logical_requests=len(logical - successful_decisions),
                      exhausted_requests=sum(e['attempt'] == 4 and j.jev_retry.retryable(
                          j.JevRequestError(e['category'], status_code=e['status_code'])) for e in failures),
                      http_latency_seconds=[e['elapsed_seconds'] for e in raw_responses if 'elapsed_seconds' in e],
                      latency_includes_retries=True)
    result.update(actual_wins=result['overall']['wins'], actual_losses=result['overall']['losses'], actual_draws=result['overall']['draws'])
    result['passed'] = (len(valid) == len(schedule) and len(pair_scores) * 2 == len(schedule)
                        and action_audit and not error and len(wires) == len(inputs)
                        and len(transports) == session.calls)
    return result


async def play(player, role, names, attempt, *, session=None, deadline):
    from poke_env.concurrency import handle_threaded_coroutines
    from . import cli
    await asyncio.wait_for(handle_threaded_coroutines(player.ps_client.logged_in.wait()), timeout=60)
    j.write(attempt / f'{role}.ready.json', dict(ready=True, pid=os.getpid(), role=role))
    other = 'p2' if role == 'p1' else 'p1'
    async def check():
        if session and session.terminal_error:
            raise session.terminal_error
        if getattr(player, 'output_error', None):
            raise player.output_error
        if getattr(player, 'benchmark_environment_error', None):
            raise player.benchmark_environment_error
        if (attempt / 'cancel.json').exists():
            raise RuntimeError('peer_failure')
        if (attempt / f'{other}.result.json').exists():
            result = json.loads((attempt / f'{other}.result.json').read_text())
            if result.get('error'):
                raise RuntimeError('opponent technical failure: ' + result['error']['type'])
        if time.monotonic() >= deadline or (session and session.remaining() <= 0):
            raise TimeoutError('battle or collection deadline')
    task = None
    try:
        while not (attempt / f'{other}.ready.json').exists():
            await check()
            await asyncio.sleep(.1)
        task = asyncio.create_task(player.send_challenges(names[other], 1) if role == 'p1'
                                   else player.accept_challenges(names[other], 1))
        while not task.done():
            await check()
            await asyncio.sleep(.1)
        await task
        await check()
        battles = list(player.battles.values())
        if len(battles) != 1 or player.n_finished_battles != 1:
            raise RuntimeError('missing terminal battle')
        battle = battles[0]
        if battle.player_role != role:
            raise ValueError('unexpected actual actor role')
        return dict(completed=True, outcome='player_won' if battle.won else 'player_lost' if battle.lost else 'tied',
                    turns=battle.turn, battle_tag=battle.battle_tag, actor=role)
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await cli._close_players([player])


async def bot_worker(attempt):
    import numpy as np
    from poke_env.player.baselines import AbyssalPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from .battle_adapter import guard_parser, install_identity_adapter
    install_identity_adapter()
    request = json.loads((attempt / 'request.json').read_text())
    row = request['slot']
    role = 'p2' if row['jev_actor'] == 'p1' else 'p1'
    index = int(role[-1]) - 1
    seed = row['actor_seeds'][index]
    random.seed(seed)
    np.random.seed(seed)
    player = AbyssalPlayer(team=request['teams'][row['teams'][index]]['showdown_team'], battle_format='gen9ou',
                          max_concurrent_battles=1, account_configuration=AccountConfiguration(request['names'][role], None),
                          server_configuration=ServerConfiguration(f'localhost:{PORT}', 'https://play.pokemonshowdown.com/action.php?'))
    guard_parser(player)
    result = dict(completed=False, pid=os.getpid(), python_random_seed=seed, numpy_random_seed=seed,
                  python_hash_seed=os.environ.get('PYTHONHASHSEED'), actor=role)
    try:
        result.update(await play(player, role, request['names'], attempt, deadline=time.monotonic() + request['watchdog_seconds']))
    except Exception as exc:
        result['error'] = dict(type=type(exc).__name__, detail=str(exc))
    finally:
        await __import__('integration.pokechamp.cli', fromlist=['_close_players'])._close_players([player])
        j.write(attempt / f'{role}.result.json', result)
    return result


def seal(directory):
    paths = sorted(p for p in directory.rglob('*') if p.is_file() and p.name != 'checksums.sha256')
    (directory / 'checksums.sha256').write_text(''.join(f'{sha(p)}  {p.relative_to(directory)}\n' for p in paths))


async def run(directory, *, fake=False, experiment="EX-052"):
    import numpy as np
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from . import cli
    from .battle_adapter import install_identity_adapter
    from .parallel_server import BattleServer
    from .jev_battle_audit import audit
    directory = Path(directory).resolve()
    live, receipt_path, ep, version = experiment_settings(experiment)
    if not fake and directory != live:
        raise ValueError(f'{experiment} live output is fixed')
    if directory.exists():
        raise FileExistsError(directory)
    rows, teams, origin = study_schedule(experiment)
    schedule = [r for r in rows if r['repetition'] == 1] if fake else rows
    sources = j.source_identity()
    config, env = (dict(model='jev-latest', endpoint='mock://local/systemone'), {}) if fake else (configuration() if experiment == 'EX-052' else configuration(experiment))
    if experiment in ('EX-056', 'EX-057') and fake:
        raise ValueError(f'{experiment} has no preflight/local execution path')
    if not fake and experiment not in ('EX-056', 'EX-057', 'EX-058', 'EX-059'):
        receipt = json.loads(receipt_path.read_text())
        if not receipt['passed'] or receipt['source'] != sources or receipt['schedule_sha256'] != j.digest(rows) or receipt['model'] != config:
            raise ValueError(f'missing or stale {experiment} verification')
        if experiment in ('EX-053', 'EX-054') and receipt.get('identity') != v3_identity(rows, teams, origin, config, sources, experiment):
            raise ValueError(f'missing or stale {experiment} identity verification')
    preflight = None
    if experiment in ('EX-058', 'EX-059'):
        if fake:
            raise ValueError('EX-058 uses saved-case checks, no mock battles')
        if experiment == 'EX-059':
            from .jev_v5 import probe, data_identity
        else:
            from .jev_v4 import probe, data_identity
        preflight = await probe(config, env, sources)
        if j.source_identity() != sources:
            raise ValueError('source changed after probe; collection prohibited')
    directory.mkdir(parents=True, exist_ok=False)
    session = StudySession(directory, fake=fake, environ=env,
                           retry_policy=(j.jev_retry.CURRENT if experiment in ("EX-056", "EX-057", "EX-058", "EX-059") else
                                         j.jev_retry.V1 if experiment == "EX-054" else j.jev_retry.LEGACY))
    if preflight is not None:
        session.started = preflight['first_request_at']
        session.monotonic_started = preflight['monotonic_started']
    session.input_version = version
    session.capture_request_body = experiment in ("EX-053", "EX-054", "EX-056", "EX-057", "EX-058", "EX-059")
    for name in sources:
        target = directory / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    manifest = dict(execution_profile=PROFILE, experiment_id=ep + '-local' if fake else experiment,
                    version=version, schema_version=version, validation_version=j.VALIDATION_VERSION,
                    initial_pp_policy=session.initial_pp_policy,
                    effect_reference_identity=session.effect_reference_identity, fake=fake, source=sources, model=config,
                    schedule=schedule, schedule_origin=origin, schedule_sha256=j.digest(schedule), teams=teams,
                    prompt=j.PROMPT.with_name(version + '.txt').read_text(), timer_enabled=False,
                    limits=dict(games=len(schedule), calls=None, collection_seconds=COLLECTION_SECONDS,
                                total_seconds=TOTAL_SECONDS, concurrency=1, retries=len(j.jev_retry.delays_for(session.retry_policy)), recollection=0),
                    submodules={name: dict(sha=c['sha']) for name, c in cli.SUBMODULES.items()},
                    observation_build=json.loads((Path(__file__).with_name('observation') / 'build-identity.json').read_text()),
                    efficacy_evidence=False, created_at=time.time(), rng_isolation='separate-processes')
    if experiment in ('EX-054', 'EX-056', 'EX-057', 'EX-058', 'EX-059'):
        manifest.update(transport_policy=session.retry_policy, provider_retries=3, retry_delays_seconds=list(j.jev_retry.delays_for(session.retry_policy)))
    if experiment in ('EX-053', 'EX-054'):
        manifest['verification_identity'] = v3_identity(rows, teams, origin, config, sources, experiment)
        if not fake:
            manifest['verification_receipt_sha256'] = sha(receipt_path)
    if experiment in ('EX-056', 'EX-057'):
        identity = v3_identity(rows, teams, origin, config, sources, experiment)
        approval = receipt_path.with_name('approval.md')
        entry = dict(experiment_id=experiment, preflight_status='skipped_by_user',
                     preflight_passed=False, tests_run=False, mock_games=0, api_probes=0,
                     first_four_gate=False, prior_receipts_reused=False,
                     approval_path=str(approval.relative_to(ROOT)), approval_sha256=sha(approval),
                     identity=identity, created_at=time.time())
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with receipt_path.open('x') as stream:
            stream.write(json.dumps(entry, ensure_ascii=False, indent=2) + '\n')
        j.write(directory / 'entry-record.json', entry)
        manifest.update(entry_record_sha256=sha(receipt_path), execution_identity=identity,
                        preflight_status='skipped_by_user', first_four_gate=False)
    if preflight is not None:
        manifest.update(input_data_identity=preflight['data_identity'], preflight=preflight,
                        first_four_gate=False, verification_receipt_sha256=sha(receipt_path))
    j.write(directory / 'manifest.json', manifest)
    install_identity_adapter()
    outcomes, error = [], None
    owner = asyncio.current_task()
    async def cleanup_watchdog():
        while True:
            await asyncio.sleep(1)
            if session.started is not None and time.monotonic() - session.monotonic_started >= TOTAL_SECONDS - 60:
                session.fail(TimeoutError('cleanup deadline guard'))
                owner.cancel()
                return
    watchdog = asyncio.create_task(cleanup_watchdog())
    try:
        for number, row in enumerate(schedule, 1):
            if session.remaining() <= 0:
                raise TimeoutError('collection deadline; no new match')
            if preflight is not None and data_identity() != preflight['data_identity']:
                raise ValueError('input data changed before admission')
            if j.source_identity() != sources:
                raise ValueError('source changed before admission')
            attempt = directory / f'battle-{number}'
            attempt.mkdir()
            server = BattleServer(attempt, PORT, row['battle_seed'])
            process = log = player = None
            start_event = len(session.records)
            start_calls = session.calls
            role = row['jev_actor']
            other = 'p2' if role == 'p1' else 'p1'
            seed = row['actor_seeds'][int(role[-1]) - 1]
            identity = hashlib.sha256(f'{directory}:{row["slot_id"]}'.encode()).hexdigest()[:12]
            names = {role: 'jev' + identity, other: 'aby' + identity}
            outcome = dict(slot=number, **row, username=names[role], completed=False, audit_passed=False,
                           jev_pid=os.getpid(), python_random_seed=seed, numpy_random_seed=seed)
            outcomes.append(outcome)
            try:
                await asyncio.to_thread(server.start)
                local_limit = 900 if fake else session.remaining()
                j.write(attempt / 'request.json', dict(slot=row, teams=teams, names=names, watchdog_seconds=local_limit))
                child_env = cli._child_environment(PYTHONPATH=f'{ROOT}:{ROOT / "pokechamp"}',
                    PYTHONHASHSEED=str(row['actor_seeds'][int(other[-1]) - 1]),
                    OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
                log = (attempt / 'abyssal.log').open('xb')
                process = subprocess.Popen([sys.executable, '-m', 'integration.pokechamp.jev_study', 'bot', '--output', str(attempt)],
                    cwd=ROOT / 'pokechamp', env=child_env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True)
                outcome['abyssal_pid'] = process.pid
                random.seed(seed)
                np.random.seed(seed)
                player = j.player_class()(session=session, expected_actor=role,
                    team=teams[row['teams'][int(role[-1]) - 1]]['showdown_team'], battle_format='gen9ou', max_concurrent_battles=1,
                    account_configuration=AccountConfiguration(names[role], None),
                    server_configuration=ServerConfiguration(f'localhost:{PORT}', 'https://play.pokemonshowdown.com/action.php?'))
                outcome.update(await play(player, role, names, attempt, session=session, deadline=time.monotonic() + local_limit))
                await asyncio.to_thread(process.wait, 15)
                peer = json.loads((attempt / f'{other}.result.json').read_text())
                complement = {'player_won': 'player_lost', 'player_lost': 'player_won', 'tied': 'tied'}
                if (process.returncode or not peer['completed'] or peer['outcome'] != complement[outcome['outcome']]
                        or peer['turns'] != outcome['turns'] or peer['actor'] != other
                        or peer['python_random_seed'] != row['actor_seeds'][int(other[-1]) - 1]):
                    raise ValueError('opponent terminal or seed mismatch')
            except j.UnusableChoice as exc:
                outcome.update(error=dict(type=type(exc).__name__, detail=str(exc)), failure_scope='battle', outcome='output_failure')
            except BaseException as exc:
                outcome.update(error=dict(type=type(exc).__name__, detail=j.redact(str(exc), env)), failure_scope='collection')
                raise
            finally:
                j.write(attempt / 'cancel.json', dict(reason='attempt ended'))
                if player is not None:
                    await cli._close_players([player])
                    if player.official is not None:
                        player.official.close()
                if process is not None and process.poll() is None:
                    from .benchmark import terminate
                    await asyncio.to_thread(terminate, process)
                if log:
                    log.close()
                await asyncio.to_thread(server.close)
                outcome['server_cleaned'] = not server.created and (server.process is None or server.process.poll() is not None)
                outcome['opponent_cleaned'] = process is None or process.poll() is not None
                outcome['requests'] = session.calls - start_calls
                j.write(attempt / 'outcome.json', outcome)
            # A model output failure is audited, but never blocks independent slots.
            partial = dict(passed=bool(outcome['completed']), planned=1, completed=int(outcome['completed']),
                           failed=int(not outcome['completed']), outcomes=[outcome], error=None,
                           sent_actions=sum(e['type'] == 'wire' for e in session.records[start_event:]))
            check = await asyncio.to_thread(audit, directory, checkpoint=True, events=session.records[start_event:], result=partial)
            if not check['passed']:
                raise ValueError('per-match technical audit failed')
            outcome['audit_passed'] = check['passed']
            j.write(attempt / 'audit.json', check)
            j.write(attempt / 'outcome.json', outcome)
            result = summarize(session, outcomes, schedule)
            j.write(directory / 'progress.json', result)
            print(json.dumps(dict(slot=number, slot_id=row['slot_id'], completed=result['completed'], outcome=outcome.get('outcome'),
                                  requests=session.calls, elapsed=result['elapsed_collection_seconds']), ensure_ascii=False), flush=True)
            if number == 4 and experiment not in ('EX-056', 'EX-057', 'EX-058', 'EX-059'):
                j.write(directory / 'first-four-check.json', dict(passed=True, audited=4,
                    completed=result['completed'], output_failures=result['failed'], model_failures_do_not_block=True))
    except (Exception, asyncio.CancelledError) as exc:
        error = dict(type=type(exc).__name__, detail=j.redact(str(exc), env))
        session.record(dict(type='failure', error=error))
    finally:
        watchdog.cancel()
        await asyncio.gather(watchdog, return_exceptions=True)
        if getattr(session, 'v4_adapter', None):
            await asyncio.to_thread(session.v4_adapter.close)
    if j.source_identity() != sources:
        error = dict(type='SourceChanged', detail='source changed during collection')
    result = summarize(session, outcomes, schedule, error)
    if preflight is not None:
        result['received_usage'] = result['tokens']
        result['usage_unknown_attempts'] = result['unanswered_requests'] + result['missing_usage_responses']
        if result['usage_unknown_attempts']:
            result['tokens'] = None
        result.update(preflight_requests=1, cumulative_physical_requests=session.calls + 1,
                      input_generation_seconds=[e['input_generation_seconds'] for e in session.records if e['type'] == 'input'])
    j.write(directory / 'result.json', result)
    seal(directory)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('local', 'live', 'bot'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--experiment', choices=('EX-052', 'EX-053', 'EX-054', 'EX-056', 'EX-057', 'EX-058', 'EX-059'), default='EX-052')
    args = parser.parse_args()
    if args.mode in ('local', 'bot') and args.output is None:
        parser.error('local/bot requires --output')
    result = asyncio.run(bot_worker(args.output) if args.mode == 'bot' else run(args.output or experiment_settings(args.experiment)[0], fake=args.mode == 'local', experiment=args.experiment))
    print(json.dumps({k: result.get(k) for k in ('passed', 'completed', 'external_requests', 'error')}, ensure_ascii=False))
    return 0 if result.get('passed', result.get('completed')) and not result.get('error') else 2


if __name__ == '__main__':
    raise SystemExit(main())
