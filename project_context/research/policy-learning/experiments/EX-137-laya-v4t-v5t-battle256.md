# EX-137 — laya v4+테라와 v5+테라 같은 실행 256경기(GPU0, EX-120 일정)

- 상태: Planned
- 생성일: 2026-10-27
- 책임자: Claude Code
- 관련 exec plan: [EP-218](../plans/EP-218-laya-renderer-v5-item-state.md)
- 관련 decision: [D-195](../decisions/D-195-laya-item-state-renderer-v5.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행: [EX-136](EX-136-laya-v5-tera-training.md)(학습 완료만, 판정 무관), [EX-130](EX-130-laya-v4-tera-training.md), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

같은 일정과 같은 상대(Abyssal)에서, 상대 아이템 상태와 상태 카운터를 표시한 v5 입력 모델이 v4+테라보다 배틀 성적이 나은가?

## 가설 또는 qualification 목표

- **진행 조건**: EX-136 학습·평가 완료만 본다. 오프라인 결과는 진행 여부를 정하지 않는다(D-191).
- **qualification**: 모델별 128슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **판정**(실행 전 동결): 같은 슬롯 점수 차이(`laya-v5t` − `laya-v4t`)를 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261033)로 본다.
  - 하한 > 0 → "v5+테라가 배틀 성적을 개선"
  - 하한 > −0.05 → "비퇴보"
  - 그 외 → "퇴보를 배제하지 못함"
  - 어느 모델이든 정상 종료가 120/128 미만이면 판정을 보류한다.
- **보고 지표**(판정 외):
  - **v2t 대비**: EX-125 v2t 128슬롯과 같은 슬롯 차이(`laya-v5t` − `laya-v2t`)와 같은 bootstrap 구간. 결정적 경로이므로 재사용한다.
  - **결정성 확인**: 이번 v4t 128슬롯의 결과가 EX-131 v4t와 같은 슬롯에서 일치하는 수. 파서 필드 추가가 v4 동작을 바꾸지 않았는지 확인한다.
  - 실패·무효 기술 비율, 반복 지표(`comparison.failed_moves`), 테라 사용
  - 상대 아이템이 제거된 뒤의 결정 수와, 그 결정에서 지면 기술이 무효였던 횟수
  - Sleep Talk 실패를 원인별로 나눈다(그 턴에 깨어남 / 깨어 있는데 사용).

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-v4t | EX-120 봉인 일정 128슬롯, Abyssal, 300턴/600결정, GPU0 서빙 | EX-130 selected, `laya-compact-v4[damage,fails,moves,out,speed,switch]` | `runs/model-training/EX-137/games/v4t-*` |
| laya-v5t | 같음 | EX-136 selected, `laya-compact-v5[counters,damage,fails,items,moves,out,speed,switch]` | `runs/model-training/EX-137/games/v5t-*` |

- **진행 순서**: EX-131과 같은 구조다. EX-120 쌍마다 두 모델 쌍을 연달아 두고, 먼저 할 모델은 시드 20261033의 digest로 정한다.
- **fallback, 재질의, 재경기**: 없다. 단일 후보는 자동 제출한다.
- **분모**: 모델별 예정 128
- **단계 상한**: 10시간

## 환경 및 출처

- 배틀: `pokechamp/.venv`, `BattleServer`, 포트 8107(`port8107.lock`)
- 서빙: laya venv, GPU0(`gpu0.lock`, UUID와 유휴 확인), node 계산기
- 실행기: `scripts/laya-imitation compare7 {mock,prepare,execute,export}`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-137`

## 격리 및 오염 통제

- 일정: EX-120 collection 봉인을 확인한 뒤 복사한다.
- 자원 분리: GPU1·GPU2·GPU3과 그 포트는 쓰지 않는다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex137/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1), 생성기 `laya-imitation-researcher-v1`. 압축 입력 탭은 모델별 렌더러(v4/v5)로 복원한다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. mock: v5 렌더러와 EX-136 selected로 2경기. 분모 밖이다.
2. prepare: 두 체크포인트의 완료·봉인, 렌더러 일치, 일정 봉인을 확인한 뒤 동결한다.
3. execute: 256슬롯을 진행하고 경기별로 감사한다.
4. export: 보고, 뷰어, 오프라인 검사, 봉인

## 승인·무효화·중단 조건

- **승인**: 256슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **무효**: 입력 경계 위반, 신원 불일치, 감사 실패(그 경기만)
- **중단**: 10시간 상한, 수집 결함(phase 오류)

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯만 수정과 독립 검증을 거친 뒤 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-137` | `checksums.sha256`, `report.md` | 예정 |
| 뷰어 | `/workspace/exports/battle_viewers/ex137/index.html` | `checksums.sha256` | 예정 |

## 결과

진행 전.

## 분석 및 한계

- 상대는 Abyssal 하나이고 테라를 쓰지 않는다. Abyssal이 Air Balloon이나 Knock Off를 얼마나 쓰는지에 따라 이 변경이 드러나는 결정 수가 제한될 수 있다(보고 지표로 센다).
- 128쌍 차이로 작은 효과는 구별되지 않을 수 있다.

## 결론 및 후속 작업

진행 전.
