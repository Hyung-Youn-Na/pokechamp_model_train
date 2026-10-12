# EX-034 — Smogon 기반 원본 A 운용 한계 진단 설계

- 상태: Prepared — 팀·대진·검토·자원 명세 검증 완료, 대전 미실행
- 날짜: 2026-09-11 (Asia/Seoul)
- 관련: [D-040](../decisions/D-040-smogon-diagnostic-design.md), [EP-028](../exec-plans/completed/EP-028-smogon-diagnostic-design.md), [EX-033](EX-033-external-memory-repeat32.md)
- 승인: 현재 사용자의 평가 준비 계획 구현·검증. 유료 대전·실행기 구현은 제외한다.

## 질문과 산출물

원본 A가 셋업·공격 전개 순서, 교체·설치기 누적, 회복·핵심 포켓몬 보존,
날씨 등 제한된 턴 활용에서 어떤 판단을 내리는지 조사할 구성을 마련했다.
판단 실패가 발견될 것이라는 방향성 가설은 없다. 탐색64경기의 성적과 행동 증거로
후속 가설을 만들 수 있지만 현재 자료로 A의 한계·개선 효과를 결론 내리지 않는다.

| 산출물 | 위치 |
|---|---|
| 후보12 비교, 선정8의 출처·운용 근거·불확실성·해시 | [팀 선별 명세](smogon-diagnostic-design/team-selection.md), [기계 판독 목록](smogon-diagnostic-design/candidates.json) |
| 수정하지 않은 원본 팀 구성 | [teams/](smogon-diagnostic-design/teams/) |
| 탐색64경기 순서·팀 배정·진영·모든 seed | [JSON](smogon-diagnostic-design/schedule.json), [CSV](smogon-diagnostic-design/schedule.csv) |
| 분모·행동 전수 검토·중단·후속 확인 기준 | [평가 protocol](smogon-diagnostic-design/protocol.md) |
| EX-033 A 사용량·장기전 민감도 | [자원 명세](smogon-diagnostic-design/resources.md), [재집계 근거](../exec-plans/evidence/ep028/a-usage.json) |
| 고정 baseline·실행기 지원 차이 | [실행기 조사](smogon-diagnostic-design/runner-gap.md) |
| 로컬 검증 결과 및 재현 명령 | [검증 기록](../exec-plans/evidence/ep028/verification.json), [EP-028](../exec-plans/completed/EP-028-smogon-diagnostic-design.md) |

Smogon [Sample Teams](https://www.smogon.com/forums/threads/sv-ou-sample-teams.3712513/)와
[Tournament Team’s Bazaar](https://www.smogon.com/forums/threads/sv-ou-tournament-teams-bazaar.3752863/)를
진입점으로 원본 paste와 연결된 해설을 조사했다. 현재 공개 ladder가 아니라
저장소의 `pokemon-showdown@e64915c0eab066db1d3e732b1280386468dd7415`의 `gen9ou`가
합법성 기준이다. 최신 티어 적합성과 pinned 환경 적합성을 혼동하지 않는다.

## 고정 설계

탐색팀 S1/H1/R1/W1 × 기존 팀2/6 × Abyssal/OneStep × A의 새팀/기존팀 배정 × 반복2 = 64경기다.
각 32개 세부 셀에서 반복마다 게임 seed를 달리하고 A를 p1/p2에 한 번씩 배정한다.
반복2개가 seed와 진영의 독립 효과를 추정하지는 못한다. 제출 순서와 seed는 이미 고정됐으며,
병렬 실행의 완료 순서·provider 내부 처리는 결정론적으로 보장하지 않는다.

A는 EX-033의 `io`/upstream IO·fallback, `state_translate2`, `glm-5.3-flash`, thinking `low`,
temperature0, model seed100, 출력131072, provider 기본 context를 유지한다.
새 전략 해설·필드 설명서·요약·외부 메모리·개선된 B 입력을 추가하지 않는다.
실험 전체 정책 metadata에 B 버전이 보인다는 이유로 그 prompt가 A에 주입됐다고 해석하지 않는다.
EX-033의 실제 A 요청457개 및 source173개를 대조한 근거는 `a-usage.json`에 있다.

후속확인팀 S2/H2/R2/W2는 이번64경기에 들어가지 않는다. 확인 단계에서 팀 구성·평가 기준을
결과에 맞춰 바꾸거나, 무조건 추가 경기를 실행하지 않는다. 탐색 결과와 별도의 사전등록이 필요하다.

## 실행·복구 경계와 현재 분모

현재는 **설계상 예정64·시도0·유효완료0·실패0·무효0·미실행64**다.
실행 승인은 없고 `schedule.json`의 `execution_authorized=false`가 이를 명시한다.
Cloud 호출·provider 재시도·보충 경기·새 유료 시계는 모두0이다.
후속64경기 기본안은 slot당1회, provider retry0, 보충·재수집0이다.
EX-033 A 내부의 출력 파싱 재질의/fallback 알고리즘은 그대로 유지하고 provider 재시도와 구분한다.

[C-018](../CONTRACTS.md#c-018-recovery)의 영향 범위 중단·증거 보존·무효화·별도 재평가를 적용한다.
경기별 provider/timeout/watchdog/환경 실패는 분리하고, 공유 설정·수집·무결성 결함은 영향 범위를
중지한다. 범위를 입증하지 못하면 잠재 영향 전체를 중단한다. 별도의 전체 중단 예외는 없다.
실제 수집 결함의 재수집은 이번 기본안에서0이며 원자료/halt/누적 사용량을 지우지 않는다.
원본 A가 본래 생략하는 정보는 baseline의 관측 특성으로 기록하고 수집 구현의 이탈과 구별한다.

이 준비의 완료 기준은 재현 가능한 팀·대진·평가 명세와 로컬 검증이다.
실행기 지원, 새 유료 예산/상한·최초시계, 실행 검증·대전·검토가 완료됐다는 뜻은 아니다.
후속 실행의 구체적인 승인 대상과 필요한 변경은 실행기 조사 문서에 남겼다.
