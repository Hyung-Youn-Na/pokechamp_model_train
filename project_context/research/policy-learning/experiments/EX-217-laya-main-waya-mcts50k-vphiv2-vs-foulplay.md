# EX-217 — 방식 A(Laya 메인 합의형 블런더 가드 + MCTS 50k + V_phi v2 + 렌더러 무효 대면 수정) 대 foul-play, Blim 128경기

- 상태: Completed
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-245](../plans/EP-245-laya-main-blunder-veto-mcts50k-vphi-v2.md)
- 관련 decision: [D-221](../decisions/D-221-laya-main-waya-mcts50k-vphi-v2.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행 실험: [EX-216](EX-216-laya-state-value-v2-matchup-train.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`EX-216`에서 보강·검증된 매치업 인지 $V_\phi$ v2와 `MCTS 50,000 iterations`, 그리고 렌더러 전 공격기 무효 시 `duel: walled -> lose` 수정을 **방식 A(Laya 메인 + MCTS/V_phi 합의형 블런더 가드)**로 결합했을 때, [EX-208](EX-208-laya-search-2b-vs-foulplay-unlimited.md)(`2-B v1`, `0.406`) 대비 Blim 128경기 성적과 Laya 주권 유지율(개입률·블런더 교정 정확도)이 어떻게 변하는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 정책·렌더러 | `EX-200/checkpoints/selected` (`v13` + `way_a.install_walled_duel()`: 전 공격기 무효 시 `duel: me 9+ hits (none) ... -> lose` 발화) |
| MCTS 검증기 | `poke-engine` Rust MCTS **`50,000 iterations`** (`--workers 4`, `Taunt`+흡수 특성 회복 보정 및 `foe_options_clean` PP 파싱 수정 포함) |
| 상태가치 검수관 | [EX-216](EX-216-laya-state-value-v2-matchup-train.md) 매치업 인지 $V_\phi$ v2 (`matchup_deepsets_v2`, held-out `AUC 0.7536`, `LL 0.5848`) |
| 의사결정 방식 | **방식 A (`integration.laya_search.way_a`)**: Laya 1순위 기본 존중 + 합의형 블런더 가드 (`std: dm≥0.05 & dv≥-0.015`, `severe: dm≥0.10 & dv≥-0.03`, `endgame(≤5): dm≥0.04 & dv≥-0.02`, `walled: dm≥0.01 & dv≥-0.03`, `duel_lose: dm≥0.035/dv≥0.045`, `vphi_only: dv≥0.06 & dm≥-0.01`, `forced_switch: dm≥0.04`) |
| 통제 입력·자원 | EX-174 봉인 Blim 128슬롯, foul-play `8f541f8` 3,000ms × 병렬 4 · 스레드 1, 시간·턴 제한 해제 + 500턴 `auto-tie` 안전 처리. **물리 GPU 0 전용**(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, GPU 2·3 미사용), 포트 `8100-8103`, `mem-guard 40`, 출력 `runs/model-training/EX-217`, 뷰어 `exports/battle_viewers/ex217/`([C-047](../../../CONTRACTS.md#c-047-viewer-export)) |
| 기준선 | 주: [EX-208](EX-208-laya-search-2b-vs-foulplay-unlimited.md) (`2-B v1`, `0.406`), 보조: [EX-206](EX-206-laya-search-2a-vs-foulplay-unlimited.md) (`0.336`), [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) (`0.315`), [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md) (`0.375`), [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) (`0.331`) |

## 결과

완료·봉인(`2026-11-24`, 물리 GPU 0 전용, `verify_seal == []`, `2,955`파일 봉인, 오류 `0`).

- **성적 (`128 / 128` 정상 완료, `audit 128/128`)**: **50승 0무 78패, 평균 점수 `0.391` (`0.390625`, 조합 클러스터 95% `[0.312, 0.461]`)**.
- **같은 슬롯 비교 (보고 전용, D-191 — 모든 95% 신뢰구간이 0 포함)**:
  - vs **`EX-208` (`2-B v1`, `0.406`, `n=128`)**: **`-0.016 [-0.133, +0.102]`** (`나음 25 / 나쁨 27 / 같음 76`, 딱 2경기 차)
  - vs **`EX-201` (`rerank` 단일, `0.375`, `n=128`)**: **`+0.016 [-0.109, +0.141]`** (`31 / 29 / 68`)
  - vs **`EX-206` (`2-A` MCTS 5k, `0.336`, `n=128`)**: **`+0.055 [-0.039, +0.156]`** (`24 / 17 / 87`)
  - vs **`EX-205` (`v13` 단일, `0.315`, `n=127`)**: **`+0.079 [-0.024, +0.173]`** (`26 / 16 / 85`)
  - vs **`EX-174` (`v10rt`, `0.331`, `n=127`)**: **`+0.063 [-0.047, +0.175]`** (`30 / 22 / 75`)
- **팀 유형별·세부 지표**:
  - `balance (n=70) 0.386` (`EX-208 0.386`과 동일), `offense (n=34) 0.382` (`EX-208 0.471` 대비 3경기 열세), `weather (n=20) 0.400`, `defense (n=4) 0.500`.
  - 실패 기술률 **`5.72%`** (`306 / 5,351`, `EX-208 6.17%` 대비 감소), 테라 사용 **`90 / 128`경기** (`30승 60패`).
  - **공정성·응답**: `foul-play` `7,417`결정 **`p50 = 7.163s`** (`p95 7.688s, max 8.934s`, `tera 121`경기 — `EX-218` CPU 병행에도 간섭 없음), `waya50k` 결정 지연 `p50 3.792s / p95 7.646s` (보고서 `p50 3.872s`).
  - **방식 A 텔레메트리 (`7,522`결정, 오류 `0`)**: **Laya 1순위 유지율 `89.2%`** (`6,709`), 블런더 교정 **`10.8%`** (`813` — `duel_lose_mcts 224`, `vphi_blunder 137`, `duel_lose_vphi 137`, `severe_mcts 108`, `forced_mcts 77`, `consensus 69`, `walled 32` [감지 `156`턴], `endgame 29`), `with_vphi 88.7%` (`6,669`).
- **산출물·뷰어 ([C-047](../../../CONTRACTS.md#c-047-viewer-export))**:
  - 보고서: `runs/model-training/EX-217/report.md`
  - 뷰어: `/workspace/exports/battle_viewers/ex217/index.html` (`128`경기, `7,670`결정)
