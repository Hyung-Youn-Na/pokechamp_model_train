# EX-208 — 2-B 온라인 다중턴 탐색 + 신경망 상태가치 V_phi 결합 대 foul-play, Blim 128경기(시간 제한 없음)

- 상태: Completed
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md)
- 관련 decision: [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

[EX-206](EX-206-laya-search-2a-vs-foulplay-unlimited.md)(2-A) 온라인 탐색에 [EX-207](EX-207-laya-state-value-2b-train.md)에서 학습한 리플레이 승패 기반 상태가치 모델 $V_\phi(\text{State})$(`laya` $q$-가중 1~2플라이 리프 평가 + MCTS $Q$·사전확률 융합)를 결합하면 `EX-206` 및 `EX-205` 대비 foul-play Blim 128경기 점수가 개선되는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 모델 | 정책/상대예측: `EX-200` + `v13`, 상태가치: `EX-207` selected (모두 **GPU 0 전용** 서빙) |
| 통제 입력 | EX-174 봉인 Blim 128슬롯, foul-play 3,000ms × 병렬 4, 시간·턴·결정 수 제한 해제(`actor_unlimited`) |
| 자원·출력 | 물리 GPU 0 전용(GPU 2·3 미사용), 포트 `8100-8103`, `runs/model-training/EX-208`, 뷰어 `exports/battle_viewers/ex208/`([C-047](../../../CONTRACTS.md#c-047-viewer-export)) |
| 같은 슬롯 기준선 | 주: [EX-206](EX-206-laya-search-2a-vs-foulplay-unlimited.md)(2-A), 보조: [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md), [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md), [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) |

## 결과

- **종료 상태**: **128 / 128 정상 완료** (`failed: 0, incomplete: 0, invalid: 0, unattempted: 0`, 감사 통과 **128/128**, `verify_seal`: 2,944개 파일 일치·불일치 `[]`).
- **전적·점수 (판정 없음, 보고 전용, D-191)**:
  - **52승 0무 76패**, 평균 점수 **`0.40625`** (`0.406`, 조합 클러스터 95% CI **`[0.312, 0.500]`**) — 역대 Blim 128경기 최고 점수(`EX-201` `0.375` 상회).
  - **같은 슬롯 대비 차이** (모든 구간이 0을 포함하므로 통계적 확정은 아니며 보고 전용):
    - vs [EX-206](EX-206-laya-search-2a-vs-foulplay-unlimited.md) (`2-A` MCTS 5k 단독, `0.336`): **`+0.0703 [-0.0312, +0.1719]`** (`128`슬롯; 나음 **27**, 나쁨 **18**, 같음 83) — $V_\phi$ 추가 순효과.
    - vs [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) (`v13` 무재학습, `0.315`): **`+0.0866 [-0.0156, +0.184]`** (`127`슬롯; 나음 **28**, 나쁨 **17**, 같음 82).
    - vs [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md) (`v12` 가치재정렬, 기존 최고 `0.375`): **`+0.0312 [-0.0547, +0.1172]`** (`128`슬롯; 나음 **26**, 나쁨 **22**, 같음 80).
    - vs [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) (`v10rt`, `0.331`): **`+0.0709 [-0.047, +0.183]`** (`127`슬롯; 나음 **30**, 나쁨 **21**, 같음 76).
- **지연·탐색 텔레메트리**:
  - `search2b` 결정 지연(물리 GPU 0 단독 서빙): **`p50 1.069초` / `p95 2.346초`** (`foul-play` `7,117`결정, `p50 7.226초 / p95 7.968초 / max 9.732초`, 간섭 없음).
  - 총 `7,159`응답 중 **`6,853`회 탐색**, **`6,410`회(`93.5%`)에서 $V_\phi$ 리프 평가 적용**(결정당 평균 `393.7`개 상태 평가), **override `728`회(`10.6%`**, `EX-206`의 `14.9%`보다 선별적), `unmapped = 3` (`0.04%`), 탐색 오류 **`0`**.
- **행동·팀 유형별 특성**:
  - **테라**: `62`경기 사용(`24승 38패`), 초반(T1–9) 테라 `13`회 (`EX-205` 1회 대비 회복).
  - **팀 유형별 점수**: **`offense` (`n=34`) `0.471`** (`EX-205` `0.273`·`EX-206` `0.353` 대비 큰 폭 상승), `weather` (`n=20`) `0.400`, `balance` (`n=70`) `0.386`, `defense` (`n=4`) `0.250`.
  - **실패 기술률**: `316 / 5,119` (`6.17%`, `74`경기) — `EX-205`(`4.26%`)·`EX-206`(`5.71%`) 대비 소폭 증가.
- **산출물·뷰어([C-047](../../../CONTRACTS.md#c-047-viewer-export))**:
  - 실행·보고: `runs/model-training/EX-208/report.md`, `runs/model-training/EX-208/checksums.sha256`
  - 뷰어: `exports/battle_viewers/ex208/index.html` (`128`경기, `7,274`결정)
