# D-095 — 자기 벤치 축약 동일32경기

- Status: Accepted
- Date: 2026-09-23
- 승인: 현재 사용자 제공 계획의 구현·검증·실행 지시

EP-093 기존 compact=True를 실험 전용 jev-choice-v5로 연결한다. 일반 턴 비출전 자기 포켓몬의
known_move_set·stats만 생략하고 나머지 입력/지시문은 EX-058과 유지한다. 기본 v3·과거 v4 재현을 유지한다.
D-091의 새 후보 선정과 구분하여 이번 EX-059에 한해 EX-058 봉인 팀·32행 순서·게임/actor seed·
진영을 그대로 재현한다. 신규 팀 후보 선정은 없다. 같은 대진의 상세 대 축약 탐색 비교를 승인한다.

실험 조건·예산·gate·중단·비교 원문은 [EX-059](../experiments/EX-059-jev-compact32.md),
진행은 [EP-095](../exec-plans/completed/EP-095-jev-compact32.md)다.
