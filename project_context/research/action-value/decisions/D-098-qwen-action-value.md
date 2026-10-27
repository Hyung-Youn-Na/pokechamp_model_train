# D-098 — EX-060 기반 Qwen3.5-4B 첫 행동가치 학습

- 상태: Accepted
- 날짜: 2026-09-28

## 맥락

사용자가 제공한 첫 학습 검증 계획을 구현·검증하도록 명시적으로 지시했다.
EX-060은 한 대진의22관측·167후보·후보당32회이며 독립 성능 평가가 아니다.

## 결정

EVE 독립 worktree에서 Qwen/Qwen3.5-4B를 LoRA로 학습한다. 전체 후보별 q를 이진 soft target으로
변환하고 관측과 후보를 각각 동일 가중하는 전체 정보 half-Brier 기대손실을 사용한다.
원관측·규칙·역할 전문 유지, 물리 GPU1 한 장·시간 상한 없음·고정3epoch를 승인 계획대로 실행한다.
방법은 [연구 설계](../DESIGN.md#qwen-action-value-first-run), 실행 조건은
[EX-061](../experiments/EX-061-qwen-action-value.md), schema는 [C-048](../CONTRACTS.md#c-048-action-value-training)을 따른다.
새 배틀·API·독립 성능 평가·중단 plan 재개는 제외한다.

## 거절한 대안·근거

반전만 학습하면 결과 차이에 조건부 선택 편향이 생긴다. 최선 후보 SFT는 승률 크기·동률을 버린다.
EVE는 decoder·LoRA·letter readout·Transformers5.17 연결 범위가 가장 작다.
bandit RLCD와 전체 정보 학습을 구분한다.

## 영향·증거

기술 완료와 개발 적합을 따로 판정한다. q는 고정 숨은 상태·Abyssal 후속 값이며 배틀 개선을
보장하지 않는다. 현재 사용자 계획 구현 지시 · [EP-101 보고](../../../exec-plans/evidence/ep101/report.md) ·
[EP-102](../plans/EP-102-qwen-action-value.md).
