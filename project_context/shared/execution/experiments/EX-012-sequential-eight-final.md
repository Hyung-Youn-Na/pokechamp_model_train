# EX-012 — 포트 정리를 보완한 순차 8판

- Status: Completed
- 날짜: 2026-09-07
- Experiment ID: `glm-concurrency-v3-sequential8`
- Study ID: `glm-concurrency-v3`
- 근거: [D-016](../decisions/D-016-model-concurrency.md),
  [EP-007](../plans/EP-007-model-concurrency.md),
  [EX-004 calibration](EX-004-model-concurrency-calibration.md)

## 사전 조건

EX-009의 포트 재사용 사전 검사 실패 후, SO_REUSEADDR로 TIME_WAIT와 살아 있는 listener를
구별하고 종료한 서버의 worker listener 정리를 기다리도록 보완했다. 비교에서 여유 디스크
공간 관측값만 제외하고 source·일정·팀·모델·toolchain 조건의 일치는 계속 검사한다.
EX-011/012는 같은 수정 source로 병렬→순차 순서에 각각 새 8판을 실행한다.
과거 중단 cohort의 결과를 합치거나 완료 수를 채우는 경기로 취급하지 않는다.

C*=10. 병렬 조건은 배틀8/계정요청10/모델요청10, 순차 조건은1/1/1이다.
모델 glm-5.3-flash, low effort, 출력131072, provider 기본 context, 원본 temperature와
seed, 요청300초, 경기watchdog1200초, minimax depth 오류와 알고리즘을 유지한다.
EX-004의 요청 경로 hash와 조건을 검사해 명시적으로 이어 쓰며 추가 calibration은 없다.
최초 실측 10:28:01 KST / 신규 작업 중지14:13:01 / 정리 기한14:28:01을 유지한다.

## 분모·진행·해석 규칙

8판은 기존 core-smoke의4대진×공통1block×교환2판, 32판은 공통4blocks다.
예정/처리/attempt/유효완료/미실행을 구별하고 실패를 패배로 계산하지 않는다.
기존 transient 동일 slot1회retry만 허용하며 추가 slot은 없다.

병렬429/timeout/integrity/격리문제 없음, 유효완료>=순차, batch경과<순차를 만족하고,
대진별 관측 시간을 32판 일정에 배정한 추정×1.5가 남은 시간에 들어갈 때만
배틀10/모델요청10의32판을 시작한다. 배틀9–10 동시성의 실제 검증은 이 단계가 처음이다.
소표본 운영 기준이며 효능·완료율 차이·정상 minimax의 확증이 아니다.

## 완료 결과와 비교

예정 8 / 처리 8 / attempt 8 / 유효 완료 6(75%). 출력 검증 오류 2건이며 재시도는 없다.
Batch 실제 경과는 2497.582초(41.63분), HTTP 795회는 모두 200이었다. 실제 최대 HTTP
겹침은 1이다. 같은 포트의 연속 경기 전환에서 configuration 오류는 재발하지 않았다.

EX-011 병렬 12.28분과 비교한 관측 batch 속도비는 3.3898배다. 병렬 조건의
429/timeout/integrity/격리 오류가 없고 유효 완료가 줄지 않으며 경과 시간이 짧아
D-016의 운영 진행 기준을 통과했다. 소표본이므로 완료율 차이나 속도 향상의 통계적
확증으로 해석하지 않는다. 원래 시간 예산 내에서 EX-013을 시작했다.

[상세 보고서](../../../../.pokechamp-data/benchmarks/glm-concurrency-v3-sequential8/report.md),
[기계 판독 결과](../../../../.pokechamp-data/benchmarks/glm-concurrency-v3-sequential8/report.json),
[actor viewer](../../../../.pokechamp-data/experiments/glm-concurrency-v3-sequential8/index.html),
[통합 실측 보고서](../../../../.pokechamp-data/concurrency-studies/glm-concurrency-v3/report.md).
