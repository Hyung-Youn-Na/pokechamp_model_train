"""EX-181 (EP-235) runner, foul-play venv: smoke | prepare | search | report.

    PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m integration.laya_regret.run <stage>

prepare  replays every completed EX-174 game from the v10rt seat and writes `decisions.jsonl` (one row per decision)
         and `samples.jsonl` (foul-play's sampled states; round 0 for all decisions laya chose among options,
         round 1 again with new samples for the hash-chosen repeat set). One process.
search   runs one exact-iteration MCTS per sample in a process pool, appending `results.jsonl` (resumable). It
         submits nothing while a foul-play battle process exists (`paths.BATTLE_PATTERN`) or after `--until`; it
         then lets running samples finish and exits with status `paused`.
report   `integration.laya_regret.report`.
"""
from __future__ import annotations

import argparse
import calendar
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

from integration.laya_regret import paths as P


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def log(path, text):
    line = '[%s] %s' % (now(), text)
    print(line, flush=True)
    with open(path, 'a') as handle:
        handle.write(line + '\n')


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1) + '\n')
    os.replace(tmp, path)


def status(**value):
    path = P.RUN / 'status.json'
    old = json.loads(path.read_text()) if path.exists() else {}
    old.update(value, at=now())
    write_json(path, old)


def games():
    """Completed EX-174 games (the one time-limit game and the mock games are outside the denominator)."""
    rows = []
    for directory in sorted((P.SOURCE_RUN / 'games').iterdir()):
        outcome = json.loads((directory / 'outcome.json').read_text())
        if outcome.get('status') == 'completed':
            rows.append((directory, outcome))
    return rows


def schedule():
    rows = json.loads((P.SOURCE_RUN / 'collection/schedule.json').read_text())
    return {'fp-' + r['slot_id']: r for r in rows}


# ----------------------------------------------------------------------------------------------- prepare


def decision_rows(directory, outcome, slot_info, *, limit=None):
    """(decision rows, sample rows, game error) for one game."""
    from integration.laya_regret import replay as R
    from integration.laya_regret import search as S
    game = R.load_game(directory)
    slot = directory.name
    decisions, samples = [], []
    error = None
    try:
        for point in R.replay(game):
            if limit is not None and len(decisions) >= limit:
                break
            chosen = game['choices'].get(point.rqid)
            row = dict(slot=slot, pair=outcome.get('pair_id'), rqid=point.rqid, turn=point.turn,
                       model_side=outcome.get('model_side'), result=outcome.get('result'),
                       archetype=(slot_info or {}).get('archetypes', {}).get('model'),
                       opponent_archetype=(slot_info or {}).get('archetypes', {}).get('opponent'),
                       lead=point.lead, forced=point.forced, checks=point.checks)
            if chosen is None:
                row.update(status='no_choice', command=game['sends'].get(point.rqid))
                decisions.append(row)
                continue
            row.update(kind=chosen['kind'], command=chosen['command'], action=chosen['choice'],
                       automatic=chosen['automatic'], options=len(chosen['commands']), elapsed=chosen['elapsed'])
            try:
                row['laya_choice'] = R.fp_choice(point.view, chosen['command'])
                mapped = {}
                for action, command in chosen['commands'].items():
                    key = R.fp_choice(point.view, command)
                    mapped[key] = mapped.get(key, 0.0) + float(chosen['probabilities'].get(action, 0.0))
                row['laya_probs'] = mapped
                if chosen['automatic'] or len(chosen['commands']) < 2:
                    row['status'] = 'automatic'
                    decisions.append(row)
                    continue
                rounds = [0, 1] if S.in_repeat(slot, point.rqid) else [0]
                for round_ in rounds:
                    states, ms = S.sample_states(point.view, S.seed_of(slot, point.rqid, round_))
                    for index, (state, chance) in enumerate(states):
                        samples.append(dict(id='%s:%d:%d:%d' % (slot, point.rqid, round_, index), slot=slot,
                                            rqid=point.rqid, round=round_, index=index, chance=chance, ms=ms,
                                            iterations=P.ITERATIONS, state=state))
                    row['samples_%d' % round_] = len(states)
                row['repeat'] = len(rounds) > 1
                row['status'] = 'ready'
            except Exception as exc:                          # mapping / sampling defect: counted, not hidden
                row.update(status='error', error='%s: %s' % (type(exc).__name__, exc),
                           trace=traceback.format_exc(limit=3)[-600:])
            decisions.append(row)
    except Exception as exc:
        error = dict(slot=slot, error='%s: %s' % (type(exc).__name__, exc), trace=traceback.format_exc(limit=4)[-900:],
                     after_decisions=len(decisions))
    return decisions, samples, error


