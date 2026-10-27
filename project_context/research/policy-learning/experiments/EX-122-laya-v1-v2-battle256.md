# EX-122 — laya v1·v2 같은 실행 256경기 비교 (EX-120 일정)

- 상태: Completed
- 생성일: 2026-10-22
- 책임자: Claude Code
- 관련 exec plan: [EP-210](../plans/EP-210-laya-renderer-v2.md)
- 관련 decision: [D-185](../decisions/D-185-laya-modular-renderer-v2.md)
- 선행: [EX-121](EX-121-laya-v2-all-training.md)(v2 selected), [EX-118](EX-118-laya-compact-imitation-training.md)(v1 selected), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

같은 일정(새 팀 32개, 128슬롯)과 같은 상대(Abyssal)에서, v2 렌더러로 학습한 모델이 v1 모델보다 배틀 성적이 나은가? 두 모델을 같은 실행 안에서 번갈아 진행해 직접 비교한다.

## 가설 또는 qualification 목표

- **qualification**: 모델별 128슬롯이 모두 처리되고 분모 산술이 맞으며 봉인된다.
- **판정**(실행 전 동결): 같은 슬롯끼리 점수 차이 `v2 − v1`의 평균을 구하고, 조합(32개) 클러스터 bootstrap 95% 구간(10,000회, 시드 20261024)으로 판정한다.
  - 하한 > 0 → "v2가 배틀 성적을 개선"
  - 상한 < 0 → "v2가 악화"
  - 그 외 → "구별되지 않음"
  - 두 모델 모두 정상 종료한 슬롯만 차이에 쓴다. 어느 모델이든 정상 종료가 120/128 미만이면 판정을 보류한다.
- **보조 지표**(판정 외):
  - 모델별 승/무/패, EX-120 방식의 조합 클러스터 95%
  - 결과가 다른 슬롯 수
  - v1 재현성: 같은 슬롯의 EX-120 결과와 일치하는 비율
  - 지연
  - 테라 사용: 모델별 테라 사용 경기 수(protocol `|-terastallize|`), 결정당 테라 선택률, 테라 턴. 실행 전인 2026-10-23에 EX-125와 같은 보고 항목으로 추가했다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| v1 | EX-120 봉인 일정 128슬롯(팀, 시드, 진영, 순서), Abyssal, 300턴/600결정, GPU0 서빙 | EX-118 selected + `laya-compact-v1` | `runs/model-training/EX-122/games/v1-*` |
| v2 | 같음 | EX-121 selected + `laya-compact-v2[damage,moves,speed,switch]` | `runs/model-training/EX-122/games/v2-*` |

- **진행 순서**:
  - EX-120 일정의 쌍 순서를 따른다.
  - 각 쌍마다 v1 쌍과 v2 쌍을 연달아 둔다. 어느 쪽이 먼저인지는 `digest([20261024,'ex122_first',pair_id])`의 첫 비트로 정한다.
  - slot_id는 `<v1|v2>-<EX-120 slot_id>`다.
- **서빙**:
  - v1과 v2 서버를 GPU0에 동시에 둔다(loopback 별도 포트).
  - 서빙은 각 렌더러가 해당 자료 생성기와 같은지 확인한다.
  - v2 서빙은 계산기 워커를 함께 띄운다.
- **fallback, 재질의, 재경기**: 없다. 단일 후보는 자동 제출한다. 실행 불가능한 선택은 실패다.
- **분모**: 모델별 예정 128 = 정상 + 실패 + 미완료 + 무효 + 미실행
- **중단 규칙**: 수집 결함이 생기면 중지한다. 단계 상한은 10시간이다.

## 환경 및 출처

