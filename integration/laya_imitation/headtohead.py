"""EX-134 / EX-135 / EX-138 laya-vs-laya games on the sealed EX-120 schedule (D-194), GPU2 / port 8108.

Each EX-120 row is played by the base model (`model`, on `model_side` with that side's team) against another laya
model on the other side (`opponent_model`); the swapped-team pair gives both models both teams. Both sides are EX-071
model players with their own Session and serving: the base side logs to the attempt directory (the layout `battle`'s
audit and the failure/Tera counts already read), the other side to `opponent/` with a mirrored `request.json`, so the
same `audit_match` checks both. Symlinks give each audit the other side's team submission and the shared seed record.
No fallback, requery or replay; argmax on both sides. Score = the base model's game score; judged against 0.5 by a
matchup-cluster bootstrap. Abyssal results of the same models on the same slots (EX-120/125/127/129/131/133) are read
back for the "does it agree with Abyssal, and is it sharper" comparison.
"""
from __future__ import annotations
import argparse
import asyncio
import html
import json
import os
from pathlib import Path
import shutil
import sys
import time

from . import config as c
from .battle import BATTLE_SECONDS, CLEANUP_SECONDS, Serving, play_slot, summarize
from .comparison import RENDER, Study, failed_moves
from .generalization import COLLECTION, SCORE, _bootstrap, summarize_generalization
from .storage import append_jsonl, atomic, digest, jsonl, read, seal, sha, source_identity, verify_seal

DRAWS = 10000
FLIP = {'p1': 'p2', 'p2': 'p1'}
RESULT_FLIP = {'win': 'loss', 'loss': 'win', 'draw': 'draw', None: None}
RUNS = {'laya-v1': ('EX-118', c.RUN_TRAINING), 'laya-v2': ('EX-121', c.RUN_V2_TRAINING),
        'laya-v2t': ('EX-124', c.RUN_TERA_TRAINING), 'laya-v2te': ('EX-126', c.RUN_EFFECT_TRAINING),
        'laya-v3t': ('EX-128', c.RUN_V3_TRAINING), 'laya-v4t': ('EX-130', c.RUN_V4_TRAINING),
        'laya-v2tw': ('EX-132', c.RUN_WEIGHTED_TRAINING), 'laya-v5t': ('EX-136', c.RUN_V5_TRAINING)}
# The same model's Abyssal games on the same EX-120 slots: (run, slot prefix or None for EX-120's own ids).
ABYSSAL = {'laya-v1': ('EX-120', c.RUN_GENERAL, None), 'laya-v2': ('EX-125', c.RUN_COMPARE2, 'v2'),
           'laya-v2t': ('EX-125', c.RUN_COMPARE2, 'v2t'), 'laya-v2te': ('EX-127', c.RUN_COMPARE3, 'v2te'),
           'laya-v3t': ('EX-129', c.RUN_COMPARE4, 'v3t'), 'laya-v4t': ('EX-131', c.RUN_COMPARE5, 'v4t'),
           'laya-v2tw': ('EX-133', c.RUN_COMPARE6, 'v2tw'), 'laya-v5t': ('EX-137', c.RUN_COMPARE7, 'v5t')}

EX134 = Study(
    experiment='EX-134', plan='EP-217', seed=20261030, base='laya-v2t',
    others=('laya-v2', 'laya-v1', 'laya-v2te', 'laya-v3t'), out=c.RUN_H2H, viewer=c.VIEWER_H2H,
    gpu=(c.GPU2_INDEX, c.GPU2_UUID), port=c.PORT3, hours=c.H2H_HOURS,
    meta=dict(experiment='EX-134', plan='EP-217', slug='ex134', title='EX-134 · laya 직접 대결 512경기',
              heading='EX-134 · laya v2+테라(EX-124) 대 v2·v1·v2+테라+효과·v3+테라 직접 대결 · EX-120 일정',
              intro='EX-120 일정(새 팀 32개, 128슬롯)의 각 슬롯에서 v2+테라가 model 진영, 비교 모델이 반대 진영을 맡았습니다. '
                    '두 진영 모두 laya 서빙(GPU2)의 argmax 선택이며 확률은 행동 선택 확률이고 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex134-laya-h2h-v1'))

