# D-099 — Qwen 행동가치 로컬 서빙·배틀 연결

- 상태: Accepted
- 날짜: 2026-09-28
- 승인 근거: 사용자가 제공한 계획을 새 맥락에서 구현·검증하라는 명시적 지시.

EX-061 최종 LoRA를 GPU1에서 한 번 로딩하여 후보별 독립 q를 제공하고,
PokéChamp 전용 프로필이 최대 q의 합법 행동을 실행한다. EVE와 배틀 가상환경은 분리한다.
새 연결 검증은 Abyssal과 진영을 바꾼 고정2경기다. 시간 전체 상한 없음·요청600초·재시도0,
검증 후 소유 서버 종료와 재실행 명령 제공까지 승인한다.

방법·해석은 [RD](../RESEARCH_DESIGN.md#qwen-local-battle), runtime은
[C-049](../CONTRACTS.md#c-049-qwen-local), 실행 조건은
[EX-062](../experiments/EX-062-qwen-local-battle.md), 구현·진행은
[EP-103](../exec-plans/active/EP-103-qwen-local-battle.md)이 소유한다.
승패는 연결 검증의 관측 결과이며 독립 성능 개선 판정에 사용하지 않는다.
기존 봉인 자료·Blocked 실험·EX-061 가중치·EVE lock·canonical submodule을 보존한다.
