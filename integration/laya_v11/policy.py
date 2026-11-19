"""EX-170 (D-209 decision 4, values of D-210): what v11rtc trains on besides the v11 rows.

    python -m integration.laya_v11.policy weights        # exclusions and row weights for v11-ladder-merged train
    python -m integration.laya_v11.policy corrections    # bot-state correction rows from the local games

`weights` reads every imitation train row once:
- drop (weight 0): the human label is a dead option in the v11 input (fixed-judge confirmed fail or x0 damage) and the
  raw replay shows the move failed with the foe not switching (`analysis.hindsight.fate`);
- weight: `WEIGHTS[category]` for rows whose label is the response of a category (the largest when several apply):
  `stalled_break` (stalled damaging streak, label is another action), `duel_lose_switch` (`duel -> lose`, label
  switches), `boosted_switch` (foe at +2 Atk / SpA or more, label switches);
- everything else 1. Weights are scaled so the kept rows average 1 (EX-146's rule).
The file has the `outcome_weights` layout (`weights.jsonl`: sample_id, weight).

`corrections` renders the local bot-vs-bot decisions with the v11 renderer and keeps turn decisions where v10rt chose
(or would have chosen by argmax) an unacceptable option, or where its own last move had just failed. Unacceptable =
dead in the v11 input, or the move that just failed (fail / immune) against the same foe. The target is v10rt's logged
distribution with the unacceptable options at 0, renormalised (`gold` rows, laya's soft-target schema).
"""
from __future__ import annotations
from collections import Counter, defaultdict
import json
from multiprocessing import Pool, get_context
import os
import sys
import time

from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic, seal, sha

from . import data_v11, paths
from .analysis import features as F
from .analysis import games, hindsight, rules

WEIGHTS = dict(stalled_break=1.9, duel_lose_switch=1.4, boosted_switch=2.2)      # D-210
OUT_WEIGHTS = c.SHARED / 'datasets/generated/laya-v11-policy-weights/v1'
OUT_CORRECTIONS = c.SHARED / 'datasets/generated/laya-v11-corrections/v1'
LOCAL_GAMES = c.SHARED / 'runs/model-training/EX-170/localplay/games'
_render = _tok = None


def categories(facts, state, label):
    if facts['kind'] != 'turn_action':
        return []
    chosen = F.chosen(facts, label)
    out = []
    if F.loop_class(state, label) == 'stall_break':
        out.append('stalled_break')
    if facts['duel'] == 'lose' and chosen['switch']:
        out.append('duel_lose_switch')
    if facts['opp_offence'] >= 2 and chosen['switch']:
        out.append('boosted_switch')
    return out


def _scan(job):
    path, start, end = job
    rows = []
    with open(path, 'rb') as f:
        if start:
            f.seek(start - 1)
            f.readline()
        while f.tell() < end:
            line = f.readline()
            if not line:
                break
            row = json.loads(line)
            state, criteria = row['state'], row['questions']['action']['criteria']
            label = row['expected']['action']
            facts = F.describe(state, criteria)
            cats = categories(facts, state, label)
            dead = None
            if facts['kind'] == 'turn_action':
                chosen = F.chosen(facts, label)
                if chosen['dead']:
                    dead = dict(turn=facts['turn'], move=chosen['move'])
            rows.append((row['sample_id'], cats, dead))
    return rows


def _fates(item):
    path, rows = item
    try:
        raw = hindsight.load(path)
    except OSError:
        return [(sid, 'no_log', False) for sid, _ in rows]
    out = []
    for sid, dead in rows:
        result, switched, _ = hindsight.fate(raw['log'], sid.split(':')[1], dead['turn'], dead['move'])
        out.append((sid, result, switched))
    return out


def weights(workers=48):
    out = OUT_WEIGHTS
    if (out / 'manifest.json').exists():
        raise FileExistsError(out)
    train = data_v11.MERGED / 'train.jsonl'
    size = os.path.getsize(train)
    step = size // (workers * 2) + 1
    jobs = [(str(train), a, min(size, a + step)) for a in range(0, size, step)]
    started = time.time()
    cats, dead, order = {}, {}, []
    with Pool(workers) as pool:
        for part in pool.imap(_scan, jobs):
            for sid, cs, d in part:
                order.append(sid)
                if cs:
                    cats[sid] = cs
                if d:
                    dead[sid] = d
    if len(set(order)) != len(order):
        raise ValueError('sample ids repeat in %s' % train)
    where = hindsight.raw_paths()
    grouped = defaultdict(list)
    for sid, d in dead.items():
        grouped[where.get(sid.split(':')[0], '/nonexistent')].append((sid, d))
    fate = {}
    with Pool(workers) as pool:
        for part in pool.imap_unordered(_fates, grouped.items(), chunksize=64):
            for sid, result, switched in part:
                fate[sid] = (result, switched)
    drop = {sid for sid, (result, switched) in fate.items() if result == 'failed' and not switched}
    raw = {}
    counts = Counter(rows=len(order), dead_labels=len(dead), dropped=len(drop))
    for sid in order:
        if sid in drop:
            raw[sid] = 0.0
            continue
        value = max((WEIGHTS[k] for k in cats.get(sid, ())), default=1.0)
        raw[sid] = value
        for k in cats.get(sid, ()):
            counts['category:' + k] += 1
        counts['weighted'] += value != 1.0
    kept = len(order) - len(drop)
    scale = kept / sum(raw.values())
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'weights.jsonl', 'w') as f:
        for sid in order:
            f.write(json.dumps(dict(sample_id=sid, weight=raw[sid] * scale)) + '\n')
    with open(out / 'dropped.jsonl', 'w') as f:
        for sid in order:
            if sid in drop:
                f.write(json.dumps(dict(sample_id=sid, **dead[sid])) + '\n')
    manifest = dict(dataset='laya-v11-policy-weights', version='v1', experiment='EX-170', decision='D-209 / D-210',
                    rule=dict(weights=WEIGHTS, drop='dead label in the v11 input that failed in the replay, foe not '
                                                    'switching', overlap='largest weight', scale='kept rows average 1'),
                    counts=dict(counts), scale=scale, kept=kept,
                    fates=dict(Counter('%s%s' % (r, ' (foe switched)' if s else '') for r, s in fate.values())),
                    mean_kept=sum(raw.values()) * scale / kept,
                    source=dict(dataset=str(data_v11.MERGED), train_sha256=sha(train)),
                    seconds=round(time.time() - started, 1))
    atomic(out / 'manifest.json', manifest, immutable=True)
    seal(out)
    print(json.dumps(manifest, indent=1))
    return manifest


