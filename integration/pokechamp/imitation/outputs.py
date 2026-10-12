"""Locked stage handoff and the Korean report, from preserved evidence only."""
from __future__ import annotations
from collections import Counter
import os
from pathlib import Path
import subprocess
import time

from . import config as c
from .storage import atomic, jsonl, read, sha


def battle_readiness(directory):
    directory=Path(directory).resolve()
    lock_path=directory/'evaluation-lock.json'
    parity_path=directory/'reload/serving-parity.json'
    lock,parity=read(lock_path),read(parity_path)
    report=read(directory/'evaluation/report.json')
    if not parity.get('passed') or set(report['metrics'])!={'initial','selected'}:
        raise ValueError('both locked test passes and serving parity are required')
    for model in ('initial','selected'):
        receipt=read(directory/'evaluation'/f'completed-{model}.json')
        if receipt['predictions_sha256']!=sha(directory/'evaluation'/f'test-{model}.jsonl'):
            raise ValueError('test predictions changed before battle handoff')
    resource=read(directory/'resource.json')
    result=dict(passed=True,schedule_sha256=sha(directory/'schedule.json'),
        models={name:dict(checkpoint=path,checkpoint_sha256=lock['checkpoint_sha256'][name])
                for name,path in lock['model_checkpoints'].items()},
        resource=dict(gpu_index=resource['physical_gpu'],uuid=resource['uuid']),
        evaluation_lock=dict(path=str(lock_path),sha256=sha(lock_path)),
        serving_parity=dict(path=str(parity_path),sha256=sha(parity_path)),
        python=str(c.KEV_PYTHON),port=8021)
    from .battle import verify_readiness
    path=directory/'battle-readiness.json'
    if path.exists():
        if read(path)!=result:raise ValueError('existing battle readiness differs')
    else:atomic(path,result,immutable=True)
    verify_readiness(path,directory/'schedule.json')
    return result


def estimation_summary(directory):
    path=Path(directory)/'preparation/imputation.jsonl'
    totals=Counter()
    if not path.exists():return dict(available=False)
    for replay in jsonl(path):
        for side,slots in (replay.get('value') or {}).items():
            totals['imputed_perspectives']+=1
            for slot in slots:
                totals['sets']+=1
                observed=slot['observed']
                totals['revealed_moves']+=len(observed['moves'])
                totals['inferred_moves']+=len(slot['inferred_moves'])
                totals['core_fields']+=3
                totals['inferred_core_fields']+=len(slot['inferred_fields'])
                totals['other_fields']+=len(slot['inferred_other_fields'])
    result=dict(totals,available=True,unit='successfully_imputed_sets_before_recovery_exclusions')
    moves=totals['revealed_moves']+totals['inferred_moves']
    result['inferred_move_fraction']=totals['inferred_moves']/moves if moves else None
    result['inferred_core_fraction']=totals['inferred_core_fields']/totals['core_fields'] if totals['core_fields'] else None
    return result


