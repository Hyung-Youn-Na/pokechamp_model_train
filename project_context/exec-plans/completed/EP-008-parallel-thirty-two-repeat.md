# EP-008 — 병렬 32판 추가 실행

- Status: Completed
- 날짜: 2026-09-07
- 근거: 사용자 추가 실행 지시, [D-016](../../decisions/D-016-model-concurrency.md)

## 범위와 조건

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

## 완료 기준

새 plan/source/execution seal 후 32 slot을 실행하고 모든 attempt를 보존한다.
실제 batch 시간, 완료·실패, HTTP 상한과 사용량, fallback을 보고한다.
Bundle/source 무결성, credential 비노출, owned process/worktree와 포트 정리를 확인한 뒤
EX-014, index와 STATUS를 갱신한다. 코드 변경은 범위에 포함하지 않는다.

## 완료 판정과 evidence

32 slot 실행과 사후 검증을 완료했다. 유효 완료 20, 실패 {'output_contract': 4, 'watchdog': 8},
실제 경과 37.10분이다. 모든 acceptance criterion을 해결했으며
실패를 정상 완료로 간주하지 않는다.

[EX-014 결과와 검증](../../experiments/EX-014-parallel-thirty-two-repeat.md)에 상세 분모·
요청 지표·원자료와 viewer를 기록했다. 별도 새 조건의 오류 수정 작업은 시작하지 않았다.
