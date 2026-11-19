"""EX-170 local bot-vs-bot games: laya-play's `bot.py` unchanged, with the accept step replaced by a challenge.

    <laya-play battle python> localplay_challenger.py TARGET [bot.py arguments...]     (PYTHONPATH = laya-play app)

Run with laya-play's own interpreter and import path (its `integration` copy, not /workspace's), so this file imports
nothing from `integration.laya_v11`. Every game it sends a gen9ou challenge to TARGET (a `laya_play.bot` waiting on
the same local Showdown) with the next team of its order and plays it with the usual session (events.jsonl,
result.json, `--policy sample` if asked). A challenge is repeated until the target is online and accepts.
"""
import asyncio
import sys

from laya_play import bot as B

TARGET = sys.argv[1]
RETRY_SECONDS = 20
_base = B.challenge_class


def challenge_class(base):
    accepting = _base(base)

    class Challenger(accepting):
        async def _accept_challenges(self, opponent, n_challenges, packed_team):
            await self.ps_client.logged_in.wait()
            if self.bag is not None:
                team_id, _ = self.bag.choose(None)
                team = self.bag.teams[team_id]
                self.use_team(team)
                self.chosen = team_id
                self.log.record(dict(type='team_choice', username=self.username, team_id=team_id, mode='challenge',
                                     target=TARGET))
            while not self.battles:
                await self.ps_client.send_message('/cancelchallenge %s' % TARGET)
                await self.ps_client.challenge(TARGET, self._format, self.next_team)
                for _ in range(RETRY_SECONDS * 5):
                    if self.battles:
                        break
                    await asyncio.sleep(0.2)
            await self._battle_semaphore.acquire()
            await self._battle_count_queue.join()

    return Challenger


B.challenge_class = challenge_class

if __name__ == '__main__':
    sys.exit(B.main(sys.argv[2:]))
