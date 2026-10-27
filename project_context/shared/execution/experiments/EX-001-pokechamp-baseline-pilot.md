# EX-001 — PokéChamp 기준선 pilot

- 상태 (Status): Stopped
- 생성일: 2026-09-06
- 관련 plan: [EP-004](../plans/EP-004-pokechamp-baseline-pilot.md)
- 관련 decision: [D-012](../decisions/D-012-adopt-pokechamp-baseline-pilot.md)

## 목적

기존 5개 방법의 실행 신뢰성, 호출량, 토큰, 소요 시간을 측정하고 본 실험의 N을 결정한다.
Pilot 승패는 기술적·탐색적 관찰이며 superiority claim이 아니다.

## 사전 protocol

Gen9 OU pinned 팀 13개 중 개발용 8개, 확증용 5개. Seed 20260906.
10개 대진마다 공통 2개 team/seed 블록, 블록당 팀/진영 교환 2경기: 40개 예정 slot.
모델 glm-5.3-flash, low, context 8192, output 512. Showdown timer off.
Source snapshot, 정확한 팀/seed/order는 실행 전 sealed benchmark plan에 기록한다.
LLM/player와 server는 경기별 새 process. Actor별 Python/NumPy RNG는 독립이다.
Provider request 120초, 경기 watchdog 1200초. Watchdog 중단은 패배가 아니다.
일시 provider transport/rate-limit/timeout은 한 번만 재시도; 모든 attempt 보존.
설정·auth/model·evidence 오류는 즉시 batch 중단. 출력/알고리즘 오류는 재시도하지 않는다.

## 분모 및 해석

배정 slot, attempt, 유효 완료, 실패를 각각 센다. 유효 완료만 승/무/패 분모에 들어간다.
IO/minimax의 핵심 점수는 Abyssal·OneStep 각각의 (W+0.5D)/N을 동일 가중 평균한다.
둘 중 한 대진이 미완료이면 종합 점수는 null이다. Pilot CI나 우열 결론을 내리지 않는다.
토큰/시간은 실패 attempt도 포함해 보고하며 actual billing 근거 없이 금액을 만들지 않는다.

## 격리

Pilot은 개발 팀만 사용한다. 이후 main seed와 분리한다. 확증 trace의 개발·메모리 유입을 금지한다.
기존 smoke/demo는 포함하지 않는다. 과거 bundle을 덮어쓰거나 efficacy로 재분류하지 않는다.

## 결과 및 evidence

Stopped. Evidence: POKECHAMP_DATA_ROOT/benchmarks/baseline-pilot-v2/ 및
experiments/baseline-pilot-v2/battles/ 의 actor별 bundle.

## 실행 전 검토

초기 `baseline-pilot-v1/plan.json`은 실행하지 않았다. Environment metadata에 qualification용
team/seed 기본값이 중첩되어 benchmark 설정과 혼동될 수 있어 원 seal을 보존하고 v2 identity로
교체한다. v1에는 경기 attempt가 없으며 결과 분모에 포함하지 않는다.

## 선행 검증

- Integration test 62개 통과; 변경 Python 파일 Ruff E/F/I/W (100 columns) 통과.
- All-scope preflight 통과; submodule 두 개 clean; project_context broken link 0.
- 독립 server/process 규칙 봇 재실행 2회: 모두 39턴, 양측 wire action sequence 동일.
- 별도 Cloud qualification: minimax 대 Random 29턴 종료, 148/148 valid calls, 입력 303031 /
  출력 8518 tokens, orchestration 포함 497.2초. 이 qualification 승패는 pilot 분모에 미포함.
- 실행 identity: baseline-pilot-v2. Source snapshot과 schedule seal 후 2026-09-06 실행 시작.

- Pilot 중간 관찰: `minimax-one_step-b01-s0-a1`에서 opponent_action의 교체 후보 검증 실패가
  발생했다. 두 actor의 source는 정상 seal됐으며, 사전 규칙대로 output_contract로 보존하고
  패배 변환/재시도 없이 다음 slot으로 진행했다. 최종 집계 전의 운영 관찰이다.

## 중단 결과

2026-09-06, baseline-pilot-v2는 7/40 slot 처리 후 source drift guard에서 중단됐다.
6개 유효 완료, 1개 output_contract, 7 attempts. 진행 중 경기는 원 코드로 완료·봉인했다.
Peer failure/watchdog에서 pending 응답을 기다리는 동안 다음 호출이 시작될 수 있는 경로를
code review에서 발견해 수정했기 때문이다. 실제 출력 오류 1건을 숨기기 위한 변경이 아니며
model/prompt/search 조건은 변경하지 않았다. 중단 전에 처리한 원자료와 report.json/report.md를
보존한다. 이 cohort를 수정 후 pilot과 합쳐 기준선으로 발표하지 않는다.

후속 EX-002가 수정된 source snapshot으로 동일한 사전 pilot schedule을 새로 수행한다.
EX-001의 토큰/시간은 개발·검증 비용이며 EX-002의 경기 분모에 포함하지 않는다.
