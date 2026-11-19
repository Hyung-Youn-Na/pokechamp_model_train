"""EX-169: re-render every bot decision with the serving configuration of its game -> `tables/decisions.jsonl`.

    python -m integration.laya_v11.analysis.render [--workers N]

The model input text is not in the game record (serving renders it), so the request body is rendered again with the
unchanged v10 live renderer. A game's configuration (`games.era`: usage extension, fixed judge) is applied in the
worker processes of its group. `score` then checks the text against the logged probabilities.
"""
from __future__ import annotations
import argparse
import json
from multiprocessing import get_context
import time

from .. import paths
from . import games

_render = None


def configure(ext, fix):
    """Apply a serving configuration to this process (what `laya_ladder.serve` of laya-play does)."""
    identity = dict(usage_extension=None, judge_fix=None)
    if ext:
        from .. import usage_extension
        identity['usage_extension'] = usage_extension.install(paths.USAGE_EXTENSION)
    if fix:
        from integration.laya_engine import judge as J
        J.WORKER = paths.JUDGE_FIXED
        identity['judge_fix'] = paths.JUDGE_FIXED.name
    return identity


def live_renderer():
    from integration.laya_engine import judge as J
    from integration.laya_imitation import features
    from integration.laya_v10 import data_v10
    return data_v10.live_renderer(features.Calc(), J.Judge())


def _init(ext, fix):
    global _render
    configure(ext, fix)
    _render = live_renderer()


def _game(name):
    from integration.pokechamp.imitation.schema import ImitationInput
    game = games.Game(name)
    out = []
    for row in game.rows():
        e = game.inputs[row['k']]
        try:
            state, question = _render(ImitationInput.from_body(e['body']))
            row.update(state=state, criteria=question['criteria'], instructions=question['instructions'],
                       render_error=None)
        except Exception as error:   # a decision the renderer rejects is kept and listed
            row.update(state=None, criteria=None, instructions=None, render_error='%s: %s' % (type(error).__name__,
                                                                                               error))
        out.append(row)
    return out


def run(workers=24):
    paths.TABLES.mkdir(parents=True, exist_ok=True)
    target = paths.TABLES / 'decisions.jsonl'
    if target.exists():
        raise FileExistsError(target)
    started = time.time()
    groups = {}
    for name in games.names():
        cfg = games.era(name)
        groups.setdefault((cfg['ext'], cfg['fix']), []).append(name)
    rows = []
    for (ext, fix), members in sorted(groups.items()):
        with get_context('spawn').Pool(min(workers, len(members)), initializer=_init, initargs=(ext, fix)) as pool:
            for part in pool.imap(_game, members, chunksize=1):
                rows.extend(part)
        print('rendered ext=%s fix=%s: %d games' % (ext, fix, len(members)), flush=True)
    rows.sort(key=lambda r: (r['game'], r['k']))
    with open(target, 'w') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    summary = dict(games=len({r['game'] for r in rows}), decisions=len(rows),
                   automatic=sum(r['automatic'] for r in rows), render_errors=sum(r['render_error'] is not None
                                                                                  for r in rows),
                   groups={'ext=%s fix=%s' % k: len(v) for k, v in sorted(groups.items())},
                   seconds=round(time.time() - started, 1))
    (paths.TABLES / 'decisions.summary.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=24)
    run(parser.parse_args().workers)
