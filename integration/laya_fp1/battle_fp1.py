"""EX-179 (D-213): laya fp1 (EX-178 selected) vs foul-play on EX-174's sealed Blim schedule.

    python -m integration.laya_fp1.battle_fp1 {mock,prepare,execute,export} EX-179        (laya env)

`integration.foulplay.battle` unchanged (EP-232/233's runner: schedule, play_slot, audits, summary, report); this
module adds the EX-179 study and replaces, in this process and its game workers only:
- the worker module (`WORKER` = this module): the model side gets `Fp1Session`, which adds the `fp1` member to every
  request input (public prefix, own sets, snapshot, decision kind, previous choice); the foul-play side is unchanged;
- the serving for render `fp1`: `integration.laya_fp1.serve_fp1` on CPU (one tracker per game in its render worker);
- the renderer check: the served fp1 code equals the code the fp1 dataset recorded (`manifest.json` `code`).
Teams, sides, seeds, foul-play settings and limits are EX-174's; the outcome pairs with EX-174's v10rt slot.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

from integration.foulplay import battle as B
from integration.foulplay import paths as P
from integration.laya_imitation import config as c

MODEL = 'laya-fp1'
DATASET = P.SHARED / 'datasets/generated/laya-compact-imitation/fp1-ladder-merged'
B.WORKER = 'integration.laya_fp1.battle_fp1'
B.STUDIES['EX-179'] = B.Study(
    experiment='EX-179', run=P.SHARED / 'runs/model-training/EX-179', viewer=P.ROOT / 'exports/battle_viewers/ex179',
    base=B._blim_base, teams=B.BLIM_TEAMS, slug='ex179', model=MODEL, label='fp1',
    source=('EX-178', P.SHARED / 'runs/model-training/EX-178'), render='fp1', ports=(8100, 8101, 8102, 8103),
    baseline=('EX-174 v10rt', B.EX174, lambda r: r['slot_id']))
# EX-180 (EP-234, user instruction 2026-11-19): EX-179's conditions with EX-178's epoch-2 checkpoint while epoch 3
# trains. The checkpoint is a frozen copy (`source-epoch2/checkpoints/selected`, hashes in `checkpoint.sha256`).
_EX180 = P.SHARED / 'runs/model-training/EX-180'
B.STUDIES['EX-180'] = B.Study(
    experiment='EX-180', run=_EX180, viewer=P.ROOT / 'exports/battle_viewers/ex180',
    base=B._blim_base, teams=B.BLIM_TEAMS, slug='ex180', model=MODEL, label='fp1e2',
    source=('EX-178 epoch-2', _EX180 / 'source-epoch2'), render='fp1', ports=(8100, 8101, 8102, 8103),
    baseline=('EX-174 v10rt', B.EX174, lambda r: r['slot_id']))


def _code():
    from integration.laya_imitation.storage import sha
    here = Path(__file__).parent
    return {p.name: sha(p) for p in sorted(here.glob('*.py'))}


_original_matches = B._renderer_matches


def _renderer_matches(study):
    if study.render != 'fp1':
        return _original_matches(study)
    recorded = json.loads((DATASET / 'manifest.json').read_text())['code']
    live = _code()
    return all(live.get(name) == digest for name, digest in recorded.items()
               if name in ('tracker.py', 'render_fp1.py'))


B._renderer_matches = _renderer_matches
_original_serving = B._serving


def _serving(directory, study):
    if study.render != 'fp1':
        return _original_serving(directory, study)
    from integration.laya_imitation import serving
    from integration.laya_imitation.battle import Serving as Base
    serving.MODELS = tuple(dict.fromkeys(serving.MODELS + (MODEL,)))

    class ServingFp1(Base):
        def start(self, env):
            from integration.pokechamp.imitation.player import http_json
            from integration.laya_v10 import paths as p10
            ready = self.directory / ('serving-%s.ready.json' % self.model)
            self.log = (self.directory / ('serving-%s.log' % self.model)).open('xb')
            child = dict(os.environ, PYTHONPATH='%s:%s' % (p10.LAYA_SOURCE, c.ROOT), PYTHONDONTWRITEBYTECODE='1',
                         HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false', **env)
            self.process = subprocess.Popen(
                [str(c.LAYA_PYTHON), '-m', 'integration.laya_fp1.serve_fp1', '--checkpoint', str(self.checkpoint),
                 '--model', self.model, '--device', self.device, '--ready-file', str(ready)],
                cwd=c.ROOT, env=child, stdin=subprocess.DEVNULL, stdout=self.log, stderr=subprocess.STDOUT,
                start_new_session=True)
            started = time.monotonic()
            while time.monotonic() - started < 300:
                if self.process.poll() is not None:
                    raise RuntimeError('serving exited before readiness')
                if ready.exists():
                    info = json.loads(ready.read_text())
                    health = http_json(info['endpoint'], '/health', timeout=5)
                    self.identity = dict(health, endpoint=info['endpoint'], pid=self.process.pid)
                    return self.identity
                time.sleep(0.5)
            raise RuntimeError('serving readiness timeout')

    return ServingFp1(directory, str(study.checkpoint), study.model, 'cpu', render='fp1')


B._serving = _serving


def _install_audit():
    """The shared `audit_match` with the fp1 member taken into account (fp1 games only).

    `Fp1Session` adds `fp1` to the recorded input `body` and the HTTP `input` (the serving strips it before hashing),
    so the shared audit's byte checks fail on every model decision. Here each fp1 member is checked first (present on
    every input; the HTTP request carries the same member; the HTTP bytes equal the recorded body; `game`/`side`
    match the game), then the shared audit runs unchanged on the events with `fp1` removed."""
    import copy
    import threading
    from integration.pokechamp.imitation import battle as IB, reporting
    from integration.pokechamp.imitation.player import compact
    from integration.pokechamp.imitation.schema import ImitationInput
    original, lock = IB.audit_match, threading.Lock()

    def audit(directory, outcome):
        directory = Path(directory)
        row = json.loads((directory / 'request.json').read_text())['slot']
        if row.get('model') != MODEL:
            return original(directory, outcome)
        events, members, errors = reporting.jsonl(directory / 'events.jsonl'), {}, []
        stripped = []
        for event in events:
            event = copy.deepcopy(event)
            decision = event.get('decision')
            if event['type'] == 'input':
                body = event['body']
                member = body.pop('fp1', None)
                if (member is None or ImitationInput(event['body_json']).body != body
                        or member.get('side') != event['actor'] or member.get('game') != str(directory)):
                    errors.append(dict(decision=decision, error='fp1 input member missing or inconsistent'))
                members[decision] = member
            elif event['type'] == 'http_request':
                if event['body_json'] != compact(event['body']):
                    errors.append(dict(decision=decision, error='fp1 HTTP bytes differ from recorded body'))
                member = event['body'].get('input', {}).pop('fp1', None)
                if member is None or member != members.get(decision):
                    errors.append(dict(decision=decision, error='fp1 HTTP member differs from recorded input'))
                event['body_json'] = compact(event['body'])
            stripped.append(event)
        if errors:
            return dict(passed=False, errors=errors, counts={}, inference_seconds=[])
        with lock:
            plain = reporting.jsonl
            reporting.jsonl = lambda path: stripped if Path(path) == directory / 'events.jsonl' else plain(path)
            try:
                result = original(directory, outcome)
            finally:
                reporting.jsonl = plain
        result.setdefault('counts', {})['fp1_inputs'] = len(members)
        return result

    IB.audit_match = audit


_install_audit()


_original_export = B.export


def _fp1_inputs(run):
    """input_sha256 -> (state, question) as served: the `fp1_state` / `fp1_criteria` of each recorded response."""
    from integration.laya_imitation.storage import jsonl
    from integration.laya_fp1.serve_fp1 import INSTRUCTIONS
    out = {}
    for events in sorted((run / 'games').glob('*/events.jsonl')):
        for e in jsonl(events):
            if e.get('type') != 'http_response' or e.get('status_code') != 200:
                continue
            body = json.loads(e['raw_body'])
            if 'fp1_state' in body:
                out[body['input_sha256']] = (body['fp1_state'], dict(type='choice', instructions=INSTRUCTIONS,
                                                                     criteria=body['fp1_criteria']))
    return out


def export(study):
    """B.export with the viewer showing the fp1 input the model was served (not a v10 re-render)."""
    if study.render != 'fp1':
        return _original_export(study)
    from integration.laya_imitation import viewer
    from integration.laya_v10 import data_v10
    served = _fp1_inputs(study.run)

    def render(value):
        if value.sha256 in served:
            return served[value.sha256]
        ids = list(value.action_ids)            # a single legal action: taken without a serving call
        return ('(서빙 호출 없음: 선택지 %d개, 자동 선택)' % len(ids),
                dict(type='choice', instructions='', criteria={k: '' for k in ids}))

    saved = data_v10.live_renderer, viewer.export
    data_v10.live_renderer = lambda calc, judge: render

    def export_viewer(run, output, meta, **kw):
        meta = dict(meta, plan='EP-234', intro=meta['intro'] + ' 입력은 서빙이 기록한 fp1 입력입니다.')
        return saved[1](run, output, meta=meta, **kw)

    viewer.export = export_viewer
    try:
        return _original_export(study)
    finally:
        data_v10.live_renderer, viewer.export = saved


B.export = export


def install_session():
    """`player.Session` with the fp1 member on every request input (game workers of the model side)."""
    from integration.pokechamp.imitation import player as p

    class Fp1Value:
        def __init__(self, value, extra):
            self._value, self._extra = value, extra

        @property
        def body(self):
            body = self._value.body
            body['fp1'] = self._extra
            return body

        def __getattr__(self, name):
            return getattr(self._value, name)

    class Fp1Session(p.Session):
        previous = None

        def generate(self, official, prefix, actions, *, actor):
            value, snapshot = super().generate(official, prefix, actions, actor=actor)
            kind = p.decision_kind(official['request'])
            extra = dict(game=str(self.path.parent), side=actor, own_sets=self.own_sets,
                         lines=p.public_prefix(prefix), snapshot=snapshot, decision_kind=kind,
                         previous=self.previous)
            ids = list(value.action_ids)
            self.previous = ids[0] if len(ids) == 1 else None     # a single legal action is taken as is
            return Fp1Value(value, extra), snapshot

        async def evaluate(self, value, decision):
            choice, probabilities = await super().evaluate(value, decision)
            self.previous = choice
            return choice, probabilities

    p.Session = Fp1Session


def worker(argv):
    from integration.laya_imitation.storage import read
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--role', choices=('p1', 'p2'), required=True)
    args = parser.parse_args(argv)
    row = read(args.attempt / 'request.json')['slot']
    if args.role == row['model_side'] and row['model'] == MODEL:
        from integration.laya_imitation import serving
        serving.MODELS = tuple(dict.fromkeys(serving.MODELS + (MODEL,)))
        install_session()
    return B.worker(argv)


if __name__ == '__main__':
    if sys.argv[1] == 'worker':
        sys.exit(worker(sys.argv[1:]))
    study = B.STUDIES[sys.argv[2] if len(sys.argv) > 2 else 'EX-179']
    {'mock': B.mock, 'prepare': B.prepare, 'execute': B.execute, 'export': export}[sys.argv[1]](study)
