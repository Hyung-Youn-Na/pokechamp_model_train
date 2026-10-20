# D-153 — GLM-5.3 low 동일 대진 새1경기

- 상태: Accepted
- 날짜: 2026-10-15
- 승인: 사용자 “glm 5.3 … EX099와 같은 설정으로 실험”, “Implement the plan.” 및 후속 “reasoning effort는 low로 설정해줘”

새 EX-100에서 planner.model을glm-5.3으로, reasoning_effort를low로 설정한다.
EX-099의 Flash/high와 비교하여 모델과 추론 강도가 함께 달라지는 처치다.
기존 Z.ai endpoint·인증 경로·thinking enabled·temperature0·top_p0.95·max_tokens131072·
시간null·개별HTTP 정책·형식복구·JEV/GPU0·팀/seed·프롬프트/피해계산·호출/자원 한도는 유지한다.
공식 근거: https://docs.z.ai/guides/llm/glm-5.3 및 https://docs.z.ai/api-reference/llm/chat-completion

설정 검증에glm-5.3을 허용하되 공통 Flash/low 기본값과 과거 동결 설정은 유지한다.
모델 접근 실패 시 Flash/다른 endpoint로 대체하지 않는다. 재경기/자동재개0이다.
기존 EX-099 및 모든 중단 실험의 원자료·뷰어·봉인은 보존한다.
조건 원문은 [EX-100](../experiments/EX-100-glm53-low-sample.md),
진행은 [EP-159](../exec-plans/completed/EP-159-glm53-low-sample.md)다.