# EX-135: the two newest candidates (EX-132 outcome weights, EX-130 renderer v4) against v2+Tera, after both are sealed.
EX135 = Study(
    experiment='EX-135', plan='EP-217', seed=20261031, base='laya-v2t', others=('laya-v2tw', 'laya-v4t'),
    out=c.RUN_H2H2, viewer=c.VIEWER_H2H2, gpu=(c.GPU2_INDEX, c.GPU2_UUID), port=c.PORT3, hours=c.H2H_HOURS,
    meta=dict(experiment='EX-135', plan='EP-217', slug='ex135', title='EX-135 · laya 직접 대결 256경기',
              heading='EX-135 · laya v2+테라(EX-124) 대 승패 가중(EX-132)·v4+테라(EX-130) 직접 대결 · EX-120 일정',
              intro='EX-120 일정(새 팀 32개, 128슬롯)의 각 슬롯에서 v2+테라가 model 진영, 비교 모델이 반대 진영을 맡았습니다. '
                    '두 진영 모두 laya 서빙(GPU2)의 argmax 선택이며 확률은 행동 선택 확률이고 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex134-laya-h2h-v1'))
# EX-138 (D-195): v5+Tera (EX-136) as the base side against the current best v2+Tera and its v4+Tera parent.
EX138 = Study(
    experiment='EX-138', plan='EP-218', seed=20261034, base='laya-v5t', others=('laya-v2t', 'laya-v4t'),
    out=c.RUN_H2H3, viewer=c.VIEWER_H2H3, gpu=(c.GPU2_INDEX, c.GPU2_UUID), port=c.PORT3, hours=c.H2H_HOURS,
    meta=dict(experiment='EX-138', plan='EP-218', slug='ex138', title='EX-138 · laya 직접 대결 256경기',
              heading='EX-138 · laya v5+테라(EX-136) 대 v2+테라(EX-124)·v4+테라(EX-130) 직접 대결 · EX-120 일정',
              intro='EX-120 일정(새 팀 32개, 128슬롯)의 각 슬롯에서 v5+테라가 model 진영, 비교 모델이 반대 진영을 맡았습니다. '
                    '두 진영 모두 laya 서빙(GPU2)의 argmax 선택이며 확률은 행동 선택 확률이고 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex134-laya-h2h-v1'))
STUDIES = {'EX-134': EX134, 'EX-135': EX135, 'EX-138': EX138}


def _prefix(model):
    return model.split('-', 1)[1]


# ----------------------------------------------------------------------------- schedule

def make_schedule(base, study=EX134):
    """EX-120 rows -> one row per (EX-120 slot, other model); per EX-120 pair, the others in a seeded digest order."""
    pairs = []
    for row in base:
        if not pairs or pairs[-1][0]['pair_id'] != row['pair_id']:
            pairs.append([])
        pairs[-1].append(row)
    out = []
    for pair in pairs:
        order = sorted(study.others, key=lambda m: digest([study.seed, 'h2h_order', pair[0]['pair_id'], m]))
        for other in order:
            for row in pair:
                out.append(dict(row, slot_id='%s-%s' % (_prefix(other), row['slot_id']),
                                pair_id='%s-%s' % (_prefix(other), row['pair_id']), base_slot_id=row['slot_id'],
                                base_pair_id=row['pair_id'], model=study.base, opponent='laya:' + other,
                                opponent_model=other))
    for order, row in enumerate(out, 1):
        row['submission_order'] = order
    return out


def mirror(row):
    """The same slot seen from the other model's side (what its worker and audit read)."""
    side = FLIP[row['model_side']]
    return dict(row, model=row['opponent_model'], model_side=side, model_seed=row['opponent_seed'],
                opponent_seed=row['model_seed'], opponent='laya:' + row['model'], opponent_model=row['model'],
                archetypes=dict(model=row['archetypes']['opponent'], opponent=row['archetypes']['model']))


def prepare_attempt(serving_identity):
    """`play_slot(before=...)`: write `opponent/request.json` and the evidence links both audits read."""
    def before(directory):
        directory = Path(directory)
        request = read(directory / 'request.json')
        other = directory / 'opponent'
        other.mkdir()
        atomic(other / 'request.json', dict(request, slot=mirror(request['slot']), serving=serving_identity),
               immutable=True)
        (directory / 'opponent-events.jsonl').symlink_to('opponent/events.jsonl')
        (other / 'opponent-events.jsonl').symlink_to('../events.jsonl')
        (other / 'battle-seed.jsonl').symlink_to('../battle-seed.jsonl')
    return before


def audit_both(directory, outcome):
    from integration.pokechamp.imitation.battle import audit_match
    directory = Path(directory)
    main = audit_match(directory, outcome)
    side = read(directory / 'opponent/request.json')['slot']
    other = audit_match(directory / 'opponent', dict(outcome, model=side['model'], model_side=side['model_side'],
                                                     result=RESULT_FLIP[outcome.get('result')]))
    atomic(directory / 'opponent/audit.json', other, immutable=True)
    return dict(main, passed=main['passed'] and other['passed'],
                errors=main['errors'] + [dict(e, side='opponent') for e in other['errors']],
                opponent=dict(passed=other['passed'], counts=other['counts'],
                              inference_seconds=other['inference_seconds']))


