"""EX-206 (EP-243, D-219): 2-A online multi-turn search (EX-200 + v13 + GPU 0 + MCTS 5k prior fusion) vs foul-play.

    python -m integration.laya_search.battle_search {mock,prepare,execute,export} EX-206   (laya env)

Strictly binds serving to physical GPU 0 (`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`); GPUs 2 and 3 are NEVER touched.
Composes:
- `integration.laya_value.battle_value`: lifts all wall-clock / turn / decision limits + `actor_unlimited` panic isolation;
- `integration.laya_fp1.battle_fp1`: `Fp1Session` on model side + `fp1` audit;
- `integration.laya_v13.render_v13`: v13 rendering on serving and viewer export;
- `integration.laya_search.serve_search`: GPU 0 serving + 4-lane Rust MCTS 5k + KL-regularized prior fusion.
Existing packages are untouched.
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

from . import search_core as SC

PACKAGE = c.ROOT / 'integration/laya_search'
FILES = ('search_core.py', 'search_worker.py', 'serve_search.py', 'battle_search.py')

F.MODEL = 'laya-v11rtc'
B.WORKER = 'integration.laya_search.battle_search'

EX206 = B._v11('EX-206', 'laya-v11rtc', 'search2a', 'EX-200', (8100, 8101, 8102, 8103))
EX206.baseline = ('EX-205 v13value-zeroshot (제한 없음)', c.SHARED / 'runs/model-training/EX-205', lambda r: r['slot_id'])
B.STUDIES['EX-206'] = EX206

EX207_CKPT = c.SHARED / 'runs/model-training/EX-207/checkpoints/selected'
EX208 = B._v11('EX-208', 'laya-v11rtc', 'search2b', 'EX-200', (8100, 8101, 8102, 8103))
EX208.baseline = ('EX-205 v13value-zeroshot (제한 없음)', c.SHARED / 'runs/model-training/EX-205', lambda r: r['slot_id'])
B.STUDIES['EX-208'] = EX208

_ACTIVE_STUDY = 'EX-206'


def _serving_search_class():
    from integration.laya_v10 import paths as p10
    base = B._serving_v11_class()

    class ServingSearch(base):
        """GPU 0 serving started on `integration.laya_search.serve_search` (physical GPU 0 UUID pinned)."""

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
            # Strictly pin physical GPU 0 only (GPUs 2 and 3 are reserved for another project)
            child['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
            child['CUDA_VISIBLE_DEVICES'] = SC.GPU0_UUID
            cmd = [
                str(c.LAYA_PYTHON), '-m', 'integration.laya_search.serve_search',
                '--checkpoint', str(self.checkpoint), '--model', self.model,
                '--device', 'cuda', '--ready-file', str(ready),
            ]
            if _ACTIVE_STUDY == 'EX-208':
                cmd += ['--value-checkpoint', str(EX207_CKPT)]
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
                    if not info.get('v13_render') or not info.get('search'):
                        raise RuntimeError('serving did not report v13_render and search identity')
                    health = http_json(info['endpoint'], '/health', timeout=5)
                    self.identity = dict(
                        health, endpoint=info['endpoint'], pid=self.process.pid,
                        device='cuda', gpu=0, gpu_uuid=SC.GPU0_UUID,
                        v11_render=info['v11_render'], v12_render=info['v12_render'],
                        v13_render=info['v13_render'], search=info['search'],
                    )
                    return self.identity
                time.sleep(0.5)
            raise RuntimeError('serving readiness timeout')

    return ServingSearch


def identity():
    v13_dir = c.ROOT / 'integration/laya_v13'
    out = dict(
        BV.identity(),
        laya_v13={n: sha(v13_dir / n) for n in ('render_v13.py', 'serve_v13.py')},
        laya_search={n: sha(PACKAGE / n) for n in FILES},
        gpu_policy=dict(device='cuda', gpu=0, gpu_uuid=SC.GPU0_UUID, allowed_uuids=list(SC.ALLOWED_GPU_UUIDS)),
    )
    if _ACTIVE_STUDY == 'EX-208':
        out['laya_search_2b'] = {n: sha(PACKAGE / n) for n in ('featurize.py', 'value_model.py', 'search_2b.py')}
        out['ex207_checkpoint'] = {
            n: sha(EX207_CKPT / n) for n in ('config.json', 'vocab.json', 'weights.pt') if (EX207_CKPT / n).exists()
        }
    return out


def install():
    BV.install()
    B.ServingV11 = lambda *a, **k: _serving_search_class()(*a, **k)
    B.identity = identity


def export(study):
    from integration.laya_imitation import viewer
    from integration.laya_v13 import render_v13
    render_v13.install()
    original = viewer.export
    suffix = (
        ' 선택은 v13 입력 + 다중턴 MCTS(5,000회) Q값 + EX-207 신경망 상태가치 V_phi + laya 사전확률 융합(2-B) 결과입니다.'
        if study.experiment == 'EX-208'
        else ' 선택은 v13 입력 + 다중턴 MCTS(5,000회) Q값과 laya 사전확률 융합(2-A) 결과입니다.'
    )

    def labelled(run, output, meta, **kw):
        meta = dict(meta, plan='EP-243', intro=meta['intro'] + suffix)
        return original(run, output, meta=meta, **kw)

    viewer.export = labelled
    try:
        return V.export(study)
    finally:
        viewer.export = original


def worker(argv):
    """Model side: `Fp1Session` over `LimitedSession` (limits lifted by `battle_value`). Foul-play: `actor_unlimited`."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--role', choices=('p1', 'p2'), required=True)
    args = parser.parse_args(argv)
    row = read(args.attempt / 'request.json')['slot']
    if args.role == row['model_side']:
        from integration.pokechamp.imitation import player as p
        original = p.worker

        async def wrapped(attempt, role):
            slot = read(Path(attempt) / 'request.json')['slot']
            if role == slot['model_side'] and slot['model'] == F.MODEL:
                F.install_session()
            return await original(attempt, role)

        p.worker = wrapped
        return B.worker(argv)
    return BV.worker(argv)


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(worker(sys.argv[1:]))
    _ACTIVE_STUDY = sys.argv[2] if len(sys.argv) > 2 else 'EX-206'
    install()
    study = B.STUDIES[_ACTIVE_STUDY]
    if sys.argv[1] == 'export':
        export(study)
    else:
        {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute}[sys.argv[1]](study)
