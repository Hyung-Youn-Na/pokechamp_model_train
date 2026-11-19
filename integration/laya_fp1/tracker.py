"""EX-177 (D-213): foul-play's battle tracking replayed over a Showdown replay log, from one player's view.

Runs under the foul-play venv (`.tools/foul-play/.venv`, PYTHONPATH = repo root + `.tools/foul-play/src`). foul-play
itself is unmodified; this module only feeds it what its websocket loop would have fed a bot playing that side:

- team preview: the opponent's `|poke|` lines and a first request built from the player's own six sets;
- then, at every decision of that player (the EX-071 / EX-166 recovered records, `cutoff_line` = the log prefix the
  decision sees), the log lines since the previous decision and a request built from the record's own-team snapshot,
  exactly as `update_battle` handles a `|request|` (`request()` then `process_battle_updates()`);
- the player's own HP in the log is the spectator `x/100`; foul-play reads its own side's conditions as exact HP, so
  those conditions are rewritten to `round(x / 100 * maxhp)/maxhp`; replays that show exact HP for both sides
  (smogtours) get the opponent's as `x/100`, as a player sees it; older logs' `-weather|Snow` becomes `Snowscape`
  (the only three rewrites of the log);
- after each decision, `user.last_selected_move` is the record's label (foul-play sets it from its own choice).

`view()` is what foul-play searches on: a copy with the request applied (`async_pick_move`).
"""
from __future__ import annotations

import copy
import json
import re

STATS = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')
UNKNOWN_CHOICE = 'helpinghand'     # see `Tracker.chose`
_CONDITION_EVENTS = {'switch': 3, 'drag': 3, '-damage': 3, '-heal': 3, '-sethp': 3, 'replace': None,
                     'detailschange': None}
_READY = False