# ----------------------------------------------------------------------------- worker

def worker(attempt, role):
    """EX-071 model worker for either side: own request (main or mirrored), own Session directory."""
    from integration.pokechamp.imitation import player as p
    p.MAX_TURNS = c.TURN_LIMIT

    class LimitedSession(p.Session):
        async def evaluate(self, value, decision):
            if self.calls >= c.DECISION_LIMIT:
                raise p.BattleLimit('decision_limit')
            return await super().evaluate(value, decision)

    result = asyncio.run(_play(p, LimitedSession, Path(attempt), role))
    print(p.compact(result))
    return 0 if result['status'] == 'completed' else 1


async def _play(p, session_class, attempt, role):
    import random
    import numpy as np
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration

    from integration.pokechamp import cli
    from integration.pokechamp.battle_adapter import install_identity_adapter

    main = json.loads((attempt / 'request.json').read_text())
    home = attempt if role == main['slot']['model_side'] else attempt / 'opponent'
    own = main if home == attempt else json.loads((home / 'request.json').read_text())
    row = own['slot']
    if row['model_side'] != role:
        raise RuntimeError('mirrored request does not own this side')
    seed = row['model_seed']
    random.seed(seed)
    np.random.seed(seed)
    install_identity_adapter()
    player = session = None
    result = dict(actor=role, status='failed', result=None, pid=os.getpid(), policy=row['model'], seed=seed,
                  python_hash_seed=os.environ.get('PYTHONHASHSEED'))
    try:
        team = row['teams'][role]
        session = session_class(home, model=row['model'], serving=own['serving'], own_sets=p.submitted_sets(team),
                                deadline=main['deadline_monotonic'])
        common = dict(team=team['packed'], battle_format='gen9ou', max_concurrent_battles=1,
                      start_timer_on_battle_start=False,
                      account_configuration=AccountConfiguration(main['names'][role], None),
                      server_configuration=ServerConfiguration('localhost:%s' % main['port'],
                                                               'https://play.pokemonshowdown.com/action.php?'))
        player = p.player_class()(session=session, expected_actor=role, **common)
        p.record_sends(player, session)
        result.update(await p.play(player, role, main, attempt, session=session))
    except p.BattleLimit as error:
        result.update(status='incomplete', reason=str(error), failure_scope='battle')
    except p.legacy.UnusableChoice as error:
        result.update(status='failed', error=dict(type=type(error).__name__, detail=str(error)), failure_scope='battle')
    except BaseException as error:
        result.update(status='failed', error=dict(type=type(error).__name__, detail=str(error)), failure_scope='phase')
    finally:
        if player is not None:
            result['observed_turn'] = max((b.turn for b in player.battles.values()), default=0)
            try:
                await cli._close_players([player])
                if getattr(player, 'official', None):
                    player.official.close()
            except BaseException as error:
                result.update(status='failed', result=None, failure_scope='phase',
                              cleanup_error=dict(type=type(error).__name__, detail=str(error)))
        if session is not None:
            try:
                session.close()
            except BaseException as error:
                result.update(status='failed', result=None, failure_scope='phase',
                              cleanup_error=dict(type=type(error).__name__, detail=str(error)))
        p._atomic_json(attempt / ('%s.result.json' % role), result)
    return result


# ----------------------------------------------------------------------------- run

