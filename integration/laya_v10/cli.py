"""EP-227 stages (D-204). `python -m integration.laya_v10.cli <stage>` with the laya 0.4.13 interpreter and
`paths.LAYA_SOURCE` (laya with `option_max_len`) first on PYTHONPATH.

measure / data / parity (CPU) -> train / evaluate (GPU0, EX-161) -> mock / prepare / execute / export (EX-162).
"""
from __future__ import annotations
import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('measure', 'data', 'parity', 'train', 'evaluate', 'mock', 'prepare',
                                          'execute', 'export'))
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args(argv)
    from . import training_v10
    training_v10.require_laya()
    if args.stage in ('measure', 'data', 'parity'):
        from . import data_v10
        {'measure': data_v10.measure, 'data': data_v10.build, 'parity': data_v10.parity}[args.stage]()
    elif args.stage == 'train':
        from integration.laya_imitation.training import run
        from .data_v10 import budget
        chosen = budget()
        training_v10.install(chosen['option'])
        run(preflight_only=args.preflight_only, spec=training_v10.spec(chosen))
    elif args.stage == 'evaluate':
        from .evaluation_v10 import run
        run()
    else:
        from . import battle_v10
        getattr(battle_v10, args.stage)()


if __name__ == '__main__':
    main()
