"""EP-224 / EX-151 stage 2: the engine judge against what really happened.

`battles(out)`: every model-side move of the nine fail-survey runs (EP-221..223). Each turn decision whose choice was
a move is judged from its logged input (the serving `ImitationInput`), then compared with the protocol: a move
`failed` when a `-fail` / `-immune` / `-block` follows it before the next move or turn boundary
(`comparison._failed_after`, the battle reports' definition), and also counts as not working when the foe absorbed it
(Ability heal / boost) or bounced it (Magic Bounce). The same decisions are labelled by the rules
(`effect_knowledge.option_outcomes` on the raw input, the fail survey's `marked`, and the v7 renderer's marks).
`replays(out)`: every EX-071 train / validation / test row: how many rows the judge marks and how often the human
chose a marked option.
"""
from __future__ import annotations
import collections
import json
from multiprocessing import Pool
from pathlib import Path
import re
import sys
import time

from integration.pokechamp.imitation.schema import ImitationInput

from . import judge as J

BASE = Path('/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training')
RUNS = ('EX-143', 'EX-144', 'EX-145', 'EX-147', 'EX-148', 'EX-150', 'EX-147-h2h', 'EX-148-h2h-v6st', 'EX-148-h2h-v6ht')
SURVEY = Path('/workspace/project_context/exec-plans/evidence/ep223/fail-survey/fail-survey.json')
ABSORB = re.compile(r'\[from\] ability: (Volt Absorb|Lightning Rod|Motor Drive|Water Absorb|Storm Drain|Dry Skin|'
                    r'Flash Fire|Well-Baked Body|Sap Sipper|Earth Eater|Wind Rider)')
ABSORB_START = re.compile(r'^\|-(start|immune|heal|boost)\|p[12]a: [^|]*\|.*ability: (Volt Absorb|Lightning Rod|Motor Drive|'
                          r'Water Absorb|Storm Drain|Dry Skin|Flash Fire|Well-Baked Body|Sap Sipper|Earth Eater|Wind Rider)')
PROTECTED = re.compile(r"^\|-activate\|p[12]a: [^|]*\|(move: )?(Protect|Detect|King's Shield|Spiky Shield|Baneful Bunker|"
                       r"Obstruct|Silk Trap|Burning Bulwark)")
mid = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())

_judge = None


def _init():
    global _judge
    _judge = J.Judge()


def _rules(body):
    from integration.laya_imitation.effect_knowledge import option_outcomes
    from integration.laya_imitation import features_v4, features_v5, features_v7
    raw = option_outcomes(dict(input=body))
    value = ImitationInput.from_body(body)
    v7 = {}
    try:
        resolved, view = features_v5.resolved(value)
        v7 = dict(features_v4.known_failures(resolved))
        v7.update(features_v7.typechange_failures(view, value.action_ids))
    except ValueError:
        pass
    return raw, v7


def _actual(lines, i, side):
    """What followed the model's `|move|` at line i."""
    from integration.laya_imitation.comparison import _failed_after
    failed = _failed_after(lines, i)
    j = i + 1
    while j < len(lines) and not lines[j].startswith(('|move|', '|turn|', '|upkeep')):
        j += 1
    window = lines[i + 1:j]
    foe = 'p2' if side == 'p1' else 'p1'
    bounced = j < len(lines) and lines[j].startswith('|move|' + foe) and 'Magic Bounce' in lines[j]
    absorbed = any((ABSORB.search(x) or ABSORB_START.match(x)) and x.split('|')[2].startswith(foe)
                   for x in window if len(x.split('|')) > 2)
    why = next((x for x in window if x.startswith(('|-fail|', '|-immune|', '|-block|'))), '')
    hit = any(x.startswith(('|-damage|' + foe, '|-crit|', '|-supereffective|', '|-resisted|')) and '[from]' not in x
              for x in window)
    protected = any(PROTECTED.match(x) and x.split('|')[2].startswith(foe) for x in window)
    return dict(failed=failed, bounced=bounced, absorbed=absorbed, why=why[:120], hit=hit, protected=protected,
                miss=any(x.startswith('|-miss|' + side) for x in window))


