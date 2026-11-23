"""EP-238 EX-195: opponent-action rows ("what will the opponent do this turn?") from the v12 rows, and fresh imitation rows.

    python -m integration.laya_foe.data_foe build        (any python 3; CPU, two passes over the v12 train files)

Labels come for free: the v12 train files hold both players' decisions of most games (rows are shuffled, so a
first pass collects every turn_action label by (game, player, turn), a second builds the rows). For a turn_action
row of player A at turn t whose opponent B also has a turn_action row at turn t, the opponent row is:
- state: A's v12 state, unchanged (A's information only: B's hidden set is not in it);
- question: "Predict the action the opponent will choose this turn ...", options from A's state only:
  B's active moves seen + likely (`OPP ... | seen` and `opp set: ... likely moves`), one "another move not yet seen",
  and a switch to every non-fainted B bench Pokemon (`opp team:`);
- label: B's actual choice (move name, tera variant folded; a move outside the listed moves -> the "other" option;
  a switch -> the species). Rows whose label species is not among the switch options are dropped and counted.
Splits by game:
- `heldout`: HELDOUT_GAMES games drawn (seed) from the ladder games NOT in v12-ladder-merged (never trained: EX-192
  used only the merged games). Their opponent rows and imitation rows are written apart and never trained on.
- the other unused ladder games give fresh imitation rows (`laya-compact-imitation/v12-fresh`, validation = the
  merged validation) and opponent rows; the merged games give opponent rows only.
Opponent train rows are capped at FOE_TRAIN_CAP (seeded sample over all train games).
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

SHARED = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research')
GEN = SHARED / 'datasets/generated'
V12 = GEN / 'laya-compact-imitation'
SOURCES = {'tour': V12 / 'v12-all/train.jsonl', 'ladder': V12 / 'v12-ladder/train.jsonl'}
MERGED = V12 / 'v12-ladder-merged'
OUT = GEN / 'laya-foe/v1'
FRESH = V12 / 'v12-fresh'
RUN = SHARED / 'runs/model-training/EX-195'
SEED = 20261195
HELDOUT_GAMES = 400
FOE_TRAIN_CAP = 600_000
INSTRUCTIONS = 'Predict the action the opponent will choose this turn in this Gen 9 OU singles battle.'
OTHER = 'foe:move:other'


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 22), b''):
            h.update(block)
    return h.hexdigest()


def _id(line):
    return line[14:line.index('"', 14)]


def _turn(state):
    head = state[:40].split(' | ')
    return int(head[0].split()[1]), head[1]


def label_of(row):
    """A row's own choice as (kind, name): ('move', move) or ('switch', species)."""
    action = row['expected']['action']
    if action.startswith('move:'):
        return 'move', action.split(':')[1]
    if action.startswith('switch:'):
        return 'switch', row['questions']['action']['criteria'][action].split(' ', 1)[0]
    return None


def _segments(line):
    return [s.strip() for s in line.split(' | ')]


def foe_options(state):
    """Options for the opponent's action, from the deciding player's state text only."""
    lines = state.split('\n')
    seen, likely, bench = [], [], []
    for line in lines:
        if line.startswith('OPP '):
            for seg in _segments(line):
                if seg.startswith('seen '):
                    seen = seg[5:].split()
        elif line.startswith('opp set:'):
            for part in line[len('opp set:'):].split(';'):
                part = part.strip()
                if part.startswith('likely moves '):
                    for item in part[len('likely moves '):].split(','):
                        bits = item.split()
                        if bits:
                            likely.append((bits[0], bits[1] if len(bits) > 1 else ''))
        elif line.startswith('opp team:'):
            for entry in line[len('opp team:'):].split('||'):
                segs = _segments(entry.strip())
                if not segs or not segs[0] or ' fainted' in segs[0] or segs[0].endswith('fainted'):
                    continue
                answer = [s for s in segs if s.startswith('answer ')]
                bench.append((segs[0].split(' ', 1)[0], ' | '.join([segs[0]] + answer[:1])))
    criteria = {}
    for m in seen:
        criteria['foe:move:' + m] = '%s (seen)' % m
    for m, p in likely:
        criteria.setdefault('foe:move:' + m, '%s (likely %s)' % (m, p) if p else '%s (likely)' % m)
    criteria[OTHER] = 'another move not yet seen'
    for species, text in bench:
        criteria.setdefault('foe:switch:' + species, 'switch to ' + text[:220])
    return criteria


def foe_row(row, label):
    criteria = foe_options(row['state'])
    kind, name = label
    if kind == 'move':
        target = 'foe:move:' + name
        if target not in criteria:
            target = OTHER
    else:
        target = 'foe:switch:' + name
        if target not in criteria:
            return None
    lk = 'foe_switch' if kind == 'switch' else ('foe_other' if target == OTHER else 'foe_move')
    return dict(sample_id=row['sample_id'] + ':foe', input_sha256=row['input_sha256'], state=row['state'],
                questions=dict(action=dict(type='choice', instructions=INSTRUCTIONS, criteria=criteria)),
                expected=dict(action=target), meta=dict(decision_kind='foe_action', label_kind=lk, tera_used=False))


