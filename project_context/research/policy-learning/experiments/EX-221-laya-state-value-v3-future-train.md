# EX-221 — 미래 영향력 반영 상태가치망 V_phi v3 데이터 구축 및 학습 (GPU 0)

- 상태: Completed
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-247](../plans/EP-247-vphi-v3-future-horizon-and-multiturn-search.md)
- 관련 decision: [D-223](../decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-216](EX-216-laya-state-value-v2-matchup-train.md) ($V_\phi$ v2: `val AUC 0.75362`, `LL 0.58475`, 종반 `AUC 0.85286`), [EX-207](EX-207-laya-state-value-2b-train.md) ($V_\phi$ v1: `val AUC 0.73893`, `LL 0.59674`), 보정 `evaluate.rs` (`AUC 0.72346`)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`EX-207`/`EX-216`과 동일한 누수 통제 분할(train 5,470 / calib 304 / val 304, Blim 64팀 제외) 위에 (1) **잔여 회복기 PP·직전 턴 `Protect`/회복 상태 피처**와 `Multiscale` `full_hp` 불연속 완화, (2) **미래 `t+3`, `t+5`, `t+10`턴 보드 유리도·5턴 모멘텀·3턴 후 상대 랭업 누적 보조 타깃**, (3) **인간 프로 기각/선택 기반 반사실적(Counterfactual) 회복·`Protect` 쌍대 순위 손실**을 결합해 학습한 $V_\phi$ v3가 정적 승률 예측 성능(`val AUC`/`LogLoss`)을 유지·개선하면서 반사실적 회복 과대평가 편향을 얼마나 교정하는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 데이터 분할 | `EX-207` 동일 게임 분할(`SEED=20261207`, Blim 64팀 제외) → `datasets/generated/laya-state-value/v3/` (`train/calib/val.npz` + `train_cf/val_cf.npz`) |
| 입력 피처 | `EX-216` `pair_only(38)+global(47)` + v3 동적 피처(개체별 `heal_pp_frac`, `min_pp_frac` + 진영별 `just_protected`, `just_healed`, `protect_active`, 정확한 제로섬 반대칭) |
| 학습 손실 | 주 손실 `BCE(z_win, win)` + 미래 보조 손실(`h_3`, `h_5`, `h_10`, `h_delta5`, `h_opp_boost3` SmoothL1) + 반사실적 순위 손실(`margin_ranking` on `s'_good > s'_bad_heal_or_protect`) |
| 자원·격리 | 추출 CPU `36w nice 19` (`foul-play` venv, `PYTHONHASHSEED=0`), 학습 **물리 GPU 0 단독**(`GPU-4f27dd5a-...`, GPU 2·3 미사용) |

## 결과

**완료 (`Completed`, 2026-11-24 09:49Z / 18:49 KST, 물리 GPU 0 단독)** — 선택 모델: **`v3_cf_06`** (`runs/model-training/EX-221/checkpoints/selected`, `arch=future_deepsets_v3`, `55,000` params, 정확한 제로섬 반대칭).

### 1. 데이터 구축 (`datasets/generated/laya-state-value/v3/`)
- `6,372`경기 추출(오류 `6`, Blim 64팀 `291`경기·무승부 `3`경기 제외) → `EX-207`/`EX-216`과 동일한 게임 분할(`SEED=20261207`):
  - 상태 행: `train 321,367` / `calib 17,448` / `val 17,699` (각 상태에 미래 궤적 `fut_adv_3`, `fut_adv_5`, `fut_adv_10`, `fut_delta_5`, `fut_boost_diff_3` 포함).
  - 반사실적(Counterfactual) 회복·`Protect` 쌍: `train_cf 39,415` / `val_cf 2,150` (게임 완전 분리, `reject_heal 1,493`, `reject_protect 520`, `accept_heal_low 137`).

### 2. 핵심 절제 발견 (지름길 차단) 및 최종 성능 비교
- **1차 절제 교훈**: `just_used_heal`/`just_used_protect` 입력 채널은 강한 반사실 손실(`lam_cf=0.15~0.30`)에서 단순 지름길로 작동해 `accept_heal_low`를 `74.5% → 21~36%`로 훼손하고 `val AUC`를 `-0.017~-0.029` 떨어뜨렸다.
- **최종 Clean v3 (`39+47`, `EX-216` 피처 + `heal_pp_frac` 전용, `accept_heal_low` 가중 `4×`, 미래 5헤드 `lam_fut=0.35`)**: 지름길 입력 없이 **정당한 저HP 회복(`accept_heal_low`)을 `73.7%`로 보존**하면서 **고·중HP 회복 과대평가 편향을 대폭 교정**했다.

| 모델 | `val LL` | `val AUC` | `Late T26+ AUC` | `val ECE` | `val_cf 전체` | `reject_heal ≥70%` | `reject_heal 40–69%` | `reject_protect` | `accept_heal ≤65%` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `EX-216` $V_\phi$ v2 (기준) | `0.58475` | `0.75362` | `0.85286` | `0.02502` | `60.37%` | `64.10%` | `38.34%` (`-0.0219`) | `57.50%` | `74.45%` |
| `EX-221 v3_future` (`lam_cf=0`) | `0.58800` | `0.74963` | `0.84204` | — | `61.81%` | `66.91%` | `36.79%` | `56.92%` | `75.91%` |
| `EX-221 v3_cf_03` (`lam_cf=0.03`) | `0.58942` | `0.74935` | `0.83695` | — | `64.84%` | `70.91%` | `41.45%` | `59.04%` | `72.99%` |
| **`EX-221 v3_cf_06` (선택)** | **`0.58985`** | **`0.74820`** | **`0.83892`** | **`0.02381`** | **`65.26%` (`+4.9%p`)** | **`70.99%` (`+6.9%p`)** | **`45.60%` (`+7.3%p`, `-0.0018`)** | **`58.27%`** | **`73.72%`** |
| `EX-221 v3_cf_10` (`lam_cf=0.10`) | `0.59116` | `0.74671` | `0.83677` | — | `67.72%` (`+7.4%p`) | `73.48%` (`+9.4%p`) | `48.19%` (`+9.9%p`) | `61.73%` | `72.26%` |

- `v3_cf_06`은 `EX-207`(`AUC 0.73893`) 대비 `+0.00927`, 보정 `evaluate.rs`(`0.72346`) 대비 `+0.02474`의 높은 정적 판별력과 더 나은 캘리브레이션(`ECE 0.02381`)을 유지하면서, `EX-216`의 중HP 회복 음수 편향(`mean_diff -0.0219 → -0.0018`)을 **12배 축소**했다. ([D-191](../decisions/D-191-no-offline-battle-gate.md) 보고 전용)
