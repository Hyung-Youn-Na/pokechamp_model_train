"""EX-181 (EP-235): foul-play's battle tracking replayed over the v10rt side of one EX-174 game.

Runs under the foul-play venv (PYTHONPATH = repo root + `.tools/foul-play/src`). foul-play is unmodified and only
imported. The websocket messages the laya actor received (`events.jsonl` `protocol` events, in `sequence` order) go
through the same calls as foul-play's own loop (`StandardBattleMode.start_battle_common` / `start_battle`,
`handle_team_preview`, `run_battle.pokemon_battle` with `update_battle`), so at every request the battle is the one
foul-play would hold had it been playing that seat. One difference: after each decision `user.last_selected_move`
is what laya actually sent (foul-play sets it from its own pick), because the rest of the log follows laya's choices.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

from integration.laya_regret import paths as P

_READY = False


def setup():
    """Once per process: sealed inference data, no network, the EP-232 foul-play configuration, quiet logging.

    Same steps as `integration.laya_fp1.tracker.setup` (EX-177), kept here so this package depends only on the
    EP-232 actor helpers.
    """
    global _READY
    if _READY:
        return
    import logging
    from integration.foulplay import actor
    actor.verify_data()
    actor.offline()
    actor.configure('laya-regret')
    from fp.config import FoulPlayConfig
    from fp.data.mods.apply_mods import apply_mods
    from fp.data.sets import smogon
    apply_mods(FoulPlayConfig.format_spec)
    parsed = {}
    original = smogon.SmogonSets._get_smogon_stats_json

    def cached(self, url):
        if url not in parsed:
            parsed[url] = original(self, url)
        return parsed[url]
    smogon.SmogonSets._get_smogon_stats_json = cached
    logging.disable(logging.WARNING)
    _READY = True


# ----------------------------------------------------------------------------------------------- recorded game


def load_game(directory):
    """Messages, laya's sent commands and model outputs of one EX-174 game (laya side)."""
    directory = Path(directory)
    events = [json.loads(line) for line in open(directory / 'events.jsonl')]
    outcome = json.loads((directory / 'outcome.json').read_text())
    protocol = sorted((e for e in events if e['type'] == 'protocol'), key=lambda e: e['sequence'])
    username = protocol[0]['username']
    reval = {e['decision']: e for e in events if e['type'] == 'revalidation'}
    kinds = {}
    for e in events:
        if e['type'] == 'input':
            try:
                kinds[e['decision']] = json.loads(e['body']['state'])['snapshot'].get('decision_kind')
            except (KeyError, TypeError, ValueError):
                kinds[e['decision']] = None
    sends = {}
    for e in events:
        if e['type'] == 'ps_send' and e.get('request_id') not in (None, ''):
            sends[int(e['request_id'])] = e['command']          # the last send for a request is what counted
    choices = {}
    for e in events:
        if e['type'] != 'selection':
            continue
        rv = reval.get(e['decision'])
        if rv is None or not rv.get('passed'):
            continue
        rqid = int(rv['request_id'])
        if sends.get(rqid) != e['command']:
            continue
        choices[rqid] = dict(decision=e['decision'], choice=e['choice'], command=e['command'],
                             probabilities=e.get('probabilities') or {}, automatic=bool(e.get('automatic')),
                             commands=rv.get('commands') or {}, kind=kinds.get(e['decision']),
                             elapsed=e.get('elapsed_seconds'))
    return dict(slot=directory.name, protocol=[e['protocol'] for e in protocol], username=username,
                choices=choices, sends=sends, outcome=outcome)


# ----------------------------------------------------------------------------------------------- command mapping


def fp_choice(view, command):
    """A Showdown command laya sent -> foul-play's / poke-engine's choice string for the same action.

    `/choose move N [terastallize]` -> the request's N-th move id (+ `-tera`); `/choose switch N` -> `switch <name>`
    of the reserve with request index N; `/team D...` (team preview) -> `switch <name>` of the lead.
    """
    from fp.battle.helpers import normalize_name
    parts = command.split()
    if parts[0] == '/team':
        index = int(parts[1][0])
        return 'switch ' + _by_index(view, index).name
    if parts[0] == '/switch' or parts[:2] == ['/choose', 'switch']:
        return 'switch ' + _by_index(view, int(parts[-1])).name
    if parts[:2] == ['/choose', 'move']:
        moves = view.request_json['active'][0]['moves']
        move = normalize_name(moves[int(parts[2]) - 1]['id'])
        return move + ('-tera' if 'terastallize' in parts[3:] else '')
    raise ValueError('unknown command %r' % command)


