"""EX-162: v7t (EX-149) vs v10t (EX-161) on the sealed EX-120 schedule vs Abyssal, GPU0 / port 8107 (D-204).

`laya_imitation.comparison`'s stages (schedule, ledger, no replay of claimed slots, audits, summary, non-inferiority
verdict) run unchanged. This module only adds what the v10 model needs, in its own process:
- `comparison.RENDER` maps the v10 models to render `v10`, and `serve_v10.register()` teaches `serving` that render;
- the owned serving of a v10 model runs `integration.laya_v10.serve_v10` with the laya that has `option_max_len`;
- every game's workers run `integration.laya_v10.battle_v10 worker`, which is `laya_imitation.battle.worker` with the
  v10 models added to its `early_history` models (the v7t worker input is unchanged);
- prepare also freezes the laya_v10 file hashes and the laya worktree diff, and execute refuses to run if they changed;
- export renders the viewer's compact input tab with the live v10 renderer for v10 games.
"""
from __future__ import annotations
import functools
import hashlib
import json
import os
import subprocess
import sys
import time

from integration.laya_imitation import battle, comparison
from integration.laya_imitation import config as c
from integration.laya_imitation.storage import atomic, read, seal, sha

from . import paths

MODELS = ('laya-v10t', 'laya-v10t-initial')
RENDER = 'v10'
WORKER = 'integration.laya_v10.battle_v10'

EX162 = comparison.Study(
    experiment='EX-162', plan='EP-227', seed=20261063, models=('laya-v7t', 'laya-v10t'), out=paths.RUN_COMPARE,
    viewer=paths.VIEWER_COMPARE, gpu=paths.GPU, port=paths.PORT, hours=c.COMPARE_HOURS,
    runs={'laya-v7t': ('EX-149', c.RUN_V7_TRAINING), 'laya-v10t': ('EX-161', paths.RUN_V10_TRAINING)},
    mock_model='laya-v10t-initial', replicate=None, margin=0.05,
    verdicts=('v10이 배틀 성적을 개선', '퇴보를 배제하지 못함', '비퇴보'),
    meta=dict(experiment='EX-162', plan='EP-227', slug='ex162', pairs=128,
              title='EX-162 · laya v7·v10 256경기',
              heading='EX-162 · laya v7(EX-149)과 v10 정보 전부 + lock + 전략(EX-161) · EX-120 일정 대 Abyssal',
              intro='같은 일정(새 팀 32개, 128슬롯)을 두 모델이 번갈아 진행했습니다. v10 입력은 v6h의 긴 기록만 빼고 '
                    'v1~v9 정보를 모두 넣고, 기술 고정(lock)과 형세·결투·매치업·PP·회복·예상 교체·테라 방어·해저드 '
                    '정보를 더한 2,048토큰 입력입니다. 확률은 행동 선택 확률이고 승률이 아닙니다.',
              changelog='project_context/shared/viewers/CHANGELOG.md#ex148-laya-v1'))


def laya_identity():
    """The laya worktree the v10 serving imports: HEAD and a digest of its uncommitted diff."""
    head = subprocess.run(['git', '-C', str(paths.LAYA_SOURCE), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                          check=True).stdout.strip()
    diff = subprocess.run(['git', '-C', str(paths.LAYA_SOURCE), 'diff', 'HEAD'], capture_output=True, check=True).stdout
    return dict(path=str(paths.LAYA_SOURCE), head=head, diff_sha256=hashlib.sha256(diff).hexdigest())


class Serving(battle.Serving):
    """`battle.Serving`; a v10 model is served by `integration.laya_v10.serve_v10`."""

    def start(self, env):
        if self.render != RENDER:
            return super().start(env)
        from integration.pokechamp.imitation.player import http_json
        ready = self.directory / ('serving-%s.ready.json' % self.model)
        self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
        child = dict(os.environ, PYTHONPATH='%s:%s' % (paths.LAYA_SOURCE, c.ROOT), PYTHONDONTWRITEBYTECODE='1',
                     HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', **env)
        self.process = subprocess.Popen(
            [str(c.LAYA_PYTHON), '-m', 'integration.laya_v10.serve_v10', '--checkpoint', str(self.checkpoint),
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
    from . import serve_v10
    serve_v10.register()
    for model in MODELS:
        comparison.RENDER[model] = RENDER
    comparison.Serving = Serving
    if not isinstance(comparison.play_slot, functools.partial):
        comparison.play_slot = functools.partial(comparison.play_slot, worker=WORKER)


def v10_identity():
    return dict(code={n: sha(paths.PACKAGE / n) for n in sorted(p.name for p in paths.PACKAGE.glob('*.py'))},
                pp=sha(paths.PACKAGE / 'pp_gen9.json'), laya=laya_identity())


def mock():
    register()
    comparison.mock(EX162)


def prepare():
    register()
    comparison.prepare(EX162)
    atomic(EX162.out / 'source/v10-identity.json', v10_identity(), immutable=True)


def execute():
    register()
    if read(EX162.out / 'source/v10-identity.json') != v10_identity():
        raise RuntimeError('laya_v10 or its laya worktree changed after the EX-162 freeze')
    comparison.execute(EX162)


def export():
    """`comparison.export` with v7 and v10 renderers for the viewer's compact input tab."""
    from integration.laya_engine import judge as J
    from integration.laya_imitation.features import Calc
    from integration.laya_imitation.reporting import compare_report
    from integration.laya_imitation.serving import v7_renderer
    from integration.laya_imitation.viewer import export as export_viewer
    from . import data_v10
    register()
    study, out = EX162, EX162.out
    result = read(out / 'result.json')
    counts = ' · '.join('%s %d승 %d무 %d패' % (k, v['wins'], v['draws'], v['losses']) for k, v in result['models'].items())
    meta = dict(study.meta, intro=study.meta['intro'] + ' 모델별: ' + counts + '. 판정: ' + result['verdict'] + '.')
    with Calc() as calc, J.Judge() as judge:
        renderers = dict(v7=v7_renderer(calc), v10=data_v10.live_renderer(calc, judge))
        viewer = export_viewer(out, study.viewer, meta=meta, columns=comparison._columns,
                               renderer_for=lambda row: renderers[comparison.RENDER[row['model']]])
    compare_report(out, result, viewer, study)
    atomic(out / 'status.json', dict(stage='completed', at=time.time(), verdict=result['verdict']))
    seal(out, skip=('showdown-worktree',))
    print(json.dumps(dict(viewer=str(study.viewer / 'index.html'))))


def worker(argv):
    """`laya_imitation.battle`'s worker CLI with the v10 models given `early_history` (D-198 path)."""
    battle.EARLY_HISTORY_MODELS = tuple(battle.EARLY_HISTORY_MODELS) + MODELS
    return battle.main(argv)


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(worker(sys.argv[1:]))
    {'mock': mock, 'prepare': prepare, 'execute': execute, 'export': export}[sys.argv[1]]()
