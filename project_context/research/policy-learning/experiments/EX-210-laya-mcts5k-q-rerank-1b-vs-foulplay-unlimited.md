# EX-210 — 1-B 오프라인 MCTS-5k Q 재정렬 학습 모델(EX-209, v13 단일 forward) 대 foul-play, Blim 128경기(시간 제한 없음)

- 상태: Completed
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md)
- 관련 decision: [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

[EX-209](EX-209-laya-mcts5k-q-rerank-1b-train.md)에서 경량 MCTS(`5,000 iters`) 루트 $Q$ 후보 재정렬 타깃과 `v13` 입력으로 학습한 단일 forward 모델이, 탐색 없이도 [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) 및 [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md) 대비 foul-play Blim 128경기 점수를 높이는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 체크포인트 | `runs/model-training/EX-209/checkpoints/selected` (`v13` 서빙, 단일 forward argmax) |
| 통제 입력 | EX-174 봉인 Blim 128슬롯, foul-play 3,000ms × 병렬 4, 시간·턴·결정 수 제한 해제(`actor_unlimited`) |
| 자원·출력 | CPU 서빙(또는 GPU 0 전용, GPU 2·3 미사용), 포트 `8100-8103`, `runs/model-training/EX-210`, 뷰어 `exports/battle_viewers/ex210/`([C-047](../../../CONTRACTS.md#c-047-viewer-export)) |
| 같은 슬롯 기준선 | 주: [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md), 보조: [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md)(0.375), [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)(0.331) |

## 결과

- **종료 상태**: **96 / 128 정상 완료** (`completed: 96, failed: 1, incomplete: 0, invalid: 0, unattempted: 31`, 감사 통과 **97/97**, `verify_seal`: 2,416개 파일 불일치 `[]`).
  - **중단 사유 (`phase_halt`, `fp-b20-s1-a`, `observed_turn: 499`, `audit_passed: true`)**: [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md)의 `fp-b20-s2-a`와 동일한 스톨 대진에서 500턴 도달 시 Showdown의 `|bigerror|You will auto-tie...` 경고를 `pokechamp` 클라이언트가 `ValueError("Showdown rejected battle action")`으로 오인해 `phase_halt` 발생(모델 결함이 아닌 `actor_unlimited` 하네스 500턴 파서 한계). 정상 종료 `96/128 < 120`이므로 규정에 따라 **판정 보류**로 봉인·보고.
- **전적·점수 (96경기 기준, 판정 보류·보고 전용 D-191)**:
  - **33승 0무 63패**, 평균 점수 **`0.34375`** (`0.344`, 조합 클러스터 95% CI **`[0.231, 0.458]`**).
  - **같은 슬롯 (`n=96`) 대비 차이** (모든 구간이 0 포함):
    - vs [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) (`v13` 무재학습): **`+0.0417 [-0.0833, +0.1702]`** (나음 19 / 나쁨 15 / 같음 62)
    - vs [EX-206](EX-206-laya-search-2a-vs-foulplay-unlimited.md) (2-A 온라인 MCTS 5k 단독): **`+0.0104 [-0.102, +0.125]`** (나음 19 / 나쁨 18 / 같음 59) — 온라인 탐색 없이 단일 forward(`p50 0.269초`)만으로 2-A와 동급
    - vs [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) (`v10rt`): **`+0.0208 [-0.0957, +0.1458]`** (나음 17 / 나쁨 15 / 같음 64)
    - vs [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md) (`v12` 1턴 가치): **`-0.0417 [-0.1667, +0.0833]`** (나음 15 / 나쁨 19 / 같음 62)
    - vs [EX-208](EX-208-laya-search-2b-vs-foulplay-unlimited.md) (2-B 온라인 MCTS 5k + $V_\phi$): **`-0.0729 [-0.2062, +0.0729]`** (나음 18 / 나쁨 25 / 같음 53)
- **지연·행동·팀 유형별 특성**:
  - GPU 0 단일 forward 지연 **`p50 0.269초 / p95 0.578초`** (`foul-play` `5,332`결정, `p50 7.202초`, 간섭 없음).
  - **팀 유형별 점수**: **`balance` (`n=56`) `0.429`**(강세), `weather` (`n=15`) `0.267`, **`offense` (`n=22`) `0.227`**(취약 — `EX-208` `offense 0.471`과 대조), `defense` (`n=3`) `0.000`.
  - 테라 `45/97`경기(`13승 32패`, 초반 T1–9 `6`회), 실패 기술률 `5.72%` (`202/3,530`).
- **산출물·뷰어([C-047](../../../CONTRACTS.md#c-047-viewer-export))**:
  - 실행·보고: `runs/model-training/EX-210/report.md`, `runs/model-training/EX-210/checksums.sha256`
  - 뷰어: `exports/battle_viewers/ex210/index.html` (`97`경기, `5,590`결정)
