# D-139 — GLM planner–JEV 수행 모델 실험 환경

- 상태: Accepted
- 날짜: 2026-10-15
- 승인: 현재 대화의 설계 선택과 확정 계획에 대한 사용자 `Implement the plan.` 지시

`glm-5.3-flash`를 전략 planner로, 기본 `autotrust/JEV-9B`를 합법 행동 선택기로 연결한다.
호출 정책과 프롬프트를 독립 설정으로 바꾸는 환경을 구현하고 기존27B·MiniCPM5-2B-Jev
패키지도 선택 가능하게 한다. 기본 입력은 교정된 계산기 포함 v6다.
사용자가 선택한 범위는 구현·입력 미리보기·모의 실행·로컬 검증이며 유료 API/GPU 추론과
새 실제 모델 배틀 실험은 포함하지 않는다. 실제 실행의 EX·대진·예산/자원은 후속 등록한다.

호출은 동기이며 off/initial_only/every_decision/periodic/events/events_or_periodic을 지원한다.
기본은 최초+3턴 간격+기절/실제Tera/자기 강제교체 요청이다. JEV 확률 기반 호출과 비동기
갱신은 이번 범위에서 제외한다. Planner는 현재 입력·이전 계획·계획 이후 공개 사건을 보고
전략·우선순위만 제공한다. 사용할 수 없는 계획 응답은 해당 경기만 실패 처리한다.

참고 구현은 `/ref/minecraft-agent` commit `78b40ed59514e5e2abde33a05ce398ecb2c39e05`다.
계획을 수행 모델 state에 넣는 구조를 참고하되 실시간 timer·비동기 갱신·재시도·고정 경로를
승계하지 않는다. 프롬프트/호출 변경을 구분하며 저장 경기 재생으로 승률 효과를 주장하지 않는다.

연구 방법은 [planner 환경 설계](../RESEARCH_DESIGN.md#jev-planner-environment), runtime은
[C-070](../CONTRACTS.md#c-070-jev-planner), 진행·검증은
[EP-145](../exec-plans/completed/EP-145-jev-planner-environment.md)에서 관리한다.
기존 실험 조건·모델 수치·자료·봉인·Blocked/Paused는 보존한다.
