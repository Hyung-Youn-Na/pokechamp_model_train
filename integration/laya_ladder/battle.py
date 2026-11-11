"""EX-168: v10t (EX-161) vs v10rt (EX-167) on the sealed EX-120 schedule vs Abyssal, GPU0 / port 8107 (D-208).

`laya_v10.battle_v10` with one more v10 model: `laya-v10rt` renders `v10`, is served by `integration.laya_ladder.serve`
(serve_v10 with the name added) and gets `early_history` in its workers' requests. Everything else -- schedule,
ledger, audits, verdict, export -- is `laya_imitation.comparison` through `battle_v10`.
"""
from __future__ import annotations
import functools
import json
import os
import subprocess
import sys
import time

from integration.laya_imitation import battle, comparison
from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic, read, seal, sha
from integration.laya_v10 import battle_v10, paths as p10

from . import paths
from .serve import MODEL

MODELS = battle_v10.MODELS + (MODEL,)
WORKER = 'integration.laya_ladder.battle'

EX168 = comparison.Study(
    experiment='EX-168', plan='EP-230', seed=20261068, models=('laya-v10t', MODEL), out=paths.RUN_COMPARE,
    viewer=paths.VIEWER_COMPARE, gpu=p10.GPU, port=p10.PORT, hours=c.COMPARE_HOURS,
    runs={'laya-v10t': ('EX-161', paths.V10_RUN), MODEL: ('EX-167', paths.RUN_TRAINING)},
    mock_model='laya-v10t-initial', replicate=None, margin=0.05,
    verdicts=('최근 래더 자료가 배틀 성적을 개선', '퇴보를 배제하지 못함', '비퇴보'),
    meta=dict(experiment='EX-168', plan='EP-230', slug='ex168', pairs=128,
              title='EX-168 · laya v10t·v10rt 256경기',
              heading='EX-168 · laya v10t(EX-161)과 v10 + 최근 래더 자료(EX-167) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. 두 모델 모두 v10 입력(2,048토큰)이고, '
                    'v10rt는 학습 자료에 레이팅 1500 이상 최근 래더 경기를 더했습니다. 확률은 행동 선택 확률이고 '
                    '승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex148-laya-v1'))


class Serving(battle_v10.Serving):
    """`battle_v10.Serving`; the EX-167 model is served by `integration.laya_ladder.serve`."""

    def start(self, env):
        if self.model != MODEL:
            return super().start(env)
        from integration.pokechamp.imitation.player import http_json
        ready = self.directory / ('serving-%s.ready.json' % self.model)
        self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
        child = dict(os.environ, PYTHONPATH='%s:%s' % (p10.LAYA_SOURCE, c.ROOT), PYTHONDONTWRITEBYTECODE='1',
                     HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', **env)
        self.process = subprocess.Popen(
            [str(c.LAYA_PYTHON), '-m', 'integration.laya_ladder.serve', '--checkpoint', str(self.checkpoint),
             '--model', self.model, '--device', self.device, '--ready-file', str(ready)],
            cwd=c.ROOT, env=child, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
            start_new_session=True)
        started = time.monotonic()
        while time.monotonic() - started < 300:
            if self.process.poll() is not None:
                raise RuntimeError('serving exited before readiness')
            if ready.exists():
                info = read(ready)
                health = http_json(info['endpoint'], '/health', timeout=5)
                self.identity = dict(health, endpoint=info['endpoint'], pid=self.process.pid)
                return self.identity
            time.sleep(0.5)
        raise RuntimeError('serving readiness timeout')


def register():
    from integration.laya_imitation import serving
    from integration.laya_v10 import serve_v10
    serve_v10.MODELS = tuple(dict.fromkeys(serve_v10.MODELS + (MODEL,)))
    battle_v10.register()
    if MODEL not in serving.MODELS:
        serving.MODELS = serving.MODELS + (MODEL,)
    comparison.RENDER[MODEL] = battle_v10.RENDER
    comparison.Serving = Serving
    play = comparison.play_slot
    base = play.func if isinstance(play, functools.partial) else play
    comparison.play_slot = functools.partial(base, worker=WORKER)


def identity():
    return dict(v10=battle_v10.v10_identity(),
                ladder={n: sha(paths.ROOT / 'integration/laya_ladder' / n) for n in ('serve.py', 'battle.py', 'paths.py')})


def mock():
    register()
    comparison.mock(EX168)


def prepare():
    register()
    comparison.prepare(EX168)
    atomic(EX168.out / 'source/v10-identity.json', identity(), immutable=True)


def execute():
    register()
    if read(EX168.out / 'source/v10-identity.json') != identity():
        raise RuntimeError('laya_v10, laya_ladder or the laya worktree changed after the EX-168 freeze')
    comparison.execute(EX168)


def export():
    from integration.laya_engine import judge as J
    from integration.laya_imitation.features import Calc
    from integration.laya_imitation.reporting import compare_report
    from integration.laya_imitation.viewer import export as export_viewer
    from integration.laya_v10 import data_v10
    register()
    study, out = EX168, EX168.out
    result = read(out / 'result.json')
    counts = ' · '.join('%s %d승 %d무 %d패' % (k, v['wins'], v['draws'], v['losses']) for k, v in result['models'].items())
    meta = dict(study.meta, intro=study.meta['intro'] + ' 모델별: ' + counts + '. 판정: ' + result['verdict'] + '.')
    with Calc() as calc, J.Judge() as judge:
        render = data_v10.live_renderer(calc, judge)
        viewer = export_viewer(out, study.viewer, meta=meta, columns=comparison._columns, renderer_for=lambda row: render)
    compare_report(out, result, viewer, study)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(), verdict=result['verdict']))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(study.viewer / 'index.html'))))


def worker(argv):
    """`laya_imitation.battle`'s worker CLI with every v10 model given `early_history`."""
    from integration.laya_imitation import serving
    if MODEL not in serving.MODELS:
        serving.MODELS = serving.MODELS + (MODEL,)
    battle.EARLY_HISTORY_MODELS = tuple(battle.EARLY_HISTORY_MODELS) + MODELS
    return battle.main(argv)


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(worker(sys.argv[1:]))
    {'mock': mock, 'prepare': prepare, 'execute': execute, 'export': export}[sys.argv[1]]()
