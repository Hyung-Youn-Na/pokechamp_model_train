# EX-206 — 2-A 온라인 다중턴 탐색(EX-200 + v13 + GPU 0 서빙 + MCTS 5k 사전확률 융합) 대 foul-play, Blim 128경기(시간 제한 없음)

- 상태: Completed
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md)
- 관련 decision: [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-218](../decisions/D-218-laya-v13-input-bugfixes.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

재학습 없이 `EX-200` + `v13` 입력(GPU 0 fp32 서빙)에 합법 수 제한된 `poke-engine` MCTS(`5,000 iters`, `turn_action`·`forced_switch`) 루트 $Q_{\text{mcts}}$와 `laya` 사전확률 융합($\text{score}(a) = Q_{\text{mcts}}(a) + 0.03 \ln\max(p(a), 10^{-4})$, 마진 `0.015`)을 결합하면, 단일 forward 기준선([EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md)·[EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md)) 대비 foul-play Blim 128경기 점수가 얼마나 향상되는가?

## 가설 또는 qualification 목표

- **판정 없음(보고 전용, D-191)**.
- 보고 지표: 승/무/패, 평균 점수·조합 클러스터 95% CI, 같은 슬롯 `EX-205`·`EX-201`·`EX-174` 대비 차이, 결정 지연(p50/p95), 탐색 override 비율, 테라 사용·승률, 실패 기술률, 팀 유형별 점수.
- 정상 종료 < 120/128이면 "판정 보류".

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 체크포인트 | `runs/model-training/EX-200/checkpoints/selected` (sha256 `22531f2f…`, 재학습 없음) |
| 변경 처치 | `integration.laya_search.serve_search` (`v13` 입력, GPU 0 fp32 배치 서빙 + `search_worker` 4레인 풀 MCTS `5,000 iters`, `λ=0.03`, `ε=1e-4`, `margin=0.015`, `turn_action`·`forced_switch` 전체 합법 수 탐색) |
| 통제 입력 | EX-174 봉인 Blim 128슬롯, foul-play `8f541f8` 3,000ms × 병렬 4 · 스레드 1 · 2026-10 통계, 시간·턴·결정 수 제한 해제(`actor_unlimited`) |
| 자원·포트 | **물리 GPU 0 전용**(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, GPU 2·3 미사용), 포트 `8100-8103`(EX-205 완료 후 실행), `scripts/mem-guard 40` |
| 같은 슬롯 기준선 | 주: [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md)(무재학습 v13), 보조: [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md)(0.375), [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)(0.331) |

## 격리 및 오염 통제

- 출력: `runs/model-training/EX-206`, 뷰어([C-047](../../../CONTRACTS.md#c-047-viewer-export)): `exports/battle_viewers/ex206/`.
- `EX-205` 종료 전에는 `execute`를 시작하지 않는다. 결함 복구는 [D-029](../../../shared/governance/decisions/D-029-experiment-defect-recovery.md)를 따른다.

## 결과

- **판정**: 보고 (정상 종료 **128/128**, 실패 0, 미완료 0, 무효 0, 감사 전원 통과, `error: null`).
- **승 / 무 / 패**: **43 / 0 / 85**, 평균 점수 **0.336**, 조합 클러스터 95% CI **`[0.258, 0.406]`**.
- **같은 슬롯 [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) (`v13`, 제한 없음) 대비**: **`+0.016`, 95% `[-0.064, +0.094]`** (127슬롯; 나음 20, 나쁨 18, 같음 89 — 95% CI가 0 포함).
- **같은 슬롯 [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md) (`v12`, 제한 없음) 대비**: **`-0.039`** (128슬롯; 나음 21, 나쁨 26, 같음 81).
- **같은 슬롯 [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) (`v10rt`) 대비**: **`0.000`, 95% `[-0.095, +0.095]`** (127슬롯; 나음 23, 나쁨 23, 같음 81).
- **테라 및 팀 유형 변화**: 테라 사용 **71/128경기**(`choice_rate 1.39%`, `22승 49패`, T1–9 조기 테라 **14회** — EX-205 51경기·T1–9 1회 대비 완전 회복), `offense` 팀 `0.273 → 0.353`(`+8.0%p`), `balance` `0.386`, `weather` `0.200`, `defense` `0.000`.
- **실패 기술률**: `282/4,943`(**`5.71%`**, 70경기 — EX-205 `4.26%` 대비 `+1.45%p` 증가; MCTS override가 `v13` judge `; fails` 경고를 덮어쓰는 경우 포함).
- **지연 / 상대 통제**: GPU 0 서빙 + 4레인 MCTS 5k 결정 지연 **`p50 0.669s / p95 1.568s`**(EX-205 CPU `3.012s` 대비 4.5배, EX-197 `9.662s` 대비 14.4배 단축; 보고서 템플릿의 `(CPU 서빙)` 문구는 기존 러너 고정 문자열). `foul-play` 7,106결정 `p50 7.130s / p95 7.672s`(EX-201 `7.274s`와 동일, `EX-207` 병행 간섭 없음 확인).
- **산출물·봉인**: `runs/model-training/EX-206/{result.json,report.md,versus-ex174.json,checksums.sha256}`, 뷰어([C-047](../../../CONTRACTS.md#c-047-viewer-export)): `exports/battle_viewers/ex206/index.html`(128경기, 7,342결정).
