# D-037 — 계산기 기술명 정규화

- 상태: Accepted
- 날짜: 2026-09-10

사용자가 EX-031 Weather Ball 결함의 수정을 명시적으로 요청했다.
날씨 Sun은 입력됐으나 소문자 ID가 Move.originalName에 남아 라이브러리의 canonical 이름 비교를 통과하지 않았다.
worker는 기존 generation move lookup의 name을 두 계산 경로의 Move 생성에 사용한다.
기술 목록을 임의로 열거해 우회하지 않고 pinned 데이터의 정식 이름을 일관되게 사용한다.
설치 라이브러리와 입력 schema/semantics/평가 기준은 그대로 두고 새 source hash와 회귀 증거로 구현을 구분한다.
과거 source qualification은 새 source에 적용되지 않으며 새 유료 실험·재수집을 승인하지 않는다.
[EP-025](../plans/EP-025-calculator-move-names.md)에 범위·완료 기준을 등록한다.

수정은 독립28조건/16roll·593회귀·81입력 재생으로 검증했다. 현재 runtime 제한은 이 버그 수정 범위를 반영하되 EX-031의 과거 무효/미완료 상태는 유지한다.
