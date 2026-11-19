"""EX-173..176: laya (v10rt EX-167; EP-233: v11rt EX-171, v11rtc EX-172) vs foul-play (3 s x 4 parallel MCTS) on the sealed EX-120 schedule, CPU only (D-211).

The EX-120 128 slots with Abyssal replaced by foul-play; teams, sides, simulator seeds and the 300-turn / 600-decision
limits are EX-168's, so each slot pairs with EX-168's v10rt game against Abyssal.

- Per game: `laya_imitation.battle.play_slot` unchanged (owned local server, ledger, audits), with this module as the
  worker. The model side runs `laya_ladder.battle`'s worker; the other side execs the foul-play venv on
  `integration.foulplay.actor`.
- Serving: one v10rt `laya_ladder.serve` on CPU (8 threads). Up to four games at once on ports 8100..8103.
- Stages: mock (first pair, outside every denominator) -> prepare (freeze) -> execute -> export. No re-runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import threading
import time
from contextlib import ExitStack
from pathlib import Path

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import append_jsonl, atomic, read, seal, sha, source_identity, verify_seal

from . import paths as P

WORKER = 'integration.foulplay.battle'
MODEL = 'laya-v10rt'
OPPONENT = 'foulplay'
PREFIXES = ('lay', 'fpl')
EX168 = P.SHARED / 'runs/model-training/EX-168'
EX167 = P.SHARED / 'runs/model-training/EX-167'
EX174 = P.SHARED / 'runs/model-training/EX-174'
DRAWS = 10000
BLIM_TEAMS = 'Blim 팀 64개(32개 대진 × 시드 2 × 팀 교환, 128슬롯)'


class Study:
    """One foul-play run. `model` / `label` / `source` (experiment, run dir) / `render` name the laya side;
    `baseline` is a same-slot reference (label, run dir, outcome key of a row) or None."""

    def __init__(self, **kw):
        self.__dict__.update(dict(model=MODEL, label='v10rt', source=('EX-167', EX167), render='v10',
                                  ports=P.PORTS, baseline=None), **kw)

    def rows(self):
        return make_schedule(self.base(), self.model)

    @property
    def checkpoint(self):
        return self.source[1] / 'checkpoints/selected'


def _blim_base():
    from . import blim
    return blim.base_schedule()


def _v11(experiment, model, label, source, ports):
    return Study(experiment=experiment, run=P.SHARED / 'runs/model-training' / experiment,
                 viewer=P.ROOT / 'exports/battle_viewers' / experiment.replace('-', '').lower(), base=_blim_base,
                 teams=BLIM_TEAMS, slug=experiment.replace('-', '').lower(), model=model, label=label,
                 source=(source, P.SHARED / 'runs/model-training' / source), render='v11', ports=ports,
                 baseline=('EX-174 v10rt', EX174, lambda r: r['slot_id']))


STUDIES = {
    'EX-173': Study(experiment='EX-173', run=P.RUN, viewer=P.VIEWER, base=lambda: base_schedule(),
                    baseline=('EX-168 v10rt 대 Abyssal', EX168, lambda r: 'v10rt-' + r['base_slot_id']),
                    teams='EX-120 일정(새 팀 32개, 128슬롯)', slug='ex173'),
    'EX-174': Study(experiment='EX-174', run=EX174, viewer=P.ROOT / 'exports/battle_viewers/ex174', base=_blim_base,
                    teams=BLIM_TEAMS, slug='ex174'),
    # EP-233: the v11 models on EX-174's sealed Blim schedule, same-slot against EX-174's v10rt games
    'EX-175': _v11('EX-175', 'laya-v11rt', 'v11rt', 'EX-171', (8100, 8101, 8102, 8103)),
    'EX-176': _v11('EX-176', 'laya-v11rtc', 'v11rtc', 'EX-172', (8104, 8105, 8106, 8107)),
}


# ----------------------------------------------------------------------------- schedule and teams

def make_schedule(base, model=MODEL):
    """Base rows -> foul-play rows (same order, sides, seeds and teams; the opponent is foul-play)."""
    out = []
    for order, row in enumerate(base, 1):
        out.append(dict(row, slot_id='fp-' + row['slot_id'], pair_id='fp-' + row['pair_id'],
                        base_slot_id=row['slot_id'], base_pair_id=row['pair_id'], model=model, opponent=OPPONENT,
                        submission_order=order))
    return out


def base_schedule():
    from integration.laya_imitation.comparison import _base_schedule
    rows = _base_schedule()
    if len(rows) != 128:
        raise RuntimeError('EX-120 schedule is not 128 slots')
    return rows


def team_export(packed):
    """Packed Showdown team -> export text (foul-play's `export_to_dict` input), by the pinned Showdown dist."""
    script = ("const {Teams}=require('./pokemon-showdown/dist/sim/teams.js');"
              "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const t=Teams.unpack(s);"
              "process.stdout.write(JSON.stringify({text:Teams.export(t),n:t.length}))});")
    out = subprocess.run(['node', '-e', script], input=packed, text=True, capture_output=True, check=True, cwd=c.ROOT)
    value = json.loads(out.stdout)
    if value['n'] != 6:
        raise ValueError('packed team did not unpack into six sets')
    return value['text']


# ----------------------------------------------------------------------------- worker

def worker(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('command')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--role', choices=('p1', 'p2'), required=True)
    args = parser.parse_args(argv)
    row = read(args.attempt / 'request.json')['slot']
    if args.role == row['model_side']:
        from integration.laya_imitation import battle as base, serving
        from integration.laya_ladder import battle as ladder
        from .serve_v11 import MODELS as V11
        serving.MODELS = tuple(dict.fromkeys(serving.MODELS + V11))
        base.EARLY_HISTORY_MODELS = tuple(base.EARLY_HISTORY_MODELS) + V11    # v11 = v10 input + fixes
        return ladder.worker(argv)
    (args.attempt / 'foulplay-team.txt').write_text(team_export(row['teams'][args.role]['packed']))
    env = dict(os.environ, PYTHONPATH='%s:%s' % (c.ROOT, P.FP_SOURCE), PYTHONDONTWRITEBYTECODE='1')
    os.execve(str(P.FP_PYTHON), [str(P.FP_PYTHON), '-m', 'integration.foulplay.actor',
                                 '--attempt', str(args.attempt), '--role', args.role], env)


# ----------------------------------------------------------------------------- identity

def foulplay_identity():
    caches = {('fp', 'data', 'smogon_stats_cache'), ('fp', 'data', 'pkmn_sets_cache')}   # sealed by DATA_SUMS
    files = {}
    for path in sorted(P.FP_SOURCE.rglob('*')):
        rel = path.relative_to(P.FP_SOURCE)
        if path.is_file() and '__pycache__' not in rel.parts and rel.parts[:3] not in caches:
            files[str(rel)] = sha(path)
    engine = subprocess.check_output([str(P.FP_PYTHON), '-c', 'import importlib.metadata as m;'
                                      'print(m.version("poke-engine"))'], text=True).strip()
    return dict(commit=P.FP_COMMIT, files=files, data_sums=P.DATA_SUMS.read_text(), poke_engine=engine,
                search=dict(time_ms=P.SEARCH_TIME_MS, parallelism=P.SEARCH_PARALLELISM, threads=P.SEARCH_THREADS),
                smogon_url=P.SMOGON_URL)


def identity():
    from integration.laya_ladder import battle as ladder
    own = {p.name: sha(p) for p in sorted((c.ROOT / 'integration/foulplay').glob('*.py'))}
    v11 = {n: sha(c.ROOT / 'integration/laya_v11' / n) for n in ('render_v11.py', 'judge_fixed.cjs', 'paths.py')}
    return dict(foulplay_package=own, ladder=ladder.identity(), foulplay=foulplay_identity(),
                laya_imitation=source_identity()['files'], laya_v11=v11)


# ----------------------------------------------------------------------------- run

def _serving(directory, study):
    from integration.laya_imitation import serving
    from integration.laya_ladder import battle as ladder
    from .serve_v11 import MODELS as V11
    ladder.register()
    serving.MODELS = tuple(dict.fromkeys(serving.MODELS + V11))
    if study.render == 'v11':
        return ServingV11(directory, str(study.checkpoint), study.model, 'cpu', render='v10')
    return ladder.Serving(directory, str(study.checkpoint), study.model, 'cpu', render='v10')


def _serving_v11_class():
    from integration.laya_imitation.battle import Serving as Base
    from integration.laya_v10 import paths as p10

    class ServingV11(Base):
        """`laya_ladder.battle.Serving` started on `integration.foulplay.serve_v11` (v11 input)."""

        def start(self, env):
            from integration.pokechamp.imitation.player import http_json
            ready = self.directory / ('serving-%s.ready.json' % self.model)
            self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
            child = dict(os.environ, PYTHONPATH='%s:%s' % (p10.LAYA_SOURCE, c.ROOT), PYTHONDONTWRITEBYTECODE='1',
                         HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', **env)
            self.process = subprocess.Popen(
                [str(c.LAYA_PYTHON), '-m', 'integration.foulplay.serve_v11', '--checkpoint', str(self.checkpoint),
                 '--model', self.model, '--device', self.device, '--ready-file', str(ready)],
                cwd=c.ROOT, env=child, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                start_new_session=True)
            started = time.monotonic()
            while time.monotonic() - started < 300:
                if self.process.poll() is not None:
                    raise RuntimeError('serving exited before readiness')
                if ready.exists():
                    info = read(ready)
                    if not info.get('v11_render'):
                        raise RuntimeError('serving did not report the v11 input')
                    health = http_json(info['endpoint'], '/health', timeout=5)
                    self.identity = dict(health, endpoint=info['endpoint'], pid=self.process.pid,
                                         v11_render=info['v11_render'])
                    return self.identity
                time.sleep(0.5)
            raise RuntimeError('serving readiness timeout')

    return ServingV11


def ServingV11(*args, **kwargs):
    return _serving_v11_class()(*args, **kwargs)


def _run(directory, rows, hours, study, expected_sha=None, ports=None):
    ports = ports or study.ports
    from integration.laya_imitation.battle import CLEANUP_SECONDS, play_slot
    from integration.laya_imitation.resources import port as port_lock
    directory.mkdir(parents=True, exist_ok=True)
    ledger, games = directory / 'ledger.jsonl', directory / 'games'
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
    pending = [r for r in rows if r['slot_id'] not in claimed]
    lock, stop, errors = threading.Lock(), threading.Event(), []
    serving = _serving(directory, study)

    def lane(port, identity):
        while not stop.is_set():
            with lock:
                if not pending:
                    return
                if time.time() > deadline - CLEANUP_SECONDS:
                    append_jsonl(ledger, dict(type='admission_closed', reason='stage_time_limit', at=time.time()))
                    stop.set()
                    return
                row = pending.pop(0)
                append_jsonl(ledger, dict(type='slot_claim', slot_id=row['slot_id'], port=port, at=time.time()))
            outcome, audit = play_slot(games / row['slot_id'], row, identity,
                                       lambda: serving.check(identity['checkpoint_sha256']), port=port,
                                       worker=WORKER, prefixes=PREFIXES)
            with lock:
                outcomes.append(outcome)
                latencies.extend(audit['inference_seconds'])
                append_jsonl(ledger, dict(type='slot_finished', outcome=outcome, at=time.time()))
                done = [o for o in outcomes if o['status'] == 'completed']
                atomic(directory / 'status.json', dict(
                    stage='running', done=len(outcomes), of=len(rows), at=time.time(),
                    wins=sum(o['result'] == 'win' for o in done), losses=sum(o['result'] == 'loss' for o in done),
                    other=len(outcomes) - len(done)))
                if outcome.get('failure_scope') == 'phase':
                    errors.append(dict(type='phase_halt', slot_id=row['slot_id'], reason=outcome.get('error')))
                    stop.set()

    error = None
    with ExitStack() as stack:
        held = [stack.enter_context(port_lock(p)) for p in ports]
        try:
            identity = serving.start(dict(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS=P.SERVING_THREADS,
                                          MKL_NUM_THREADS=P.SERVING_THREADS))
            if expected_sha and identity['checkpoint_sha256'] != expected_sha:
                raise RuntimeError('served checkpoint differs from the frozen one')
            append_jsonl(ledger, dict(type='serving_started', identity=identity, ports=held, at=time.time()))
            threads = [threading.Thread(target=lane, args=(p, identity), daemon=True) for p in held]
            for t in threads:
                t.start()
                time.sleep(2)
            for t in threads:
                t.join()
            error = errors[0] if errors else None
        except BaseException as caught:
            stop.set()
            error = dict(type=type(caught).__name__, detail=str(caught))
        finally:
            serving.stop()
            append_jsonl(ledger, dict(type='closed', error=error, at=time.time()))
    order = {r['slot_id']: i for i, r in enumerate(rows)}
    outcomes.sort(key=lambda o: order[o['slot_id']])
    return outcomes, latencies, error


# ----------------------------------------------------------------------------- summary

def cluster_bootstrap(groups, seed=P.SEED, draws=DRAWS):
    if not groups:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(draws):
        sample = [rng.choice(groups) for _ in groups]
        means.append(sum(map(sum, sample)) / sum(map(len, sample)))
    means.sort()
    return [means[int(.025 * draws)], means[int(.975 * draws) - 1]]


def versus_baseline(rows, outcomes, study):
    """Same-slot difference: this game - the baseline game (laya side's score), matchup clusters.
    EX-173: EX-168 v10rt vs Abyssal; EX-175 / EX-176: EX-174 v10rt vs foul-play."""
    from integration.laya_imitation.generalization import SCORE
    label, run, key = study.baseline
    base = {o['slot_id']: o for o in read(run / 'result.json')['outcomes']}
    by_slot = {o['slot_id']: o for o in outcomes}
    clusters, rows_out = {}, []
    for r in rows:
        mine, theirs = by_slot.get(r['slot_id']), base.get(key(r))
        if not (mine and theirs and mine['status'] == 'completed' and theirs['status'] == 'completed'):
            continue
        d = SCORE[mine['result']] - SCORE[theirs['result']]
        clusters.setdefault(r['matchup_id'], []).append(d)
        rows_out.append(d)
    return dict(slots=len(rows_out), mean_diff=sum(rows_out) / len(rows_out) if rows_out else None,
                matchup_bootstrap_95=cluster_bootstrap(list(clusters.values())),
                foulplay_harder=sum(d < 0 for d in rows_out), foulplay_easier=sum(d > 0 for d in rows_out),
                same=sum(d == 0 for d in rows_out))


def opponent_report(directory, rows, outcomes):
    """foul-play side: decisions, search seconds, Tera use and terminal agreement."""
    seconds, tera_games, decisions = [], 0, 0
    for o in outcomes:
        game = directory / 'games' / o['slot_id']
        path = game / 'foulplay-events.jsonl'
        if not path.exists():
            continue
        tera = False
        for line in path.read_text().splitlines():
            e = json.loads(line)
            if e['type'] == 'decision':
                decisions += 1
                seconds.append(e['seconds'])
                choice = e['choice'] if isinstance(e['choice'], str) else ' '.join(e['choice'])
                tera = tera or 'terastallize' in choice   # EX-174 report: a list membership test counted 0
        tera_games += tera
    seconds.sort()
    pick = lambda q: seconds[int(q * (len(seconds) - 1))] if seconds else None
    return dict(decisions=decisions, seconds=dict(n=len(seconds), p50=pick(.5), p95=pick(.95), max=pick(1.0)),
                tera_games=tera_games)


def summarize_all(directory, rows, outcomes, latencies, study):
    from integration.laya_imitation.comparison import failed_moves, tera_usage
    from integration.laya_imitation.generalization import summarize_generalization
    summary = summarize_generalization(rows, outcomes, latencies)
    completed = summary['status']['completed']
    verdict = '판정 보류(정상 종료 %d/128 < 120)' % completed if completed < 120 else '보고'
    same = versus_baseline(rows, outcomes, study) if study.baseline else None
    out = dict(summary, verdict=verdict, baseline=dict(same, label=study.baseline[0]) if same else None,
               tera=tera_usage(directory, rows, outcomes), failed_moves=failed_moves(directory, rows, outcomes),
               foulplay=opponent_report(directory, rows, outcomes))
    if study.experiment == 'EX-173':
        out['versus_abyssal'] = same
    return out


# ----------------------------------------------------------------------------- stages

def mock(study):
    """The first scheduled pair (2 games), outside every denominator."""
    rows = study.rows()
    pair = [r for r in rows if r['pair_id'] == rows[0]['pair_id']]
    directory = study.run / 'mock'
    if (directory / 'result.json').exists():
        raise RuntimeError('%s mock already completed' % study.experiment)
    outcomes, latencies, error = _run(directory, pair, 1.0, study, ports=study.ports[:2])
    result = dict(outcomes=outcomes, latency=latencies, phase_error=error,
                  foulplay=opponent_report(directory, pair, outcomes))
    atomic(directory / 'result.json', result, immutable=True)
    atomic(directory / 'manifest.json', dict(experiment_id=study.experiment + '-mock', schedule=pair), immutable=True)
    print(json.dumps(dict(games=[(o['slot_id'], o['status'], o.get('result'), o.get('turns'), o.get('audit_passed'))
                                 for o in outcomes], error=error, foulplay=result['foulplay']), ensure_ascii=False))


def _renderer_matches(study):
    """The live renderer of this study's input equals its dataset generator (v10: v10-all; v11: v11-ladder)."""
    from integration.laya_imitation import serving
    if study.render == 'v10':
        return serving.renderer_matches_dataset('v10')
    from integration.laya_v10 import data_v10
    from integration.laya_v11 import data_v11
    data_v11.configure('ladder')            # installs v11 and points the check at the v11-ladder generator copy
    return data_v10.renderer_matches_dataset()


def prepare(study):
    from integration.laya_imitation.serving import checkpoint_identity
    from integration.laya_ladder import battle as ladder
    from integration.project_context.registry import freeze_document, resolve_record
    out, name = study.run, study.experiment
    if (out / 'manifest.json').exists():
        raise RuntimeError('%s already prepared' % name)
    source, source_run = study.source
    # EX-167 is sealed; EX-171 / EX-172 (EP-231) are completed but not sealed by their plan: the served checkpoint's
    # hash is frozen in the manifest and checked at serving start instead.
    sealed = (source_run / 'checksums.sha256').exists()
    if read(source_run / 'status.json')['stage'] != 'completed' or (sealed and verify_seal(source_run)):
        raise RuntimeError('%s is not completed (or its seal fails)' % source)
    if study.baseline and (read(study.baseline[1] / 'status.json')['stage'] != 'completed'
                           or verify_seal(study.baseline[1])):
        raise RuntimeError('the baseline run is not completed and sealed')
    ladder.register()
    frozen = identity()                     # before `_renderer_matches`, which re-points config for v11
    if not _renderer_matches(study):
        raise RuntimeError('the live %s renderer differs from its dataset generator' % study.render)
    mock_result = read(out / 'mock/result.json')
    if mock_result['phase_error'] or not all(o['status'] == 'completed' and o.get('audit_passed')
                                             for o in mock_result['outcomes']):
        raise RuntimeError('%s mock did not pass' % name)
    rows = study.rows()
    freeze_document(resolve_record(name), out / 'protocol' / (name + '.md'))
    atomic(out / 'source/identity.json', frozen, immutable=True)
    checkpoint = study.checkpoint
    manifest = dict(experiment_id=name, schedule=rows, teams=study.teams,
                    serving=dict(model=study.model, checkpoint=str(checkpoint), sha=checkpoint_identity(checkpoint),
                                 render=study.render, device='cpu', threads=P.SERVING_THREADS,
                                 usage_extension=False, guard=False, source=source, source_sealed=sealed),
                    opponent=dict(name=OPPONENT, **foulplay_identity()), ports=list(study.ports),
                    turn_limit=P.TURN_LIMIT, decision_limit=P.DECISION_LIMIT, stage_hours=P.HOURS,
                    retries=0, fallback=0, requery=0,
                    baseline=('%s (same slots)' % study.baseline[0]) if study.baseline else None,
                    probability_meaning='action_selection_probability', created_at=time.time())
    atomic(out / 'manifest.json', manifest, immutable=True)
    atomic(out / 'status.json', dict(stage='prepared', at=time.time()))
    print(json.dumps(dict(prepared=len(rows), sha=manifest['serving']['sha'])))


def execute(study):
    out = study.run
    manifest = read(out / 'manifest.json')
    if (out / 'result.json').exists():
        raise RuntimeError('%s already executed' % study.experiment)
    if identity() != read(out / 'source/identity.json'):
        raise RuntimeError('source, foul-play copy or inference cache changed after the %s freeze' % study.experiment)
    outcomes, latencies, error = _run(out, manifest['schedule'], P.HOURS, study, manifest['serving']['sha'])
    result = dict(summarize_all(out, manifest['schedule'], outcomes, latencies, study), outcomes=outcomes,
                  phase_error=error, all_slots_attempted=len(outcomes) == len(manifest['schedule']))
    atomic(out / 'result.json', result, immutable=True)
    atomic(out / 'status.json', dict(stage='executed', at=time.time(), verdict=result['verdict']))
    print(json.dumps(dict(record=(result['wins'], result['draws'], result['losses']), status=result['status'],
                          mean=result['mean_score'], ci=result['matchup_bootstrap_95'],
                          baseline=result['baseline'], foulplay=result['foulplay'], error=error),
                     ensure_ascii=False))


def _columns(row):
    return [('조합', row['matchup_id']), ('시드', row['seed_index']), ('laya 팀 유형', row['archetypes']['model']),
            ('상대 팀 유형', row['archetypes']['opponent'])]


def write_report(out, result, viewer, study):
    pct = lambda v: '—' if v is None else '%.3f' % v
    ci = lambda v: '—' if not v else '[%.3f, %.3f]' % tuple(v)
    va, fp, name = result.get('baseline') or result.get('versus_abyssal'), result['foulplay'], study.label
    lat = result['inference_seconds']
    tera = result['tera'].get(study.model, {})
    fm = result['failed_moves'].get(study.model, {}) if isinstance(result['failed_moves'], dict) else {}
    lines = [
        '# %s — laya %s 대 foul-play(3초 × 병렬 4) · %s' % (study.experiment, name, study.teams), '',
        '- 판정: %s' % result['verdict'],
        '- 상태: %s' % json.dumps(result['status'], ensure_ascii=False),
        '- %s 승/무/패: %d/%d/%d, 평균 점수 %s, 조합 클러스터 95%% %s' % (
            name, result['wins'], result['draws'], result['losses'], pct(result['mean_score']),
            ci(result['matchup_bootstrap_95'])),
        ('- 같은 슬롯 %s 대비 차이: %s, 95%% %s (%d슬롯; 이번이 나쁨 %d, 나음 %d, 같음 %d)' % (
            study.baseline[0], pct(va['mean_diff']), ci(va['matchup_bootstrap_95']), va['slots'],
            va['foulplay_harder'], va['foulplay_easier'], va['same'])) if va else '- 같은 슬롯 기준선: 없음',
        '- %s 결정 지연 p50 %s초, p95 %s초 (CPU 서빙)' % (name, pct(lat['p50']), pct(lat['p95'])),
        '- foul-play 결정 %d개, 탐색 시간 p50 %s초, p95 %s초, 최대 %s초, 테라 사용 경기 %d' % (
            fp['decisions'], pct(fp['seconds']['p50']), pct(fp['seconds']['p95']), pct(fp['seconds']['max']),
            fp['tera_games']),
        '- %s 테라: %s' % (name, json.dumps(tera, ensure_ascii=False)),
        '- %s 실패 기술: %s' % (name, json.dumps({k: v for k, v in fm.items() if not isinstance(v, (list, dict))},
                                               ensure_ascii=False)),
        '- 팀 유형별(laya): %s' % json.dumps(result['archetype_model'], ensure_ascii=False),
        '- 승리 턴: %s' % result['turns']['wins'], '- 패배 턴: %s' % result['turns']['losses'],
        '- 뷰어: %s' % viewer, '']
    (out / 'report.md').write_text('\n'.join(lines))


def export(study):
    from integration.laya_engine import judge as J
    from integration.laya_imitation.features import Calc
    from integration.laya_imitation.viewer import export as export_viewer
    from integration.laya_ladder import battle as ladder
    from integration.laya_v10 import data_v10
    ladder.register()
    if study.render == 'v11':
        from integration.laya_v11 import render_v11
        render_v11.install()                # the viewer shows the input the model was served
    out = study.run
    result = read(out / 'result.json')
    plan = 'EP-233' if study.render == 'v11' else 'EP-232'
    meta = dict(experiment=study.experiment, plan=plan, slug=study.slug, pairs=64,
                title='%s · laya %s 대 foul-play 128경기' % (study.experiment, study.label),
                heading='%s · laya %s(%s) 대 foul-play(MCTS 3초 × 병렬 4) · %s' % (
                    study.experiment, study.label, study.source[0], study.teams),
                intro='%s로 %s와 foul-play가 같은 팀을 번갈아 잡았습니다. %s는 CPU로 서빙했습니다. '
                      '확률은 행동 선택 확률이고 승률이 아닙니다. %s %d승 %d무 %d패.' % (
                          study.teams, study.label, study.label, study.label,
                          result['wins'], result['draws'], result['losses']),
                changelog='project_context/shared/viewers/CHANGELOG.md#ex148-laya-v1')
    with Calc() as calc, J.Judge() as judge:
        render = data_v10.live_renderer(calc, judge)
        viewer = export_viewer(out, study.viewer, meta=meta, columns=_columns, renderer_for=lambda row: render)
    write_report(out, result, viewer, study)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(), verdict=result['verdict']))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(study.viewer / 'index.html'), report=str(out / 'report.md'))))


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(worker(sys.argv[1:]))
    study = STUDIES[sys.argv[2] if len(sys.argv) > 2 else 'EX-173']
    {'mock': mock, 'prepare': prepare, 'execute': execute, 'export': export}[sys.argv[1]](study)
