"""EX-184 / EX-185 / EX-187 (D-214, D-215): v11-input laya models vs foul-play on EX-174's sealed Blim schedule.

    python -m integration.laya_distill.battle_distill {mock,prepare,execute,export} EX-184|EX-185|EX-187   (laya env)

`integration.foulplay.battle` unchanged (EP-232/233's runner); the studies are EX-176's (`battle._v11`: v11 input
via `serve_v11`, CPU serving, argmax, same-slot baseline EX-174) with another checkpoint:
- EX-184: EX-172 selected (v11rtc, the complete 128-slot baseline EX-176 did not finish);
- EX-185: EX-183 selected (distilled); EX-187: EX-186 selected (reinforcement learning).
The serving model name stays `laya-v11rtc` (`serve_v11.MODELS`, read by worker processes that do not import this
module); the checkpoint (and its sha256 in the run identity) tells the models apart.
"""
from __future__ import annotations

import sys

from integration.foulplay import battle as B

PORTS = (8100, 8101, 8102, 8103)
B.STUDIES['EX-184'] = B._v11('EX-184', 'laya-v11rtc', 'v11rtc', 'EX-172', PORTS)
B.STUDIES['EX-185'] = B._v11('EX-185', 'laya-v11rtc', 'v11d', 'EX-183', PORTS)
B.STUDIES['EX-187'] = B._v11('EX-187', 'laya-v11rtc', 'v11drl', 'EX-186', PORTS)


def _plan_label():
    """The viewer and report name EP-236 (the runner names EP-233 for every v11 study)."""
    from integration.laya_imitation import viewer
    original = viewer.export

    def export(run, output, meta, **kw):
        return original(run, output, meta=dict(meta, plan='EP-236'), **kw)
    viewer.export = export


if __name__ == '__main__':
    study = B.STUDIES[sys.argv[2]]
    if sys.argv[1] == 'export':
        _plan_label()
    {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute, 'export': B.export}[sys.argv[1]](study)