def write_report(directory):
    directory=Path(directory).resolve()
    paths={'prepared':'prepared/manifest.json','inputs':'preparation/inputs.json',
           'audit':'audit.json','preflight':'preflight/report.json','selection':'training/selection.json',
           'offline':'evaluation/report.json','battle':'battle/result.json','parity':'reload/serving-parity.json',
           'viewer':'final/viewer-check.json','training':'training/progress.json',
           'resource':'resource.json','qualification':'audit-gate.json',
           'resume':'execution/resume-completed.json','resume_missing':'execution/resume-not-performed.json'}
    evidence={key:read(directory/path) for key,path in paths.items() if (directory/path).exists()}
    estimation=estimation_summary(directory)
    lines=['# EX-071 Qwen 4B 리플레이 모방 학습과 첫 배틀 평가','',
        '관측된 선택의 재현과 실제 배틀 성능을 별도로 평가했다. 출력은 행동 선택 확률이며 승률/q가 아니다.',
        '기존 EX-066/GPU1 학습은 이번 자료·모델·평가와 분리하여 보존한다. 자기대국과 추가 설정 탐색은 수행하지 않는다.','']
    if 'prepared' in evidence:
        counts=evidence['prepared']['counts'];inputs=evidence['inputs']
        lines += ['## 데이터와 정보 경계','',
            f"출발 {counts['source_replays']:,}경기에서 기존 평가팀 구성과 겹치는 {counts['excluded_replays']:,}경기를 제외했다. "
            f"경기/양측 관점/6종 팀 연결 {inputs['groups']:,}그룹(최대 {inputs['largest_group']:,}경기)을 분리했다.",
            f"경기 분할: {inputs['split_counts']}. 복원 입력 {counts['recovered_decisions']:,}개, "
            f"학습/선택 평가 가능 {counts['eligible_decisions']:,}개. 실제 고정 표본: {counts['selected_split']}.",
            f"선택 미공개 {counts['unknown_selection']:,}개와 단일 후보 {counts['single_candidate']:,}개는 학습/선택 평가 분모에서 분리했다. "
            f"지원하지 않는 메뉴/자동 실행 등의 별도 격리 {counts.get('quarantined_records',0):,}개를 보존했다.",'',
            '| 제외·격리 단위 | 사유 | 수 |','|---|---|---:|']
        for unit,reasons in counts.get('reasons_by_unit',{}).items():
            for reason,count in sorted(reasons.items()):lines.append(f'| {unit} | {reason} | {count:,} |')
        if estimation.get('available'):
            lines += ['',f"보완에 성공한 세트 {estimation.get('sets',0):,}개(복원 제외 이전)에서 미공개 보완 기술 "
                f"{estimation.get('inferred_moves',0):,}/{estimation.get('inferred_moves',0)+estimation.get('revealed_moves',0):,}, "
                f"도구·특성·Tera 보완 {estimation.get('inferred_core_fields',0):,}/{estimation.get('core_fields',0):,}이다. "
                'nature/EV/IV는 corpus에서 추정했다. 원래 세트 일치가 실제 숨은 세트의 동일성을 보장하지 않는다.']
        lines += ['', '상대는 결정 직전 공개 prefix만 사용한다. 자신의 원래 세트 복원에 사용한 이후 공개 자료, '
            '승패·이름·rating·seed·출처·정답은 모델 입력에 전달하지 않는다. '
            '최대8,192 상태 토큰 초과는 무절단 제외하며 미래 정보·중간 턴·분할/후보 검증 증거를 별도 보존했다.','']
    if 'selection' in evidence:
        selection=evidence['selection'];preflight=evidence['preflight']
        lines += ['## 첫 학습','',f"GPU 사전검사 {len(preflight['samples'])}개·optimizer0회. "
            f"사전 동결 업데이트 {preflight['planned_updates']:,}회, 선택 업데이트 {selection['selected_update']:,}회.",
            f"선택 checkpoint: `{selection['checkpoint']}`.",
            'Base BF16·LoRA/head/손실 FP32·BF16 forward의 같은 unmerged 경로를 사용했다. '
            '15분 재개 checkpoint에는 optimizer/scheduler/RNG/부분 경사/데이터 위치와 최초24시간 시계를 포함한다.',
            f"계획 학습 완료 여부: {selection.get('completed_planned_training')}; 중단 사유: {selection.get('stopped_reason')}.",'']
        if 'training' in evidence:
            training=evidence['training'];cursor=training['cursor']
            lines += [f"실제 업데이트 {cursor['updates']:,}회·학습 표본 처리 {cursor['examples_seen']:,}개, "
                f"사전검사부터 학습/validation 종료까지 {training['elapsed_seconds']/3600:.3f}시간. "
                f"학습 peak allocated {training['max_allocated_bytes']/2**30:.3f}GiB·"
                f"reserved {training['max_reserved_bytes']/2**30:.3f}GiB.",
                f"물리 GPU {evidence['resource']['physical_gpu']} ({evidence['resource']['name']}); "
                f"p95 사전검사 표본 처리시간 {preflight['p95_sample_seconds']:.3f}초.", '']
    if 'offline' in evidence:
        offline=evidence['offline']
        lines += ['## 잠긴 test 평가','',f"각 모델 {offline['observations_per_model']:,}개를 한 번 평가했다. "
            'NLL과 행동 일치율은 인간 선택 재현 지표다.','',
            '| 모델 | NLL | 행동 일치율 |','|---|---:|---:|']
        for model,label in [('initial','초기'),('selected','선택')]:
            m=offline['metrics'][model]['all'];lines.append(f"| {label} | {m['nll']:.6f} | {m['action_match_rate']:.2%} |")
        lines += ['',f"선택−초기 NLL {offline['nll_difference']:+.6f}, 행동 일치율 "
            f"{offline['action_match_rate_difference']*100:+.2f}%p. 결정 종류/실제 선택 종류/Tera 소모·선택별 분모와 지표는 "
            '[원문 평가](../evaluation/report.json)에 보존했다.','']
    if 'resume' in evidence:
        lines += ['실제 학습의 부분 경사·AdamW·scheduler·RNG·데이터 위치를 저장하고 새 PID로 '
            '재개한 뒤 다음 update의 연속성과 최초 시계·initial validation 불변을 확인했다. '
            '[실제 재개 검사](../execution/resume-completed.json)는 GPU 무중단 경로와의 bit-exact 비교가 아니다.','']
    elif 'resume_missing' in evidence:
        lines += ['실제 학습 중단/재개 검증은 수행하지 못했다. 원래 학습량 안에서 안전한 검사 구간을 '
                  '확인하지 못했으며 CPU 재개 검사와 구분한다. [미실시 사유](../execution/resume-not-performed.json).','']
    if 'battle' in evidence:
        from .reporting import report_markdown
        lines += [report_markdown(evidence['battle']).replace('# EX-071 첫 배틀 평가','## 고정40경기 평가')
                  .replace('(result.json)','(../battle/result.json)').replace('(manifest.json)','(../battle/manifest.json)')]
    else:
        lines += ['## 배틀 평가','', '아직 배틀 결과가 없다. 예정40경기를 실제 수행한 것으로 표시하지 않는다.','']
    missing=[name for name in ('prepared','audit','preflight','selection','offline','battle','parity','viewer','resume') if name not in evidence]
    complete=not missing and evidence['audit'].get('passed') and evidence['selection'].get('completed_planned_training')
    complete=bool(complete and evidence['battle'].get('all_slots_attempted') and not evidence['battle'].get('phase_error')
                  and evidence['viewer'].get('passed'))
    complete=bool(complete and evidence['resume'].get('passed'))
    lines += ['## 검증·한계·산출물','',f"실행 완료 기준 충족: {complete}. 누락 단계: {missing or '없음'}.",
        '작은 첫 배틀 평가이며 통계적 불확실성과 복원/세트 추정·제외 편향이 있다. '
        '오프라인 손실 감소만으로 배틀 개선을 주장하지 않는다. 설명 오류 검토는 기본 제외로 미평가다.','',
        '[배틀 뷰어](../../../../exports/battle_viewers/ex071/index.html) · '
        '[준비 manifest](../prepared/manifest.json) · [전체 출처/검증 목록](report.json)','']
    if 'viewer' in evidence:
        lines += ['폴더 이동 후 실제 Chromium 오프라인 열람과 저장 입력·확률·선택·전송 표시를 '
                  '[최종 뷰어 검사](viewer-check.json)에서 확인했다.','']
    target=directory/'final';target.mkdir(exist_ok=True)
    atomic(target/'report.md','\n'.join(lines).encode(),immutable=True)
    report=dict(at=time.time(),complete=complete,missing=missing,estimation=estimation,
        evidence={key:dict(path=str(directory/paths[key]),sha256=sha(directory/paths[key])) for key in evidence})
    atomic(target/'report.json',report,immutable=True)
    return report


