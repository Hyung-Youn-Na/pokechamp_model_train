# EX-138 — laya v5+테라 대 v2+테라·v4+테라 직접 대결 256경기(GPU2, EX-120 일정)

- 상태: Planned
- 생성일: 2026-10-27
- 책임자: Claude Code
- 관련 exec plan: [EP-218](../plans/EP-218-laya-renderer-v5-item-state.md)
- 관련 decision: [D-195](../decisions/D-195-laya-item-state-renderer-v5.md), [D-194](../decisions/D-194-laya-head-to-head-evaluation.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행: [EX-136](EX-136-laya-v5-tera-training.md)(학습 완료·봉인만, 판정 무관), [EX-134](EX-134-laya-head-to-head512.md)·[EX-135](EX-135-laya-head-to-head-v2tw-v4t.md)(하네스), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

v5+테라가 현재 배틀 최고 모델 v2+테라(EX-124)와, 변수 하나 차이인 v4+테라(EX-130)를 직접 대결에서 이기는가?

## 가설 또는 qualification 목표

- **qualification**: 쌍별 128슬롯이 처리되고, 두 진영 감사를 통과하고, 분모 산술이 맞고, 봉인된다.
- **판정**(실행 전 동결, 쌍마다):
  - 점수는 `laya-v5t`의 경기 점수(승 1, 무 0.5, 패 0)다.
  - 평균을 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261034)로 본다.
    - 하한 > 0.5 → "laya-v5t 우세"
    - 상한 < 0.5 → "<비교 모델> 우세"
    - 그 외 → "구별되지 않음"
  - 그 쌍의 정상 종료가 120/128 미만이면 판정을 보류한다.
- **보고 지표**(판정 외):
  - Abyssal 같은 슬롯 차이(v5t − 비교 모델: EX-137 v5t, EX-125 v2t, EX-137 v4t)와 방향 일치
  - 진영별 실패·무효 기술과 반복 지표, 교환쌍 분포, 진영별 추론 지연
  - 상대 아이템이 제거된 뒤 결정 수와 그때의 지면 기술 무효 횟수, Sleep Talk 실패 원인(진영별)

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| v5t 대 v2t | EX-120 봉인 일정 128슬롯, v5t는 model 진영과 그 팀, 300턴/600결정, GPU2 서빙, 두 진영 argmax | 반대 진영 EX-124 selected(v2 렌더러) | `runs/model-training/EX-138/games/v2t-*` |
| v5t 대 v4t | 같음 | 반대 진영 EX-130 selected(v4 렌더러) | `.../games/v4t-*` |

- **진행 순서**: EX-135와 같다. EX-120 쌍마다 두 비교 모델을 시드 20261034의 digest 순서로 두고, 각 모델이 그 쌍의 두 슬롯(교환쌍)을 연달아 둔다.
- **서빙**: 세 모델을 단계 내내 GPU2에 함께 띄운다. 각 진영은 자기 모델 서빙만 부른다.
- **fallback, 재질의, 재경기**: 없다. 후보가 하나뿐이면 자동 제출한다.
- **분모**: 쌍별 예정 128, 전체 256
- **단계 상한**: 12시간

## 환경 및 출처

- 배틀: `pokechamp/.venv`, `BattleServer`, 포트 8108(`port8108.lock`)
- worker: `python -m integration.laya_imitation.headtohead worker`
- 서빙: laya venv, GPU2(`GPU-c79ce3fd-81e7-454b-75ce-e63fad63baa4`, `gpu2.lock`, UUID와 유휴 확인), node 계산기
- 실행기: `scripts/laya-imitation h2h3 {mock,prepare,execute,export}`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-138`

## 격리 및 오염 통제

- 기록, symlink, 두 진영 감사는 EX-134와 같다.
- 자원 분리: GPU0·GPU1·GPU3과 그 포트는 쓰지 않는다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex138/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1), 생성기 `laya-imitation-researcher-v1`과 `headtohead.export_viewer`. 압축 입력 탭은 진영별 렌더러(v2/v4/v5)로 복원한다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. mock: v5t 대 v5t, EX-120 첫 두 쌍 4경기. 분모 밖이다.
2. prepare: 세 체크포인트의 완료·봉인, 렌더러 일치, 일정 봉인을 확인한 뒤 동결한다.
3. execute: 256슬롯을 진행하고 경기별로 두 진영을 감사한다.
4. export: 보고, 뷰어, 오프라인 검사, 봉인, 자원 반환

## 승인·무효화·중단 조건

- **승인**: 256슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **무효**: 입력 경계 위반, 신원 불일치, 어느 한 진영의 감사 실패(그 경기만)
- **중단**: 12시간 상한, 수집 결함(phase 오류)

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 원본은 `diagnostics/`에 보존한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-138` | `checksums.sha256`, `report.md` | 예정 |
| 뷰어 | `/workspace/exports/battle_viewers/ex138/index.html` | `checksums.sha256` | 예정 |

## 결과

진행 전.

## 분석 및 한계

- 직접 대결은 laya 계열끼리의 상대 강도다. 사람이나 다른 봇 상대의 강도를 직접 말하지 않는다.
- 두 진영 모두 결정적이라, 표본은 EX-120 128슬롯(32조합)이 전부다.

## 결론 및 후속 작업

진행 전.
