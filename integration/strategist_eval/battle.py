"""Official observation boundary with dedicated Strategist action selection."""
import asyncio
import copy
import hashlib
import json
import os
import random
import subprocess
import threading
import time
from pathlib import Path
from integration.pokechamp import jev_battle as shared
from .core import ROOT, RUN, PORT, BATTLE_PY, build_input, candidates, select, ensure_current
from .storage import write


class BattleLimit(RuntimeError):
    pass


class Session:
    record = shared.Session.record
    fail = shared.Session.fail

    def __init__(self, directory, model):
        from integration.pokechamp.observation.build import DEFAULT_BUILD, verify
        self.directory = directory
        self.environ = {}
        self.records = []
        self.lock = threading.RLock()
        self.failure_event = threading.Event()
        self.terminal_error = None
        self.model = model
        self.slot_id = None
        self.count = 0
        verify()
        self.dex = json.loads((DEFAULT_BUILD/'dex.json').read_text())

    def remaining(self):
        if self.model.failure:
            self.fail(self.model.failure)
        return self.model.started + 14400 - time.time()


def player_class():
    class Strategist(shared.player_class()):
        latest_rqid = None

        async def _handle_battle_message(self, messages):
            for fields in messages:
                if len(fields) >= 3 and fields[1] == 'request':
                    req = json.loads('|'.join(fields[2:])) if fields[2] else None
                    self.latest_rqid = req.get('rqid') if req else None
            return await super()._handle_battle_message(messages)

        async def _handle_battle_request(self, battle, from_teampreview_request=False, maybe_default_order=False):
            if maybe_default_order:
                raise ValueError('automatic default forbidden')
            if battle.in_team_preview and from_teampreview_request and not self.request:
                battle.move_on_next_request = True
                return
            if battle.in_team_preview and not from_teampreview_request and not (self.request or {}).get('teamPreview'):
                return
            if not self.request or self.request.get('wait'):
                return
            if battle.turn > 300 or self.session.count >= 600:
                raise BattleLimit('300-turn/600-decision limit')
            actor = self.request['side']['id']
            if actor != self.expected_actor:
                raise ValueError('unexpected actor')
            rqid = self.request['rqid']
            if rqid != self.latest_rqid:
                raise ValueError('stale request before input')
            if self.official is None:
                from integration.pokechamp.observation.runtime import OfficialClient
                self.official = OfficialClient(actor)
            snapshot = await asyncio.to_thread(self.official.snapshot, copy.deepcopy(self.prefix), battle.battle_tag, boundary=self.boundary)
            payload = build_input(snapshot, self.prefix, actor, self.session.dex)
            self.session.count += 1
            decision = f'{self.session.slot_id}:d{self.session.count:04d}'
            legal = payload['candidates']
            self.session.record(dict(type='input', decision=decision, slot_id=self.session.slot_id,
                battle=battle.battle_tag, actor=actor, payload=payload, official=snapshot,
                boundary=self.boundary, prefix=copy.deepcopy(self.prefix),
                observation_identity=self.official.identity))
            response = None
            if len(legal) > 1:
                self.session.record(dict(type='model_call', decision=decision))
                response = await asyncio.to_thread(self.session.model.call, payload['messages'], decision)
                self.session.record(dict(type='response', decision=decision, **response))
            result = select(response['raw'] if response else '', legal, self.session.slot_id, decision)
            current = await asyncio.to_thread(self.official.snapshot, copy.deepcopy(self.prefix), battle.battle_tag, boundary=self.boundary)
            _, now = candidates(current)
            ensure_current(rqid, self.latest_rqid, self.request, legal, now, self.session.failure_event.is_set() or self.session.remaining() <= 0)
            chosen = next(c for c in legal if c['id'] == result['choice'])
            self.session.record(dict(type='selection', decision=decision, **result,
                command=chosen['command'], revalidated_request_id=rqid, latest_request_id=self.latest_rqid,
                revalidated_candidates=now))
            await self.ps_client.send_message(chosen['command'], battle.battle_tag, str(rqid))
            self.session.record(dict(type='wire', decision=decision, command=chosen['command'], request_id=rqid, status='sent'))
    return Strategist