def export(directory):
    from . import viewer
    directory=Path(directory).resolve()
    destination=c.ROOT/'exports/battle_viewers/ex071'
    result=viewer.export(directory/'battle',destination)
    receipt=directory/'final/viewer-check.json'
    subprocess.run([str(c.ROOT/'pokechamp/.venv/bin/python'),'-m',
        'integration.pokechamp.imitation.browser_check','--viewer',str(destination),
        '--receipt',str(receipt)],check=True,cwd=c.ROOT,
        env=dict(os.environ,CUDA_VISIBLE_DEVICES='',
                 PYTHONPATH=str(c.ROOT)+':/tmp/ep037/tools/lib/python3.11/site-packages'))
    if not read(receipt).get('passed'):
        raise ValueError('actual moved offline viewer qualification failed')
    # Only the mutable directory index changes; earlier experiment bundles stay sealed.
    index=destination.parent/'index.html'
    text=index.read_text()
    if 'href="ex071/index.html"' in text:
        raise ValueError('EX-071 is already registered in the viewer index')
    text=text.replace('</ul>', '<li><a href="ex071/index.html">EX-071 — Qwen 리플레이 모방 학습 첫 평가</a>'
        f" · 정상{result['completed']}/40 · 행동 선택 확률</li></ul>")
    atomic(index,text.encode())
    report=write_report(directory)
    return dict(viewer=result,report=report)