def _run(directory, rows, servings, hours, study=EX134):
    """`comparison._run` with both sides served: every model in `servings` is up for the whole stage."""
    from .resources import gpu, port
    directory.mkdir(parents=True, exist_ok=True)
    ledger, games = directory / 'ledger.jsonl', directory / 'games'
    outcomes = [dict(read(games / r['slot_id'] / 'outcome.json'), opponent_model=r['opponent_model']) for r in rows
                if (games / r['slot_id'] / 'outcome.json').exists()]
    claimed = {r['slot_id'] for r in rows if (games / r['slot_id']).exists()}
    if claimed - {o['slot_id'] for o in outcomes}:
        raise RuntimeError('a claimed slot has no outcome; it is not replayed: %s' % sorted(claimed))
    if not (directory / 'clock.json').exists():
        atomic(directory / 'clock.json', dict(first_started=time.time(), hours=hours), immutable=True)
    deadline = read(directory / 'clock.json')['first_started'] + hours * 3600
    latencies = {}
    for o in outcomes:
        audit = read(games / o['slot_id'] / 'audit.json')
        latencies.setdefault(o['model'], []).extend(audit['inference_seconds'])
        latencies.setdefault(o['opponent_model'], []).extend(audit.get('opponent', {}).get('inference_seconds', []))
    error, owned = None, {}
    with port(study.port), gpu(*study.gpu) as (env, _):
        try:
            identities = {}
            for model, spec in servings.items():
                owned[model] = Serving(directory, spec['checkpoint'], model, 'cuda', render=RENDER[model])
                identities[model] = owned[model].start(env)
                if spec.get('sha') and identities[model]['checkpoint_sha256'] != spec['sha']:
                    raise RuntimeError('served checkpoint differs from the frozen one: ' + model)
                append_jsonl(ledger, dict(type='serving_started', identity=identities[model], at=time.time()))

            def check(a, b):
                owned[a].check(identities[a]['checkpoint_sha256'])
                owned[b].check(identities[b]['checkpoint_sha256'])

            for row in rows:
                if row['slot_id'] in claimed:
                    continue
                if time.time() > deadline - CLEANUP_SECONDS:
                    append_jsonl(ledger, dict(type='admission_closed', reason='stage_time_limit', at=time.time()))
                    break
                a, b = row['model'], row['opponent_model']
                other = dict(endpoint=identities[b]['endpoint'], checkpoint_sha256=identities[b]['checkpoint_sha256'])
                append_jsonl(ledger, dict(type='slot_claim', slot_id=row['slot_id'], at=time.time()))
                outcome, audit = play_slot(games / row['slot_id'], row, identities[a], lambda a=a, b=b: check(a, b),
                                           port=study.port, worker='integration.laya_imitation.headtohead',
                                           prefixes=('lay', 'opp'), before=prepare_attempt(other), audit=audit_both)
                outcome = dict(outcome, opponent_model=b)
                outcomes.append(outcome)
                latencies.setdefault(a, []).extend(audit['inference_seconds'])
                latencies.setdefault(b, []).extend(audit.get('opponent', {}).get('inference_seconds', []))
                append_jsonl(ledger, dict(type='slot_finished', outcome=outcome, at=time.time()))
                atomic(directory / 'status.json', dict(stage='running', done=len(outcomes), of=len(rows), at=time.time()))
                if outcome.get('failure_scope') == 'phase':
                    error = dict(type='phase_halt', slot_id=row['slot_id'], reason=outcome.get('error'))
                    break
        except BaseException as caught:
            error = dict(type=type(caught).__name__, detail=str(caught))
        finally:
            for serving in owned.values():
                serving.stop()
            append_jsonl(ledger, dict(type='closed', error=error, at=time.time()))
    return outcomes, latencies, error


# ----------------------------------------------------------------------------- summary

def abyssal_scores(model):
    """{EX-120 slot: score} of `model`'s Abyssal games on the EX-120 schedule, or None when that run is missing."""
    name, run, prefix = ABYSSAL[model]
    if not (run / 'result.json').exists():
        return None
    out = {}
    for o in read(run / 'result.json')['outcomes']:
        if o['status'] != 'completed':
            continue
        slot = o['slot_id']
        if prefix is not None:
            if not slot.startswith(prefix + '-'):
                continue
            slot = slot[len(prefix) + 1:]
        out[slot] = SCORE[o['result']]
    return out


def abyssal_diff(base, other, seed):
    """Same-slot Abyssal score difference base - other with the matchup-cluster interval (None if not both run)."""
    a, b = abyssal_scores(base), abyssal_scores(other)
    if not a or not b:
        return None
    slots = sorted(set(a) & set(b))
    clusters = {}
    for s in slots:
        clusters.setdefault(s.split('-')[0], []).append(a[s] - b[s])
    diffs = [d for v in clusters.values() for d in v]
    return dict(source=[ABYSSAL[base][0], ABYSSAL[other][0]], slots=len(slots), base_score=sum(a[s] for s in slots) / len(slots),
                other_score=sum(b[s] for s in slots) / len(slots), mean_diff=sum(diffs) / len(diffs),
                matchup_bootstrap_95=_bootstrap(list(clusters.values()), seed=seed, draws=DRAWS),
                base_better=sum(d > 0 for d in diffs), other_better=sum(d < 0 for d in diffs),
                same=sum(d == 0 for d in diffs))


def verdict(block, base, other):
    if block['status']['completed'] < 120:
        return '판정 보류(정상 종료 %d/128 < 120)' % block['status']['completed']
    low, high = block['h2h_bootstrap_95']
    return '%s 우세' % base if low > 0.5 else '%s 우세' % other if high < 0.5 else '구별되지 않음'


