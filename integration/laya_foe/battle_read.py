"""EX-197 (EP-238, D-216): laya v12 + opponent prediction + one-turn read (EX-196 selected) vs foul-play, Blim 128 slots.

    python -m integration.laya_foe.battle_read {mock,prepare,execute,export} EX-197   (laya env)

`integration.foulplay.battle` unchanged; this composes the existing wrappers:
- `laya_fp1.battle_fp1`: `Fp1Session` on the model side (put on top of the early-history session, `worker`) (the `fp1` member: public prefix, own sets, snapshot, decision
  kind, previous choice) and its audit (the member checked, then the shared audit on the stripped events), both
  keyed on `battle_fp1.MODEL`, set here to this study's model name;
- `laya_v12.battle_v12`: the v12 renderer check, frozen identity (+ v12 files) and the EX-174 report line;
- serving: `integration.laya_foe.serve_read` (v12 input, opponent question, `read_worker`), which must report `read`.
Same-slot baseline: EX-193 (v12 argmax). The model name stays `laya-v11rtc` (battle workers read `serve_v11.MODELS`).
The viewer shows laya's input with the served probabilities (laya's with the read pick exchanged); the read itself
(laya p, opponent q, values, pick) is in every recorded serving answer (`read`).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from integration.foulplay import battle as B
from integration.laya_fp1 import battle_fp1 as F
from integration.laya_imitation import config as c
from integration.laya_imitation.storage import read, sha
from integration.laya_v12 import battle_v12 as V

PORTS = (8100, 8101, 8102, 8103)
EX193 = c.SHARED / 'runs/model-training/EX-193'
PACKAGE = c.ROOT / 'integration/laya_foe'
F.MODEL = 'laya-v11rtc'
B.WORKER = 'integration.laya_foe.battle_read'
STUDY = B._v11('EX-197', 'laya-v11rtc', 'read', 'EX-196', PORTS)
STUDY.baseline = ('EX-193 v12', EX193, lambda r: r['slot_id'])
B.STUDIES['EX-197'] = STUDY


def _serving_class():
    from integration.laya_v10 import paths as p10
    base = B._serving_v11_class()

    class ServingRead(base):
        def start(self, env):
            from integration.pokechamp.imitation.player import http_json
            ready = self.directory / ('serving-%s.ready.json' % self.model)
            self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
            child = dict(os.environ, PYTHONPATH='%s:%s' % (p10.LAYA_SOURCE, c.ROOT), PYTHONDONTWRITEBYTECODE='1',
                         HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', **env)
            self.process = subprocess.Popen(
                [str(c.LAYA_PYTHON), '-m', 'integration.laya_foe.serve_read', '--checkpoint', str(self.checkpoint),
                 '--model', self.model, '--device', self.device, '--ready-file', str(ready)],
                cwd=c.ROOT, env=child, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                start_new_session=True)
            started = time.monotonic()
            while time.monotonic() - started < 300:
                if self.process.poll() is not None:
                    raise RuntimeError('serving exited before readiness')
                if ready.exists():
                    info = read(ready)
                    if not info.get('read') or not info.get('v12_render'):
                        raise RuntimeError('serving did not report the v12 input and the read')
                    health = http_json(info['endpoint'], '/health', timeout=5)
                    self.identity = dict(health, endpoint=info['endpoint'], pid=self.process.pid,
                                         v11_render=info['v11_render'], v12_render=info['v12_render'],
                                         read=info['read'])
                    return self.identity
                time.sleep(0.5)
            raise RuntimeError('serving readiness timeout')

    return ServingRead


def identity():
    return dict(V.identity(), laya_foe={p.name: sha(p) for p in sorted(PACKAGE.glob('*.py'))})


def _ex174_line(out, result, viewer, study):
    V.write_report(out, result, viewer, study)          # B's report + the EX-174 line


def install():
    V.install()
    B.ServingV11 = lambda *a, **k: _serving_class()(*a, **k)
    B.identity = identity


def _plan_label():
    from integration.laya_imitation import viewer
    original = viewer.export

    def labelled(run, output, meta, **kw):
        meta = dict(meta, plan='EP-238', intro=meta['intro'] + ' 선택은 한 턴 읽기를 거친 수이고, 표시 확률은 laya 확률에서 '
                                                         '고른 수와 laya 1순위의 값을 맞바꾼 것입니다.')
        return original(run, output, meta=meta, **kw)
    viewer.export = labelled


def worker(argv):
    """The runner's worker with `Fp1Session` as the outermost session class on the model side.

    `laya_imitation.battle.worker` builds its `LimitedSession` (early history for the v10/v11 models) when the game
    starts and its `generate` does not call the parent's, so `battle_fp1.install_session` (applied before) would be
    skipped. Here the fp1 session is put on top of whatever session class `player.worker` is about to use."""
    from integration.pokechamp.imitation import player as p
    original = p.worker

    async def wrapped(attempt, role):
        row = read(Path(attempt) / 'request.json')['slot']
        if role == row['model_side'] and row['model'] == F.MODEL:
            F.install_session()                     # Fp1Session(p.Session = LimitedSession)
        return await original(attempt, role)
    p.worker = wrapped
    return B.worker(argv)


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(worker(sys.argv[1:]))
    install()
    command = sys.argv[1]
    if command == 'export':
        _plan_label()
        V.export(STUDY)
    else:
        {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute}[command](STUDY)
