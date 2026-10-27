"""EX116 stages. No implicit training from status/help or data preparation."""
import argparse
import fcntl
import json
from pathlib import Path
import time
from .config import OUTPUT,CONFIG
from .data import prepare_training,dump,sha
from .prepare import evaluation,diagnostics,freeze,verify


def preflight(output):
    from .launcher import launch
    if (output/'preflight-selected.json').exists():raise FileExistsError('preflight choice already frozen')
    failures=[]
    for cap in CONFIG['microbatch_candidates']:
        if (output/f'preflight-{cap}.json').exists():raise FileExistsError('preflight already attempted')
        started=time.time_ns()
        try:launch('preflight',output,microbatch=cap)
        except Exception as exc:
            files=[p for p in output.glob(f'failure-preflight-{cap}-rank-*.json') if p.stat().st_mtime_ns>=started]
            details='\n'.join(p.read_text() for p in files)+'\n'+repr(exc)
            receipts=sorted(output.glob('preflight-receipt-*.json'),key=lambda p:p.stat().st_mtime_ns)
            if receipts:details+='\n'+receipts[-1].read_text()
            allowed=any(v in details for v in ['batch readout inequivalent','batch gradient inequivalent','out of memory','exceeds 44 GiB','exceeds 64 GiB','GPU memory budget'])
            failures.append(dict(microbatch=cap,error=repr(exc),files=[str(p) for p in files],allowed_lower_cap=allowed))
            dump(output/'preflight-attempts.json',failures)
            if not allowed:raise
            continue
        dump(output/'preflight-selected.json',dict(microbatch=cap,passed=True,receipt_sha=sha(output/f'preflight-{cap}.json'),prior_failures=failures))
        return
    raise RuntimeError('all approved microbatch sizes failed; training prohibited')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare-training','prepare-evaluation','freeze','preflight','train','evaluate','diagnose','export','all','status'])
    p.add_argument('--rules',type=Path);p.add_argument('--resume',type=Path)
    a=p.parse_args();output=OUTPUT
    if a.resume and a.action!='train':p.error('--resume only with train')
    if a.action=='status':
        for name in ['training-validation.json','evaluation-validation.json','preflight-selected.json','progress.json','selection.json','active.json','completion.json','pipeline-failure.json']:
            if (output/name).exists():print(name,(output/name).read_text())
        return
    output.mkdir(parents=True,exist_ok=True)
    with (output/'controller.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.action=='prepare-training':prepare_training(output)
        elif a.action=='prepare-evaluation':
            if a.rules is None:p.error('--rules is required')
            evaluation(output,a.rules);diagnostics(output)
        elif a.action=='freeze':freeze(output)
        elif a.action=='preflight':verify(output);preflight(output)
        elif a.action=='export':
            from .report import export
            verify(output);export(output)
        else:
            from .launcher import launch
            verify(output)
            if a.action=='all':
                try:
                    if not (output/'preflight-selected.json').exists():preflight(output)
                    launch('train',output);launch('evaluate',output);launch('diagnose',output)
                    from .report import export
                    export(output)
                except BaseException as exc:
                    dump(output/'pipeline-failure.json',dict(time=time.time(),error=repr(exc)));raise
            else:
                if not (output/'preflight-selected.json').exists():raise RuntimeError('preflight not passed')
                launch(a.action,output,resume=a.resume)
if __name__=='__main__':main()
