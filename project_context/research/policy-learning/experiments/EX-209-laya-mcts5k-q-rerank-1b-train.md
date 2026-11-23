# EX-209 — 1-B 오프라인 경량 MCTS-5k 루트 Q 후보 재정렬 타깃 생성 및 v13 단일 모델 학습(GPU 0·1)

- 상태: Running
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md)
- 관련 decision: [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-218](../decisions/D-218-laya-v13-input-bugfixes.md), [D-217](../decisions/D-217-laya-engine-value-rerank-training.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`EX-199/200`의 1턴 `evaluate.rs` 타깃을 **다중턴 경량 MCTS(`5,000 iters`) 루트 $Q$ 기반 후보 내부 재정렬 타깃**(+ `v13` 입력)으로 대체해 단일 forward 모델을 학습하면, held-out 다중턴 타깃 일치도와 후속 배틀([EX-210](EX-210-laya-mcts5k-q-rerank-1b-vs-foulplay-unlimited.md)) 성적이 `EX-200`보다 개선되는가? (`1-A` 2플라이 오프라인 타깃은 사용자 지시로 보류.)

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 출발 체크포인트 | `runs/model-training/EX-196/checkpoints/selected` (또는 `EX-200`, 상세 확정 후 동결) |
| 입력·타깃 | `v13` 입력, ~6만 `turn_action`·`forced_switch` 후보 결정에 `poke-engine` MCTS `5,000 iters` 루트 $Q$ 계산(합법 수 `restrict` 적용) → 후보 내부 softmax 재정렬 + 인간 앵커 + 상대예측 + 테라 지식 혼합 |
| 자원 | 추론(`infer`)·DDP 학습: **물리 GPU 0·1 전용**(`--nproc_per_node 2`, 유효 배치 유지 위해 `grad_accum=4`, GPU 2·3 미사용); MCTS 타깃 생성: CPU 48~64워커(`nice 19`, `mem-guard 40`, 배틀 비충돌 시) |
| 출력 | `datasets/generated/laya-mcts5k-q/v1/`, `runs/model-training/EX-209/checkpoints/selected` |

## 결과

실행 전(Planned).
