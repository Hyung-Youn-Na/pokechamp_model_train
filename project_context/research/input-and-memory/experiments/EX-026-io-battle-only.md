# EX-026 — 요약 없는 improved_io A/B 비교

- 상태: Blocked — Cloud 출력·의미 gate 실패, A/B 비교 미완료
- 등록일: 2026-09-09
- 관련: [D-030](../decisions/D-030-io-battle-only.md), [EP-018](../plans/EP-018-io-battle-only.md)
- 승인·처치·대진·평가·예산·복구 규칙: D-030 및 RESEARCH_DESIGN의 D-030 절.

## 사전 protocol

A upstream과 요약 없는 B 전체 구성을16대응/32판으로 탐색 비교한다. EX-016 개발 대진
Abyssal/OneStep×b01–b04×양쪽 진영을 사용한다. Smoke b04의8판과 과거 결과는 합치지 않는다.
주지표는 상대별 (승+0.5×무)/유효완료, 두 상대 동일 가중 평균, 완료 대응 B−A 및 누락이다.
예정/시도/유효완료/실패/무효/미실행/미확정/복구를 분리한다. 설명 오류는 별도 오류율이며
합법 완료 승패를 불리한 결과 때문에 제외하지 않는다. Prompt 단독 또는 L1-L5 효능 주장은 없다.

준비→fake32→행동90→smoke8→조건부compare32. Low/temperature0/seed100/출력131072/
timeout300/context기본/동시10/retry0. 최초Cloud4시간(신규3시간45분), 누적4000요청.
복구1차의 gate180/smoke16/compare64 포함 상한. D-029/C-018의 독립 재현·수정·검증,
영향 대응 양쪽 재수집·시계/호출수 보존을 적용하며 이전 실험은 복구하지 않는다.

## 결과와 중단

구현과 로컬 검증은 완료했다. 최종367회귀(171.63초), 운영15장면/독립 의미·입력 도달성/
사후3 및 fake32 유효32/32·실제 동시10·격리/정리를 통과했다. 별도31행동의 B 요약·통합·
archive는0이다. Source139개를 동결한
[최종 준비](../../../../.pokechamp-data/io-battle-only/ex026-preflight-e1/prepare/result.json)와
[fake32](../../../../.pokechamp-data/io-battle-only/ex026-preflight-e1/fake32/result.json)를 봉인했다.

최초 c0의1응답은 영문 숫자 범위 대시를 ASCII-only 검사로 거부한 평가 구현 오류였다.
D-029에 따라 원문/JSON·입력·수집을 보존하고 새 profile의 문장 부호 검사만 교정했다.
Rubric·prompt·전략·prior·계산기는 그대로다. 전체 회귀·새 fake32와 실제 입력 동등성을
검증하고 별도 e1에서 원본1개를 재평가·재사용했다. e1은 미제출89 중3개만 호출한 뒤
출력 계약 오류로 중단했다. 같은 시계/누적 원장을 사용했고 유료 재수집 차수는0이다.
원본과 교정 판정은 [복구 분석](../../../../.pokechamp-data/io-battle-only/ex026/analyses/english-typography-recovery.json)에 연결했다.

| 단계 | 예정 | 고유 시도/응답 | 출력 유효 | 출력 실패 | 미실행 | 미확정 |
|---|---:|---:|---:|---:|---:|---:|
| B 행동 gate | 90 | 4/4 | 3 | 1 | 86 | 0 |
| smoke8 | 8 | 0/0 | 0 | 0 | 8 | 0 |
| 본 비교 A | 16 | 0/0 | 0 | 0 | 16 | 0 |
| 본 비교 B | 16 | 0/0 | 0 | 0 | 16 | 0 |

실제 입력·처치·수집 무효0, 재수집0이다. c0의 원래 평가 실패1은 별도 보존하지만 e1의
고유 요청 수에 중복 합산하지 않는다. 본 비교 실패/무효/미확정은 각 조건0이며 유효 대응0/16,
누락16이다. 상대별 점수·동일 가중 평균·대응 차이·A fallback·배틀 설명 오류율은 미산출이다.

[수집된4응답 검토](../../../../.pokechamp-data/io-battle-only/ex026/gate-review-e1.json)에서:

- IO-C01: 원래1응답의 모델링 조건부 피해/KO·순서와 합법 출력은 교정 검사에서 통과했다.
- IO-C02: 현행 Air Balloon, 대표 시나리오 피해 범위와 전략 설명은 근거가 있다.
  다른 prior 조합을 모두 열거하거나 최적 행동을 맞히도록 요구하지 않았다.
- IO-C03: 현재5턴에3턴의 Earthquake 면역을 “지난 턴”으로 설명한 시점 오류다.
- IO-C04: 설명과 JSON을 같은 줄에 출력했다. 검사기의 `missing rationale` 메시지는
  설명 자체가 없다는 뜻으로 해석하지 않는다. 실제 위반은 final-line JSON 분리다.
  별도로 Poison Heal 회복을 누락하고 두 번 명중 KO를 단정했다. 입력의 h0/HP219에서
  최소 피해124 두 번과 사이 회복44를 적용하면15HP가 남는다. 혼란 자해는 확정이 아니다.

의미 오류 응답2/4, 출력 오류1/4이며 중복을 합산한 실패율로 제시하지 않는다.
[독립 계산·시점 근거](../../../../.pokechamp-data/io-battle-only/ex026/model-error-evidence.json)에
원문과 입력/계산을 연결했다. 모델 오류를 도구 결함으로 재분류하거나 재수집하지 않았다.

## 자원·해석·정리

총4호출/응답, HTTP200 4건, provider 실패/재시도/미확정0, 입력193,606·출력920 tokens다.
수집 wall time은 c0 6.97초 + e1 14.52초, HTTP 순차 p50 4,748ms/p95 6,426.2ms다.
실제 HTTP 겹침은1이며 병렬45호출은 미실행이므로 겹침10/p95비율은 검증되지 않았다.
요약/통합0, 실제 배틀 batch0초다. 본 비교 시간 적합성은 smoke 미실행으로 평가하지 않았다.

최초 요청 후24.03분에 [정리 검증](../../../../.pokechamp-data/io-battle-only/ex026/closure-verification.json)을
완료했다. 과거41,474파일·기존4개 Blocked plan 보존,128 actor 봉인·139 source 일치·
134개 sidecar·2965개 새 파일 credential 검사와 pinned submodule/소유 프로세스/포트 정리를 통과했다.
후속 배틀은 gate 실패로 차단됐으며 남은 시간/호출 예산은 재개 허가가 아니다.

[보고서](../../../../.pokechamp-data/io-battle-only/ex026/final-report/report.md)와
[기계 판독 집계](../../../../.pokechamp-data/io-battle-only/ex026/final-report/report.json)에 smoke와
본 비교, 과거 자료를 분리했다. 구현·로컬 검증·수집분 검토·중단 보고·정리 완료이며,
사전 Cloud90·smoke8·본32/16대응은 미완료다. 효과 결론은 없고 EP-018은 Blocked로 유지한다.
요약·통합 진단은 이번 비교에서 분리했으며 기존 Blocked·halt·시계를 변경하지 않았다.
