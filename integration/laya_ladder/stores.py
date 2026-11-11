"""EX-166: the v10 stores and rows for `laya-ladder-source/v1`, built by the unchanged EX-071 code at new paths.

Every store module reads its locations from `laya_imitation.config` (and `laya_v10.paths`) when it runs, so `apply()`
points those names at the ladder source and stores in this process; forked pools inherit it. The Metamon re-parse
workers (`item_state`, `early_history`) are separate interpreters started as `-m <module> worker`; `_Spawn` starts
them through this module instead, which applies the same names before calling the module's `_worker`. Nothing in
`laya_imitation`, `laya_engine`, `laya_threat` or `laya_v10` is edited.
"""
from __future__ import annotations
from collections import Counter
import json
import subprocess
import sys
import time

from integration.laya_imitation import config as c
from integration.laya_v10 import paths as p10

from . import paths

CONFIG = dict(EX071=paths.SOURCE, EX071_PREPARED=paths.SOURCE / 'prepared', EX071_PREPARATION=paths.SOURCE / 'preparation',
              ITEM_STATE=paths.ITEM_STATE, V5_FEATURES=paths.V5_FEATURES, EARLY_HISTORY=paths.EARLY_HISTORY,
              ENGINE_JUDGE=paths.ENGINE_JUDGE)
V10 = dict(V10_DATASET=paths.LADDER_ROWS, RUN_V10_TRAINING=paths.RUN_DATA)


def apply():
    for name, value in CONFIG.items():
        setattr(c, name, value)
    for name, value in V10.items():
        setattr(p10, name, value)


class _Spawn:
    """Stands in for `subprocess` inside a re-parse module: `-m <that module> worker a b` becomes
    `-m integration.laya_ladder.stores worker <short name> a b`."""

    def __init__(self, module):
        self.module = module

    def call(self, cmd, **kw):
        i = cmd.index('-m')
        if cmd[i + 1:i + 3] != [self.module.__name__, 'worker']:
            raise RuntimeError('unexpected re-parse command: %r' % cmd)
        cmd = cmd[:i + 1] + [__name__, 'worker', self.module.__name__.rsplit('.', 1)[1]] + cmd[i + 3:]
        return subprocess.call(cmd, **kw)

    def __getattr__(self, name):
        return getattr(subprocess, name)


def _reparse(module):
    module.subprocess = _Spawn(module)
    try:
        return module.reparse(workers=48)
    finally:
        module.subprocess = subprocess


