"""EX-169 A2: the same measures on (1) human labels, (2) v10rt on human states, (3) the bot on its own states.

    python -m integration.laya_v11.analysis.compare score     # GPU3: v10rt on held-out human rows
    python -m integration.laya_v11.analysis.compare table     # the three-way table

(2) uses ladder train-pool rows that `v10-ladder-merged` left out (older games, not seen by v10rt) and is paired with
the human label on the same rows. A random sample covers the common measures; each rare measure gets its own random
top-up, and a measure is only computed on the random sample plus its own top-up (a row drawn for another measure
would bias it). Intervals: replay-cluster (human) and game-cluster (bot) bootstrap, 95%.
"""
from __future__ import annotations
from collections import defaultdict
import json
import random
import sys

from integration.laya_ladder import paths as ladder

from .. import paths
from . import features as F
from . import score as S

RANDOM_ROWS = 12000
TOP_UP = 2500
RARE = ('dead_pick', 'all_dead_switch', 'repeat_after_fail', 'stalled_streak_repeat', 'duel_lose_switch',
        'boosted_foe_switch', 'protect_again')
DRAWS = 10000
ORDER = ('switch', 'status_move', 'tera', 'dead_pick', 'dead_pick_live_move', 'all_dead_switch', 'repeat_after_fail',
         'repeat_after_ok', 'stalled_streak_repeat', 'duel_lose_switch', 'duel_win_switch', 'boosted_foe_switch',
         'boosted_foe_status', 'protect_again')


def sample():
    """{sample_id: (offset, tags)}; tags name the draws a row belongs to (`random` or a rare measure)."""
    rng = random.Random(paths.SEED)
    rows = [json.loads(line) for line in open(paths.TABLES / 'human-held-candidates.jsonl')]
    rows.sort(key=lambda r: r[0])
    chosen = {}
    for sid, offset, _ in rng.sample(rows, RANDOM_ROWS):
        chosen[sid] = (offset, {'random'})
    for name in RARE:
        pool = [r for r in rows if name in r[2]]
        for sid, offset, _ in rng.sample(pool, min(TOP_UP, len(pool))):
            chosen.setdefault(sid, (offset, set()))[1].add(name)
    return chosen


def score():
    target = paths.TABLES / 'human-scored.jsonl'
    if target.exists():
        raise FileExistsError(target)
    chosen = sample()
    rows = []
    with open(ladder.LADDER_ROWS / 'train.jsonl', 'rb') as f:
        for sid, (offset, tags) in sorted(chosen.items(), key=lambda kv: kv[1][0]):
            f.seek(offset)
            row = json.loads(f.readline())
            if row['sample_id'] != sid:
                raise ValueError('offset does not match ' + sid)
            q = row['questions']['action']
            rows.append(dict(sample_id=sid, tags=sorted(tags), state=row['state'], criteria=q['criteria'],
                             instructions=q['instructions'], label=row['expected']['action']))
    with S.held_gpu():
        probs = S.Scorer().probabilities(rows, batch_size=32)
    with open(target, 'w') as f:
        for row, p in zip(rows, probs):
            f.write(json.dumps(dict(row, probabilities=p), ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps(dict(rows=len(rows), random=sum('random' in r['tags'] for r in rows))))


def _resampled(matrix, draws, seed, chunk=100):
    """Column sums of `matrix` (clusters x columns) over `draws` cluster resamples, with numpy."""
    import numpy as np
    matrix = np.asarray(matrix, dtype=float)
    rng = np.random.default_rng(seed)
    k = matrix.shape[0]
    if k > 20000:
        draws = min(draws, 2000)
    p = np.full(k, 1.0 / k)
    out = np.empty((draws, matrix.shape[1]))
    done = 0
    while done < draws:
        m = min(chunk, draws - done)
        out[done:done + m] = rng.multinomial(k, p, size=m) @ matrix
        done += m
    return out


def _interval(clusters, draws=DRAWS, seed=paths.SEED):
    """clusters: list of (n, s) per cluster -> (rate, lo, hi) of sum(s)/sum(n)."""
    import numpy as np
    n, s = sum(c[0] for c in clusters), sum(c[1] for c in clusters)
    if not n:
        return None
    sums = _resampled([(c[0], c[1]) for c in clusters], draws, seed)
    rates = sums[:, 1][sums[:, 0] > 0] / sums[:, 0][sums[:, 0] > 0]
    lo, hi = np.percentile(rates, [2.5, 97.5])
    return s / n, float(lo), float(hi)


def _diff(clusters, draws=DRAWS, seed=paths.SEED):
    """clusters: list of (n, a, b) -> (b - a)/n with a cluster bootstrap interval (paired rows)."""
    import numpy as np
    n = sum(c[0] for c in clusters)
    if not n:
        return None
    sums = _resampled([(c[0], c[2] - c[1]) for c in clusters], draws, seed)
    values = sums[:, 1][sums[:, 0] > 0] / sums[:, 0][sums[:, 0] > 0]
    lo, hi = np.percentile(values, [2.5, 97.5])
    return sum(c[2] - c[1] for c in clusters) / n, float(lo), float(hi)


def human_all():
    """Label rates over every scanned human row, by replay cluster: {measure: {group: [(n, s)]}}."""
    out = defaultdict(lambda: defaultdict(list))
    for line in open(paths.TABLES / 'human-replays.jsonl'):
        r = json.loads(line)
        group = 'tour' if r['source'] == 'tour' else 'ladder_held' if r['held'] else 'ladder_trained'
        for name, (n, s) in r['measures'].items():
            out[name][group].append((n, s))
            out[name]['all'].append((n, s))
    return out


def human_scored():
    """On the scored held-out rows, per measure and replay: n, label sum, v10rt argmax sum, v10rt mass sum."""
    out = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0.0]))
    for line in open(paths.TABLES / 'human-scored.jsonl'):
        r = json.loads(line)
        facts = F.describe(r['state'], r['criteria'])
        probs = r['probabilities']
        top = max(probs, key=probs.get)
        label, argmax, mass = (F.measures(facts, r['state'], r['label']), F.measures(facts, r['state'], top),
                               F.mass(facts, r['state'], probs))
        replay = r['sample_id'].split(':')[0]
        for name in label:
            if 'random' not in r['tags'] and name not in r['tags']:
                continue
            cell = out[name][replay]
            cell[0] += 1
            cell[1] += label[name]
            cell[2] += argmax[name]
            cell[3] += mass.get(name, 0.0)
    return out


