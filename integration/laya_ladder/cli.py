"""EP-230 command line: `python -m integration.laya_ladder.cli {source,stores,merge}` (CPU).

source  select -> corpora -> recover -> split (all train-pool rows; the budget is applied at merge)
stores  item-state, v5 facts, early-history, engine judge, v10 measure / rows / parity for the source
merge   v10-ladder-merged from v10-all and the newest ladder games that fit the 24-hour budget
"""
from __future__ import annotations
import sys

from . import paths


def main(argv):
    command = argv[0]
    if command == 'source':
        from . import source
        kept = source.select()
        source.corpora(kept)
        source.recover(kept)
        source.split(kept, train_rows=10 ** 9)
    elif command == 'stores':
        from . import stores
        stores.build()
    elif command == 'merge':
        from . import stores
        measures = sorted((paths.RUN_TRAINING / 'measure').glob('measure-*.json'))
        stores.merge(measures[-1])
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
