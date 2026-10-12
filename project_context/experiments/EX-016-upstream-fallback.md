# EX-016 — 원본 fallback 병렬32판

- Status: Completed
- 실험 ID: `glm-upstream-fallback32-v1`
- 근거: D-018 / EP-010, 사용자 명시적 실행 승인

## 사전 등록

질문: 기존 Cloud/환경 조건 위에서 원본 행동 생성·출력 fallback을 사용한32슬롯의 완료율,
승패,비용,실제 fallback 행동 빈도는 어떠한가? L1-L5 효능/정상 minimax/최대 처리량 검증이 아니다.
Population은 core-repeat32 고정 팀/seed/진영/대진이다. action_policy=upstream,10/10,
retry_transient=0, watchdog1200초. Cloud 시작부터4시간/신규3시간45분 중지다.
출력 오류는 원본 재시도/fallback으로 회복하며 정상 종료는 유효하다. Provider 장애는 중단한다.
전체 시도와 유효 완료 각각 IO/minimax 역할별 파싱/연결 오류, 추가 호출/회복 IO,
단계별 fallback, 실제 fallback 전송 판단/전체 choose 전송 판단, fallback 경기/해당 경기 분모를
보고한다. 미실행/실패 슬롯도 남기며 보충하지 않는다. 과거 evidence와 합치지 않는다.

## 증거

예정: `.pokechamp-data/benchmarks/glm-upstream-fallback32-v1/`.

- 실행 봉인: source 41개, core-repeat32 일정/팀이 EX-014와 일치.
  최종142 tests/Ruff 통과. Cloud 시작 epoch 1788760375.64703,
  신규 중지 1788773875.64703, 정리 기한 1788774775.64703.

## 완료 결과

예정32 / 처리32 / 유효 완료32 / 실패0 / 미실행0이다.
실제 batch 1256.796초(20.95분). 실패 분류: {}.
Fallback 정상 종료를 유효 결과에 포함했으며 이전 실험과 분모를 합치지 않았다.

| 방법 | 실제 fallback 판단/전송 판단 | fallback 경기/경기 | 추가 호출 | 회복 IO |
|---|---|---|---|---|
| io | 0/376 (0.0%) | 0/16 | 0 | 0 |
| minimax | 293/508 (57.7%) | 16/16 | 6 | 2 |

전체 시도 및 유효 완료의 역할별 출력 오류·IO·단계별 집계는 `report.json/upstream_fallback`에 있다.
기존 `minimax_fallback` 항목은 handler 진입 진단이며 실제 전송 비율은 새 `upstream_fallback`을 사용한다.

| 대진 | 승 | 무 | 패 | 유효 분모 |
|---|---|---|---|---|
| io vs abyssal | 4 | 0 | 4 | 8 |
| io vs one_step | 8 | 0 | 0 | 8 |
| minimax vs abyssal | 2 | 0 | 6 | 8 |
| minimax vs one_step | 4 | 0 | 4 | 8 |

전체 보고 사용량: {"calls": 1757, "prompt_tokens": 3269596, "completion_tokens": 253607}. 미보고 사용량은 비용0으로 가정하지 않는다.
요청 겹침/지연: {"error_counts": {}, "http_p50_ms": 2588.0, "http_p95_ms": 5791.4, "http_status_counts": {"200": 1757}, "maximum_account_http_overlap": 10, "maximum_model_http_overlap": {"glm-5.3-flash": 10}, "note": "Client HTTP overlap; provider internal queue/execution timing is unknown.", "observed_http_calls": 1757, "permit_wait_p50_ms": 1.0, "permit_wait_p95_ms": 1.0}.

최종142 tests/Ruff, 고정 원본 동등성·RNG/provider/집계 검증과 fake provider 로컬2/2가 통과했다.
41개 source archive, 32 attempt seals, 64 actor seals/viewer,
950개 artifact credential 검사, 이전 EX-014 32 attempt/64 actor seals,
pinned submodule·소유 프로세스/임시 worktree·8000/8100–8109 포트 정리, 잔여 permit0과4시간 제한을 검증했다.

환경 호환 수정과 기존 Cloud 설정 위에서 원본 행동 생성 방식을 측정했다. 기존 depth 예외와
상대 fallback의 자기 팀 참조는 보존했다. 오류 없는 minimax 성능이나 최대 처리량 검증이 아니다.

[상세 보고서](../../.pokechamp-data/benchmarks/glm-upstream-fallback32-v1/report.md),
[JSON](../../.pokechamp-data/benchmarks/glm-upstream-fallback32-v1/report.json),
[무결성·정리](../../.pokechamp-data/benchmarks/glm-upstream-fallback32-v1/hygiene.json),
[64 actor viewer](../../.pokechamp-data/experiments/glm-upstream-fallback32-v1/index.html).
