# D-135 — 상대 공개 정보 v6와 JEV 재평가

- Status: Accepted
- Date: 2026-10-13
- 승인: 현재 사용자 제공 계획의 구현·검증·신규64경기 실행 지시

현재 공식 관측과 같은 행 cutoff의 전체 공개 prefix로 상대의 공개 기술·도구·특성을
재구성하는 `jev-choice-v6`를 추가한다. 공개 정보 보존과 현재 상태 교정을 함께 평가하며
v4/v5·EX-083/085 원자료·뷰어·봉인은 유지한다. 신규 평가에만 턴별 공개 서버 로그 뷰어를 쓴다.

runtime 원문은 [C-067](../CONTRACTS.md#c-067-jev-public-memory-v6), 실험 공통 조건과27B는
[EX-086](../experiments/EX-086-jev27b-public-memory-v6.md),9B는
[EX-087](../experiments/EX-087-jev9b-public-memory-v6.md), 진행은
[EP-140](../plans/EP-140-jev-public-memory-v6.md)에서 관리한다.
기존 환경·공식 모델·정책·계산 범위를 유지하고27B→9B 순서로GPU0–3을 독점 사용한다.
일반 성능이나 모델 크기만의 효과를 주장하지 않는다.
