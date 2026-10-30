"""EX-119: the EX-118 selected policy on the sealed EX-089 32-slot schedule against Abyssal.

The per-game worker, player, Session, opponent and audit are EX-071's (`imitation/player.py`,
`imitation/battle.audit_match`), driven by a `request.json` in their format. What is new here:
the EX-089 schedule mapping, owned laya serving on GPU0, port 8107, the 300-turn / 600-decision
limits (applied by patching the EX-071 worker in this process only), the ledger and the summary.
Stages: mock (2 CPU games, not scored), prepare (freeze), execute (32 slots), export (report, viewer, seal).
"""
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

from . import config as c
from .storage import append_jsonl, atomic, read, seal, sha, source_identity, verify_seal

BATTLE_SECONDS = 1200
CLEANUP_SECONDS = 60


# ----------------------------------------------------------------------------- schedule

def _pack(showdown_team):
    script = ("const {Teams}=require('./pokemon-showdown/dist/sim/teams.js');"
              "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const t=Teams.import(s);"
              "process.stdout.write(JSON.stringify({packed:Teams.pack(t),n:t.length}))});")
    out = subprocess.run(['node', '-e', script], input=showdown_team, text=True, capture_output=True, check=True,
                         cwd=c.ROOT)
    value = json.loads(out.stdout)
    if value['n'] != 6:
        raise ValueError('team did not import as six sets')
    return value['packed']


def schedule_from_ex089():
    bad = verify_seal(c.EX089_COLLECTION) if (c.EX089_COLLECTION / 'checksums.sha256').exists() else ['missing']
    manifest = read(c.EX089_COLLECTION / 'manifest.json')
    if 'manifest.json' in bad or bad == ['missing']:
        raise ValueError('EX-089 manifest seal failed')
    packed = {k: dict(packed=_pack(v['showdown_team']), source=v['source'], sha256=v['sha256'])
              for k, v in manifest['teams'].items()}
    rows = []
    for r in sorted(manifest['schedule'], key=lambda r: r['submission_order']):
        side = r['jev_actor']
        index = 0 if side == 'p1' else 1
        rows.append(dict(slot_id=r['slot_id'], pair_id=r['paired_slot_id'], block_id=r['block_id'],
                         submission_order=r['submission_order'], model='laya-selected', model_side=side,
                         opponent='abyssal', team_ids=dict(p1=r['teams'][0], p2=r['teams'][1]),
                         teams=dict(p1=packed[r['teams'][0]], p2=packed[r['teams'][1]]),
                         simulator_seed=[int(x) for x in r['battle_seed'].split(',')],
                         model_seed=r['actor_seeds'][index], opponent_seed=r['actor_seeds'][1 - index]))
    if len(rows) != 32 or len({r['pair_id'] for r in rows}) != 16:
        raise ValueError('EX-089 schedule is not 32 slots / 16 pairs')
    return rows, dict(manifest_sha256=sha(c.EX089_COLLECTION / 'manifest.json'),
                      schedule_sha256=manifest.get('schedule_sha256'))


# ----------------------------------------------------------------------------- serving

class Serving:
    """Owned laya serving subprocess (laya 0.4.13 interpreter) on GPU0 or CPU."""

    def __init__(self, directory, checkpoint, model, device, render='v1'):
        self.directory, self.checkpoint, self.model, self.device = Path(directory), checkpoint, model, device
        self.render = render
        self.process = self.log = self.identity = None

    def start(self, env):
        from integration.pokechamp.imitation.player import http_json
        ready = self.directory / ('serving-%s.ready.json' % self.model)
        self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
        child = dict(os.environ, PYTHONPATH=str(c.ROOT), PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1',
                     TOKENIZERS_PARALLELISM='false', **env)
        self.process = subprocess.Popen(
            [str(c.LAYA_PYTHON), '-m', 'integration.laya_imitation.cli', 'serve', '--checkpoint', str(self.checkpoint),
             '--model', self.model, '--device', self.device, '--ready-file', str(ready), '--render', self.render],
            cwd=c.ROOT, env=child, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
            start_new_session=True)
        started = time.monotonic()
        while time.monotonic() - started < 300:
            if self.process.poll() is not None:
                raise RuntimeError('serving exited before readiness')
            if ready.exists():
                info = read(ready)
                health = http_json(info['endpoint'], '/health', timeout=5)
                self.identity = dict(health, endpoint=info['endpoint'], pid=self.process.pid)
                return self.identity
            time.sleep(0.5)
        raise RuntimeError('serving readiness timeout')

    def check(self, expected_sha):
        from integration.pokechamp.imitation.player import http_json
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError('owned serving is not running')
        health = http_json(self.identity['endpoint'], '/health', timeout=5)
        if health.get('checkpoint_sha256') != expected_sha or health.get('model') != self.model:
            raise RuntimeError('serving identity changed')

    def stop(self):
        from integration.pokechamp.benchmark import terminate
        if self.process is not None:
            terminate(self.process)
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None


