# D-221 — Laya 메인 합의형 블런더 가드(방식 A), MCTS 50k 심화, 상성·도구·특성·기술 반영 가치망 V_phi v2 및 렌더러 무효 대면 보완

- 상태: Accepted
- 결정일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-245](../plans/EP-245-laya-main-blunder-veto-mcts50k-vphi-v2.md)
- 관련 experiment: [EX-216](../experiments/EX-216-laya-state-value-v2-matchup-train.md), [EX-217](../experiments/EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md)
- 선행 결정: [D-220](D-220-laya-recovery-matchup-2bv2-and-v14.md), [D-219](D-219-laya-multiturn-search-and-value.md), [D-218](D-218-laya-v13-input-bugfixes.md), [D-214](D-214-laya-foulplay-primary-ladder-final.md), [D-191](D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 배경 및 근거

[EX-215](../experiments/EX-215-laya-search2bv2-ladder.md) 공식 래더(`battle-gen9ou-2718581763` Turn 10~20, `Air Balloon Gholdengo` vs `Dragonite`) 실전 진단에서 기존 3-모듈 결합(`2-B v2`)의 세 가지 구조적 약점이 동시에 겹치는 사례를 확인했다.

1. **렌더러 `strategy.duel()` 전 공격기 무효 엣지케이스**: 공격기 전부 `fails`(0 데미지)일 때 `best is None`이 되어 `duel()`이 `None`을 반환함으로써 `duel: ... -> lose` 경고와 `2-B v2`의 `duel_lose` 완화가 모두 꺼졌다.
2. **MCTS `5,000` iterations의 탐색 깊이 한계**: 같은 Turn 10 보드에서 MCTS 반복 수를 `5,000 → 50,000`으로 늘리면 `Dragon Dance` 1위(`0.455~0.505`)에서 `switch gholdengo/darkrai` 1위(`0.396~0.399`)로 즉시 역전되며, 8샘플 순차 기준 `50,000`회도 턴당 `~1.14s`(CPU 1코어, GPU 0)로 실전·평가 모두 감당 가능하다.
3. **$V_\phi$ (`EX-207`)의 상성·도구·특성·기술 맹점**: `EX-207`은 5,470경기에서 원시 ID(`species/ability/item/move`) 임베딩이 경기 서명 과적합(`val AUC 0.645`)을 일으켜 이를 0으로 마스킹한 23개 순수 상태 수치만 썼다. 그 결과 `Air Balloon`·고스트 무효·흡수 특성·회복기·상성 배율 등 핵심 매치업 역학을 전혀 보지 못해 "상대를 못 때리는 랭크업"을 큰 이득으로 오판했다.
4. **Laya 메인 주권 구조 요청**: 사용자 지시(2026-11-24 11:28 KST)로 **Laya를 주 결정권자(메인)**로 두고, **MCTS(`50k`)**와 **보강된 $V_\phi$ v2**가 합의형 블런더 가드(방식 A)로 동작하도록 재설계하며, **$V_\phi$ v2 보강 실험([EX-216](../experiments/EX-216-laya-state-value-v2-matchup-train.md))을 우선 수행**한다.

## 결정

기존 동결 패키지(`laya_imitation`, `laya_v10~v13`, `laya_foe`, `laya_value`, `laya_fp1`, `foulplay`, `.tools/foul-play/`, `EX-207` 체크포인트·자료)는 수정하지 않고, **물리 GPU 0·1 전용**(GPU 2·3 미사용) 아래 다음을 단계적으로 실행한다.

1. **1단계 — 상성·도구·특성·기술 반영 가치망 $V_\phi$ v2 ([EX-216](../experiments/EX-216-laya-state-value-v2-matchup-train.md), 우선 실행)**:
   - 원시 ID 임베딩 과적합을 피하면서도 Gen 9 메커니즘을 정확히 반영하기 위해, `poke_engine.State`의 `(mon_num, mon_cat, global_num)`에서 결정론적·팀-독립적 **6×6 기계적 매치업 피처**(`integration/laya_search/matchup_features.py`)를 계산한다: 타입 상성·테라 타입/자속·`Air Balloon`/부유/흡수 특성 무효 및 회복·주요 방어/공격 특성(`Multiscale`, `Unaware`, `Good as Gold`, `Regenerator`, `Poison Heal`, `Thick Fat`, `Purifying Salt`, `Huge Power`, `Supreme Overlord`, `Ruin` 등)·주요 도구(`Choice Band/Specs/Scarf`, `Life Orb`, `Assault Vest`, `Heavy-Duty Boots`, `Focus Sash`, `Leftovers`, `Eviolite` 등)·기술 분류(회복기·드레인·랭크업·선공기·교대기·장판/제거·상태이상/방해)·스피드 우위·유효 데미지·`is_walled`(공격 무효)·회복 고려 2HKO·6×6 팀 커버리지 요약.
   - 정확한 영합 반대칭성($V_\phi(\text{swap}(s)) = 1 - V_\phi(s)$)을 구조적으로 보장하는 `StateValueNetV2`(`integration/laya_search/value_model_v2.py`)를 `EX-207`과 동일한 누수 통제 분할(`datasets/generated/laya-state-value/v1`, train 5,470 / calib 304 / val 304게임, Blim 64팀 제외)에서 **물리 GPU 0 전용**으로 학습한다.
   - `EX-207`(`AUC 0.7389`, `LogLoss 0.5967`) 및 `evaluate.rs`(`AUC 0.7235`) 대비 held-out 지표와 실전 회귀 사례(`Air Balloon Gholdengo` T10~11, `Draining Kiss` T4~6, `Water Absorb` T22)를 검증한다.
2. **2단계 — 방식 A(Laya 메인 합의형 블런더 가드) + MCTS `50k` + 렌더러 무효 대면 수정 ([EX-217](../experiments/EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md))**:
   - `EX-216` 검증 완료 후, (a) 렌더러 전 공격기 무효 시 `duel: me 9+ hits (none) ... -> lose` 출력 보강, (b) `MCTS 50,000 iterations` 전술 검증기, (c) `EX-216` $V_\phi$ v2 이중 승인 검수관을 결합해 **Laya 1순위를 기본 존중하고 MCTS·$V_\phi$ v2가 합의하여 큰 블런더(또는 종반/`forced_switch` 확정 손해)를 지적할 때만 교정**하는 방식 A를 구현하고 Blim 128경기로 [EX-208](../experiments/EX-208-laya-search-2b-vs-foulplay-unlimited.md)(`0.406`)과 같은 슬롯 비교한다.
3. **후속 로드맵 — 방식 B(입력 도구 주입) · 방식 C(교사/크리틱 내재화)**:
   - 사용자 지시(2026-11-24: A·B·C 순차 실험)에 따라 전체 3단계 설계·전제·지름길 붕괴/분포 이동 방지 규칙을 [DESIGN.md#laya-main-abc-roadmap](../DESIGN.md#laya-main-abc-roadmap) 및 [RESEARCH_MANUAL.md](../../../RESEARCH_MANUAL.md)에 고정 기록한다. 방식 B·C는 `EX-217`(방식 A) 결과 확인 후 별도 EP/EX 등록 및 실행 확인을 거쳐 착수한다.

## 판정 기준

[D-191](D-191-no-offline-battle-gate.md)에 따라 오프라인 지표 및 Blim 128경기 모두 보고 전용이며, 95% 신뢰구간이 0을 포함하면 통계적 개선을 주장하지 않는다.
