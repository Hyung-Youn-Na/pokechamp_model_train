# D-120 — 고정 대진 GPU 학습·실험 실행

- 상태: Accepted
- 날짜: 2026-10-07
- 근거: 사용자 “GPU 학습과 실제 고정 A/B 실험을 진행해주세요.”

D-119의 구현 완료 후 [EX-076](../experiments/EX-076-fixed-matchup-mcts.md)의 기존 조건으로
단일 GPU·최초 검증부터12시간1회 실행을 승인한다. 모델·탐색·팀·평가·gate·복구 조건은 유지한다.
[EP-125](../plans/EP-125-fixed-matchup-run.md)에서 준비/검증·pilot·학습·잠긴 평가·
감사/뷰어·봉인·자원 반환을 수행한다. 선행 gate 실패 시 의존 단계는 중단한다.
기존 Qwen 실험·Blocked plan·자료를 재개하지 않으며 추가 주기는 자동 시작하지 않는다.