# ----------------------------------------------------------------------------- one game

def _outcome(row, status, **extra):
    return dict(slot_id=row['slot_id'], pair_id=row['pair_id'], model=row['model'], model_side=row['model_side'],
                opponent=row['opponent'], status=status, result=None, **extra)


def play_slot(directory, row, serving_identity, check, port=c.PORT, worker='integration.laya_imitation.battle',
              prefixes=('lay', 'aby'), before=None, audit=None):
    """One scheduled game in its own directory; never re-run (the directory is created exclusively).

    The keyword hooks are for EX-134's laya-vs-laya games (`headtohead`): the worker module, the user-name prefixes
    of the model and the other side, `before(directory)` after `request.json` is written, and the audit function.
    The defaults are the Abyssal path, unchanged."""
    from integration.pokechamp import cli as pcli
    from integration.pokechamp.benchmark import terminate
    from integration.pokechamp.imitation.battle import audit_match
    from integration.pokechamp.parallel_server import BattleServer
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + BATTLE_SECONDS
    tag = hashlib.sha256(row['slot_id'].encode()).hexdigest()[:12]
    names = {side: (prefixes[0] if side == row['model_side'] else prefixes[1]) + tag for side in ('p1', 'p2')}
    serving = dict(endpoint=serving_identity['endpoint'], checkpoint_sha256=serving_identity['checkpoint_sha256'])
    atomic(directory / 'request.json', dict(slot=row, names=names, serving=serving, deadline_monotonic=deadline,
                                            port=port), immutable=True)
    if before is not None:
        before(directory)
    server = BattleServer(directory, port, ','.join(map(str, row['simulator_seed'])))
    processes, logs, cleanup = {}, [], []
    started = time.monotonic()
    outcome = _outcome(row, 'failed', failure_scope='phase')
    try:
        check()
        server.start()
        for actor in ('p1', 'p2'):
            seed = row['model_seed'] if actor == row['model_side'] else row['opponent_seed']
            stream = (directory / ('%s.log' % actor)).open('xb')
            logs.append(stream)
            env = pcli._child_environment(PYTHONPATH='%s:%s' % (c.ROOT, c.ROOT / 'pokechamp'), CUDA_VISIBLE_DEVICES='',
                                          PYTHONHASHSEED=str(seed), OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                                          MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
            processes[actor] = subprocess.Popen(
                [str(c.BATTLE_PYTHON), '-m', worker, 'worker', '--attempt', str(directory),
                 '--role', actor], cwd=c.ROOT / 'pokechamp', env=env, stdin=subprocess.DEVNULL, stdout=stream,
                stderr=subprocess.STDOUT, start_new_session=True)
        next_guard = time.monotonic() + 30
        while True:
            if time.monotonic() >= deadline:
                outcome.update(status='incomplete', reason='time_limit', failure_scope='battle')
                break
            if time.monotonic() >= next_guard:
                check()
                next_guard = time.monotonic() + 30
            results = {a: read(directory / ('%s.result.json' % a)) for a in processes
                       if (directory / ('%s.result.json' % a)).exists()}
            stopped = [r for r in results.values() if r['status'] != 'completed']
            if stopped:
                first = next((r for r in stopped if r.get('failure_scope') == 'phase'), stopped[0])
                outcome.update(status=first['status'], failure_scope=first.get('failure_scope'),
                               reason=first.get('reason'), error=first.get('error'), actor_results=results)
                break
            if len(results) == 2:
                model = results[row['model_side']]
                other = results['p2' if row['model_side'] == 'p1' else 'p1']
                if model['result'] != dict(win='loss', loss='win', draw='draw')[other['result']] \
                        or model['turns'] != other['turns']:
                    raise RuntimeError('actor terminal results disagree')
                for actor, result in results.items():
                    expected = row['model_seed'] if actor == row['model_side'] else row['opponent_seed']
                    if result['seed'] != expected or result['python_hash_seed'] != str(expected):
                        raise RuntimeError('actor seed or role mismatch')
                outcome.update(status='completed', result=model['result'], turns=model['turns'],
                               battle_tag=model['battle_tag'], actor_results=results, failure_scope=None)
                break
            for actor, process in processes.items():
                if process.poll() is not None and actor not in results:
                    raise RuntimeError('actor exited without a result: ' + actor)
            time.sleep(0.1)
    except BaseException as error:
        outcome.update(status='failed', result=None, failure_scope='phase',
                       error=dict(type=type(error).__name__, detail=str(error)))
    finally:
        atomic(directory / 'cancel.json', dict(reason='attempt ended'))
        for process in processes.values():
            try:
                terminate(process)
            except Exception as error:
                cleanup.append(dict(type=type(error).__name__, detail=str(error)))
        for stream in logs:
            stream.close()
        try:
            server.close()
        except Exception as error:
            cleanup.append(dict(type=type(error).__name__, detail=str(error)))
        if cleanup:
            outcome.update(status='invalid' if outcome['status'] == 'completed' else 'failed', result=None,
                           failure_scope='phase', cleanup_errors=cleanup)
        outcome.update(elapsed_seconds=time.monotonic() - started)
    try:
        audit = (audit or audit_match)(directory, outcome)
    except Exception as error:
        audit = dict(passed=False, errors=[dict(error=str(error), type=type(error).__name__)], counts={},
                     inference_seconds=[])
    atomic(directory / 'audit.json', audit, immutable=True)
    if not audit['passed']:
        outcome.update(status='invalid' if outcome['status'] == 'completed' else 'failed', result=None,
                       failure_scope='phase', audit_passed=False)
    else:
        outcome['audit_passed'] = True
    atomic(directory / 'outcome.json', outcome, immutable=True)
    return outcome, audit


# ----------------------------------------------------------------------------- summary

def summarize(rows, outcomes, latencies, seed=20261022, draws=10000):
    by_slot = {o['slot_id']: o for o in outcomes}
    normal = [o for o in outcomes if o['status'] == 'completed']
    score = {'win': 1.0, 'draw': 0.5, 'loss': 0.0}
    pairs = {}
    for r in rows:
        o = by_slot.get(r['slot_id'])
        if o and o['status'] == 'completed':
            pairs.setdefault(r['pair_id'], []).append(score[o['result']])
    complete = [sum(v) / 2 for v in pairs.values() if len(v) == 2]
    rng = random.Random(seed)
    boot = sorted(sum(rng.choice(complete) for _ in complete) / len(complete) for _ in range(draws)) if complete else []
    counts = {s: sum(o['status'] == s for o in outcomes) for s in ('completed', 'failed', 'incomplete', 'invalid')}
    counts['unattempted'] = len(rows) - len(outcomes)
    wins = sum(o['result'] == 'win' for o in normal)
    draws_ = sum(o['result'] == 'draw' for o in normal)
    lat = sorted(latencies)
    return dict(scheduled=len(rows), status=counts, wins=wins, draws=draws_, losses=len(normal) - wins - draws_,
                mean_score=(wins + 0.5 * draws_) / len(normal) if normal else None,
                completed_pairs=len(complete),
                pair_bootstrap_95=[boot[int(.025 * draws)], boot[int(.975 * draws) - 1]] if boot else None,
                inference_seconds=dict(n=len(lat), p50=lat[len(lat) // 2] if lat else None,
                                       p95=lat[int(.95 * (len(lat) - 1))] if lat else None))


# ----------------------------------------------------------------------------- stages

def _run(directory, rows, checkpoint, model, device, expected_sha=None, hours=c.BATTLE_HOURS):
    from .resources import gpu0, port
    directory.mkdir(parents=True, exist_ok=True)
    ledger = directory / 'ledger.jsonl'
    games = directory / 'games'
    outcomes = [read(games / r['slot_id'] / 'outcome.json') for r in rows
                if (games / r['slot_id'] / 'outcome.json').exists()]
    claimed = {r['slot_id'] for r in rows if (games / r['slot_id']).exists()}
    if claimed - {o['slot_id'] for o in outcomes}:
        raise RuntimeError('a claimed slot has no outcome; it is not replayed: %s' % sorted(claimed))
    if not (directory / 'clock.json').exists():
        atomic(directory / 'clock.json', dict(first_started=time.time(), hours=hours), immutable=True)
    deadline = read(directory / 'clock.json')['first_started'] + hours * 3600
    latencies = []
    for o in outcomes:
        latencies += read(games / o['slot_id'] / 'audit.json')['inference_seconds']
    error = None
    if device == 'cuda':
        gpu = gpu0()
    else:
        from contextlib import nullcontext
        gpu = nullcontext((dict(CUDA_VISIBLE_DEVICES=''), None))
    with port(), gpu as (env, _):
        serving = Serving(directory, checkpoint, model, device)
        try:
            identity = serving.start(env)
            if expected_sha and identity['checkpoint_sha256'] != expected_sha:
                raise RuntimeError('served checkpoint differs from the frozen one')
            append_jsonl(ledger, dict(type='serving_started', identity=identity, at=time.time()))
            for row in rows:
                if row['slot_id'] in claimed:
                    continue
                if time.time() > deadline - CLEANUP_SECONDS:
                    append_jsonl(ledger, dict(type='admission_closed', reason='stage_time_limit', at=time.time()))
                    break
                append_jsonl(ledger, dict(type='slot_claim', slot_id=row['slot_id'], at=time.time()))
                outcome, audit = play_slot(games / row['slot_id'], row, identity,
                                           lambda: serving.check(identity['checkpoint_sha256']))
                outcomes.append(outcome)
                latencies += audit['inference_seconds']
                append_jsonl(ledger, dict(type='slot_finished', outcome=outcome, at=time.time()))
                atomic(directory / 'status.json', dict(stage='running', done=len(outcomes), of=len(rows),
                                                       summary=summarize(rows, outcomes, latencies), at=time.time()))
                if outcome.get('failure_scope') == 'phase':
                    error = dict(type='phase_halt', slot_id=row['slot_id'], reason=outcome.get('error'))
                    break
        except BaseException as caught:
            error = dict(type=type(caught).__name__, detail=str(caught))
        finally:
            serving.stop()
            append_jsonl(ledger, dict(type='closed', error=error, at=time.time()))
    result = dict(summarize(rows, outcomes, latencies), outcomes=outcomes, phase_error=error)
    return result


def mock():
    """Two CPU games (one side-swapped pair) with the untrained base checkpoint; not part of any denominator."""
    rows, _ = schedule_from_ex089()
    pair = [r for r in rows if r['pair_id'] == rows[0]['pair_id']]
    for r in pair:
        r['model'] = 'laya-initial'
    directory = c.RUN_BATTLE / 'mock'
    if (directory / 'result.json').exists():
        raise RuntimeError('mock already completed')
    result = _run(directory, pair, c.MODEL_DIR, 'laya-initial', 'cpu', hours=1.0)
    atomic(directory / 'result.json', result, immutable=True)
    atomic(directory / 'manifest.json', dict(experiment_id='EX-119-mock', schedule=pair), immutable=True)
    print(json.dumps({k: v for k, v in result.items() if k != 'outcomes'}, ensure_ascii=False))


def prepare():
    from integration.project_context.registry import freeze_document, resolve_record
    from .serving import checkpoint_identity, renderer_matches_dataset
    out = c.RUN_BATTLE
    if (out / 'manifest.json').exists():
        raise RuntimeError('EX-119 already prepared')
    training = read(c.RUN_TRAINING / 'status.json')
    if training['stage'] != 'completed' or verify_seal(c.RUN_TRAINING):
        raise RuntimeError('EX-118 is not completed and sealed')
    if not renderer_matches_dataset():
        raise RuntimeError('renderer differs from the dataset generator')
    rows, ex089 = schedule_from_ex089()
    checkpoint = c.RUN_TRAINING / 'checkpoints/selected'
    freeze_document(resolve_record('EX-119'), out / 'protocol/EX-119.md')
    atomic(out / 'source/identity.json', source_identity(), immutable=True)
    manifest = dict(experiment_id='EX-119', schedule=rows, ex089=ex089, checkpoint=str(checkpoint),
                    checkpoint_sha256=checkpoint_identity(checkpoint), model='laya-selected', opponent='abyssal',
                    port=c.PORT, gpu_uuid=c.GPU_UUID, turn_limit=c.TURN_LIMIT, decision_limit=c.DECISION_LIMIT,
                    battle_seconds=BATTLE_SECONDS, stage_hours=c.BATTLE_HOURS, retries=0, fallback=0, requery=0,
                    probability_meaning='action_selection_probability', render=read(c.DATASET / 'manifest.json')['render'],
                    created_at=time.time())
    atomic(out / 'manifest.json', manifest, immutable=True)
    atomic(out / 'status.json', dict(stage='prepared', at=time.time()))
    print(json.dumps(dict(prepared=len(rows), checkpoint_sha256=manifest['checkpoint_sha256'])))


def execute():
    out = c.RUN_BATTLE
    manifest = read(out / 'manifest.json')
    if (out / 'result.json').exists():
        raise RuntimeError('EX-119 already executed')
    if source_identity()['files'] != read(out / 'source/identity.json')['files']:
        raise RuntimeError('source changed after the EX-119 freeze')
    result = _run(out, manifest['schedule'], manifest['checkpoint'], 'laya-selected', 'cuda',
                  expected_sha=manifest['checkpoint_sha256'])
    result['all_slots_attempted'] = len(result['outcomes']) == len(manifest['schedule'])
    atomic(out / 'result.json', result, immutable=True)
    atomic(out / 'status.json', dict(stage='executed', at=time.time(),
                                     summary={k: v for k, v in result.items() if k != 'outcomes'}))
    print(json.dumps({k: v for k, v in result.items() if k != 'outcomes'}, ensure_ascii=False))


def export():
    from .reporting import battle_report
    from .viewer import export as export_viewer
    out = c.RUN_BATTLE
    result = read(out / 'result.json')
    viewer = export_viewer(out, c.VIEWER)
    battle_report(out, result, viewer)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(),
                                     summary={k: v for k, v in result.items() if k != 'outcomes'}))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(c.VIEWER / 'index.html'))))


