# EX-133 — laya v2+테라와 v2+테라 승패 가중 모방 같은 실행 256경기(GPU0, EX-120 일정)

- 상태: Planned
- 생성일: 2026-10-26
- 책임자: Claude Code
- 관련 exec plan: [EP-216](../plans/EP-216-laya-outcome-weighted-imitation.md)
- 관련 decision: [D-193](../decisions/D-193-laya-outcome-weighted-imitation.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행: [EX-132](EX-132-laya-v2t-outcome-weighted-training.md)(학습 완료만, 판정 무관), [EX-124](EX-124-laya-v2-tera-knowledge-training.md), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

같은 일정과 같은 상대(Abyssal)에서 승패 가중 모방 모델이 v2+테라보다 배틀 성적이 나은가?

## 가설 또는 qualification 목표

- **진행 조건**: EX-132 학습과 평가가 완료됐는지만 본다. 오프라인 결과는 진행 여부를 정하지 않는다(D-191).
- **qualification**: 모델별 128슬롯이 처리되고 분모 산술이 맞으며 봉인된다.
- **판정**(실행 전 동결): 같은 슬롯 점수 차이(`laya-v2tw` − `laya-v2t`)를 본다. 구간은 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261029)다.
  - 하한 > 0 → "승패 가중이 배틀 성적을 개선"
  - 상한 < 0 → "악화"
  - 그 외 → "구별되지 않음"
  - 어느 모델이든 정상 종료가 120/128 미만이면 판정을 보류한다.
- **보고 지표**(판정 외):
  - 실패·무효 기술 비율과 반복 지표(`comparison.failed_moves`)
  - 테라 사용
  - v2+테라 결과가 EX-125·EX-127·EX-129의 같은 슬롯과 일치하는지(재현)

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-v2t | EX-120 봉인 일정 128슬롯, Abyssal, 300턴/600결정, GPU0 서빙, `laya-compact-v2[damage,moves,speed,switch]` | EX-124 selected | `runs/model-training/EX-133/games/v2t-*` |
| laya-v2tw | 같음 | EX-132 selected | `runs/model-training/EX-133/games/v2tw-*` |

- **진행 순서**: EX-125·EX-129와 같은 구조다. EX-120 쌍마다 두 모델의 쌍을 연달아 두고, 먼저 할 모델은 시드 20261029의 digest로 정한다.
- **fallback, 재질의, 재경기**: 없다. 후보가 하나뿐이면 자동 제출한다.
- **분모**: 모델별 예정 128경기
- **단계 상한**: 10시간

## 환경 및 출처

- **배틀**: `pokechamp/.venv`, `BattleServer`, 포트 8107(`port8107.lock`)
- **서빙**: laya venv, GPU0(`gpu0.lock`, UUID 확인), node 계산기
- **실행기**: `scripts/laya-imitation compare6 {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ep216`
- **출력**: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-133`

## 격리 및 오염 통제

- **일정**: EX-120 collection 봉인을 확인한 뒤 일정을 복사한다.
- **자원 분리**: GPU1·GPU2와 그 포트를 쓰지 않는다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex133/index.html`에 두고, 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)
- **viewer 생성기**: `laya-imitation-researcher-v1`. 압축 입력 탭은 두 모델 모두 v2 렌더러로 복원한다.
- **viewer 출력 판본과 변경일지**: v1. [변경일지](../../../shared/viewers/CHANGELOG.md)에 항목을 추가한다.
- **공유 상태 예외**: 없다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. **mock**: v2 렌더러와 시작 체크포인트로 CPU 2경기를 한다. 분모에 넣지 않는다.
2. **prepare**: 다음을 확인하고 동결한다.
   - EX-124와 EX-132가 완료·봉인됐는지
   - 렌더러가 일치하는지
   - 일정이 봉인됐는지
3. **execute**: 256슬롯을 진행하고 경기별로 감사한다.
4. **export**: 보고, 뷰어, 봉인, 자원 반환을 한다.

## 승인·무효화·중단 조건

- **승인**: 256슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **무효**: 입력 경계 위반, 신원 불일치
- **중단**: 10시간 상한, 수집 결함

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯만 수정과 독립 검증을 거친 뒤 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-133` | `checksums.sha256`, `report.md` | 예정 |
| 뷰어 | `/workspace/exports/battle_viewers/ex133/index.html` | `checksums.sha256` | 예정 |

## 결과

예정.

## 분석 및 한계

- Abyssal 한 상대의 결과다. v2t는 Abyssal 대비 0.867로 천장에 가깝다. 따라서 작은 개선은 이 실험에서 구별되지 않을 수 있다.
- laya 직접 대결 평가는 별도 결정(D-194)에서 다룬다.

## 결론 및 후속 작업

예정.
