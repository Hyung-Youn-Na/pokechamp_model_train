"""EX-177 qualification 6: token measurement of fp1 rows with the laya tokenizer and the v10 limits (laya env).

    python -m integration.laya_fp1.tokens_fp1 FILE [--sample N]

Uses `laya_v10.data_v10.measure_row` / `fits` (2,048 total, head 768, option 64), as v10 / v11 did.
"""
from __future__ import annotations

import argparse
import json
import random


def main(argv=None):
    from integration.laya_imitation.data_v2 import _tokenizer
    from integration.laya_v10 import data_v10, paths
    parser = argparse.ArgumentParser()
    parser.add_argument('file')
    parser.add_argument('--sample', type=int, default=0)
    args = parser.parse_args(argv)
    tok = _tokenizer()
    rng = random.Random(0)
    rows = []
    with open(args.file) as f:             # reservoir sample, so a multi-GB train file is never held in memory
        for i, line in enumerate(f):
            if not args.sample or len(rows) < args.sample:
                rows.append(json.loads(line))
            else:
                j = rng.randrange(i + 1)
                if j < args.sample:
                    rows[j] = json.loads(line)
    totals, heads, options, fails, worst = [], [], [], 0, []
    for row in rows:
        q = row['questions']['action'] if 'questions' in row else dict(
            type='choice', instructions='x', criteria=row['criteria'])
        m = data_v10.measure_row(tok, row['state'], q, paths.HEAD_LIMIT, paths.OPTION_LIMIT)
        ok = data_v10.fits(m, paths.HEAD_LIMIT, paths.OPTION_LIMIT)
        fails += not ok
        totals.append(m['total'])
        heads.append(m['head'])
        options.append(m['option_max'])
        if not ok:
            worst.append((row['sample_id'], m))

    def q(v):
        v = sorted(v)
        return {p: v[min(len(v) - 1, int(p / 100 * len(v)))] for p in (50, 90, 99, 100)}
    print(json.dumps(dict(rows=len(rows), over_limit=fails, rate=fails / max(1, len(rows)), total=q(totals),
                          head=q(heads), option_max=q(options), examples=worst[:5])))


if __name__ == '__main__':
    main()
