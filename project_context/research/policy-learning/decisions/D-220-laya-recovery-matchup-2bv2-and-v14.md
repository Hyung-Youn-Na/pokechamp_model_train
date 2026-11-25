# D-220 — 상대 회복·흡수 기반 대면 불리 대응: 2-B v2 탐색 개선(CPU 서빙) 및 v14 입력·재학습 병행

- 상태: Accepted
- 결정일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-244](../plans/EP-244-laya-search-2bv2-and-v14-training.md)
- 관련 experiment: [EX-212](../experiments/EX-212-laya-search-2bv2-vs-foulplay-unlimited.md), [EX-213](../experiments/EX-213-laya-v14-data-and-mcts5k-training.md), [EX-214](../experiments/EX-214-laya-v14-search2bv2-vs-foulplay-unlimited.md)
- 선행 결정: [D-219](D-219-laya-multiturn-search-and-value.md), [D-218](D-218-laya-v13-input-bugfixes.md), [D-214](D-214-laya-foulplay-primary-ladder-final.md), [D-191](D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 배경 및 근거

[EX-208](../experiments/EX-208-laya-search-2b-vs-foulplay-unlimited.md)(6,410결정)과 [EX-211](../experiments/EX-211-laya-search2b-ladder.md)(공식 래더 8판, 311결정)의 전수 로그 및 `poke-engine v0.0.48` 검증에서, 상대 체력 회복(`Draining Kiss`, `Water Absorb` 등)으로 인한 대면 불리를 제대로 회피하지 못하는 5개 원인을 확인했다.

1. **2-B 융합 스케일 불일치**: 합법 수 간 폭(`max - min` 중앙값)이 `Q_mcts`(`0.215`, `1.80×`)·`0.03·ln(p)`(`0.250`, `2.09×`) 대비 `Q_vphi`(`0.120`)가 2배 가까이 좁아, `Q_vphi`와 `Q_mcts`가 충돌한 턴(49.8%) 중 `Q_vphi`가 승리하는 비율이 `25.0%`에 그쳤다(`sleepman610` T4~T6에서 $V_\phi$는 교체를 1위로 맞췄으나 `EX-200` 사전확률과 `MCTS`에 덮임).
2. **`laya_foe` PP 괄호 파싱 버그**: `seen calmmind drainingkiss(13/16 used)`의 공백 포함 괄호가 `seg[5:].split()`에서 깨져, PP를 절반 이상 쓴 관측 기술이 `foe:move:other`로 누락되었다(`EX-208` 15.6%, `EX-211` 16.1% 턴에서 `other ≥ 0.30`).
3. **입력 표현(`v10~v13`) 결손**: 회복 무시 거짓 `2HKO` 표기(`compact_v2._damage_move`), `opp heals:`의 드레인 기술·흡수 특성 누락, 흡수 특성 공격 시 `fails`만 표기(`heals opp 25%` 미표기).
4. **`poke-engine v0.0.48`의 `Taunt` + 흡수 회복 누락 버그**: 일반 상태에서는 14종 회복·흡수가 정상이지만, 공격자가 `TAUNT` 상태일 때 `Water Absorb`의 `Heal SideTwo`(+25%)가 생성되지 않아 `MCTS`·$V_\phi$ 모두 회복 0으로 시뮬레이션했다(`Xrlylyl` T22~T26, `EX-211` `Water Absorb` 26회 발동).
5. **500턴 `auto-tie` 파서 중단**: `EX-205`·`EX-210`의 스톨 미러(`fp-b20`)에서 Showdown 500턴 경고(`|bigerror|You will auto-tie...`)가 액션 거절로 오인되어 `phase_halt`를 유발했다.

## 결정

기존 동결 패키지(`laya_imitation`, `laya_v10~v13`, `laya_foe`, `laya_value`, `laya_fp1`, `foulplay`, `.tools/foul-play/`)는 일절 수정하지 않고, **물리 GPU 0·1 전용**(GPU 2·3 미사용) 자원 격리 아래 두 경로를 병행 추진한다.

1. **경로 (1) — 2-B v2 탐색·서빙 개선 ([EX-212](../experiments/EX-212-laya-search-2bv2-vs-foulplay-unlimited.md), CPU 서빙)**:
   - `integration/laya_search/search_2b_v2.py`에 (A) PP 괄호를 제거하는 `foe_options_clean(state)`, (B) `Q_vphi`–`Q_mcts` 스케일 매칭 융합(`alpha=0.55`, 클리핑 `1.0~2.5×`) 및 `duel: ... -> lose` 구간 `prior_lambda` 완화(`0.03 → 0.015`, `floor 1e-3`), (C) `Taunt`+흡수 특성 회복 누락 보정(`V_phi` 자식 상태 `hp_frac +0.25` 반영 및 `Q_mcts` 역이득 보정)을 구현한다.
   - `EX-200` + `v13` + `EX-207` $V_\phi$ 그대로 재학습 없이 **CPU 서빙**(`OMP_NUM_THREADS=4`, `mem-guard 40`)으로 Blim 128경기를 수행해 [EX-208](../experiments/EX-208-laya-search-2b-vs-foulplay-unlimited.md) 대비 순효과를 검증한다.
2. **경로 (2) — `v14` 회복 인지 렌더러 및 재학습 ([EX-213](../experiments/EX-213-laya-v14-data-and-mcts5k-training.md), CPU 16w → GPU 0·1 DDP)**:
   - 비침습 래퍼 `integration/laya_v14/render_v14.py`로 ① 회복(`Leftovers`/드레인/`Poison Heal`) 반영 거짓 `2HKO` 제거(`recoverko`), ② `opp heals:`에 드레인 기술·흡수 특성 포함(`drainheal`), ③ 흡수 특성 공격에 `; heals opp 25%` / `; boosts opp` 명시(`absorbheal`)를 추가한다.
   - 기존 `EX-209`와 동일한 MCTS-5k Q 골드(`125k`×2) + 인간 앵커(`150k`) + `foe_options_clean` 기반 상대예측 앵커(`100k`) + 테라 지식 행을 `v14`로 재렌더링(CPU `16워커 nice 19`, `mem-guard 30`)하고, `EX-196`에서 1에폭 **물리 GPU 0·1 DDP 학습**(`mem-guard 55`)을 수행한다.
3. **결합 평가 ([EX-214](../experiments/EX-214-laya-v14-search2bv2-vs-foulplay-unlimited.md), 후속)**: `EX-212`·`EX-213` 완료 후 `v14` 체크포인트 + `2-B v2` 탐색 결합 Blim 128경기를 평가한다.

## 판정 기준

[D-191](D-191-no-offline-battle-gate.md)에 따라 오프라인 지표 및 Blim 128경기 모두 보고 전용이며, 95% 신뢰구간이 0을 포함하면 통계적 개선을 주장하지 않는다.