- 배틀: `pokechamp/.venv`, `BattleServer`, 포트 8107
- 서빙: laya venv, node 계산기(v2)
- 실행기: `scripts/laya-imitation compare {mock,prepare,execute,export}`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-122`
- 체크포인트:
  - v1 = EX-118 `checkpoints/selected`(`403581f2…`)
  - v2 = EX-121 `checkpoints/selected`(prepare에서 sha를 기록한다)

## 격리 및 오염 통제

- **일정**: EX-120 collection 봉인을 확인한 뒤 일정을 복사한다. 결과를 보기 전에 정해진 일정이다.
- **상대 가정 세트**: v2의 가정 세트는 EX-071 corpus 최빈 세트다. EX-120 팀의 개별 세트가 같은 풀 출신이라 가정이 실제와 맞을 수 있다는 한계를 명시한다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex122/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)
- **viewer 생성기**: `laya-imitation-researcher-v1`
  - 목록에 모델, 조합, 시드, 유형 열을 추가한다.
  - 압축 입력 탭은 모델별 렌더러(v1 또는 v2)로 복원한다.
- **viewer 출력 판본과 변경일지**: v1, [변경일지](../../../shared/viewers/CHANGELOG.md)에 항목을 추가한다.
- **공유 상태 예외**: 없다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. mock: v2 렌더러와 시작 체크포인트로 CPU 2경기를 한다. 분모 밖이다.
2. prepare: EX-121 완료와 봉인, EX-120 일정 봉인, 렌더러 일치를 확인하고 동결한다.
3. execute: 256슬롯을 순차 진행하고 경기별로 감사한다.
4. export: 보고, 뷰어, 봉인, 자원 반환

## 승인·무효화·중단 조건

- **승인**: 256슬롯 처리, 분모 산술, 봉인
- **무효 시도**: 입력 경계 위반, 신원 불일치
- **중단**: 10시간 상한, 수집 결함

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯은 수정과 독립 검증 뒤 해당 슬롯만 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-122` | `checksums.sha256` (sha256 `2e090600…`), `report.md` (`e9223155…`) | Sealed |
| 뷰어 | `/workspace/exports/battle_viewers/ex122/index.html` | `checksums.sha256` | Sealed, [오프라인 검사](../../../exec-plans/evidence/ep210/viewer-check.json), [리플레이 검사](../../../exec-plans/evidence/ep210/viewer-replay-check.json) |

## 결과

- **실행**: 2026-10-23 06:31 ~ 09:00 UTC, GPU0, 포트 8107
  - 체크포인트: v1 `403581f2…`, v2 `f3e60754…`
  - mock 2경기 정상(분모 밖), 결함 복구 없음
- **분모**: 모델별 128/128 정상 종료. 실패·미완료·무효·미실행 0이고 전 경기 감사를 통과했다.

| 모델 | 승/무/패 | 평균 점수 | 조합 클러스터 95% | 교환쌍 2승/1승1패/2패 |
|---|---|---:|---|---|
| v1 (EX-118) | 89/0/39 | 0.695 | [0.617, 0.773] | 28/33/3 |
| v2 (EX-121) | **102/0/26** | **0.797** | [0.734, 0.859] | 40/22/2 |

- **판정**(동결): 같은 슬롯 차이(v2 − v1) 평균 +0.1016, 조합 클러스터 95% [+0.0234, +0.1797] → **"v2가 배틀 성적을 개선"**
  - 128슬롯 중 v2 우세 25, v1 우세 12, 같음 91
- **v1 재현성**: EX-120 같은 슬롯 128/128에서 결과와 턴 수가 모두 같다. 같은 시드에서 배틀 경로가 결정적이다.
- **laya 팀 유형별**(v1 → v2):
  - 날씨 0.719 → 0.812
  - 공격형 0.594 → 0.781
  - 수비형 0.688 → 0.750
  - 밸런스는 보고서 표 참고
- **테라 사용**: v1 18/128경기(결정 0.39%), v2 16/128경기(0.35%). 사람은 78.8%(3.41%)다. v2도 거의 쓰지 않는다.
- **실패·무효 기술**(다른 세션이 보고 함수에 추가한 지표):
  - v1 176/3,868(4.55%). Thunder Wave 34/38, Aurora Veil 20/25 실패
  - v2 134/3,713(3.61%). **Spikes 74/120 실패**: 층이 다 찬 뒤 반복 사용
- **지연**: 모델 질의 p50은 v1 0.118초, v2 0.127초(계산기 포함)다.
- **보고서 결함**: `report.md`의 유형별 표 머리줄 구분선이 깨졌다(`reporting.compare_report` 형식 버그). 수치는 정확하다. 봉인된 보고서는 그대로 두고, 이후 보고를 위해 코드만 고쳤다.

## 분석 및 한계

- 상대는 Abyssal 하나뿐이다.
- 쌍 차이 128개로 볼 때 작은 개선은 구별되지 않을 수 있다.
- 확률은 행동 선택 확률이며 승률이 아니다.

## 결론 및 후속 작업

- 렌더러 v2(기술 변형·속도·교체·피해량)는 같은 실행 안에서 v1보다 배틀 성적을 높였다(+0.10, 구간 하한 > 0). 오프라인 NLL 차이(EX-121, 구별되지 않음)보다 배틀 차이가 더 뚜렷하다.
- 테라 사용은 늘지 않았다. 테라 지식 실험 [EX-124](EX-124-laya-v2-tera-knowledge-training.md)와 [EX-125](EX-125-laya-v2-tera-battle256.md)가 이어서 본다.
- 개선 후보: 층이 다 찬 Spikes, 무효인 Thunder Wave처럼 실패가 확정된 행동의 반복을 입력이나 지식으로 줄인다.
