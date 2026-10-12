from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from .storage import DEFAULT,ROOT,owner


def main():
    parser=argparse.ArgumentParser(description='EX-065 CPU-only joint q data')
    parser.add_argument('command',choices=('prepare','freeze','capture','inputs','register','collect','export','tokens','audit','pilot-gate','benchmark','recovery-probe'))
    parser.add_argument('--directory',type=Path,default=DEFAULT)
    parser.add_argument('--cohort',choices=('pilot','rest','test','all'),default='pilot')
    parser.add_argument('--workers',type=int,default=32)
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    os.chdir(ROOT/'pokechamp')
    if os.environ.get('PYTHONHASHSEED')!='20260929':
        raise ValueError('start with PYTHONHASHSEED=20260929 for process-count-independent policy iteration')
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[k]='1'
    args.directory.mkdir(parents=True,exist_ok=True)
    from . import manifest,pipeline
    with owner(args.directory):
        if args.command=='prepare':
            result=manifest.prepare(args.directory)
        elif args.command=='freeze':
            result=manifest.freeze(args.directory)
            result={k:v for k,v in result.items() if k!='files'}
        elif args.command in ('capture','inputs','register'):
            games=pipeline.select_games(args.directory,args.cohort)
            if args.limit is not None:
                games=games[:args.limit]
            if args.command=='capture':
                result=pipeline.capture_games(args.directory,games,min(args.workers,4))
            elif args.command=='inputs':
                result=pipeline.generate_inputs(args.directory,games,min(args.workers,8))
            else:
                result=pipeline.register(args.directory,games,manifest.verify(args.directory))
        elif args.command=='collect':
            result=pipeline.collect(args.directory,args.workers,args.limit)
        elif args.command=='recovery-probe':
            from .recovery_probe import run
            result=run(args.directory)
        elif args.command=='benchmark':
            from .benchmark import run
            result=run(args.directory)
        elif args.command=='export':
            result=pipeline.export(args.directory)
        else:
            from . import verify as checks
            result={'tokens':checks.tokens,'audit':checks.audit,'pilot-gate':checks.pilot_gate}[args.command](args.directory)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
