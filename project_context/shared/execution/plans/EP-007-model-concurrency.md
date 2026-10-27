# EP-007 — 모델 동시성 측정과 병렬 배틀

- Status: Completed
- 생성일 / 완료일: 2026-09-07
- 근거: 사용자 실행 계획, [D-016](../decisions/D-016-model-concurrency.md)

## 범위와 완료 판정

Execution seal, 독립 서버·actor, 계정/모델 공통 permit broker, cancellation/cooldown,
calibration과 batch wall-time 보고를 구현했다. 기존 8/32/40 일정과 순차 호환성을 유지했다.
4시간 bounded 측정의 calibration → 동일 source 8판 비교 → 조건부 32판을 모두 실행했다.
실패를 분모에 남겼으며 이 plan의 완료는 32판 전부 정상 완료했다는 뜻이 아니다.

## 검증

- 전체 114 tests 및 Ruff E/F/I/W(line-length 100) 통과.
- 여러 process의 계정·모델 합계 상한, 대기 취소, broker/worker 종료, 429 공통 대기,
  fail-closed, permit 반환 및 orphan timeout을 검증했다.
- Hard-stop은 attempt의 응답 보존 대기가 끝나기 전에 신규 호출과 경기 배정을 차단한다.
  완료 slot 중복 방지, 미완료 attempt 보존, 시간 예산과 순차 seal 회귀를 검증했다.
- 실제 로컬 동시 2판의 서로 다른 seed 격리, 한 경기 취소 중 다른 경기 완료,
  같은 8100 포트의 2경기 연속 완료와 총 12개 actor bundle 보존을 확인했다.
- 실측 66 attempts(구 cohort 포함), 130 actor의 이름/seed와 260개 서버 roster 검사를 통과했다.
  Calibration 20 corpus/600 calls/30 levels 및 source/report seal과 C*=10 선택을 재검증했다.
- 최종 8/8/32판의 viewer 96개를 생성했다. Credential 비노출, pinned submodule cleanliness,
  owned server/actor/worktree 종료, 포트 정리와 broker 잔여 permit 0을 확인했다.

## 실행 이력과 결과

EX-004는 315.445초 동안 C=1–10을 각 3회 측정했다. HTTP 600회 모두 성공했고 엄격한
JSON 완결은 598회다. 전송 오류는 없으며 사전 선택 규칙으로 C*=10을 선택했다.

EX-006은 검토에서 발견한 hard-stop 전파 지연을 보완하기 위해 안전하게 중단했다.
EX-008은 병렬 8판을 완료했지만 EX-009는 포트 재사용 검사에서 중단됐다. TIME_WAIT와
살아 있는 listener를 구별하고 owned worker 종료를 기다리도록 보완했다. 두 구 cohort는
원형 보존하며 최종 비교에 합치지 않는다. EX-005/007/010은 NotRun이다.

수정된 동일 source의 EX-011/012는 병렬 12.28분 / 순차 41.63분, 각각 유효 완료 6/8이었다.
관측 속도비 3.3898배이며 병렬 429/timeout/integrity/격리 오류가 없어 운영 기준을 통과했다.
EX-013은 배틀 10 / 계정 요청 10 / 모델 요청 10으로 32 slot을 각 1회 처리했다.
실제 경과 37.22분, 유효 완료 20, 출력 오류 4, watchdog 8이며 보충 경기는 없다.
배틀 실제 최대 동시 수는 10, HTTP 겹침은 9다. HTTP 1622회는 모두 200이었다.

최초 실측 10:28:01 KST부터 종료까지 125.23분이다. 구현 보완 중에도 최초 시계를 유지했고
calibration을 다시 호출하지 않았다. 32판 예상 22.11분과 여유 포함 33.16분보다 느렸지만
전체 4시간에 들어갔다. C*=10은 해당 계정·모델·요청 조건과 탐색 범위에서만 채택한다.

## 한계

Watchdog 8건은 모두 b04 팀6/12이며 팀12 nickname 관련 parser 예외를 관찰했다.
같은 팀의 순차 대조가 없으므로 동시성의 인과 효과로 단정하지 않는다. 기존 minimax depth
오류도 유지했다. 소표본 운영 기준이며 정상 minimax 효능, 완료율 차이의 확증,
32판 전부 정상 완료하는 시간의 보장은 없다. 추가 작업은 자동으로 채택하지 않는다.

## Evidence

- [통합 실측 보고서](../../../../.pokechamp-data/concurrency-studies/glm-concurrency-v3/report.md)
  및 같은 디렉터리의 sealed summary.json, 분석 source analysis.py.
- [EX-004](../experiments/EX-004-model-concurrency-calibration.md),
  [EX-011](../experiments/EX-011-parallel-eight-final.md),
  [EX-012](../experiments/EX-012-sequential-eight-final.md),
  [EX-013](../experiments/EX-013-parallel-thirty-two-final.md).
- 로컬 격리: `.pokechamp-data/benchmarks/ep007-local-isolation-1788743982028972589/`.
- 로컬 취소: `.pokechamp-data/benchmarks/ep007-local-cancel-1788744249628296337/`.
- 로컬 포트 재사용: `.pokechamp-data/benchmarks/ep007-local-serial-1788746385365023389/`.