def summarize_h2h(rows, outcomes, latencies, study=EX134):
    by_slot = {o['slot_id']: o for o in outcomes}
    pairs = {}
    for other in study.others:
        sub = [r for r in rows if r['opponent_model'] == other]
        outs = [by_slot[r['slot_id']] for r in sub if r['slot_id'] in by_slot]
        block = summarize_generalization(sub, outs, ())
        clusters = {}
        for r in sub:
            o = by_slot.get(r['slot_id'])
            if o and o['status'] == 'completed':
                clusters.setdefault(r['matchup_id'], []).append(SCORE[o['result']])
        block['h2h_bootstrap_95'] = _bootstrap(list(clusters.values()), seed=study.seed, draws=DRAWS)
        block['abyssal'] = abyssal_diff(study.base, other, study.seed)
        block['verdict'] = verdict(block, study.base, other) if block['h2h_bootstrap_95'] else '판정 불가'
        if block['abyssal'] and block['h2h_bootstrap_95']:
            low, high = block['abyssal']['matchup_bootstrap_95']
            ab = 'base' if low > 0 else 'other' if high < 0 else 'none'
            hl, hh = block['h2h_bootstrap_95']
            hb = 'base' if hl > 0.5 else 'other' if hh < 0.5 else 'none'
            sign = lambda x: (x > 0) - (x < 0)
            block['agreement'] = dict(abyssal_separates=ab, h2h_separates=hb,
                                      same_direction=sign(block['abyssal']['mean_diff']) == sign(block['mean_score'] - 0.5))
        pairs[other] = block
    lat = {m: sorted(v) for m, v in latencies.items()}
    return dict(base=study.base, pairs=pairs,
                inference_seconds={m: dict(n=len(v), p50=v[len(v) // 2] if v else None) for m, v in lat.items()})


def side_failures(directory, rows, outcomes):
    """Failed/immune moves per (side, pairing) from the public protocol the base side recorded."""
    base = failed_moves(directory, rows, outcomes, model_of=lambda r: '%s (대 %s)' % (r['model'], r['opponent_model']))
    flipped = [dict(o, model_side=FLIP[o['model_side']]) for o in outcomes]
    other = failed_moves(directory, rows, flipped, model_of=lambda r: '%s (대 %s)' % (r['opponent_model'], r['model']))
    return dict(base, **other)


# ----------------------------------------------------------------------------- stages

def _base_schedule():
    if verify_seal(COLLECTION):
        raise RuntimeError('EX-120 collection seal failed')
    return read(COLLECTION / 'schedule.json')


def _servings(models):
    from .serving import checkpoint_identity
    out = {}
    for model in models:
        name, run = RUNS[model]
        if read(run / 'status.json')['stage'] != 'completed' or verify_seal(run):
            raise RuntimeError('%s is not completed and sealed' % name)
        path = run / 'checkpoints/selected'
        out[model] = dict(checkpoint=str(path), sha=checkpoint_identity(path), render=RENDER[model])
    return out


def mock(study=EX134):
    """The first two EX-120 pairs, base model against itself (one serving), outside every denominator."""
    base = _base_schedule()
    first = [p for p in dict.fromkeys(r['pair_id'] for r in base)][:2]
    rows = [dict(r, slot_id='mock-' + r['slot_id'], pair_id='mock-' + r['pair_id'], base_slot_id=r['slot_id'],
                 base_pair_id=r['pair_id'], model=study.base, opponent='laya:' + study.base, opponent_model=study.base)
            for r in base if r['pair_id'] in first]
    directory = study.out / 'mock'
    if (directory / 'result.json').exists():
        raise RuntimeError('%s mock already completed' % study.experiment)
    outcomes, latencies, error = _run(directory, rows, _servings([study.base]), 1.0, study)
    result = dict(outcomes=outcomes, latency=latencies, phase_error=error)
    atomic(directory / 'result.json', result, immutable=True)
    atomic(directory / 'manifest.json', dict(experiment_id=study.experiment + '-mock', schedule=rows), immutable=True)
    print(json.dumps(dict(games=[(o['slot_id'], o['status'], o.get('result'), o.get('audit_passed')) for o in outcomes],
                          error=error), ensure_ascii=False))


def prepare(study=EX134):
    from integration.project_context.registry import freeze_document, resolve_record
    from .serving import renderer_matches_dataset
    out = study.out
    if (out / 'manifest.json').exists():
        raise RuntimeError('%s already prepared' % study.experiment)
    models = (study.base,) + tuple(study.others)
    if not all(renderer_matches_dataset(RENDER[m]) for m in models):
        raise RuntimeError('a live renderer differs from its dataset generator')
    servings = _servings(models)
    rows = make_schedule(_base_schedule(), study)
    freeze_document(resolve_record(study.experiment), out / 'protocol' / (study.experiment + '.md'))
    atomic(out / 'source/identity.json', source_identity(), immutable=True)
    collection = read(COLLECTION / 'manifest.json')
    manifest = dict(experiment_id=study.experiment, schedule=rows, base=study.base, others=list(study.others),
                    collection=dict(path=str(COLLECTION), schedule_sha256=collection['schedule_sha256']),
                    servings=servings, opponent='laya', port=study.port, gpu_uuid=study.gpu[1],
                    turn_limit=c.TURN_LIMIT, decision_limit=c.DECISION_LIMIT, battle_seconds=BATTLE_SECONDS,
                    stage_hours=study.hours, retries=0, fallback=0, requery=0,
                    probability_meaning='action_selection_probability', created_at=time.time())
    atomic(out / 'manifest.json', manifest, immutable=True)
    atomic(out / 'status.json', dict(stage='prepared', at=time.time()))
    print(json.dumps(dict(prepared=len(rows), servings={k: v['sha'] for k, v in servings.items()})))


def execute(study=EX134):
    out = study.out
    manifest = read(out / 'manifest.json')
    if (out / 'result.json').exists():
        raise RuntimeError('%s already executed' % study.experiment)
    if source_identity()['files'] != read(out / 'source/identity.json')['files']:
        raise RuntimeError('source changed after the %s freeze' % study.experiment)
    outcomes, latencies, error = _run(out, manifest['schedule'], manifest['servings'], study.hours, study)
    summary = summarize_h2h(manifest['schedule'], outcomes, latencies, study)
    overall = summarize(manifest['schedule'], outcomes, [x for v in latencies.values() for x in v], seed=study.seed)
    result = dict(overall, **summary, failed_moves=side_failures(out, manifest['schedule'], outcomes),
                  outcomes=outcomes, phase_error=error, all_slots_attempted=len(outcomes) == len(manifest['schedule']))
    atomic(out / 'result.json', result, immutable=True)
    verdicts = {k: v['verdict'] for k, v in summary['pairs'].items()}
    atomic(out / 'status.json', dict(stage='executed', at=time.time(), verdicts=verdicts))
    print(json.dumps(dict(verdicts=verdicts, scores={k: (v['wins'], v['draws'], v['losses'], v['h2h_bootstrap_95'])
                                                     for k, v in summary['pairs'].items()}, error=error),
                     ensure_ascii=False))


def export(study=EX134):
    out = study.out
    result, manifest = read(out / 'result.json'), read(out / 'manifest.json')
    viewer = export_viewer(out, study)
    write_report(out, result, manifest, viewer, study)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(),
                                     verdicts={k: v['verdict'] for k, v in result['pairs'].items()}))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(study.viewer / 'index.html'))))


