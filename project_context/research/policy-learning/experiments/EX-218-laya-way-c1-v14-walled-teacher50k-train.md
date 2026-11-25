# EX-218 — 방식 C-1: v14+walled_duel 데이터·Hard-Example MCTS 50k + EX-216 V_phi v2 교사 타깃 생성 및 DDP 학습 (GPU 0·1)

- 상태: Stopped
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-246](../plans/EP-246-laya-way-c1-v14-walled-teacher50k-distill.md)
- 관련 decision: [D-222](../decisions/D-222-laya-way-c1-v14-walled-teacher50k.md), [D-221](../decisions/D-221-laya-main-waya-mcts50k-vphi-v2.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-209](EX-209-laya-mcts5k-q-rerank-1b-train.md) (`v13` + MCTS 5k, held-out `gold_CE 1.0751`, `top-1 80.15%`, Tera `A 96.33% / B 95.94%`), `EX-200`, `EX-196`
- 기준 연구선: `research/model-training`

## 질문 및 목적

`v14+walled_duel`(회복·드레인·흡수·전 공격기 무효 `duel: lose`) 입력 위에 **Hard-Example(`~25k` 학습 + `~3k` held-out: 전체 `walled`/`absorb` + `duel: lose`/`heals`/종반/불일치 상위)에 대해 `MCTS 50k + EX-216 V_phi v2` 결합 교사 타깃**을 생성하고, 일반 MCTS-5k 골드·인간 앵커·`foe_options_clean`·테라 지식과 함께 `EX-196`에서 1에폭 DDP 학습했을 때, Laya 본체의 오프라인 교사 일치도(일반·Hard 50k)·테라 지식 및 후속 배틀([EX-219](EX-219-laya-way-c1-vs-foulplay-unlimited.md)) 성적이 얼마나 개선되는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 출발 체크포인트 | `runs/model-training/EX-196/checkpoints/selected` (`EX-209`와 동일 출발점, 통제 비교) |
| 입력 렌더러 | `render_v14` + `way_a.install_walled_duel()` (`v14+walled_duel`, `laya-v14-mcts5k-q/v1`에서 `walled` 후보 행 증분 정밀 재렌더링) |
| Hard-Example 교사 | 학습 `25,000`턴 + held-out `3,000`턴: `EX-200` `p`/`foe` (GPU 1) + `MCTS 50,000 iterations` + `expand_turn1_features_v2` (CPU `28w nice 19`) + `EX-216` $V_\phi$ v2 (GPU 1) → `Q_teacher = 0.55*Q_mcts50k_adj + 0.45*Q_vphi2` (`tau=0.025`, `rescue≥0.06`·`walled≥0.015` 자동 승격) |
| 학습 혼합 | Hard 50k+V_phi2 골드(`~25k` ×3) + 일반 MCTS-5k 골드(`~100k` ×2) + 인간 앵커(`150k`) + `foe_options_clean`(`100k`) + 테라 지식 |
| 자원·일정 | 데이터·교사: CPU `nice 19` + **물리 GPU 1 전용**(`EX-217`과 병행); DDP 학습: `EX-217` 종료·GPU 0 유휴 확인 후 **물리 GPU 0·1 전용**(`mem-guard 55`, GPU 2·3 미사용) |

## 결과

**사용자 지시로 조기 종료 (`Stopped`, 2026-11-24 08:23Z / 17:23 KST, DDP `step 7,500 / 36,419`, 약 20.6%)** — 물리 GPU 0·1 유휴 반환 (`0 MiB`).

### 조기 종료(실패) 원인 — 교사 타깃의 HP 회복 과대평가 오염

`EX-218`은 별도의 가치함수 $V$를 새로 학습하지 않고, [EX-216](EX-216-laya-state-value-v2-matchup-train.md) $V_\phi$ v2를 고정 교사로 사용하여 `Q_teacher = 0.55*Q_mcts50k_adj + 0.45*Q_vphi2`로 `Hard 25k` 타깃(`datasets/generated/laya-v14w-c1/v1/hard_train.jsonl`, 학습 시 `×3` 가중)을 생성했다. [EX-220](EX-220-laya-waya-mcts50k-ladder.md) 실전 진단 과정에서 `EX-216` $V_\phi$ v2 + `MCTS 50k` 결합 교사의 **HP 회복 과대평가 편향**이 `EX-218` 학습 타깃에도 직접 유입된 것이 확인되어 학습을 중단했다.

1. **`hard_train.jsonl` 순수 HP 회복기 (`Roost`/`Recover`/`Rest` 등, 가능 턴 `6,456 / 25,000`) 분석**:
   - **전체**: 인간 프로(`Human`) `14.8%` (`957`) / `EX-200` Laya `13.5%` (`870`) → **`EX-218` 교사 `20.6%` (`1,329`, 인간 대비 `+5.8%p`, Laya→교사 뒤집기: 회복으로 `977`건 vs 회복 취소 `518`건 = `1.89배` 순 편향)**.
   - **HP 구간별 교사 회복률 vs 인간 프로**:
     - `≥ 90%` (`n=2,313`): 인간 `4.1%` / Laya `2.1%` / 교사 `2.4%` (풀피 폭주는 KL·합산으로 억제됨)
     - `70–89%` (`n=1,755`): 인간 `11.2%` / Laya `9.1%` / 교사 `12.9%` (`+1.7%p`)
     - **`40–69%` (`n=1,705`)**: 인간 `27.7%` / Laya `27.3%` → **교사 `45.2%` (`+17.5%p` 급등, 회복으로 `562` vs 취소 `258`)**
     - **`< 40%` (`n=683`)**: 인간 `28.1%` / Laya `28.6%` → **교사 `40.4%` (`+12.3%p` 급등, 회복으로 `187` vs 취소 `106`)**
2. **참고 (`Protect`, 가능 턴 `2,847`)**: `EX-218` 교사는 `Protect` 남발을 오히려 줄였다(Laya `22.8%` / 인간 `18.3%` → 교사 `15.8%`, 취소 `437` vs 추가 `239`).
3. **근본 원인**:
   - `EX-216` $V_\phi$ v2의 **1-ply 추론 근시안성**(즉시 `+50% HP` / `full_hp >= 0.999` `Multiscale` 복구 보상 대비 2~5턴 뒤 상대 랭업·해저드·템포 상실 미반영, [featurize.py](../../../../integration/laya_search/featurize.py)의 남은 PP·연속 `Protect` 카운터 누락, 반사실적 음수 학습 부재).
   - `MCTS 50k` (`poke-engine` `evaluate.rs`)의 현재 HP 비율 과가중이 중·저HP 구간에서 $V_\phi$ v2와 같은 방향으로 겹침.
4. **보존된 산출물**: `datasets/generated/laya-v14w-c1/v1/`(`v14+walled_duel` `3,400`행 업그레이드, `hard_train 25k` / `hard_heldout 3k`) 및 `runs/model-training/EX-218/status.json`(`stage: stopped`)은 사후 분석·재활용 근거로 보존한다. 후속 증류는 미래 영향력을 반영한 가치함수($V_\phi$ v3) 및 다수 턴(2-ply/PUCT) 탐색 교정 후 새 EX로 진행한다.
