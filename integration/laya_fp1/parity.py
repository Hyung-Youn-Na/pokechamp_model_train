"""EX-177 qualification 7 (D-213): the serving renderer (`render_worker`, one tracker per game, fed decision by
decision with the public prefix) gives the stored dataset row, on locked-test rows (foul-play venv).

    PYTHONHASHSEED=0 PYTHONPATH=.:.tools/foul-play/src .tools/foul-play/.venv/bin/python -m integration.laya_fp1.parity

Each sampled game side is replayed through a `render_worker` subprocess exactly as `serve_fp1` drives it: the first
request builds the tracker from the prefix, every later request carries the previous decision's label as `previous`.
Rows are compared byte for byte (state and criteria) with the fp1 test files.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys

from integration.laya_fp1 import data_fp1 as D
from integration.laya_fp1 import tracker as T


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--rows', type=int, default=512)
    parser.add_argument('--out')
    args = parser.parse_args(argv)
    stored = {}
    for path in (D.TESTS / 'tour/test.jsonl', D.TESTS / 'ladder/test.jsonl'):
        for line in open(path):
            row = json.loads(line)
            stored[row['sample_id']] = row
    by_game = {}
    for sid in stored:
        by_game.setdefault(sid.split(':', 1)[0], []).append(sid)
    games = sorted(by_game)
    random.Random(234).shuffle(games)
    chosen, n = [], 0
    for g in games:
        if n >= args.rows:
            break
        chosen.append(g)
        n += len(by_game[g])
    want = {sid: 'x' for g in chosen for sid in by_game[g]}
    env = dict(os.environ, PYTHONHASHSEED='0')
    worker = subprocess.Popen([sys.executable, '-m', 'integration.laya_fp1.render_worker'], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, text=True, bufsize=1, env=env)
    assert json.loads(worker.stdout.readline())['status'] == 'ready'

    def call(req):
        worker.stdin.write(json.dumps(req, ensure_ascii=False) + '\n')
        worker.stdin.flush()
        return json.loads(worker.stdout.readline())

    same, differ, errors, examples = 0, 0, 0, []
    for job in D.jobs(want):
        recovered, raw = D.load(job['recovered']), D.load(job['raw'])
        lines = T.lines_of(raw)
        result = recovered['result']
        for side in sorted(result['original_sets']):
            own = result['original_sets'][side]
            key = '%s#%s' % (job['replay_id'], side)
            previous = None
            for record in T.recovered_records(recovered, side):
                sid = '%s:%s:%d:%s' % (job['replay_id'], side, record['cutoff_line'], record['decision_kind'])
                reply = call(dict(op='render', game=key, side=side, own_sets=own,
                                  lines=lines[:record['cutoff_line']], snapshot=record['snapshot'],
                                  decision_kind=record['decision_kind'], actions=record['actions'],
                                  previous=previous, sample_id=sid))
                previous = record.get('label')      # None -> the worker records the unobserved choice, as the dataset
                if sid not in stored:
                    continue
                if 'error' in reply:
                    errors += 1
                    examples.append(dict(sample_id=sid, error=reply['error']))
                    continue
                row = stored[sid]
                if reply['state'] == row['state'] and reply['criteria'] == row['questions']['action']['criteria']:
                    same += 1
                else:
                    differ += 1
                    if len(examples) < 5:
                        examples.append(dict(sample_id=sid, kind='differ'))
            call(dict(op='close', game=key))
    worker.stdin.close()
    worker.wait()
    out = dict(games=len(chosen), rows=same + differ + errors, identical=same, different=differ, errors=errors,
               examples=examples[:10])
    print(json.dumps(out, indent=1))
    if args.out:
        with open(args.out, 'w') as f:
            json.dump(out, f, indent=1)


if __name__ == '__main__':
    main()
