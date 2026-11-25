# EX-223 — 방식 A v2(미래인지 V_phi v3 + 2-ply Top-K + MCTS 50k + 회복/Protect 가드레일) 대 foul-play, Blim 128경기

- 상태: Completed
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-247](../plans/EP-247-vphi-v3-future-horizon-and-multiturn-search.md)
- 관련 decision: [D-223](../decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행 실험: [EX-221](EX-221-laya-state-value-v3-future-train.md), [EX-222](EX-222-multiturn-2ply-waya-v2-ab.md)
- 비교 대상: [EX-217](EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md) (방식 A v1 + $V_\phi$ v2 1-ply, 50승 78패 `0.391 [0.312, 0.461]`), [EX-208](EX-208-laya-search-2b-vs-foulplay-unlimited.md) (`2-B v1`, 52승 76패 `0.406 [0.312, 0.500]`), [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md) (`0.375`), [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) (`0.331`)
- 기준 연구선: `research/model-training`

## 질문 및 목적

사용자 지시(2026-11-24 17:44 KST: "고친 상태함수로 기존 상태함수를 대체하여 foulplay 테스트도 이어서 진행해주세요."): [EX-217](EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md)의 `EX-216` $V_\phi$ v2 (1-ply) + `Way A v1`을 **[EX-221](EX-221-laya-state-value-v3-future-train.md) 미래 영향력 반영 $V_\phi$ v3 + 2-ply Top-K 기대미니맥스 탐색 + `Way A v2` 회복/`Protect` 가드레일**로 대체해 동일 Blim 128경기 일정(`EX-174` 64팀 × 2선후공, 시간 제한 없음 `foul-play`)으로 평가했을 때, 같은 슬롯 승률·고/중HP 회복률·실패 기술률·Veto 품질이 어떻게 변하는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 정책·입력 | `EX-200` 체크포인트 + `render_v13` + `walled_duel` + `foe_options_clean` (`EX-217`과 동일 본체, 상태가치망·탐색·가드레일만 통제 교체) |
| 상태가치·탐색 | `EX-221` $V_\phi$ v3 (`checkpoints/selected`) + `2-ply Top-K` (`--two-ply`, `search_multiturn.py`) + `MCTS 50,000 iterations` + `--way-a-v2` (`way_a_v2.py`) |
| 상대·일정 | `foul-play` 무제한 Blim 64팀 × 2선후공 = 128경기 (`battle_way_a_v2.py`, `scripts/laya-way-a-v2-ep247`) |
| 자원·산출물 | **물리 GPU 0 단독**(`GPU-4f27dd5a-...`, GPU 2·3 미접촉), 봉인 `runs/model-training/EX-223`, 뷰어 `exports/battle_viewers/ex223/index.html` ([C-047](../../../CONTRACTS.md#c-047-viewer-export)) |

## 결과

**완료·봉인 (`Completed`, 2026-11-24 14:52Z / 23:52 KST, 물리 GPU 0 단독)** — `128/128` 정상 완료(`failed=0`, `incomplete=0`, `verify_seal == []`, 서빙 오류 `0`), **53승 0무 75패 · 평균 점수 `0.414 [0.328, 0.492]` (Blim 128 역대 최고점)**.

- **뷰어 ([C-047](../../../CONTRACTS.md#c-047-viewer-export))**: [ex223/index.html](../../../../exports/battle_viewers/ex223/index.html) (`128`경기, `7,907`결정), 보고서 `runs/model-training/EX-223/report.md`.
- **팀 유형별 성적**: `offense` **`0.529`** (`n=34`, 18승 16패), `weather` `0.400` (`n=20`), `balance` `0.386` (`n=70`), `defense` `0.000` (`n=4`).
- **지연·기술 실패율**: `waya_v2_2ply` `p50 4.689s` / `p95 8.288s` (`2-ply` 평균 `114.8` 리프), `foul-play` `p50 7.235s` (`7,725`결정, 테라 `117`경기). 실패 기술률 **`4.95%`** (`268/5,417`, `EX-208 6.17%`·`EX-217 5.72%` 대비 최저).

### 1. 같은 슬롯 기준선 비교 ([D-191](../decisions/D-191-no-offline-battle-gate.md) 보고 전용)
| 비교 기준선 | 공통 슬롯 | `EX-223` | 기준선 | 같은 슬롯 차이 (95% CI) | 개선/악화/동일 |
|---|---:|---:|---:|---|---|
| [EX-217](EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md) (`Way A v1 + EX-216 V_phi v2 1-ply`) | 128 | `0.414` | `0.391` | **`+0.023 [-0.070, +0.117]`** | `26 / 23 / 79` |
| [EX-208](EX-208-laya-search-2b-vs-foulplay-unlimited.md) (`2-B v1`, 종전 최고) | 128 | `0.414` | `0.406` | **`+0.008 [-0.102, +0.109]`** | `22 / 21 / 85` |
| [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md) (`EX-200` v12 단일) | 128 | `0.414` | `0.375` | **`+0.039 [-0.063, +0.141]`** | `28 / 23 / 77` |
| [EX-206](EX-206-laya-search-2a-vs-foulplay-unlimited.md) (`2-A` MCTS 5k 단독) | 128 | `0.414` | `0.336` | **`+0.078 [-0.023, +0.188]`** | `28 / 18 / 82` |
| [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) (`EX-200` v13 단일) | 127 | `0.417` | `0.315` | **`+0.102 [+0.000, +0.205]`** | `31 / 18 / 78` |
| [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) (`v10rt` 기준) | 127 | `0.417` | `0.331` | **`+0.087 [-0.016, +0.188]`** | `32 / 21 / 74` |

*(모든 95% 신뢰구간이 0을 포함·경계에 걸치므로 통계적 입증을 주장하지 않고 보고 전용으로 기록한다.)*

### 2. 핵심 검증: 실전 128경기 HP 회복 · `Protect` 편향 교정 (`EX-217` vs `EX-223`)
- **Way A v2 텔레메트리** (`7,791`결정, 오류 `0`, `walled 176`턴): Laya 1순위 유지 **`87.8%`** (`6,838`), 오버라이드 `12.2%` (`953`: `unanimous_veto 266`, `duel_lose_vphi 162`, `duel_lose_mcts 143`, `severe_mcts 105`, `vphi_blunder 98`, `forced_mcts 75`, `consensus 50`, `walled 31`, `endgame 21`, `consec_protect 2`).
- **순수 회복기 (`n=3,065`턴)**:
  - `V_phi` 단독 회복기 1순위 비율: `EX-217 25.5%` → **`EX-223 20.3%` (`-5.2%p`)** (`≥90%`: `7.5%→4.8%`, `70–89%`: `23.3%→18.3%`, `40–69%`: `46.3%→38.5%`, `<40%`: `55.0%→39.0%`).
  - **`vphi_blunder_veto` 회복 방향 (INTO : AWAY)**: `EX-217` **`34 : 3` (`11.3배` 극단 편향)** → `EX-223` **`6 : 7` (`0.86배`, 완전 균형 해소)**.
  - 전체 Veto 회복 방향 (INTO : AWAY): `EX-217 90 : 43 (2.1배)` → **`EX-223 70 : 54 (1.3배)`**.
- **`Protect` (`n=580`턴)**:
  - `V_phi` 단독 풀피(`≥90%`) `Protect` 1순위: `EX-217 21.6%` → **`EX-223 5.0%` (`4.3배` 감소)**, 전체 `19.8% → 15.3%`.
  - `walled_veto`의 `Protect` 덮어쓰기: **`0건`** (완전 차단), `Protect` Veto 방향 `INTO 6 : AWAY 12`.
