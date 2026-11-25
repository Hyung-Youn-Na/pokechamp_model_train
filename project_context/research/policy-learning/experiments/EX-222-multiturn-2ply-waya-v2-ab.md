# EX-222 — 다수 턴 2-ply Top-K 탐색기 + Way A v2 가드레일 오프라인 A/B 진단

- 상태: Completed
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-247](../plans/EP-247-vphi-v3-future-horizon-and-multiturn-search.md)
- 관련 decision: [D-223](../decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행 실험: [EX-221](EX-221-laya-state-value-v3-future-train.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

[EX-221](EX-221-laya-state-value-v3-future-train.md) $V_\phi$ v3에 **2-ply Top-K 기대미니맥스 탐색(`search_multiturn.py`)**과 **`Way A v2` 가드레일(`way_a_v2.py`)**을 결합했을 때, 기존 `EX-216` 1-ply + `Way A v1` 대비 (1) [EX-220](EX-220-laya-waya-mcts50k-ladder.md) 4대 실전 실패 장면(`073833` 96%/100% HP `Roost`, `074335` 8연속 `Roost`, `072713` 15연속 `Protect`, `075028` 랭업 앞 `Roost`/`Protect`), (2) `EX-217` Blim / `EX-218` held-out 고·중HP 회복률(`HP ≥ 70%`, `40–69%`) 및 상대 랭업 허용률, (3) 턴당 추론 지연(GPU 0 / CPU)이 어떻게 변하는가?

## 조건 및 변수

- `EX-221` 학습 완료 직후 물리 GPU 0(및 CPU 지연 측정)에서 비침습 오프라인 A/B 스크립트(`integration/laya_search/eval_ab_v3.py`)로 비교 실행.
- 결과 보고 후 후속 Blim 128 배틀 또는 Way C/B 재가동 여부를 사용자 확인으로 결정한다.

## 결과

**완료 (`Completed`, 2026-11-24 10:25Z / 19:25 KST, 물리 GPU 0 단독)** — `runs/model-training/EX-222/{ab_summary.json,ex220_replay_audit.json}`.

### 1. Testbed A — `EX-220` 4대 실전 실패 장면 Before / After
- **`073833` (`Dragonite` vs `1% Garchomp`)**: T20~T24 `5/5`턴 전부 `V_phi v2 (1-ply)`가 `Roost`를 1순위로 찍던 현상이 **`EX-221 V_phi v3 (2-ply)`에서 `Earthquake`/`Extreme Speed`로 교정**되었고, T23 `96% HP` `vphi_blunder_veto -> Roost`가 완전히 제거됨(`Extreme Speed` 유지).
- **`074335` (`Dragonite` 8연속 `Roost` vs `Araquanid Lunge`)**: 기존 `W1`이 8턴 연속 `Roost`에 갇혔던 장면에서 **`W2 + V3_2p`가 T4–T5 `Dragon Dance`, T7–T11 `switch:6 (Zamazenta)`로 즉시 탈출**(`unanimous_veto`).
- **`072713` (`Gliscor` 15연속 `Protect` vs `+6 Corviknight`)**: T22에서 기존 `walled_veto`가 Laya의 `Spikes`를 `Protect`로 덮어쓰던 결함이 제거되어 `Spikes`를 정상 유지.
- **`075028` (`Dragonite`/`Gliscor` vs `Moltres-Galar` 랭업)**: T5 `Dragon Dance`, T7 `Extreme Speed:tera`(2-ply 교정), T18 연속 `Protect` 실패 턴 → `switch:6` 탈출(`consec_protect_veto`).

### 2. Testbed B — `EX-217` Blim 240턴 층화 A/B (순수 회복 `n=200`, `Protect` `n=40`)
| 회복기 HP 구간 | `n` | Laya | `MCTS 50k` | `EX-216 V2 (1-ply)` | **`EX-221 V3 (1-ply)`** | **`EX-221 V3 (2-ply)`** | `Final W1` → **`W2+V3_2p`** | Veto (into/away) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **전체 (`HEAL`)** | 200 | `28.0%` | `35.0%` | `34.5%` | **`27.5%`** | **`27.5%` (`-7.0%p`)** | `32.0%` → **`31.0%`** | `11/3` → **`11/5`** |
| **≥ 90% (풀피)** | 50 | `4.0%` | `12.0%` | `8.0%` | **`2.0%`** | **`2.0%` (4배 감소)** | `8.0%` → **`6.0%`** | `2/0` → **`1/0`** |
| **70–89% (고HP)** | 50 | `6.0%` | `22.0%` | `24.0%` | **`16.0%`** | **`18.0%` (`-6.0%p`)** | `12.0%` → **`10.0%`** | `3/0` → **`2/0`** |
| **40–69% (중HP)** | 50 | `54.0%` | `50.0%` | `42.0%` | `40.0%` | **`38.0%` (`-4.0%p`)** | `54.0%` → `54.0%` | `3/3` → **`4/4`** |
| **< 40% (저HP)** | 50 | `48.0%` | `56.0%` | `64.0%` | `52.0%` | **`52.0%`** | `54.0%` → `54.0%` | `3/0` → `4/1` |

- `Protect` (`n=40`): `HP ≥ 90%`에서 `V2_1p 35.3%` → `V3_2p 29.4%`, `Final W2` `0.0%`.
- **2-ply 지연 시간**: `mean 432.0 ms`, `p50 424.3 ms`, `p95 631.8 ms` (HTTP 경유 기준; `MCTS 50k` 대비 ~11% 수준으로 충분히 실용적). ([D-191](../decisions/D-191-no-offline-battle-gate.md) 보고 전용)
