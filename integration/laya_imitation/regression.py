"""NHJ-20261028 regression set: fixed live decisions of laya-play v1.1 (`laya-v2t-fix`) against the human player NHJ.

Each case is one recorded `/evaluate` input from `data/NHJ-20261028` with action sets labelled from NHJ's feedback and
the 2026-10-28 game analysis: `bad` actions cannot work in that state (immune, no-op, a Tera that turns a known resisted
move super effective), `preferred` actions are the expert line. Groups:

- `immune` (rule): Ting-Lu vs Air Balloon + Good as Gold Gholdengo, battle 34 turns 15-21. Earthquake, Whirlwind and Taunt
  cannot work; switching is preferred. Gholdengo's only legal Ability is Good as Gold, so turn 15 already counts.
- `noop` (rule): battle 38 turn 46, Trick between two known Leftovers holders.
- `tera` (rule): battle 38 turn 60, Tera Steel Clodsire against a Zamazenta with a revealed Body Press.
- `wall` (judgement): battle 38, Unaware Clodsire against Iron Defense Zamazenta; Toxic is the line NHJ named.
- `stuck` (judgement): battle 39, Ninetales-Alola and Kyurem repeating into a Slack Off Slowking-Galar; switch (or Encore
  once Slack Off is revealed) is preferred.
- `control`: decisions v1.1 got right (Aurora Veil on the Dragapult U-turn, Tera Fairy Dazzling Gleam, Toxic on the
  Zamazenta switch-in) that a new model should keep.

Scoring is report only: per case the probability mass on `bad` / `preferred` and the class of the argmax, next to the
recorded v1.1 response. It is not a battle gate. Any server with the EX-071 `/health`·`/evaluate` contract can be scored.
"""
from __future__ import annotations
from pathlib import Path
import json

from . import config as c
from .storage import atomic, digest, read

SOURCE = c.ROOT / 'data/NHJ-20261028/NHJ-20261028'
FIXTURE = Path(__file__).with_name('tests') / 'nhj20261028_regression.json'
SWITCH = ('switch:',)


def _moves(*names, tera=True):
    return tuple('move:%s:%s' % (n, k) for n in names for k in (('normal', 'tera') if tera else ('normal',)))


# (case id, battle, decision, turn, group, source, bad prefixes, preferred prefixes, note)
CASES = [
    *[('b34-t%d-tinglu' % t, 'battle-gen9ou-34', d, t, 'immune', 'NHJ-1', _moves('earthquake', 'whirlwind', 'taunt'),
       SWITCH, 'Ting-Lu vs Gholdengo (Air Balloon held, Good as Gold): only a switch or Stealth Rock does anything')
      for t, d in ((15, 'LayaBot-35-158'), (16, 'LayaBot-37-168'), (17, 'LayaBot-39-178'), (18, 'LayaBot-41-188'),
                   (19, 'LayaBot-43-198'), (20, 'LayaBot-45-208'), (21, 'LayaBot-47-218'))],
    ('b38-t46-trick', 'battle-gen9ou-38', 'LayaBot-121-540', 46, 'noop', 'NHJ-2', _moves('trick'),
     _moves('makeitrain', 'shadowball', tera=False), 'Gholdengo Trick: both sides hold Leftovers (Zamazenta revealed t32)'),
    ('b38-t60-tera', 'battle-gen9ou-38', 'LayaBot-153-700', 60, 'tera', 'analysis', (':tera',),
     _moves('toxic', tera=False), 'Clodsire Tera Steel turns the revealed, resisted Body Press super effective'),
    ('b38-t45-clodsire', 'battle-gen9ou-38', 'LayaBot-119-530', 45, 'wall', 'NHJ-2', (),
     _moves('toxic', tera=False), 'Unaware Clodsire stays in on Zamazenta and Toxics (v1.1 switched to Gholdengo)'),
    *[('b38-t%d-clodsire' % t, 'battle-gen9ou-38', d, t, 'wall', 'NHJ-2', (), _moves('toxic', tera=False),
       'Unaware Clodsire vs unstatused Iron Defense Zamazenta: Toxic, not Earthquake')
      for t, d in ((51, 'LayaBot-131-590'), (52, 'LayaBot-133-600'), (53, 'LayaBot-135-610'), (54, 'LayaBot-137-620'),
                   (56, 'LayaBot-141-640'), (58, 'LayaBot-147-670'))],
    *[('b39-t%d-ninetales' % t, 'battle-gen9ou-39', d, t, 'stuck', 'NHJ-3', (), SWITCH + _moves('encore', tera=False),
       'Ninetales-Alola Blizzard into Slack Off Slowking-Galar while Aurora Veil and snow run out')
      for t, d in ((4, 'LayaBot-13-48'), (5, 'LayaBot-15-58'), (6, 'LayaBot-17-68'), (7, 'LayaBot-19-78'),
                   (8, 'LayaBot-21-88'))],
    *[('b39-t%d-kyurem' % t, 'battle-gen9ou-39', d, t, 'stuck', 'analysis', (), SWITCH,
       'Kyurem Ice Beam into Slack Off Slowking-Galar for the sixth time')
      for t, d in ((12, 'LayaBot-31-138'), (13, 'LayaBot-33-148'), (14, 'LayaBot-35-158'))],
    ('b39-t1-veil', 'battle-gen9ou-39', 'LayaBot-5-16', 1, 'control', 'NHJ-3', (), _moves('auroraveil', tera=False),
     'Aurora Veil while the Dragapult lead U-turns out'),
    ('b39-t28-tera', 'battle-gen9ou-39', 'LayaBot-83-350', 28, 'control', 'analysis', (), ('move:dazzlinggleam:tera',),
     'Gholdengo Tera Fairy Dazzling Gleam into Zamazenta'),
    ('b38-t43-toxic', 'battle-gen9ou-38', 'LayaBot-113-508', 43, 'control', 'NHJ-2', (), _moves('toxic', tera=False),
     'Clodsire Toxic on Zamazenta (NHJ read it with Slowking-Galar)'),
]
GROUPS = ('immune', 'noop', 'tera', 'wall', 'stuck', 'control')