# ----------------------------------------------------------------------------- report and viewer

def _interval(v):
    return '[%.3f, %.3f]' % tuple(v) if v else '—'


def write_report(out, result, manifest, viewer, study=EX134):
    base = study.base
    lines = ['# %s %s 보고' % (study.experiment, study.meta['heading'].split(' · ', 1)[1]), '', study.meta['intro'], '',
             '## 판정 (실행 전 동결)', '',
             '점수는 %s의 경기 점수(승 1, 무 0.5, 패 0)다. 조합(32) 클러스터 bootstrap 95%%(10,000회, 시드 %d)의 하한 > 0.5면 '
             '%s 우세, 상한 < 0.5면 비교 모델 우세, 그 외는 구별되지 않음이다.' % (base, study.seed, base), '',
             '| 비교 모델 | 정상 | %s 승/무/패 | %s 점수 | 95%% | 교환쌍 2승/1승1패/2패 | 판정 |' % (base, base),
             '|---|---|---|---:|---|---|---|']
    for other, b in result['pairs'].items():
        d = b['swapped_pairs']
        lines.append('| %s | %d/%d | %d/%d/%d | %.3f | %s | %s/%s/%s | **%s** |' % (
            other, b['status']['completed'], b['scheduled'], b['wins'], b['draws'], b['losses'], b['mean_score'] or 0,
            _interval(b['h2h_bootstrap_95']), d['both_won'], d['split'], d['both_lost'], b['verdict']))
    lines += ['', '## Abyssal 판정과 비교 (보고 지표, 판정 외)', '',
              '같은 EX-120 슬롯에서 두 모델이 각자 Abyssal과 둔 결과(결정적 경로)의 같은 슬롯 차이(%s − 비교 모델)다.' % base, '',
              '| 비교 모델 | Abyssal 출처 | Abyssal 차이 | 95% | 차이 슬롯(우세/열세/같음) | Abyssal 구별 | 직접 대결 구별 | 방향 일치 |',
              '|---|---|---:|---|---|---|---|---|']
    for other, b in result['pairs'].items():
        a, g = b.get('abyssal'), b.get('agreement')
        if not a:
            lines.append('| %s | 없음 | — | — | — | — | — | — |' % other)
            continue
        lines.append('| %s | %s | %+.3f | %s | %d/%d/%d | %s | %s | %s |' % (
            other, '·'.join(a['source']), a['mean_diff'], _interval(a['matchup_bootstrap_95']), a['base_better'],
            a['other_better'], a['same'], g['abyssal_separates'], g['h2h_separates'], '예' if g['same_direction'] else '아니오'))
    lines += ['', '## 실패·무효 기술 (보고 지표, 판정 외)', '',
              '| 진영 | 경기 | 기술 사용 | 실패·무효 | 비율 | 같은 기술 3연속 실패 경기 | 많이 실패한 기술 |', '|---|---:|---:|---:|---:|---:|---|']
    for name, m in sorted(result['failed_moves'].items()):
        lines.append('| %s | %d | %d | %d | %.2f%% | %d | %s |' % (
            name, m['games'], m['moves'], m['failed'], 100 * (m['rate'] or 0), len(m['loops']),
            ', '.join('%s %d/%d' % (k, f, u) for k, f, u in m['top_failed'][:5])))
    lat = result['inference_seconds']
    lines += ['', '## 실행', '',
              '- 분모: 예정 %d, 정상 %d, 실패 %d, 미완료 %d, 무효 %d, 미실행 %d' % (
                  result['scheduled'], result['status']['completed'], result['status']['failed'],
                  result['status']['incomplete'], result['status']['invalid'], result['status']['unattempted']),
              '- 지연 p50: ' + ', '.join('%s %.3f초(n=%d)' % (m, v['p50'], v['n']) for m, v in sorted(lat.items()) if v['p50']),
              '- 단계 오류: %s' % (result['phase_error'] or '없음'),
              '- 뷰어: `%s`(%d경기, 결정 %d)' % (viewer['output'], viewer['games'], viewer['decisions']), '',
              '## 해석 한계', '',
              '- 두 진영 모두 argmax라 같은 슬롯은 결정적이다. 표본은 EX-120의 128슬롯(32조합)이 전부다.',
              '- 직접 대결은 laya 계열끼리의 상대 강도다. 사람이나 다른 봇 상대의 강도를 직접 말하지 않는다.',
              '- v2+테라가 모든 쌍의 공통 진영이라, 쌍 사이 점수는 v2+테라 기준의 상대 비교다.', '']
    (out / 'report.md').write_text('\n'.join(lines))


