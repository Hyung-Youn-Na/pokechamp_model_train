import argparse
from contextlib import nullcontext
import fcntl
import json
import os
from pathlib import Path
import signal
import time
import traceback
from ..storage import atomic, read
from .artifacts import now
from .config import DATA, OUTPUT


def main():
    parser=argparse.ArgumentParser(description='EX-066 joint q training and independent evaluation')
    parser.add_argument('stage',choices=['prepare','preflight','train','evaluate','verify'])
    parser.add_argument('--data',type=Path,default=DATA)
    parser.add_argument('--out',type=Path,default=OUTPUT)
    parser.add_argument('--download',action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--recovery-receipt',type=Path)
    parser.add_argument('--phase',choices=['unit','reload','final'],default='final')
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    def interrupted(*_):
        raise KeyboardInterrupt('technical interruption requested')
    signal.signal(signal.SIGTERM,interrupted)
    signal.signal(signal.SIGINT,interrupted)
    from .runtime import gpu_owner
    gpu=args.stage in ('preflight','train','evaluate') or (args.stage=='verify' and args.phase=='reload')
    with (args.out/'coordinator.lock').open('a+') as handle:
        try:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('another EX-066 stage is running') from None
        recovery=None
        if (args.out/'STOP.json').exists() and gpu:
            stop=read(args.out/'STOP.json')
            if args.stage=='preflight' and args.recovery_receipt is not None:
                from .recovery import validate_preflight_recovery
                recovery=validate_preflight_recovery(args.data,args.out,args.recovery_receipt)
                atomic(args.out/f'failures/recovery-entry-{time.time_ns()}.json',
                    dict(at=now(),original_stop=stop,verified_recovery=recovery),immutable=True)
            elif not (args.stage=='train' and args.resume and stop['resumable']):
                raise RuntimeError('dependent execution stopped; see STOP.json')
        if not (args.out/'entry.json').exists():
            atomic(args.out/'entry.json',dict(at=now(),pid=os.getpid(),data=str(args.data)),immutable=True)
        try:
            with gpu_owner(args.out,args.stage) if gpu else nullcontext():
                if args.stage=='prepare':
                    from .prepare import prepare
                    result=prepare(args.data,args.out,args.download)
                    result={'prepared':True,'denominators':result['denominators'],'token_summary':result['token_summary']}
                elif args.stage=='preflight':
                    from .train import preflight
                    result=preflight(args.data,args.out)
                    result={k:result[k] for k in ['passed','checks','optimizer_updates','padding_max_q_difference',
                            'estimated_train_forward_backward_seconds']}
                elif args.stage=='train':
                    from .train import train
                    result=train(args.data,args.out,args.resume)
                elif args.stage=='evaluate':
                    from .evaluate import evaluate
                    result=evaluate(args.data,args.out)
                else:
                    from .verify import unit_tests,final
                    from .evaluate import reload_and_lock
                    result=(unit_tests(args.out) if args.phase=='unit' else
                            reload_and_lock(args.data,args.out) if args.phase=='reload' else final(args.data,args.out))
                    if args.phase=='reload':
                        result={k:result[k] for k in ['passed','maximum_q_difference','reloaded_validation_observations']}
        except BaseException as exc:
            resumable=args.stage=='train' and isinstance(exc,(KeyboardInterrupt,OSError))
            failure=dict(at=now(),stage=args.stage,phase=args.phase,error=str(exc),
                error_type=type(exc).__name__,traceback=traceback.format_exc(),resumable=resumable)
            atomic(args.out/f'failures/{time.time_ns()}.json',failure,immutable=True)
            if gpu or args.stage=='prepare':
                atomic(args.out/'STOP.json',failure)
            raise
        if (args.stage=='train' and args.resume or recovery is not None) and (args.out/'STOP.json').exists():
            original=read(args.out/'STOP.json')
            if original['resumable'] or recovery is not None:
                atomic(args.out/f'failures/resolved-stop-{time.time_ns()}.json',
                    dict(at=now(),original_stop=original,
                         resumed_from_complete_checkpoint=bool(args.resume),preflight_recovery=recovery),immutable=True)
                (args.out/'STOP.json').unlink()
        print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
