# EX-210 — 1-B 오프라인 MCTS-5k Q 재정렬 학습 모델(EX-209, v13 단일 forward) 대 foul-play, Blim 128경기(시간 제한 없음)

- 상태: Planned
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md)
- 관련 decision: [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

[EX-209](EX-209-laya-mcts5k-q-rerank-1b-train.md)에서 경량 MCTS(`5,000 iters`) 루트 $Q$ 후보 재정렬 타깃과 `v13` 입력으로 학습한 단일 forward 모델이, 탐색 없이도 [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) 및 [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md) 대비 foul-play Blim 128경기 점수를 높이는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 체크포인트 | `runs/model-training/EX-209/checkpoints/selected` (`v13` 서빙, 단일 forward argmax) |
| 통제 입력 | EX-174 봉인 Blim 128슬롯, foul-play 3,000ms × 병렬 4, 시간·턴·결정 수 제한 해제(`actor_unlimited`) |
| 자원·출력 | CPU 서빙(또는 GPU 0 전용, GPU 2·3 미사용), 포트 `8100-8103`, `runs/model-training/EX-210`, 뷰어 `exports/battle_viewers/ex210/`([C-047](../../../CONTRACTS.md#c-047-viewer-export)) |
| 같은 슬롯 기준선 | 주: [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md), 보조: [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md)(0.375), [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)(0.331) |

## 결과

실행 전(Planned).