def judge_game(job):
    run, game = job
    g = BASE / run / 'games' / game
    o = json.loads((g / 'outcome.json').read_text())
    side = o['model_side']
    foe_side = 'p2' if side == 'p1' else 'p1'
    events = [json.loads(line) for line in open(g / 'events.jsonl')]
    lines = [x for e in events if e['type'] == 'protocol' for x in e['protocol'].split('\n')]
    inputs = {e['decision']: e for e in events if e['type'] == 'input'}
    decisions = {}
    for s in events:
        if s['type'] == 'selection' and s['decision'] in inputs:
            body = inputs[s['decision']]['body']
            snap = json.loads(body['state'])['snapshot']
            if snap['decision_kind'] == 'turn_action':
                decisions[snap['turn']] = (s, body)
    rows, turn, turn_start = [], 0, 0
    for i, line in enumerate(lines):
        p = line.split('|')
        if len(p) > 2 and p[1] == 'turn':
            turn, turn_start = int(p[2]), i
            continue
        if not (len(p) > 3 and p[1] == 'move' and p[2].startswith(side) and '[from]' not in line):
            continue
        move = mid(p[3])
        d = decisions.get(turn)
        if d is None or not d[0]['choice'].startswith('move:%s:' % move):
            rows.append(dict(run=run, game=game, turn=turn, move=move, matched=False, **_actual(lines, i, side)))
            continue
        s, body = d
        before = lines[turn_start:i]
        foe_switched = any(len(x.split('|')) > 2 and x.split('|')[1] in ('switch', 'drag') and
                           x.split('|')[2].startswith(foe_side) for x in before)
        foe_tera = any(x.startswith('|-terastallize|' + foe_side) for x in before)
        foe_moves = [x.split('|')[3] for x in before if x.startswith('|move|' + foe_side) and len(x.split('|')) > 3]
        value = ImitationInput.from_body(body)
        t0 = time.perf_counter()
        try:
            labels, detail = J.option_outcomes(value, _judge)
        except Exception as exc:     # a worker crash is a defect to report, not a label
            labels, detail = {}, dict(reproduced=False, error='python:' + repr(exc)[:200], options={})
        seconds = time.perf_counter() - t0
        raw, v7 = _rules(body)
        chosen = engine = detail['options'].get(s['choice'], {})
        rows.append(dict(
            run=run, game=game, turn=turn, move=move, matched=True, choice=s['choice'], decision=s['decision'],
            p=(s.get('probabilities') or {}).get(s['choice']), foe_switched=foe_switched, foe_tera=foe_tera,
            foe_moves=foe_moves, seconds=round(seconds, 4), reproduced=detail.get('reproduced'),
            error=detail.get('error'), label=labels.get(s['choice']), engine=engine.get('label'),
            engine_error=chosen.get('error'), cases=engine.get('cases'),
            rule=raw.get(s['choice']), rule_v7=v7.get(s['choice']),
            marks=dict(engine=labels, rule=raw, rule_v7=v7), options=len(value.action_ids),
            **_actual(lines, i, side)))
    return rows


def battles(out, workers=96, limit=None):
    jobs = []
    for run in RUNS:
        games = BASE / run / 'games'
        for g in sorted(games.iterdir()):
            if (g / 'events.jsonl').exists() and (g / 'outcome.json').exists():
                jobs.append((run, g.name))
    jobs = jobs[:limit] if limit else jobs
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    n = 0
    with Pool(workers, initializer=_init) as pool, open(out, 'w') as f:
        for rows in pool.imap_unordered(judge_game, jobs, chunksize=1):
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
            n += 1
            if n % 200 == 0:
                print('games %d/%d %.0fs' % (n, len(jobs), time.time() - started), flush=True)
    print('done %d games %.0fs' % (n, time.time() - started))


# ----------------------------------------------------------------------------- summary

FAILING = set(J.FAILING)


def survey_classes():
    # `classify.py` runs on import; take its definitions only (the fail survey's own `cls`, unchanged).
    src = (SURVEY.parent / 'classify.py').read_text()
    scope = {'collections': collections}
    exec(src[src.index('PROTECT = '):src.index('c = collections.Counter')], scope)
    cls = scope['cls']
    d = json.loads(SURVEY.read_text())
    return {(u['run'], u['game'], u['turn'], u['move']): cls(u) for u in d['unmarked']}, d['totals']


def did_not_work(r):
    """Failed, or did nothing to the target: absorbed, bounced, missed (a miss is checked before most failures) or
    blocked by the foe's Protect (the foe's choice, like a switch)."""
    return r['failed'] or r['bounced'] or r['absorbed'] or r['miss'] or r.get('protected', False)


