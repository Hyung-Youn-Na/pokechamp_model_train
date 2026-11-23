"""EX-182 (D-215): foul-play search teacher labels on human train decisions; EX-183 training files.

    PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m integration.laya_distill.data_distill select
    ... data_distill label --qual        (qualification: QUAL_GAMES games, every position searched twice)
    ... data_distill label               (all selected games; resumable by finished game)
    python3 -m integration.laya_distill.data_distill build          (any python: teacher rows, validation, weights)

Positions: games of `v11-ladder-merged` train (never validation / locked test), drawn by game (seed SEED_SELECT);
TRAIN_GAMES for teacher train, VALIDATION_GAMES other games for teacher validation; in each game the non-lead
decisions with two or more options, at most PER_GAME of them drawn at random.
Each position: EX-177's tracker replays the game from that side (`render_job`'s order: advance, view, then the
human label as the previous choice) -> EX-181's `sample_states` (foul-play `prepare_battles`, sha256 seed per
position) -> one exact-iteration MCTS per sample (ITERATIONS, one thread) -> `aggregate` (sample-chance-weighted
visit share). Every laya option id maps to foul-play's choice string (`render_fp1.engine_choice`, a switch as
`switch <name>`); search share on choices no laya option has is dropped and the rest renormalised.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
import random
import sys
import time
import traceback

from integration.laya_distill import paths as P

TEACHER = P.TEACHER_RUN


def _sid(line):
    return line[14:line.index('"', 14)]


def select():
    """selection.json: {train: {game: [sid]}, validation: {game: [sid]}} (lead decisions dropped here; one-option
    decisions are dropped at labelling, where the options are known)."""
    by_game = {}
    with open(P.V11_MERGED / 'train.jsonl') as f:
        for line in f:
            sid = _sid(line)
            if sid.endswith(':lead'):
                continue
            by_game.setdefault(sid.split(':', 1)[0], []).append(sid)
    games = sorted(by_game)
    rng = random.Random(P.SEED_SELECT)
    rng.shuffle(games)
    out = {}
    for name, chosen in (('train', games[:P.TRAIN_GAMES]),
                         ('validation', games[P.TRAIN_GAMES:P.TRAIN_GAMES + P.VALIDATION_GAMES])):
        out[name] = {}
        for g in sorted(chosen):
            sids = sorted(by_game[g])
            out[name][g] = sorted(rng.sample(sids, min(P.PER_GAME, len(sids))))
    TEACHER.mkdir(parents=True, exist_ok=True)
    path = TEACHER / 'selection.json'
    if path.exists():
        raise SystemExit('%s exists; the selection is fixed' % path)
    path.write_text(json.dumps(dict(seed=P.SEED_SELECT, per_game=P.PER_GAME, **out), indent=1))
    print(json.dumps({k: dict(games=len(v), positions=sum(map(len, v.values()))) for k, v in out.items()}))


def _seed(sid, round_):
    return int(hashlib.sha256(('%d:%s:%d' % (P.SEED_SELECT, sid, round_)).encode()).hexdigest()[:16], 16)


def choice_map(view, actions, own_sets):
    """laya option id -> foul-play / poke-engine choice string."""
    from integration.laya_fp1 import render_fp1 as R
    out = {}
    for a in actions:
        aid = a['id']
        c = R.engine_choice(aid, view, own_sets)
        if aid.startswith('switch:'):
            c = 'switch ' + c
        out[aid] = c
    return out


def restrict(view, mapping):
    """The search may only use the legal actions (the laya options come from the real request): moves that are not
    an option are disabled (choice lock, Encore, Taunt, Assault Vest... the synthesized tracker request does not
    carry them), Tera is off without a `:tera` option, and with no switch option the active is trapped."""
    from fp.battle.helpers import normalize_name
    choices = set(mapping.values())
    me = view.user.active
    if me is not None:
        for m in me.moves:
            if normalize_name(m.name) not in choices:
                m.disabled = True
        if not any(c.endswith('-tera') for c in choices):
            me.can_terastallize = False
    if not any(c.startswith('switch ') for c in choices):
        view.user.trapped = True
    return view


def teacher(view, sid, mapping, rounds=1):
    """[{share over laya ids, q, unmapped, best laya id, samples, seconds}] per search round."""
    from integration.laya_regret import search as S
    out = []
    for round_ in range(rounds):
        started = time.monotonic()
        states, _ = S.sample_states(view, _seed(sid, round_))
        samples = []
        for i, (state, chance) in enumerate(states):
            r = S.mcts(dict(id=i, state=state, ms=P.SEARCH_TIME_MS, iterations=P.ITERATIONS))
            samples.append((chance, r))
        agg = S.aggregate(samples)
        if agg is None:
            out.append(None)
            continue
        inverse = {}
        for aid, c in mapping.items():
            inverse.setdefault(c, []).append(aid)
        share, unmapped = {aid: 0.0 for aid in mapping}, 0.0
        for c, s in agg['share'].items():
            if c in inverse:
                for aid in inverse[c]:
                    share[aid] += s / len(inverse[c])
            else:
                unmapped += s
        total = sum(share.values())
        if total <= 0:
            out.append(None)
            continue
        share = {k: v / total for k, v in share.items()}
        q = {aid: agg['q'][mapping[aid]] for aid in mapping if mapping[aid] in agg['q']}
        out.append(dict(share=share, q=q, unmapped=unmapped, best=max(share, key=lambda k: (share[k], k)),
                        root=agg['root'], samples=len(samples),
                        iterations=sorted(r['total_visits'] for _, r in samples),
                        seconds=round(time.monotonic() - started, 2)))
    return out


def label_job(job):
    from integration.laya_fp1 import data_fp1 as F
    from integration.laya_fp1 import tracker as T
    want = set(job['wanted'])
    rows, errors = [], []
    try:
        recovered, raw = F.load(job['recovered']), F.load(job['raw'])
    except Exception as exc:
        return dict(replay_id=job['replay_id'], rows=[], errors=[dict(stage='load', error=repr(exc))])
    result = recovered['result']
    for side in sorted(result['original_sets']):
        if not any(s.split(':')[1] == side for s in want):
            continue
        own = result['original_sets'][side]
        try:
            tracker = T.Tracker(raw, side, own)
        except Exception as exc:
            errors.append(dict(side=side, stage='init', error='%s: %s' % (type(exc).__name__, exc)))
            continue
        for record in T.recovered_records(recovered, side):
            sid = '%s:%s:%d:%s' % (job['replay_id'], side, record['cutoff_line'], record['decision_kind'])
            try:
                if record['decision_kind'] != 'lead':
                    tracker.advance(record['cutoff_line'], record['snapshot'], record['decision_kind'])
                    if sid in want and len(record['actions']) >= 2:
                        view = tracker.view()
                        mapping = choice_map(view, record['actions'], own)
                        restrict(view, mapping)
                        found = teacher(view, sid, mapping, rounds=job['rounds'])
                        rows.append(dict(sample_id=sid, kind=record['decision_kind'], label=record.get('label'),
                                         mapping=mapping, search=found))
                tracker.chose(record.get('label'))
            except Exception as exc:
                errors.append(dict(side=side, sample_id=sid, stage='decision', wanted=sid in want,
                                   error='%s: %s' % (type(exc).__name__, exc),
                                   trace=traceback.format_exc(limit=3)[-600:]))
                break
    return dict(replay_id=job['replay_id'], rows=rows, errors=errors)


def _init():
    from integration.laya_fp1 import tracker
    tracker.setup()


def label(qual=False, workers=P.WORKERS):
    from multiprocessing import Pool
    from integration.laya_fp1 import data_fp1 as F
    if os.environ.get('PYTHONHASHSEED') != '0':
        raise RuntimeError('run with PYTHONHASHSEED=0')
    sel = json.loads((TEACHER / 'selection.json').read_text())
    split_of = {}
    want = {}
    for split in ('train', 'validation'):
        for g, sids in sel[split].items():
            split_of[g] = split
            for s in sids:
                want[s] = split
    if qual:
        games = sorted(sel['train'])[:P.QUAL_GAMES]
        want = {s: v for s, v in want.items() if s.split(':', 1)[0] in set(games)}
    out_dir = TEACHER / ('qualification' if qual else 'staging')
    out_dir.mkdir(parents=True, exist_ok=True)
    done = set()
    for part in out_dir.glob('done-*.txt'):
        done.update(part.read_text().split())
    todo = [dict(j, rounds=2 if qual else 1) for j in F.jobs(want) if j['replay_id'] not in done
            and j['replay_id'] not in P.EXCLUDED_GAMES]
    print('[teacher] %d positions, %d games to do (%d done), workers %d' % (len(want), len(todo), len(done), workers),
          flush=True)
    tag = '%d-%d' % (int(time.time()), os.getpid())
    started, n, nrows, nerr = time.time(), 0, 0, 0
    with open(out_dir / ('part-%s.jsonl' % tag), 'a') as out, open(out_dir / ('errors-%s.jsonl' % tag), 'a') as err, \
            open(out_dir / ('done-%s.txt' % tag), 'a') as fin, Pool(workers, initializer=_init, maxtasksperchild=20) as pool:
        for res in pool.imap_unordered(label_job, todo, chunksize=1):
            for row in res['rows']:
                out.write(json.dumps(dict(row, split=split_of[res['replay_id']]), separators=(',', ':')) + '\n')
            for e in res['errors']:
                err.write(json.dumps(dict(e, replay_id=res['replay_id'])) + '\n')
            out.flush(), err.flush()
            fin.write(res['replay_id'] + '\n')
            fin.flush()
            n += 1
            nrows += len(res['rows'])
            nerr += len(res['errors'])
            if n % 20 == 0 or n == len(todo):
                rate = n / max(1e-9, time.time() - started)
                print('[teacher] %d/%d games, %d positions, %d errors, %.3f games/s, eta %.0f min' % (
                    n, len(todo), nrows, nerr, rate, (len(todo) - n) / max(1e-9, rate) / 60), flush=True)
    return dict(games=n, positions=nrows, errors=nerr)


def staged(directory):
    rows = {}
    for part in sorted(directory.glob('part-*.jsonl')):
        for line in open(part):
            r = json.loads(line)
            rows[r['sample_id']] = r
    return rows


def qualification():
    rows = list(staged(TEACHER / 'qualification').values())
    searched = [r for r in rows if r['search'] and all(r['search'])]
    unm = [r['search'][0]['unmapped'] for r in searched]
    agree = sum(r['search'][0]['best'] == r['search'][1]['best'] for r in searched)
    secs = sorted(s['seconds'] / max(1, s['samples']) for r in searched for s in r['search'])
    human = [r for r in searched if r['label'] in r['search'][0]['share']]
    out = dict(positions=len(rows), searched=len(searched),
               unmapped_mean=sum(unm) / max(1, len(unm)),
               unmapped_row_rate=sum(u > P.UNMAPPED_ROW for u in unm) / max(1, len(unm)),
               repeat_top1_agreement=agree / max(1, len(searched)),
               seconds_per_sample_p50=secs[len(secs) // 2] if secs else None,
               human_top1_agreement=sum(r['search'][0]['best'] == r['label'] for r in human) / max(1, len(human)),
               human_share_mean=sum(r['search'][0]['share'][r['label']] for r in human) / max(1, len(human)))
    out['passed'] = bool(searched) and out['unmapped_mean'] <= P.UNMAPPED_MEAN and \
        out['unmapped_row_rate'] <= P.UNMAPPED_ROW_RATE and abs(out['repeat_top1_agreement'] - 0.869) <= 0.10 and \
        out['seconds_per_sample_p50'] <= 1.5 * 3.94
    (TEACHER / 'qualification.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def build():
    """laya-distill/v1: teacher-train.jsonl, teacher-validation.jsonl (v11 rows + gold), human-weights (EX-183),
    validation.jsonl (= teacher validation, the EX-183 selection file), manifest.json."""
    rows = staged(TEACHER / 'staging')
    keep = {s: r for s, r in rows.items() if r['search'] and r['search'][0] and
            r['search'][0]['unmapped'] <= P.UNMAPPED_ROW}
    P.DATA.mkdir(parents=True, exist_ok=True)
    counts, sel = Counter(), json.loads((TEACHER / 'selection.json').read_text())
    held_games = set(sel['validation'])
    outs = {'train': open(P.DATA / 'teacher-train.jsonl', 'w'), 'validation': open(P.DATA / 'teacher-validation.jsonl', 'w')}
    weights_src = [json.loads(x)['weight'] for x in open(P.EX172_WEIGHTS)]
    rng = random.Random(P.SEED_HUMAN)
    human_w = []
    with open(P.V11_MERGED / 'train.jsonl') as f:
        for i, line in enumerate(f):
            sid = _sid(line)
            game = sid.split(':', 1)[0]
            w = weights_src[i]
            if game in held_games or rng.random() >= P.HUMAN_SHARE:
                w = 0.0
            human_w.append(w)
            if sid in keep:
                r = json.loads(line)
                t = keep[sid]
                row = dict(sample_id=sid, state=r['state'], questions=r['questions'],
                           gold={'action': {'probabilities': t['search'][0]['share']}},
                           meta=dict(r.get('meta', {}), human_label=r['expected']['action'], teacher=True))
                split = t['split']
                outs[split].write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
                counts[split] += 1
    for h in outs.values():
        h.close()
    (P.DATA / 'human-weights').mkdir(exist_ok=True)
    with open(P.DATA / 'human-weights/weights.jsonl', 'w') as f:      # `train_v11.load_weights` layout
        for w in human_w:
            f.write(json.dumps(dict(weight=w)) + '\n')
    (P.DATA / 'human-weights/manifest.json').write_text(json.dumps(dict(
        source=str(P.EX172_WEIGHTS), share=P.HUMAN_SHARE, seed=P.SEED_HUMAN, held_out_games=len(held_games),
        kept=sum(1 for w in human_w if w > 0), rows=len(human_w)), indent=1))
    (P.DATA / 'validation.jsonl').write_text((P.DATA / 'teacher-validation.jsonl').read_text())
    os.symlink(P.V11_MERGED / 'train.jsonl', P.DATA / 'train.jsonl') if not (P.DATA / 'train.jsonl').exists() else None
    man = dict(counts=dict(counts), staged=len(rows), dropped=len(rows) - len(keep),
               human_kept=sum(1 for w in human_w if w > 0), human_rows=len(human_w),
               weights_source=str(P.EX172_WEIGHTS), excluded_games=P.EXCLUDED_GAMES, at=time.time())
    (P.DATA / 'manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man))


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('select')
    lab = sub.add_parser('label')
    lab.add_argument('--qual', action='store_true')
    lab.add_argument('--workers', type=int, default=P.WORKERS)
    sub.add_parser('qualification')
    sub.add_parser('build')
    args = parser.parse_args(argv)
    if args.cmd == 'select':
        select()
    elif args.cmd == 'label':
        print(json.dumps(label(args.qual, args.workers)))
        if args.qual:
            qualification()
    elif args.cmd == 'qualification':
        qualification()
    else:
        build()


if __name__ == '__main__':
    main()
