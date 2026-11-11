"""laya-compact-v10 (D-204): every v1-v9 module but `longhist`, plus lock and strategy facts, for a 2,048-token input.

`compute(value, calc, judged)` gathers the facts; `render(value, facts)` is a pure function of them. On top of
`compact_v7.render` with all v7 modules (v1-v6s text, `opp set`, `opp watch`, bench `likely`):
- failure marks are the engine judge's (`render_v8.marks`) plus `; likely fails` (v8l); foe spreads are v9's;
- every switch option whose worst plausible hit qualifies gets the full `; risk a-b% <move>` (v9 rule, no budget
  trimming), and `opp threat:` shows the worst case and the likely attack (#26);
- `first p` on the speed line (#11), lock marks (#27-32), and the strategy lines and marks (#33-41).
Rows that do not fit the v10 budgets are excluded by the dataset builder; nothing is trimmed here.
"""
from __future__ import annotations
import copy
import json

from integration.laya_engine import judge as J
from integration.laya_engine import render_v8, render_v8l
from integration.laya_imitation import compact_v7, features_v5, features_v7
from integration.laya_threat import render_v9, spreads, threat

from . import lock, strategy

MODULES = compact_v7.MODULES + ('judge', 'likely', 'spreads', 'threat', 'firstp', 'lock', 'strategy')
VERSION = 'laya-compact-v10[%s]' % ','.join(MODULES)


def _p(value):
    return '1' if value >= 0.995 else ('%.2f' % value)[1:]


def _pct(value):
    return '%d' % round(value)


def _hits(n):
    return '9+' if n > 9 else str(n)


def _hp(value):
    return '%d%%' % round(value)


def compute(value, calc, judged, ext=None):
    """Facts for `render`. `value`: the D-195 input; `ext`: the same input with `early_history` (lock and PP)."""
    with spreads.patched():
        facts = features_v5.compute(value, calc)
        v7 = features_v7.compute(value)
        risk = threat.compute(value, calc)
        shown, kept = render_v8.marks(value, facts, judged, v7)
        strat = strategy.compute(ext or value, facts, risk, set(shown), calc)
    return dict(facts=facts, v7=v7, risk=risk, judged=judged, shown=shown, kept=kept,
                likely=render_v8l.likely(value, judged), lock=lock.compute(ext or value), strategy=strat)


def _threat_line(worst, likely):
    parts = []
    if worst is not None and worst['max'] >= render_v9.ACTIVE_FLOOR:
        notes = []
        if not worst['item_known'] and worst['item']:
            notes.append(worst['item'] + '?')
        if worst['tera'] and not worst['terastallized']:
            notes.append('tera ' + worst['tera'])
        parts.append('worst %s %s-%s%% to me%s' % (worst['move'], _pct(worst['min']), _pct(worst['max']),
                                                  ' (%s)' % ', '.join(notes) if notes else ''))
    if likely is not None and likely['max'] >= render_v9.ACTIVE_FLOOR:
        parts.append('likely %s p%s %s-%s%%' % (likely['move'], _p(likely['p']), _pct(likely['min']),
                                               _pct(likely['max'])))
    return 'opp threat: ' + ' | '.join(parts) if parts else None


def _board_line(s, view):
    b = s['board']
    text = 'board: me %d alive %s | opp %d alive %s' % (b['me'], _hp(b['me_hp']), b['opp'], _hp(b['opp_hp']))
    mine, theirs = s['wincon']
    if mine or theirs:
        own = {m['slot']: m['species'] for m in view['own_team']}
        opp = {m['slot']: m['species'] for m in view['opponent_team']}
        text += ' | wincon me %s | opp %s' % (', '.join(own[x] for x in mine) or 'none',
                                              ', '.join(opp[y] for y in theirs) or 'none')
    return text


def _hazard_line(h):
    if h is None:
        return None
    parts = []
    if h['entry']:
        parts.append('opp entry ' + ', '.join('%s %s%%%s' % (sp, _pct(pct), ' (boots?)' if boots else '')
                                              for sp, pct, boots in h['entry']))
    if h['opp_remover']:
        parts.append('opp remover ' + ', '.join('%s %s%s' % (sp, mv, '' if p is None else ' ' + _p(p))
                                                for sp, mv, p in h['opp_remover']))
    if h['my_remover']:
        parts.append('my remover ' + ', '.join('%s %s' % (sp, mv) for sp, mv in h['my_remover']))
    return 'hazards: ' + ' | '.join(parts) if parts else None


def _duel_line(d):
    if d is None:
        return None
    return 'duel: me %s hits (%s) vs opp %s hits (%s), %s first -> %s' % (
        _hits(d['me_hits']), d['me_move'], _hits(d['opp_hits']), d['opp_move'], 'me' if d['me_first'] else 'opp',
        d['result'])


def _heal_line(items):
    if not items:
        return None
    parts = []
    for kind, name, p, left in items:
        if p == 'seen':
            parts.append('%s (seen%s)' % (name, '' if left is None else ', %d left?' % left))
        else:
            parts.append('%s %s' % (name, _p(p)))
    return 'opp heals: ' + ', '.join(parts)


def _locked(found):
    move, cause = found
    return ' | locked %s (%s)' % (move, cause)


def _own_pp(line, me):
    """`moves a b` on the ME line -> `roost(3/8)` for moves at half PP or less."""
    head, sep, rest = line.partition(' | moves ')
    if not sep:
        return line
    names, tail_sep, tail = rest.partition(' | ')
    pp = {m['id']: m for m in me['moves']}
    shown = []
    for name in names.split(' '):
        m = pp.get(name)
        low = m is not None and m.get('pp') is not None and m.get('max_pp') and m['pp'] * 2 <= m['max_pp']
        shown.append('%s(%d/%d)' % (name, m['pp'], m['max_pp']) if low else name)
    return head + sep + ' '.join(shown) + tail_sep + tail


