"""EP-225 stages (D-202). `python -m integration.laya_threat.cli <stage>` with the laya 0.4.13 interpreter.

measure / data / parity (CPU) -> train / evaluate (GPU3, EX-157) -> mock / prepare / execute / export (EX-158).
"""
from __future__ import annotations
import argparse

from integration.laya_imitation import config as c

from . import paths


def spec():
    """EX-157: EX-149's settings with the action rows rendered by v9, on GPU3, no time limit."""
    from integration.laya_imitation.training import Spec
    return Spec('EX-157', paths.V9_DATASET, paths.RUN_V9_TRAINING, c.V2_HEAD_LIMIT, 'ex157', max_exclusion_rate=0.005,
                extra_train=c.TERA_KNOWLEDGE / 'train.jsonl', gpu=paths.GPU, hours=None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('measure', 'data', 'parity', 'train', 'evaluate', 'mock', 'prepare',
                                          'execute', 'export'))
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args(argv)
    if args.stage in ('measure', 'data', 'parity'):
        from . import data_v9
        {'measure': data_v9.measure, 'data': data_v9.build, 'parity': data_v9.parity}[args.stage]()
    elif args.stage == 'train':
        from integration.laya_imitation.training import run
        run(preflight_only=args.preflight_only, spec=spec())
    elif args.stage == 'evaluate':
        from .evaluation_v9 import run
        run()
    else:
        from . import battle_v9
        getattr(battle_v9, args.stage)()


if __name__ == '__main__':
    main()