def ident(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def setup():
    """Once per process: sealed inference data, no network, the EP-232 foul-play configuration, quiet logging."""
    global _READY
    if _READY:
        return
    import logging
    from integration.foulplay import actor
    actor.verify_data()
    actor.offline()
    actor.configure('laya-fp1')
    from fp.config import FoulPlayConfig
    from fp.data.mods.apply_mods import apply_mods
    from fp.data.sets import smogon
    apply_mods(FoulPlayConfig.format_spec)
    # The sealed Smogon stats file is parsed once per process instead of once per game (each Tracker initializes
    # the datasets as a new battle does). `_get_pokemon_information` only reads the parsed dictionary.
    parsed = {}
    original = smogon.SmogonSets._get_smogon_stats_json

    def cached(self, url):
        if url not in parsed:
            parsed[url] = original(self, url)
        return parsed[url]
    smogon.SmogonSets._get_smogon_stats_json = cached
    logging.disable(logging.WARNING)
    _READY = True


def lines_of(raw):
    if isinstance(raw, dict):
        raw = raw['log']
    return raw.splitlines() if isinstance(raw, str) else list(raw)


def preview(lines):
    teams = {'p1': [], 'p2': []}
    for line in lines:
        parts = line.split('|')
        if len(parts) >= 4 and parts[1] == 'poke' and parts[2] in teams:
            teams[parts[2]].append(parts[3])
    return teams


def own_stats(original):
    """Exact stats of one own set (foul-play's own stat formula, so the engine sees what a bot would)."""
    from fp.battle.helpers import calculate_stats
    from fp.data import pokedex
    from fp import constants
    name = ident(original['species'])
    base = pokedex[name][constants.BASESTATS]
    evs = tuple(int(original.get('evs', {}).get(k, 0)) for k in STATS)
    ivs = tuple(int(original.get('ivs', {}).get(k, 31)) for k in STATS)
    stats = calculate_stats(base, int(original.get('level', 100)), ivs, evs, ident(original.get('nature') or 'serious'))
    keys = (constants.HITPOINTS, constants.ATTACK, constants.DEFENSE, constants.SPECIAL_ATTACK,
            constants.SPECIAL_DEFENSE, constants.SPEED)
    return {k: int(stats[c]) for k, c in zip(STATS, keys)}


class Tracker:
    """One replay, one perspective."""

    def __init__(self, raw, perspective, own_sets):
        setup()
        from fp.battle.state import Battle
        from fp.modes.standard_battle import StandardBattleMode
        self.lines = lines_of(raw)
        self.side = perspective
        self.other = 'p2' if perspective == 'p1' else 'p1'
        self.own_sets = list(own_sets)
        self.stats = [own_stats(s) for s in self.own_sets]
        self.maxhp = {ident(s['species']): st['hp'] for s, st in zip(self.own_sets, self.stats)}
        self.nick = {}                       # own nickname -> original species ident
        self.position = 0
        self.rqid = 0
        battle = Battle('battle-gen9ou-' + perspective)
        battle.pokemon_format = 'gen9ou'
        battle.generation = battle.format_spec.generation
        battle.battle_type = battle.format_spec.battle_type
        battle.mode = StandardBattleMode()
        battle.opponent.name = self.other
        self.battle = battle
        self._team_preview()

    # ------------------------------------------------------------------------------------------- request building

    def _slot_of(self, species):
        key = ident(species)
        for index, s in enumerate(self.own_sets):
            if ident(s['species']) == key:
                return index
        return None

    def _request(self, snapshot=None, *, preview=False, forced=False, wait=False):
        """A Showdown request for the own side. `snapshot` is the laya record snapshot (own team state)."""
        team = []
        active_index = None
        own = (snapshot or {}).get('own_team') or []
        by_slot = {m.get('slot'): m for m in own}
        for index, (original, stats) in enumerate(zip(self.own_sets, self.stats)):
            mon = by_slot.get(index + 1) or {}
            maxhp = stats['hp']
            hp_percent = mon.get('hp_percent', 100.0) if mon else 100.0
            status = mon.get('status')
            if status == 'fnt' or (hp_percent is not None and hp_percent <= 0):
                condition = '0 fnt'
            else:
                hp = max(1, int(round(float(hp_percent) / 100.0 * maxhp)))
                condition = '%d/%d' % (hp, maxhp) + (' ' + status if status else '')
            species = mon.get('species') or original['species']
            # The one public alias (impute.species_ident): Greninja-Bond is shown as Greninja in the log, preview and
            # snapshot, and foul-play names the pokemon from the log, so every request uses the public name.
            if ident(species) == 'greninjabond':
                species = 'Greninja'
            active = (index == 0) if preview else (snapshot is not None and
                                                   snapshot.get('own_active_slot') == index + 1)
            if active:
                active_index = index
            moves = [ident(m['id']) for m in mon.get('moves', [])] or [ident(m) for m in original['moves']]
            entry = dict(ident='%s: %s' % (self.side, self._nickname(index)),
                         details='%s, L%d%s' % (species, int(original.get('level', 100)),
                                                ', ' + original['gender'] if original.get('gender') in ('M', 'F') else ''),
                         condition=condition, active=active,
                         stats={k: stats[k] for k in STATS[1:]},
                         moves=moves, baseAbility=ident(original.get('ability') or ''),
                         item=ident(mon.get('item') or '') if mon else ident(original.get('item') or ''),
                         pokeball='pokeball', ability=ident((mon.get('ability') if mon else None)
                                                            or original.get('ability') or ''),
                         teraType=original.get('teraType') or 'Normal',
                         terastallized=(original.get('teraType') or '') if mon.get('terastallized') else '')
            team.append(entry)
        # Showdown lists the active Pokémon first
        if active_index not in (None, 0):
            team.insert(0, team.pop(active_index))
        self.rqid += 1
        request = dict(side=dict(name=self.side, id=self.side, pokemon=team), rqid=self.rqid)
        if preview:
            request['teamPreview'] = True
        elif forced:
            request['forceSwitch'] = [True]
        elif wait:
            request['wait'] = True
        elif active_index is not None:
            mon = by_slot.get(active_index + 1) or {}
            moves = []
            for m in mon.get('moves', []):
                moves.append(dict(move=m['id'], id=ident(m['id']), pp=m.get('pp') if m.get('pp') is not None else 1,
                                  maxpp=m.get('max_pp') or 1, target='normal', disabled=bool(m.get('disabled'))))
            active = dict(moves=moves)
            if snapshot.get('can_tera'):
                active['canTerastallize'] = self.own_sets[active_index].get('teraType') or 'Normal'
            request['active'] = [active]
        return request

    def _nickname(self, index):
        species = ident(self.own_sets[index]['species'])
        for nick, sp in self.nick.items():
            if sp == species:
                return nick
        return self.own_sets[index]['species']

    # ------------------------------------------------------------------------------------------- log feeding

    def _rewrite(self, line):
        """Own-side `x/100` conditions -> exact HP (what the player's own client shows).

        Also the one protocol-version difference found so far: older Showdown (the EX-071 tour replays) names the
        weather `Snow`; current Showdown and foul-play use `Snowscape`.
        """
        if line.startswith('|-weather|Snow') and not line.startswith('|-weather|Snowscape'):
            line = '|-weather|Snowscape' + line[len('|-weather|Snow'):]
        parts = line.split('|')
        if len(parts) < 4:
            return line
        event = parts[1]
        who = parts[2]
        position = {'switch': 4, 'drag': 4, '-damage': 3, '-heal': 3, '-sethp': 3}.get(event)
        if not who.startswith(self.side):
            # Some replays (smogtours) show exact HP for both sides; foul-play reads the opponent's as `x/100`.
            if position is not None and len(parts) > position:
                match = re.match(r'^(\d+)/(\d+)(.*)$', parts[position])
                if match and int(match.group(2)) not in (0, 100):
                    hp, maxhp = int(match.group(1)), int(match.group(2))
                    percent = 0 if hp == 0 else max(1, int(round(100.0 * hp / maxhp)))
                    parts[position] = '%d/100%s' % (percent, match.group(3))
                    return '|'.join(parts)
            return line
        if event in ('switch', 'drag', 'replace', 'detailschange') and len(parts) >= 4:
            nick = who.split(':', 1)[1].strip() if ':' in who else who
            slot = self._slot_of(parts[3].split(',')[0])
            if slot is not None:
                self.nick[nick] = ident(self.own_sets[slot]['species'])
        if position is None or len(parts) <= position:
            return line
        condition = parts[position]
        match = re.match(r'^(\d+)/(\d+)(.*)$', condition)
        if not match or int(match.group(2)) == 0:
            return line
        nick = who.split(':', 1)[1].strip() if ':' in who else who
        species = self.nick.get(nick)
        maxhp = self.maxhp.get(species)
        if maxhp is None:
            return line
        fraction = int(match.group(1)) / int(match.group(2))     # `x/100` (spectator) or exact (smogtours)
        hp = 0 if fraction == 0 else max(1, int(round(fraction * maxhp)))
        parts[position] = '%d/%d%s' % (hp, maxhp, match.group(3))
        return '|'.join(parts)

    def _team_preview(self):
        from fp import constants
        teams = preview(self.lines)
        if len(teams[self.side]) != 6 or len(teams[self.other]) != 6:
            raise ValueError('six preview slots required')
        battle = self.battle
        request = self._request(preview=True)
        battle.request_json = request
        battle.rqid = request['rqid']
        battle.user.initialize_first_turn_user_from_json(request)
        battle.initialize_team_preview(teams[self.other], battle.pokemon_format)
        battle.during_team_preview()
        names = set(p.name for p in battle.opponent.reserve + battle.user.reserve)
        battle.mode.initialize_team_preview_datasets(battle.pokemon_format, names, '')
        battle.team_preview = False
        # the log up to |start| is the preview; foul-play keeps nothing from it but the teams above
        for index, line in enumerate(self.lines):
            if line.startswith('|start'):
                self.position = index
                break

    def advance(self, cutoff, snapshot, decision_kind):
        """Feed the log up to `cutoff` (exclusive) and the request of this decision."""
        from fp.battle.protocol import process_battle_updates, request as handle_request
        if cutoff < self.position:
            raise ValueError('decisions out of order')
        battle = self.battle
        for line in self.lines[self.position:cutoff]:
            line = self._rewrite(line)
            parts = line.split('|')
            if len(parts) < 2:
                continue
            battle.msg_list.append(line)
        self.position = cutoff
        req = self._request(snapshot, forced=decision_kind in ('forced_switch', 'pivot_switch'))
        handle_request(battle, ['', 'request', json.dumps(req)])
        process_battle_updates(battle)

    def chose(self, label):
        """The player's choice at this decision (foul-play sets `last_selected_move` from its own choice).

        An unobserved choice (`label` None: e.g. the player fainted before acting) is unknown to us, whereas a bot
        always knows its own. It is recorded as `UNKNOWN_CHOICE`, a +5 priority move, so that foul-play's
        speed-range check for that turn sees unequal priorities and skips (it would otherwise compare against a
        stale choice or fail on an empty one).
        """
        from fp.battle.state import LastUsedMove
        battle = self.battle
        name = battle.user.active.name if battle.user.active else ''
        if not label:
            battle.user.last_selected_move = LastUsedMove(name, UNKNOWN_CHOICE, battle.turn)
            return
        kind, _, rest = label.partition(':')
        if kind == 'move':
            move = rest.split(':')[0]
            battle.user.last_selected_move = LastUsedMove(name, move, battle.turn)
        elif kind == 'lead':
            species = ident(self.own_sets[int(rest) - 1]['species'])
            battle.user.last_selected_move = LastUsedMove('teampreview', 'switch ' + species, battle.turn)
        elif kind == 'switch':
            slot = int(rest) - 1
            species = ident(self.own_sets[slot]['species'])
            name = battle.user.active.name if battle.user.active else 'teampreview'
            battle.user.last_selected_move = LastUsedMove(name, 'switch ' + species, battle.turn)

    def view(self):
        battle = copy.deepcopy(self.battle)
        battle.user.update_from_request_json(battle.request_json)
        return battle

    def lead_view(self):
        """The team-preview battle (no actives yet), as foul-play's `handle_team_preview` sees it."""
        if self.position and any(l.startswith('|switch|') for l in self.lines[:self.position]):
            raise ValueError('lead view after the battle started')
        battle = copy.deepcopy(self.battle)
        battle.team_preview = True
        return battle


def recovered_records(recovered, perspective):
    """The decisions of one side, in log order."""
    result = recovered.get('result', recovered)
    rows = [r for r in result['records'] if r['perspective'] == perspective]
    return sorted(rows, key=lambda r: r['cutoff_line'])
