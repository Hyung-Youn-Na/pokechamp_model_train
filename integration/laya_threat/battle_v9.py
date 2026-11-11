"""EX-158: v7t (EX-149) vs v9t (EX-157) on the sealed EX-120 schedule vs Abyssal, GPU3 / port 8106 (D-202).

`laya_imitation.comparison`'s stages (schedule, ledger, no replay of claimed slots, audits, summary, non-inferiority
verdict) run unchanged. This module only adds what the v9 model needs, in its own process:
- `comparison.RENDER` maps the v9 models to render `v9`, and `serve.register()` teaches `serving` that render;
- the owned serving of a v9 model runs `integration.laya_threat.serve` (the laya_imitation CLI cannot serve v9);
- prepare also freezes the laya_threat file hashes, and execute refuses to run if they changed;
- export renders the viewer's compact input tab with the live v9 renderer for v9 games.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time

from integration.laya_imitation import battle, comparison
from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic, read, seal, sha

from . import data_v9, paths, serve

EX158 = comparison.Study(
    experiment='EX-158', plan='EP-225', seed=20261053, models=('laya-v7t', 'laya-v9t'), out=paths.RUN_COMPARE,
    viewer=paths.VIEWER_COMPARE, gpu=paths.GPU, port=paths.PORT, hours=c.COMPARE_HOURS,
    runs={'laya-v7t': ('EX-149', c.RUN_V7_TRAINING), 'laya-v9t': ('EX-157', paths.RUN_V9_TRAINING)},
    mock_model='laya-v9t-initial', replicate=None, margin=0.05,
    verdicts=('v9가 배틀 성적을 개선', '퇴보를 배제하지 못함', '비퇴보'),
    meta=dict(experiment='EX-158', plan='EP-225', slug='ex158', pairs=128,
              title='EX-158 · laya v7·v9 상대 위협 표시 256경기',
              heading='EX-158 · laya v7(EX-149)과 v9 상대 노력치 보정·최악 피해 표시(EX-157) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. 차이는 v9 입력이 상대 가정 세트의 '
                    '노력치를 도구·공개 기술에 맞추고, 미공개 기술·도구·테라까지 넣은 최악 피해를 교체 선택지(`risk`)와 '
                    '현재 포켓몬(`opp threat`)에 보여 주는 것입니다. 확률은 행동 선택 확률이고 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex148-laya-v1'))


class Serving(battle.Serving):
    """`battle.Serving`; a v9 model is served by `integration.laya_threat.serve`."""

    def start(self, env):
        if self.render != serve.RENDER:
            return super().start(env)
        from integration.pokechamp.imitation.player import http_json
        ready = self.directory / ('serving-%s.ready.json' % self.model)
        self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
        child = dict(os.environ, PYTHONPATH=str(c.ROOT), PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1',
                     TOKENIZERS_PARALLELISM='false', **env)
        self.process = subprocess.Popen(
            [str(c.LAYA_PYTHON), '-m', 'integration.laya_threat.serve', '--checkpoint', str(self.checkpoint),
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
    serve.register()
    for model in serve.MODELS:
        comparison.RENDER[model] = serve.RENDER
    comparison.Serving = Serving


def threat_identity():
    return {n: sha(paths.PACKAGE / n) for n in sorted(p.name for p in paths.PACKAGE.glob('*.py'))}


def mock():
    register()
    comparison.mock(EX158)


def prepare():
    register()
    comparison.prepare(EX158)
    atomic(EX158.out / 'source/threat-identity.json', threat_identity(), immutable=True)


def execute():
    register()
    if read(EX158.out / 'source/threat-identity.json') != threat_identity():
        raise RuntimeError('laya_threat changed after the EX-158 freeze')
    comparison.execute(EX158)


def export():
    """`comparison.export` with v7 and v9 renderers for the viewer's compact input tab."""
    from integration.laya_imitation.features import Calc
    from integration.laya_imitation.reporting import compare_report
    from integration.laya_imitation.serving import v7_renderer
    from integration.laya_imitation.viewer import export as export_viewer
    register()
    study, out = EX158, EX158.out
    result = read(out / 'result.json')
    counts = ' · '.join('%s %d승 %d무 %d패' % (k, v['wins'], v['draws'], v['losses']) for k, v in result['models'].items())
    meta = dict(study.meta, intro=study.meta['intro'] + ' 모델별: ' + counts + '. 판정: ' + result['verdict'] + '.')
    with Calc() as calc:
        renderers = dict(v7=v7_renderer(calc), v9=data_v9.live_renderer(calc))
        viewer = export_viewer(out, study.viewer, meta=meta, columns=comparison._columns,
                               renderer_for=lambda row: renderers[comparison.RENDER[row['model']]])
    compare_report(out, result, viewer, study)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(), verdict=result['verdict']))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(study.viewer / 'index.html'))))


if __name__ == '__main__':
    {'mock': mock, 'prepare': prepare, 'execute': execute, 'export': export}[sys.argv[1]]()
