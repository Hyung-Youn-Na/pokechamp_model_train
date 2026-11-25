# D-222 — 방식 C-1: v14+walled_duel 입력 및 Hard-Example MCTS 50k + EX-216 V_phi v2 교사 증류 학습

- 상태: Accepted
- 결정일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-246](../plans/EP-246-laya-way-c1-v14-walled-teacher50k-distill.md)
- 관련 experiment: [EX-218](../experiments/EX-218-laya-way-c1-v14-walled-teacher50k-train.md), [EX-219](../experiments/EX-219-laya-way-c1-vs-foulplay-unlimited.md)
- 선행 결정: [D-221](D-221-laya-main-waya-mcts50k-vphi-v2.md), [D-220](D-220-laya-recovery-matchup-2bv2-and-v14.md), [D-219](D-219-laya-multiturn-search-and-value.md), [D-191](D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 배경 및 근거

[DESIGN.md#laya-main-abc-roadmap](../DESIGN.md#laya-main-abc-roadmap)의 Laya 메인 3단계(방식 A·B·C) 로드맵에 따라, 방식 A([EX-217](../experiments/EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md), 물리 GPU 0 실행 중)와 병행하여 **방식 C-1(고품질 교사 증류를 통한 Laya 본체 체급 강화)**을 추진한다(사용자 지시 2026-11-24 13:24 KST).

1. 기존 [EX-209](../experiments/EX-209-laya-mcts5k-q-rerank-1b-train.md)은 `v13` 입력 + `MCTS 5k` 단독 교사를 사용해 회복·흡수·`walled` 맹점과 5k 근시안이 타깃에 그대로 남아 있었다.
2. [EX-213](../experiments/EX-213-laya-v14-data-and-mcts5k-training.md)에서 이미 구축한 `v14` 데이터(`335,998`행, 거짓 `2HKO` 제거 `23,673`건, PP 손상 `foe` 복구 `6,766`건)에 `walled_duel` 수정(전 공격기 무효 시 `duel: me 9+ hits (none) ... -> lose`)을 100% 라이브-오프라인 일치하게 반영한다.
3. 특히 실수가 집중되는 **Hard-Example `~25,000` 학습 턴 + `~3,000` held-out 턴**(전체 `walled`·`absorb` 100% 포함 + `duel: lose`·`opp heals:`·종반·불일치 상위)에 대해 **`MCTS 50,000 iterations` + `EX-216` 매치업 인지 $V_\phi$ v2** 결합 교사(`Q_teacher = 0.55*Q_mcts50k_adj + 0.45*Q_vphi2`)로 KL-정규화 신뢰구간 소프트 타깃을 생성한다.

## 결정

기존 동결 패키지와 `EX-209`/`EX-213` 원자료는 수정하지 않고, **물리 GPU 0·1 전용**(GPU 2·3 미사용) 아래 [EX-218](../experiments/EX-218-laya-way-c1-v14-walled-teacher50k-train.md)을 다음 단계로 실행한다.

1. **병행 준비 단계 (`EX-217` GPU 0 실행과 동시 수행)**:
   - `v14+walled_duel` 증분 재렌더링(CPU `16w nice 19`, `mem-guard 30`) → `datasets/generated/laya-v14w-c1/v1/`
   - Hard-Example `~28k`턴 `EX-200` `p`/`foe` 추론(**물리 GPU 1 전용**) → `MCTS 50k` + 1-ply 전개(CPU `28w nice 19`, `mem-guard 40`) → `EX-216` $V_\phi$ v2 평가(**물리 GPU 1 전용**) → KL-정규화 소프트 타깃(`tau=0.025`, `walled`/`rescue` 자동 승격) 조립.
2. **본 학습 및 평가 단계 (`EX-217` 완료 후 GPU 0 유휴 확인 시 자동 진입)**:
   - `EX-196` 출발점에서 `Hard-50k+Vphi2` 골드(×3) + 일반 `MCTS-5k` 골드(×2) + 인간 앵커(`150k`) + `foe_options_clean`(`100k`) + 테라 지식 행으로 **물리 GPU 0·1 DDP 1에폭 학습**(`mem-guard 55`).
   - 물리 GPU 0에서 held-out 일반 MCTS-5k Q, **Hard-Example `MCTS 50k + V_phi v2` held-out**, 테라 지식(`heldout-A/B`)을 `EX-196`·`EX-200`·`EX-209`와 비교 보고한다.
3. **후속 배틀 평가 ([EX-219](../experiments/EX-219-laya-way-c1-vs-foulplay-unlimited.md))**: `EX-218` 완료 보고 후 사용자 확인을 받아 `EX-218` 단독 및 방식 A 결합 Blim 128경기를 진행한다.

## 판정 기준

[D-191](D-191-no-offline-battle-gate.md)에 따라 오프라인 지표 및 배틀 지표 모두 보고 전용이며, 95% 신뢰구간이 0을 포함하면 통계적 개선을 주장하지 않는다.
