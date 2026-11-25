# EX-216 — 상성·도구·특성·기술 기계적 매치업 피처 반영 상태가치망 V_phi v2 학습 및 검증 (GPU 0)

- 상태: Completed
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-245](../plans/EP-245-laya-main-blunder-veto-mcts50k-vphi-v2.md)
- 관련 decision: [D-221](../decisions/D-221-laya-main-waya-mcts50k-vphi-v2.md), [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-207](EX-207-laya-state-value-2b-train.md)(`clean_deepsets_v2`, held-out `AUC 0.73893`, `LogLoss 0.59674`, `Brier 0.20626`, `ECE 0.02578`), `evaluate.rs` calibrated(`AUC 0.72346`, `LogLoss 0.61471`)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`EX-207`의 순수 상태 동역학 피처(23개)에 원시 ID 암기 없이 Gen 9 **상성(타입·테라)·도구(`Air Balloon`, Choice, Boots, Life Orb, Assault Vest 등)·특성(흡수·부유·`Multiscale`·`Unaware`·`Regenerator`·`Poison Heal` 등)·기술(유효 데미지·`is_walled`·회복기·드레인·선공기·랭크업·장판/교대기)**에서 결정론적으로 계산한 **6×6 기계적 매치업 피처**와 **정확한 영합 반대칭성**을 결합한 **`V_phi v2`**가:
1. 동일 held-out 304경기(`17,699`행)에서 `EX-207`(`AUC 0.7389`) 및 `evaluate.rs`(`AUC 0.7235`)를 얼마나 상회하는가?
2. `EX-207`이 실패했던 실전 회귀 3종(`Air Balloon Gholdengo` vs `Dragonite` T10~11, `Draining Kiss` T4~6, `Water Absorb` T22)에서 올바른 유불리 순위를 복원하는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 데이터 분할 | `datasets/generated/laya-state-value/v1/` (`EX-207`과 100% 동일: train 321,367행/5,470게임, calib 17,448행/304게임, val 17,699행/304게임, Blim 64팀 제외) |
| 추가 피처 | `integration.laya_search.matchup_features` — Gen 9 `dex_v2` 기반 6×6 유효 데미지 행렬, `is_walled`, 회복 고려 2HKO, 선공/스피드 우위, 기능적 도구·특성·기술 키트 플래그, 장판 진입 피해, 팀 커버리지 요약, 액티브 대결 전역 차이(원시 ID 임베딩 미사용) |
| 아키텍처·자원 | `StateValueNetV2` (`matchup_deepsets_v2`, exact antisymmetry `0.5*(f(s)-f(swap(s)))`, 온도 보정), **물리 GPU 0 전용**(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, GPU 2·3 미사용), 출력 `runs/model-training/EX-216/` |

## 결과

완료(`2026-11-24`, 물리 GPU 0 전용, `54,529` params, 전처리 `3.26s`, 학습 `~20s`, 단위·반대칭·메커니즘 테스트 `26/26` 통과, `EX-207`과 100% 동일 누수 통제 분할 `val 17,699행 / 304게임`).

### 1. 피처·정규화 절제 실험 요약 (동일 `val.npz`, 304경기)

- 정적 포켓몬별 22개 키트 플래그(`has_pivot`, `has_haz_set` 등)를 함께 넣으면(`all 60`) 5,470경기에서 팀 조합 지문화로 에폭 5~7 이후 과적합(`AUC 0.7413~0.7524`)이 발생했다.
- 반면 정적 키트 플래그를 빼고 **Gen 9 상성·테라·도구(`Air Balloon`/Choice/Boots/AV/LO 등)·특성(흡수·부유·`Multiscale`·`Unaware`·`Poison Heal` 등)·기술(회복·드레인·선공기·위력)이 물리 계산 내부에 모두 녹아든 15개 쌍별 매치업 상호작용 피처 + 12개 전역 매치업 차이**만 결합한 **`pair_only(38)` + `global(47)`**(`d_model=64, dropout=0.35, wd=0.10`)가 과적합 없이(`best_epoch=17, T=0.9282`) 최고 일반화 성능을 기록했다.

