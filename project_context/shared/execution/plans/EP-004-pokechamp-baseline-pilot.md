# EP-004 — PokéChamp 기준선 도구와 pilot

- 상태 (Status): Completed
- 완료일: 2026-09-07 (Asia/Seoul)
- 생성일: 2026-09-06
- 책임자: repository agent
- 관련 결정: [D-012](../decisions/D-012-adopt-pokechamp-baseline-pilot.md)
- 관련 실험: [EX-001](../experiments/EX-001-pokechamp-baseline-pilot.md) (Stopped),
  [EX-002](../experiments/EX-002-pokechamp-baseline-pilot.md) (Completed)

## 목표와 범위

Benchmark plan/run/analyze, 역할별 minimax Cloud 검증, 경기별 격리와 evidence를 구현하고
40개 pilot slot을 처리해 본 실험 규모 결정에 필요한 보고서를 만든다. Parent integration,
script와 project_context만 변경한다. 외부 submodule, 기존 artifact는 변경하지 않는다.

## 완료 기준

- [x] 재현 가능한 설정·팀 분할·40-slot schedule 및 source snapshot
- [x] 역할별 JSON 검증, 양측 trace, process/RNG 격리, 중단·재시도·resume
- [x] 분모·실패·비용·시간 분석과 meaningful integration/regression tests
- [x] Pilot 모든 slot 처리 또는 사전 중단 기준에 따른 정직한 Stopped 기록
- [x] 원자료 seal 검증, 결과 및 후속 규모 추정 보고서

## 중단 규칙

Source/configuration drift, 잘못된 evidence, auth/model failure는 batch를 중단한다.
Provider 일시 장애만 slot당 한 번 재시도한다. 상위 authority 충돌은 기록·보고한다.
본 실험 규모는 pilot 이후 결정하며 자동 실행하지 않는다.

## 진행

- 2026-09-06 — 사용자 실행 지시로 시작. 팀 13개 모두 pinned gen9ou validator 통과.

## 검증과 결과

66 integration tests와 changed-file Ruff 통과. 규칙 봇 독립 재실행의 39턴/양측 wire action
일치. Cloud minimax 29턴, 148/148 valid calls. 이후 EX-001은 Stopped, EX-002는 Completed다.

- Pilot 중간 관찰: `minimax-one_step-b01-s0-a1`에서 opponent_action의 교체 후보 검증 실패가
  발생했다. 두 actor의 source는 정상 seal됐으며, 사전 규칙대로 output_contract로 보존하고
  패배 변환/재시도 없이 다음 slot으로 진행했다. 최종 집계 전의 운영 관찰이다.

- EX-001은 7개 slot 후 source guard에서 중단. Peer cancellation의 후속 호출 방지와
  mixed failure retry 우선순위를 보완했다. 수정 전후 source를 분리해 EX-002로 새 pilot을 수행한다.

- Peer cancellation 실제 양측 actor + local Showdown fixture(Cloud network 0)에서 양측
  source complete/seal, actor당 call 1개, 취소 후 choose action 0개를 확인했다.
- 전체 66 tests 통과. EX-002는 수정 후 code snapshot만 사용한다.

- EX-002/baseline-pilot-v3의 새 source/schedule seal을 확인하고 실행을 시작했다.

## 최종 보고 마무리

실행 중 source snapshot을 유지하고 EX-002의 모든 slot을 처리한 뒤 분석·분류 보완을 적용했다.
Actor 자체 오류와 peer 중단을 구별하고, pinned AST의 outer search handler와 실제 choose
전송으로 action fallback을 계산했다. 기타 예외 handler 방문은 별도 진단이다. 파생 보고서는
분석 source 사본/hash를 포함하며 원 actor/match source와 eligibility를 변경하지 않았다.

### EX-002 실행 중 확인한 해석 제한

첫 정상 완료 minimax 경기(`minimax-one_step-b01-s1-a1`)에서 outer search exception 39회와
`name 'depth' is not defined` 로그 39회를 확인했다. Pinned upstream의 시각화/성능 로그 경로에
미정의 변수가 있어 damage-calculator action fallback을 반환한다. 실행 중 고정 구현을
수정하지 않는다. 이 결과를 정상 minimax 탐색의 성능으로 해석하지 않고, 해당 pinned 구현의
fallback을 포함한 관찰 기준선으로 보고한다. 후속 알고리즘 수정은 별도 조건과 실행 identity가 필요하다.

`minimax-one_step-b01-s0-a1`은 match summary가 algorithm이지만 actor의 자체 종료 이유는
output_contract다. Parent가 worker exit를 먼저 관찰하면 일반 분류를 기록할 수 있다. 원
summary는 보존하고 actor 원인별 표를 별도로 제공한다. 재시도 가능 오류가 이 일반 분류에
가려졌는지도 최종 감사한다.

## 최종 결과와 종결 검증

- EX-002: 40 slot/40 attempts/31 유효 완료, output_contract 8건/watchdog 1건. 재시도 없음.
  규칙 봇 자체 오류와 transient/hard-stop actor 오류는 0건이다. EX-001의 7 slot은 별도 보존한다.
- IO/minimax 핵심 점수는 각각 1.0/0.0이나, 소표본과 실패 제외·minimax 오류 fallback 때문에
  우월성을 주장하지 않는다. 상세 분모·비용·한계는 EX-002와 연결된 보고서에 보존했다.
- Minimax 유효 완료 choose 331회 중 outer search 예외 fallback 267회(80.7%). Upstream
  depth 미정의 오류를 명시하고 원 pinned source를 수정하지 않았다.
- 본 실험 자원 시나리오를 보고했으며 N/자원 한도를 확정하거나 본 실험을 실행하지 않았다.
- 실행 후 worker exit 분류 경쟁 조건을 수정하고 auth/timeout/output/watchdog 회귀 fixture,
  자체/peer 분모와 대진별 자원 환산 테스트를 추가했다. 전체 72 tests와 changed-file Ruff 통과.
- 40 match/80 actor source seal과 분석 source hash 검증, 80개 viewer/replay 생성 완료.
  Artifact 1133개 credential 검사 통과. 외부 submodule clean/pinned, port 8000 종료 확인.
- 완료 plan 이동 후 project_context의 local Markdown link 검사와 Git diff whitespace 검사 통과.
- 남은 구현·실험 작업 없음. 본 실험 또는 알고리즘 수정은 새로운 승인 조건과 bounded plan이 필요하다.
