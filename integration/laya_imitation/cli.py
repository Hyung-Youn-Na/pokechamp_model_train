"""`scripts/laya-imitation <command>`: data, train, evaluate, serve, battle, general, v2, tera, effects, v3, v4, v5, compare,
compare2, compare3, compare4, compare5, weighted, compare6, compare7, compare8, compare9, h2h, regression, status.

`status` only reads saved JSON. Every writing step refuses to overwrite a finished output and
nothing is re-run automatically after a failure.
"""
from __future__ import annotations
import argparse
import json
import sys

from . import config as c


def status():
    from .storage import read
    out = {}
    for name, path in (('dataset', c.DATASET / 'validation.json'), ('training', c.RUN_TRAINING / 'status.json'),
                       ('evaluation', c.RUN_TRAINING / 'evaluation/report.json'),
                       ('battle', c.RUN_BATTLE / 'status.json'), ('general', c.RUN_GENERAL / 'status.json'),
                       ('v2_features', c.V2_FEATURES / 'manifest.json'), ('v2_dataset', c.V2_DATASET / 'validation.json'),
                       ('v2_training', c.RUN_V2_TRAINING / 'status.json'), ('compare', c.RUN_COMPARE / 'status.json'),
                       ('tera_training', c.RUN_TERA_TRAINING / 'status.json'),
                       ('compare2', c.RUN_COMPARE2 / 'status.json'),
                       ('effect_knowledge', c.EFFECT_KNOWLEDGE / 'manifest.json'),
                       ('effect_training', c.RUN_EFFECT_TRAINING / 'status.json'),
                       ('compare3', c.RUN_COMPARE3 / 'status.json'),
                       ('v3_features', c.V3_FEATURES / 'manifest.json'), ('v3_dataset', c.V3_DATASET / 'validation.json'),
                       ('v3_training', c.RUN_V3_TRAINING / 'status.json'),
                       ('compare4', c.RUN_COMPARE4 / 'status.json'),
                       ('v4_features', c.V4_FEATURES / 'manifest.json'), ('v4_dataset', c.V4_DATASET / 'validation.json'),
                       ('v4_training', c.RUN_V4_TRAINING / 'status.json'),
                       ('compare5', c.RUN_COMPARE5 / 'status.json'),
                       ('outcome_weights', c.OUTCOME_WEIGHTS / 'manifest.json'),
                       ('weighted_training', c.RUN_WEIGHTED_TRAINING / 'status.json'),
                       ('compare6', c.RUN_COMPARE6 / 'status.json'),
                       ('h2h', c.RUN_H2H / 'status.json'), ('h2h2', c.RUN_H2H2 / 'status.json'),
                       ('item_state', c.ITEM_STATE / 'manifest.json'), ('v5_features', c.V5_FEATURES / 'manifest.json'),
                       ('v5_dataset', c.V5_DATASET / 'validation.json'), ('v5_training', c.RUN_V5_TRAINING / 'status.json'),
                       ('compare7', c.RUN_COMPARE7 / 'status.json'), ('h2h3', c.RUN_H2H3 / 'status.json'),
                       ('compare8', c.RUN_COMPARE8 / 'status.json'), ('compare9', c.RUN_COMPARE9 / 'status.json')):
        out[name] = read(path) if path.exists() else None
    print(json.dumps(out, ensure_ascii=False, indent=1))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='laya-imitation')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('data', help='build laya-compact-imitation/v1 (CPU)')
    p = sub.add_parser('train', help='EX-118 preflight + training + selection on GPU0')
    p.add_argument('--preflight-only', action='store_true')
    sub.add_parser('evaluate', help='EX-118 locked test, once per model')
    p = sub.add_parser('serve', help='loopback HTTP policy for EX-119')
    p.add_argument('--checkpoint', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--port', type=int, default=0)
    p.add_argument('--ready-file')
    p.add_argument('--device', default='cuda', choices=('cuda', 'cpu'))
    p.add_argument('--render', default='v1', choices=('v1', 'v2', 'v3', 'v4', 'v5', 'v2fix', 'v2info', 'v2fixtd'))
    p = sub.add_parser('battle', help='EX-119 stages')
    p.add_argument('stage', choices=('mock', 'prepare', 'execute', 'export'))
    p = sub.add_parser('general', help='EX-120 stages (new-team generalization)')
    p.add_argument('stage', choices=('collect', 'mock', 'prepare', 'execute', 'export'))
    p = sub.add_parser('v2', help='EX-121 renderer v2 stages')
    p.add_argument('stage', choices=('measure', 'features', 'data', 'parity', 'train', 'evaluate'))
    p.add_argument('--preflight-only', action='store_true')
    p = sub.add_parser('tera', help='EX-124 Tera knowledge stages')
    p.add_argument('stage', choices=('data', 'train', 'evaluate'))
    p.add_argument('--preflight-only', action='store_true')
    p = sub.add_parser('effects', help='EX-126 move/item/Ability effect knowledge stages (GPU2)')
    p.add_argument('stage', choices=('data', 'train', 'evaluate'))
    p.add_argument('--preflight-only', action='store_true')
    p = sub.add_parser('v3', help='EX-128 renderer v3 (opponent sets) + Tera knowledge stages (GPU0)')
    p.add_argument('stage', choices=('measure', 'features', 'data', 'parity', 'train', 'evaluate'))
    p.add_argument('--preflight-only', action='store_true')
    p = sub.add_parser('v4', help='EX-130 renderer v4 (known failures, switch-in offense) + Tera knowledge stages (GPU1)')
    p.add_argument('stage', choices=('measure', 'features', 'data', 'parity', 'train', 'evaluate'))
    p.add_argument('--preflight-only', action='store_true')
    p = sub.add_parser('v5', help='EX-136 renderer v5 (opponent item state, status/turn counters) + Tera knowledge (GPU0)')
    p.add_argument('stage', choices=('reparse', 'measure', 'features', 'data', 'parity', 'train', 'evaluate'))
    p.add_argument('--preflight-only', action='store_true')
    p = sub.add_parser('weighted', help='EX-132 outcome-weighted imitation (v2 + Tera knowledge) stages (GPU0)')
    p.add_argument('stage', choices=('weights', 'train', 'evaluate'))
    p.add_argument('--preflight-only', action='store_true')
    p = sub.add_parser('compare', help='EX-122 v1 vs v2 battle stages')
    p.add_argument('stage', choices=('mock', 'prepare', 'execute', 'export'))
    p = sub.add_parser('compare2', help='EX-125 v2 vs v2+Tera battle stages (GPU1, port 8109)')
    p.add_argument('stage', choices=('mock', 'prepare', 'execute', 'export'))
    p = sub.add_parser('compare3', help='EX-127 v2+Tera vs v2+Tera+effects battle stages (GPU2, port 8108)')
    p.add_argument('stage', choices=('mock', 'prepare', 'execute', 'export'))
    p = sub.add_parser('compare4', help='EX-129 v2+Tera vs v3+Tera battle stages (GPU0, port 8107)')
    p.add_argument('stage', choices=('mock', 'prepare', 'execute', 'export'))
    p = sub.add_parser('compare5', help='EX-131 v2+Tera vs v4+Tera battle stages (GPU1, port 8109)')
    p.add_argument('stage', choices=('mock', 'prepare', 'execute', 'export'))
    p = sub.add_parser('compare6', help='EX-133 v2+Tera vs outcome-weighted v2+Tera battle stages (GPU0, port 8107)')
    p.add_argument('stage', choices=('mock', 'prepare', 'execute', 'export'))
    p = sub.add_parser('compare7', help='EX-137 v4+Tera vs v5+Tera battle stages (GPU0, port 8107)')
    p.add_argument('stage', choices=('mock', 'prepare', 'execute', 'export'))
    p = sub.add_parser('compare8', help='EX-139 v2+Tera (EX-124) on D-195-corrected inputs, fix/info (GPU1, port 8109)')
    p.add_argument('stage', choices=('mock', 'probe', 'prepare', 'execute', 'export'))
    p = sub.add_parser('compare9', help='EX-140 EX-124 on v2fix: Tera-pooled k=1/3, Tera defence text (GPU1, 8109)')
    p.add_argument('stage', choices=('mock', 'prepare', 'execute', 'export'))
    p = sub.add_parser('h2h', help='EX-134 / EX-135 / EX-138 laya-vs-laya battle stages (GPU2, port 8108)')
    p.add_argument('stage', choices=('mock', 'prepare', 'execute', 'export'))
    p.add_argument('--study', default='EX-134', choices=('EX-134', 'EX-135', 'EX-138'))
    p = sub.add_parser('regression', help='NHJ-20261028 fixed-decision regression set: build once, score a served model')
    p.add_argument('stage', choices=('build', 'baseline', 'score'))
    p.add_argument('--endpoint', help='http://127.0.0.1:PORT of a running serve (score)')
    p.add_argument('--out', help='result JSON path, never overwritten (score)')
    sub.add_parser('status', help='read saved status only')
    args = parser.parse_args(argv)
    if args.command == 'data':
        from .data import build
        manifest, validation = build()
        print(json.dumps(dict(counts=manifest['counts'], validation=validation), ensure_ascii=False))
    elif args.command == 'train':
        from .training import run
        run(preflight_only=args.preflight_only)
    elif args.command == 'evaluate':
        from .evaluation import run
        run()
    elif args.command == 'serve':
        from .serving import main as serve
        serve(args.checkpoint, args.model, args.port, args.ready_file, args.device, args.render)
    elif args.command == 'battle':
        from . import battle
        getattr(battle, args.stage)()
    elif args.command == 'v2':
        if args.stage in ('measure', 'features', 'data', 'parity'):
            from . import data_v2
            {'measure': data_v2.measure, 'features': data_v2.build_features, 'data': data_v2.build,
             'parity': data_v2.parity}[args.stage]()
        elif args.stage == 'train':
            from .training import EX121, run
            run(preflight_only=args.preflight_only, spec=EX121)
        else:
            from .evaluation_v2 import run
            run()
    elif args.command == 'tera':
        if args.stage == 'data':
            from .tera_knowledge import build
            build()
        elif args.stage == 'train':
            from .training import EX124, run
            run(preflight_only=args.preflight_only, spec=EX124)
        else:
            from .evaluation_tera import run
            run()
    elif args.command == 'effects':
        if args.stage == 'data':
            from .effect_knowledge import build
            build()
        elif args.stage == 'train':
            from .training import EX126, run
            run(preflight_only=args.preflight_only, spec=EX126)
        else:
            from .evaluation_effects import run
            run()
    elif args.command == 'v3':
        if args.stage in ('measure', 'features', 'data', 'parity'):
            from . import data_v3
            {'measure': data_v3.measure, 'features': data_v3.build_features, 'data': data_v3.build,
             'parity': data_v3.parity}[args.stage]()
        elif args.stage == 'train':
            from .training import EX128, run
            run(preflight_only=args.preflight_only, spec=EX128)
        else:
            from .evaluation_v3 import run
            run()
    elif args.command == 'v4':
        if args.stage in ('measure', 'features', 'data', 'parity'):
            from . import data_v4
            {'measure': data_v4.measure, 'features': data_v4.build_features, 'data': data_v4.build,
             'parity': data_v4.parity}[args.stage]()
        elif args.stage == 'train':
            from .training import EX130, run
            run(preflight_only=args.preflight_only, spec=EX130)
        else:
            from .evaluation_v4 import run
            run()
    elif args.command == 'v5':
        if args.stage == 'reparse':
            from .item_state import reparse
            reparse()
        elif args.stage in ('measure', 'features', 'data', 'parity'):
            from . import data_v5
            {'measure': data_v5.measure, 'features': data_v5.build_features, 'data': data_v5.build,
             'parity': data_v5.parity}[args.stage]()
        elif args.stage == 'train':
            from .training import EX136, run
            run(preflight_only=args.preflight_only, spec=EX136)
        else:
            from .evaluation_v5 import run
            run()
    elif args.command == 'weighted':
        if args.stage == 'weights':
            from .outcome_weights import build
            build()
        elif args.stage == 'train':
            from .training import EX132, run
            run(preflight_only=args.preflight_only, spec=EX132)
        else:
            from .evaluation_v2tw import run
            run()
    elif args.command == 'compare':
        from . import comparison
        getattr(comparison, args.stage)()
    elif args.command == 'compare2':
        from . import comparison
        getattr(comparison, args.stage + '2')()
    elif args.command == 'compare3':
        from . import comparison
        getattr(comparison, args.stage + '3')()
    elif args.command == 'compare4':
        from . import comparison
        getattr(comparison, args.stage + '4')()
    elif args.command == 'compare5':
        from . import comparison
        getattr(comparison, args.stage + '5')()
    elif args.command == 'compare6':
        from . import comparison
        getattr(comparison, args.stage + '6')()
    elif args.command == 'compare7':
        from . import comparison
        getattr(comparison, args.stage + '7')()
    elif args.command == 'compare8':
        from . import variant_battle
        getattr(variant_battle, args.stage)()
    elif args.command == 'compare9':
        from . import tera_battle
        getattr(tera_battle, args.stage)()
    elif args.command == 'regression':
        from . import regression
        if args.stage == 'build':
            doc = regression.build()
            print(json.dumps(dict(cases=len(doc['cases']), digest=doc['digest']), ensure_ascii=False))
        elif args.stage == 'baseline':
            print(json.dumps(regression.baseline(regression.read(regression.FIXTURE))[1], ensure_ascii=False, indent=1))
        else:
            if not args.endpoint or not args.out:
                parser.error('regression score needs --endpoint and --out')
            print(regression.table(regression.score(args.endpoint, args.out)))
    elif args.command == 'h2h':
        from . import headtohead
        getattr(headtohead, args.stage)(headtohead.STUDIES[args.study])
    elif args.command == 'general':
        from . import generalization
        getattr(generalization, args.stage)()
    else:
        status()
    return 0


if __name__ == '__main__':
    sys.exit(main())