### 2. Held-out 최종 비교 (`n = 17,699`, 304 unseen games, Blim 64팀 제외)

| 모델 | LogLoss ↓ | Brier ↓ | **ROC-AUC ↑** | Acc ↑ | ECE ↓ | Early (`T1-10`) AUC | Mid (`T11-25`) AUC | **Late (`T26+`) AUC** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `evaluate.rs` (calibrated) | `0.61471` | `0.21304` | `0.72346` | `65.96%` | `0.0319` | `0.6092` | `0.7549` | `0.8168` |
| `EX-207` ($V_\phi$ v1, 순수 상태 23) | `0.59674` | `0.20626` | `0.73893` | `66.55%` | `0.0258` | `0.6213` | `0.7691` | `0.8283` |
| **`EX-216` ($V_\phi$ v2, 매치업 보강)** | **`0.58475`** (`-0.0120`) | **`0.20108`** | **`0.75362`** (**`+0.0147`**) | **`67.66%`** | **`0.0250`** | **`0.6267`** (`+0.0054`) | **`0.7841`** (`+0.0150`) | **`0.8529`** (**`+0.0246`**) |

- **`EX-207` 대비 개선**: 전체 `AUC +0.01469`, `LogLoss -0.01199`, `Acc +1.11%p` (초·중·종반 전 구간 개선, 특히 종반 `LogLoss 0.5084 → 0.4766`, `AUC 0.8283 → 0.8529`).
- **보정된 `evaluate.rs` 대비**: 전체 `AUC +0.03016`, `LogLoss -0.02996` (기존 `EX-207`의 격차를 약 2배 확대).

### 3. 실전 회귀 3종 진단 (`runs/model-training/EX-216/diagnostics.json`)

- **행동 간 변별력(`spread = max - min`)**: 전 사례에서 `27~54%` 확대 (`airballoon_T10` `0.0913→0.1406`, `drainingkiss_T4` `0.1272→0.1724`, `waterabsorb_T22` `0.0174→0.0253`).
- **`Air Balloon Gholdengo` T10·T11 (`freedomafter20yrs`)**:
  - `EX-207`은 `switch:5 (Darkrai)`·`switch:2 (Gholdengo)`를 모든 잔류 수 아래(`-0.049` on T10, `-0.088` on T11)로 낮게 평가했으나, **`EX-216`**은 `earthquake`/`extremespeed`를 대폭 하향하고 **`switch:5 (0.5010)`·`switch:2 (0.5005)`를 2·3위**로 끌어올렸다(T11에서는 `DD`와 `switch:5` 격차를 `-0.0876 → -0.0064`로 14배 축소).
  - 단, 1-ply 특성상 `Dragonite`의 잔여 6×6 스윕 잠재력 때문에 `DD`가 여전히 근소 1위(`+0.027` on T10, `+0.006` on T11)로 남으며, 이는 다수 턴 수읽기를 담당하는 **`MCTS 50k`**가 교대를 1위로 지목할 때 함께 작동해 해소된다.
- **`Water Absorb` T22 (`Xrlylyl`)**: `liquidation` 점수 하향(`0.9402→0.9314`, `liquidation:tera 0.9214 < switch:4 0.9243`), `Taunt+Water Absorb` 엔진 버그는 `search_2b_v2` 보정이 함께 처리.
- **`Draining Kiss` T4~6 (`sleepman610`)**: `Unaware Dondozo`가 1턴 교환에서는 `Earthquake`가 유리해 보이는 1-ply 한계는 남아 있어, 다수 턴 회복 루프는 `MCTS 50k`가 보완해야 함을 확인.

산출물: `runs/model-training/EX-216/{checkpoints/selected,selection.json,diagnostics.json}`.
