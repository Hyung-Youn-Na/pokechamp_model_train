"""EX-169: the ladder games of the EX-169 source snapshot as decision rows.

A game folder holds laya-play's `events.jsonl` (protocol, model input, probabilities, command) and `result.json`.
`Game` flattens the protocol into lines addressed by (protocol `sequence`, line index), the address an input's
`boundary` uses, so the lines between two decisions are what happened after the first one.

The serving configuration changed twice on 2026-11-16 (service restarts, seen as the local bot folders
`…-blimAI-…` created at the same second): the usage extension from 05:43:30Z and the fixed engine judge from
06:34:37Z. `era` gives the configuration a game was played with; `render` re-renders with it and `score` checks the
re-rendered input against the logged probabilities.
"""
from __future__ import annotations
import json
import re

from .. import paths

ERA_EXT = '20261116-054330'
ERA_FIX = '20261116-063437'
PROTECT = ('Protect', 'Detect', "King's Shield", 'Spiky Shield', 'Baneful Bunker', 'Silk Trap', 'Burning Bulwark',
           'Obstruct', 'Max Guard')
SETUP = ('Swords Dance', 'Dragon Dance', 'Nasty Plot', 'Calm Mind', 'Quiver Dance', 'Shell Smash', 'Bulk Up',
         'Iron Defense', 'Agility', 'Shift Gear', 'Coil', 'Curse', 'Tidy Up', 'Victory Dance', 'Belly Drum',
         'Trailblaze', 'Torch Song', 'Flame Charge', 'Power-Up Punch', 'Growth', 'Work Up', 'Cosmic Power',
         'Amnesia', 'Stockpile', 'No Retreat', 'Clangorous Soul', 'Fillet Away', 'Rock Polish', 'Autotomize')


