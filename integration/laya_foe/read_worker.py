"""EP-238 EX-197: the one-turn read worker, one JSON request per line on stdin -> one JSON line on stdout (foul-play venv).

    PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m integration.laya_foe.read_worker

Keeps one `laya_fp1.tracker.Tracker` per game and feeds it exactly as `laya_fp1.render_worker` does (first request:
public prefix + own sets; later: the previous choice, then advance to the decision). Every model decision is sent,
so the tracker sees every choice; the read itself is computed only for turn_action decisions with two or more
candidates:
- samples: `laya_regret.search.sample_states(view, seed)` (foul-play's own `prepare_battles`; seed from sample_id);
- candidates: laya action id -> engine choice (`render_fp1.engine_choice`);
- values: `read.values(samples, candidates, foe)`.
Request: {op: "read", game, side, own_sets, lines, snapshot, decision_kind, previous, sample_id, candidates, foe}
         {op: "close", game}
Reply:   {values: {id: value} | null, samples, errors, seconds} or {error}.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import traceback

from integration.laya_fp1 import render_fp1 as RF
from integration.laya_fp1 import tracker as T

from . import read as R


def seed_of(sample_id):
    return int(hashlib.sha256(('ex197:' + sample_id).encode()).hexdigest()[:16], 16)


def main():
    from integration.laya_regret.search import sample_states
    T.setup()
    games = {}
    sys.stdout.write(json.dumps(dict(status='ready')) + '\n')
    sys.stdout.flush()
    for line in sys.stdin:
        started = time.monotonic()
        try:
            req = json.loads(line)
            if req.get('op') == 'close':
                games.pop(req['game'], None)
                out = dict(closed=req['game'])
            else:
                game = games.get(req['game'])
                raw = dict(log='\n'.join(req['lines']))
                if game is None:
                    game = games[req['game']] = T.Tracker(raw, req['side'], req['own_sets'])
                else:
                    game.lines = T.lines_of(raw)
                    game.chose(req.get('previous'))
                kind = req['decision_kind']
                if kind == 'lead':
                    view = game.lead_view()
                else:
                    game.advance(len(game.lines), req['snapshot'], kind)
                    view = game.view()
                out = dict(values=None, samples=0, errors=0)
                cands = req.get('candidates') or []
                if kind == 'turn_action' and len(cands) > 1 and req.get('foe'):
                    mine = {a: RF.engine_choice(a, view, req['own_sets']) for a in cands}
                    mine = {a: ch for a, ch in mine.items() if ch}
                    samples, _ = sample_states(view, seed_of(req['sample_id']))
                    values, errors = R.values(samples, mine, req['foe'])
                    out = dict(values=values, samples=len(samples), errors=errors, choices=mine)
            out['seconds'] = round(time.monotonic() - started, 3)
        except Exception as exc:
            out = dict(error='%s: %s' % (type(exc).__name__, exc), trace=traceback.format_exc(limit=4)[-800:])
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
