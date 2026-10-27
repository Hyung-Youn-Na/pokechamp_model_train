# D-152 — 경기/전체 시간 상한 해제·GLM 최대 출력 새1경기

- 상태: Accepted
- 날짜: 2026-10-15
- 승인: 사용자 “경기 시간제한 없이, glm max_tokens 제한도 최대로 설정하여 다른 것은 EX098과 동일하게 설정하여 새 실험”

새 EX-099에서 battle_seconds와 total_seconds를null로 설정해 양쪽 actor와 전역 예산의 경과시간
상한을 없앤다. 유한 수치의 과거 설정/기본값은 보존하고 무한대는 내부 계산에만 사용한다.
직렬화한 config/상대 watchdog은null이며 실제 경과시간은 계속 기록한다.
GLM max_tokens는 공식 API 최대131072로 설정한다.
근거: https://docs.z.ai/api-reference/llm/chat-completion (2026-10-15 확인, 허용1..131072).

EX-098의 high/temperature0/top_p0.95·모델/GPU0 Marlin·프롬프트/피해v6·팀/seed·호출정책·
출력형식 최초+추가5회·GLM HTTP128/JEV256(사전8포함)/경기1·메모리·disk null은 유지한다.
개별 통신 timeout과 HTTP 재시도는 기존 정책이며 모든 오류/사용량을 보존한다.
현재 실행에 강제 수정/재개하지 않고 새1경기를 수행한다. 기존 EX-098 사용자 중단/봉인은 불변이다.
공용 기본 max_tokens/시간 한도는 자동 변경하지 않는다.
조건 원문은 [EX-099](../experiments/EX-099-planner-unlimited-time-max-output.md),
진행은 [EP-158](../plans/EP-158-planner-unlimited-time-max-output.md)다.
