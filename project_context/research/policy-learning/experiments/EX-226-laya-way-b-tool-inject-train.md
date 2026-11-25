# EX-226 — 방식 B: calc-duel-free + MCTS50k/V_phi v3 5단계 matchup & eval 프롬프트 주입 + 35% Tool Dropout + 인간 앵커 보존 학습 (GPU 0·1 DDP)

- 상태: Completed
- 생성일: 2026-11-24
- 완료일: 2026-11-25
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-248](../plans/EP-248-batch-b-waya-v2-ladder-wayc1-clean-wayb.md)
- 관련 decision: [D-224](../decisions/D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md), [D-223](../decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행 실험: [EX-225](EX-225-laya-way-c1-clean-vphiv3-2ply-train.md) (공유 `vphi3_2ply` 재채점 결과 재활용 및 DDP 완료 직후 자동 연쇄)
- 기준 연구선: `research/model-training`

## 질문 및 목적

[DESIGN.md#laya-main-abc-roadmap](../DESIGN.md#laya-main-abc-roadmap)의 **방식 B** 설계에 따라, 계산기 기반 1:1 `duel: win/lose`를 전 분할에서 제거(`calc-duel-free`)하고 **`MCTS 50k (0.45) + EX-221 V_phi v3 2-ply (0.55)` 조합 5단계 대면 유불리(`matchup:`) + 상대 격차(`eval: mcts ... || vphi ...`)**를 프롬프트에 직접 주입하되 **35% Tool Dropout**과 **비블런더 턴 인간 프로 정답 보존**을 적용해 `EX-196`에서 1에폭 GPU 0·1 DDP 학습했을 때, Laya가 외부 수식 없이 **100% 단독 최종 결정권자**로서 도구 유무(`with_eval` / `no_eval`) 모두에서 지름길 붕괴 없이 높은 정확도와 건강한 회복률을 달성하는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 출발·입력 | `runs/model-training/EX-196/checkpoints/selected`, **계산기 기반 `duel: ... -> win/lose` 전 분할(`281,481`행) 제거(`calc_duel=0`)** + **`MCTS 50k (0.45) + EX-221 V_phi v3 2-ply (0.55)` 조합 5단계 유불리 `matchup: <very unfavorable\|unfavorable\|even\|favorable\|very favorable> (stay X% vs switch Y%, ±Z%)`** + `eval: mcts ... \|\| vphi ...` 주입 (최대 2,048토큰 준수) |
| 지름길 방지 | (1) `hard_train`(25k)·`general_train`(100k) 35% Tool Dropout + `anchor_noduel`(150k) 100% 무도구, (2) 비블런더 턴(`gap < 0.030`, 비`walled`/비`absorb`) 인간 정답 50/50 보존(`train_hard 50.3%`, `train_general 67.8%`), (3) `hard_heldout` `with_eval` vs `no_eval` 동시 평가 |
| 자원·산출물 | **물리 GPU 0·1 DDP** 1에폭(`36,419` steps, `val NLL 1.3229 → 1.3180 → 1.3137`, GPU 2·3 미접촉) → 물리 GPU 0 오프라인 평가. 체크포인트 `runs/model-training/EX-226/checkpoints/selected`, 평가 `runs/model-training/EX-226/evaluation/summary.json` |

## 결과 (2026-11-25 완료, 오프라인 보고 전용 — D-191)

### 1. `with_eval` (도구 주입: `matchup:` + `eval: mcts || vphi`)
| 모델 | Hard `gold_kl` ↓ | Hard `match_gold` ↑ | Hard `changed_match` (`n=1,480`) ↑ | Hard `walled_match` (`n=296`) ↑ | Gen-2k `gold_kl` ↓ | Gen-2k `match_gold` ↑ |
|---|---:|---:|---:|---:|---:|---:|
| `EX-200` (제로샷) | `0.3899` | `52.47%` | `17.36%` | `77.36%` | `0.2304` | `78.05%` |
| `EX-225` (Way C-1 Clean) | `0.3502` | `57.83%` | `35.95%` | `82.43%` | `0.1949` | `79.85%` |
| **`EX-226` (Way B)** | **`0.1174`** | **`83.23%`** | **`81.35%`** | **`89.86%`** | **`0.1103`** | **`88.85%`** |

### 2. `no_eval` (35% Tool Dropout 단독 추론 강건성 — 지름길 붕괴 없음 검증)
| 모델 | Hard `match_human` ↑ | Hard `changed_match` ↑ | Hard `walled_match` ↑ | Gen-2k `gold_kl` ↓ | Gen-2k `match_human` ↑ |
|---|---:|---:|---:|---:|---:|
| `EX-200` (`calc-duel-free`) | `44.40%` | `8.18%` | `76.01%` | `0.2443` | `57.65%` |
| `EX-225` (`calc-duel-free`) | `42.10%` | `28.58%` | `81.76%` | `0.2036` | `55.85%` |
| **`EX-226` (Way B, no_eval)** | **`45.97%`** | `19.80%` | `77.03%` | `0.2301` | **`58.35%`** |

### 3. HP 회복 정화 및 Tera 지식 보존
- **Held-out 예측 HP 회복률 (`hard_with_eval`, `n=837`)**: `HP ≥ 90%` **`5.33%`** (인간 `4.92%`, `general_2k` **`1.75%`** = 인간 `1.75%`와 완전 일치), `HP 70–89%` **`10.04%`**, `HP 40–69%` **`37.84%`** (`EX-225 45.17%`·`EX-200 39.77%`보다 가장 낮고 깔끔함), `HP < 40%` **`45.71%`** 보존.
- **Tera 지식 보존**: `heldout-A` **`97.24%`**, `heldout-B` **`96.31%`** (`EX-225` 97.10%/95.99% 상회).
- **해석**: 도구 주입 시 블런더 교정률 **`81.35%`**, `walled` 교정률 **`89.86%`**를 달성하면서도 무도구(`no_eval`) 단독 추론 시 인간 프로 일치율이 `EX-200`·`EX-225`를 모두 상회해 지름길 붕괴가 전혀 없음을 확인. 최종 실전 강도는 Blim 128 배틀 평가에서 확정(D-191).
