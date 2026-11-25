"""EP-249 / D-225: Parallel Blim 128 foul-play evaluation for EX-226 (Way B) & EX-225 (Way C-1 Clean).

    python -m integration.laya_search.battle_ep249 {mock,prepare,execute,export} EX-227   # GPU 0, ports 8100..8103 (EX-226 Way B)
    python -m integration.laya_search.battle_ep249 {mock,prepare,execute,export} EX-228   # GPU 1, ports 8104..8107 (EX-225 standalone no-search)
    python -m integration.laya_search.battle_ep249 {mock,prepare,execute,export} EX-229   # GPU 1, ports 8104..8107 (EX-225 + Way A v2 noduel)

Strict GPU isolation:
- EX-227 pins physical GPU 0 ONLY (`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`).
- EX-228 & EX-229 pin physical GPU 1 ONLY (`GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`).
- Physical GPUs 2 & 3 are NEVER touched.
- Includes `_patch_autotie_bigerror` via `battle_search_v2.worker`.
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
EX221_CKPT = c.SHARED / 'runs/model-training/EX-221/checkpoints/selected'

F.MODEL = 'laya-v11rtc'
B.WORKER = 'integration.laya_search.battle_ep249'

# Track 1 (GPU 0, ports 8100..8103): EX-226 Way B (calc-duel-free + matchup: + eval: prompt injection, 100% Laya final decision)
EX227 = B._v11('EX-227', 'laya-v11rtc', 'ex226_wayb_noduel', 'EX-226', (8100, 8101, 8102, 8103))
EX227.baseline = ('EX-223 waya_v2_2ply (역대 최고 0.414)', c.SHARED / 'runs/model-training/EX-223', lambda r: r['slot_id'])

# Track 2-A (GPU 1, ports 8104..8107): EX-225 Way C-1 Clean standalone (no search, v14+walled_duel)
EX228 = B._v11('EX-228', 'laya-v11rtc', 'ex225_standalone', 'EX-225', (8104, 8105, 8106, 8107))
EX228.baseline = ('EX-205 EX-200 v13 단독 (0.315)', c.SHARED / 'runs/model-training/EX-205', lambda r: r['slot_id'])

# Track 2-B (GPU 1, ports 8104..8107): EX-225 Way C-1 Clean + Way A v2 (calc-duel-free + V_phi v3 2-ply + MCTS 50k)
EX229 = B._v11('EX-229', 'laya-v11rtc', 'ex225_waya_v2_noduel', 'EX-225', (8104, 8105, 8106, 8107))
EX229.baseline = ('EX-223 waya_v2_2ply (역대 최고 0.414)', c.SHARED / 'runs/model-training/EX-223', lambda r: r['slot_id'])

B.STUDIES['EX-227'] = EX227
B.STUDIES['EX-228'] = EX228
B.STUDIES['EX-229'] = EX229

STUDY_CFG = {
    'EX-227': dict(
        gpu_uuid=SC.GPU0_UUID,
        gpu_label='cuda:gpu0',
        flags=['--v14', '--way-b', '--two-ply', '--walled-duel', '--no-calc-duel',
               '--value-checkpoint', str(EX221_CKPT),
               '--iterations', str(WA.MCTS_ITERATIONS_WAY_A), '--workers', '4'],
        require_keys=('way_b', 'two_ply', 'no_calc_duel'),
        viewer_suffix=' 선택은 EX-226 Way B(calc-duel-free + MCTS 50k/V_phi v3 5단계 matchup & eval 프롬프트 주입, Laya 100% 단독 최종결정) 결과입니다.',
    ),
    'EX-228': dict(
        gpu_uuid=SC.GPU1_UUID,
        gpu_label='cuda:gpu1',
        flags=['--v14', '--walled-duel', '--no-search'],
        require_keys=('no_search',),
        viewer_suffix=' 선택은 EX-225 Way C-1 정화판(v14+walled_duel) 무탐색 단독 추론 결과입니다.',
    ),
    'EX-229': dict(
        gpu_uuid=SC.GPU1_UUID,
        gpu_label='cuda:gpu1',
        flags=['--v14', '--way-a-v2', '--two-ply', '--walled-duel', '--no-calc-duel',
               '--value-checkpoint', str(EX221_CKPT),
               '--iterations', str(WA.MCTS_ITERATIONS_WAY_A), '--workers', '4'],
        require_keys=('way_a_v2', 'two_ply', 'no_calc_duel'),
        viewer_suffix=' 선택은 EX-225 Way C-1 정화판(v14, calc-duel-free) + 방식 A v2(MCTS 50k + EX-221 V_phi v3 2-ply 5단계 유불리 가드) 결과입니다.',
    ),
}

_ACTIVE_STUDY = 'EX-227'


def _serving_ep249_class(study_id: str):
    from integration.laya_v10 import paths as p10
    base = B._serving_v11_class()
    cfg = STUDY_CFG[study_id]

    class ServingEP249(base):
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
                CUDA_VISIBLE_DEVICES=cfg['gpu_uuid'],
                OMP_NUM_THREADS='4',
                MKL_NUM_THREADS='4',
            )
            cmd = [
                str(c.LAYA_PYTHON), '-m', 'integration.laya_search.serve_search',
                '--checkpoint', str(self.checkpoint),
                *cfg['flags'],
                '--model', self.model,
                '--device', 'cuda',
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
                    missing = [k for k in cfg['require_keys'] if not srch.get(k)]
                    if not info.get('v14_render') or missing:
                        raise RuntimeError('serving missing v14_render or %r: %r' % (missing, srch))
                    health = http_json(info['endpoint'], '/health', timeout=5)
                    self.identity = dict(
                        health, endpoint=info['endpoint'], pid=self.process.pid,
                        device=cfg['gpu_label'], gpu_uuid=cfg['gpu_uuid'],
                        v11_render=info['v11_render'], v12_render=info['v12_render'],
                        v13_render=info['v13_render'], v14_render=info['v14_render'],
                        search=srch,
                    )
                    return self.identity
                time.sleep(0.5)
            raise RuntimeError('serving readiness timeout')

    return ServingEP249


def identity():
    v14_dir = c.ROOT / 'integration/laya_v14'
    files = ('search_core.py', 'search_worker.py', 'serve_search.py', 'featurize.py',
             'featurize_v3.py', 'matchup_features.py', 'value_model_v2.py', 'value_model_v3.py',
             'search_2b.py', 'search_2b_v2.py', 'search_multiturn.py',
             'way_a.py', 'way_a_v2.py', 'matchup_eval.py', 'battle_ep249.py')
    cfg = STUDY_CFG[_ACTIVE_STUDY]
    return dict(
        BV.identity(),
        laya_v14={n: sha(v14_dir / n) for n in ('render_v14.py', 'data_way_b.py') if (v14_dir / n).exists()},
        laya_ep249={n: sha(PACKAGE / n) for n in files if (PACKAGE / n).exists()},
        ex221_checkpoint={
            n: sha(EX221_CKPT / n) for n in ('config.json', 'weights.pt') if (EX221_CKPT / n).exists()
        },
        device_policy='physical %s ONLY (%s); GPUs 2 & 3 never touched' % (cfg['gpu_label'], cfg['gpu_uuid']),
    )


def install(study_id: str):
    global _ACTIVE_STUDY
    _ACTIVE_STUDY = study_id
    BV.install()
    B.ServingV11 = lambda *a, **k: _serving_ep249_class(study_id)(*a, **k)
    B.identity = identity


def export(study):
    from integration.laya_imitation import viewer
    from integration.laya_v14 import render_v14
    render_v14.install()
    WA.install_walled_duel()
    original = viewer.export
    suffix = STUDY_CFG[study.experiment]['viewer_suffix']

    def labelled(run, output, meta, **kw):
        meta = dict(meta, plan='EP-249', intro=meta['intro'] + suffix)
        return original(run, output, meta=meta, **kw)

    viewer.export = labelled
    try:
        return V.export(study)
    finally:
        viewer.export = original


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(B2.worker(sys.argv[1:]))
    sid = sys.argv[2] if len(sys.argv) > 2 else 'EX-227'
    install(sid)
    study = B.STUDIES[sid]
    if sys.argv[1] == 'export':
        export(study)
    else:
        {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute}[sys.argv[1]](study)
