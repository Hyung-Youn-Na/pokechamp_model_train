# EX-134 — laya v2+테라 대 v2·v1·v2+테라+효과·v3+테라 직접 대결 512경기(GPU2, EX-120 일정)

- 상태: Completed
- 생성일: 2026-10-26
- 책임자: Claude Code
- 관련 exec plan: [EP-217](../plans/EP-217-laya-head-to-head-evaluation.md)
- 관련 decision: [D-194](../decisions/D-194-laya-head-to-head-evaluation.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행: [EX-120](EX-120-laya-team-generalization128.md)(일정), 체크포인트 EX-118·121·124·126·128(모두 완료·봉인)
- 기준 연구선: `research/model-training`

## 질문 및 목적

laya끼리 직접 붙이면 Abyssal 평가에서 구별되지 않았던 차이가 구별되는가? 그 방향은 Abyssal 결과와 같은가?

비교한 쌍과 Abyssal 결과(같은 슬롯):

| 쌍 | Abyssal 결과 | 출처 |
|---|---|---|
| v2t 대 v2 | +0.070 [0.000, 0.141] | [EX-125](EX-125-laya-v2-tera-battle256.md) |
| v2t 대 v1 | EX-125와 EX-120을 같은 슬롯으로 맞춘 값(v2→v1 +0.102는 EX-122) | EX-125, EX-120 |
| v2t 대 v2te | +0.070 [−0.008, +0.148] | [EX-127](EX-127-laya-v2t-v2te-battle256.md) |
| v2t 대 v3t | +0.055 [−0.008, +0.125] | [EX-129](EX-129-laya-v2t-v3t-battle256.md) |

## 가설 또는 qualification 목표

- **qualification**: 쌍별 128슬롯이 처리되고, 두 진영 감사를 통과하고, 분모 산술이 맞고, 봉인된다.
- **판정**(실행 전 동결, 쌍마다):
  - 점수는 `laya-v2t`의 경기 점수(승 1, 무 0.5, 패 0)다.
  - 평균을 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261030)로 본다.
    - 하한 > 0.5 → "laya-v2t 우세"
    - 상한 < 0.5 → "<비교 모델> 우세"
    - 그 외 → "구별되지 않음"
  - 그 쌍의 정상 종료가 120/128 미만이면 판정을 보류한다.
- **보고 지표**(판정 외):
  - **Abyssal 비교**: 같은 슬롯 Abyssal 차이(v2t − 비교 모델)와 같은 bootstrap 구간, 두 평가의 구별 여부, 방향이 같은지
  - 진영별 실패·무효 기술과 반복 지표(공개 protocol 기준)
  - 교환쌍 분포, 진영별 추론 지연

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| v2t 대 v2 | EX-120 봉인 일정 128슬롯, v2t는 model 진영과 그 팀, 300턴/600결정, GPU2 서빙, 두 진영 argmax | 반대 진영 EX-121 selected(v2 렌더러) | `runs/model-training/EX-134/games/v2-*` |
| v2t 대 v1 | 같음 | EX-118 selected(v1 렌더러) | `.../games/v1-*` |
| v2t 대 v2te | 같음 | EX-126 selected(v2 렌더러) | `.../games/v2te-*` |
| v2t 대 v3t | 같음 | EX-128 selected(v3 렌더러) | `.../games/v3t-*` |

- **진행 순서**: EX-120 쌍마다 네 비교 모델을 시드 20261030의 digest 순서로 두고, 각 모델이 그 쌍의 두 슬롯(교환쌍)을 연달아 둔다.
- **서빙**: 다섯 모델을 단계 내내 GPU2에 함께 띄운다. 각 진영은 자기 모델 서빙만 부른다.
- **fallback, 재질의, 재경기**: 없다. 후보가 하나뿐이면 자동 제출한다.
- **분모**: 쌍별 예정 128, 전체 512
- **단계 상한**: 12시간

## 환경 및 출처