def prepare(args):
    P.RUN.mkdir(parents=True, exist_ok=True)
    plog = P.RUN / 'prepare.log'
    info = schedule()
    rows = games()
    log(plog, 'prepare: %d completed games, iterations %d, seed %d' % (len(rows), P.ITERATIONS, P.SEED))
    status(stage='prepare', games=len(rows))
    dtmp, stmp = P.RUN / 'decisions.jsonl.tmp', P.RUN / 'samples.jsonl.tmp'
    errors = []
    counts = {}
    started = time.monotonic()
    with open(dtmp, 'w') as dfile, open(stmp, 'w') as sfile:
        for n, (directory, outcome) in enumerate(rows, 1):
            decisions, samples, error = decision_rows(directory, outcome, info.get(directory.name))
            for row in decisions:
                counts[row['status']] = counts.get(row['status'], 0) + 1
                dfile.write(json.dumps(row, ensure_ascii=False) + '\n')
            for row in samples:
                sfile.write(json.dumps(row) + '\n')
            if error:
                errors.append(error)
            if n % 10 == 0 or n == len(rows):
                log(plog, '%d/%d games, %s, game errors %d, %.0fs' % (n, len(rows), counts, len(errors),
                                                                     time.monotonic() - started))
    os.replace(dtmp, P.RUN / 'decisions.jsonl')
    os.replace(stmp, P.RUN / 'samples.jsonl')
    write_json(P.RUN / 'prepare-errors.json', errors)
    status(stage='prepared', decisions=counts, game_errors=len(errors))
    log(plog, 'prepared: %s, game errors %d' % (counts, len(errors)))


# ----------------------------------------------------------------------------------------------- search


def battle_running():
    out = subprocess.run(['pgrep', '-f', '-a', P.BATTLE_PATTERN], capture_output=True, text=True).stdout
    me = {str(os.getpid()), str(os.getppid())}
    lines = [l for l in out.splitlines() if l.split(' ', 1)[0] not in me and 'pgrep' not in l]
    return lines


def available_gb():
    for line in open('/proc/meminfo'):
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) / 1024 / 1024
    return 0.0


def search(args):
    slog = P.RUN / 'search.log'
    until = calendar.timegm(time.strptime(args.until, '%Y-%m-%dT%H:%M:%SZ')) if args.until else None
    if args.wait:
        announced = False
        while True:
            if until is not None and time.time() >= until:
                log(slog, 'not started: --until %s passed while waiting' % args.until)
                status(stage='search_paused', reason='until')
                return 3
            running = battle_running()
            if not running:
                break
            if not announced:
                log(slog, 'waiting for foul-play battles to end: %s' % running[0][:160])
                status(stage='search_waiting')
                announced = True
            time.sleep(60)
        log(slog, 'no foul-play battle process; starting')
    if until is not None and time.time() >= until:
        log(slog, 'not started: --until %s passed' % args.until)
        status(stage='search_paused', reason='until')
        return 3
    if available_gb() < 30:
        log(slog, 'not started: available memory %.0f GB < 30 GB' % available_gb())
        status(stage='search_paused', reason='memory')
        return 4
    done = set()
    results = P.RUN / 'results.jsonl'
    if results.exists():
        for line in open(results):
            try:
                done.add(json.loads(line)['id'])
            except ValueError:
                pass                                          # a torn last line from a killed run
    jobs = []
    for line in open(P.RUN / 'samples.jsonl'):
        row = json.loads(line)
        if row['id'] not in done:
            jobs.append(dict(id=row['id'], state=row['state'], ms=row['ms'], iterations=row['iterations']))
    jobs.sort(key=lambda j: (j['id'].split(':')[2], j['id']))            # all round 0 first, then the repeat
    log(slog, 'search: %d to do, %d done, workers %d, iterations %d, until %s'
        % (len(jobs), len(done), args.workers, P.ITERATIONS, args.until))
    running = battle_running()
    if running:
        log(slog, 'not started: foul-play battle running: %s' % running[0][:160])
        status(stage='search_paused', reason='battle_running')
        return 3
    status(stage='search', todo=len(jobs), done=len(done))
    reason = None
    finished = 0
    started = last_check = last_log = time.monotonic()
    queue = iter(jobs)
    with open(results, 'a') as out, cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending = set()
        while True:
            if reason is None and time.monotonic() - last_check >= 5:
                last_check = time.monotonic()
                running = battle_running()
                if running:
                    reason = 'battle_running'
                    log(slog, 'pausing: foul-play battle started: %s' % running[0][:160])
                elif until is not None and time.time() >= until:
                    reason = 'until'
                    log(slog, 'pausing: reached --until %s' % args.until)
            while reason is None and len(pending) < args.workers:
                job = next(queue, None)
                if job is None:
                    break
                pending.add(pool.submit(P_mcts, job))
            if not pending:
                break
            ready, pending = cf.wait(pending, timeout=1.0, return_when=cf.FIRST_COMPLETED)
            for future in ready:
                out.write(json.dumps(future.result()) + '\n')
                finished += 1
            out.flush()
            if time.monotonic() - last_log >= 60:
                last_log = time.monotonic()
                rate = finished / max(1e-9, time.monotonic() - started)
                left = len(jobs) - finished
                log(slog, '%d/%d samples, %.2f/s, eta %.0f min' % (finished, len(jobs), rate, left / max(rate, 1e-9) / 60))
    left = len(jobs) - finished
    if left == 0:
        status(stage='searched', done=len(done) + finished)
        log(slog, 'search complete: %d samples this run' % finished)
        return 0
    status(stage='search_paused', reason=reason, done=len(done) + finished, left=left)
    log(slog, 'search paused (%s): %d done this run, %d left' % (reason, finished, left))
    return 3