# ----------------------------------------------------------------------------- worker

# D-198: models trained on `early_history` get it in their live inputs; every other model's input is unchanged.
EARLY_HISTORY_MODELS = ('laya-v6ht', 'laya-v6ht-initial')


def worker(attempt, role):
    """EX-071 worker with this experiment's turn and decision limits."""
    from integration.pokechamp.imitation import player as p
    p.MAX_TURNS = c.TURN_LIMIT
    early = read(Path(attempt) / 'request.json')['slot']['model'] in EARLY_HISTORY_MODELS

    class LimitedSession(p.Session):
        async def evaluate(self, value, decision):
            if self.calls >= c.DECISION_LIMIT:
                raise p.BattleLimit('decision_limit')
            return await super().evaluate(value, decision)

        def generate(self, official, prefix, actions, *, actor):
            if not early:
                return super().generate(official, prefix, actions, actor=actor)
            if self.bridge is None:
                from integration.pokechamp.imitation.metamon_bridge import BridgeClient
                self.bridge = BridgeClient()
            snapshot = self.bridge.snapshot(p.public_prefix(prefix), self.own_sets, actor,
                                            p.decision_kind(official['request']), early_history=True)
            return p.from_snapshot(snapshot, actions), snapshot

    p.Session = LimitedSession
    result = asyncio.run(p.worker(attempt, role))
    print(p.compact(result))
    return 0 if result['status'] == 'completed' else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    w = sub.add_parser('worker')
    w.add_argument('--attempt', type=Path, required=True)
    w.add_argument('--role', choices=('p1', 'p2'), required=True)
    args = parser.parse_args(argv)
    return worker(args.attempt, args.role)


if __name__ == '__main__':
    sys.exit(main())