def _by_index(view, index):
    for pkmn in view.user.reserve:
        if pkmn.index == index:
            return pkmn
    raise ValueError('no reserve with request index %d' % index)


# ----------------------------------------------------------------------------------------------- replay


@dataclass
class Point:
    """One decision of the laya seat, with the battle foul-play would search on."""
    rqid: int
    view: object                     # foul-play Battle (a copy; search on a further copy)
    lead: bool
    forced: bool
    turn: int
    checks: dict = field(default_factory=dict)


def replay(game):
    """Yield a `Point` at every request the seat acts on, then apply laya's actual command."""
    setup()
    from fp import constants
    from fp.battle.helpers import normalize_name
    from fp.battle.protocol import update_battle
    from fp.battle.state import Battle, LastUsedMove, Pokemon
    from fp.config import FoulPlayConfig
    from fp.modes.standard_battle import StandardBattleMode
    from fp.run_battle import battle_is_finished

    FoulPlayConfig.username = FoulPlayConfig.user_id = game['username']
    messages = iter(game['protocol'])

    # BattleMode.start_battle_common / get_battle_tag_and_opponent
    for msg in messages:
        split = msg.split('|')
        if 'battle' in split[0]:
            tag = split[0].replace('>', '').strip()
            opponent = split[4].replace(game['username'], '').replace('vs.', '').strip()
            break
    battle = Battle(tag)
    battle.opponent.account_name = opponent
    battle.pokemon_format = P.FORMAT
    battle.generation = battle.format_spec.generation
    battle.battle_type = battle.format_spec.battle_type
    battle.mode = StandardBattleMode()
    for msg in messages:
        if '|player|' in msg and opponent in msg:
            battle.opponent.name = msg.split('|')[2]
            battle.user.name = constants.ID_LOOKUP[battle.opponent.name]
            break
    battle.user.team_dict = None

    # StandardBattleMode.start_battle (team preview branch)
    while constants.START_TEAM_PREVIEW not in msg:
        msg = next(messages)
    preview_msg = msg
    opponent_pokemon = []
    for line in msg.split(constants.START_TEAM_PREVIEW)[-1].split('\n'):
        split_line = line.split('|')
        if len(split_line) > 3 and split_line[1] == constants.TEAM_PREVIEW_POKE \
                and split_line[2].strip() == battle.opponent.name:
            opponent_pokemon.append(split_line[3])
    for msg in messages:                                     # get_first_request_json
        split = msg.split('|')
        if len(split) > 2 and split[1].strip() == 'request' and split[2].strip():
            user_json = json.loads(split[2].strip("'"))
            battle.request_json = user_json
            battle.user.initialize_first_turn_user_from_json(user_json)
            battle.rqid = user_json[constants.RQID]
            break
    battle.initialize_team_preview(opponent_pokemon, P.FORMAT)
    battle.during_team_preview()
    names = set(p.name for p in battle.opponent.reserve + battle.user.reserve)
    battle.mode.initialize_team_preview_datasets(P.FORMAT, names, preview_msg)

    # handle_team_preview
    view = copy.deepcopy(battle)
    view.user.active = Pokemon.get_dummy()
    view.opponent.active = Pokemon.get_dummy()
    view.team_preview = True
    rqid = int(battle.rqid)
    yield Point(rqid=rqid, view=view, lead=True, forced=False, turn=battle.turn)
    command = game['sends'].get(rqid)
    if command:
        name = fp_choice(view, command).removeprefix('switch ')
        battle.user.last_selected_move = LastUsedMove('teampreview', 'switch ' + name, battle.turn)

    # run_battle.pokemon_battle
    for msg in messages:
        if battle_is_finished(battle.battle_tag, msg):
            return
        action_required = update_battle(battle, msg)
        if not (action_required and not battle.wait):
            continue
        rqid = int(battle.rqid)
        view = copy.deepcopy(battle)                           # async_pick_move
        view.user.update_from_request_json(view.request_json)
        checks = {}
        side = view.request_json.get('side', {}).get('pokemon', [])
        active = [m for m in side if m.get('active')]
        if active and view.user.active is not None and not battle.force_switch:
            species = normalize_name(active[0]['details'].split(',')[0])
            checks['own_active'] = species == view.user.active.name or species.startswith(view.user.active.name)
        yield Point(rqid=rqid, view=view, lead=False, forced=bool(battle.force_switch), turn=battle.turn,
                    checks=checks)
        command = game['sends'].get(rqid)
        if command:
            choice = fp_choice(view, command)
            battle.user.last_selected_move = LastUsedMove(
                battle.user.active.name, choice.removesuffix('-tera').removesuffix('-mega'), battle.turn)
