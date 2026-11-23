"""EX-210 (EP-243, D-219, 1-B): Trained EX-209 single-forward policy (`v13` serving, argmax) vs foul-play (no limits).

    python -m integration.laya_search.battle_1b {mock,prepare,execute,export} EX-210   (laya env)

Pure single-forward evaluation (no online search) on `v13` serving (`integration.laya_v13.serve_v13`), strictly
isolating the offline MCTS-5k root-Q target training gain against `EX-205` (`EX-200` + `v13`, same unlimited slots)
and `EX-201` (`EX-200` + `v12`). Uses physical GPU 0 serving (`GPU-4f27dd5a-...`, ~2 GB VRAM, 44ms/turn) or CPU.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

from integration.foulplay import battle as B
from integration.laya_imitation import config as c
from integration.laya_imitation.storage import read, sha
from integration.laya_v12 import battle_v12 as V
from integration.laya_value import battle_value as BV

from . import search_core as SC

PACKAGE = c.ROOT / 'integration/laya_search'

EX210 = B._v11('EX-210', 'laya-v11rtc', 'mcts5k1b-v13', 'EX-209', (8100, 8101, 8102, 8103))
EX210.baseline = ('EX-205 v13value-zeroshot (제한 없음)', c.SHARED / 'runs/model-training/EX-205', lambda r: r['slot_id'])
B.STUDIES['EX-210'] = EX210


def _serving_v13_gpu0_class():
    from integration.laya_v10 import paths as p10
    base = B._serving_v11_class()

    class ServingV13Gpu0(base):
        def start(self, env):
            from integration.pokechamp.imitation.player import http_json
            ready = self.directory / ('serving-%s.ready.json' % self.model)
            self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
            child = dict(
                os.environ,
                PYTHONPATH='%s:%s' % (p10.LAYA_SOURCE, c.ROOT),
                PYTHONDONTWRITEBYTECODE='1',
                HF_HUB_OFFLINE='1',
                TOKENIZERS_PARALLELISM='false',
                **env,
            )
            child['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
            child['CUDA_VISIBLE_DEVICES'] = SC.GPU0_UUID
            self.process = subprocess.Popen(
                [str(c.LAYA_PYTHON), '-m', 'integration.laya_v13.serve_v13',
                 '--checkpoint', str(self.checkpoint), '--model', self.model,
                 '--device', 'cuda', '--ready-file', str(ready)],
                cwd=c.ROOT, env=child, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            started = time.monotonic()
            while time.monotonic() - started < 300:
                if self.process.poll() is not None:
                    raise RuntimeError('serving exited before readiness')
                if ready.exists():
                    info = read(ready)
                    if not info.get('v13_render'):
                        raise RuntimeError('serving did not report v13_render')
                    health = http_json(info['endpoint'], '/health', timeout=5)
                    self.identity = dict(
                        health, endpoint=info['endpoint'], pid=self.process.pid,
                        device='cuda', gpu=0, gpu_uuid=SC.GPU0_UUID,
                        v11_render=info['v11_render'], v12_render=info['v12_render'], v13_render=info['v13_render'],
                    )
                    return self.identity
                time.sleep(0.5)
            raise RuntimeError('serving readiness timeout')

    return ServingV13Gpu0


def identity():
    v13_dir = c.ROOT / 'integration/laya_v13'
    return dict(
        BV.identity(),
        laya_v13={n: sha(v13_dir / n) for n in ('render_v13.py', 'serve_v13.py')},
        laya_search_1b={n: sha(PACKAGE / n) for n in ('data_mcts_1b.py', 'train_mcts_1b.py', 'battle_1b.py')},
        gpu_policy=dict(device='cuda', gpu=0, gpu_uuid=SC.GPU0_UUID),
    )


def install():
    BV.install()
    B.ServingV11 = lambda *a, **k: _serving_v13_gpu0_class()(*a, **k)
    B.identity = identity


def export(study):
    from integration.laya_v13 import render_v13
    render_v13.install()
    V._plan_label('EP-243')
    return V.export(study)


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(BV.worker(sys.argv[1:]))
    install()
    study = B.STUDIES[sys.argv[2] if len(sys.argv) > 2 else 'EX-210']
    if sys.argv[1] == 'export':
        export(study)
    else:
        {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute}[sys.argv[1]](study)