async def bot_worker(attempt):
    import numpy as np
    from poke_env.player.baselines import AbyssalPlayer
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from integration.pokechamp.battle_adapter import guard_parser, install_identity_adapter
    from integration.pokechamp.jev_study import play
    from integration.pokechamp import cli
    install_identity_adapter()
    request = json.loads((attempt/'request.json').read_text())
    row = request['slot']; role = 'p2' if row['jev_actor'] == 'p1' else 'p1'
    index = int(role[-1])-1; seed = row['actor_seeds'][index]
    random.seed(seed); np.random.seed(seed)
    class NoTeraAbyssal(AbyssalPlayer):
        def choose_move(self, battle):
            battle._can_tera = False
            order = super().choose_move(battle)
            if 'terastallize' in order.message:
                raise ValueError('Abyssal tera forbidden')
            return order
    player = NoTeraAbyssal(team=request['teams'][row['teams'][index]]['showdown_team'],
        battle_format='gen9ou', max_concurrent_battles=1, start_timer_on_battle_start=False,
        account_configuration=AccountConfiguration(request['names'][role], None),
        server_configuration=ServerConfiguration(f'localhost:{PORT}', 'https://play.pokemonshowdown.com/action.php?'))
    original_send = player.ps_client.send_message
    async def send(message, *args, **kwargs):
        if 'terastallize' in message:
            raise ValueError('Abyssal tera wire forbidden')
        with (attempt/'abyssal-wire.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(message=message, args=args))+'\n')
        return await original_send(message, *args, **kwargs)
    player.ps_client.send_message = send
    guard_parser(player)
    result = dict(completed=False, pid=os.getpid(), actor=role, python_random_seed=seed,
                  numpy_random_seed=seed, python_hash_seed=os.environ.get('PYTHONHASHSEED'))
    try:
        result.update(await play(player, role, request['names'], attempt, deadline=float('inf')))
    except BaseException as exc:
        result['error'] = dict(type=type(exc).__name__, detail=str(exc))
    finally:
        await cli._close_players([player])
        write(attempt/f'{role}.result.json', result)
    return result


async def run(model, manifest):
    import numpy as np
    from poke_env.ps_client.account_configuration import AccountConfiguration
    from poke_env.ps_client.server_configuration import ServerConfiguration
    from integration.pokechamp import cli
    from integration.pokechamp.battle_adapter import install_identity_adapter
    from integration.pokechamp.parallel_server import BattleServer
    from integration.jev27b.battle import play_owned
    from integration.pokechamp.benchmark import terminate
    from .report import audit_events
    from .execute import verify_source
    directory = RUN/'collection'; directory.mkdir(exist_ok=False)
    session = Session(directory, model)
    outcomes = []; error = None
    install_identity_adapter()
    try:
        for number, row in enumerate(manifest['schedule'], 1):
            verify_source(manifest)
            if session.remaining() <= 0 or model.failure:
                raise RuntimeError('collection resource/time limit')
            session.slot_id = row['slot_id']; session.count = 0
            role = row['jev_actor']; other = 'p2' if role == 'p1' else 'p1'
            seed = row['actor_seeds'][int(role[-1])-1]
            identity = hashlib.sha256(f"EX-106:{row['slot_id']}".encode()).hexdigest()[:12]
            names = {role: 'str'+identity, other: 'aby'+identity}
            attempt = directory/f'battle-{number}';attempt.mkdir()
            outcome = dict(slot=number, **row, username=names[role], completed=False)
            outcomes.append(outcome)
            write(attempt/'request.json', dict(slot=row, teams=manifest['teams'], names=names))
            server = BattleServer(attempt, PORT, row['battle_seed'])
            process = log = player = None
            start = len(session.records)
            technical = None
            try:
                await asyncio.to_thread(server.start)
                env = cli._child_environment(PYTHONPATH=f'{ROOT}:{ROOT / "pokechamp"}',
                    PYTHONHASHSEED=str(row['actor_seeds'][int(other[-1])-1]),
                    OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
                log = (attempt/'abyssal.log').open('x')
                process = subprocess.Popen([str(BATTLE_PY), '-m', 'integration.strategist_eval.battle', str(attempt)],
                    cwd=ROOT/'pokechamp', env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                random.seed(seed);np.random.seed(seed)
                player = player_class()(session=session, expected_actor=role,
                    team=manifest['teams'][row['teams'][int(role[-1])-1]]['showdown_team'],
                    battle_format='gen9ou',max_concurrent_battles=1,start_timer_on_battle_start=False,
                    account_configuration=AccountConfiguration(names[role],None),
                    server_configuration=ServerConfiguration(f'localhost:{PORT}','https://play.pokemonshowdown.com/action.php?'))
                outcome.update(await play_owned(player,role,names,attempt,session=session,process=process,server=server))
                await asyncio.to_thread(process.wait,15)
                peer=json.loads((attempt/f'{other}.result.json').read_text())
                complement={'player_won':'player_lost','player_lost':'player_won','tied':'tied'}
                if process.returncode or not peer['completed'] or peer['outcome'] != complement[outcome['outcome']] or peer['turns'] != outcome['turns'] or peer['python_random_seed'] != row['actor_seeds'][int(other[-1])-1]:
                    raise ValueError('peer terminal/seed mismatch')
            except BattleLimit as exc:
                outcome.update(completed=False, outcome='incomplete', error=str(exc))
                session.terminal_error=None;session.failure_event.clear()
            except BaseException as exc:
                technical=exc
                outcome.update(completed=False, outcome='failed', error=dict(type=type(exc).__name__,detail=str(exc)))
            finally:
                write(attempt/'cancel.json',dict(reason='attempt ended'))
                if player:
                    await cli._close_players([player])
                    if player.official:
                        player.official.close()
                if process and process.poll() is None:
                    await asyncio.to_thread(terminate,process)
                if log:
                    log.close()
                await asyncio.to_thread(server.close)
                outcome.update(server_cleaned=not server.created and (server.process is None or server.process.poll() is not None),
                    opponent_cleaned=process is None or process.poll() is not None)
                write(attempt/'outcome.json',outcome)
            check=audit_events(session.records[start:])
            write(attempt/'audit.json',check)
            outcome['audit_passed']=check['passed']
            write(attempt/'outcome.json',outcome)
            write(directory/'progress.json',dict(outcomes=outcomes,calls=model.calls))
            print(json.dumps(dict(slot=number,outcome=outcome.get('outcome'),calls=model.calls)),flush=True)
            if technical:
                raise technical
            if not check['passed']:
                raise RuntimeError('per-battle audit failed: '+repr(check['errors']))
    except BaseException as exc:
        error=dict(type=type(exc).__name__,detail=str(exc))
    result=dict(outcomes=outcomes,error=error,calls=model.calls)
    write(directory/'result.json',result)
    return result


if __name__ == '__main__':
    import sys
    asyncio.run(bot_worker(Path(sys.argv[1])))