def _game_page(game, row, outcome, number, suffix, side_row, renderer, meta, target):
    from integration.jev_eval.turn_logs import build_turn_log, raw_text
    from integration.jevk5_ruleqa_battle.viewer_ui import render_replay
    from .viewer import decisions_for, render_page
    request = read(game / 'request.json')
    events = list(jsonl(game / 'events.jsonl'))
    decisions = decisions_for(events, renderer)
    log = build_turn_log(events, request['names'][side_row['model_side']], side_row['model_side'], decisions)
    (target / 'raw').mkdir(parents=True)
    for name in ('events.jsonl', 'outcome.json', 'audit.json', 'request.json'):
        if (game / name).exists():
            shutil.copyfile(game / name, target / 'raw' / name)
    seen = dict(outcome, model=side_row['model'], model_side=side_row['model_side'],
                result=outcome.get('result') if suffix == '' else RESULT_FLIP[outcome.get('result')])
    data = dict(experiment=meta['experiment'], slot='%d%s' % (number, suffix), outcome=seen, decisions=decisions,
                turn_log=log, synthetic=False)
    atomic(target / 'decisions.json', data)
    text = raw_text([r for turn in log['turns'] for r in turn['rows']])
    (target / 'showdown.log').write_text(text)
    (target / 'replay.html').write_text(render_replay('%s-%d%s' % (meta['slug'], number, suffix), text))
    (target / 'index.html').write_text(render_page(data))
    return len(decisions)


