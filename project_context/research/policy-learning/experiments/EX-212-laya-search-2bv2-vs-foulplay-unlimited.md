# EX-212 — 2-B v2 탐색 개선(foe PP 파싱 수정·스케일 정규화·duel lose 완화·Taunt 흡수 보정, CPU 서빙) 대 foul-play, Blim 128경기

- 상태: Stopped
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-244](../plans/EP-244-laya-search-2bv2-and-v14-training.md)
- 관련 decision: [D-220](../decisions/D-220-laya-recovery-matchup-2bv2-and-v14.md), [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

재학습 없이 `EX-208`과 동일한 체크포인트(`EX-200` + `v13` + `EX-207` $V_\phi$)에 (A) `foe_options_clean` PP 괄호 파싱 수정, (B) `Q_vphi`–`Q_mcts` 스케일 매칭 융합 및 `duel: lose` 시 `prior_lambda` 완화, (C) `poke-engine` `Taunt`+흡수 특성 회복 누락 보정을 적용한 **2-B v2**(`laya-search-2b-v2`)가 [EX-208](../experiments/EX-208-laya-search-2b-vs-foulplay-unlimited.md)(`0.406`) 대비 Blim 128경기 성적과 대면 불리/흡수 오류를 얼마나 개선하는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 체크포인트 | 정책/상대예측: `EX-200/checkpoints/selected` (`v13`), 상태가치: `EX-207/checkpoints/selected` (`clean_deepsets_v2`) |
| 변경 처치 | `integration.laya_search.search_2b_v2` (`foe_options_clean`, 스케일 매칭 `alpha=0.55`, `duel: lose` 시 `lam=0.015 / floor=1e-3`, `Taunt`+흡수 회복 보정, 500턴 `auto-tie` 알림 안전 처리) |
| 통제 입력 | EX-174 봉인 Blim 128슬롯, foul-play `8f541f8` 3,000ms × 병렬 4 · 스레드 1, 시간·턴·결정 수 제한 해제(`actor_unlimited`) |
| 자원·출력 | **CPU 서빙**(`CUDA_VISIBLE_DEVICES=''`, `OMP_NUM_THREADS=4 MKL_NUM_THREADS=4`, `EX-213` GPU 0·1 DDP와 병행), 포트 `8100-8103`, `mem-guard 40`, 출력 `runs/model-training/EX-212`, 뷰어 `exports/battle_viewers/ex212/`([C-047](../../../CONTRACTS.md#c-047-viewer-export)) |
| 같은 슬롯 기준선 | 주: [EX-208](EX-208-laya-search-2b-vs-foulplay-unlimited.md)(`0.406`), 보조: [EX-206](EX-206-laya-search-2a-vs-foulplay-unlimited.md)(`0.336`), [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md)(`0.315`), [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md)(`0.375`), [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)(`0.331`) |

## 결과

사용자 지시(2026-11-24 11:12 KST, `strategy.duel()` 전 공격기 무효 시 `duel: lose` 미발화 등 렌더러 입력 버그 수정을 우선하기 위해 조기 종료)로 **`18 / 128`경기 완료 시점**에 정상 중단했다(`Stopped`, 프로세스·자원 전부 반환).

- **중단 시점 전적 (`18 / 128`, `audit_passed 18/18`, 오류 `0`)**: **7승 0무 11패 (`0.389`)**, `foul-play p50 = 7.172s` (`852`결정).
- **같은 슬롯 (`n = 18`) 중간 비교**: vs `EX-208` `0.389 vs 0.389` (`+0.000`, `2/2/14`), vs `EX-206` `0.389 vs 0.389` (`+0.000`, `3/3/12`), vs `EX-205` `0.389 vs 0.278` (`+0.111`, `5/3/10`), vs `EX-174` `0.389 vs 0.389` (`+0.000`, `3/3/12`). 소표본 조기 중단으로 판정 보류.
