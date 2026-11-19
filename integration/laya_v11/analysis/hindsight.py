"""EX-169 A4: what the log shows for human labels on dead options, and rating strata of the A2 measures.

    python -m integration.laya_v11.analysis.hindsight join      # tables/human-dead-hindsight.jsonl
    python -m integration.laya_v11.analysis.hindsight strata    # problem measures by rating band (ladder rows)

`join`: for every training row whose human label is a dead option (engine-confirmed fail or x0), the raw replay
gives the fate of that move: it failed / was immune / absorbed (`failed`), it worked because the foe switched or the
state changed first (`worked`), or the player never moved. D-209's label cleaning drops `failed` rows whose target
did not switch. Uses only the row's own turn, so it filters labels and never enters an input.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import gzip
import json
from multiprocessing import Pool
import sys

from integration.laya_imitation import config as c
from integration.laya_ladder import paths as ladder

from .. import paths
from . import compare
from .games import PROTECT, tid

REPLAYS = (c.EX071 / 'preparation/replays.jsonl', ladder.SOURCE / 'preparation/replays.jsonl')
BANDS = ((0, 1600, '1500-1599'), (1600, 1700, '1600-1699'), (1700, 10 ** 6, '1700+'))
PROBLEMS = ('dead_pick', 'stalled_streak_repeat', 'repeat_after_fail', 'duel_lose_switch', 'boosted_foe_switch',
            'all_dead_switch', 'switch')


def raw_paths():
    out = {}
    for path in REPLAYS:
        for line in open(path):
            row = json.loads(line)
            out[row['replay_id']] = row['raw_path']
    return out


def load(path):
    data = open(path, 'rb').read()
    return json.loads(gzip.decompress(data) if data[:2] == b'\x1f\x8b' else data)


def fate(log, side, turn, move):
    """(result, target_switched) of `side`'s move in `turn`: result in failed/protect/miss/worked/none."""
    me, op = side + 'a: ', ('p1' if side == 'p2' else 'p2') + 'a: '
    lines, current = [], 0
    for line in log.split('\n'):
        if line.startswith('|turn|'):
            current = int(line.split('|')[2])
        elif current == turn:
            lines.append(line)
        elif current > turn:
            break
    switched = False
    for i, line in enumerate(lines):
        if line.startswith(('|switch|' + op, '|drag|' + op)):
            switched = True
        if line.startswith('|move|' + me) and '[from]' not in line:
            used = tid(line.split('|')[3])
            window = []
            for nxt in lines[i + 1:]:
                if nxt.startswith(('|move|', '|upkeep')):
                    break
                window.append(nxt)
            if any(w.startswith('|-activate|' + op) and any(p in w for p in PROTECT) for w in window):
                result = 'protect'
            elif any(w.startswith(('|-immune|', '|-fail|')) for w in window) or \
                    any('[from] ability:' in w and w.startswith(('|-heal|' + op, '|-boost|' + op, '|-start|' + op,
                                                                  '|-immune|' + op)) for w in window):
                result = 'failed'
            elif any(w.startswith('|-miss|') for w in window):
                result = 'miss'
            else:
                result = 'worked'
            return result, switched, used == move
    return 'none', switched, False


def _job(item):
    path, rows = item
    try:
        raw = load(path)
    except OSError:
        return [dict(r, result='no_log', target_switched=False, same_move=False, rating=None) for r in rows]
    out = []
    for r in rows:
        _, side = r['sample_id'].split(':')[:2]
        result, switched, same = fate(raw['log'], side, r['turn'], r['move'])
        out.append(dict(r, result=result, target_switched=switched, same_move=same, rating=raw.get('rating')))
    return out


def join(workers=32):
    where = raw_paths()
    grouped = defaultdict(list)
    for line in open(paths.TABLES / 'human-dead-labels.jsonl'):
        row = json.loads(line)
        row.pop('offset', None)
        grouped[where.get(row['sample_id'].split(':')[0], '/nonexistent')].append(row)
    rows = []
    with Pool(workers) as pool:
        for part in pool.imap_unordered(_job, grouped.items(), chunksize=64):
            rows.extend(part)
    rows.sort(key=lambda r: r['sample_id'])
    for r in rows:
        r['drop'] = r['result'] == 'failed' and not r['target_switched']
    with open(paths.TABLES / 'human-dead-hindsight.jsonl', 'w') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    group = lambda r: 'tour' if r['source'] == 'tour' else 'ladder_held' if r['held'] else 'ladder_trained'
    summary = dict(rows=len(rows),
                   by_result=dict(Counter('%s%s' % (r['result'], ' (foe switched)' if r['target_switched'] else '')
                                          for r in rows).most_common()),
                   drop=dict(Counter(group(r) for r in rows if r['drop'])),
                   dead_labels=dict(Counter(group(r) for r in rows)),
                   drop_by_mark=dict(Counter(r['mark'] for r in rows if r['drop'])),
                   drop_moves=Counter(r['move'] for r in rows if r['drop']).most_common(20),
                   worked_moves=Counter(r['move'] for r in rows if r['result'] == 'worked').most_common(12),
                   drop_repeats_last=sum(r['repeats_last'] for r in rows if r['drop']),
                   drop_after_own_failure=sum(r['last_fate'] in ('fail', 'immune', 'protect') for r in rows if r['drop']))
    (paths.TABLES / 'a4-dead-hindsight.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return summary


def strata():
    """A2 measures of the human label by rating band (the replay's rating: the lower of the two players)."""
    rating = {}
    for line in open(ladder.RUN_DATA / 'select/kept.jsonl'):
        row = json.loads(line)
        rating[row['replay_id']] = row.get('rating')
    cells = {name: {band: [] for _, _, band in BANDS} for name in PROBLEMS}
    for line in open(paths.TABLES / 'human-replays.jsonl'):
        r = json.loads(line)
        value = rating.get(r['replay'])
        if r['source'] != 'ladder' or value is None:
            continue
        band = next(b for lo, hi, b in BANDS if lo <= value < hi)
        for name in PROBLEMS:
            if name in r['measures']:
                cells[name][band].append(tuple(r['measures'][name]))
    out = {}
    for name in PROBLEMS:
        out[name] = {}
        for _, _, band in BANDS:
            got = compare._interval(cells[name][band], draws=2000)
            out[name][band] = dict(n=sum(x[0] for x in cells[name][band]), replays=len(cells[name][band]), rate=got)
        print('%-22s ' % name + ' | '.join('%s: %.3f [%.3f, %.3f] n=%d' % ((band,) + out[name][band]['rate'] +
                                                                           (out[name][band]['n'],))
                                           for _, _, band in BANDS))
    (paths.TABLES / 'a4-rating-strata.json').write_text(json.dumps(out, indent=1))
    return out


if __name__ == '__main__':
    dict(join=join, strata=strata)[sys.argv[1]]()
