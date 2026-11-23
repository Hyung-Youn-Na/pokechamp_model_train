"""EX-205 (EP-241, D-218): zero-shot EX-200 checkpoint with v13 input bugfixes vs foul-play (no limits).

    python -m integration.laya_v13.battle_v13 {mock,prepare,execute,export} EX-205   (laya env)

Composes `integration.laya_value.battle_value` (lifted wall-clock / turn / decision limits + `actor_unlimited`
engine-panic isolation) and swaps serving / export rendering from `v12` to `v13` (`render_v13` / `serve_v13`).
Existing packages (`foulplay`, `laya_v12`, `laya_value`) are untouched.
Same-slot baseline: EX-201 (same EX-200 checkpoint, same unlimited settings, v12 input).
"""
from __future__ import annotations

import os
import sys
import subprocess
import time

from integration.foulplay import battle as B
from integration.laya_imitation import config as c
from integration.laya_imitation.storage import read, sha
from integration.laya_v12 import battle_v12 as V
from integration.laya_value import battle_value as BV

PACKAGE = c.ROOT / 'integration/laya_v13'
FILES = ('render_v13.py', 'serve_v13.py', 'battle_v13.py')

EX205 = B._v11('EX-205', 'laya-v11rtc', 'v13value-zeroshot', 'EX-200', (8100, 8101, 8102, 8103))
EX205.baseline = ('EX-201 v12value (제한 없음)', c.SHARED / 'runs/model-training/EX-201', lambda r: r['slot_id'])
B.STUDIES['EX-205'] = EX205


def _serving_v13_class():
    from integration.laya_v10 import paths as p10
    base = B._serving_v11_class()

    class ServingV13(base):
        """The foul-play runner's serving started on `integration.laya_v13.serve_v13`."""

        def start(self, env):
            from integration.pokechamp.imitation.player import http_json
            ready = self.directory / ('serving-%s.ready.json' % self.model)
            self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
            child = dict(os.environ, PYTHONPATH='%s:%s' % (p10.LAYA_SOURCE, c.ROOT), PYTHONDONTWRITEBYTECODE='1',
                         HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', **env)
            self.process = subprocess.Popen(
                [str(c.LAYA_PYTHON), '-m', 'integration.laya_v13.serve_v13', '--checkpoint', str(self.checkpoint),
                 '--model', self.model, '--device', self.device, '--ready-file', str(ready)],
                cwd=c.ROOT, env=child, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                start_new_session=True)
            started = time.monotonic()
            while time.monotonic() - started < 300:
                if self.process.poll() is not None:
                    raise RuntimeError('serving exited before readiness')
                if ready.exists():
                    info = read(ready)
                    if not info.get('v13_render'):
                        raise RuntimeError('serving did not report the v13 input')
                    health = http_json(info['endpoint'], '/health', timeout=5)
                    self.identity = dict(health, endpoint=info['endpoint'], pid=self.process.pid,
                                         v11_render=info['v11_render'], v12_render=info['v12_render'],
                                         v13_render=info['v13_render'])
                    return self.identity
                time.sleep(0.5)
            raise RuntimeError('serving readiness timeout')

    return ServingV13


def identity():
    return dict(BV.identity(), laya_v13={n: sha(PACKAGE / n) for n in FILES})


def install():
    BV.install()
    B.ServingV11 = lambda *a, **k: _serving_v13_class()(*a, **k)
    B.identity = identity


def export(study):
    from . import render_v13
    render_v13.install()   # before V.export's render_v12.install() and B.export's render_v11.install()
    return V.export(study)


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(BV.worker(sys.argv[1:]))
    install()
    study = B.STUDIES[sys.argv[2] if len(sys.argv) > 2 else 'EX-205']
    if sys.argv[1] == 'export':
        V._plan_label('EP-241')
        export(study)
    else:
        {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute}[sys.argv[1]](study)
