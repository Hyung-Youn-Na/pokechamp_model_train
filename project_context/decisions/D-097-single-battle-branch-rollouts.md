# D-097 — EX-058 한 경기 행동별 분기 데이터

- Status: Accepted
- Date: 2026-09-28
- 승인: 대화의 완성 계획에 대한 사용자 `Implement the plan.` 지시.

EX-058 battle-19 / b02-r3-s0의 원경기 22개 결정·167개 후보를 재현하고,
후보마다32회 양측 Abyssal 후속 시뮬레이션으로 조건부 행동 가치 자료를 수집한다.
실전 관측 입력을 유지하고 원경기 복원 gate를 통과해야 한다. 고정13팀 재사용은
이번 과거 경기 재현·분기 추출에 한정한 명시적 예외이며 새 팀 모집단 선택이 아니다.
과거 자료·Blocked 실험·기존 운영 기본값은 변경하지 않는다.

protocol 원문은 [EX-060](../experiments/EX-060-single-battle-branch-rollouts.md),
진행은 [EP-101](../exec-plans/completed/EP-101-single-battle-branch-rollouts.md)이다.
후속 Abyssal·실제 숨은 서버 상태에 조건부인 값이며 최적 정책·JEV 승률·일반 OU 효능으로
해석하지 않는다. 사용 대진은 개발 자료로 분류하고 독립 평가 holdout에서 제외한다.
