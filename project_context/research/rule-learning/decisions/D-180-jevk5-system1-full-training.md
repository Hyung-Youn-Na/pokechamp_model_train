# D-180 — JevK5 전체 System One 학습

- 상태: Accepted
- 날짜: 2026-10-21

## 맥락·결정

현재 사용자가 제공한 전체 학습 계획을 구현하고 실행하도록 명시했다.
원본 JevK5 새 LoRA로 8묶음 전체를 학습하고 별도 동결한 독립 평가를 사용한다.
세부 조건의 원문은 [EX-116](../experiments/EX-116-jevk5-system1-full-training.md), 구현·검증은 [EP-203](../plans/EP-203-jevk5-system1-full-training.md)이다.
기존 EX113 결과/adapter/봉인·서버·다른 Blocked/Paused 실행을 변경하거나 재개하지 않는다.

## 근거·영향

학습pool 전체 사용과 독립 평가 분리, 비Thinking 유효후보CE가 사용자 목표다.
자료·GPU 사전검사 및 새 평가 동결 이전에는 본학습을 시작하지 않는다. 완료와 개선은 별도 판정한다.
대안은 기존 adapter 이어학습/기존자료 재분할이며 사용자 확정조건에 부합하지 않아 채택하지 않는다.
