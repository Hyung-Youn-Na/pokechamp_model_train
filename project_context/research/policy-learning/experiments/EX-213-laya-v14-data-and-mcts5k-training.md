# EX-213 — v14 회복·흡수 인지 입력 렌더러 데이터 생성 및 MCTS-5k Q 단일 모델 DDP 학습(GPU 0·1)

- 상태: Stopped
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-244](../plans/EP-244-laya-search-2bv2-and-v14-training.md)
- 관련 decision: [D-220](../decisions/D-220-laya-recovery-matchup-2bv2-and-v14.md), [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`v13` 위에 회복·흡수 결손 3건(① 회복 고려 거짓 `2HKO` 제거, ② `opp heals:`에 드레인 기술·흡수 특성 추가, ③ 흡수 특성 공격에 `; heals opp 25%` / `; boosts opp` 명시)을 보강한 **`v14` 렌더러**와 `foe_options_clean`(PP 괄호 수정)으로 기존 `EX-209`와 동일한 MCTS-5k Q 골드(`125k`×2) + 인간 앵커(`150k`) + 상대예측 앵커(`100k`) + 테라 지식을 재렌더링·학습하면, held-out MCTS-5k Q 일치도·상대예측 NLL·테라 지식 보존과 후속 배틀([EX-214](EX-214-laya-v14-search2bv2-vs-foulplay-unlimited.md)) 성적이 개선되는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 출발 체크포인트 | `runs/model-training/EX-196/checkpoints/selected` (`EX-209`와 동일 출발점, 통제 비교) |
| 입력·타깃 | `integration.laya_v14.render_v14` (`v13` + `recoverko,drainheal,absorbheal`), `EX-209`와 동일한 2,200 train / 335 held-out MCTS-5k Q 골드 타깃(`125k`×2) + 인간 앵커(`150k`) + `foe_options_clean` 상대예측(`100k`) + 테라 지식 |
| 자원·출력 | 재렌더링: CPU `16워커 nice 19, mem-guard 30`(`EX-212` 병행); 학습: **물리 GPU 0·1 전용 DDP**(`--nproc_per_node 2, grad_accum=4, mem-guard 55`, GPU 2·3 미사용). 출력: `datasets/generated/laya-v14-mcts5k-q/v1/`, `runs/model-training/EX-213/checkpoints/selected` |

## 결과

사용자 지시(2026-11-24 11:12 KST, `strategy.duel()` 전 공격기 무효 시 `duel: lose` 누락 등 렌더러 입력 버그를 반영한 뒤 재실행하기 위해 조기 종료)로 **DDP 학습 `step 4,500 / 34,857` (약 13%) 시점**에 정상 중단했다(`Stopped`, 물리 GPU 0·1 유휴 `0 MiB` 반환).

- **`v14` 데이터 재렌더링 완료 통계** (`datasets/generated/laya-v14-mcts5k-q/v1/manifest.json`): `train_gold 125,481`, `heldout_gold 20,198`, `anchor_train 150,000`, `anchor_val 1,024`, `foe 100,000`, 토큰 한도 제외 **`0`**(`fits 335,998/335,998`). `recoverko` 거짓 `2HKO` 제거 **`23,673`건**, `foe_options_clean` PP 손상 행 복구 **`6,766`건**, `absorb_heal 1,636`, `absorb_boost 15`, `heals_line 195,193`.
- **학습 중단 지점**: `point-0` (`EX-196` 초기 상태 `v14` val raw NLL `1.2842`, shipped `1.2800`, acc `51.86%`) 후 `step 4,500 / 34,857`에서 중단(`point-1` 저장 전).
