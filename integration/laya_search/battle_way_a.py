"""EX-217 (EP-245, D-221): Way A (Laya-Main Consensus Blunder Veto + MCTS 50k + EX-216 V_phi v2 + walled_duel)
vs foul-play Blim 128 on physical GPU 0 ONLY.

    python -m integration.laya_search.battle_way_a {mock,prepare,execute,export} EX-217   (laya env)

- Strictly pins physical GPU 0 (`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`). Physical GPUs 2 & 3 are NEVER touched.
- Serves `EX-200` + `render_v13` + `walled_duel` + `EX-216` Matchup-Aware V_phi v2 + `--way-a --iterations 50000 --workers 4`.
- Includes `_patch_autotie_bigerror` so 500-turn Showdown countdown notices never trigger false `phase_halt`.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

from integration.foulplay import battle as B
from integration.laya_fp1 import battle_fp1 as F
from integration.laya_imitation import config as c
from integration.laya_imitation.storage import read, sha
from integration.laya_v12 import battle_v12 as V
from integration.laya_value import battle_value as BV

from . import battle_search_v2 as B2
from . import search_core as SC
from . import way_a as WA

PACKAGE = c.ROOT / 'integration/laya_search'
EX216_CKPT = c.SHARED / 'runs/model-training/EX-216/checkpoints/selected'

F.MODEL = 'laya-v11rtc'
B.WORKER = 'integration.laya_search.battle_way_a'

EX217 = B._v11('EX-217', 'laya-v11rtc', 'waya50k', 'EX-200', (8100, 8101, 8102, 8103))
EX217.baseline = ('EX-208 search2b-v1 (제한 없음)', c.SHARED / 'runs/model-training/EX-208', lambda r: r['slot_id'])
B.STUDIES['EX-217'] = EX217


def _serving_way_a_gpu0_class():
    from integration.laya_v10 import paths as p10
    base = B._serving_v11_class()

    class ServingWayAGpu0(base):
        """GPU 0 ONLY serving of `integration.laya_search.serve_search --way-a --walled-duel --iterations 50000`."""

        def start(self, env):
            from integration.pokechamp.imitation.player import http_json
            ready = self.directory / ('serving-%s.ready.json' % self.model)
            self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
            child = dict(os.environ)
            child.update(env)
            child.update(
                PYTHONPATH='%s:%s' % (p10.LAYA_SOURCE, c.ROOT),
                PYTHONDONTWRITEBYTECODE='1',
                HF_HUB_OFFLINE='1',
                TOKENIZERS_PARALLELISM='false',
                CUDA_DEVICE_ORDER='PCI_BUS_ID',
                CUDA_VISIBLE_DEVICES=SC.GPU0_UUID,
                OMP_NUM_THREADS='4',
                MKL_NUM_THREADS='4',
            )
            cmd = [
                str(c.LAYA_PYTHON), '-m', 'integration.laya_search.serve_search',
                '--checkpoint', str(self.checkpoint),
                '--value-checkpoint', str(EX216_CKPT),
                '--way-a',
                '--walled-duel',
                '--iterations', str(WA.MCTS_ITERATIONS_WAY_A),
                '--model', self.model,
                '--device', 'cuda',
                '--workers', '4',
                '--ready-file', str(ready),
            ]
            self.process = subprocess.Popen(
                cmd,
                cwd=c.ROOT, env=child, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            started = time.monotonic()
            while time.monotonic() - started < 300:
                if self.process.poll() is not None:
                    raise RuntimeError('serving exited before readiness')
                if ready.exists():
                    info = read(ready)
                    srch = info.get('search') or {}
                    if not info.get('v13_render') or not srch.get('way_a') or not srch.get('walled_duel'):
                        raise RuntimeError('serving missing v13_render / way_a / walled_duel identity: %r' % (srch,))
                    health = http_json(info['endpoint'], '/health', timeout=5)
                    self.identity = dict(
                        health, endpoint=info['endpoint'], pid=self.process.pid,
                        device='cuda:gpu0', gpu_uuid=SC.GPU0_UUID,
                        v11_render=info['v11_render'], v12_render=info['v12_render'],
                        v13_render=info['v13_render'], search=srch,
                    )
                    return self.identity
                time.sleep(0.5)
            raise RuntimeError('serving readiness timeout')

    return ServingWayAGpu0


def identity():
    v13_dir = c.ROOT / 'integration/laya_v13'
    files = ('search_core.py', 'search_worker.py', 'serve_search.py', 'featurize.py',
             'matchup_features.py', 'value_model_v2.py', 'search_2b.py', 'search_2b_v2.py',
             'way_a.py', 'battle_way_a.py')
    return dict(
        BV.identity(),
        laya_v13={n: sha(v13_dir / n) for n in ('render_v13.py', 'serve_v13.py')},
        laya_way_a={n: sha(PACKAGE / n) for n in files},
        ex216_checkpoint={
            n: sha(EX216_CKPT / n) for n in ('config.json', 'weights.pt') if (EX216_CKPT / n).exists()
        },
        device_policy='physical GPU 0 ONLY (%s); GPUs 2 & 3 never touched' % SC.GPU0_UUID,
    )


def install():
    BV.install()
    B.ServingV11 = lambda *a, **k: _serving_way_a_gpu0_class()(*a, **k)
    B.identity = identity


def export(study):
    from integration.laya_imitation import viewer
    from integration.laya_v13 import render_v13
    render_v13.install()
    WA.install_walled_duel()
    original = viewer.export
    suffix = ' 선택은 v13+walled_duel 입력 · Laya 메인 합의형 블런더 가드(방식 A) + MCTS 50k + EX-216 매치업 가치망 V_phi v2 결과입니다.'

    def labelled(run, output, meta, **kw):
        meta = dict(meta, plan='EP-245', intro=meta['intro'] + suffix)
        return original(run, output, meta=meta, **kw)

    viewer.export = labelled
    try:
        return V.export(study)
    finally:
        viewer.export = original


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(B2.worker(sys.argv[1:]))
    install()
    study = B.STUDIES[sys.argv[2] if len(sys.argv) > 2 else 'EX-217']
    if sys.argv[1] == 'export':
        export(study)
    else:
        {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute}[sys.argv[1]](study)