def _match(ids, prefixes):
    return [k for k in ids if any(k.startswith(p) or (p.startswith(':') and k.endswith(p)) for p in prefixes)]


def _events(path, decisions):
    found = {}
    with open(path) as f:
        for line in f:
            e = json.loads(line)
            if e.get('decision') in decisions and e['type'] in ('input', 'response'):
                found.setdefault(e['decision'], {})[e['type']] = e
    return found


def build(source=SOURCE, out=FIXTURE):
    """Extract and label the cases from the exported games; refuses to overwrite and checks every recorded identity."""
    from integration.pokechamp.imitation.schema import ImitationInput
    manifest = read(Path(source) / 'manifest.json')
    games = {g['battle_id']: g for g in manifest['games']}
    rows = []
    for case, game, decision, turn, group, origin, bad, preferred, note in CASES:
        events = _events(Path(source) / game / 'events.jsonl', {decision})[decision]
        body, response = events['input']['body'], events['response']['body']
        value = ImitationInput.from_body(body)
        snapshot = json.loads(body['state'])['snapshot']
        ids = list(value.action_ids)
        if snapshot['turn'] != turn or snapshot['decision_kind'] != 'turn_action':
            raise ValueError('%s: recorded turn %s/%s' % (case, snapshot['turn'], snapshot['decision_kind']))
        if response['input_sha256'] != value.sha256 or response['action_ids'] != ids:
            raise ValueError('%s: recorded response does not belong to this input' % case)
        rows.append(dict(
            id=case, battle=game, decision=decision, turn=turn, group=group, source=origin, note=note,
            own=next(p['species'] for p in snapshot['own_team'] if p['slot'] == snapshot['own_active_slot']),
            foe=next(p['species'] for p in snapshot['opponent_team'] if p['slot'] == snapshot['opponent_active_slot']),
            bad=_match(ids, bad), preferred=_match(ids, preferred), action_ids=ids, input_sha256=value.sha256,
            input_json=value.body_json,   # a string: the stored JSON is key-sorted, the criteria order is not
            baseline=dict(model=response['model'], checkpoint_sha256=response['checkpoint_sha256'],
                          choice=response['choice'], probabilities=response['probabilities'])))
        if (bad and not rows[-1]['bad']) or not rows[-1]['preferred']:
            raise ValueError('%s: an action label matches no legal action' % case)
    doc = dict(name='nhj-20261028-regression', source=str(source), manifest_created_at=manifest['created_at_kst'],
               games={g: games[g]['source_events_sha256'] for g in sorted({r['battle'] for r in rows})},
               groups=list(GROUPS), cases=rows)
    doc['digest'] = digest(rows)
    atomic(out, doc, immutable=True)
    return doc


