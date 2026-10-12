# D-049 — Viewer 턴 탭과 LLM 응답 기본 표시

- 상태 (Status): Accepted
- 날짜: 2026-09-14

## 맥락

사용자가 공통 viewer의 턴 이동과 LLM 응답·reasoning 기본 표시 개선을 명시적으로 요청했다.
현재 호출 전체가 details 안에 있으며 결정은 일렬로 표시된다.

## 결정

기록된 decision_start.showdown_turn으로 표시용 그룹을 구성하고 준비/team_preview·턴 미상은 별도로 둔다.
첫 그룹을 기본 선택하고 탭, 바로가기 선택란, 이전/다음과 키보드 이동을 제공한다.
기존 decision/issue anchor와 URL history가 선택한 그룹을 복원한다.
각 호출의 reasoning/원문 답변은 접힘 밖에서 생략 없이 표시하고 입력/B2 원본/metadata는 접어 둔다.
전체 protocol은 별도 details로 제공한다. 내장 JavaScript는 CSP hash로 허용하고 비활성 시 모두 정적으로 읽는다.
새 생성분에만 적용하며 기존 실험 viewer·source·봉인·Blocked 상태를 보존한다.

## 거절한 대안

- 기존 실험 일괄 재생성: 사용자 범위 밖이다.
- 외부 UI 의존성 및 schema 변경: 표시 개선에 필요하지 않다.

## 근거·영향

C-009/D-010의 원자료와 derived output 분리 및 full-fidelity 열람을 유지한다.
showdown_turn은 표시용이며 decision identity를 대체하지 않는다. 연구 설계·parser·계산 변경은 없다.

## 증거

- 현재 사용자 제공 구현 계획 및 [EP-037](../exec-plans/completed/EP-037-viewer-turn-tabs.md).
- [C-009](../CONTRACTS.md#c-009--pokéchamp-research-battle-observability), [D-010](D-010-adopt-pokechamp-battle-observability.md).
