# D-161 — Tacit 규칙 Q&A LoRA 1회

- 상태: Accepted
- 날짜: 2026-10-19

## 맥락·승인

현재 사용자가 제시한 GPU1·2·3 학습 계획의 구현·검증·실행을 명시적으로 요청했다.
D-159의 데이터 전용 작업과 별도 실험이며 EX-104 중단이나 GPU0 EX-106을 재개/변경하지 않는다.

## 결정·근거

[EX-107](../experiments/EX-107-tacit-ruleqa-lora.md)의 고정 조건으로 규칙 Q&A LoRA1회를 수행한다.
기반 고정·assistant-only loss·기존 split·validation 선택·test 잠금으로 동일 템플릿 내 개선을 평가한다.
배틀/긴 Thinking 개선으로 해석하지 않는다. 원응답과 실패·효과 없음도 보존한다.

## 대안·영향

다른 방법/초모수 탐색은 승인 범위가 아니다. 환경/모델 다운로드 없이 기존 자산을 사용한다.
구현·진행은 [EP-173](../exec-plans/completed/EP-173-tacit-ruleqa-lora.md), 실험 조건 원문은 EX-107이다.
