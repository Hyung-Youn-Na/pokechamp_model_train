# D-157 — Tacit-9B Thinking + GLM-5.3 Low 판단 비교

- 상태: Accepted
- 날짜: 2026-10-16
- 승인: 사용자가 제시된 EX-104 계획을 “Implement the plan.”으로 승인했다.

EX-103의 수행 모델을 Tacit-9B BF16 Transformers 패키지로 교체한다. 모든 다후보 입력에서
첫 판단과 thinking 이후 판단을 기록하고 후자를 실행한다. GLM-5.3 Low와 대전/입력/사건 정책은
유지한다. 기존 사전8회와 EX-103 2·5·6턴 고정3사례 뒤 같은 서버에서 실제1경기를 수행한다.
8192토큰과 공식 sampling 기본값을 사용하며 규칙에 의한 선택 교정은 추가하지 않는다.
조건·gate·중단·분모·해석은 [EX-104](../experiments/EX-104-tacit-thinking-low.md), 진행은
[EP-163](../exec-plans/active/EP-163-tacit-thinking-low.md)를 따른다. 기존 기록/봉인/Blocked는 보존한다.
