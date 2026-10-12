from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from ..storage import ROOT, atomic, read, sha
from .artifacts import file_manifest, now, validate_checkpoint
from .config import CONFIG
from .evaluate import analyze, checked_lock


def unit_tests(out):
    directory=Path(out)/'verification'
    directory.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    log=directory/f'tests-{stamp}.log'
    commands=[]
    xmls=[]
    returncodes=[]
    totals={key:0 for key in ('tests','failures','errors','skipped')}
    with log.open('w') as handle:
        for name,python,test in [('learning',sys.executable,'test_joint_q_learning.py'),
                                 ('public_loader',str(ROOT/'pokechamp/.venv/bin/python'),'test_joint_q.py')]:
            xml=directory/f'tests-{stamp}-{name}.xml'
            command=[python,'-m','pytest','-q',str(ROOT/'integration/pokechamp/tests'/test),'--junitxml='+str(xml)]
            env=dict(os.environ,PYTHONPATH=str(ROOT)+':'+str(ROOT/'pokechamp'))
            cwd=ROOT if name=='learning' else ROOT/'pokechamp'
            result=subprocess.run(command,cwd=cwd,env=env,stdout=handle,stderr=subprocess.STDOUT)
            if not xml.exists():
                raise RuntimeError('pytest did not produce results: '+str(log))
            suites=ET.parse(xml).getroot()
            for key in totals:
                totals[key]+=sum(int(s.get(key,'0')) for s in suites.iter('testsuite'))
            commands.append(command)
            returncodes.append(result.returncode)
            xmls.append(dict(path=str(xml),sha256=sha(xml)))
    receipt=dict(at=now(),passed=all(c==0 for c in returncodes) and totals['skipped']==0,
        commands=commands,returncodes=returncodes,**totals,log=str(log),log_sha256=sha(log),
        xmls=xmls,test_source_sha256=sha(ROOT/'integration/pokechamp/tests/test_joint_q_learning.py'))
    atomic(directory/f'tests-{stamp}.json',receipt,immutable=True)
    atomic(directory/'tests.json',receipt)
    if not receipt['passed']:
        raise RuntimeError('required tests failed: '+str(log))
    return receipt


