# EX-127 — laya v2+테라와 v2+테라+효과 지식 같은 실행 256경기(GPU2, EX-120 일정)

- 상태: Completed
- 생성일: 2026-10-23
- 책임자: Claude Code
- 관련 exec plan: [EP-213](../plans/EP-213-laya-effect-knowledge.md)
- 관련 decision: [D-188](../decisions/D-188-laya-effect-knowledge.md)
- 선행: [EX-126](EX-126-laya-v2-tera-effect-training.md), [EX-124](EX-124-laya-v2-tera-knowledge-training.md), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

같은 일정과 같은 상대(Abyssal)에서 효과 지식을 더한 모델이 v2+테라 모델보다 배틀 성적이 나은가? 실패·무효 기술을 덜 쓰는가?

## 가설 또는 qualification 목표

- **qualification**: 모델별 128슬롯이 처리되고, 분모 산술이 맞으며, 봉인된다.
- **판정**(실행 전 동결): 같은 슬롯 점수 차이(`laya-v2te` − `laya-v2t`)를 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261026)로 본다.
  - 하한 > 0 → "효과 지식이 배틀 성적을 개선"
  - 상한 < 0 → "악화"
  - 그 외 → "구별되지 않음"
  - 어느 모델이든 정상 종료가 120/128 미만이면 판정을 보류한다.
- **실패 기술 지표**(보고, 판정 외):
  - 모델 쪽 `|move|`(다른 기술로 불려 나온 것 제외) 바로 뒤, 다음 기술·턴 전에 `-fail`/`-immune`/`-block`이 나온 비율을 센다(`comparison.failed_moves`).
  - 기술별 상위 목록과 Aurora Veil 실패/사용을 함께 낸다.
  - 기준선은 같은 함수로 센 EX-120 v1이다. 사전 집계(다음 줄만 본 근사)는 4.8%(187/3,895), Aurora Veil 20/25였다.
- **테라 지표**: EX-125와 같은 방식으로 보고한다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-v2t | EX-120 봉인 일정 128슬롯, Abyssal, 300턴/600결정, `laya-compact-v2[damage,moves,speed,switch]`, GPU2 서빙 | EX-124 selected | `runs/model-training/EX-127/games/v2t-*` |
| laya-v2te | 같음 | EX-126 selected | `runs/model-training/EX-127/games/v2te-*` |

- **진행 순서**: EX-122와 같은 구조로, EX-120 쌍마다 두 모델 쌍을 연달아 둔다. 먼저 할 모델은 `digest([20261026,'ex127_first',pair_id])`로 정한다.
- **fallback, 재질의, 재경기**: 없다. 단일 후보는 자동 제출한다.
- **분모**: 모델별 예정 128
- **단계 상한**: 10시간

## 환경 및 출처

- 배틀: `pokechamp/.venv`, `BattleServer`, 포트 8108(`port8108.lock`)
- 서빙: laya venv, GPU2(`gpu2.lock`, UUID 확인), node 계산기
- 실행기: `scripts/laya-imitation compare3 {mock,prepare,execute,export}`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-127`

## 격리 및 오염 통제

- **일정**: EX-120 collection 봉인을 확인한 뒤 일정을 복사한다.
- **자원 분리**: EX-122(GPU0·8107), EX-125(GPU1·8109)와 동시에 진행할 수 있다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex127/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)
- **viewer 생성기**: `laya-imitation-researcher-v1`. 목록에 모델, 조합, 시드 열을 둔다. 압축 입력 탭은 v2 렌더러로 복원한다.
- **viewer 출력 판본과 변경일지**: v1, [변경일지](../../../shared/viewers/CHANGELOG.md)에 항목을 추가한다.
- **공유 상태 예외**: 없다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. mock: v2 렌더러와 시작 체크포인트로 CPU 2경기를 한다. 분모 밖이다.
2. prepare: EX-124와 EX-126의 완료와 봉인, 렌더러 일치, 일정 봉인을 확인하고 동결한다.
3. execute: 256슬롯을 진행하고 경기별로 감사한다.
4. export: 보고(실패 기술 표 포함, EX-120 기준선 행), 뷰어, 봉인, 자원 반환

## 승인·무효화·중단 조건

- **승인**: 256슬롯 처리, 분모 산술, 봉인
- **무효**: 입력 경계 위반, 신원 불일치
- **중단**: 10시간 상한, 수집 결함

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯만 수정과 독립 검증 뒤 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-127` | `checksums.sha256`, `report.md` | 생성·봉인 |
| 뷰어 | `/workspace/exports/battle_viewers/ex127/index.html` | 오프라인 검사 [receipt](../../../exec-plans/evidence/ep213/viewer-check.json) | 생성 |

## 결과

- 2026-10-23 — mock(분모 밖) 3차에서 2경기 정상 종료, 감사 통과. 1·2차는 도구 결함(서빙 모델 이름 허용 목록, 포트 범위)으로 경기 전 중단했고 `diagnostics/mock-v1`, `mock-v2`에 보존했다. 3차 실행은 사용자 승인으로 했다.
- 2026-10-25 09:06Z prepare → execute → 11:33Z 256경기 종료. 모델별 128/128 정상 종료, 실패·무효·미실행 0, 전 경기 감사 통과. export는 2026-10-26 05:07Z에 EP-216 작업 중 수행했다(실행 세션이 export 전에 끝나 있었다).

| 모델 | 승/무/패 | 평균 점수 | 조합 클러스터 95% | 교환쌍 2승/1승1패/2패 | 지연 p50 |
|---|---|---:|---|---|---:|
| laya-v2t (EX-124) | 111/0/17 | 0.867 | [0.805, 0.922] | 47/17/0 | 0.126초 |
| laya-v2te (EX-126) | 102/0/26 | 0.797 | [0.727, 0.867] | 39/24/1 | 0.127초 |

- **판정**(동결): 같은 슬롯 차이(v2te − v2t) −0.0703, 95% [−0.1484, +0.0078] → **"구별되지 않음"**. v2te 우세 9, v2t 우세 18, 같음 101.
- **재현**: laya-v2t는 EX-125와 같은 111-17이다(같은 체크포인트, 결정적 경로).
- **실패·무효 기술**: v2t 240/4,177(5.75%), v2te 186/3,517(5.29%). v2te는 Toxic Spikes 50/60, Whirlwind 35/42가 많다.
- **테라 사용**: v2t 22경기(21승 1패), v2te 19경기(13승 6패)
- 산출물: `runs/model-training/EX-127/report.md`, 뷰어 `/workspace/exports/battle_viewers/ex127/index.html`(오프라인 1440px·390px, 256경기, 페이지 오류 0)

## 분석 및 한계

- 상대 Abyssal은 테라를 쓰지 않는다(EX-120 0/128).
- 128쌍 차이로 작은 효과는 구별되지 않을 수 있다.
- 실패 기술 지표는 같은 기술을 반복하는 정도에도 영향을 받는다. 판정에는 쓰지 않는다.

## 결론 및 후속 작업

- 효과 지식 행은 Abyssal 상대 배틀 성적을 개선하지 못했다. 점추정은 −0.070이고, 실패 기술 비율은 5.75% → 5.29%로 거의 같다(지식 행이 행동을 바꾸지 못한 EX-126과 같은 양상).
- 실패 반복은 [EP-215](../plans/EP-215-laya-renderer-v4.md)(렌더러 v4)에서, 학습 목표 변경은 [EP-216](../plans/EP-216-laya-outcome-weighted-imitation.md)(승패 가중 모방)에서 다룬다.
