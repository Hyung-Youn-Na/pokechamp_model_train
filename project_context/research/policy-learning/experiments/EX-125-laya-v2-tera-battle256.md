# EX-125 — laya v2와 v2+테라 지식 같은 실행 256경기(GPU1, EX-120 일정)

- 상태: Completed
- 생성일: 2026-10-23
- 책임자: Claude Code
- 관련 exec plan: [EP-212](../plans/EP-212-laya-tera-knowledge.md)
- 관련 decision: [D-187](../decisions/D-187-laya-tera-knowledge.md)
- 선행: [EX-124](EX-124-laya-v2-tera-knowledge-training.md), [EX-121](EX-121-laya-v2-all-training.md), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

같은 일정과 같은 상대(Abyssal)에서 테라 지식을 더한 v2 모델이 v2보다 배틀 성적이 나은가? 테라를 실제로 더 쓰는가?

## 가설 또는 qualification 목표

- **qualification**: 모델별 128슬롯이 처리되고 분모 산술이 맞으며 봉인된다.
- **판정**(실행 전 동결): 같은 슬롯 점수 차이(`laya-v2t` − `laya-v2`)를 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261025)로 본다.
  - 하한 > 0 → "v2+테라가 배틀 성적을 개선"
  - 상한 < 0 → "악화"
  - 그 외 → "구별되지 않음"
  - 어느 모델이든 정상 종료가 120/128 미만이면 판정을 보류한다.
- **테라 지표**(보고, 판정 외):
  - 모델별 테라 사용 경기 수(protocol `|-terastallize|`), 결정당 테라 선택률, 테라 턴
  - 테라 사용 경기의 승패
  - 사람 기준(경기 78.8%, 결정 3.41%)과 EX-120 v1(14%, 0.39%)과 비교

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-v2 | EX-120 봉인 일정 128슬롯, Abyssal, 300턴/600결정, `laya-compact-v2[damage,moves,speed,switch]`, GPU1 서빙 | EX-121 selected | `runs/model-training/EX-125/games/v2-*` |
| laya-v2t | 같음 | EX-124 selected | `runs/model-training/EX-125/games/v2t-*` |

- **진행 순서**: EX-122와 같은 구조로, EX-120 쌍마다 두 모델 쌍을 연달아 둔다. 먼저 할 모델은 `digest([20261025,'ex125_first',pair_id])`로 정한다.
- **fallback, 재질의, 재경기**: 없다. 단일 후보는 자동 제출한다.
- **분모**: 모델별 예정 128
- **단계 상한**: 10시간

## 환경 및 출처

- 배틀: `pokechamp/.venv`, `BattleServer`, 포트 8109(`port8109.lock`)
- 서빙: laya venv, GPU1(`gpu1.lock`, UUID 확인), node 계산기
- 실행기: `scripts/laya-imitation compare2 {mock,prepare,execute,export}`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-125`

## 격리 및 오염 통제

- **일정**: EX-120 collection 봉인을 확인한 뒤 일정을 복사한다.
- **자원 분리**: EX-122(GPU0·8107)와 동시에 진행할 수 있다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex125/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)
- **viewer 생성기**: `laya-imitation-researcher-v1`. 목록에 모델, 조합, 시드, 테라 사용 열을 둔다. 압축 입력 탭은 v2 렌더러로 복원한다.
- **viewer 출력 판본과 변경일지**: v1, [변경일지](../../../shared/viewers/CHANGELOG.md)에 항목을 추가한다.
- **공유 상태 예외**: 없다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. mock: v2 렌더러와 EX-124 시작 체크포인트로 CPU 2경기를 한다. 분모 밖이다.
2. prepare: EX-121과 EX-124의 완료와 봉인, 렌더러 일치, 일정 봉인을 확인하고 동결한다.
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
| 배틀 run | `/mnt/.../runs/model-training/EX-125` | `checksums.sha256` (sha256 `df426388…`), `report.md` (`5628e389…`) | Sealed |
| 뷰어 | `/workspace/exports/battle_viewers/ex125/index.html` | `checksums.sha256` | Sealed, [오프라인 검사](../../../exec-plans/evidence/ep212/viewer-check.json), [리플레이 검사](../../../exec-plans/evidence/ep212/viewer-replay-check.json) |

## 결과

- **실행**: 2026-10-23 11:16 ~ 13:45 UTC, GPU1, 포트 8109
  - 체크포인트: v2 `f3e60754…`, v2t `12519d98…`
  - mock 2경기 정상, 결함 복구 없음
- **분모**: 모델별 128/128 정상 종료하고 전 경기 감사를 통과했다.

| 모델 | 승/무/패 | 평균 점수 | 조합 클러스터 95% | 교환쌍 2승/1승1패/2패 |
|---|---|---:|---|---|
| v2 (EX-121) | 102/0/26 | 0.797 | [0.734, 0.859] | 40/22/2 |
| v2+테라 (EX-124) | **111/0/17** | **0.867** | [0.805, 0.922] | 47/17/0 |

- **판정**(동결): 같은 슬롯 차이 평균 +0.0703, 조합 클러스터 95% [**+0.0000**, +0.1406] → **"구별되지 않음"**
  - 하한이 정확히 0이라 "하한 > 0"을 충족하지 못했다.
  - v2t 우세 18, v2 우세 9, 같음 101
- **재현성**: v2의 128슬롯 결과와 턴 수가 EX-122의 v2와 128/128 같다.
- **테라 사용**:
  - v2: 16/128경기(결정 0.35%), 테라 경기 11승 5패
  - v2t: **22/128경기**(0.46%), 테라 경기 **21승 1패**
  - 사람은 78.8%(3.41%)다.
- **실패·무효 기술**(다른 세션 추가 지표):
  - v2 134/3,713(3.61%)
  - v2t 240/4,177(5.75%). Sleep Talk 43/100, Whirlwind 39/81, Wish 24/56
  - v2t는 Spikes 반복 실패가 74회에서 16회로 줄었지만, 다른 기술의 실패가 늘었다.

## 분석 및 한계

- 상대 Abyssal은 테라를 쓰지 않는다(EX-120 0/128).
- 128쌍 차이로 작은 효과는 구별되지 않을 수 있다.

## 결론 및 후속 작업

- 테라 지식 모델은 성적이 더 높았지만(+0.07, 111승 대 102승), 동결 기준으로는 v2와 구별되지 않는다(구간 하한 0).
- 테라 사용은 16경기에서 22경기로 조금 늘었다. 사람 수준(약 79%)과는 여전히 거리가 멀다.
- 오프라인 판정은 EX-124의 "개선 없음"이다. 배틀 차이가 테라 지식 때문인지, 학습량 증가 때문인지는 분리하지 않았다.
- **후속 후보**(별도 승인):
  - 테라 결정 분리(기술 선택 후 테라 여부를 따로 판단)
  - 결과 기반 학습
  - 반복 실패 행동 억제
  - 같은 결론이 다른 시드나 다른 상대에서도 나오는지 확인
