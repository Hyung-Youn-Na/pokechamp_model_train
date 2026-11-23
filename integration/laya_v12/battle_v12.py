"""EX-193 (EP-237, D-214): laya v12 (EX-192 selected) vs foul-play on EX-174's sealed Blim schedule.

    python -m integration.laya_v12.battle_v12 {mock,prepare,execute,export} EX-193|EX-198   (laya env)

`integration.foulplay.battle` unchanged; this wraps EX-184's study (`battle._v11`: CPU serving, argmax, same slots)
with the v12 input:
- serving starts `integration.laya_v12.serve_v12` (v11 serving + `render_v12.install()`) and must report `v12_render`;
- the prepare check compares the live v12 renderer with the `v12-ladder` generator copy (`data_v12.configure`);
- the frozen identity adds the v12 package files (and the pinned set file);
- export installs v12 so the viewer shows the served input, and the report adds the same-slot EX-174 (v10rt) line.
Same-slot baseline is EX-184 (v11rtc). The model name stays `laya-v11rtc` (battle workers read `serve_v11.MODELS`);
the checkpoint sha in the manifest tells the models apart.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from integration.foulplay import battle as B
from integration.laya_imitation import config as c
from integration.laya_imitation.storage import read, sha

PORTS = (8100, 8101, 8102, 8103)
EX184 = c.SHARED / 'runs/model-training/EX-184'
PACKAGE = c.ROOT / 'integration/laya_v12'
FILES = ('observe.py', 'sets.py', 'render_v12.py', 'serve_v12.py', 'battle_v12.py', 'data_v12.py',
         'data/foulplay_full_sets_gen9ou.json')

STUDY = B._v11('EX-193', 'laya-v11rtc', 'v12', 'EX-192', PORTS)
STUDY.baseline = ('EX-184 v11rtc', EX184, lambda r: r['slot_id'])
B.STUDIES['EX-193'] = STUDY
# EP-238 EX-198: EX-196 selected (v12 + opponent prediction) with the same argmax play, ports 8104-8107 (EX-197 runs
# on 8100-8103 at the same time). Same-slot baseline EX-193.
EX198 = B._v11('EX-198', 'laya-v11rtc', 'v12foe', 'EX-196', (8104, 8105, 8106, 8107))
EX198.baseline = ('EX-193 v12', c.SHARED / 'runs/model-training/EX-193', lambda r: r['slot_id'])
B.STUDIES['EX-198'] = EX198


def _serving_v12_class():
    from integration.laya_v10 import paths as p10
    base = B._serving_v11_class()

    class ServingV12(base):
        """The foul-play runner's v11 serving, started on `integration.laya_v12.serve_v12`."""

        def start(self, env):
            from integration.pokechamp.imitation.player import http_json
            ready = self.directory / ('serving-%s.ready.json' % self.model)
            self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
            child = dict(os.environ, PYTHONPATH='%s:%s' % (p10.LAYA_SOURCE, c.ROOT), PYTHONDONTWRITEBYTECODE='1',
                         HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', **env)
            self.process = subprocess.Popen(
                [str(c.LAYA_PYTHON), '-m', 'integration.laya_v12.serve_v12', '--checkpoint', str(self.checkpoint),
                 '--model', self.model, '--device', self.device, '--ready-file', str(ready)],
                cwd=c.ROOT, env=child, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                start_new_session=True)
            started = time.monotonic()
            while time.monotonic() - started < 300:
                if self.process.poll() is not None:
                    raise RuntimeError('serving exited before readiness')
                if ready.exists():
                    info = read(ready)
                    if not info.get('v12_render'):
                        raise RuntimeError('serving did not report the v12 input')
                    health = http_json(info['endpoint'], '/health', timeout=5)
                    self.identity = dict(health, endpoint=info['endpoint'], pid=self.process.pid,
                                         v11_render=info['v11_render'], v12_render=info['v12_render'])
                    return self.identity
                time.sleep(0.5)
            raise RuntimeError('serving readiness timeout')

    return ServingV12


def _renderer_matches(study):
    from integration.laya_v10 import data_v10
    from . import data_v12
    data_v12.configure('ladder')           # installs v12 and points the check at the v12-ladder generator copy
    return data_v10.renderer_matches_dataset()


_identity = B.identity


def identity():
    return dict(_identity(), laya_v12={n: sha(PACKAGE / n) for n in FILES})


_export = B.export
_write_report = B.write_report


def export(study):
    from . import render_v12
    render_v12.install()                   # before B.export's render_v11.install() (a no-op afterwards)
    return _export(study)


def write_report(out, result, viewer, study):
    _write_report(out, result, viewer, study)
    rows = read(out / 'manifest.json')['schedule']
    other = B.Study(**dict(study.__dict__, baseline=('EX-174 v10rt', B.EX174, lambda r: r['slot_id'])))
    va = B.versus_baseline(rows, result['outcomes'], other)
    pct = lambda v: '—' if v is None else '%.3f' % v
    ci = lambda v: '—' if not v else '[%.3f, %.3f]' % tuple(v)
    line = '- 같은 슬롯 EX-174 v10rt 대비 차이: %s, 95%% %s (%d슬롯; 이번이 나쁨 %d, 나음 %d, 같음 %d)' % (
        pct(va['mean_diff']), ci(va['matchup_bootstrap_95']), va['slots'], va['foulplay_harder'],
        va['foulplay_easier'], va['same'])
    text = (out / 'report.md').read_text().splitlines()
    at = next(i for i, l in enumerate(text) if l.startswith('- 같은 슬롯')) + 1
    (out / 'report.md').write_text('\n'.join(text[:at] + [line] + text[at:]) + '\n')
    (out / 'versus-ex174.json').write_text(json.dumps(va, ensure_ascii=False, indent=1))


def install():
    B.ServingV11 = lambda *a, **k: _serving_v12_class()(*a, **k)
    B._renderer_matches = _renderer_matches
    B.identity = identity
    B.write_report = write_report


def _plan_label(plan='EP-237'):
    from integration.laya_imitation import viewer
    original = viewer.export

    def labelled(run, output, meta, **kw):
        return original(run, output, meta=dict(meta, plan=plan), **kw)
    viewer.export = labelled


if __name__ == '__main__':
    install()
    command = sys.argv[1]
    study = B.STUDIES[sys.argv[2] if len(sys.argv) > 2 else 'EX-193']
    if command == 'export':
        _plan_label('EP-238' if study.experiment == 'EX-198' else 'EP-237')
        export(study)
    else:
        {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute}[command](study)
