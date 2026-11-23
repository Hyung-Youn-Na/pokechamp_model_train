"""EX-201 / EX-202 (EP-239, D-217): laya v12 argmax vs foul-play on EX-174's Blim schedule with every limit lifted.

    python -m integration.laya_value.battle_value {mock,prepare,execute,export} EX-201|EX-202   (laya env)

`integration.foulplay.battle` and `integration.laya_v12.battle_v12` unchanged; this composes them as EX-198 does
(v12 serving, argmax, the same 128 slots) and lifts, in this module only (user instruction 2026-11-22: "성능을 보기
위한 실험은 시간 제한을 모두 해제하고 테스트 해주세요"):
- the game wall clock (`laya_imitation.battle.BATTLE_SECONDS`, 1,200 s) and the stage clock (`foulplay.paths.HOURS`);
- the model side's turn and decision limits (`laya_imitation.config.TURN_LIMIT` / `DECISION_LIMIT`, read by the
  worker at call time; this module is the worker entry);
- foul-play's turn and decision limits (`foulplay.paths`, through `actor_unlimited`).
Showdown's own rules (the endless-battle clause) stay. EX-201: EX-200 selected, ports 8100-8103, same-slot baseline
EX-202. EX-202: EX-196 selected (EX-198 again without limits), ports 8104-8107, same-slot baseline EX-198.
"""
from __future__ import annotations

import os
import sys

from integration.foulplay import battle as B
from integration.foulplay import paths as P
from integration.laya_imitation import battle as lab
from integration.laya_imitation import config as c
from integration.laya_imitation.storage import read, sha
from integration.laya_v12 import battle_v12 as V

UNLIMITED = 10 ** 6
lab.BATTLE_SECONDS = 10 ** 8
P.HOURS = 10.0 ** 4
P.TURN_LIMIT = P.DECISION_LIMIT = UNLIMITED
c.TURN_LIMIT = c.DECISION_LIMIT = UNLIMITED
B.WORKER = 'integration.laya_value.battle_value'
PACKAGE = c.ROOT / 'integration/laya_value'

EX201 = B._v11('EX-201', 'laya-v11rtc', 'v12value', 'EX-200', (8100, 8101, 8102, 8103))
EX201.baseline = ('EX-202 v12foe (제한 없음)', c.SHARED / 'runs/model-training/EX-202', lambda r: r['slot_id'])
EX202 = B._v11('EX-202', 'laya-v11rtc', 'v12foe', 'EX-196', (8104, 8105, 8106, 8107))
EX202.baseline = ('EX-198 v12foe (1,200초)', c.SHARED / 'runs/model-training/EX-198', lambda r: r['slot_id'])
B.STUDIES['EX-201'] = EX201
B.STUDIES['EX-202'] = EX202


def identity():
    return dict(V.identity(), laya_value={n: sha(PACKAGE / n) for n in ('battle_value.py', 'actor_unlimited.py')},
                limits=dict(battle_seconds=lab.BATTLE_SECONDS, stage_hours=P.HOURS, turn=P.TURN_LIMIT,
                            decision=P.DECISION_LIMIT, model_turn=c.TURN_LIMIT, model_decision=c.DECISION_LIMIT))


def install():
    V.install()
    B.identity = identity


def worker(argv):
    """The runner's worker: the model side as `foulplay.battle.worker` (limits lifted above); foul-play's side through
    `actor_unlimited` instead of `foulplay.actor`."""
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument('command')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--role', choices=('p1', 'p2'), required=True)
    args = parser.parse_args(argv)
    row = read(args.attempt / 'request.json')['slot']
    if args.role == row['model_side']:
        return B.worker(argv)
    (args.attempt / 'foulplay-team.txt').write_text(B.team_export(row['teams'][args.role]['packed']))
    env = dict(os.environ, PYTHONPATH='%s:%s' % (c.ROOT, P.FP_SOURCE), PYTHONDONTWRITEBYTECODE='1')
    os.execve(str(P.FP_PYTHON), [str(P.FP_PYTHON), '-m', 'integration.laya_value.actor_unlimited',
                                 '--attempt', str(args.attempt), '--role', args.role], env)


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(worker(sys.argv[1:]))
    install()
    study = B.STUDIES[sys.argv[2]]
    if sys.argv[1] == 'export':
        V._plan_label('EP-239')
        V.export(study)
    else:
        {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute}[sys.argv[1]](study)
