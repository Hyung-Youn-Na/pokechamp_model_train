# D-082 — JEV v3 기본 지식·효과 사전

- 상태: Accepted
- 날짜: 2026-09-21
- 승인: 사용자 계획 구현 지시와 배틀 지식 전문 제공

새 jev-choice-v3를 기본으로 준비한다. 제공된 GENERATION 9 SINGLES MECHANICS를 그대로
추가하고 고정 gen9-effects-v1의 영어 name/desc를 state.effect_reference에 요청당 한 번 제공한다.
자기·확인된 상대·합법 후보·최근 공개 이력만 수집하며 설명 속 다른 효과는 확장하지 않는다.
JEV 기술 객체의 id를 사용하고 불리언 테라 플래그를 효과 이름으로 읽지 않는다.
current_pp_source는 새 모델 입력의 모든 위치에서 제거하되 값·이유·산출 검증은 유지한다.
PP 정책·원래 관측/request와 사전 identity는 모델 밖 감사 근거다.
규범 계약은 C-045, 처치 범위는 RESEARCH_DESIGN의 D-082, 구현·검증은 EP-074다.
v1/v2·EX-051/052 봉인/뷰어는 보존하며 과거 감사는 당시 버전을 사용한다.
새 API·배틀·성능 평가나 과거 재개는 포함하지 않는다.
