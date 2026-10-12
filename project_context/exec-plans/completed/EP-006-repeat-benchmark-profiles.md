# EP-006 — 반복 benchmark 설정과 시간 재측정

- 상태 (Status): Completed
- 완료일: 2026-09-07
- 생성일: 2026-09-06
- 책임자: Codex
- 관련 contract: [C-010](../../CONTRACTS.md)
- 관련 decision: [D-015](../../decisions/D-015-repeat-benchmark-profiles.md)
- 관련 experiment: [EX-003](../../experiments/EX-003-core-smoke-timing.md)

## 목표와 범위

사용자의 구현 지시에 따라 40판 재현성을 보존하고 핵심 8판·32판 설정을 추가한다.
허용 범위는 parent integration, tests, 매뉴얼과 project_context다. 새 8판으로 128K 출력·
300초 요청 조건의 시간과 신뢰성을 측정하고 32판의 4시간 예산 적합성을 평가한다.
32판은 반복 규모 지원이며 이번 작업에서 자동 실행하지 않는다.

## 불변 조건

개발 팀만 사용한다. 공통 team/seed block, 팀·진영 교환, 사전 무작위 순서를 고정한다.
기존 source/실험은 변경하지 않는다. Pinned minimax 오류 수정과 L1-L5 효능 실험은 범위 밖이다.
실패는 패배가 아니며 유효 완료 수를 채우려고 추가 slot을 만들지 않는다.
기존 transient 1회 retry, auth/model/configuration/integrity hard stop과 source seal을 보존한다.

## 완료 기준

- [x] 40판의 기존 일정과 설정을 재현한다.
- [x] 8판·32판의 판수, 대진 균형, 교환, 개발/확증 분리와 일정 재현성을 검증한다.
- [x] 신뢰성·출력 오류·timeout·fallback·시간·호출량과 32판 시간 추정을 보고한다.
- [x] EX-003 8판 재측정 또는 실제 실행 차단 근거를 보존하고 현재 상태를 갱신한다.

## 검증과 진행

- 2026-09-06: authority와 빈 active registry 확인. 사용자 계획을 새 실행 단위로 등록했다.
- 검증: integration pytest, changed-file Ruff, 기존 sealed schedule 회귀, 새 계획 seal 및 실제 8판.

## 차단 및 중단 조건

Authority conflict, source drift, auth/model/configuration/integrity 오류이면 중단·보고한다.
4시간은 운영 예산이며 요청 정리/허용 retry를 포함한 통계적 상한이 아니다.

## 결과 및 증거

8/32판 설정과 보고서 확장 완료. EX-003 8판의 시간과 신뢰성을 측정했다.
전체 91 tests, Ruff E/F/I/W, Markdown link 검증 통과. 기존 40판 일정 fingerprint 및
EX-002 40 match/80 actor seal 불변. EX-003 8 match/16 actor source seal, 분석 source hash,
221개 artifact credential 검사와 16개 viewer 생성 통과.

EX-003은 44.5분/6 유효 완료/출력 오류 2건이다. 32판 추정 177.9분, 여유 50% 포함
266.9분으로 4시간 기준을 충족하지 않았다. Minimax fallback 74/88회(84.1%)를 포함하며
정상 minimax나 효능 근거가 아니다. 32판은 자동 실행하지 않았다. 상세 결과는 EX-003 참조.

- 구현 검증: 기존 EX-002 일정 fingerprint 동일, 초기 전체 87 tests 통과. 새 profile별
  CLI plan/analyze와 resume 검증을 추가했고 기존 test의 41-attempt 고정 기대값을
  실제 schedule 길이+허용 retry 1로 수정했다. Ruff E/F/I/W 통과.
- Preflight: server가 꺼진 첫 검사에서 loopback 항목만 실패했다. Parent server start 후
  `.artifacts/pokechamp/preflight/20260906T235812.315104Z/manifest.json`의 전 항목 통과,
  benchmark 소유권 확보를 위해 해당 server를 정상 종료했다.

- 최종 확인: 두 pinned submodule은 clean이며 port 8000 listener와 소유 server process가 없다.
