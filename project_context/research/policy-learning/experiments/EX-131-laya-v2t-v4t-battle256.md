# EX-131 — laya v2+테라와 v4+테라 같은 실행 256경기(GPU1, EX-120 일정)

- 상태: Planned
- 생성일: 2026-10-26
- 책임자: Claude Code
- 관련 exec plan: [EP-215](../plans/EP-215-laya-renderer-v4.md)
- 관련 decision: [D-192](../decisions/D-192-laya-renderer-v4-fail-out.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행: [EX-130](EX-130-laya-v4-tera-training.md)(학습 완료만, 판정 무관), [EX-124](EX-124-laya-v2-tera-knowledge-training.md), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

같은 일정과 같은 상대(Abyssal)에서 v4 입력 모델이 v2+테라보다 배틀 성적이 나은가? 실패 기술 반복이 줄어드는가?

## 가설 또는 qualification 목표

- **진행 조건**: EX-130 학습·평가 완료만 본다. 오프라인 결과는 진행 여부를 정하지 않는다(D-191).
- **qualification**: 모델별 128슬롯이 처리되고 분모 산술이 맞으며 봉인된다.
- **판정**(실행 전 동결): 같은 슬롯 점수 차이(`laya-v4t` − `laya-v2t`)를 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261028)로 본다.
  - 하한 > 0 → "v4+테라가 배틀 성적을 개선"
  - 하한 > −0.05 → "비퇴보"
  - 그 외 → "퇴보를 배제하지 못함"
  - 어느 모델이든 정상 종료가 120/128 미만이면 판정을 보류한다.
- **보고 지표**(판정 외):
  - 실패·무효 기술 비율과 많이 실패한 기술(`comparison.failed_moves`)
  - **반복 지표**: 실패가 나온 경기 수, 같은 기술이 연속 3회 이상 실패한 경기 수와 그 승패, 최장 연속 횟수
  - 테라 사용
  - v2+테라 결과의 EX-125·EX-127·EX-129 같은 슬롯 재현 일치

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-v2t | EX-120 봉인 일정 128슬롯, Abyssal, 300턴/600결정, GPU1 서빙 | EX-124 selected, `laya-compact-v2[damage,moves,speed,switch]` | `runs/model-training/EX-131/games/v2t-*` |
| laya-v4t | 같음 | EX-130 selected, `laya-compact-v4[damage,fails,moves,out,speed,switch]` | `runs/model-training/EX-131/games/v4t-*` |

- **진행 순서**: EX-125·EX-129와 같은 구조다. EX-120 쌍마다 두 모델 쌍을 연달아 두고, 먼저 할 모델은 시드 20261028의 digest로 정한다.
- **fallback, 재질의, 재경기**: 없다. 단일 후보는 자동 제출한다.
- **분모**: 모델별 예정 128
- **단계 상한**: 10시간

## 환경 및 출처

- 배틀: `pokechamp/.venv`, `BattleServer`, 포트 8109(`port8109.lock`)
- 서빙: laya venv, GPU1(`gpu1.lock`, UUID 확인), node 계산기. v4 서빙은 매 결정에서 실패 표시와 교체 후보 피해를 실시간으로 계산한다.
- 실행기: `scripts/laya-imitation compare5 {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ep215`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-131`

## 격리 및 오염 통제

- **일정**: EX-120 collection 봉인을 확인한 뒤 일정을 복사한다.
- **자원 분리**: GPU0·GPU2와 그 포트를 쓰지 않는다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex131/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)
- **viewer 생성기**: `laya-imitation-researcher-v1`. 압축 입력 탭은 모델별 렌더러(v2, v4)로 복원한다.
- **viewer 출력 판본과 변경일지**: v1, [변경일지](../../../shared/viewers/CHANGELOG.md)에 항목을 추가한다.
- **공유 상태 예외**: 없다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. mock: v4 렌더러와 시작 체크포인트로 CPU 2경기를 한다. 분모 밖이다.
2. prepare: EX-124와 EX-130의 완료와 봉인, 렌더러 일치, 일정 봉인을 확인하고 동결한다.
3. execute: 256슬롯을 진행하고 경기별로 감사한다.
4. export: 보고, 뷰어, 봉인, 자원 반환

## 승인·무효화·중단 조건

- **승인**: 256슬롯 처리, 분모 산술, 봉인
- **무효**: 입력 경계 위반, 신원 불일치
- **중단**: 10시간 상한, 수집 결함

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯만 수정과 독립 검증 뒤 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-131` | `checksums.sha256`, `report.md` | 예정 |
| 뷰어 | `/workspace/exports/battle_viewers/ex131/index.html` | `checksums.sha256` | 예정 |

## 결과

예정.

## 분석 및 한계

- Abyssal 한 상대의 결과다. 래더(사람) 효과는 이 실험으로 입증되지 않는다.
- Abyssal은 버티기 싸움을 하지 않으므로, 사람식 턴 넘기기의 득실은 이 실험에서 드러나지 않는다.

## 결론 및 후속 작업

예정.