def _labels():
    """Pass 1: (game, player, turn) -> label for every turn_action row; and the game -> source map."""
    labels, games = {}, {}
    for source, path in SOURCES.items():
        with open(path) as f:
            for line in f:
                sid = _id(line)
                if not sid.endswith(':turn_action'):
                    games.setdefault(sid.split(':')[0], source)
                    continue
                row = json.loads(line)
                game, player = sid.split(':')[:2]
                games.setdefault(game, source)
                labels[(game, player, _turn(row['state'])[0])] = label_of(row)
    return labels, games


def build():
    if (OUT / 'manifest.json').exists() or (FRESH / 'manifest.json').exists():
        raise FileExistsError('EX-195 outputs exist')
    started = time.time()
    RUN.mkdir(parents=True, exist_ok=True)
    merged_games = set(json.loads((MERGED / 'manifest.json').read_text())['ladder_games'])
    labels, games = _labels()
    unused = sorted(g for g, s in games.items() if s == 'ladder' and g not in merged_games)
    rng = random.Random(SEED)
    heldout = set(rng.sample(unused, HELDOUT_GAMES))
    print('[foe] pass 1: %d labels, %d games (%d ladder unused, %d held out)' % (
        len(labels), len(games), len(unused), len(heldout)), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    FRESH.mkdir(parents=True, exist_ok=True)
    tally = Counter()
    tmp_train = OUT / 'foe-train.all.jsonl'
    with open(tmp_train, 'w') as foe_train, open(OUT / 'foe-heldout.jsonl', 'w') as foe_held, \
            open(OUT / 'imitation-heldout.jsonl', 'w') as imi_held, open(FRESH / 'train.jsonl', 'w') as fresh:
        for source, path in SOURCES.items():
            with open(path) as f:
                for line in f:
                    sid = _id(line)
                    game, player = sid.split(':')[:2]
                    is_held = game in heldout
                    is_fresh = source == 'ladder' and game not in merged_games and not is_held
                    if is_held:
                        imi_held.write(line)
                        tally['imitation heldout'] += 1
                    elif is_fresh:
                        fresh.write(line)
                        tally['imitation fresh'] += 1
                    if not sid.endswith(':turn_action'):
                        continue
                    row = json.loads(line)
                    other = 'p2' if player == 'p1' else 'p1'
                    label = labels.get((game, other, _turn(row['state'])[0]))
                    if label is None:
                        tally['no opponent row'] += 1
                        continue
                    out = foe_row(row, label)
                    if out is None:
                        tally['dropped: switch target not in options'] += 1
                        continue
                    tally[out['meta']['label_kind'] + (' heldout' if is_held else ' train')] += 1
                    (foe_held if is_held else foe_train).write(json.dumps(out, ensure_ascii=False,
                                                                          separators=(',', ':')) + '\n')
    n = sum(1 for _ in open(tmp_train))
    keep = set(random.Random(SEED + 1).sample(range(n), min(n, FOE_TRAIN_CAP)))
    with open(tmp_train) as f, open(OUT / 'foe-train.jsonl', 'w') as g:
        for i, line in enumerate(f):
            if i in keep:
                g.write(line)
    tmp_train.unlink()
    shutil.copyfile(MERGED / 'validation.jsonl', FRESH / 'validation.jsonl')
    common = dict(created_at=time.time(), experiment='EX-195', plan='EP-238', seed=SEED, sources={
        k: str(v) for k, v in SOURCES.items()}, merged_manifest_sha256=sha(MERGED / 'manifest.json'),
        heldout_games=sorted(heldout))
    (FRESH / 'manifest.json').write_text(json.dumps(dict(
        common, dataset='laya-compact-imitation', version='v12-fresh',
        counts={'train:v12-ladder-unused': tally['imitation fresh'], 'validation:v12-ladder-merged': sum(
            1 for _ in open(FRESH / 'validation.jsonl'))},
        note='v12-ladder train rows of the ladder games not in v12-ladder-merged, minus the held-out games'),
        ensure_ascii=False, indent=1))
    manifest = dict(common, dataset='laya-foe', version='v1', instructions=INSTRUCTIONS, foe_train_cap=FOE_TRAIN_CAP,
                    foe_train_pool=n, counts=dict(tally),
                    files={p.name: sha(p) for p in sorted(OUT.glob('*.jsonl'))}, seconds=round(time.time() - started))
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    (RUN / 'build.json').write_text(json.dumps({k: v for k, v in manifest.items() if k != 'heldout_games'},
                                               ensure_ascii=False, indent=1))
    print(json.dumps(dict(tally), ensure_ascii=False))
    return manifest


if __name__ == '__main__':
    if sys.argv[1:] == ['build']:
        build()
    else:
        raise SystemExit(__doc__)
