# D-158 — 기존 Tacit vLLM 서버로 새 평가

- 상태: Accepted
- 날짜: 2026-10-16
- 승인: 사용자 “해당 vllm 서빙 모델을 사용해서 다시 테스트 해주세요.”

기동 완료한 사용자 소유 Tacit-9B vLLM 서버를 사용해 EX-104와 같은 사전8·고정3·실제1경기를
별도 EX-105로 수행한다. 기존 EX-104 Blocked·원자료·봉인은 보존한다.
GPU1 외부 서버에 HTTP로 연결하며 적재·종료·재시작 권한은 승계하지 않는다.
후보 전체 logprob_token_ids 판독, 서버 sampling/cache/backend와 HTTP 계측 차이는 새 처치의
일부로 명시한다. CPU forward 계측을 vLLM 물리 forward로 가장하지 않는다.
조건·자원·해석은 [EX-105](../experiments/EX-105-tacit-vllm-low.md),
진행은 [EP-164](../plans/EP-164-tacit-vllm-low.md)를 따른다.
