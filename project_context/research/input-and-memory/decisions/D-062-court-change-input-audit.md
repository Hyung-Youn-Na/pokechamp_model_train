# D-062 — Court Change 입력 교정과 EX-042 전수 오프라인 감사

- 상태: Accepted
- 날짜: 2026-09-16
- 승인: 현재 사용자의 제공 계획 구현·검증 지시.

B 정규화는 공개 protocol로 입증된 Court Change 실행 알림만 계산용 effects에서 제외하고 parser_effects를 보존한다. 공개 -swapsideconditions에서 pinned Showdown 교환 대상의 현재 진영 이력을 이동하며 설치 시점·원본 참조·중첩을 보존한다. 교환을 신규 설치로 세지 않는다.
기존 현재 효과·공개 이력 계약의 bugfix이며 CLI/입력 schema/계산 의미 버전은 유지하고 source hash로 구분한다. 근거 없는 제거·계산기 허용 목록 확대·미공개 정보 추정은 제외한다.
[EP-051](../plans/EP-051-court-change-input-audit.md)에 전체 결정·입력·독립 사례·회귀·보존 검증을 등록한다. 기존 보고는 보존하고 영향은 별도 정정 분석으로 연결한다. 본실험 보류, 유료 호출·신규 배틀 실험·과거 재개0. 선봉 품질·승률·Gen9 OU 전체 정확성 claim은 없다.

추가 감사 결함: 공개 -status의 [from] ability / [of] holder를 명시된 보유자에 반영하며, 기절한 상대의 effective_types는 pinned Showdown의 테라 해제에 맞춘다. 원시 parser types·과거 관측 tera_type과 자기 request는 유지한다. schema/계산 의미 변경 없이 기존 현재 상태 계약을 복구하며 전수 차이·별도 정정 분석·독립 검증을 요구한다.