def final(data,out):
    out=Path(out)
    lock=checked_lock(data,out)
    tests=read(out/'verification/tests.json')
    if not tests['passed'] or tests['test_source_sha256']!=sha(ROOT/'integration/pokechamp/tests/test_joint_q_learning.py'):
        raise ValueError('required unit test evidence missing/changed')
    preflight=read(out/'preflight/report.json')
    selection=read(out/'training/selection.json')
    reload=read(out/'reload/report.json')
    if not preflight['passed'] or not reload['passed'] or selection['updates']!=615:
        raise ValueError('mandatory execution checks incomplete')
    for cp in [out/'training/initial']+[out/f'training/epoch-{e}' for e in (1,2,3)]:
        saved=validate_checkpoint(cp)
        if saved['base_fingerprints']!=preflight['initial_base_fingerprints']:
            raise ValueError('checkpoint base fingerprint differs')
    metrics=read(out/'evaluation/metrics.json') if (out/'evaluation/metrics.json').exists() else analyze(data,out)
    costs={}
    for stage in ('prepared','preflight','training','reload','evaluation'):
        costs[stage]=read(out/stage/'progress.json')
    for path in sorted(list(out.glob('versions/*/preflight/progress.json'))+
                       list(out.glob('versions/*/prepared/progress.json'))):
        costs[str(path.relative_to(out))]=read(path)
    for path in sorted(out.glob('diagnostics/*/progress.json')):
        costs[str(path.relative_to(out))]=read(path)
    disk_bytes=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    report=dict(at=now(),completed=True,config=CONFIG,selected_checkpoint=selection['checkpoint'],
        selected_epoch=selection['selected_epoch'],validation_mse=selection['epoch_validation_mse'],
        tests=tests,denominators=read(out/'prepared/manifest.json')['denominators'],
        preflight_checks=preflight['checks'],reload_max_q_difference=reload['maximum_q_difference'],
        padding_max_q_difference=preflight['padding_max_q_difference'],base_unchanged=True,
        lora_changed=selection['lora_changed'],head_changed=selection['head_changed'],
        costs=costs,total_gpu_compute_seconds=sum(v.get('gpu_seconds',0) for v in costs.values()),
        artifact_bytes=disk_bytes,test_evaluations_per_model=1,metrics=metrics,
        candidate_order_diagnostic=reload['candidate_order_diagnostic'])
    atomic(out/'report.json',report,immutable=True)
    table=[]
    for model in ('initial','selected','constant_0.5','train_mean_constant'):
        value=metrics['metrics'][model]['all']['metrics']
        table.append(f'| {model} | {value["mse"]:.6f} | {value["mae"]:.6f} | '
                     f'{value["regret"]:.6f} | {100*value["best_action_rate"]:.2f}% |')
    text=(f'# EX-066 공동 q 학습·독립 평가 보고\n\n'
        f'필수 검증·3epoch/615update 학습·독립 test·봉인을 완료했다. 선택은 epoch{selection["selected_epoch"]}이며 '
        f'validation 관측 평균 MSE는 {selection["validation_mse"]:.6f}다.\n\n'
        '| 모델 | test MSE | MAE | regret | 최고 후보 선택률 |\n|---|---:|---:|---:|---:|\n'+'\n'.join(table)+'\n\n'
        f'test는20경기/709관측/6369후보이며 초기·선택 모델별1회 평가했다. '
        f'재로딩 최대 q 차이는 {reload["maximum_q_difference"]:.8g}, padding 차이는 '
        f'{preflight["padding_max_q_difference"]:.8g}다. Base 불변·LoRA/head 변경을 확인했다.\n\n'
        f'모델 계산 시간은 {report["total_gpu_compute_seconds"]/3600:.2f} GPU시간, '
        f'보존 용량은 {disk_bytes/2**30:.2f} GiB다. 단계별 실제 시간·최대 VRAM은 [기계 보고](report.json)에 있다.\n\n'
        '전체·선택력 관측, 경기/상대팀, 중복 민감도,5개 팀 그룹 paired bootstrap95% CI는 '
        '[평가 지표](evaluation/metrics.json), 후보 순서 민감도는 [validation 진단](reload/report.json)을 따른다. '
        '그룹5개와 고정 자기 팀/Abyssal 후속 정책 조건이라는 해석 한계를 유지한다. '
        '배틀 승률 개선·세 RLCD 환경 차이는 미평가다.\n\n'
        '최초 preflight의 padding 경계 실패와 수정 전 source/준비 자료는 `versions/preflight-v1/`에 '
        '보존했다. 마스크된 padding만 제거하는 수정과 기존 무패딩 q 불변을 독립 검증한 뒤 '
        '동일 입력·학습 조건에서 preflight를 재검사했다. GPU2 지정(D-105) 뒤 사용 중이면 '
        '다른 유휴 GPU를 쓰라는 후속 지시(D-106)에 따라 GPU1로 고정했다. 변경 전 준비와 '
        'CPU 중단 증거도 보존했다. 최초 실패 시의 GPU 시간 일부는 측정 하한이며 '
        '위 GPU시간은 CUDA event로 기록된 구간의 합이다. 학습/test 재수집0이다.\n\n'
        '초기 validation 중 유한한0경사를 잘못 차단하는 경계 검사를 독립 재현했다. '
        'optimizer update0에서 원 source·사전검사·중단 증거를 보존하고 이 검사만 교정했다. '
        '설정·입력·초기 checkpoint를 유지하고 해당 RNG에서 재개했으며 반복된 초기 validation '
        '비용도 누적했다. [교정 원문](gradient-recovery-receipt.json)을 따른다.\n\n'
        f'선택 checkpoint: `{selection["checkpoint"]}`. LoRA와 별도 value head, optimizer/RNG/cursor, '
        'Base/tokenizer revision·renderer/data/source 해시를 보존했다.\n\n'
        '[재실행 명령](commands.md) · [동결 설정](prepared/manifest.json) · '
        '[test 잠금](evaluation-lock.json) · [봉인 목록](seal.json).\n')
    (out/'report.md').write_text(text)
    manifest=file_manifest(out)
    manifest.pop('seal.json',None)
    # Locks are mutable coordination metadata; they are not research evidence.
    manifest={k:v for k,v in manifest.items() if not k.endswith('.lock')}
    atomic(out/'seal.json',dict(at=now(),files=manifest,completed=True),immutable=True)
    for name,expected in manifest.items():
        if sha(out/name)!=expected:
            raise ValueError('final seal validation failed: '+name)
    return dict(completed=True,selected_epoch=selection['selected_epoch'],
        report=str(out/'report.md'),selected_checkpoint=selection['checkpoint'],sealed_files=len(manifest))
