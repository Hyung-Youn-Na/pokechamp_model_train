# EX-014 — 동일 조건의 병렬 32판 반복

- Status: Completed
- 날짜: 2026-09-07
- 근거: [EP-008](../plans/EP-008-parallel-thirty-two-repeat.md), 사용자 추가 실행 지시

## 사전 조건과 해석

사용자 추가 지시 “이어서 병렬로 32판 진행해주세요”에 따른 독립 반복 실행이다.
Experiment ID는 `glm-parallel32-repeat-v1`이며 EX-013과 별도 분모로 보존한다.
현재 source seal이 EX-013과 일치하고 pinned submodule과 포트 8100–8109를 확인했다.
동일 계정·모델·요청 조건에서 EX-004의 C*=10 evidence를 명시적으로 사용한다.
배틀10/계정요청10/모델요청10, core-repeat 32 slot, seed 20260906과 기존 팀을 유지한다.
추가 calibration이나 순차 8판 비교는 하지 않는다. 팀 nickname 및 minimax depth 오류,
모델·출력/context·요청300초·watchdog1200초는 변경하지 않는다.

이번 추가 실행의 독립 예산은 4시간이며 시작 기준 2026-09-07T13:03:34.971653+09:00,
신규 경기/요청 중지 epoch 1788767314.9716525, 정리 기한 epoch 1788768214.9716525이다.
기존 study의 시계나 결과는 변경하지 않는다. 직전 32판 관측 37.22분의 1.5배인
55.83분은 이번 예산에 들어간다. 같은 일정의 반복 관측이며 독립 팀 표본으로 간주하지 않는다.
실패·미실행을 분모에 남기고 완료 수를 채우는 추가 slot은 없다.
기존 transient 오류의 동일 slot 1회 retry, hard-stop과 응답 보존 규칙을 유지한다.

## 완료 결과

예정 32 / 처리 32 / attempt 32 / 유효 완료 20 / 미실행 0이다.
실제 batch 경과는 2226.253초(37.10분)이며 이번 4시간 예산에 들어갔다.
실패는 {"output_contract": 4, "watchdog": 8}이며 실패를 패배로 계산하지 않는다.
HTTP 1709회, 상태 분포 {'200': 1709}, 실제 최대 요청 겹침은
9개다. 배틀 최대 동시 수는 10개다.
로컬 permit 대기 p50/p95는 1.0/1.0ms,
HTTP 지연 p50/p95는 1356.0/2803.399999999999ms다.

동일 source·일정·팀·모델·calibration evidence를 명시적으로 재사용한 별도 반복이다.
EX-013과 합쳐 승패를 계산하지 않았다. Watchdog 경기의 b04 팀6/12 nickname 관련 parser
예외가 재발했으며 모델·팀·알고리즘·watchdog는 바꾸지 않았다. 같은 팀·seed 반복이므로
독립 팀 표본으로 간주하지 않는다. 정상 minimax 효능과 32판 모두 정상 완료하는 시간은 미검증이다.

32 attempt와 64 actor bundle seal, 이름·팀·seed 격리 검사, credential 비노출,
pinned submodule cleanliness와 owned server/worktree/포트 정리를 통과했다.
Broker 종료 시 잔여 permit은 0이다. 코드 변경이 없어 기존 114 tests를 재실행하지 않았으며,
이번 실행의 실제 source·bundle·요청 상한과 프로세스 정리를 검증했다.

[상세 보고서](../../../../.pokechamp-data/benchmarks/glm-parallel32-repeat-v1/report.md),
[기계 판독 결과](../../../../.pokechamp-data/benchmarks/glm-parallel32-repeat-v1/report.json),
[64개 actor viewer](../../../../.pokechamp-data/experiments/glm-parallel32-repeat-v1/index.html).
