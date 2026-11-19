"""EX-177 qualification 1 (tracker vs laya snapshot) over a seeded sample of reference games, both sources.

    PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m integration.laya_fp1.qualify \
        --games 40 --out RUN/qualification-1.json

Every decision of the sampled games is compared (activity, species, HP within 1%, boosts, active status, side
condition kinds, weather); the report gives the decision count, mismatch counts by field and examples.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import random

from integration.laya_fp1 import data_fp1 as D
from integration.laya_fp1 import probe as PR
from integration.laya_fp1 import tracker as T


BOOST_KEYS = {'attack': 'atk', 'defense': 'def', 'special-attack': 'spa', 'special-defense': 'spd', 'speed': 'spe'}
EV_KEYS = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')


def _spec(p, original=None):
    evs = (original or {}).get('evs') or dict(zip(EV_KEYS, getattr(p, 'evs', None) or (0,) * 6))
    return dict(species=p.name, level=p.level, nature=(original or {}).get('nature') or p.nature,
                evs={k: int(evs.get(k, 0)) for k in EV_KEYS}, ability=p.ability, item=p.item,
                boosts={BOOST_KEYS[k]: v for k, v in p.boosts.items() if k in BOOST_KEYS and v},
                status=str(p.status) if p.status else '', hp_percent=100.0 * p.hp / max(1, p.max_hp))


def damage_check(scenes=200, out=None):
    """Qualification 5 (report only): poke-engine max normal roll vs @smogon/calc max roll, same attacker / defender
    (my active vs the top sampled opponent set), damaging non-tera moves, the battle's weather."""
    import subprocess
    from poke_engine import calculate_damage
    from integration.laya_fp1 import render_fp1 as R
    calc = subprocess.Popen(['node', str(T_ROOT / 'integration/laya_imitation/calc.cjs')], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    if json.loads(calc.stdout.readline()).get('status') != 'ready':
        raise RuntimeError('calc worker failed')
    rng = random.Random(5)
    lines = open(D.SOURCES['ladder']['replays']).readlines()
    rng.shuffle(lines)
    diffs, rows = [], []
    for line in lines:
        if len(rows) >= scenes:
            break
        r = json.loads(line)
        path = D.SOURCES['ladder']['recovered'] / (r['replay_id'] + '.json.gz')
        if not path.exists():
            continue
        rec, raw = D.load(path), D.load(r['raw_path'])
        side = sorted(rec['result']['original_sets'])[0]
        own = rec['result']['original_sets'][side]
        tr = T.Tracker(raw, side, own)
        records = [x for x in T.recovered_records(rec, side) if x['decision_kind'] == 'turn_action']
        if not records:
            continue
        pick = records[rng.randrange(len(records))]
        for x in T.recovered_records(rec, side):
            if x['cutoff_line'] > pick['cutoff_line']:
                break
            if x['decision_kind'] != 'lead':
                tr.advance(x['cutoff_line'], x['snapshot'], x['decision_kind'])
            if x is not pick:
                tr.chose(x.get('label'))
        view = tr.view()
        draws = R.sample(view, R.seed_of(r['replay_id']), 8)
        if not draws:
            continue
        b = draws[0]
        state = R.engine_state(b)
        me, foe = b.user.active, b.opponent.active
        original = next((s for s in own if T.ident(s['species']) in (me.name, me.base_name)), None)
        weather = T.ident(b.weather or '')
        for m in me.moves:
            from fp.data import all_move_json
            if all_move_json.get(m.name, {}).get('category') == 'status':
                continue
            try:
                engine = calculate_damage(state, m.name, 'none', True)[0][0]
            except Exception:
                continue
            req = dict(attacker=_spec(me, original), defender=_spec(foe), move=m.name, weather=weather)
            calc.stdin.write(json.dumps([req]) + '\n')
            calc.stdin.flush()
            res = json.loads(calc.stdout.readline())[0]
            if 'error' in res or res.get('max', 0) <= 0 and engine <= 0:
                continue
            pct = 100.0 * engine / max(1, foe.max_hp)
            diffs.append(pct - res['max'])
            rows.append(dict(replay=r['replay_id'], me=me.name, foe=foe.name, move=m.name, engine_max=round(pct, 1),
                             calc_max=res['max'], unresolved=res.get('unresolved')))
    calc.stdin.close()
    a = sorted(abs(d) for d in diffs)
    report = dict(scenes=len(rows), within_1pt=sum(x <= 1.0 for x in a) / max(1, len(a)),
                  within_5pt=sum(x <= 5.0 for x in a) / max(1, len(a)),
                  median_abs=a[len(a) // 2] if a else None, worst=sorted(rows, key=lambda x: -abs(
                      x['engine_max'] - x['calc_max']))[:15])
    text = json.dumps(report, indent=1)
    if out:
        open(out, 'w').write(text)
    print(text[:3000])


T_ROOT = D.ROOT


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--games', type=int, default=40)
    parser.add_argument('--out')
    parser.add_argument('--damage', type=int, default=0, help='qualification 5 with this many scenes instead')
    args = parser.parse_args(argv)
    if args.damage:
        return damage_check(args.damage, args.out)
    rng = random.Random(20261118)
    picks = []
    for source, where in D.SOURCES.items():
        lines = open(where['replays']).readlines()
        for line in rng.sample(lines, args.games // 2):
            r = json.loads(line)
            picks.append((source, r['replay_id'], r['raw_path'], where['recovered'] / (r['replay_id'] + '.json.gz')))
    decisions, mismatched, fields, examples, errors = 0, 0, Counter(), [], []
    for source, rid, raw_path, rec_path in picks:
        if not rec_path.exists():
            continue
        rec, raw = D.load(rec_path), D.load(raw_path)
        for side in sorted(rec['result']['original_sets']):
            try:
                tr = T.Tracker(raw, side, rec['result']['original_sets'][side])
                for r in T.recovered_records(rec, side):
                    if r['decision_kind'] == 'lead':
                        tr.chose(r.get('label'))
                        continue
                    tr.advance(r['cutoff_line'], r['snapshot'], r['decision_kind'])
                    issues = PR.compare(tr.view(), r['snapshot'])
                    decisions += 1
                    if issues:
                        mismatched += 1
                        for i in issues:
                            fields[i[0]] += 1
                        if len(examples) < 20:
                            examples.append(dict(source=source, sample=rid, side=side, turn=r['turn'],
                                                 kind=r['decision_kind'], issues=[list(map(str, i)) for i in issues]))
                    tr.chose(r.get('label'))
            except Exception as exc:
                errors.append(dict(source=source, replay=rid, side=side, error='%s: %s' % (type(exc).__name__, exc)))
    report = dict(games=len(picks), decisions=decisions, mismatched=mismatched, fields=dict(fields),
                  errors=errors, examples=examples)
    text = json.dumps(report, indent=1)
    if args.out:
        open(args.out, 'w').write(text)
    print(text[:4000])


if __name__ == '__main__':
    main()
