# EX-209 — 1-B 오프라인 경량 MCTS-5k 루트 Q 후보 재정렬 타깃 생성 및 v13 단일 모델 학습(GPU 0·1)

- 상태: Completed
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md)
- 관련 decision: [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-218](../decisions/D-218-laya-v13-input-bugfixes.md), [D-217](../decisions/D-217-laya-engine-value-rerank-training.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`EX-199/200`의 1턴 `evaluate.rs` 타깃을 **다중턴 경량 MCTS(`5,000 iters`) 루트 $Q$ 기반 후보 내부 재정렬 타깃**(+ `v13` 입력)으로 대체해 단일 forward 모델을 학습하면, held-out 다중턴 타깃 일치도와 후속 배틀([EX-210](EX-210-laya-mcts5k-q-rerank-1b-vs-foulplay-unlimited.md)) 성적이 `EX-200`보다 개선되는가? (`1-A` 2플라이 오프라인 타깃은 사용자 지시로 보류.)

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 출발 체크포인트 | `runs/model-training/EX-196/checkpoints/selected` (또는 `EX-200`, 상세 확정 후 동결) |
| 입력·타깃 | `v13` 입력, ~6만 `turn_action`·`forced_switch` 후보 결정에 `poke-engine` MCTS `5,000 iters` 루트 $Q$ 계산(합법 수 `restrict` 적용) → 후보 내부 softmax 재정렬 + 인간 앵커 + 상대예측 + 테라 지식 혼합 |
| 자원 | 추론(`infer`)·DDP 학습: **물리 GPU 0·1 전용**(`--nproc_per_node 2`, 유효 배치 유지 위해 `grad_accum=4`, GPU 2·3 미사용); MCTS 타깃 생성: CPU 48~64워커(`nice 19`, `mem-guard 40`, 배틀 비충돌 시) |
| 출력 | `datasets/generated/laya-mcts5k-q/v1/`, `runs/model-training/EX-209/checkpoints/selected` |

## 결과

- **전처리 완료 (`infer → mcts → targets → prepare`, `datasets/generated/laya-mcts5k-q/v1/`)**:
  - `infer` (GPU 0·1, 약 33분): `EX-196` 체크포인트로 2,535경기(train 2,200 + held-out 335) `158,034`결정 추론(오류 0).
  - `mcts` (CPU 16워커 `nice 19`, 약 67분): 2,535/2,535경기 `146,147`행 MCTS `5,000 iters` 루트 $Q$ 계산(오류 3건).
  - `targets` (`tau_q=0.03, near=0.15, max_candidates=4, rescue_gap=0.08`): 골드 타깃 **145,679행** (`train` **125,481행** / `heldout` **20,198행**, `skipped_few_cands=250`). `gold_argmax_changed` **40,195건 (27.6%)**, `forced_switch` **15,252건 (10.5%)**, `human_is_laya_argmax` `84,651` (58.1%), `human_is_gold_argmax` `77,812` (53.4%).
  - `prepare`: 인간 앵커 `150,000`행(`heldout` 335경기 제외) + 상대예측 앵커 `100,000`행(`gold_repeat=2`) 준비 완료.
- **학습 (`train`, GPU 0·1 DDP, 5.8시간 `20,918초`, `34,857`스텝, `peak 22.90 GiB/GPU`, `host RSS 4.62 GB`)**:
  - Validation NLL 곡선: `point-0` `1.2791` → `point-1` `1.3578` → `point-2` `1.3322` → `point-3` `1.3279` → **`point-4` `1.3208`** (`point-4` 선택, 보정 온도 `T=1.0628`, 보정 validation NLL `1.3094`).
  - *(학습 말미 `EX-209/selection.json`이 `data_mcts_1b` 게임 선택 파일과 이름 충돌해 `FileExistsError` 발생 — `checkpoints/selected`는 이미 저장 완료 상태였고 게임 선택 파일을 `game_selection.json`으로 이관 후 `train_v11` 최종화 블록으로 `selection.json`·`status.json` 완료, `data_mcts_1b.py` 코드도 `game_selection.json`으로 수정).*
- **오프라인 held-out 검증 (`heldout.jsonl` 335경기 2,000행 표본 + 테라 지식, 보고 전용 D-191)**:
  - **`EX-209` (1-B MCTS-5k Q)**: **`gold_CE 1.0751` · `KL 0.1779` · `gold top-1 80.15%` · 변경 턴(`n=519`) 일치 `38.92%` · `forced_switch`(`n=216`) 일치 `67.13%`**, 사람 일치 `57.45%`.
  - 비교 `EX-200` (1턴 평가): `gold_CE 1.1238` · `KL 0.2266` · `gold top-1 77.35%` · 변경 턴 `30.44%` · `forced_switch 62.04%`, 사람 일치 `57.60%`.
  - 비교 `EX-196` (출발점): `gold_CE 1.1536` · `KL 0.2564` · `gold top-1 74.05%` · 변경 턴 `0.00%` · `forced_switch 61.57%`, 사람 일치 `60.20%`.
  - **테라 지식 held-out**: **`heldout-A 96.33%` · `heldout-B 95.94%`** (보존 확인).
- **체크포인트**: `runs/model-training/EX-209/checkpoints/selected` (`EX-210` 단일 forward 배틀 평가 투입).
