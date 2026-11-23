# EX-208 — 2-B 온라인 다중턴 탐색 + 신경망 상태가치 V_phi 결합 대 foul-play, Blim 128경기(시간 제한 없음)

- 상태: Running
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md)
- 관련 decision: [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

[EX-206](EX-206-laya-search-2a-vs-foulplay-unlimited.md)(2-A) 온라인 탐색에 [EX-207](EX-207-laya-state-value-2b-train.md)에서 학습한 리플레이 승패 기반 상태가치 모델 $V_\phi(\text{State})$(`laya` $q$-가중 1~2플라이 리프 평가 + MCTS $Q$·사전확률 융합)를 결합하면 `EX-206` 및 `EX-205` 대비 foul-play Blim 128경기 점수가 개선되는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 모델 | 정책/상대예측: `EX-200` + `v13`, 상태가치: `EX-207` selected (모두 **GPU 0 전용** 서빙) |
| 통제 입력 | EX-174 봉인 Blim 128슬롯, foul-play 3,000ms × 병렬 4, 시간·턴·결정 수 제한 해제(`actor_unlimited`) |
| 자원·출력 | 물리 GPU 0 전용(GPU 2·3 미사용), 포트 `8100-8103`, `runs/model-training/EX-208`, 뷰어 `exports/battle_viewers/ex208/`([C-047](../../../CONTRACTS.md#c-047-viewer-export)) |
| 같은 슬롯 기준선 | 주: [EX-206](EX-206-laya-search-2a-vs-foulplay-unlimited.md)(2-A), 보조: [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md), [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md), [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) |

## 결과

실행 전(Planned).
