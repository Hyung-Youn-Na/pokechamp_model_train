"""EX-173 foul-play actor, run by `integration.foulplay.battle` under the foul-play venv (D-211).

One game on the owned local Showdown server, with the same attempt-directory contract as the laya / Abyssal workers
(`integration.pokechamp.imitation.player.worker`):

- `<role>.ready.json` after login, then wait for the other side's; p1 challenges, p2 accepts.
- `opponent-events.jsonl` records the `/utm` team submission (the shared `audit_match` compares it with the frozen
  packed team); `foulplay-events.jsonl` records every searched decision (turn, seconds, choice).
- `<role>.result.json` with status / result / turns / battle_tag / seed / python_hash_seed.

foul-play itself (`.tools/foul-play/src`, commit 8f541f8) is unmodified. Only these are replaced at run time:
the login (local `/trn name,0,` instead of the play.pokemonshowdown.com assertion), the network (every `requests`
call raises: the inference files are the sealed cache), the Smogon stats month (pinned to 2026-10), and outgoing
chat and `/timer on` (dropped, so the game runs under the same no-timer conditions as EX-168).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

from integration.foulplay import paths as P

DROPPED = ('hf', 'gg', '/timer on')


class Limit(Exception):
    pass


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.%d.tmp' % os.getpid())
    with temporary.open('x') as stream:
        stream.write(compact(value) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class Log:
    def __init__(self, path):
        self.stream = Path(path).open('a')

    def record(self, value):
        self.stream.write(compact(dict(value, at=time.time())) + '\n')
        self.stream.flush()

    def close(self):
        self.stream.close()


def verify_data(source=P.FP_SOURCE, sums=P.DATA_SUMS):
    """The sealed inference cache (SHA256SUMS lines relative to the foul-play source)."""
    for line in Path(sums).read_text().splitlines():
        digest, name = line.split(None, 1)
        if hashlib.sha256((Path(source) / name.strip()).read_bytes()).hexdigest() != digest:
            raise RuntimeError('foul-play inference cache changed: ' + name)


def offline():
    import requests

    def refuse(*args, **kwargs):
        raise RuntimeError('network is disabled in the EX-173 foul-play actor: %r' % (args[:2],))

    requests.get = requests.post = requests.request = refuse
    requests.Session.request = refuse
    from fp.data.sets import smogon
    smogon.SmogonSets._get_smogon_stats_file_name = (
        lambda self, game_mode, month_delta=1: P.SMOGON_URL.replace('gen9ou-0', game_mode + '-0'))


def configure(username):
    from fp.config import BotModes, FoulPlayConfig, SaveReplay, init_logging
    FoulPlayConfig.username = FoulPlayConfig.user_id = username
    FoulPlayConfig.password = None
    FoulPlayConfig.avatar = None
    FoulPlayConfig.bot_mode = BotModes.accept_challenge
    FoulPlayConfig.pokemon_format = P.FORMAT
    FoulPlayConfig.smogon_stats = None
    FoulPlayConfig.search_time_ms = P.SEARCH_TIME_MS
    FoulPlayConfig.parallelism = P.SEARCH_PARALLELISM
    FoulPlayConfig.team_preview_search_time_ms = P.SEARCH_TIME_MS
    FoulPlayConfig.team_preview_search_parallelism = P.SEARCH_PARALLELISM
    FoulPlayConfig.search_threads = P.SEARCH_THREADS
    FoulPlayConfig.run_count = 1
    FoulPlayConfig.team_name = FoulPlayConfig.team_list = FoulPlayConfig.user_to_challenge = None
    FoulPlayConfig.save_replay = SaveReplay.never
    FoulPlayConfig.room_name = None
    FoulPlayConfig.log_level = 'INFO'
    FoulPlayConfig.log_to_file = False
    init_logging('INFO', False)
    return FoulPlayConfig


def client_class():
    from fp.websocket_client import PSWebsocketClient

    class Client(PSWebsocketClient):
        """Local login, an independent send recorder and turn tracking; foul-play's protocol handling unchanged."""
        events = None
        turn = 0

        @classmethod
        async def create(cls, username, password, address):
            # foul-play's `create` builds a plain PSWebsocketClient; build this class instead.
            import websockets
            self = cls()
            self.username, self.password, self.address = username, password, address
            self.websocket = await websockets.connect(address)
            self.login_uri = None
            return self

        async def login(self):
            await self.get_id_and_challstr()
            await PSWebsocketClient.send_message(self, '', ['/trn %s,0,' % self.username])
            while True:
                message = await self.receive_message()
                for line in message.split('\n'):
                    parts = line.split('|')
                    if len(parts) > 3 and parts[1] == 'updateuser' and parts[3] == '1' \
                            and parts[2].strip().lstrip('@+%&#~*').strip() == self.username:
                        return self.username

        async def send_message(self, room, message_list):
            if len(message_list) == 1 and message_list[0] in DROPPED:
                return
            text = '|'.join(message_list)
            if text.startswith('/utm '):
                self.events.record(dict(type='team_submission', username=self.username,
                                        packed_team=text.removeprefix('/utm ')))
            else:
                self.events.record(dict(type='ps_send', username=self.username, battle=room, command=text))
            await PSWebsocketClient.send_message(self, room, message_list)

        async def receive_message(self):
            message = await PSWebsocketClient.receive_message(self)
            if message.startswith('>battle-'):
                for line in message.split('\n'):
                    if line.startswith('|turn|'):
                        self.turn = int(line.split('|')[2])
            return message

    return Client