- **배틀**: `pokechamp/.venv`, `BattleServer`, 포트 8108(`port8108.lock`)
- **worker**: `python -m integration.laya_imitation.headtohead worker`(두 진영 모두 EX-071 모델 player)
- **서빙**: laya venv, GPU2(`GPU-c79ce3fd-81e7-454b-75ce-e63fad63baa4`, `gpu2.lock`, UUID와 유휴 확인), node 계산기
- **실행기**: `scripts/laya-imitation h2h {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ep217`
- **출력**: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-134`

## 격리 및 오염 통제

- **일정**: EX-120 collection 봉인을 확인한 뒤 일정을 복사한다.
- **기록**:
  - 기준 진영: 시도 폴더의 `events.jsonl`, `request.json`
  - 비교 진영: `opponent/events.jsonl`, 거울 `opponent/request.json`(진영·시드·서빙만 바뀜)
  - 상대 팀 제출과 시뮬레이터 시드 기록은 symlink로 서로 연결한다.
  - 두 진영을 같은 `audit_match`로 각각 감사한다.
- **자원 분리**: GPU0·GPU1과 그 포트는 쓰지 않는다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex134/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)
- **viewer 생성기**: `laya-imitation-researcher-v1`과 `headtohead.export_viewer`
  - 경기마다 두 페이지를 둔다. 기준 진영은 `battle-NNN`, 비교 진영은 `battle-NNNb`다.
  - 압축 입력 탭은 진영별 모델 렌더러로 복원한다.
- **viewer 판본과 변경일지**: UI v1 안의 확장이다([변경일지](../../../shared/viewers/CHANGELOG.md#ex134-laya-h2h-v1)). 사전 확인은 EP-217의 mock 뷰어 검사다.
- **공유 상태 예외**: 없다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. **mock**(완료): v2t 대 v2t, EX-120 첫 두 쌍 4경기. 분모에 넣지 않는다.
2. **prepare**: 다섯 체크포인트의 완료·봉인, 렌더러 일치, 일정 봉인을 확인한 뒤 동결한다.
3. **execute**: 512슬롯을 진행하고 경기별로 두 진영을 감사한다.
4. **export**: 보고, 뷰어, 오프라인 검사, 봉인, 자원 반환

## 승인·무효화·중단 조건

- **승인**: 512슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **무효**: 입력 경계 위반, 신원 불일치, 어느 한 진영의 감사 실패(그 경기만)
- **중단**: 12시간 상한, 수집 결함(phase 오류)

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯만 수정과 독립 검증을 거친 뒤 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| mock | `/mnt/.../runs/model-training/EX-134/mock` | — | 4/4 정상, 두 진영 감사 통과 |
| 배틀 run | `/mnt/.../runs/model-training/EX-134` | `checksums.sha256`, `report.md` | 완료·봉인 |
| 뷰어 | `/workspace/exports/battle_viewers/ex134/index.html` | `checksums.sha256` | 생성·확인 통과(`exec-plans/evidence/ep217/ex134-viewer-check.json`) |

## 결과

- 2026-10-26 prepare 05:25Z, execute 05:27Z~15:58Z(GPU2·8108), export 15:58Z~16:10Z. 보고 `runs/model-training/EX-134/report.md`. 뷰어 확인 16:13Z 통과(1440·390 폭, 512경기·비교 진영 512페이지, 페이지 오류 0, `exec-plans/evidence/ep217/ex134-viewer-check.json`).
- 분모: 예정 512, 정상 507, 미완료 5, 실패·무효·미실행 0. 미완료는 모두 300턴 상한이다(v2-m29-s2-b, v2te-m30-s2-a, v2te-m32-s1-b, v2te-m32-s2-b, v3t-m32-s1-a). 모든 쌍이 정상 120/128 이상이라 판정한다.
- **판정**(laya-v2t 점수, 조합 클러스터 95%):

| 비교 모델 | 정상 | v2t 승/무/패 | v2t 점수 | 95% | 교환쌍 2승/1승1패/2패 | 판정 |
|---|---|---|---:|---|---|---|
| laya-v1 | 128/128 | 83/0/45 | 0.648 | [0.570, 0.727] | 27/29/8 | **laya-v2t 우세** |
| laya-v2 | 127/128 | 63/0/64 | 0.496 | [0.421, 0.571] | 11/40/12 | **구별되지 않음** |
| laya-v2te | 125/128 | 60/0/65 | 0.480 | [0.394, 0.569] | 11/38/12 | **구별되지 않음** |
| laya-v3t | 127/128 | 65/0/62 | 0.512 | [0.438, 0.583] | 10/44/9 | **구별되지 않음** |

- Abyssal 비교(같은 슬롯 v2t − 비교 모델):

| 비교 모델 | Abyssal 출처 | Abyssal 차이 | 95% | Abyssal 구별 | 직접 대결 구별 | 방향 일치 |
|---|---|---:|---|---|---|---|
| laya-v1 | EX-125·EX-120 | +0.172 | [0.094, 0.250] | v2t 우세 | v2t 우세 | 예 |
| laya-v2 | EX-125·EX-125 | +0.070 | [0.000, 0.141] | 구별되지 않음 | 구별되지 않음 | 아니오 |
| laya-v2te | EX-125·EX-127 | +0.070 | [−0.008, 0.148] | 구별되지 않음 | 구별되지 않음 | 아니오 |
| laya-v3t | EX-125·EX-129 | +0.055 | [−0.008, 0.125] | 구별되지 않음 | 구별되지 않음 | 예 |

- 진영별 실패·무효 기술: 비교 진영 v1 256/5937(4.31%), v2 400/5950(6.72%), v2te 374/6088(6.14%), v3t 384/5671(6.77%). v2t 진영은 쌍별 5.62~6.61%. 같은 기술 3회 이상 연속 실패 경기는 진영별 8~16이다.
- 지연 p50: v1 0.160초, v2 0.168초, v2t 0.168초, v2te 0.168초, v3t 0.176초.

## 분석 및 한계

- 직접 대결은 laya 계열끼리의 상대 강도다. 사람이나 다른 봇 상대의 강도를 직접 말하지 않는다.
- v2t가 모든 쌍의 공통 진영이다.
- 두 진영 모두 결정적이라, 표본은 EX-120 128슬롯(32조합)이 전부다.

## 결론 및 후속 작업

- 직접 대결은 Abyssal에서 이미 구별된 v1만 구별했다(v2t 0.648). Abyssal에서 구별되지 않던 v2·v2te·v3t는 직접 대결에서도 구별되지 않았다.
- v2·v2te는 방향도 Abyssal과 반대다(v2t 점수 0.496, 0.480). 직접 대결이 Abyssal 천장 문제를 풀지 못했다.
- 하네스와 뷰어 확장은 [EX-135](EX-135-laya-head-to-head-v2tw-v4t.md)·[EX-138](EX-138-laya-head-to-head-v5t.md)에서 그대로 쓴다.
