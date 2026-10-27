"""EX-136 (D-195): re-parse EX-071 replays with the D-195 parser and keep only the new optional fields.

Each replay is replayed through `replay.Timeline` with the original sets frozen in the EX-071 recovery cache
(no re-imputation). Every prepared row must come back with the *same* existing snapshot fields; the new
optional fields (`weather_turn`, per-mon `status_counter`/`status_source`, opponent `item_state`) are written
to `laya-item-state/v1/<split>.jsonl` in prepared order, keyed by `sample_id`. `merge` puts them back into a
prepared input body. Workers run in the pinned Metamon env (`.tools/metamon-imitation`), like the bridge.
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
from .storage import seal, source_identity

SPLITS = ('train', 'validation', 'test')
METAMON = c.ROOT / '.tools/metamon-imitation'
README = """# laya-item-state v1 (EX-136, D-195)

EX-071 prepared rows re-parsed with the D-195 parser (`replay.py` optional public state). One row per prepared
row, same order: `sample_id`, `weather_turn`, `own_team` / `opponent_team` lists of the new per-mon fields.
`parity.json` proves every existing snapshot field is unchanged; `summary.json` counts the new states.
"""


def optional_fields(snapshot):
    from integration.pokechamp.imitation.schema import OPTIONAL_MON_KEYS, OPTIONAL_SNAPSHOT_KEYS
    if not set(OPTIONAL_SNAPSHOT_KEYS) <= set(snapshot):
        raise ValueError('snapshot was not produced by the D-195 parser')
    return dict(weather_turn=snapshot['weather_turn'],
                **{side: [{k: m[k] for k in OPTIONAL_MON_KEYS if k in m} for m in snapshot[side]]
                   for side in ('own_team', 'opponent_team')})


def strip(snapshot):
    from integration.pokechamp.imitation.schema import OPTIONAL_MON_KEYS, OPTIONAL_SNAPSHOT_KEYS
    result = {k: v for k, v in snapshot.items() if k not in OPTIONAL_SNAPSHOT_KEYS}
    for side in ('own_team', 'opponent_team'):
        result[side] = [{k: v for k, v in m.items() if k not in OPTIONAL_MON_KEYS} for m in snapshot[side]]
    return result


def merge(body, fields):
    """Prepared input body + this store's row -> body whose snapshot carries the optional fields."""
    state = json.loads(body['state'])
    snapshot = state['snapshot']
    snapshot['weather_turn'] = fields['weather_turn']
    for side in ('own_team', 'opponent_team'):
        for mon, extra in zip(snapshot[side], fields[side], strict=True):
            mon.update(extra)
    return dict(body, state=canonical(dict(version=state['version'], snapshot=snapshot)))


# ----------------------------------------------------------------------------- worker (Metamon env)

def _only_life_orb(old, new):
    """The one allowed difference: EX-071 was frozen before `replay.py` learned the Life Orb recoil reveal."""
    for a, b in zip(old, new, strict=True):
        for key in a:
            if a[key] != b.get(key) and not (key == 'item' and a[key] is None and b.get(key) == 'lifeorb'):
                return False
    return True


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
                                replay_id=replay_id).consume(capture=True)
            records = {f"{replay_id}:{r['perspective']}:{r['cutoff_line']}:{r['decision_kind']}": r
                       for r in timeline.records}
            for sample_id, old in job['rows']:
                record = records.get(sample_id)
                if record is None:
                    out.write(json.dumps(dict(sample_id=sample_id, equal=False, reason='missing')) + '\n')
                    continue
                new = json.loads(json.dumps(_snapshot(record['snapshot'])))
                kept = strip(new)
                diff = sorted(k for k in old if kept.get(k) != old[k])
                life_orb = bool(diff) and diff == ['opponent_team'] and _only_life_orb(old['opponent_team'], kept['opponent_team'])
                out.write(json.dumps(dict(sample_id=sample_id, equal=not diff or life_orb, life_orb=life_orb,
                                          fields=optional_fields(new), diff=None if not diff or life_orb else diff),
                                     separators=(',', ':')) + '\n')


# ----------------------------------------------------------------------------- driver (laya env)