def P_mcts(job):
    from integration.laya_regret import search as S
    return S.mcts(job)


# ----------------------------------------------------------------------------------------------- smoke


def smoke(args):
    """One game: replay + mapping on every decision, then search the first few at a small budget (no files)."""
    from integration.laya_regret import search as S
    directory = P.SOURCE_RUN / 'games' / args.game
    outcome = json.loads((directory / 'outcome.json').read_text())
    started = time.monotonic()
    decisions, samples, error = decision_rows(directory, outcome, schedule().get(args.game))
    counts = {}
    for row in decisions:
        counts[row['status']] = counts.get(row['status'], 0) + 1
    checks = [r['checks'].get('own_active') for r in decisions if 'own_active' in r.get('checks', {})]
    print(json.dumps(dict(game=args.game, result=outcome.get('result'), decisions=len(decisions), counts=counts,
                          samples=len(samples), error=error, own_active_ok=sum(1 for c in checks if c),
                          own_active_checked=len(checks), seconds=round(time.monotonic() - started, 1)), indent=1))
    by_decision = {}
    for s in samples:
        if s['round'] == 0:
            by_decision.setdefault(s['rqid'], []).append(s)
    shown = 0
    for row in decisions:
        if row['status'] != 'ready' or shown >= args.limit:
            continue
        shown += 1
        results = []
        for s in by_decision[row['rqid']]:
            job = dict(id=s['id'], state=s['state'], ms=s['ms'], iterations=args.iterations)
            results.append((s['chance'], S.mcts(job)))
        agg = S.aggregate(results)
        options = sorted(agg['share'])
        print(json.dumps(dict(rqid=row['rqid'], turn=row['turn'], lead=row['lead'], forced=row['forced'],
                              kind=row.get('kind'), laya=row['laya_choice'], laya_in_options=row['laya_choice'] in agg['share'],
                              laya_keys_missing=sorted(set(row['laya_probs']) - set(options)),
                              search_only=sorted(set(options) - set(row['laya_probs'])),
                              best=agg['best'], share_laya=round(agg['share'].get(row['laya_choice'], 0), 3),
                              q_best=round(agg['q'][agg['best']], 3), q_laya=round(agg['q'].get(row['laya_choice'], -1), 3),
                              samples=len(results), seconds=[r['seconds'] for _, r in results][:2])))
    errs = [r for r in decisions if r['status'] == 'error']
    for r in errs[:5]:
        print('ERROR', r['rqid'], r['error'], r.get('trace', '')[-300:])


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='stage', required=True)
    s = sub.add_parser('smoke')
    s.add_argument('--game', default='fp-b01-s1-a')
    s.add_argument('--limit', type=int, default=4)
    s.add_argument('--iterations', type=int, default=20_000)
    sub.add_parser('prepare')
    s = sub.add_parser('search')
    s.add_argument('--workers', type=int, default=P.WORKERS)
    s.add_argument('--until', default=None, help='UTC, e.g. 2026-11-19T07:30:00Z: submit nothing after this')
    s.add_argument('--wait', action='store_true', help='wait (60 s checks) until no foul-play battle process exists')
    sub.add_parser('report')
    args = parser.parse_args(argv)
    if args.stage == 'smoke':
        return smoke(args)
    if args.stage == 'prepare':
        return prepare(args)
    if args.stage == 'search':
        return search(args)
    from integration.laya_regret import report
    return report.main()


if __name__ == '__main__':
    sys.exit(main() or 0)
