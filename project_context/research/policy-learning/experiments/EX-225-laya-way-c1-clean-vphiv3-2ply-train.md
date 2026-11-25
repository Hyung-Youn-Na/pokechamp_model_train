# EX-225 — 방식 C-1 오염 제거판: EX-221 V_phi v3 + 2-ply 정화 교사 증류 학습 (GPU 0·1 DDP)

- 상태: Completed
- 생성일: 2026-11-24
- 완료일: 2026-11-25
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-248](../plans/EP-248-batch-b-waya-v2-ladder-wayc1-clean-wayb.md)
- 관련 decision: [D-224](../decisions/D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md), [D-223](../decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행 실험: [EX-218](EX-218-laya-way-c1-v14-walled-teacher50k-train.md)(조기 종료·오염 기록), [EX-221](EX-221-laya-state-value-v3-future-train.md)(`V_phi v3`), [EX-223](EX-223-laya-waya-v2-vphiv3-2ply-vs-foulplay.md)(Blim 128 `0.414` 검증)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`EX-218`의 캐시(`v14+walled_duel` 기본 분할·`EX-200` `infer-hard.jsonl`·`MCTS 50k` 28k 탐색 결과)를 재활용하고 오염 원인이었던 `EX-216 V_phi v2 1-ply`만 **`EX-221` 미래 지향 `V_phi v3` + 2-ply Top-K**로 재채점·정화한 뒤 `EX-196`에서 1에폭 GPU 0·1 DDP 학습했을 때, 오프라인 held-out에서 `EX-200`/`EX-209` 대비 정확도·`walled` 교정률·Tera 지식을 개선하면서 HP 회복 과대평가 오염 없이 건강한 회복률을 유지하는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 정화 교사 | `0.45 * Q_mcts50_adj + 0.55 * Q_vphi3_2ply` (`datasets/generated/laya-v14w-c1v3/v1/`, `23,576/25,000` train hard + `2,938/3,000` held-out hard 2-ply 커버, 고HP 회복·`Protect` rescue 차단) |
| 학습·자원 | `runs/model-training/EX-196/checkpoints/selected` → 1에폭(`36,419` steps) **물리 GPU 0·1 DDP** (`mem-guard 55`, GPU 2·3 미접촉) → GPU 0 오프라인 평가 |
| 산출물 | 체크포인트 `runs/model-training/EX-225/checkpoints/selected`, 평가 `runs/model-training/EX-225/evaluation/summary.json`, 데이터 감사 `datasets/generated/laya-v14w-c1v3/v1/manifest.json` |

## 결과 (2026-11-25 완료, 오프라인 보고 전용 — D-191)

### 1. 정화 데이터셋 HP 회복 오염 감사 (`manifest.json`)
- `HP ≥ 90% HEAL`: 교사 **`2.04%`** (인간 `4.08%` 이하)
- `HP 70–89% HEAL`: 교사 **`10.65%`** (인간 `11.27%` 이하)
- `HP 40–69% HEAL`: 교사 **`39.63%`** (`EX-218` 오염 `45.2%` 대비 `-5.6%p` 정화)
- `Protect` 전체: 교사 **`11.35%`** (인간 `18.26%` / Laya `22.27%` 이하)

### 2. Held-out 오프라인 평가 (`evaluation/summary.json`)
| 모델 | Hard `gold_kl` ↓ | Hard `gold_ce` ↓ | Hard `match_gold` ↑ | Hard `changed_match` (`n=1,480`) ↑ | Hard `walled_match` (`n=296`) ↑ | Gen-2k `gold_kl` ↓ | Gen-2k `changed_match` ↑ |
|---|---:|---:|---:|---:|---:|---:|---:|
| `EX-196` (출발점) | `0.4974` | `1.5256` | `31.97%` | `6.76%` | `72.97%` | `0.2517` | `1.91%` |
| `EX-200` (기준선) | `0.3996` | `1.4278` | `50.67%` | `0.00%` | `77.70%` | `0.2212` | `33.69%` |
| `EX-209` (`MCTS 5k`) | `0.3837` | `1.4118` | `53.50%` | `25.14%` | `79.73%` | `0.1813` | `45.55%` |
| **`EX-225` (Way C-1 Clean)** | **`0.3587`** | **`1.3869`** | **`55.70%`** | **`28.85%`** | **`81.08%`** | **`0.1775`** | **`47.03%`** |

- **Held-out 예측 HP 회복률 (`hard_50k_vphi3_2ply`, `n=837`)**: `HP ≥ 90%` **`4.51%`** (인간 `4.92%` 이하), `HP 70–89%` **`7.86%`** (인간 `8.73%` 이하), `HP 40–69%` `41.31%`, `HP < 40%` **`47.62%`** (위기 회복 보존). `general_2k` `HP ≥ 90%` **`1.20%`** (인간과 일치).
- **Tera 지식 보존**: `heldout-A` **`97.10%`**, `heldout-B` **`95.99%`**.
- **해석**: 오프라인 전 지표 최우수 및 회복 오염 해소 확인. 실전 강도 판정은 `EX-226` 완료 후 Blim 128 배틀 평가에서 확정(D-191).
