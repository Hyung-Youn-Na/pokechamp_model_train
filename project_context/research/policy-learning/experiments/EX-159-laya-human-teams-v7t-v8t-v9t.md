# EX-159 — laya v7t·v8t·v9t 사람이 짠 완성 팀 123개 대 Abyssal(GPU0·1·2)

- 상태: Stopped
- 생성일: 2026-11-02
- 책임자: Claude Code
- 관련 exec plan: [EP-226](../plans/EP-226-laya-human-teams-v7-v8-v9.md)
- 관련 decision: [D-203](../decisions/D-203-laya-human-teams-v7-v8-v9.md), [D-199](../decisions/D-199-laya-play-teams-abyssal-battle.md)
- 비교 대상: `laya-v7t`(EX-149), `laya-v8t`(EX-152), `laya-v9t`(EX-157). EX-120 일정 결과 [EX-153](EX-153-laya-v7t-v8t-battle256.md)·[EX-158](EX-158-laya-v7t-v9t-battle256.md)와 방향을 비교한다.
- 기준 연구선: `research/model-training`

## 질문 및 목적

사람이 직접 짠 완성 팀으로 Abyssal과 두었을 때 v8t(엔진 실패 표시)·v9t(상대 위협 표시)가 v7t보다 나은가, v9t가 v8t보다 나은가? EX-120 재구성 팀 결과와 같은 방향인가?

## 가설 또는 qualification 목표

- **qualification**: 모델별 492슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **판정**(실행 전 동결, D-203): 쌍 v8t − v7t(시드 20261055), v9t − v7t(20261056), v9t − v8t(20261057). 같은 슬롯 점수 차이의 조합(123) 클러스터 bootstrap 95%, 10,000회.
  - 하한 > 0 → "개선", 하한 > −0.05 → "비퇴보", 그 외 → "퇴보를 배제하지 못함"
  - 어느 모델이든 정상 종료 467/492 미만이면 판정 보류
- **보고 지표**(판정 외): 모델별 승무패·점수, 팀 묶음(smogon/blim/trained)·학습 노출(`train_games` 0 / 그 외)·유형별 점수율, 실패·무효 기술 비율과 3회 이상 연속 실패, 테라 사용, 결정 지연

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 위치 |
|---|---|---|---|
| laya-v7t | EX-159 일정 492슬롯, Abyssal, 300턴/600결정, 쌍별 GPU 묶음 | EX-149 selected, `v7` | `EX-159/shards/g*/games/v7t-*` |
| laya-v8t | 같음 | EX-152 selected, `v8` | `.../v8t-*` |
| laya-v9t | 같음 | EX-157 selected, `v9`(`integration.laya_threat.serve`) | `.../v9t-*` |

### 일정 (`integration.laya_teamset.battle collect`)

- 팀: laya-play v1.8.0 `teams.json`(smogon 32)·`teams_blim.json`(blim 65)·`teams_trained.json`(trained 69)을 이 순서로 훑어 6종족 서명별 첫 팀. 고정 로컬 Showdown `gen9ou` 검증기 재통과(탈락 시 제외·기록). 결과 123팀(smogon 32, blim 62, trained 29), 탈락 0.
- 원형 배열 `digest([20261054, 'ex159_ring', 서명])`, 조합 m = (팀 m, 팀 m+1 mod 123), 시드 2개 × 팀 교환. 시드·진행 순서는 EX-145와 같은 방식(`ex159_seeds`, `ex159_order`).
- 쌍(246)은 진행 순서대로 g0·g1·g2에 돌아가며 나눈다(각 82쌍, 164 기본 슬롯). 묶음 안에서 같은 쌍의 세 모델을 연달아 둔다(`comparison.make_schedule`, 첫 모델 순서 digest).
- fallback, 재질의, 재경기 없음. 단일 후보 자동 제출.

## 환경 및 출처