def _early_history(workers=48):
    """`early_history.reparse` with the worker results kept on disk: the unchanged driver holds every row's events in
    memory (`found`, `rows_by_split`), which at 1.58M ladder rows exceeded the machine (killed 2026-11-04 10:15Z).
    Same shards, workers, parity rule, files, summary and manifest; rows are read back by offset in prepared order."""
    import os
    from concurrent.futures import ThreadPoolExecutor
    from integration.laya_imitation import early_history as eh, item_state
    from integration.laya_imitation.storage import seal, source_identity
    from integration.pokechamp.imitation.storage import atomic, sha
    output = c.EARLY_HISTORY
    if (output / 'manifest.json').exists():
        raise FileExistsError('early-history store already built: %s' % output)
    work = output / 'work'
    work.mkdir(parents=True, exist_ok=True)
    started = time.time()
    shards, order, replays = item_state._shards(work, workers)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join((str(c.ROOT), str(eh.METAMON / 'upstream'))))

    def run(shard):
        result, log = shard.with_suffix('.out'), shard.with_suffix('.log')
        with log.open('w') as err:
            code = subprocess.call([str(eh.METAMON / '.venv/bin/python'), '-m', __name__, 'worker', 'early_history',
                                    str(shard), str(result)], cwd=c.ROOT, env=env, stderr=err)
        if code:
            raise RuntimeError('re-parse worker failed: %s (see %s)' % (shard.name, log))
        return result

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(run, shards))
    split_of = {s: split for split in eh.SPLITS for s in order[split]}
    index, counts, mismatches, life_orb = {}, Counter(), [], 0
    for i, path in enumerate(results):
        with open(path, 'rb') as f:
            offset = 0
            for line in f:
                row = json.loads(line)
                sid = row['sample_id']
                index[sid] = (i, offset)
                offset += len(line)
                life_orb += bool(row.get('life_orb', False))
                if not row['equal']:
                    mismatches.append(dict(sample_id=sid, reason=row.get('reason'), diff=row.get('diff')))
                    continue
                split, events = split_of[sid], row['early_history']
                counts[split + ':rows'] += 1
                counts[split + ':rows_with_early_history'] += bool(events)
                counts[split + ':events_total'] += len(events)
                counts[split + ':events_max'] = max(counts[split + ':events_max'], len(events))
                counts[split + ':turns_max'] = max(counts[split + ':turns_max'], len({e['turn'] for e in events}))
    parity = dict(rows=len(index), replays=replays, equal=len(index) - len(mismatches), mismatches=len(mismatches),
                  life_orb_reveal_only=life_orb,
                  note='life_orb_reveal_only: same allowance as laya-item-state/v1 (rule added after the EX-071 freeze)',
                  examples=mismatches[:20])
    atomic(output / 'parity.json', parity)
    if mismatches:
        raise ValueError('existing snapshot fields changed for %d rows; see parity.json' % len(mismatches))
    handles = [open(p, 'rb') for p in results]
    try:
        for split in eh.SPLITS:
            with open(output / (split + '.jsonl'), 'w') as f:
                for sid in order[split]:
                    i, offset = index[sid]
                    handles[i].seek(offset)
                    r = json.loads(handles[i].readline())
                    f.write(json.dumps(dict(sample_id=r['sample_id'], early_history=r['early_history']),
                                       ensure_ascii=False, separators=(',', ':')) + '\n')
    finally:
        for h in handles:
            h.close()
    for split in eh.SPLITS:
        for key in ('rows', 'rows_with_early_history', 'events_total', 'events_max', 'turns_max'):
            counts.setdefault(split + ':' + key, 0)
    atomic(output / 'summary.json', dict(sorted(counts.items())))
    for path in work.iterdir():
        path.unlink()
    work.rmdir()
    manifest = dict(store='laya-early-history', version='v1', experiment='EX-142', decision='D-198',
                    counts={s: len(order[s]) for s in eh.SPLITS}, replays=replays,
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'),
                    parser=dict(replay=sha(c.ROOT / 'integration/pokechamp/imitation/replay.py'),
                                schema=sha(c.ROOT / 'integration/pokechamp/imitation/schema.py')),
                    source_code=source_identity(), files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in eh.SPLITS},
                    seconds=round(time.time() - started, 1), created_at=started, driver=__name__ + '._early_history')
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(eh.README)
    seal(output)
    print(json.dumps(dict(parity={k: parity[k] for k in ('rows', 'equal', 'mismatches')},
                          seconds=manifest['seconds']), ensure_ascii=False))
    return manifest


def build(workers=64):
    """item-state -> v5 facts -> early-history -> engine judge -> v10 measure -> v10 rows -> parity."""
    apply()
    from integration.laya_engine import store
    from integration.laya_imitation import data_v5, item_state
    from integration.laya_v10 import data_v10
    if not (paths.SOURCE / 'prepared/manifest.json').exists():
        raise RuntimeError('split the source first')
    log = lambda s: print('[%s] %s' % (time.strftime('%H:%M:%SZ', time.gmtime()), s), flush=True)
    if not (paths.ITEM_STATE / 'manifest.json').exists():
        log('item-state')
        _reparse(item_state)
    if not (paths.V5_FEATURES / 'manifest.json').exists():
        log('v5 facts')
        data_v5.build_features(output=paths.V5_FEATURES, workers=workers)
    if not (paths.EARLY_HISTORY / 'manifest.json').exists():
        log('early-history')
        _early_history()
    if not (paths.ENGINE_JUDGE / 'manifest.json').exists():
        log('engine judge')
        store.build(output=paths.ENGINE_JUDGE, workers=workers)
    if not list((paths.RUN_DATA / 'diagnostics/measure').glob('measure-*.json')):
        log('v10 measure')
        data_v10.measure(workers=workers)
    if not (paths.LADDER_ROWS / 'manifest.json').exists():
        log('v10 rows')
        data_v10.build(workers=workers)
    if not (paths.RUN_DATA / 'diagnostics/parity.json').exists():
        log('v10 parity')
        data_v10.parity()


def budget_rows(spr, hours=paths.TARGET_HOURS, overhead_hours=1.0, epochs=3):
    """Training rows that fit `hours` at `spr` seconds per row (EX-167 measure), less loading/validation overhead."""
    return int((hours - overhead_hours) * 3600 / (epochs * spr))


def _chars(path, limit=4096):
    n = total = 0
    with open(path) as f:
        for line in f:
            total += len(json.loads(line)['state'])
            n += 1
            if n == limit:
                break
    return total / max(1, n)