def tid(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


def era(name):
    stamp = name[:15]
    return dict(ext=stamp >= ERA_EXT, fix=stamp >= ERA_FIX)


def names():
    """Game folders of the bot account with at least one decision, oldest first."""
    out = []
    for path in sorted(paths.GAMES.iterdir()):
        if paths.BOT in path.name and (path / 'events.jsonl').exists():
            out.append(path.name)
    return out


class Game:
    def __init__(self, name, root=None, bot=None):
        """`root` / `bot`: another games folder and its bot user (the local EX-170 games); default the ladder games."""
        self.name = name
        folder = (root or paths.GAMES) / name
        self.events = [json.loads(line) for line in open(folder / 'events.jsonl')]
        bot = bot or paths.BOT
        self.result = json.loads((folder / 'result.json').read_text()) if (folder / 'result.json').exists() else {}
        self.lines = []
        for e in self.events:
            if e['type'] == 'protocol':
                for i, text in enumerate(e['protocol'].split('\n')):
                    self.lines.append((e['sequence'], i, text))
        self.at = {(s, i): k for k, (s, i, _) in enumerate(self.lines)}
        self.me = self.op = None
        for _, _, text in self.lines:
            found = re.match(r'^\|player\|(p[12])\|%s\|' % re.escape(bot), text)
            if found:
                self.me = found.group(1)
                self.op = 'p1' if self.me == 'p2' else 'p2'
                break
        self.inputs = [e for e in self.events if e['type'] == 'input']
        self.selection = {e['decision']: e for e in self.events if e['type'] == 'selection'}
        self.sample = {e['decision']: e for e in self.events if e['type'] == 'policy_sample'}

    def teams(self):
        team = lambda side: [m.split(',')[0] for _, _, t in self.lines
                             for m in re.findall(r'^\|poke\|%s\|([^|]+)' % side, t)]
        return team(self.me), team(self.op)

    def span(self, k):
        """Protocol lines after decision `k` up to the next decision's boundary (to the end for the last one)."""
        b = self.inputs[k]['boundary']
        start = self.at[(b['protocol_event_seq'], b['line_index'])] + 1
        if k + 1 < len(self.inputs):
            n = self.inputs[k + 1]['boundary']
            end = self.at[(n['protocol_event_seq'], n['line_index'])] + 1
        else:
            end = len(self.lines)
        return [t for _, _, t in self.lines[start:end] if t and not t.startswith(('|request|', '>', '|t:|', '|c|',
                                                                                 '|j|', '|l|', '|inactive|'))]

    def after(self, k, choice):
        """What the log shows after decision `k`: my move and its fate, the foe's action, faints and boosts."""
        me, op = self.me + 'a: ', self.op + 'a: '
        lines = self.span(k)
        out = dict(my_move=None, my_result=None, target_switched=False, opp_move=None, opp_switch=None,
                   my_faint=False, opp_faint=False, opp_boosts=0, my_cant=None, opp_tera=False, crit_on_me=False,
                   my_miss=False)
        foe_switched_at = None
        for i, line in enumerate(lines):
            parts = line.split('|')
            kind = parts[1] if len(parts) > 1 else ''
            if kind in ('switch', 'drag') and parts[2].startswith(op):
                out['opp_switch'] = tid(parts[3].split(',')[0])
                foe_switched_at = i
            elif kind == 'move' and parts[2].startswith(op) and '[from]' not in line and out['opp_move'] is None:
                out['opp_move'] = parts[3]
            elif kind == 'faint':
                out['my_faint' if parts[2].startswith(me) else 'opp_faint'] = True
            elif kind == '-boost' and parts[2].startswith(op):
                out['opp_boosts'] += int(parts[4])
            elif kind == 'cant' and parts[2].startswith(me) and out['my_cant'] is None:
                out['my_cant'] = parts[3]
            elif kind == '-terastallize' and parts[2].startswith(op):
                out['opp_tera'] = True
            elif kind == '-crit' and parts[2].startswith(me):
                out['crit_on_me'] = True
            elif kind == 'move' and parts[2].startswith(me) and '[from]' not in line and out['my_move'] is None:
                out['my_move'] = parts[3]
                window = []
                for nxt in lines[i + 1:]:
                    if nxt.startswith(('|move|', '|turn|', '|upkeep', '|switch|', '|drag|')) and \
                            not (nxt.startswith('|switch|' + self.me) or nxt.startswith('|drag|')):
                        break
                    window.append(nxt)
                out['target_switched'] = foe_switched_at is not None and choice.startswith('move:')
                if any(w.startswith('|-activate|' + op) and any(('move: ' + p) in w or w.endswith('|' + p)
                                                                 for p in PROTECT) for w in window):
                    out['my_result'] = 'protect'
                elif any(w.startswith('|-immune|') for w in window):
                    out['my_result'] = 'immune'
                elif any(w.startswith('|-fail|') for w in window):
                    out['my_result'] = 'fail'
                elif any('[from] ability:' in w and w.startswith(('|-heal|' + op, '|-boost|' + op, '|-start|' + op))
                         for w in window):
                    out['my_result'] = 'absorbed'
                elif any(w.startswith('|-miss|') for w in window):
                    out['my_result'], out['my_miss'] = 'miss', True
                else:
                    out['my_result'] = 'ok'
        return out, lines

    def rows(self):
        """One dict per decision (without the rendered input; `render` adds it)."""
        cfg = era(self.name)
        policy = (self.result.get('policy') or {}).get('name', 'argmax')
        mine, theirs = self.teams() if self.me else ([], [])
        for k, e in enumerate(self.inputs):
            sel = self.selection.get(e['decision'])
            if sel is None:
                continue
            probs = sel.get('probabilities') or {}
            after, lines = self.after(k, sel['choice'])
            yield dict(game=self.name, k=k, decision=e['decision'], turn=e['official']['turn'],
                       kind=e['snapshot']['decision_kind'], choice=sel['choice'], probabilities=probs,
                       argmax=max(probs, key=probs.get) if probs else sel['choice'],
                       automatic=bool(sel.get('automatic')), sampled=e['decision'] in self.sample, policy=policy,
                       ext=cfg['ext'], fix=cfg['fix'], result=self.result.get('result'),
                       opponent=self.result.get('opponent'), turns=self.result.get('turns'),
                       opp_team=theirs, after=after, log=lines, input_sha256=e['input_sha256'])
