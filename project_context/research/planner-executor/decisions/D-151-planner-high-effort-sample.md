# D-151 — GLM high 추론 강도 동일 대진 샘플

- 상태: Accepted
- 날짜: 2026-10-15
- 승인: 사용자 “reasoning effort를 high로 조정해서 다시 실험해보자.”

EX-097의 low를 high로 바꾼 새 실제1경기를 수행한다. 이번 실행 설정만 변경하며 공용 기본값은
자동 변경하지 않는다. temperature0·출력8192·프롬프트/피해 계산·호출/형식 재시도·JEV 모델/환경/
GPU0 Marlin·대진/seed·호출/시간/메모리 상한은 유지한다. 원 EX-097과 앞선 실패·봉인은 보존한다.
[EX-098](../experiments/EX-098-planner-high-effort-sample.md)의 원문을 따르며
[EP-157](../plans/EP-157-planner-high-effort-sample.md)에서 수행한다.
새 경기에서 계획을 생성한다. 호출시간·usage·출력복구·Ruination 선택/입력/계획의 기술적 사례를
EX-097과 비교하되 경로 차이를 포함한 단일 표본으로 일반 성능/인과효과를 주장하지 않는다.
