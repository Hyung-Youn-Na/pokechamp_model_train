"""EX-212 (EP-244, D-220): 2-B v2 online search (CPU serving, parallel with EX-213 GPU 0·1 DDP) vs foul-play Blim 128.

    python -m integration.laya_search.battle_search_v2 {mock,prepare,execute,export} EX-212   (laya env)

- Serves `EX-200` + `v13` + `EX-207` V_phi with `--v2 --device cpu` (`CUDA_VISIBLE_DEVICES=''`, `OMP_NUM_THREADS=4`),
  leaving physical GPUs 0 & 1 completely free for EX-213 DDP training (and GPUs 2 & 3 untouched).
- Adds a non-invasive guard in the EX-212 model worker that ignores Showdown's harmless 500-turn countdown notice
  (`|bigerror|You will auto-tie...`) while keeping strict error raising on every real battle action rejection.
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

PACKAGE = c.ROOT / 'integration/laya_search'
EX207_CKPT = c.SHARED / 'runs/model-training/EX-207/checkpoints/selected'

F.MODEL = 'laya-v11rtc'
B.WORKER = 'integration.laya_search.battle_search_v2'

EX212 = B._v11('EX-212', 'laya-v11rtc', 'search2bv2', 'EX-200', (8100, 8101, 8102, 8103))
EX212.baseline = ('EX-208 search2b-v1 (제한 없음)', c.SHARED / 'runs/model-training/EX-208', lambda r: r['slot_id'])
B.STUDIES['EX-212'] = EX212


def _serving_search_v2_cpu_class():
    from integration.laya_v10 import paths as p10
    base = B._serving_v11_class()

    class ServingSearchV2Cpu(base):
        """CPU serving of `integration.laya_search.serve_search --v2` (0 GPU, OMP_NUM_THREADS=4)."""

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
                CUDA_VISIBLE_DEVICES='',
                OMP_NUM_THREADS='4',
                MKL_NUM_THREADS='4',
            )
            cmd = [
                str(c.LAYA_PYTHON), '-m', 'integration.laya_search.serve_search',
                '--checkpoint', str(self.checkpoint),
                '--value-checkpoint', str(EX207_CKPT),
                '--v2',
                '--model', self.model,
                '--device', 'cpu',
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
                    if not info.get('v13_render') or not (info.get('search') or {}).get('v2'):
                        raise RuntimeError('serving did not report v13_render and search v2 identity')
                    health = http_json(info['endpoint'], '/health', timeout=5)
                    self.identity = dict(
                        health, endpoint=info['endpoint'], pid=self.process.pid,
                        device='cpu',
                        v11_render=info['v11_render'], v12_render=info['v12_render'],
                        v13_render=info['v13_render'], search=info['search'],
                    )
                    return self.identity
                time.sleep(0.5)
            raise RuntimeError('serving readiness timeout')

    return ServingSearchV2Cpu


def identity():
    v13_dir = c.ROOT / 'integration/laya_v13'
    files = ('search_core.py', 'search_worker.py', 'serve_search.py', 'featurize.py',
             'value_model.py', 'search_2b.py', 'search_2b_v2.py', 'battle_search_v2.py')
    return dict(
        BV.identity(),
        laya_v13={n: sha(v13_dir / n) for n in ('render_v13.py', 'serve_v13.py')},
        laya_search_v2={n: sha(PACKAGE / n) for n in files},
        ex207_checkpoint={
            n: sha(EX207_CKPT / n) for n in ('config.json', 'vocab.json', 'weights.pt') if (EX207_CKPT / n).exists()
        },
        device_policy='cpu (OMP_NUM_THREADS=4, parallel with EX-213 GPU 0·1 DDP)',
    )


def install():
    BV.install()
    B.ServingV11 = lambda *a, **k: _serving_search_v2_cpu_class()(*a, **k)
    B.identity = identity


def export(study):
    from integration.laya_imitation import viewer
    from integration.laya_v13 import render_v13
    render_v13.install()
    original = viewer.export
    suffix = ' 선택은 v13 입력 + 2-B v2(foe PP 수정·스케일 매칭 V_phi·duel lose 완화·Taunt 흡수 보정, CPU 서빙) 결과입니다.'

    def labelled(run, output, meta, **kw):
        meta = dict(meta, plan='EP-244', intro=meta['intro'] + suffix)
        return original(run, output, meta=meta, **kw)

    viewer.export = labelled
    try:
        return V.export(study)
    finally:
        viewer.export = original


def _patch_autotie_bigerror():
    """Non-invasively rewrite Showdown's harmless 500-turn `|bigerror|You will auto-tie...` notice into a plain
    info line before `jev_battle._handle_battle_message` checks for `|bigerror|`, avoiding false `phase_halt`."""
    from integration.pokechamp import jev_battle
    orig_player_class = jev_battle.player_class

    def wrapped_player_class(*a, **kw):
        cls = orig_player_class(*a, **kw)

        class SafeAutoTiePlayer(cls):
            async def _handle_battle_message(self, messages):
                cleaned = []
                for fields in messages:
                    if (len(fields) >= 3 and fields[1] == 'bigerror'
                            and 'auto-tie' in '|'.join(fields).lower()):
                        cleaned.append(['', 'raw', '|'.join(fields[2:])])
                    else:
                        cleaned.append(fields)
                return await super()._handle_battle_message(cleaned)

        return SafeAutoTiePlayer

    jev_battle.player_class = wrapped_player_class


def worker(argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--role', choices=('p1', 'p2'), required=True)
    args = parser.parse_args(argv)
    row = read(args.attempt / 'request.json')['slot']
    if args.role == row['model_side']:
        from integration.pokechamp.imitation import player as p
        _patch_autotie_bigerror()
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
    install()
    study = B.STUDIES[sys.argv[2] if len(sys.argv) > 2 else 'EX-212']
    if sys.argv[1] == 'export':
        export(study)
    else:
        {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute}[sys.argv[1]](study)
