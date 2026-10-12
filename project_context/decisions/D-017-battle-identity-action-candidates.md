# D-017 — 배틀 식별과 요청별 행동 후보 통합

- Status: Accepted
- 날짜: 2026-09-07
- 근거: 사용자가 전달한 수정·단계 검증·조건부 병렬 32판 계획 전체의 구현 지시.

## 결정

Parent benchmark actor 전용 어댑터에서 protocol 진영과 nickname을 분리하고 request ident/details를
미리보기 객체에 연결한다. 부분 문자열·유사도 병합을 금지하며 모호성은 environment 오류다.
비동기 parser 예외를 actor 감시 루프에 전달하고 해당 경기만 취소한다.
요청별 동일 후보 객체를 prompt, 엄격한 JSON 검증, 행동 변환에 사용한다.
자기 행동은 실제/모의 상태의 available 목록·강제 교체·변신 가능 여부를 따른다.
상대 교체는 공개 미리보기와 관찰을 합치고 active/fainted를 제외한다. 상대 기술 추정법은 유지한다.
설명 요구를 제거하고 정확한 JSON 후보 목록을 명시한다. 첫 출력 오류에서 중단한다.
후보 없음·변환 실패도 기록하고 중단하며 재질문·임의 행동 대체는 없다.

## 검증 및 해석

과거 실패 8판 protocol, 잘못된 응답 4개와 경계 조건을 오프라인 검증한 뒤 b04 팀6/12의
기존 seed·진영으로 로컬 8판을 실행한다. 모두 정상일 때 고정 corpus20+실패4 상태를 새 조건으로
봉인하여 동시성1/10 각각3회(총144회, 보충 없음)를 실행한다. 전체 출력/전송 성공,
p95(10)<=2*p95(1), 실제 요청 겹침10이 필수다. 과거 C*=10을 승계하지 않으며 최대 처리량 탐색이 아니다.
통과 후 새 core-smoke8(배틀8/요청10)이 8/8 유효·모든 오류0일 때만 core-repeat32(10/10)를 실행한다.
Cloud 검증부터4시간, 3시간45분 신규 작업 중지,15분 정리. 32판 추정*1.5가 남은 예산 이내여야 한다.
모델·effort·temperature·출력/context·timeout·watchdog·팀·seed와 minimax depth 오류는 유지한다.
과거 evidence/분모를 보존하며 새 조건을 기존 효능 결과와 혼합하지 않는다.

## 거절한 대안

JSON 완화, nickname 제거, 숨겨진 상대 roster 사용, 출력 repair/fallback은 사용자 범위와 맞지 않는다.

## 증거

[EX-014](../experiments/EX-014-parallel-thirty-two-repeat.md),
[공식 protocol](https://github.com/smogon/pokemon-showdown/blob/master/sim/SIM-PROTOCOL.md),
[EP-009](../exec-plans/completed/EP-009-battle-identity-action-candidates.md).
