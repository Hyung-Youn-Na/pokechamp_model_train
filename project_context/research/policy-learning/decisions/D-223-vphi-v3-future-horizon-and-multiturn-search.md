# D-223 — 미래 영향력 반영 상태가치망 V_phi v3 및 다수 턴 2-ply 탐색 · Way A v2 가드레일

- 상태: Accepted
- 결정일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-247](../plans/EP-247-vphi-v3-future-horizon-and-multiturn-search.md)
- 관련 experiment: [EX-221](../experiments/EX-221-laya-state-value-v3-future-train.md), [EX-222](../experiments/EX-222-multiturn-2ply-waya-v2-ab.md), [EX-223](../experiments/EX-223-laya-waya-v2-vphiv3-2ply-vs-foulplay.md)
- 선행 결정: [D-222](D-222-laya-way-c1-v14-walled-teacher50k.md), [D-221](D-221-laya-main-waya-mcts50k-vphi-v2.md), [D-219](D-219-laya-multiturn-search-and-value.md), [D-191](D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 배경 및 근거

[EX-220](../experiments/EX-220-laya-waya-mcts50k-ladder.md) 공식 래더 실전 진단, [EX-217](../experiments/EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md) Blim 128판(`3,094`회 회복 가능 턴), [EX-218](../experiments/EX-218-laya-way-c1-v14-walled-teacher50k-train.md) `hard_train.jsonl`(`6,456`회 회복 가능 턴) 분석에서 `EX-216` $V_\phi$ v2 + 1-ply 평가 + `Way A v1`의 구조적 **HP 회복·`Protect` 과대평가**가 확인되어 `EX-218`·`EX-220`을 조기 종료했다.

1. **추론 근시안(1-ply 고정)**: `search_2b_v2.expand_turn1_features_v2`가 1턴 뒤 $s_{t+1}$만 보고 $V_\phi$를 읽어, 2~5턴 뒤 상대 랭업(`Nasty Plot`/`Iron Defense`), 반복 `Lunge`/`Spikes`, 턴 낭비가 분기에 나타나지 않는다.
2. **미래 결정 피처 누락**: `featurize.py`에 **회복기/기술 잔여 PP** 및 **`Protect`·회복 직전 사용(`last_used_move`)** 정보가 없으며, `matchup_features.py`의 `full_hp = (hp >= 0.999)` 이진 스텝이 `96% → 100%` `Roost`에 과도한 불연속 보상을 유발했다(`073833` T23–T24).
3. **반사실적(Counterfactual) 분포 불일치**: 인간 정상 궤적의 최종 승패($z$) 단독 학습만으로는 “풀피 = 유리함” 상관관계만 외우고 “템포를 버리고 회복을 누른 나쁜 반사실 자식 상태”에 페널티를 학습하지 못한다.
4. **Way A v1 규칙 결함 3건**: `walled_veto`가 `Protect`로 덮어쓰기(`072713` T22–T23), `vphi_blunder_veto`의 고HP(`96%`) `Roost` 강제(`073833` T23), MCTS+$V_\phi$ 만장일치 합의가 `pr_ratio` 페널티로 무효화되어 8연속 `Roost` 루프에 갇힘(`074335` T7–T11).

## 결정

기존 동결 패키지 및 `EX-207`/`EX-216`/`EX-217` 기존 모듈(`featurize.py`, `matchup_features.py`, `value_model_v2.py`, `way_a.py`)은 무변경 보존하고, **물리 GPU 0·1 전용**(GPU 2·3 미접촉) 아래 새 비침습 모듈로 다음 2단계를 순차 검증한다.

1. **1단계 — 미래 영향력 반영 상태가치망 $V_\phi$ v3 ([EX-221](../experiments/EX-221-laya-state-value-v3-future-train.md))**:
   - **피처 보강 (`featurize_v3.py`, `EX-207` 동일 5,470/304/304 게임 분할·Blim 64팀 제외)**: 잔여 회복기 PP 비율(`heal_pp_frac`), 최소 기술 PP 비율, 직전 턴 `Protect` 사용(`just_protected`)·직전 턴 회복(`just_healed`)·`Protect` 활성 플래그 추가(정확한 반대칭성 유지) 및 `Multiscale` `full_hp` 불연속 점프 완화.
   - **미래 궤적 Multi-Horizon 보조 헤드**: 동일 리플레이 궤적의 `t+3`, `t+5`, `t+10`턴 보드 유리도(`alive_diff`/`hp_diff`, 종료 시 `±1`), 5턴 모멘텀 변화(`adv_{t+5} - adv_t`), 3턴 후 상대 랭업 누적(`fut_opp_boost_3`)을 정확한 반대칭 보조 헤드로 공동 학습해 인코더가 중기 미래 역학을 표현하도록 강제한다.
   - **반사실적(Counterfactual) 회복·`Protect` 순위 손실**: `train` 분할 리플레이에서 인간 프로가 회복/`Protect`를 **기각하고 공격·교체·랭업을 선택한 턴**(고HP ≥ 75%, 상대 랭업/해저드 턴, 또는 승리 게임)과 **실제로 회복을 선택해 승리한 턴**을 `poke_engine.generate_instructions`로 1-ply 시뮬레이션해 쌍대 마진 순위 손실(`train_cf.npz`, 검증용 `val_cf.npz` 게임 완전 분리)로 학습·검증한다.
2. **2단계 — 다수 턴 2-ply Top-K 탐색기 + `Way A v2` 가드레일 오프라인 A/B ([EX-222](../experiments/EX-222-multiturn-2ply-waya-v2-ab.md))**:
   - `search_multiturn.py`: 1-ply `V_phi v3` 상위 후보(`K=4`: Laya 상위 2 + 1-ply 상위 2)에 대해 2턴째(`s_{t+2}`)까지 기대미니맥스(Top-K 2-ply Expectiminimax)를 펼쳐 리프에서 `V_phi v3`를 1회 배치 추론.
   - `way_a_v2.py`: `walled_veto` `Protect`/고HP 회복 제외, 연속 `Protect` 가드, `vphi_blunder_veto` `active_hp ≥ 85%` 회복기 금지, `MCTS + V_phi` 만장일치 동의 시 `pr_ratio` 페널티 완화.
   - `EX-220` 4대 실전 실패 장면 + `EX-217`/`EX-218` held-out 고·중HP 회복률 및 턴당 지연 시간을 `EX-216` 1-ply 대비 정량 A/B 보고한 뒤, 후속 Blim 128 배틀 또는 Way C/B 재가동 여부를 사용자 확인으로 결정한다.

## 판정 기준

[D-191](D-191-no-offline-battle-gate.md)에 따라 오프라인 지표(held-out `AUC`/`LogLoss`, 반사실적 회복 분별 정확도, 고·중HP 회복률)는 보고 전용이며 배틀 성능을 대리 증명하지 않는다.
