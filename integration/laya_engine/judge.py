"""EP-224 engine judge client: `option_outcomes(value, judge)` -> {move action id: label} for one decision.

Labels: `fails` / `immune` / `absorbed` / `reflected` (every informative engine case fails: confirmed), `likely fails`
(chance-based: a Protect streak, or a Sleep Talk / Snore user at least as likely to wake as not), and nothing for
options that may work. `Judge` is a persistent node worker (`judge.cjs`) like `features.Calc`.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess

from . import state

HERE = Path(__file__).parent
WORKER = HERE / 'judge.cjs'
FAILING = ('fails', 'immune', 'absorbed', 'reflected')
LIKELY = 'likely fails'
FILES = ('judge.cjs', 'judge.py', 'state.py')


def identity():
    return dict(version='laya-engine-judge/v1',
                files={n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in FILES})


class Judge:
    """Persistent node worker; one scenario line in, one result line out."""

    def __init__(self):
        self.process = subprocess.Popen(['node', str(WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, bufsize=1)
        ready = json.loads(self.process.stdout.readline() or '{}')
        if ready.get('status') != 'ready':
            raise RuntimeError('judge worker failed to start: %s' % self.process.stderr.read()[-500:])
        self.version = ready['version']

    def run(self, scenario):
        self.process.stdin.write(state.dumps(scenario) + '\n')
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('judge worker exited: %s' % self.process.stderr.read()[-500:])
        out = json.loads(line)
        if out.get('id') != scenario['id']:
            raise RuntimeError('judge answered %r for %r' % (out.get('id'), scenario['id']))
        return out

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            self.process.wait(timeout=10)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def view_of(value):
    """The item-state-resolved snapshot (`features_v5.resolved`), or the raw one for inputs without D-195 fields."""
    from integration.laya_imitation import features_v5
    snapshot = json.loads(value.body['state'])['snapshot']
    return features_v5.resolved(value)[1] if features_v5.has_fields(snapshot) else snapshot


def likely(scenario):
    """{action id: 'likely fails'} from chance alone (engine cases are played at their most favourable)."""
    out = {}
    streak = scenario['recall']['stall_streak']
    for o in scenario['options']:
        if o['move'] in state.STALL and streak >= 1:
            out[o['id']] = LIKELY        # success chance 1/3^streak
        elif o['move'] in state.SLEEP_USABLE and scenario['wake'] is not None and scenario['wake'] >= 0.5:
            out[o['id']] = LIKELY
    return out


def judge_view(view, action_ids, judge, sid='x'):
    """(labels, detail): labels for confirmed / likely failures only; detail has every option's engine answer."""
    scenario = state.build(view, list(action_ids), sid)
    if scenario is None:
        return {}, dict(reproduced=None, options={})
    out = judge.run(scenario)
    if 'error' in out:
        return {}, dict(reproduced=False, error=out['error'], options={})
    labels = {}
    for action_id, r in out['options'].items():
        if r['label'] in FAILING:
            labels[action_id] = r['label']
    for action_id, label in likely(scenario).items():
        labels.setdefault(action_id, label)
    reproduced = not all(r['label'] == 'unknown' and str(r.get('error', '')).startswith('error:') and
                         'choice' not in str(r.get('error', '')) for r in out['options'].values())
    return labels, dict(reproduced=reproduced, options=out['options'])


def option_outcomes(value, judge):
    return judge_view(view_of(value), value.action_ids, judge)
