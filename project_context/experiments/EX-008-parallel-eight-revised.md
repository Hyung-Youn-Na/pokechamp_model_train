# EX-008 — 수정된 coordinator의 병렬 8판

- Status: Completed
- 날짜: 2026-09-07
- Experiment ID: `glm-concurrency-v2-parallel8`
- 근거: [D-016](../decisions/D-016-model-concurrency.md),
  [EP-007](../exec-plans/completed/EP-007-model-concurrency.md)

## 사전 조건

EX-006 중단 후, 치명적 actor 취소 신호를 attempt 응답 보존 완료 전에 coordinator가
감지하도록 보완했다. 알고리즘·모델·요청 경로는 바꾸지 않았다. EX-004의 C*=10과 원래
10:28:01 시작/14:13:01 신규 작업 중지/14:28:01 정리 기한을 명시적으로 유지한다.

기존 core-smoke의 4대진×공통 1 block×진영 교환 2회, 예정 8 slot이다.
배틀 8, 계정 요청 10, glm-5.3-flash 요청 10이다. EX-009와 source·일정·팀·모델 조건은
동일하며 병렬→순차 순서다. Minimax depth 오류, K=2, temperature, 출력 128K,
provider 기본 context, 요청 300초 및 경기 watchdog 1200초를 유지한다.

## 결과

예정 8/처리 8/attempt 8/유효 완료 6(75%)이다. 출력 검증 오류 2건, retry 0건이다.
실패는 패배로 계산하지 않았고 추가 slot을 실행하지 않았다.

- Batch 실제 경과: 743.562초(12.39분).
- 겹치는 attempt 자원 시간 합: 2919.680초. Batch 시간으로 사용하지 않는다.
- HTTP 879회 모두 200, 429/timeout 0건. 실제 최대 HTTP 겹침 8, 배틀 8.
- HTTP p50/p95: 1281/2696.4ms. 로컬 permit 대기 p50/p95: 1/1ms.
- 보고된 입력/출력 token: 1,731,562 / 53,119.

IO 4판은 모두 유효 완료했고 minimax는 2판 완료, 2판 출력 검증 오류다.
완료 조건부 성적과 minimax fallback은 아래 보고서에 별도로 기록한다.
순차 EX-009가 끝나기 전에는 비교와 32판 진행을 판정하지 않는다.
소표본 운영 결과이며 정상 minimax 성능이나 효능의 확증이 아니다.

## 검증과 evidence

8 attempt/16 actor bundle 무결성, current source seal 및 pinned submodule cleanliness를
확인했다. 원자료와 처음 중단한 EX-006을 합치지 않는다.

[보고서](../../.pokechamp-data/benchmarks/glm-concurrency-v2-parallel8/report.md),
[기계 판독 결과](../../.pokechamp-data/benchmarks/glm-concurrency-v2-parallel8/report.json).
Actor 원자료는 `.pokechamp-data/experiments/glm-concurrency-v2-parallel8/battles/`에 있다.

EX-009가 서버 포트 재사용 경계에서 중단되어 이 cohort의 순차 비교는 완결되지 않았다.
새 source의 EX-011/012와 합치지 않으며, 이 결과만으로 32판 진행을 승인하지 않는다.
