# EP-120 — EX-073 수치 사전검사 복구 도구

- 상태: Completed
- 생성일: 2026-10-03
- 책임자: Codex
- 승인 근거: 사용자 계획의 공유 결함 C-018 복구 지시, D-116/EP-119
- 관련: [EX-073](../experiments/EX-073-abyssal-rl.md), [C-018](../../../CONTRACTS.md#c-018-recovery)

## 목표·범위·불변 조건

첫 GPU 사전검사의 경사 불일치를 원본 보존·독립 재현으로 조사하고, 동일 조건과 최초 시계에서
검증된 초기 checkpoint만 복원하는 별도 source receipt 경로를 구현·검증한다.
변경 범위는 abyssal_rl의 backend 설정·source/CPU/checkpoint 복구 검증·최종 provenance와
관련 검사다. 기존 manifest/source/CPU receipt/실패/clock/checkpoint는 덮어쓰지 않는다.
새 복구 receipt는 원본 hash, 허용 변경 파일, 독립 증거, 새 source·CPU receipt를 연결한다.
EX-073의 입력·모델·정밀도·optimizer·배치·허용오차·실험 조건은 변경하지 않는다.
경기·update는 아직0이며 재수집0, 최초24시간·누적96GPU시간은 진단을 포함한다.
독립 진단은 distributed 담당, 복구 구현·검사는 runtime 담당, 등록·통합은 주 에이전트가 맡는다.

## 완료 기준·검증

- [x] 원본 GPU 실패·source·receipt·checkpoint를 별도 버전에 보존
- [x] 같은 입력/가중치/RNG·단일 GPU 반복만으로 원 경사 불일치 재현
- [x] strict deterministic 및 cuBLAS workspace 설정에서 출력 동일·반복 경사 일치 확인
- [x] 변경 없는 원 preflight의 독립4GPU gradient/update 및 원상 복구 통과
- [x] 원본 불변·허용 파일·CPU/proof/clock/data·checkpoint 위조 거부 회귀 검사
- [x] source에 연결한 새 CPU receipt·복구 receipt 생성 및 실제 재개 gate 통과

## 진행·증거

첫 preflight는 경사 허용오차 실패로 전체 worker가 중지됐으며 배틀·update0이다.
동일 GPU에서 NCCL 없이 반복한 경사350텐서가 불일치했다. 결정적 연산 설정에서는 같은
초기 fingerprint·prediction digest를 유지하며 모든 경사가 bitwise 일치했다.
원 증거: `.pokechamp-data/experiments/ex073-abyssal-rl/versions/gpu-preflight-v1/`.
진단: 같은 실험의 `diagnostics/gradient-reproduction-*`, `deterministic-workspace-*`.
4GPU 독립 gate 진행 중이며 통과 전 production source 교정·재개하지 않는다.

## 중단·완료 경계

[INDEX](../../../INDEX.md#workflow), RD11.1/C-018과 EX-073 원 동결 조건을 적용한다.
필수 gate를 조건 완화 없이 충족하지 못하면 의존 실험은 중단 보존한다. 이 도구의 검증 완료는
EX-073 실험 완료나 성능 목표 달성을 뜻하지 않는다. 배틀 뷰어는 상위 EP-119의 범위다.

- 독립4GPU 원 gate·원상 복구 통과 후에만 backend 설정과 복구 검증 경로 교정에 진입했다.

- 독립 검토에서 개별 rank 보고서의 원 허용오차/backend 직접 검증을 보강했다.
  새 source에 연결된 CPU132검사(학습/실행/복구74·뷰어9·native49)와 Chromium 검사를
  통과했다. receipt는 `recoveries/deterministic-v2/verification/cpu.json`이며 원 CPU 증거는 보존했다.

## 결과

원본을 보존한 복구 receipt 검증·재개와 production 수치 gate를 완료했다. 원 허용오차에서
출력 차이0·경사 최대7.450580596923828e-9·update 최대1.30385160446167e-8이며
가중치/RNG 복원 후 baseline_dev로 진입했다. 최초 시계·예산·연구 조건은 유지했다.
[복구 receipt](../../../../.pokechamp-data/experiments/ex073-abyssal-rl/recovery.json),
[production 검사](../../../../.pokechamp-data/experiments/ex073-abyssal-rl/verification/preflight.json).
후속 실험·실제 SIGTERM 검증·평가 완료는 EP-119에서 계속 관리한다.