async def battle_loop(client, team_dict, state, decisions):
    from fp import constants
    from fp.battle.protocol import async_update_battle
    from fp.modes.base import async_pick_move
    from fp.run_battle import battle_is_finished, start_battle
    battle = await start_battle(client, P.FORMAT, team_dict)
    state['battle_tag'] = battle.battle_tag
    while True:
        message = await client.receive_message()
        if battle_is_finished(battle.battle_tag, message):
            if constants.WIN_STRING in message:
                return message.split(constants.WIN_STRING)[-1].split('\n')[0].strip()
            return None
        action_required = await async_update_battle(battle, message)
        if action_required and not battle.wait:
            if state['decisions'] >= P.DECISION_LIMIT:
                raise Limit('decision_limit')
            started = time.monotonic()
            choice = await async_pick_move(battle)
            state['decisions'] += 1
            decisions.record(dict(type='decision', number=state['decisions'], turn=client.turn,
                                  seconds=time.monotonic() - started, choice=choice))
            await client.send_message(battle.battle_tag, choice)


async def run(attempt, role):
    attempt = Path(attempt)
    request = json.loads((attempt / 'request.json').read_text())
    row, names, port = request['slot'], request['names'], request['port']
    other = 'p2' if role == 'p1' else 'p1'
    seed = row['opponent_seed']
    random.seed(seed)
    deadline = request['deadline_monotonic']
    result = dict(actor=role, status='failed', result=None, pid=os.getpid(), policy=row['opponent'], seed=seed,
                  python_hash_seed=os.environ.get('PYTHONHASHSEED'),
                  search=dict(time_ms=P.SEARCH_TIME_MS, parallelism=P.SEARCH_PARALLELISM, threads=P.SEARCH_THREADS))
    events, decisions = Log(attempt / 'opponent-events.jsonl'), Log(attempt / 'foulplay-events.jsonl')
    client, task = None, None
    state = dict(decisions=0, battle_tag=None)

    def check():
        if time.monotonic() >= deadline:
            raise Limit('time_limit')
        if (attempt / 'cancel.json').exists():
            raise Limit('peer_cancelled')
        if client is not None and client.turn > P.TURN_LIMIT:
            raise Limit('turn_limit')

    try:
        verify_data()
        offline()
        configure(names[role])
        from fp.data.mods.apply_mods import apply_mods
        from fp.config import FoulPlayConfig
        from fp.teams.team_converter import export_to_dict
        apply_mods(FoulPlayConfig.format_spec)
        team_dict = export_to_dict((attempt / 'foulplay-team.txt').read_text())
        Client = client_class()
        Client.events = events
        client = await Client.create(names[role], None, 'ws://127.0.0.1:%d/showdown/websocket' % port)
        await asyncio.wait_for(client.login(), timeout=min(60, max(1, deadline - time.monotonic())))
        atomic_json(attempt / ('%s.ready.json' % role), dict(ready=True, actor=role, pid=os.getpid()))
        while not (attempt / ('%s.ready.json' % other)).exists():
            check()
            await asyncio.sleep(0.1)
        async def game():
            await client.update_team(row['teams'][role]['packed'])
            if role == 'p1':
                await client.challenge_user(names[other], P.FORMAT)
            else:
                await client.accept_challenge(P.FORMAT, None)
            return await battle_loop(client, team_dict, state, decisions)

        task = asyncio.create_task(game())
        while not task.done():
            check()
            await asyncio.sleep(0.1)
        winner = await task
        if client.turn > P.TURN_LIMIT:
            raise Limit('turn_limit')
        result.update(status='completed', turns=client.turn, battle_tag=state['battle_tag'],
                      result='draw' if winner is None else 'win' if winner == names[role] else 'loss')
    except Limit as error:
        result.update(status='incomplete', reason=str(error), failure_scope='battle')
    except BaseException as error:
        result.update(status='failed', error=dict(type=type(error).__name__, detail=str(error)), failure_scope='phase')
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        result.update(decisions=state['decisions'], observed_turn=getattr(client, 'turn', 0))
        if client is not None:
            try:
                await client.close()
            except BaseException as error:
                result.update(status='failed', result=None, failure_scope='phase',
                              cleanup_error=dict(type=type(error).__name__, detail=str(error)))
        events.close()
        decisions.close()
        atomic_json(attempt / ('%s.result.json' % role), result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--role', choices=('p1', 'p2'), required=True)
    args = parser.parse_args(argv)
    result = asyncio.run(run(args.attempt, args.role))
    print(compact(result))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(main())
