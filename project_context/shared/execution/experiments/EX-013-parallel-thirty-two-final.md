# EX-013 — 선택 조건의 32판

- Status: Completed
- 날짜: 2026-09-07
- Experiment ID: `glm-concurrency-v3-parallel32`
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

## 완료 결과와 예산

EX-011/012 비교 기준을 통과한 뒤 배틀 10 / 계정 요청 10 / 모델 요청 10을 seal해 실행했다.
32판 사전 예상은 22.108분, 여유 50% 포함 33.162분으로 당시 남은 신규 작업 예산
137.02분에 들어갔다. 실제 batch 경과는 2233.304초(37.22분)로 여유 포함 예상을 초과했다.

예정 32 / 처리 32 / attempt 32 / 유효 완료 20(62.5%) / 미실행 0이다.
출력 검증 오류 4건, watchdog 8건이며 재시도와 보충 경기는 없다. 실패를 패배로 세지 않는다.
HTTP 1622회는 모두 200이며 429와 요청 timeout은 없다. 배틀 최대 동시 수는 10,
실제 HTTP 최대 겹침은 9였다. Calibration의 실제 HTTP 겹침 10과 구별한다.
HTTP p50/p95는 1237.5/2567.65ms, 로컬 permit 대기 p50/p95는 1/2ms다.

최초 실측 시작부터 study 종료까지 7513.718초(125.23분)로 4시간 안에 끝났다.
중단된 v1/v2의 시간도 포함하며 예산 시계를 재설정하거나 calibration을 반복하지 않았다.
이번 조건에서 C*=10을 운용 상한으로 채택하되, 37.22분은 실패를 포함한 일정 처리 시간이다.
32판 모두 정상 완료하는 소요시간과 안정적인 완료율은 미검증이다.

## 한계와 원자료 검증

Watchdog 8건은 모두 b04(팀 ID 6/12)다. 팀12의 원본 닉네임
`Kurama Chakra Mode (Ninetales)`와 `Dubya (Walking Wake)`에 관해 actor 로그에서
`team already has 6 pokemons: cannot add ...` ValueError와 초기 턴 정지를 관찰했다.
같은 팀의 순차 비교가 없으므로 병렬화의 인과 효과로 단정하지 않는다.
팀·parser·알고리즘·모델·출력/context·요청 300초·경기 watchdog 1200초는 변경하지 않았다.
Pinned minimax의 depth 오류와 fallback도 유지되어 정상 minimax 효능을 주장할 수 없다.

모든 attempt와 64개 actor bundle의 seal, 팀·이름·seed 격리를 확인했다. Broker 잔여 permit은
0이며 source와 pinned submodule은 보존했다. Actor viewer 64개를 재생성했다.

[상세 보고서](../../../../.pokechamp-data/benchmarks/glm-concurrency-v3-parallel32/report.md),
[기계 판독 결과](../../../../.pokechamp-data/benchmarks/glm-concurrency-v3-parallel32/report.json),
[actor viewer](../../../../.pokechamp-data/experiments/glm-concurrency-v3-parallel32/index.html),
[통합 실측 보고서](../../../../.pokechamp-data/concurrency-studies/glm-concurrency-v3/report.md).