# ----------------------------------------------------------------------------- correction rows

def _init_render():
    global _render, _tok
    from integration.laya_imitation.data_v2 import _tokenizer
    from . import render_v11
    from .analysis import render
    render_v11.install()
    _render = render.live_renderer()
    _tok = _tokenizer()


def _game(name):
    from integration.laya_v10 import data_v10
    from integration.pokechamp.imitation.schema import ImitationInput
    folder = LOCAL_GAMES / name
    bot = name.split('-')[2]
    game = games.Game(name, root=LOCAL_GAMES, bot=bot)
    if game.result.get('status') != 'completed' or game.me is None:
        return name, [], Counter(skipped_games=1)
    rows, counts = [], Counter(games=1)
    budget = data_v10.base_budget()
    for row in game.rows():
        if row['automatic'] or row['kind'] != 'turn_action' or not row['probabilities']:
            continue
        counts['turn_decisions'] += 1
        e = game.inputs[row['k']]
        state, question = _render(ImitationInput.from_body(e['body']))
        facts = F.describe(state, question['criteria'])
        probs = row['probabilities']
        if set(probs) != set(question['criteria']):
            counts['option_mismatch'] += 1
            continue
        failed_before = facts['last_fate'] in ('fail', 'immune') and rules._same_foe(state, facts['turn'])
        bad = {a for a, m in facts['marks'].items()
               if m['dead'] or (failed_before and m['move'] and m['move'] == facts['last_move'])}
        kinds = []
        if row['choice'] in bad:
            kinds.append('chose_unacceptable')
        if row['argmax'] in bad:
            kinds.append('argmax_unacceptable')
        if failed_before:
            kinds.append('after_own_failure')
        if not kinds:
            continue
        target = {a: (0.0 if a in bad else p) for a, p in probs.items()}
        total = sum(target.values())
        if total <= 0:
            counts['no_acceptable_option'] += 1
            continue
        target = {a: p / total for a, p in target.items()}
        m = data_v10.measure_row(_tok, state, question, budget['head'], budget['option'])
        if not data_v10.fits(m, budget['head'], budget['option']):
            counts['over_budget'] += 1
            continue
        for k in kinds:
            counts['kind:' + k] += 1
        counts['rows'] += 1
        counts['removed_mass'] += 1.0 - total
        rows.append(dict(sample_id='local:%s:%s' % (name, row['decision']), state=state,
                         questions={'action': question}, gold={'action': {'probabilities': target}},
                         meta=dict(decision_kind='turn_action', source='correction', kinds=kinds,
                                   v10rt_choice=row['choice'], policy=row['policy'], removed=sorted(bad))))
    return name, rows, counts


def corrections(workers=32):
    out = OUT_CORRECTIONS
    if (out / 'manifest.json').exists():
        raise FileExistsError(out)
    names = sorted(p.name for p in LOCAL_GAMES.iterdir() if (p / 'result.json').exists())
    started = time.time()
    rows, counts = [], Counter()
    with get_context('spawn').Pool(workers, initializer=_init_render) as pool:
        for _, part, c_ in pool.imap(_game, names, chunksize=4):
            rows.extend(part)
            counts.update(c_)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'train.jsonl', 'w') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    from . import render_v11
    render_v11.install()
    summary = json.loads((LOCAL_GAMES.parent / 'summary.json').read_text())
    manifest = dict(dataset='laya-v11-corrections', version='v1', experiment='EX-170', decision='D-209',
                    counts={k: (round(v, 3) if isinstance(v, float) else v) for k, v in sorted(counts.items())},
                    local_play=summary, render=render_v11.VERSION, judge=render_v11.judge_identity(),
                    target='v10rt logged probabilities with unacceptable options at 0, renormalised',
                    files={'train.jsonl': sha(out / 'train.jsonl')}, seconds=round(time.time() - started, 1))
    atomic(out / 'manifest.json', manifest, immutable=True)
    seal(out)
    print(json.dumps(manifest, indent=1))
    return manifest


if __name__ == '__main__':
    dict(weights=weights, corrections=corrections)[sys.argv[1]]()
