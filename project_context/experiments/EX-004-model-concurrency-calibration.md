# EX-004 — 모델별 요청 동시성 측정

- Status: Completed
- 날짜: 2026-09-07
- Experiment ID: `glm-concurrency-v1-calibration`
- 근거: [D-016](../decisions/D-016-model-concurrency.md),
  [EP-007](../exec-plans/completed/EP-007-model-concurrency.md)

## 사전 조건과 선택 규칙

사용자가 선언한 Max 계정·다른 Cloud 작업 중지 조건이다. 모델은 glm-5.3-flash,
low effort, 131072 output, provider 기본 context, 원본 temperature/seed/stop,
요청 timeout 300초다. 별도 공식 모델 동시성 한도는 unknown이며, 공식 계정 한도 10은
2026-09-07 [요금 안내](https://ollama.com/pricing)에서 확인했다.

EX-003의 개발 팀 성공 trace를 attempt_id, actor, event_seq 순으로 정렬하여
IO self_action과 minimax self_action/opponent_action/tool_choice/state_value에서 각각
첫 4개를 선택했다. 고정 20개 corpus, source, 조건, 순서, 예산을 호출 전에 seal했다.
확증 팀은 포함하지 않는다. 순서는 아래와 같이 seed 20260907로 고정했다.

1. 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
2. 1, 3, 9, 8, 5, 6, 2, 7, 10, 4
3. 1, 7, 8, 6, 5, 3, 10, 4, 2, 9

최대 30분/600회이며 실패 보충 호출은 없다. 전송 오류 수준 이상은 추가 탐색을 중단하고,
auth/model/configuration/integrity는 전체 중단한다. 세 반복에 전송 오류가 없고 pooled HTTP
p95가 순차의 2배 이하인 후보 중, 최고 중앙 JSON 처리량의 95% 이상인 최소 C를 선택한다.
엄격한 JSON 완결은 응답 전체가 JSON 객체이며 done_reason=stop인 경우다.

## 결과

실측 315.445초(5.26분), 600회 HTTP 요청 전부 성공, 전송 오류 0이다.
엄격한 JSON 완결은 598/600이다. 나머지 2회도 done_reason=stop이고 내부 JSON 객체를
추출할 수 있었지만 응답 전체가 JSON 하나인 형태는 아니었다. 출력 절단으로 분류하지 않는다.
보고된 입력 token은 823,770, 출력 token은 29,572이며 청구 금액으로 환산하지 않는다.

| 동시성 | 요청 | 엄격한 JSON 완결 | 중앙 JSON/초 | pooled HTTP p95(ms) |
|---:|---:|---:|---:|---:|
| 1 | 60 | 60 | 0.609 | 2436.1 |
| 2 | 60 | 60 | 1.414 | 2388.9 |
| 3 | 60 | 60 | 1.826 | 2364.3 |
| 4 | 60 | 59 | 1.965 | 2687.2 |
| 5 | 60 | 60 | 2.825 | 2493.3 |
| 6 | 60 | 60 | 2.936 | 2546.4 |
| 7 | 60 | 59 | 3.170 | 3095.8 |
| 8 | 60 | 60 | 3.420 | 2384.2 |
| 9 | 60 | 60 | 3.821 | 2974.1 |
| 10 | 60 | 60 | 4.337 | 2974.2 |

**C*=10**이 선택됐다. 이는 실제 측정한 1–10 범위와 해당 계정·모델·고정 corpus·요청
조건의 운용 상한이다. Client HTTP 겹침은 관측했지만 provider 내부 병렬 실행이나
미측정 조건의 최대 처리량을 주장하지 않는다. 배틀 동시성 10의 검증은 조건부 32판에서
처음 수행한다.

## 예산과 후속 비교

최초 실측 시작은 2026-09-07 10:28:01 KST, 신규 작업 중지는 14:13:01,
정리 기한은 14:28:01이다. 비교 순서는 병렬→순차다. EX-006을 coordinator 구현 검토로
중단한 뒤, 요청 경로 hash와 조건을 확인해 EX-008/009에 명시적으로 이어 썼다.
Calibration 추가 호출과 예산 시계 재설정은 하지 않았다.

## Evidence

[Protocol](../../.pokechamp-data/calibrations/glm-concurrency-v1-calibration/protocol.json),
[결과](../../.pokechamp-data/calibrations/glm-concurrency-v1-calibration/report.json),
[corpus](../../.pokechamp-data/calibrations/glm-concurrency-v1-calibration/corpus.json).
같은 디렉터리의 source/ 및 calls/에 snapshot과 요청별 원자료·checksum을 보존한다.