def _shards(work, workers):
    """Group prepared rows by replay (old snapshot kept for the comparison) into `workers` shard files."""
    jobs = {}
    order = {split: [] for split in SPLITS}
    for split in SPLITS:
        with open(c.EX071_PREPARED / (split + '.jsonl')) as f:
            for line in f:
                row = json.loads(line)
                order[split].append(row['sample_id'])
                snapshot = json.loads(row['input']['state'])['snapshot']
                jobs.setdefault(row['replay_id'], []).append((row['sample_id'], snapshot))
    paths = [work / ('shard-%02d.jsonl' % i) for i in range(workers)]
    handles = [p.open('w') for p in paths]
    for i, (replay_id, rows) in enumerate(sorted(jobs.items())):
        handles[i % workers].write(json.dumps(dict(replay_id=replay_id, rows=rows), separators=(',', ':')) + '\n')
    for h in handles:
        h.close()
    return paths, order, len(jobs)


def _summary(rows_by_split):
    counts = Counter()
    for split, rows in rows_by_split.items():
        for row in rows:
            f = row['fields']
            counts[split + ':rows'] += 1
            if f['weather_turn'] is not None:
                counts[split + ':weather_turn'] += 1
            for side in ('own_team', 'opponent_team'):
                for m in f[side]:
                    if m.get('status_counter') is not None:
                        counts['%s:%s:status_counter' % (split, side)] += 1
                    if m.get('status_source') == 'rest':
                        counts['%s:%s:rest' % (split, side)] += 1
                    state = m.get('item_state')
                    if state:
                        key = state['state'] + (':' + state['cause'] if state['cause'] else '')
                        counts['%s:opponent_mon_item:%s' % (split, key)] += 1
    return dict(sorted(counts.items()))


def _active_summary(output):
    """Per-row counts on the *active* mons (the rows the renderer changes most)."""
    counts = Counter()
    for split in SPLITS:
        with open(c.EX071_PREPARED / (split + '.jsonl')) as f, open(output / (split + '.jsonl')) as g:
            for line, extra in zip(f, g, strict=True):
                snapshot = json.loads(json.loads(line)['input']['state'])['snapshot']
                fields = json.loads(extra)
                counts[split + ':rows'] += 1
                for side, slot in (('own_team', snapshot['own_active_slot']),
                                   ('opponent_team', snapshot['opponent_active_slot'])):
                    if not slot:
                        continue
                    mon, add = snapshot[side][slot - 1], fields[side][slot - 1]
                    if add.get('status_counter') is not None:
                        counts['%s:%s_active:%s' % (split, side, mon['status'])] += 1
                    state = add.get('item_state')
                    if state and state['state'] != 'unknown':
                        counts['%s:opponent_active_item:%s' % (split, state['state'] + (
                            ':' + state['cause'] if state['cause'] else ''))] += 1
                        if state['state'] == 'held' and mon['item'] is None:
                            counts[split + ':opponent_active_item:held_hidden_by_legacy_field'] += 1
    return dict(sorted(counts.items()))


def reparse(output=None, workers=24):
    output = Path(output or c.ITEM_STATE)
    if (output / 'manifest.json').exists():
        raise FileExistsError('item-state store already built: %s' % output)
    work = output / 'work'
    work.mkdir(parents=True, exist_ok=True)
    started = time.time()
    shards, order, replays = _shards(work, workers)
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
                  note='life_orb_reveal_only: opponent item None -> lifeorb, from the Life Orb recoil rule added to '
                       'replay.py after the EX-071 freeze (not D-195); counted as equal',
                  examples=[dict(sample_id=r['sample_id'], reason=r.get('reason'), diff=r.get('diff'))
                            for r in mismatches[:20]])
    atomic(output / 'parity.json', parity)
    if mismatches:
        raise ValueError('existing snapshot fields changed for %d rows; see parity.json' % len(mismatches))
    for split in SPLITS:
        with open(output / (split + '.jsonl'), 'w') as f:
            for r in rows_by_split[split]:
                f.write(json.dumps(dict(sample_id=r['sample_id'], **r['fields']), ensure_ascii=False,
                                   separators=(',', ':')) + '\n')
    summary = dict(mon_level=_summary(rows_by_split), active_level=_active_summary(output))
    atomic(output / 'summary.json', summary)
    for path in work.iterdir():
        path.unlink()
    work.rmdir()
    manifest = dict(store='laya-item-state', version='v1', experiment='EX-136', decision='D-195',
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
    with open(Path(store or c.ITEM_STATE) / (split + '.jsonl')) as f:
        for line in f:
            yield json.loads(line)


if __name__ == '__main__' and sys.argv[1:2] == ['worker']:
    _worker(sys.argv[2], sys.argv[3])