def _opp_pp(line, foe, used):
    """`seen a b` on the OPP line -> `roost(5/8 used)` for moves with half their max PP or more used."""
    head, sep, rest = line.partition(' | seen ')
    if not sep:
        return line
    names, tail_sep, tail = rest.partition(' | ')
    counts = used.get(foe['species'], {})
    from .history import max_pp
    shown = []
    for name in names.split(' '):
        top, n = max_pp(name), counts.get(name, 0)
        shown.append('%s(%d/%d used)' % (name, n, top) if top and n * 2 >= top else name)
    return head + sep + ' '.join(shown) + tail_sep + tail


def render(value, facts):
    """`ImitationInput` + `compute` facts -> (state text, laya choice question)."""
    v5 = copy.deepcopy(facts['facts'])
    v5['v4']['fails'] = facts['shown']
    state, question = compact_v7.render(value, compact_v7.MODULES, v5, dict(facts['v7'], fails_tc={}))
    snapshot = json.loads(value.body['state'])['snapshot']
    _, view = features_v5.resolved(value)
    own = {m['slot']: m for m in view['own_team']}
    opp = {m['slot']: m for m in view['opponent_team']}
    me = own.get(view['own_active_slot']) if view['own_active_slot'] else None
    foe = opp.get(view['opponent_active_slot']) if view['opponent_active_slot'] else None
    s, lk, risk = facts['strategy'], facts['lock'], facts['risk']
    lines = state.split('\n')

    # state lines
    for i, line in enumerate(lines):
        if line.startswith('speed: ') and s['first'] is not None:
            lines[i] = line + ' | first p%s' % _p(s['first'])
        elif line.startswith('ME ') and me is not None:
            line = _own_pp(line, me)
            lines[i] = line + (_locked(lk['me']) if lk['me'] else '')
        elif line.startswith('OPP ') and foe is not None:
            line = _opp_pp(line, foe, s['pp_used'])
            if lk['opp']:
                line += _locked(lk['opp'])
            elif lk['opp_likely']:
                line += ' | locked? %s p%s' % (lk['opp_likely'][0], _p(lk['opp_likely'][1]))
            lines[i] = line
        elif line.startswith('opp team: '):
            team = [m for sl, m in sorted(opp.items()) if m is not foe]
            segments = line[len('opp team: '):].split(' || ')
            if len(segments) != len(team):
                raise ValueError('team segments do not match the snapshot')
            for k, mon in enumerate(team):
                xs = s['answers'].get(mon['slot'])
                if xs is not None and mon['status'] != 'fnt':
                    c = s['matchup']['%d-%d' % (xs, mon['slot'])]
                    segments[k] += ' | answer %s (out %s%%, takes %s%%%s)' % (
                        own[xs]['species'], _pct(c['out']), _pct(c['takes']), ', ' + c['speed'] if c['speed'] else '')
            lines[i] = 'opp team: ' + ' || '.join(segments)
    added = [x for x in (_board_line(s, view), _hazard_line(s['hazards'])) if x]
    lines[2:2] = added
    duel = _duel_line(s['duel'])
    if duel:
        at = next((i for i, x in enumerate(lines) if x.startswith('speed: ')), None)
        at = at + 1 if at is not None else 2 + len(added)
        lines.insert(at, duel)
    at = next((i for i, x in enumerate(lines) if x.startswith('OPP ')), None)
    if at is not None:
        end = at + 1
        while end < len(lines) and lines[end].startswith(('opp set: ', 'opp watch: ')):
            end += 1
        extra = [x for x in (_heal_line(s['heals']),
                             _threat_line(risk['active'], s['likely']) if snapshot['decision_kind'] == 'turn_action'
                             else None) if x]
        lines[end:end] = extra

    # option marks
    criteria = {}
    likely = set(facts['likely'])
    for action_id, text in question['criteria'].items():
        if action_id in likely and '; fails' not in text and '; bounced' not in text:
            text += render_v8l.LIKELY_TEXT
        if action_id in lk['options']:
            text += '; ' + lk['options'][action_id]
        if action_id in s['walls']:
            species, wall = s['walls'][action_id]
            text += '; opp wall %s %s%%' % (species, _pct(wall))
        if action_id in s['tera']:
            move, lo, hi = s['tera'][action_id]
            text += '; tera takes %s %s-%s%%' % (move, _pct(lo), _pct(hi))
        if action_id.startswith('switch:'):
            entry = risk['switch'].get(action_id)
            if render_v9.shown_risk(entry, facts['facts']['damage'].get(action_id)):
                text += '; risk %s-%s%% %s' % (_pct(entry['min']), _pct(entry['max']), entry['move'])
        criteria[action_id] = text
    return '\n'.join(lines), dict(question, criteria=criteria)


def judged_of(value, judge):
    return render_v8.judged_of(value, judge)


def version():
    return dict(render=VERSION, judge=J.identity(), v7=compact_v7.version(compact_v7.MODULES),
                thresholds=dict(likely_lock=lock.LIKELY_FLOOR, answer_hp=strategy.ANSWER_HP,
                                wincon_shown=strategy.WINCON_SHOWN, heal_floor=strategy.HEAL_FLOOR,
                                wall_ratio=strategy.WALL_RATIO, entry_shown=strategy.ENTRY_SHOWN,
                                remover_floor=strategy.REMOVER_FLOOR, active_floor=render_v9.ACTIVE_FLOOR,
                                switch_floor=render_v9.SWITCH_FLOOR, gap=render_v9.GAP))
