"""LayaBot for the scenario server: the laya-play decision path (EX-139 live path) without the challenge step.

`scenario_server.cjs` seats this bot as p2 of an imported battle that already stands at turn 2, so the player waits for
that battle to appear instead of accepting a challenge; everything after (official client snapshot -> Metamon bridge ->
`ImitationInput` -> loopback laya serving -> argmax) is `integration.pokechamp.imitation.player` unchanged. Any served
model works; its identity comes from the serving ready file. One fresh player per game, as in laya-play.

Run with the battle interpreter and `PYTHONPATH=/workspace:/workspace/pokechamp`; see `run.py`.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

TURN_LIMIT = 300      # laya-play / EX-125 limits
DECISION_LIMIT = 600
GAME_SECONDS = 6 * 3600


def player_classes(slots):
    from integration.pokechamp.imitation import player as p
    p.MAX_TURNS = TURN_LIMIT

    class LimitedSession(p.Session):
        async def evaluate(self, value, decision):
            if self.calls >= DECISION_LIMIT:
                raise p.BattleLimit('decision_limit')
            return await super().evaluate(value, decision)

    class SeatedPlayer(p.player_class()):
        # Seated after turn 1, the bot never sees its own team preview: freeze the original game's preview slots.
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fixed_slots = p.FixedSlots(slots)

        async def _handle_battle_message(self, messages):
            # Being seated renames the bot inside the room (`|N|☆LayaBot`), and a person leaving the room sends
            # `|player|p1|`; poke_env parses neither outside a timed battle. The person's seat is kept either way.
            return await super()._handle_battle_message(
                [m for m in messages if m[1:2] != ['N'] and not (m[1:2] == ['player'] and len(m) < 6)])

    return p, LimitedSession, SeatedPlayer


async def one_game(args, serving, scenario, directory):
    from poke_env.concurrency import handle_threaded_coroutines
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from integration.pokechamp import cli as pcli

    p, LimitedSession, Player = player_classes(scenario['p2_slots'])
    team = scenario['players']['p2']['team']
    session = LimitedSession(directory, model=serving['model'], serving=serving,
                             own_sets=p.submitted_sets(dict(packed=team)), deadline=time.monotonic() + GAME_SECONDS)
    session.record(dict(type='team_submission', username=args.name, packed_team=team))
    player = Player(
        session=session, expected_actor='p2', team=team, battle_format='gen9ou',
        max_concurrent_battles=1, start_timer_on_battle_start=False,
        account_configuration=AccountConfiguration(args.name, None),
        server_configuration=ServerConfiguration('localhost:%d' % args.port,
                                                 'https://play.pokemonshowdown.com/action.php?'))
    p.record_sends(player, session)
    result = dict(model=serving['model'], status='failed', result=None, opponent=None)
    try:
        await asyncio.wait_for(handle_threaded_coroutines(player.ps_client.logged_in.wait()), timeout=60)
        print('[bot] %s (%s) is waiting to be seated in the scenario battle' % (args.name, serving['model']),
              flush=True)
        error, battle = None, None
        while True:
            battle = next(iter(player.battles.values()), None)
            error = session.terminal_error or getattr(player, 'output_error', None)
            if error is None and battle is not None and session.remaining() <= 0:
                error = p.BattleLimit('time_limit')
            if error is None and battle is not None and battle.turn > TURN_LIMIT:
                error = p.BattleLimit('turn_limit')
            if error is not None or (battle is not None and battle.finished):
                break
            await asyncio.sleep(0.2)
        for _ in range(10 if error is not None and battle is not None else 0):
            if battle.finished:
                error = None   # a choice refused because the person forfeited at that moment is not a failure
                break
            await asyncio.sleep(0.2)
        if error is not None:
            if battle is not None and not battle.finished:
                await player.ps_client.send_message('/forfeit', battle.battle_tag)
            result.update(status='stopped', error=dict(type=type(error).__name__, detail=str(error)))
            print('[bot] stopped this game and forfeited: %s: %s' % (type(error).__name__, error), flush=True)
        else:
            result.update(status='completed', turns=battle.turn, battle_tag=battle.battle_tag,
                          result='win' if battle.won else 'loss' if battle.lost else 'draw',
                          opponent=battle.opponent_username)
            print('[bot] game over vs %s: bot %s in %d turns'
                  % (battle.opponent_username, result['result'], battle.turn), flush=True)
    except BaseException as error:
        result.update(error=dict(type=type(error).__name__, detail=str(error)))
        if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)):
            raise
        print('[bot] game failed: %s: %s' % (type(error).__name__, error), flush=True)
    finally:
        await pcli._close_players([player])
        if getattr(player, 'official', None):
            player.official.close()
        session.close()
        p._atomic_json(Path(directory) / 'result.json', dict(result, decisions=session.calls))
    return result


async def main_async(args):
    from integration.pokechamp.battle_adapter import install_identity_adapter
    from integration.pokechamp.imitation.player import http_json

    install_identity_adapter()
    ready = json.loads(Path(args.serving).read_text())
    health = http_json(ready['endpoint'], '/health', timeout=10)
    if health.get('checkpoint_sha256') != ready['checkpoint_sha256']:
        raise SystemExit('serving identity differs from the ready file')
    serving = dict(endpoint=ready['endpoint'], checkpoint_sha256=ready['checkpoint_sha256'], model=health['model'])
    scenario = json.loads(Path(args.scenario).read_text())
    games = Path(args.games)
    number = 0
    while args.games_limit == 0 or number < args.games_limit:
        number += 1
        directory = games / ('%s-%s-%03d' % (time.strftime('%Y%m%d-%H%M%S'), serving['model'], number))
        directory.mkdir(parents=True)
        await one_game(args, serving, scenario, directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000, help='Showdown server port')
    parser.add_argument('--name', default='LayaBot', help='bot user name on the local server')
    parser.add_argument('--serving', required=True, help='ready file written by the laya serving process')
    parser.add_argument('--scenario', required=True, help='scenario spec (players.p2.team, p2_slots)')
    parser.add_argument('--games', required=True, help='directory for per-game logs')
    parser.add_argument('--games-limit', type=int, default=0, help='stop after N games (0 = run until stopped)')
    args = parser.parse_args(argv)
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
