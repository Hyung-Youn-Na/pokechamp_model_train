"""Dedicated CPU-only EX-067 entry point, without touching EX-066's launcher."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from .storage import ROOT, atomic, digest, owner, read, sha
from . import tera_config as config


def _result(value):
    # Source file inventory and detailed reports remain on disk.
    return {k:v for k,v in value.items() if k not in ('files','sources','data_files','test_sources')}


def execute(command,directory,cohort,recovery_parent=None):
    from . import manifest,pipeline,verify,tera_verify
    from . import benchmark,recovery_probe
    directory=Path(directory)
    if command=='prepare':
        result=manifest.prepare(directory,experiment=config.EXPERIMENT)
        tera_verify.preserve_ex066(directory)
        return result
    if command=='prepare-recovery':
        from .tera_recovery import prepare
        return prepare(recovery_parent,directory)
    config.validate_manifest(read(directory/'manifest.json'))
    if command=='freeze':
        return _result(manifest.freeze(directory))
    source=manifest.verify(directory)
    if command=='preflight':
        return _result(tera_verify.preflight(directory))
    if command in ('capture','inputs','register','benchmark','recovery-probe','collect'):
        tera_verify.preflight(directory)
    if command in ('capture','inputs','register'):
        games=pipeline.select_games(directory,cohort)
        if command=='capture':
            return dict(completed=pipeline.capture_games(directory,games,config.CAPTURE_WORKERS))
        if command=='inputs':
            return dict(completed=pipeline.generate_inputs(directory,games,config.INPUT_WORKERS))
        return pipeline.register(directory,games,source)
    if command=='benchmark':
        return benchmark.run(directory,worker_counts=(1,16),task_count=32)
    if command=='recovery-probe':
        return recovery_probe.run(directory,baseline_workers=16)
    if command=='verification':
        return tera_verify.verification(directory)
    if command=='collect':
        evidence=read(directory/'verification.json')
        if not evidence['passed'] or evidence['source_id']!=source:
            raise ValueError('production collection requires same-source invariant/recovery verification')
        return pipeline.collect(directory,workers=config.WORKERS)
    if command=='export':
        return pipeline.export(directory)
    if command=='tokens':
        return verify.tokens(directory)
    if command=='audit':
        tera_verify.input_isolation(directory)
        return verify.audit(directory)
    if command=='gate':
        return tera_verify.cohort_gate(directory,cohort)
    if command=='resume-resources':
        path=directory/'STOP'
        stopped=read(path)
        if stopped.get('reason')!='resources':
            raise ValueError('only a verified resource pause can resume without a recovery version')
        pipeline.admission(directory)
        atomic(directory/'verification'/f'resource-resume-{time.time_ns()}.json',
               dict(stopped=stopped,source_id=source,at=time.time()),immutable=True)
        path.unlink()
        return dict(resumed=True,source_id=source)
    from .tera_outputs import report,export_viewer,seal_and_copy
    if command=='report':
        target=directory/('final' if cohort=='test' else cohort)
        return report(directory,output_directory=target)
    if command=='viewer':
        data=read(directory/'final/report.json')
        return export_viewer(directory,ROOT/'exports/battle_viewers/ex067',report_data=data,
                             catalog=ROOT/'exports/battle_viewers/index.html')
    if command=='browser':
        return tera_verify.browser(directory)
    if command=='seal-copy':
        tera_verify.browser(directory)
        tera_verify.preserve_ex066(directory,final=True)
        return seal_and_copy(directory,Path(config.BACKUP),required_complete=True)
    raise ValueError('unknown command')


def stages():
    result=[('preflight','pilot'),('capture','pilot'),('inputs','pilot'),('register','pilot'),
            ('benchmark','pilot'),('recovery-probe','pilot'),('verification','pilot'),
            ('collect','pilot'),('export','pilot'),('tokens','pilot'),('audit','pilot'),
            ('report','pilot'),('gate','pilot')]
    for cohort in ('rest','test'):
        result.extend((step,cohort) for step in ('capture','inputs','register','collect','export','tokens','audit','report','gate'))
    result.extend([('viewer','test'),('browser','test'),('seal-copy','test')])
    return result


def run(directory):
    from .manifest import verify
    directory=Path(directory)
    source=verify(directory)
    jobs=ROOT/'.pokechamp-data/jobs/ex067-abyssal-tera-joint-q'/digest(str(directory))[:12]
    jobs.mkdir(parents=True,exist_ok=True)
    state_path=jobs/'state.json'
    schedule=stages()
    state=read(state_path) if state_path.exists() else dict(source_id=source,directory=str(directory),
          started_at=time.time(),next_stage=0,completed=[],status='running')
    if state['source_id']!=source or state['directory']!=str(directory):
        raise ValueError('runner source changed; explicit versioned recovery required')
    if state['status']=='complete':
        return state
    # The supervisor and child stage use different ownership files. Other stage
    # invocations still cannot mutate the ledger while a child owns it.
    with owner(jobs):
        for i in range(state['next_stage'],len(schedule)):
            command,cohort=schedule[i]
            state.update(status='running',stage=command,cohort=cohort,next_stage=i,updated_at=time.time())
            atomic(state_path,state)
            attempt=1+len(list(jobs.glob(f'{i:02d}-{command}-*.log')))
            logpath=jobs/f'{i:02d}-{command}-{attempt}.log'
            argv=[str(ROOT/'scripts/pokechamp-joint-q-tera'),command,'--directory',str(directory),'--cohort',cohort]
            with logpath.open('w') as log:
                process=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
            if process.returncode:
                state.update(status='stopped',exit_code=process.returncode,log=str(logpath),updated_at=time.time())
                atomic(state_path,state)
                raise RuntimeError('EX-067 stage failed: '+command+'; evidence: '+str(logpath))
            state['completed'].append(dict(index=i,command=command,cohort=cohort,log=str(logpath),
                                           log_sha256=sha(logpath),at=time.time()))
            state['next_stage']=i+1
            atomic(state_path,state)
        state.update(status='complete',finished_at=time.time())
        atomic(state_path,state)
    return state


def main():
    parser=argparse.ArgumentParser(description='EX-067 CPU Abyssal Tera data collection')
    parser.add_argument('command',choices=('prepare','prepare-recovery','freeze','preflight','capture','inputs','register',
        'benchmark','recovery-probe','verification','collect','export','tokens','audit','report','gate',
        'viewer','browser','seal-copy','run','resume-resources'))
    parser.add_argument('--directory',type=Path,default=config.DEFAULT)
    parser.add_argument('--cohort',choices=('pilot','rest','test'),default='pilot')
    parser.add_argument('--recovery-parent',type=Path,default=config.DEFAULT)
    args=parser.parse_args()
    args.directory=args.directory.resolve()
    if os.environ.get('PYTHONHASHSEED')!='20260930' or os.environ.get('CUDA_VISIBLE_DEVICES')!='':
        raise ValueError('use the CPU-only scripts/pokechamp-joint-q-tera launcher')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        if os.environ.get(name)!='1':
            raise ValueError('native threads must be one')
    os.chdir(ROOT/'pokechamp')
    args.directory.mkdir(parents=True,exist_ok=True)
    if args.command=='run':
        result=run(args.directory)
    else:
        with owner(args.directory):
            result=execute(args.command,args.directory,args.cohort,args.recovery_parent.resolve())
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':
    main()
