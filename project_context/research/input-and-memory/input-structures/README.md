# 배틀 입력 구조 — 사람용 상세 설명서

이 폴더는 **사람이 저장 입력과 실제 API 요청을 확인하는 용도**다.
에이전트의 새로운 필독 문서나 자동 로딩 경로, 모델 프롬프트, 실행 계약으로 사용하도록 등록한 폴더가 아니다.
연구 조건·규범 원문은 상위 주제의 CONTRACTS/DESIGN과 개별 EX에 유지한다.

| 설명서 | 입력/프로필 | 핵심 배치 |
|---|---|---|
| [EX112_INPUT_STRUCTURE.md](EX112_INPUT_STRUCTURE.md) | jev-choice-v6 + candidate-matchup-v1 | 전체 상태에 기술/피해를 유지하고 기술 후보에 현재 대면 요약 추가 |
| [EX115_INPUT_STRUCTURE.md](EX115_INPUT_STRUCTURE.md) | jev-choice-v7 + candidate-action-v1 | 사용할 기술 설명과 전체 피해 분기를 후보로 이동, 공통 상태·비후보 기술 유지 |

두 문서는 각각 전체 구조, 자기/상대 포켓몬, 기술/피해, 상성표·스피드·로그,
합법 후보, 실제 API 포장과 해석 경계를 설명한다. v7 문서는 공통 주석·두 damage의 차이와
실제 선봉/일반/테라/강제교체 예시까지 포함한다.

처음 읽을 때는 각 문서의 전체 구조 → state → 후보/피해 → API 순서로 읽는다.
버전을 비교할 때는 EX112의 move_ref/상태 기술 경로와 EX115의 move/selected_range/other_assumptions를 대조한다.
`state.version`, `state.input_profile`(v7), `current_matchup.version`은 적용 범위가 다른 식별자다.

문서의 트리에는 조건부 필드도 포함된다. 예시의 발췌와 실제 전체 JSON을 구별하고,
unknown·null·생략·계산된0을 서로 바꾸어 읽지 않는다. 기존 실험·봉인 자료는 이동하지 않았다.