def export_viewer(run, study=EX134):
    """`viewer.export`'s pages, two per game: the base model's side and the other model's side (`opponent/`)."""
    from .compact import render as v1_render
    from .features import Calc
    from .serving import v2_renderer, v3_renderer, v4_renderer, v5_renderer
    from .viewer import EXTENSIONS, RENDERER, SOURCES, UI_VERSION
    meta, output = study.meta, Path(study.viewer)
    manifest, result = read(run / 'manifest.json'), read(run / 'result.json')
    output.mkdir(parents=True, exist_ok=False)
    by_slot = {o['slot_id']: o for o in result['outcomes']}
    rows, total = [], 0
    with Calc() as calc:
        renderers = dict(v1=v1_render, v2=v2_renderer(calc), v3=v3_renderer(calc), v4=v4_renderer(calc),
                         v5=v5_renderer(calc))
        for number, row in enumerate(manifest['schedule'], 1):
            cells = ''.join('<td>%s</td>' % html.escape(str(v)) for v in (
                number, row['slot_id'], row['opponent_model'], row['matchup_id'], row['model_side']))
            outcome = by_slot.get(row['slot_id'])
            if outcome is None:
                rows.append('<tr>%s<td>미실행</td><td>—</td><td>—</td></tr>' % cells)
                continue
            game = run / 'games' / row['slot_id']
            total += _game_page(game, row, outcome, number, '', row, renderers[RENDER[row['model']]], meta,
                                output / ('battle-%03d' % number))
            other = read(game / 'opponent/request.json')['slot'] if (game / 'opponent/request.json').exists() else None
            links = '<a href="battle-%03d/index.html">%s 입력·리플레이</a>' % (number, html.escape(_prefix(row['model'])))
            if other and (game / 'opponent/events.jsonl').exists():
                total += _game_page(game / 'opponent', row, outcome, number, 'b', other,
                                    renderers[RENDER[other['model']]], meta, output / ('battle-%03db' % number))
                links += ' · <a href="battle-%03db/index.html">%s 입력</a>' % (number, html.escape(_prefix(other['model'])))
            label = dict(win='승리', loss='패배', draw='무승부').get(outcome.get('result'), outcome['status'])
            rows.append('<tr>%s<td>%s</td><td>%s</td><td>%s</td></tr>' % (cells, html.escape(label),
                                                                           outcome.get('turns', '—'), links))
    head = ''.join('<th>%s</th>' % h for h in ('경기', '슬롯', '비교 모델', '조합', '%s 진영' % study.base,
                                               '%s 결과' % study.base, '턴', '열기'))
    summary = ' · '.join('대 %s %d승 %d무 %d패 (%s)' % (k, v['wins'], v['draws'], v['losses'], v['verdict'])
                         for k, v in result['pairs'].items())
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            'initial-scale=1"><title>' + html.escape(meta['title']) + '</title><style>body{font:16px/1.7 system-ui;'
            'max-width:1100px;margin:32px auto;padding:16px}table{width:100%;border-collapse:collapse}td,th{padding:8px;'
            'border-bottom:1px solid #ddd;text-align:left}a{color:#165fa5}</style><p><a href="../index.html">← 실험 목록</a></p>'
            '<h1>' + html.escape(meta['heading']) + '</h1><p>' + html.escape(summary) + '</p><p>' + html.escape(meta['intro'])
            + '</p><p>실패 %d · 미완료 %d · 무효 %d · 미실행 %d</p>' % (
                result['status']['failed'], result['status']['incomplete'], result['status']['invalid'],
                result['status']['unattempted'])
            + '<table><tr>' + head + '</tr>' + ''.join(rows) + '</table><p><a href="raw/result.json">상세 결과</a> · '
            '<a href="raw/manifest.json">manifest</a> · <a href="provenance.json">출처</a></p></html>')
    (output / 'index.html').write_text(page)
    (output / 'raw').mkdir()
    originals = {}
    for name in ('manifest.json', 'result.json', 'ledger.jsonl'):
        shutil.copyfile(run / name, output / 'raw' / name)
        originals[name] = sha(run / name)
    sources = SOURCES + ('integration/laya_imitation/headtohead.py',)
    for rel in sources:
        target = output / 'renderer-source' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(c.ROOT / rel, target)
    provenance = dict(experiment=meta['experiment'], plan=meta['plan'], run=str(run), source_files=originals,
                      decisions=total, games=len(result['outcomes']), ui_version=UI_VERSION, renderer=RENDERER,
                      extensions=EXTENSIONS + ['비교 모델 진영 페이지'],
                      renderer_source={rel: sha(c.ROOT / rel) for rel in sources}, offline_input_response=True,
                      animation_requires_network=True, changelog=meta['changelog'])
    atomic(output / 'provenance.json', provenance)
    seal(output)
    return dict(output=str(output), decisions=total, games=len(result['outcomes']))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='laya-imitation-headtohead')
    sub = parser.add_subparsers(dest='command', required=True)
    w = sub.add_parser('worker')
    w.add_argument('--attempt', required=True)
    w.add_argument('--role', choices=('p1', 'p2'), required=True)
    args = parser.parse_args(argv)
    return worker(args.attempt, args.role)


if __name__ == '__main__':
    sys.exit(main())
