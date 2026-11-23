# EX-205 — laya v13 입력 교정(무재학습 EX-200) argmax 대 foul-play, Blim 128경기, 시간 제한 없음(CPU)

- 상태: Completed
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-241](../plans/EP-241-laya-v13-zeroshot-vs-foulplay.md)
- 관련 decision: [D-218](../decisions/D-218-laya-v13-input-bugfixes.md), [D-217](../decisions/D-217-laya-engine-value-rerank-training.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

재학습 없이 `EX-200` 체크포인트의 서빙 입력만 `v12`에서 `v13`([D-218](../decisions/D-218-laya-v13-input-bugfixes.md): 배틀 폼 스펙·`Embody Aspect` 세트 복구, 테라 후 전체 위협 재계산, 선공 `Roost` 지면화 경고·`duel` 교정, `Ivy Cudgel` 폼 타입)으로 바꿨을 때, foul-play Blim 128경기(시간 제한 없음) 성적이 같은 체크포인트의 `v12` 실행([EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md)) 대비 얼마나 달라지는가?

## 가설 또는 qualification 목표

- **판정 없음(보고 전용, D-191)**.
- 보고 지표: 승/무/패, 평균 점수와 조합 클러스터 bootstrap 95%, 같은 슬롯 [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md)(v12value, 제한 없음) 및 [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)(v10rt) 대비 차이, 테라 사용·승률, 실패 기술률, 결정 지연, 팀 유형별 점수.
- 정상 종료가 120/128 미만이면 "판정 보류"를 적는다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 체크포인트 | `runs/model-training/EX-200/checkpoints/selected` (EX-201과 바이트 동일, sha256 `22531f2f…`, 재학습 없음) |
| 변경 입력 | 서빙·뷰어 렌더러를 `v12`에서 `v13`(`integration.laya_v13.serve_v13`, `render_v13.install()`)으로 교체 |
| 통제 입력 | EX-201과 동일: EX-174 봉인 Blim 128슬롯(32대진 × 시드 2 × 진영 교환), foul-play `8f541f8` · 3,000ms × 병렬 4 · 스레드 1 · 2026-10 통계, argmax, guard 없음, 사용 통계 확장 없음, 시간·턴·결정 수 제한 전부 해제(`actor_unlimited`, Showdown 자체 규칙 유지) |
| 자원·포트 | CPU 전용(서빙 스레드 8), 포트 `8100-8103`, `scripts/mem-guard 25` |
| 같은 슬롯 기준선 | 주 기준선: [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md)(48승 80패, 0.375), 보조 기준선: [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)(42승 85패, 0.331) |

## 격리 및 오염 통제

- 출력 위치: `runs/model-training/EX-205` (메모리 로그 `runs/model-training/EX-205-memory.log`).
- 뷰어 출력([C-047](../../../CONTRACTS.md#c-047-viewer-export)): `exports/battle_viewers/ex205/` (`integration.laya_imitation.viewer`, `render_v13.install()` 적용으로 서빙된 `v13` 입력을 그대로 표시, `plan=EP-241`).
- 결함 복구([D-029](../../../shared/governance/decisions/D-029-experiment-defect-recovery.md)): foul-play 엔진 panic은 `actor_unlimited`가 해당 경기만 `incomplete`(`engine_panic`, `failure_scope=battle`)로 격리한다. 그 외 `phase_error`는 즉시 중단하며 자동 재실행하지 않는다.

## 절차

1. `scripts/laya-v13-battle-ep241 EX-205`: `mock`(첫 쌍 2경기, 분모 밖, 감사 통과 확인) → `prepare`(프로토콜·소스·체크포인트 해시 동결, `v12` 기반 무변경 확인) → `execute`(128슬롯) → `export`(보고·뷰어·봉인).

## 결과

- **판정**: 보고 (정상 종료 127/128 ≥ 120, 실패 1건, 미완료 0, 무효 0, 감사 전원 통과).
- **승 / 무 / 패**: **40 / 0 / 87**, 평균 점수 **0.315**, 조합 클러스터 95% CI **`[0.236, 0.394]`**.
- **같은 슬롯 [EX-201](EX-201-laya-engine-value-vs-foulplay-unlimited.md) (`v12value`, 제한 없음) 대비**: **`-0.055`, 95% `[-0.157, +0.039]`** (127슬롯; 이번이 나쁨 25, 나음 18, 같음 84 — 95% CI가 0 포함).
- **같은 슬롯 [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) (`v10rt`) 대비**: **`-0.016`, 95% `[-0.111, +0.078]`** (127슬롯; 이번이 나쁨 21, 나음 19, 같음 87).
- **테라 사용**: 51/128경기(`choice_rate 0.82%`, `10승 41패`; EX-201 70경기 `1.28%` 대비 **-36% 급감**, T1–9 조기 테라 8회 → 1회).
- **실패 기술 / 루프**: 211/4,950 (`4.26%`, 67경기, 루프 5건; EX-201 `4.84%`, 루프 11건 대비 감소).
- **팀 유형별**: `balance` 0.386(70), `offense` 0.273(33; EX-201 0.382 대비 `-11.0%p`), `weather` 0.200(20), `defense` 0.000(4).
- **지연 / 상대 통제**: `v13` CPU 서빙 `p50 3.012s / p95 8.053s`; `foul-play` 7,647결정 `p50 7.228s / p95 8.255s / max 13.215s`(EX-201 `p50 7.274s`와 동일).
- **실패 1건(`fp-b20-s2-a`)**: Toxapex vs Amoonguss 500턴 도달 시 Showdown의 자동 무승부 예고(`|bigerror|You will auto-tie if the battle doesn't end in 500 turns`)를 `pokechamp` 클라이언트가 `Showdown rejected battle action`으로 오인해 중단됨(`v13` 입력 결함 아님).
- **산출물·봉인**: `runs/model-training/EX-205/{result.json,report.md,versus-ex174.json,checksums.sha256}`, 뷰어([C-047](../../../CONTRACTS.md#c-047-viewer-export)): `exports/battle_viewers/ex205/index.html`(128경기, 7,843결정).

## 결론 및 후속 작업

재학습 없이 `v13`을 `EX-200`에 zero-shot 적용하면 실패 기술·루프는 줄지만(`4.84% → 4.26%`, 루프 `11 → 5`), 전체 결정의 39.4%에서 `tera takes` 위협이 상향되면서 이미 `USED_TERA=-75`로 소극적인 `EX-200`의 테라 사용이 36% 더 위축(`70 → 51`경기, 공격 팀 `-11.0%p`)되어 점추정이 `0.375 → 0.315`(`-0.055`, CI 0 포함)로 하락했다. 따라서 무재학습 온라인 탐색(`EX-206` 2-A)에서는 `v12` vs `v13` 선택을 명시적으로 검토하고, `v13`은 재학습과 결합해 활용한다.
