"""The authorized prepare→audit→preflight→train→evaluate→battle→export stages."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time
import traceback

from . import config as c
from .resource import own_gpu, own_run
from .storage import atomic, read, sha


def main(argv=None):
    parser=argparse.ArgumentParser(description='EX-071 replay imitation and first fixed battle evaluation')
    parser.add_argument('stage',choices=('prepare','audit','preflight','train','evaluate','battle','export','status'))
    parser.add_argument('--output',type=Path,default=c.OUTPUT)
    parser.add_argument('--resume',action='store_true',help='resume training from the same clock and complete checkpoint')
    args=parser.parse_args(argv)
    if args.resume and args.stage!='train':
        parser.error('--resume is only valid for train')
    out=args.output.resolve()
    if args.stage=='status':
        result={p.name:read(p) for p in (out/'stage.json',out/'preparation/recovery-progress.json',out/'training/progress.json',out/'battle/progress.json') if p.exists()}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    with own_run(out):
        stamp=str(time.time_ns())
        atomic(out/'stage.json',dict(stage=args.stage,status='running',started_at=time.time()))
        try:
            if args.stage=='prepare':
                from . import dataset
                result=dataset.prepare(out)
            elif args.stage=='audit':
                from .verification import audit
                result=audit(out)
            elif args.stage in ('preflight','train','evaluate'):
                from .verification import verify_gate
                verify_gate(out)
                gate=read(out/'audit.json')
                if not gate.get('passed') or gate['prepared_manifest_sha256']!=sha(out/'prepared/manifest.json'):
                    raise ValueError('passing exact dataset audit required')
                with own_gpu(out,args.stage):
                    from . import learning
                    result=learning.train(out,resume=args.resume) if args.stage=='train' else getattr(learning,args.stage)(out)
                if args.stage=='evaluate':
                    from .outputs import battle_readiness
                    battle_readiness(out)
            elif args.stage=='battle':
                from .verification import verify_gate
                verify_gate(out)
                from . import battle
                with own_gpu(out,args.stage):
                    result=battle.run(out,out/'schedule.json',out/'battle-readiness.json')
            else:
                from .outputs import export
                result=export(out)
            status='interrupted' if isinstance(result,dict) and result.get('status')=='interrupted' else 'complete'
            atomic(out/'stage-events'/f'{stamp}-{args.stage}-{status}.json',
                   dict(stage=args.stage,status=status,at=time.time(),result=result),immutable=True)
            atomic(out/'stage.json',dict(stage=args.stage,status=status,at=time.time(),result=result))
            print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
            return 3 if status=='interrupted' else 0
        except Exception as exc:
            failure=dict(stage=args.stage,status='failed',at=time.time(),error=type(exc).__name__,detail=str(exc),
                         traceback=traceback.format_exc())
            atomic(out/'stage-events'/f'{stamp}-{args.stage}-failed.json',failure,immutable=True)
            atomic(out/'stage.json',failure)
            print(json.dumps(failure,ensure_ascii=False,indent=2),file=sys.stderr)
            return 1


if __name__=='__main__':
    raise SystemExit(main())