def summarize(rows_path):
    rows = [json.loads(line) for line in open(rows_path)]
    matched = [r for r in rows if r['matched']]
    classes, totals = survey_classes()
    out = dict(moves=len(rows), matched=len(matched), unmatched=len(rows) - len(matched),
               failed=sum(r['failed'] for r in rows), survey_totals=totals)
    marked = [r for r in matched if r['label'] in FAILING]
    clean = [r for r in marked if not r['foe_switched']]
    out['precision'] = dict(
        marked=len(marked), foe_switched_excluded=len(marked) - len(clean),
        strict_failed=sum(r['failed'] for r in clean), not_worked=sum(did_not_work(r) for r in clean),
        strict=sum(r['failed'] for r in clean) / len(clean) if clean else None,
        extended=sum(did_not_work(r) for r in clean) / len(clean) if clean else None,
        foe_tera_same_turn=sum(r['foe_tera'] for r in clean),
        with_switch=sum(did_not_work(r) for r in marked) / len(marked) if marked else None)
    likely = [r for r in matched if r['label'] == J.LIKELY and not r['foe_switched']]
    out['likely'] = dict(marked=len(likely), failed=sum(r['failed'] for r in likely))
    wrong = [r for r in clean if not did_not_work(r)]
    out['wrong'] = collections.Counter('%s/%s' % (r['move'], r['engine']) for r in wrong).most_common(60)
    out['precision']['missed'] = sum(r['miss'] and not r['failed'] for r in clean)
    out['precision']['protected'] = sum(r.get('protected', False) and not r['failed'] and not r['miss'] for r in clean)
    # Coverage of the fail-survey groups.
    group = collections.Counter()
    caught = collections.Counter()
    for r in matched:
        if not r['failed']:
            continue
        key = (r['run'], r['game'], r['turn'], r['move'])
        if r['rule'] in FAILING:
            g = 'marked (rules)'
        else:
            c = classes.get(key, '?')
            g = c
        group[g] += 1
        caught[g] += r['label'] in FAILING
    gap = [k for k in group if k.startswith('D ')]
    out['coverage'] = {k: dict(failed=group[k], engine=caught[k]) for k in sorted(group)}
    out['coverage_groups'] = dict(
        rule_gap=dict(failed=sum(group[k] for k in gap), engine=sum(caught[k] for k in gap)),
        marked=dict(failed=group['marked (rules)'], engine=caught['marked (rules)']),
        typechange=dict(failed=sum(group[k] for k in group if k.startswith('F ')),
                        engine=sum(caught[k] for k in group if k.startswith('F '))))
    # Disagreements with the rules on the chosen option.
    dis = collections.Counter()
    for r in matched:
        e, ru = r['label'] in FAILING, r['rule'] in FAILING
        if e == ru:
            continue
        who = 'engine marks, rules do not' if e else 'rules mark, engine does not'
        dis[(who, 'did not work' if did_not_work(r) else 'worked', 'foe switched' if r['foe_switched'] else '-')] += 1
    out['disagreements'] = [dict(who=k[0], actual=k[1], foe=k[2], n=v) for k, v in sorted(dis.items())]
    def outcome(r):
        for key in ('failed', 'miss', 'absorbed', 'bounced', 'protected'):
            if r.get(key):
                return key
        return 'worked (foe Terastallized first)' if r['foe_tera'] else 'worked'
    out['by_label'] = collections.Counter('%s -> %s' % (r['label'], outcome(r)) for r in clean).most_common()
    by_move = collections.Counter()
    for r in matched:
        e, ru = r['label'] in FAILING, r['rule'] in FAILING
        if e != ru and not r['foe_switched']:
            by_move[('engine only' if e else 'rules only', r['move'],
                     'did not work' if did_not_work(r) else 'worked')] += 1
    out['disagreements_by_move'] = [dict(who=k[0], move=k[1], actual=k[2], n=v) for k, v in by_move.most_common()]
    secs = sorted(r['seconds'] for r in matched)
    q = lambda f: secs[min(len(secs) - 1, int(f * len(secs)))] if secs else None
    out['latency'] = dict(p50=q(0.5), p90=q(0.9), p99=q(0.99), max=secs[-1] if secs else None)
    out['reproduced'] = dict(decisions=len(matched), not_reproduced=sum(r['reproduced'] is False for r in matched),
                             errors=collections.Counter(str(r['error'])[:60] for r in matched if r['error']).most_common(10),
                             option_errors=collections.Counter(str(r['engine_error'])[:60] for r in matched
                                                               if r['engine'] == 'unknown').most_common(15))
    out['marks_per_decision'] = dict(
        engine=sum(len(r['marks']['engine']) for r in matched) / max(1, len(matched)),
        rule=sum(sum(v in FAILING for v in r['marks']['rule'].values()) for r in matched) / max(1, len(matched)))
    return out


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'battles':
        battles(sys.argv[2], limit=int(sys.argv[3]) if len(sys.argv) > 3 else None)
    elif cmd == 'summary':
        print(json.dumps(summarize(sys.argv[2]), ensure_ascii=False, indent=1))