def merge(measure_file):
    """`v10-ladder-merged`: train = EX-161's v10 train + the newest ladder train games that fit the 24-hour budget,
    validation = both validations (1,024 rows). Tests stay in their own datasets (EX-071's in `v10-all`, the ladder's
    in `v10-ladder`). The budget scales the measured seconds per row by the ladder / v10-all state length ratio."""
    from integration.laya_imitation.storage import atomic, read, seal, sha, verify_seal
    out = paths.MERGED
    if (out / 'manifest.json').exists():
        return read(out / 'manifest.json')
    for d in (paths.V10_DATASET, paths.LADDER_ROWS):
        if verify_seal(d):
            raise RuntimeError('seal failed: %s' % d)
    old, new = read(paths.V10_DATASET / 'manifest.json'), read(paths.LADDER_ROWS / 'manifest.json')
    for key in ('render', 'token_limit', 'head_limit', 'option_limit'):
        if old[key] != new[key]:
            raise RuntimeError('v10-all and v10-ladder differ in %s' % key)
    measured = read(measure_file)['results']['no_checkpointing']
    ratio = _chars(paths.LADDER_ROWS / 'train.jsonl') / _chars(paths.V10_DATASET / 'train.jsonl')
    spr = measured['seconds_per_row'] * ratio
    extra = sum(1 for _ in open(c.TERA_KNOWLEDGE / 'train.jsonl'))
    own = sum(1 for _ in open(paths.V10_DATASET / 'train.jsonl')) - 400   # EX-161's calibration slice
    ladder_budget = budget_rows(spr) - own - extra
    kept = {g['replay_id']: g for g in map(json.loads, open(paths.RUN_DATA / 'select/kept.jsonl'))}
    game = lambda line: json.loads(line)['sample_id'].split(':')[0]
    by_game = Counter()
    with open(paths.LADDER_ROWS / 'train.jsonl') as f:   # counts only: the whole ladder train does not fit in memory
        for line in f:
            by_game[game(line)] += 1
    chosen, rows = [], 0
    for rid in sorted(by_game, key=lambda r: (-kept[r]['uploadtime'], r)):
        if rows >= ladder_budget:
            break
        chosen.append(rid)
        rows += by_game[rid]
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    with open(out / 'train.jsonl', 'w') as f:
        with open(paths.V10_DATASET / 'train.jsonl') as g:
            for line in g:
                f.write(line)
        counts['train:v10-all'] = own + 400
        keep = set(chosen)
        with open(paths.LADDER_ROWS / 'train.jsonl') as g:
            f.writelines(line for line in g if game(line) in keep)
        counts['train:v10-ladder'] = rows
    with open(out / 'validation.jsonl', 'w') as f:
        for source in (paths.V10_DATASET, paths.LADDER_ROWS):
            lines = open(source / 'validation.jsonl').readlines()
            f.writelines(lines)
            counts['validation:' + source.name] = len(lines)
    source_validation = [read(d / 'validation.json') for d in (paths.V10_DATASET, paths.LADDER_ROWS)]
    atomic(out / 'validation.json', dict(token_budget_exclusions=sum(v['token_budget_exclusions'] for v in source_validation),
                                         exclusion_rate=max(v['exclusion_rate'] for v in source_validation),
                                         sources=source_validation), immutable=True)
    oldest = min(kept[r]['uploadtime'] for r in chosen)
    budget = dict(measure=str(measure_file), seconds_per_row_measured=measured['seconds_per_row'], length_ratio=ratio,
                  seconds_per_row=spr, target_hours=paths.TARGET_HOURS, overhead_hours=1.0,
                  total_train_rows=budget_rows(spr), own_train=own, extra_train=extra, ladder_budget=ladder_budget,
                  ladder_rows=rows, ladder_games=len(chosen), ladder_pool_games=len(by_game),
                  ladder_oldest_upload=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(oldest)),
                  expected_hours=(own + extra + rows) * 3 * spr / 3600 + 1.0)
    manifest = dict(dataset='laya-compact-imitation', version='v10-ladder-merged', experiment='EX-167', decision='D-208',
                    created_at=time.time(), counts=counts, budget=budget,
                    sources={d.name: dict(path=str(d), manifest_sha256=sha(d / 'manifest.json'))
                             for d in (paths.V10_DATASET, paths.LADDER_ROWS)},
                    render=new['render'], token_limit=new['token_limit'], head_limit=new['head_limit'],
                    option_limit=new['option_limit'], ladder_games=sorted(chosen),
                    files={s + '.jsonl': sha(out / (s + '.jsonl')) for s in ('train', 'validation')})
    atomic(out / 'manifest.json', manifest, immutable=True)
    seal(out)
    print(json.dumps(dict(counts=counts, budget=budget)))
    return manifest


if __name__ == '__main__' and sys.argv[1:2] == ['worker']:
    apply()
    import importlib
    module = importlib.import_module('integration.laya_imitation.' + sys.argv[2])
    module._worker(sys.argv[3], sys.argv[4])
