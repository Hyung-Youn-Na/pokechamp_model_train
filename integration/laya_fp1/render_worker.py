"""EX-179 (D-213): the live fp1 renderer, one JSON request per line on stdin -> one JSON line on stdout (foul-play venv).

    PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m integration.laya_fp1.render_worker

Keeps one `tracker.Tracker` per game, fed as the dataset build feeds it (`data_fp1.render_job`):
- the first request of a game builds the tracker from the public prefix (team preview) and the bot's own sets;
- each request first records the bot's previous choice (`Tracker.chose`, as the dataset records the label), then
  advances to the end of the current public prefix with the decision's snapshot and renders with `render_fp1.render`.
Request: {op: "render", game, side, own_sets, lines, snapshot, decision_kind, actions, previous, sample_id}
         {op: "close", game}
Reply:   {state, criteria, diagnostics} or {error}.
Difference from the dataset: the bot always knows its own previous choice, so `previous` is never the unobserved
case the dataset records as `tracker.UNKNOWN_CHOICE`.
"""
from __future__ import annotations

import json
import sys
import traceback

from integration.laya_fp1 import render_fp1 as R
from integration.laya_fp1 import tracker as T


def main():
    T.setup()
    games = {}
    sys.stdout.write(json.dumps(dict(status='ready', render=R.VERSION)) + '\n')
    sys.stdout.flush()
    for line in sys.stdin:
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
                state, criteria, diag = R.render(view, req['sample_id'], req['actions'], kind, req['own_sets'])
                out = dict(state=state, criteria=criteria,
                           diagnostics=dict(engine_errors=diag['engine_errors'], defaults=dict(diag['defaults'])))
        except Exception as exc:
            out = dict(error='%s: %s' % (type(exc).__name__, exc), trace=traceback.format_exc(limit=4)[-800:])
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
