"""EX-177 (D-213): the fp1 datasets — the rows of `v11-ladder-merged` and the two locked tests, re-rendered by fp1.

    render  [--workers N] [--limit G]   foul-play venv: every replay the reference rows come from, both sides, each
                                        decision through `tracker.Tracker`; the wanted ones rendered by `render_fp1`
                                        into `RUN/staging/part-*.jsonl` (unordered; finished replays are skipped on
                                        a re-run)
    order                               any python: the reference files, line by line, with the fp1 text in place of
                                        the v11 text (same sample id, input hash, label, option ids and order, meta);
                                        a reference row without an fp1 row is excluded and listed
    probe   N                           qualification 1 over N reference rows (tracker vs laya snapshot)

Reference rows (EX-170): train / validation = `v11-ladder-merged`; tests = `v11-all` test (EX-071) and
`v11-ladder` test (EX-166). Sources: EX-071 recovered replays (tour) and EX-166 recovered replays (ladder).
Token limits are checked afterwards in the laya env (`tokens_fp1`).
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
GENERATED = SHARED / 'datasets/generated'
RUN = SHARED / 'runs/model-training/EX-177'
OUTPUT = GENERATED / 'laya-compact-imitation/fp1-ladder-merged'
TESTS = GENERATED / 'laya-compact-imitation/fp1-test'
REFERENCE = dict(
    train=GENERATED / 'laya-compact-imitation/v11-ladder-merged/train.jsonl',
    validation=GENERATED / 'laya-compact-imitation/v11-ladder-merged/validation.jsonl',
    test_tour=GENERATED / 'laya-compact-imitation/v11-all/test.jsonl',
    test_ladder=GENERATED / 'laya-compact-imitation/v11-ladder/test.jsonl')
SOURCES = dict(
    tour=dict(replays=ROOT / '.pokechamp-data/experiments/ex071-qwen-replay-imitation/preparation/replays.jsonl',
              recovered=ROOT / '.pokechamp-data/experiments/ex071-qwen-replay-imitation/preparation/recovered'),
    ladder=dict(replays=GENERATED / 'laya-ladder-source/v1/preparation/replays.jsonl',
                recovered=GENERATED / 'laya-ladder-source/v1/preparation/recovered'))


def load(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw)


def sample_id_of(line):
    if not line.startswith('{"sample_id":"'):
        raise ValueError('unexpected row layout')
    return line[14:line.index('"', 14)]


def wanted():
    """sample id -> reference file key, over all reference files (sample ids are unique across them)."""
    out = {}
    for key, path in REFERENCE.items():
        with open(path) as f:
            for line in f:
                sid = sample_id_of(line)
                if sid in out:
                    raise ValueError('sample id in two reference files: %s' % sid)
                out[sid] = key
    return out


def jobs(want, limit=None):
    games = {}
    for sid in want:
        games.setdefault(sid.split(':', 1)[0], set()).add(sid)
    out = []
    for source, where in SOURCES.items():
        with open(where['replays']) as f:
            for line in f:
                r = json.loads(line)
                rid = r['replay_id']
                if rid in games:
                    out.append(dict(source=source, replay_id=rid, raw=r['raw_path'],
                                    recovered=str(where['recovered'] / (rid + '.json.gz')),
                                    wanted=sorted(games.pop(rid))))
    if games:
        raise RuntimeError('%d reference games have no source replay (e.g. %s)' % (len(games), next(iter(games))))
    out.sort(key=lambda j: j['replay_id'])
    return out[:limit] if limit else out


# ------------------------------------------------------------------------------------------------ render (fp venv)

def render_job(job):
    from integration.laya_fp1 import render_fp1 as R
    from integration.laya_fp1 import tracker as T
    started = time.time()
    rows, diag = [], Counter()
    errors = []
    want = set(job['wanted'])
    recovered = load(job['recovered'])
    raw = load(job['raw'])
    result = recovered['result']
    for side in sorted(result['original_sets']):
        own = result['original_sets'][side]
        try:
            tracker = T.Tracker(raw, side, own)
        except Exception as exc:
            errors.append(dict(side=side, stage='init', error='%s: %s' % (type(exc).__name__, exc)))
            continue
        for record in T.recovered_records(recovered, side):
            sid = '%s:%s:%d:%s' % (job['replay_id'], side, record['cutoff_line'], record['decision_kind'])
            try:
                if record['decision_kind'] == 'lead':
                    view = tracker.lead_view() if sid in want else None
                else:
                    tracker.advance(record['cutoff_line'], record['snapshot'], record['decision_kind'])
                    view = tracker.view() if sid in want else None
                if view is not None:
                    state, criteria, d = R.render(view, sid, record['actions'], record['decision_kind'], own)
                    rows.append(dict(sample_id=sid, state=state, criteria=criteria,
                                     engine_errors=d['engine_errors'], defaults=dict(d['defaults'])))
                    diag['engine_errors'] += d['engine_errors']
                tracker.chose(record.get('label'))
            except Exception as exc:
                errors.append(dict(side=side, sample_id=sid, stage='decision',
                                   error='%s: %s' % (type(exc).__name__, exc), wanted=sid in want,
                                   trace=traceback.format_exc(limit=3)[-600:]))
                break           # the tracker state is no longer trustworthy for this side
    return dict(replay_id=job['replay_id'], rows=rows, errors=errors, seconds=time.time() - started,
                engine_errors=diag['engine_errors'])


def _init():
    from integration.laya_fp1 import tracker
    tracker.setup()


def render(workers=48, limit=None, redo_errors=False, games=None):
    from multiprocessing import Pool
    if os.environ.get('PYTHONHASHSEED') != '0':
        raise RuntimeError('run with PYTHONHASHSEED=0 (deterministic foul-play set iteration)')
    staging = RUN / 'staging'
    staging.mkdir(parents=True, exist_ok=True)
    done = set()
    for part in staging.glob('done-*.txt'):
        done.update(part.read_text().split())
    want = wanted()
    if redo_errors:     # games with a staged error, rendered again into a new part (order keeps the last row)
        games = set(games or ())
        for part in staging.glob('errors-*.jsonl'):
            games.update(json.loads(line)['replay_id'] for line in open(part))
    if games is not None:
        todo = [j for j in jobs(want, limit) if j['replay_id'] in games]
    else:
        todo = [j for j in jobs(want, limit) if j['replay_id'] not in done]
    print('[fp1] %d reference rows, %d games to render (%d done)' % (len(want), len(todo), len(done)), flush=True)
    tag = '%d-%d' % (int(time.time()), os.getpid())
    started, n, nrows, nerr = time.time(), 0, 0, 0
    with open(staging / ('part-%s.jsonl' % tag), 'a') as out, \
            open(staging / ('errors-%s.jsonl' % tag), 'a') as err, \
            open(staging / ('done-%s.txt' % tag), 'a') as fin, \
            Pool(workers, initializer=_init, maxtasksperchild=200) as pool:
        for result in pool.imap_unordered(render_job, todo, chunksize=1):
            for row in result['rows']:
                out.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
            for e in result['errors']:
                err.write(json.dumps(dict(e, replay_id=result['replay_id'])) + '\n')
            out.flush()
            err.flush()
            fin.write(result['replay_id'] + '\n')
            fin.flush()
            n += 1
            nrows += len(result['rows'])
            nerr += len(result['errors'])
            if n % 200 == 0 or n == len(todo):
                rate = n / max(1e-9, time.time() - started)
                print('[fp1] %d/%d games, %d rows, %d errors, %.2f games/s, eta %.0f min' % (
                    n, len(todo), nrows, nerr, rate, (len(todo) - n) / max(1e-9, rate) / 60), flush=True)
    return dict(games=n, rows=nrows, errors=nerr)


# ------------------------------------------------------------------------------------------------ order (any python)

def order():
    staging = RUN / 'staging'
    index = {}
    for part in sorted(staging.glob('part-*.jsonl')):
        with open(part, 'rb') as f:
            offset = 0
            for line in f:
                sid = sample_id_of(line.decode())
                index[sid] = (part, offset, len(line))
                offset += len(line)
    print('[fp1] %d staged rows' % len(index), flush=True)
    handles = {}

    def fetch(sid):
        part, offset, size = index[sid]
        h = handles.get(part) or handles.setdefault(part, open(part, 'rb'))
        h.seek(offset)
        return json.loads(h.read(size))

    targets = dict(train=OUTPUT / 'train.jsonl', validation=OUTPUT / 'validation.jsonl',
                   test_tour=TESTS / 'tour/test.jsonl', test_ladder=TESTS / 'ladder/test.jsonl')
    for path in targets.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    counts, exclusions = {}, []
    for key, path in REFERENCE.items():
        kept = 0
        with open(path) as ref, open(targets[key], 'w') as out:
            for line in ref:
                old = json.loads(line)
                sid = old['sample_id']
                if sid not in index:
                    exclusions.append(dict(split=key, sample_id=sid, reason='no_fp1_row'))
                    continue
                new = fetch(sid)
                old_q = old['questions']['action']
                if list(new['criteria']) != list(old_q['criteria']):
                    exclusions.append(dict(split=key, sample_id=sid, reason='option_ids_differ'))
                    continue
                row = dict(sample_id=sid, input_sha256=old['input_sha256'], state=new['state'],
                           questions={'action': dict(type=old_q['type'], instructions=old_q['instructions'],
                                                     criteria=new['criteria'])},
                           expected=old['expected'], meta=old['meta'])
                out.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
                kept += 1
        counts[key] = kept
        print('[fp1] %s: %d rows' % (key, kept), flush=True)
    with open(RUN / 'exclusions.jsonl', 'w') as f:
        for e in exclusions:
            f.write(json.dumps(e) + '\n')
    summary = dict(counts=counts, exclusions=Counter((e['split'], e['reason']) for e in exclusions).most_common())
    reference = {k: sum(1 for _ in open(p)) for k, p in REFERENCE.items()}
    manifest = manifest_of(counts, reference, targets)
    for directory in (OUTPUT, TESTS / 'tour', TESTS / 'ladder'):
        (directory / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
    (RUN / 'order.json').write_text(json.dumps(dict(
        counts=counts, reference=reference,
        exclusion_rate={k: 1 - counts[k] / max(1, reference[k]) for k in counts},
        exclusions=[list(map(str, k)) + [v] for k, v in summary['exclusions']]), indent=1))
    return summary


def manifest_of(counts, reference, targets):
    import hashlib

    def sha(path):
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(1 << 20), b''):
                h.update(block)
        return h.hexdigest()
    here = Path(__file__).parent
    from integration.laya_fp1 import render_fp1
    return dict(dataset='laya-compact-imitation', version='fp1', experiment='EX-177', decision='D-213',
                created_at=time.time(), render=render_fp1.VERSION, counts=counts, reference_counts=reference,
                reference={k: str(p) for k, p in REFERENCE.items()},
                code={p.name: sha(p) for p in sorted(here.glob('*.py'))},
                foulplay=dict(commit='8f541f8', data_sums=sha(ROOT / '.tools/foul-play/data-SHA256SUMS'),
                              poke_engine='0.0.48'),
                token_limit=2048, head_limit=768, option_limit=64,
                files={k: dict(path=str(p), sha256=sha(p)) for k, p in targets.items()})


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('render')
    r.add_argument('--workers', type=int, default=48)
    r.add_argument('--limit', type=int)
    r.add_argument('--redo-errors', action='store_true')
    r.add_argument('--games', help='comma-separated replay ids to render again (into a new part)')
    r.add_argument('--staging', help='staging directory override (for re-render checks)')
    sub.add_parser('order')
    args = parser.parse_args(argv)
    if args.cmd == 'render':
        global RUN
        if args.staging:
            RUN = Path(args.staging)
        print(json.dumps(render(args.workers, args.limit, args.redo_errors,
                                set(args.games.split(',')) if args.games else None)))
    else:
        print(json.dumps(order(), default=str))


if __name__ == '__main__':
    main()
