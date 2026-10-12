# D-114 — 단일 GPU 자기대국과 선택 행동 확률 보정

- 상태: Accepted
- 날짜: 2026-10-02

사용자가 제공한 「자기대국 + RLCD 확률 보정: 단일 GPU 24시간 실험」의 구현·검증·첫 실행을
명시적으로 승인했다. EX-071 선택 checkpoint에서 가중치만 가져와 PPO·선택 행동 WDL
half-Brier·BC 유지 손실을 결합하고, 선택 정책의 head 보정과 독립 sampling 평가를 수행한다.
RLCD의 확률 보정 발상을 적용한 변형이며 PPO 단독 비교군이 없어 보조 손실만의 인과 효과는
주장하지 않는다. 새로운 자기대국 승인으로 D-113의 당시 비범위를 이번 실험에 한해 구체화한다.

연구 조건·예산·완료·해석 원문은 [EX-072](../experiments/EX-072-selfplay-rlcd.md),
runtime 경계는 [C-056](../CONTRACTS.md#c-056-selfplay), 실행 작업은
[EP-116](../exec-plans/completed/EP-116-selfplay-rlcd.md)가 소유한다.
기존 EX-066/GPU1·과거 자료·봉인·중단 실행은 보존한다. 같은 범위의 재승인은 요구하지 않는다.