- 배틀: `pokechamp/.venv`, `BattleServer`. 묶음 g0 GPU0(`GPU-4f27dd5a…`)·8107, g1 GPU1(`GPU-c7e2d577…`)·8109, g2 GPU2(`GPU-c79ce3fd…`)·8108. 묶음마다 서빙 3개.
- 실행기: `python -m integration.laya_teamset.battle {collect,mock,prepare,execute <g0|g1|g2>,combine,export}`(laya venv), 연결 실행 `scripts/laya-imitation-ep226 run`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-159`

## 격리 및 오염 통제

- 일정은 결과를 보기 전에 만들고 봉인한다. prepare가 laya_imitation `source_identity`, laya_threat·laya_teamset 파일 해시, 체크포인트 해시를 동결하고 execute·combine이 확인한다.
- **viewer**: [C-047](../../../CONTRACTS.md#c-047-viewer-export), battle-viewer-ui-v1, 생성기 `laya_imitation.viewer`([변경일지](../../../shared/viewers/CHANGELOG.md#ex159-laya-v1)). 압축 입력 탭은 v7/v8/v9 렌더러로 복원한다. 출력 `/workspace/exports/battle_viewers/ex159/`.
- **재개**: 묶음별 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. collect(완료) → 2. mock(CPU, g0 첫 쌍, `laya-v9t-initial` 2경기, 분모 밖) → 3. prepare → 4. 세 묶음 execute 동시 진행(묶음 상한 12시간) → 5. combine → 6. export·뷰어 확인

## 승인·무효화·중단 조건

- **무효**: 입력 경계 위반, 신원 불일치, 감사 실패(그 경기만)
- **중단**: 묶음 12시간 상한, 수집 결함(phase 오류). 한 묶음이 멈춰도 나머지 묶음은 계속하고, combine은 세 묶음이 끝난 뒤 한다.

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 일정 | `.../EX-159/collection` | `checksums.sha256` | 봉인 |
| 묶음 run | `.../EX-159/shards/g0..g2` | 묶음별 `checksums.sha256` | 중단(부분 원장, 봉인 안 함) |
| 중단 기록·중간 집계 | `.../EX-159/stopped.json` | — | 2026-11-03 |
| 합친 결과·보고 | `.../EX-159/result.json`, `report.md` | `checksums.sha256` | 만들지 않음(중지) |
| 뷰어 | `/workspace/exports/battle_viewers/ex159/index.html` | — | 만들지 않음(중지) |

## 결과

진행 중 중지. 판정 보류(모델별 정상 종료가 467/492 기준 미만).

## 중단 결과

2026-11-03 04:28:44Z에 사용자 직접 요청으로 중지했다. 사용자 판단: 지금까지 Abyssal 상대 결과(EX-125 이후 v2t~v9t가 0.87~0.89에서 구별되지 않음)로 보아 이 비교는 성능이 포화돼 의미가 적고, 다음 개선 학습에 GPU0~3을 쓰기 위함이다. 도구 결함이나 중단 조건 때문이 아니다.

- 진행: g0 378, g1 376, g2 366 / 492(묶음별). 끝난 경기는 모두 completed·감사 통과, 실패·무효 0. 중지 순간 두던 3슬롯(`v7t-m053-s2-a`, `v7t-m092-s1-a`, `v9t-m081-s2-a`)은 미완료로 분모 밖이다.
- 모델별(중간): v7t 332-40(0.892, 372경기), v8t 326-48(0.872, 374), v9t 333-41(0.890, 374).
- 같은 슬롯 차이(중간, 임시 계산 — 동결 판정 시드가 아닌 seed 0, 조합 클러스터 bootstrap 10,000회):

| 쌍 | 슬롯 / 조합 | 차이 | 95% |
|---|---|---|---|
| v8t − v7t | 372 / 117 | −0.019 | [−0.063, +0.027] |
| v9t − v7t | 372 / 117 | −0.003 | [−0.042, +0.038] |
| v9t − v8t | 374 / 117 | +0.019 | [−0.021, +0.060] |

- 네 모델(EX-160 v8lt 포함)이 모두 둔 339슬롯 중 229슬롯은 모두 이겼고 모두 진 슬롯은 3개다. 패배는 팀 상성으로 고정되기보다 경기별로 흩어진다.
- combine·export·뷰어는 하지 않았다. 묶음 원장(`shards/g*/ledger.jsonl`)과 경기 디렉터리는 그대로 두었고, 중지한 3슬롯의 Showdown worktree 등록만 제거했다. battle-window 표시 `EX-159`를 지웠고 GPU0·1·2와 포트 8107·8108·8109를 반환했다.

## 결론 및 후속 작업

중간 결과로는 v7t·v8t·v9t가 사람 팀에서도 Abyssal 상대로 구별되지 않았다(EX-153·EX-158과 같은 방향). 정식 판정은 없다. 재개는 별도 지시가 있을 때만 하며, 다음 단계는 사용자 지시에 따른 개선 학습이다.
