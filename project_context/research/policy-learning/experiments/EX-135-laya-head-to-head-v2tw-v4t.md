# EX-135 — laya v2+테라 대 승패 가중·v4+테라 직접 대결 256경기(GPU2, EX-120 일정)

- 상태: Planned
- 생성일: 2026-10-26
- 책임자: Claude Code
- 관련 exec plan: [EP-217](../plans/EP-217-laya-head-to-head-evaluation.md)
- 관련 decision: [D-194](../decisions/D-194-laya-head-to-head-evaluation.md), [D-193](../decisions/D-193-laya-outcome-weighted-imitation.md), [D-192](../decisions/D-192-laya-renderer-v4-fail-out.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행:
  - [EX-132](EX-132-laya-v2t-outcome-weighted-training.md)·[EX-130](EX-130-laya-v4-tera-training.md)의 학습 완료와 봉인만 본다. 판정과는 무관하다.
  - [EX-134](EX-134-laya-head-to-head512.md)(하네스와 같은 조건)
- 기준 연구선: `research/model-training`

## 질문 및 목적

새 후보 두 개가 v2+테라를 직접 대결에서 이기는가? 두 후보는 승패 가중 모방(EX-132)과 렌더러 v4(EX-130)다. Abyssal 비교는 각각 [EX-133](EX-133-laya-v2t-v2tw-battle256.md)과 [EX-131](EX-131-laya-v2t-v4t-battle256.md)이 맡는다.

## 가설 또는 qualification 목표

- **진행 조건**: EX-132와 EX-130의 학습·평가 완료와 봉인만 본다. 오프라인 결과는 진행 여부를 정하지 않는다(D-191).
- **qualification과 판정**: EX-134와 같은 규칙이다. 쌍마다 `laya-v2t` 점수를 조합 클러스터 bootstrap 95%(10,000회)로 본다.
  - 시드는 20261031이다.
  - 하한 > 0.5 → "laya-v2t 우세"
  - 상한 < 0.5 → "<비교 모델> 우세"
  - 그 외 → "구별되지 않음"
  - 정상 종료가 120/128 미만이면 판정을 보류한다.
- **보고 지표**: EX-134와 같다. Abyssal 비교는 EX-133·EX-131이 끝나 있을 때만 싣는다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| v2t 대 v2tw | EX-134와 같다 | 반대 진영 EX-132 selected(v2 렌더러) | `runs/model-training/EX-135/games/v2tw-*` |
| v2t 대 v4t | 같음 | EX-130 selected(v4 렌더러) | `.../games/v4t-*` |

- **분모**: 쌍별 예정 128, 전체 256
- **단계 상한**: 12시간

## 환경 및 출처

- EX-134와 같다(GPU2, 포트 8108, `headtohead` worker).
- **실행기**: `scripts/laya-imitation h2h {prepare,execute,export} --study EX-135`
- **출력**: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-135`

## 격리 및 오염 통제

- EX-134와 같다.
- mock은 EX-134 mock과 같은 하네스·서빙 경로이므로 다시 하지 않는다. 대신 prepare에서 두 새 체크포인트의 봉인과 렌더러 일치를 확인한다.
- **viewer**:
  - 출력은 `/workspace/exports/battle_viewers/ex135/index.html`이다.
  - 규격·생성기·판본은 EX-134와 같다([변경일지](../../../shared/viewers/CHANGELOG.md#ex134-laya-h2h-v1)).

## 절차

1. **prepare**: EX-124·EX-132·EX-130의 완료와 봉인, 렌더러 일치, 일정 봉인을 확인한 뒤 동결한다.
2. **execute**: 256슬롯을 진행하고 두 진영을 감사한다.
3. **export**: 보고, 뷰어, 오프라인 검사, 봉인, 자원 반환

## 승인·무효화·중단 조건

EX-134와 같다.

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-135` | `checksums.sha256`, `report.md` | 예정 |
| 뷰어 | `/workspace/exports/battle_viewers/ex135/index.html` | `checksums.sha256` | 예정 |

## 결과

예정.

## 분석 및 한계

- EX-134와 같다.

## 결론 및 후속 작업

예정.