def case_score(case, probabilities):
    """Mass on `bad` / `preferred` and the argmax class (first maximum in action order, like the player)."""
    ids = case['action_ids']
    top = max(ids, key=lambda k: probabilities[k])
    return dict(choice=top, bad_mass=sum(probabilities[k] for k in case['bad']),
                preferred_mass=sum(probabilities[k] for k in case['preferred']),
                top='bad' if top in case['bad'] else 'preferred' if top in case['preferred'] else 'other')


def summarize(rows, key):
    """Per group and overall: cases, mean bad / preferred mass, argmax class counts for scores under `key`."""
    out = {}
    for group in (*GROUPS, 'all'):
        part = [r[key] for r in rows if group in ('all', r['group'])]
        if part:
            out[group] = dict(cases=len(part), bad_mass=sum(p['bad_mass'] for p in part) / len(part),
                              preferred_mass=sum(p['preferred_mass'] for p in part) / len(part),
                              top_bad=sum(p['top'] == 'bad' for p in part),
                              top_preferred=sum(p['top'] == 'preferred' for p in part))
    return out


def baseline(doc):
    rows = [dict(id=x['id'], group=x['group'], v11=case_score(x, x['baseline']['probabilities'])) for x in doc['cases']]
    return rows, summarize(rows, 'v11')


def score(endpoint, out, fixture=FIXTURE):
    """Score every case on a running `/evaluate` server (one request each) next to the recorded v1.1 response."""
    from integration.pokechamp.imitation.player import http_json, validate_response
    from integration.pokechamp.imitation.schema import ImitationInput
    doc = read(fixture)
    if digest(doc['cases']) != doc['digest']:
        raise ValueError('regression fixture digest mismatch')
    health = http_json(endpoint, '/health', timeout=30)
    rows, _ = baseline(doc)
    for row, case in zip(rows, doc['cases']):
        value = ImitationInput(case['input_json'])
        if value.sha256 != case['input_sha256']:
            raise ValueError('%s: input digest mismatch' % case['id'])
        response = http_json(endpoint, '/evaluate', body=dict(model=health['model'], input=value.body), timeout=600)
        validate_response(response, value, model=health['model'], checkpoint_sha256=health['checkpoint_sha256'])
        row['model'] = case_score(case, response['probabilities'])
        if 'model_probabilities' in response:   # EX-140 decision rules also return the policy's own distribution
            row['policy'] = case_score(case, response['model_probabilities'])
        row['max_abs_diff_v11'] = max(abs(response['probabilities'][k] - case['baseline']['probabilities'][k])
                                      for k in case['action_ids'])
    result = dict(fixture=str(fixture), fixture_digest=doc['digest'], endpoint=endpoint,
                  model=health['model'], checkpoint_sha256=health['checkpoint_sha256'],
                  render=health.get('render'), v11=summarize(rows, 'v11'), candidate=summarize(rows, 'model'),
                  identical_to_v11=sum(r['max_abs_diff_v11'] <= 1e-6 for r in rows), rows=rows)
    if any('policy' in r for r in rows):
        result['candidate_policy'] = summarize(rows, 'policy')
    atomic(out, result, immutable=True)
    return result


def table(result):
    """Korean console table: v1.1 vs candidate per group."""
    lines = ['%s (%s) · v1.1과 확률이 같은 사례 %d/%d' % (result['model'], result['checkpoint_sha256'][:12],
                                                     result['identical_to_v11'], len(result['rows'])),
             '%-8s %4s  %-23s  %-23s' % ('group', 'n', 'bad mass v1.1→new', 'preferred mass v1.1→new')]
    for group, new in result['candidate'].items():
        old = result['v11'][group]
        lines.append('%-8s %4d  %.3f→%.3f (top %d→%d)  %.3f→%.3f (top %d→%d)' % (
            group, new['cases'], old['bad_mass'], new['bad_mass'], old['top_bad'], new['top_bad'],
            old['preferred_mass'], new['preferred_mass'], old['top_preferred'], new['top_preferred']))
    return '\n'.join(lines)
