# EX-214 — v14 학습 모델(EX-213) + 2-B v2 온라인 탐색 결합 대 foul-play, Blim 128경기

- 상태: Planned
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-244](../plans/EP-244-laya-search-2bv2-and-v14-training.md)
- 관련 decision: [D-220](../decisions/D-220-laya-recovery-matchup-2bv2-and-v14.md), [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

[EX-213](EX-213-laya-v14-data-and-mcts5k-training.md)에서 학습한 `v14` 모델과 [EX-212](EX-212-laya-search-2bv2-vs-foulplay-unlimited.md)의 `2-B v2` 온라인 탐색(MCTS 5k + $V_\phi$ 스케일 매칭 + `foe_options_clean` + 흡수 보정)을 결합하면 [EX-208](EX-208-laya-search-2b-vs-foulplay-unlimited.md)(`0.406`) 및 `EX-212` 대비 Blim 128경기 점수가 추가 상승하는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 체크포인트 | 정책/상대예측: `EX-213/checkpoints/selected` (`v14`), 상태가치: `EX-207/checkpoints/selected` |
| 실행 조건 | `EX-212`·`EX-213` 완료 후 물리 GPU 0 전용 서빙, Blim 128슬롯, 뷰어 `exports/battle_viewers/ex214/`([C-047](../../../CONTRACTS.md#c-047-viewer-export)) |

## 결과

실행 전(Planned).
