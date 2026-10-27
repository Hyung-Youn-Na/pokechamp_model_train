# EP-203 — JevK5 전체 System One 학습

- 상태: Completed
- 생성일: 2026-10-21
- 승인: 현재 사용자 제공 계획 구현·검증·실행 지시 / D-180
- 조건 원문: [EX-116](../experiments/EX-116-jevk5-system1-full-training.md)
- 기준·실제 branch/checkout: research/model-training /workspace feda62f733c1b470364868262c789ec857ef67f5; 기존 dirty변경 보존.
- 환경: /ref/kev/.venv; 새 출력 EX116 및 project_context/exec-plans/evidence/ep203.
- 원자료: EP193/195~201 보존된 exports와 원manifest. 읽기전용.

## 범위·확인

새 integration/jevk5_system1_training 및 scripts/jevk5-system1-train, 별도 독립평가와 학습/평가/내보내기.
INDEX/CHARTER/매뉴얼/RD/공통·규칙학습계약·설계/정책학습목표, 관련 EP184/193/195~202 및 중단 EP108/119/125/126/127/134/140/163/183을 확인한다.
조건·예산·복구는 EX116 원문. 기존실험 재개0·기존결과 수정0·배틀/서빙 교체0. C047 해당없음.

## 완료 기준

- [x] 전수130149 자료검사 및 새validation1152/test2304 독립성·oracle 동결
- [x] 학습수학/메모리맵/자원/재개 CPU·GPU 사전검사
- [x] 4068update·원본/epoch validation·선택·test각1회
- [x] 진단·어댑터/체크포인트·재로딩·곡선/한국어보고·봉인·자원반환

## 진행

2026-10-21 승인 범위 등록. GPU1·2·3 유휴 확인; 실제모델적재/학습0.

## 중단·검증

INDEX 공통기준과 EX116을 따른다. 실패/부분완료를 연구완료로 표시하지 않는다.

- 전수130149 native token/후보/metadata 검사 통과. 49,437,429 입력토큰/epoch·최장6127, 모든 분야 양수가중치와 epoch당1회 확인.
- 별도 규칙2688·새384경기768문항의 엔진/독립라벨 대조 및 평가 분할을 동결했다. 평가 해석·사전교정은 [의미 검토](../../../exec-plans/evidence/ep203/evaluation-review.md)에 기록했다.
- CPU5검사 및 실제Gloo3rank 가중gradient/불균등microbatch/마지막69 검사, 선택·확률지표·bootstrap 검사를 통과했다. GPU 사전검사 진행 중이며 본학습0이다.

- v1 사전검사의8/4/2 판독 동등성 실패,1의 이어학습 수치 재현 실패를 보존했다. 같은 초기상태의 메모리/디스크 대조로 GPU 역전파 비결정성을 확인했고 결정적 연산 대조는 같은1e-7 기준을 통과했다. v2 재검사 조건·근거는 EX116에 기록했다. 본학습/모델 validation/test0.
- 학습 전 추가 검토에서 HP 평가768문항의 보기 패턴을 교정했다. 문항·분할·정답 의미·엔진근거는 그대로이며 v1 동결을 보존했다. 모델 결과를 이용한 문항/기준 선택은0이다.
- 첫8검사 종료 중 NVML 조회가 약2분 지연된 뒤 GPU0MiB/UUID/잠금 재확인으로 회복됐다. 초기 장치고장 단정은 [정정 기록](../../../exec-plans/evidence/ep203/device-delay-resolution.json)으로 바로잡았다. 장치 reset·외부process 종료0.

- v2 사전검사에서 microbatch1을 최초 통과값으로 동결했다. 단독판독/gradient차이0, 기반불변·LoRA변화·유한수치/자원검사와 복원 후 동일update의3rank차이0을 확인했다. 원본에서 본학습용 새LoRA를 초기화하고 step0 완전checkpoint·원본validation 단계에 진입했다.
- 최장입력 포함96문항54339토큰 업데이트 63.57초. 토큰 처리량 기반 학습 예상 29.9~48.2시간이며 평가/저장/적재는 별도다. [시간 추정](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116/time-estimate.json) · [현재 진행](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116/progress.json).
- 단일 파이프라인이 학습→선택/test→학습자료 진단→선택/최종 adapter 내보내기·별도재로딩·보고/봉인을 이어간다. 실패하면 자동재실행하지 않고 원인을 보존한다. 완료 receipt 이후에만 문서 상태를 갱신하며 아직 학습·평가 완료나 개선을 주장하지 않는다.

- 원본validation1152문항을 완료하고 본학습 epoch1의 11/4068update까지 정상 진행을 확인했다. 이후 진행의 원문은 EX116/progress.json이다. 모델 test는 아직 미실행이다.
- 잠긴test를 읽지 않는 합성 fixture에서 예측집계·bootstrap표기·역할순서진단·4068행곡선CSV·PNG·한국어보고서 출력을 확인했다. [검사](../../../exec-plans/evidence/ep203/report-smoke.json). 합성값은 실험결과에 사용하지 않는다.


## 실행 결과

3epoch/4068update/390447노출 및 원본·선택 test각2304문항1회를 완료했다. 선택 epoch 2. 7영역 macro정확도 차이는 +6.808%p, 95%구간은 [4.353, 9.263]%p이다. 해당 평가에서 개선 근거가 있다. 실제배틀·서버교체는 수행하지 않았다.

[최종 보고](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116/report.md) · [완료 검사](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116/completion.json) · [선택 adapter](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116/adapter-selected/) · [마지막 adapter](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-116/adapter-last/).