def bot():
    """Per measure and game: n, chosen sum, model mass sum, over argmax-policy decisions (`sampled` ones listed apart)."""
    out = {key: defaultdict(lambda: defaultdict(lambda: [0, 0, 0.0])) for key in ('argmax', 'sample')}
    for row in S.decisions():
        if row['automatic'] or row['state'] is None:
            continue
        facts = F.describe(row['state'], row['criteria'])
        probs = row['probabilities']
        top = max(probs, key=probs.get)
        policy = 'sample' if row['policy'] == 'sample' else 'argmax'
        picked = F.measures(facts, row['state'], top if policy == 'argmax' else row['choice'])
        mass = F.mass(facts, row['state'], probs)
        for name, value in picked.items():
            cell = out[policy][name][row['game']]
            cell[0] += 1
            cell[1] += value
            cell[2] += mass.get(name, 0.0)
    return out


def table():
    everything, scored, own = human_all(), human_scored(), bot()
    rows = []
    for name in ORDER:
        entry = dict(measure=name)
        for group in ('all', 'ladder_held'):
            got = _interval(everything[name][group]) if everything[name][group] else None
            entry['human_' + group] = dict(n=sum(c[0] for c in everything[name][group]), rate=got) if got else None
        cells = list(scored[name].values())
        if cells:
            entry['scored'] = dict(n=sum(c[0] for c in cells), label=_interval([(c[0], c[1]) for c in cells]),
                                   argmax=_interval([(c[0], c[2]) for c in cells]),
                                   mass=_interval([(c[0], c[3]) for c in cells]),
                                   argmax_minus_label=_diff([(c[0], c[1], c[2]) for c in cells]),
                                   mass_minus_label=_diff([(c[0], c[1], c[3]) for c in cells]))
        for policy in ('argmax', 'sample'):
            cells = list(own[policy][name].values())
            if cells:
                entry['bot_' + policy] = dict(n=sum(c[0] for c in cells), games=len(cells),
                                              chosen=_interval([(c[0], c[1]) for c in cells]),
                                              mass=_interval([(c[0], c[2]) for c in cells]))
        rows.append(entry)
    (paths.TABLES / 'a2-three-way.json').write_text(json.dumps(rows, indent=1))
    fmt = lambda t: '-' if t is None else '%.3f [%.3f, %.3f]' % t
    print('%-22s | %-30s | %-30s | %-30s | %-30s | %-30s' % ('measure', 'human label (all rows)',
                                                              'human label (scored held-out)', 'v10rt argmax (same rows)',
                                                              'v10rt mass (same rows)', 'bot argmax games: chosen'))
    for e in rows:
        s, b = e.get('scored'), e.get('bot_argmax')
        print('%-22s | %-30s | %-30s | %-30s | %-30s | %-30s' % (
            e['measure'], '%s n=%d' % (fmt(e['human_all']['rate']), e['human_all']['n']) if e['human_all'] else '-',
            '%s n=%d' % (fmt(s['label']), s['n']) if s else '-', fmt(s['argmax']) if s else '-',
            fmt(s['mass']) if s else '-', '%s n=%d' % (fmt(b['chosen']), b['n']) if b else '-'))
    print()
    for e in rows:
        s, b = e.get('scored'), e.get('bot_argmax')
        if s and b:
            print('%-22s argmax-label %s | mass-label %s | bot mass %s' % (
                e['measure'], fmt(s['argmax_minus_label']), fmt(s['mass_minus_label']), fmt(b['mass'])))
    return rows


if __name__ == '__main__':
    dict(score=score, table=table)[sys.argv[1]]()
