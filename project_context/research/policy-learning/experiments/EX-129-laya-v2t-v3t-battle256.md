# EX-129 — laya v2+테라와 v3+테라 같은 실행 256경기(GPU0, EX-120 일정)

- 상태: Completed
- 생성일: 2026-10-25
- 책임자: Claude Code
- 관련 exec plan: [EP-214](../plans/EP-214-laya-renderer-v3.md)
- 관련 decision: [D-189](../decisions/D-189-laya-renderer-v3-opponent-sets.md), [D-190](../decisions/D-190-laya-ex129-gate-override.md)(진행 조건 이탈)
- 선행: [EX-128](EX-128-laya-v3-tera-training.md)(진행 조건), [EX-124](EX-124-laya-v2-tera-knowledge-training.md), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

같은 일정과 같은 상대(Abyssal)에서 v3 입력 모델이 v2+테라보다 배틀 성적이 퇴보하지 않는가? Abyssal은 숨은 정보를 노리지 않으므로 개선은 기대하지 않는다. 래더로 가기 전의 비퇴보 확인이다.

## 가설 또는 qualification 목표

- **진행 조건**: EX-128 판정에서 주 지표 S 개선 또는 비열등 N 충족. 미충족이면 실행하지 않고 그 사실을 기록한다.
  - **이탈**: EX-128은 미충족이었다(N 상한 +0.020034 > +0.02). 사용자 결정으로 [D-190](../decisions/D-190-laya-ex129-gate-override.md)에 기록하고 실행한다. 나머지 설계와 판정은 동결된 그대로다.
- **qualification**: 모델별 128슬롯이 처리되고 분모 산술이 맞으며 봉인된다.
- **판정**(실행 전 동결): 같은 슬롯 점수 차이(`laya-v3t` − `laya-v2t`)를 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261027)로 본다.
  - 하한 > 0 → "v3+테라가 배틀 성적을 개선"
  - 하한 > −0.05 → "비퇴보"
  - 그 외 → "퇴보를 배제하지 못함"
  - 어느 모델이든 정상 종료가 120/128 미만이면 판정을 보류한다.
- **보고 지표**(판정 외):
  - 실패·무효 기술 비율(`comparison.failed_moves`)
  - 테라 사용
  - EX-125의 v2+테라 111-0-17과 같은 체크포인트 결과 비교

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-v2t | EX-120 봉인 일정 128슬롯, Abyssal, 300턴/600결정, GPU0 서빙 | EX-124 selected, `laya-compact-v2[damage,moves,speed,switch]` | `runs/model-training/EX-129/games/v2t-*` |
| laya-v3t | 같음 | EX-128 selected, `laya-compact-v3[damage,moves,oppset,speed,speedp,switch,threat]` | `runs/model-training/EX-129/games/v3t-*` |

- **진행 순서**: EX-125와 같은 구조다. EX-120 쌍마다 두 모델 쌍을 연달아 두고, 먼저 할 모델은 `digest([20261027,'ex129_first',pair_id])`로 정한다.
- **fallback, 재질의, 재경기**: 없다. 단일 후보는 자동 제출한다.
- **분모**: 모델별 예정 128
- **단계 상한**: 10시간

## 환경 및 출처

- 배틀: `pokechamp/.venv`, `BattleServer`, 포트 8107(`port8107.lock`)
- 서빙: laya venv, GPU0(`gpu0.lock`, UUID 확인), node 계산기. v3 서빙은 매 결정에서 세트 추론과 위협 피해를 실시간으로 계산한다.
- 실행기: `scripts/laya-imitation compare4 {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ex129`(2026-10-25 23:4xZ 시작, 로그 `runs/model-training/EX-129-chain.log`)
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-129`

## 격리 및 오염 통제

- **일정**: EX-120 collection 봉인을 확인한 뒤 일정을 복사한다.
- **자원 분리**: EX-127(GPU2·8108)과 동시에 진행할 수 있다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex129/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)
- **viewer 생성기**: `laya-imitation-researcher-v1`. 압축 입력 탭은 모델별 렌더러(v2, v3)로 복원한다.
- **viewer 출력 판본과 변경일지**: v1, [변경일지](../../../shared/viewers/CHANGELOG.md)에 항목을 추가한다.
- **공유 상태 예외**: 없다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. 진행 조건 확인(EX-128 `status.json`의 `battle_gate`)
2. mock: v3 렌더러와 시작 체크포인트로 CPU 2경기를 한다. 분모 밖이다.
3. prepare: EX-124와 EX-128의 완료와 봉인, 렌더러 일치, 일정 봉인을 확인하고 동결한다.
4. execute: 256슬롯을 진행하고 경기별로 감사한다.
5. export: 보고, 뷰어, 봉인, 자원 반환

## 승인·무효화·중단 조건

- **승인**: 256슬롯 처리, 분모 산술, 봉인
- **무효**: 입력 경계 위반, 신원 불일치
- **중단**: 10시간 상한, 수집 결함

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯만 수정과 독립 검증 뒤 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-129` | `checksums.sha256`, `report.md` | 봉인 |
| 뷰어 | `/workspace/exports/battle_viewers/ex129/index.html` | `checksums.sha256` | 생성. 오프라인 브라우저 검사·상위 목록 연결·변경일지는 미실행 |

## 결과

2026-10-25 23:41Z mock(2경기 정상) → 23:42Z execute → 2026-10-26 02:12Z export 완료. 모델별 128/128 정상 종료, 실패·무효·미실행 0, 전 경기 감사 통과.

| 모델 | 승/무/패 | 평균 점수 | 조합 클러스터 95% | 교환쌍 2승/1승1패/2패 | 지연 p50 |
|---|---|---:|---|---|---:|
| laya-v2t (EX-124) | 111/0/17 | 0.867 | [0.805, 0.922] | 47/17/0 | 0.127초 |
| laya-v3t (EX-128) | 104/0/24 | 0.812 | [0.750, 0.875] | 40/24/0 | 0.135초 |

- **판정**(동결): 같은 슬롯 차이(v3t − v2t) −0.0547, 95% [−0.1250, +0.0078] → **"퇴보를 배제하지 못함"**. v3t 우세 8, v2t 우세 15, 같음 105.
- **재현**: laya-v2t는 EX-125와 같은 111-17이다(같은 체크포인트, 결정적 경로).
- **실패·무효 기술**: v2t 240/4,177(5.75%), v3t 240/3,839(6.25%). v3t는 **Spikes 53/95** 실패, Sleep Talk 49/89, Will-O-Wisp 26/56이다.
- **테라 사용**: v2t 22경기(21승 1패), v3t 24경기(17승 7패)
- **진행 조건 이탈**: EX-128 진행 조건 미충족 상태에서 D-190으로 실행했다.

## 분석 및 한계

- Abyssal 한 상대의 비퇴보 확인이다. 래더(사람) 효과는 이 실험으로 입증되지 않는다.

## 결론 및 후속 작업

- v3 상대 세트 추론은 Abyssal 상대 비퇴보를 보이지 못했다. 점추정은 −0.055이고, Spikes 실패 반복이 v2t보다 많다.
- 래더 평가 계획은 올리지 않는다. 실패 반복 문제는 [EP-215](../plans/EP-215-laya-renderer-v4.md)(렌더러 v4, v2 위)에서 다룬다.
