# EX-219 — 방식 C-1 학습 모델(EX-218, v14+walled_duel) 대 foul-play, Blim 128경기

- 상태: Planned
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-246](../plans/EP-246-laya-way-c1-v14-walled-teacher50k-distill.md)
- 관련 decision: [D-222](../decisions/D-222-laya-way-c1-v14-walled-teacher50k.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행 실험: [EX-218](EX-218-laya-way-c1-v14-walled-teacher50k-train.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

방식 C-1으로 강화된 `EX-218` Laya 본체(`v14+walled_duel` + Hard-Example `MCTS 50k + V_phi v2` 증류)가 단일 forward 및 방식 A 결합 시 Blim 128경기에서 기존 단일 모델([EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) `0.315`, [EX-210](EX-210-laya-mcts5k-q-rerank-1b-vs-foulplay-unlimited.md) `0.344`, [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md) `0.375`) 및 탐색 결합 기준선([EX-208](EX-208-laya-search-2b-vs-foulplay-unlimited.md) `0.406`, [EX-217](EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md)) 대비 얼마나 향상되는가?

## 조건 및 변수

- `EX-218` 학습·평가 완료 보고 후 사용자 확인을 받아 실행 구성을 확정한다.

## 결과

실행 전(Planned).
