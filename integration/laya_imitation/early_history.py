"""EX-142 (D-198): re-parse EX-071 replays and keep the opt-in `early_history` (events older than the four-turn window).

Same procedure as `item_state` (EX-136): each replay goes through `replay.Timeline` with the original sets frozen in the
EX-071 recovery cache, now with `early_history=True`. Every prepared row must come back with the same existing snapshot
fields (the D-195 optional fields and `early_history` aside, Life Orb reveal allowed as in `item_state`); the new field
is written to `laya-early-history/v1/<split>.jsonl` in prepared order, keyed by `sample_id`. `merge` adds it to an
input body that already carries the D-195 fields. Workers run in the pinned Metamon env, like the bridge.
"""
from __future__ import annotations
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from integration.pokechamp.imitation.storage import atomic, canonical, sha

from . import config as c
from . import item_state
from .storage import seal, source_identity

SPLITS = item_state.SPLITS
METAMON = item_state.METAMON
README = """# laya-early-history v1 (EX-142, D-198)

EX-071 prepared rows re-parsed with `replay.Timeline(..., early_history=True)`. One row per prepared row, same order:
`sample_id`, `early_history` (public history events of turns before T-4, normalized like `history`).
`parity.json` proves every existing snapshot field is unchanged; `summary.json` counts events and turns.
"""


def merge(body, row):
    """Input body (already merged with `item_state`) + this store's row -> body whose snapshot has `early_history`."""
    state = json.loads(body['state'])
    state['snapshot']['early_history'] = row['early_history']
    return dict(body, state=canonical(dict(version=state['version'], snapshot=state['snapshot'])))


# ----------------------------------------------------------------------------- worker (Metamon env)

def _worker(shard, output):
    from integration.pokechamp.imitation.dataset import read_replay
    from integration.pokechamp.imitation.replay import Timeline
    from integration.pokechamp.imitation.schema import _snapshot
    raw_paths = {}
    for line in open(c.EX071_PREPARATION / 'replays.jsonl'):
        r = json.loads(line)
        raw_paths[r['replay_id']] = r['raw_path']
    with open(shard) as f, open(output, 'w') as out:
        for line in f:
            job = json.loads(line)
            replay_id = job['replay_id']
            cached = read_replay(c.EX071_PREPARATION / 'recovered' / (replay_id + '.json.gz'))
            timeline = Timeline(read_replay(raw_paths[replay_id]), cached['result']['original_sets'],
                                replay_id=replay_id, early_history=True).consume(capture=True)
            records = {f"{replay_id}:{r['perspective']}:{r['cutoff_line']}:{r['decision_kind']}": r
                       for r in timeline.records}
            for sample_id, old in job['rows']:
                record = records.get(sample_id)
                if record is None:
                    out.write(json.dumps(dict(sample_id=sample_id, equal=False, reason='missing')) + '\n')
                    continue
                new = json.loads(json.dumps(_snapshot(record['snapshot'])))
                early = new.pop('early_history')
                kept = item_state.strip(new)
                diff = sorted(k for k in old if kept.get(k) != old[k])
                life_orb = bool(diff) and diff == ['opponent_team'] and \
                    item_state._only_life_orb(old['opponent_team'], kept['opponent_team'])
                out.write(json.dumps(dict(sample_id=sample_id, equal=not diff or life_orb, life_orb=life_orb,
                                          early_history=early, diff=None if not diff or life_orb else diff),
                                     separators=(',', ':')) + '\n')


# ----------------------------------------------------------------------------- driver (laya env)

def _summary(rows_by_split):
    counts = Counter()
    for split, rows in rows_by_split.items():
        events = [len(r['early_history']) for r in rows]
        turns = [len({e['turn'] for e in r['early_history']}) for r in rows]
        counts[split + ':rows'] = len(rows)
        counts[split + ':rows_with_early_history'] = sum(1 for n in events if n)
        counts[split + ':events_total'] = sum(events)
        counts[split + ':events_max'] = max(events) if events else 0
        counts[split + ':turns_max'] = max(turns) if turns else 0
    return dict(sorted(counts.items()))


def reparse(output=None, workers=24):
    output = Path(output or c.EARLY_HISTORY)
    if (output / 'manifest.json').exists():
        raise FileExistsError('early-history store already built: %s' % output)
    work = output / 'work'
    work.mkdir(parents=True, exist_ok=True)
    started = time.time()
    shards, order, replays = item_state._shards(work, workers)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join((str(c.ROOT), str(METAMON / 'upstream'))))

    def run(shard):
        result = shard.with_suffix('.out')
        log = shard.with_suffix('.log')
        with log.open('w') as err:
            code = subprocess.call([str(METAMON / '.venv/bin/python'), '-m', __name__, 'worker', str(shard), str(result)],
                                   cwd=c.ROOT, env=env, stderr=err)
        if code:
            raise RuntimeError('re-parse worker failed: %s (see %s)' % (shard.name, log))
        return result

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(run, shards))
    found = {}
    for path in results:
        for line in open(path):
            row = json.loads(line)
            found[row['sample_id']] = row
    mismatches = [r for r in found.values() if not r['equal']]
    rows_by_split = {split: [found[s] for s in order[split]] for split in SPLITS}
    parity = dict(rows=len(found), replays=replays, equal=len(found) - len(mismatches), mismatches=len(mismatches),
                  life_orb_reveal_only=sum(r.get('life_orb', False) for r in found.values()),
                  note='life_orb_reveal_only: same allowance as laya-item-state/v1 (rule added after the EX-071 freeze)',
                  examples=[dict(sample_id=r['sample_id'], reason=r.get('reason'), diff=r.get('diff'))
                            for r in mismatches[:20]])
    atomic(output / 'parity.json', parity)
    if mismatches:
        raise ValueError('existing snapshot fields changed for %d rows; see parity.json' % len(mismatches))
    for split in SPLITS:
        with open(output / (split + '.jsonl'), 'w') as f:
            for r in rows_by_split[split]:
                f.write(json.dumps(dict(sample_id=r['sample_id'], early_history=r['early_history']),
                                   ensure_ascii=False, separators=(',', ':')) + '\n')
    atomic(output / 'summary.json', _summary(rows_by_split))
    for path in work.iterdir():
        path.unlink()
    work.rmdir()
    manifest = dict(store='laya-early-history', version='v1', experiment='EX-142', decision='D-198',
                    counts={s: len(order[s]) for s in SPLITS}, replays=replays,
                    source_manifest_sha256=sha(c.EX071_PREPARED / 'manifest.json'),
                    parser=dict(replay=sha(c.ROOT / 'integration/pokechamp/imitation/replay.py'),
                                schema=sha(c.ROOT / 'integration/pokechamp/imitation/schema.py')),
                    source_code=source_identity(), files={s + '.jsonl': sha(output / (s + '.jsonl')) for s in SPLITS},
                    seconds=round(time.time() - started, 1), created_at=started)
    atomic(output / 'manifest.json', manifest, immutable=True)
    (output / 'README.md').write_text(README)
    seal(output)
    print(json.dumps(dict(parity={k: parity[k] for k in ('rows', 'equal', 'mismatches')},
                          seconds=manifest['seconds']), ensure_ascii=False))
    return manifest


def load(split, store=None):
    with open(Path(store or c.EARLY_HISTORY) / (split + '.jsonl')) as f:
        for line in f:
            yield json.loads(line)


if __name__ == '__main__' and sys.argv[1:2] == ['worker']:
    _worker(sys.argv[2], sys.argv[3])
