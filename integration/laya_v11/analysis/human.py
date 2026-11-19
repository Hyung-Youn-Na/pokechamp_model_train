"""EX-169 A2 (human side) and A4: one pass over the human rows of the v10 datasets.

    python -m integration.laya_v11.analysis.human scan [--workers N]

Files: `v10-all/train.jsonl` (EX-071 tournament rows) and `v10-ladder/train.jsonl` (every ladder train-pool row; the
games in `v10-ladder-merged`'s list were trained on by v10rt, the older rest was not: `held`). Workers read byte
ranges and return, per (replay, side), the A2 measure counts of the human label, plus:
- every row whose label is a dead option (confirmed fail or x0), for the log join (`hindsight`);
- per-row candidates of the held-out rows for model scoring (`sample`);
- A4 tallies (Toxic Spikes at two layers, boosted-foe label classes, the bot team's species as my active).
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
from multiprocessing import Pool
import os
import time

from integration.laya_ladder import paths as ladder
from integration.laya_v10 import paths as p10

from .. import paths
from . import features as F

FILES = dict(tour=p10.V10_DATASET / 'train.jsonl', ladder=ladder.LADDER_ROWS / 'train.jsonl')
BOT_TEAM = ('dragapult', 'gliscor', 'ironcrown', 'kingambit', 'ogerponwellspring', 'tinglu')
_merged = None


def _init():
    global _merged
    _merged = set(json.loads((ladder.MERGED / 'manifest.json').read_text())['ladder_games'])


def _class(c):
    return 'switch' if c['switch'] else 'protect' if c['protect'] else 'status' if c['status'] else 'attack'


def _scan(job):
    source, path, start, end = job
    per = defaultdict(lambda: defaultdict(lambda: [0, 0]))     # (replay, side, held) -> measure -> [n, sum]
    dead, cand = [], []
    tally = Counter()
    with open(path, 'rb') as f:
        if start:
            f.seek(start - 1)
            f.readline()                      # finish the line the previous range owns
        while True:
            offset = f.tell()
            if offset >= end:
                break
            line = f.readline()
            if not line:
                break
            row = json.loads(line)
            sid = row['sample_id']
            replay, side = sid.split(':')[:2]
            held = source == 'ladder' and replay not in _merged
            state, criteria = row['state'], row['questions']['action']['criteria']
            label = row['expected']['action']
            facts = F.describe(state, criteria)
            ms = F.measures(facts, state, label)
            bucket = per[(replay, side, held)]
            for name, value in ms.items():
                bucket[name][0] += 1
                bucket[name][1] += value
            tally['rows:%s:%s' % (source, 'held' if held else 'trained')] += 1
            if facts['kind'] != 'turn_action':
                continue
            c = F.chosen(facts, label)
            if c['dead']:
                dead.append(dict(sample_id=sid, source=source, held=held, turn=facts['turn'], move=c['move'],
                                 mark='confirmed' if c['confirmed'] else 'zero', text=criteria[label],
                                 repeats_last=c['repeats_last'], last_fate=facts['last_fate'], me=facts['me'],
                                 opp=facts['opp'], has_live=facts['has_live'], offset=offset))
            if held:
                cand.append((sid, offset, sorted(ms)))
            # A4 tallies
            first = state.split('\n', 2)[1]
            if 'toxic_spikes2' in first.partition(' | opp side: ')[2]:
                option = criteria.get('move:toxicspikes:normal')
                if option is not None:
                    tally['tspikes2:option'] += 1
                    tally['tspikes2:marked_fails'] += bool(F.CONFIRMED.search(option))
                    tally['tspikes2:human_picked'] += label.startswith('move:toxicspikes:')
            if facts['opp_offence'] >= 2:
                tally['boosted:%s' % _class(c)] += 1
                tally['boosted:rows'] += 1
            tally['class:%s' % _class(c)] += 1
            if facts['me'] in BOT_TEAM:
                tally['active:%s' % facts['me']] += 1
            for name in ('fail', 'immune', 'protect', 'miss'):
                if facts['last_fate'] == name:
                    tally['last_fate:%s' % name] += 1
                    tally['last_fate:%s:repeat' % name] += c['repeats_last']
    return (source, {'%s|%s|%d' % k: {m: v for m, v in d.items()} for k, d in per.items()}, dead, cand, tally)


def _ranges(path, parts):
    size = os.path.getsize(path)
    step = size // parts + 1
    return [(start, min(size, start + step)) for start in range(0, size, step)]


def scan(workers=32):
    out = paths.TABLES
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'human-replays.jsonl').exists():
        raise FileExistsError(out / 'human-replays.jsonl')
    started = time.time()
    jobs = [(source, str(path), a, b) for source, path in FILES.items() for a, b in _ranges(path, workers * 2)]
    per, tally, n_dead, n_cand = {}, Counter(), 0, 0
    with Pool(workers, initializer=_init) as pool, open(out / 'human-dead-labels.jsonl', 'w') as fd, \
            open(out / 'human-held-candidates.jsonl', 'w') as fc:
        for source, part, dead, cand, t in pool.imap_unordered(_scan, jobs):
            for key, d in part.items():
                target = per.setdefault((source, key), {})
                for m, (n, s) in d.items():
                    cell = target.setdefault(m, [0, 0])
                    cell[0] += n
                    cell[1] += s
            for row in dead:
                fd.write(json.dumps(row, ensure_ascii=False) + '\n')
            for sid, offset, names in cand:
                fc.write(json.dumps([sid, offset, names]) + '\n')
            n_dead += len(dead)
            n_cand += len(cand)
            tally.update(t)
    with open(out / 'human-replays.jsonl', 'w') as f:
        for (source, key), d in sorted(per.items()):
            replay, side, held = key.split('|')
            f.write(json.dumps(dict(source=source, replay=replay, side=side, held=bool(int(held)), measures=d)) + '\n')
    summary = dict(tally=dict(sorted(tally.items())), replay_sides=len(per), dead_labels=n_dead, held_candidates=n_cand,
                   seconds=round(time.time() - started, 1), files={k: str(v) for k, v in FILES.items()})
    (out / 'human-scan.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('scan',))
    parser.add_argument('--workers', type=int, default=32)
    args = parser.parse_args()
    scan(args.workers)
