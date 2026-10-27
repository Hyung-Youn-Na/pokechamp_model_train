# EX-119 — laya 압축 입력 모방 모델 EX-089 표준 32경기

- 상태: Completed
- 생성일: 2026-10-22
- 책임자: Claude Code
- 관련 exec plan: [EP-208](../plans/EP-208-laya-compact-imitation.md)
- 관련 decision: [D-183](../decisions/D-183-laya-compact-imitation.md)
- 선행: [EX-118](EX-118-laya-compact-imitation-training.md)의 selected checkpoint
- 기준 연구선: `research/model-training`

## 질문 및 목적

EX-118 선택 모델이 압축 입력으로 실제 Gen9 OU 배틀을 완주하는가? EX-089 표준 32경기에서 승/무/패는 어떻게 나오는가? 로컬 소형 판정 모델을 배틀 에이전트로 쓸 수 있는지를 처음 확인하는 탐색 평가다.

## 가설 또는 qualification 목표

탐색적 실험이다.
- **qualification**: 32경기 전부가 정상 종료하고, 실행 불가능한 선택이 0이다.
- 성적은 방향성 관찰로만 보고한다. 같은 일정의 기존 결과(EX-089 JEV-9B 6-0-26, EX-110 gpt-6-luna 16-0-16, EX-111 JevK5 2-0-30)는 상속 근거로 나란히 표시할 뿐, 이번 실행 안의 기준선이 아니다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-selected | EX-089 고유 32슬롯, 16 진영교환쌍, 팀, battle seed, actor seed, 순서, Abyssal 상대, Gen9 OU, Tera 허용, timer off | EX-118 selected의 압축 입력 정책 | `runs/model-training/EX-119/collection/` |

- **정책**: `ImitationInput`(C-055) → `compact.render` v1 → laya `Agent` → 보정 확률의 argmax 후보를 실행한다. 확률은 행동 선택 확률이며 승률이 아니다.
- **단일 후보**: 추론 없이 자동 제출한다.
- **fallback, 재질의, 재경기**: 없다. 실행 불가능한 선택은 그 경기의 실패다(C-046).
- **경기 제한**: 300턴, 600결정. 넘은 경기는 미완료로 분리하고 패배로 바꾸지 않는다.
- **동시성**: 경기 1개씩 순차 진행한다. 서빙은 loopback 1개, GPU0이다.
- **지표**:
  - 승/무/패, 평균 점수 `(승+0.5무)/정상 종료`
  - 정상 완료율, 완료 쌍 수
  - 진영교환쌍 bootstrap(10,000회) 95% 구간
  - 결정 수, 자동 제출 수, 추론 지연 중앙값과 p95
- **분모**: 예정 32 = 정상 + 실패 + 미완료 + 무효 + 미실행.
- **중단 규칙**: 수집 결함(입력 경계, 관측, 전송, 무결성)이 생기면 의존하는 수집을 중지한다. 단계 전체 상한은 6시간이다.

## 환경 및 출처

- branch, commit: `research/model-training` `feda62f7…`. 새 파일과 미커밋 목록은 `source/`에 보존한다.
- actor, 배틀: `pokechamp/.venv/bin/python`. Showdown은 `integration/pokechamp/parallel_server.BattleServer`, 포트는 8107(`port8107.lock`)이다.
- 서빙: `.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python -m integration.laya_imitation.serving`. loopback, GPU0이다.
- 일정: EX-089 `collection/manifest.json`과 `checksums.sha256`. 봉인을 확인한 뒤 복사한다.
- 모델: EX-118 `checkpoints/selected/`. 파일 SHA를 manifest에 기록한다.
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-119`
- 실행기: `scripts/laya-imitation battle {mock,prepare,execute,status,export}`

## 격리 및 오염 통제

- **학습 자료와 분리**: EX-089 팀은 학습 자료에 없음을 EX-118 자료 감사에서 확인한다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)을 따른다. 위치는 `/workspace/exports/battle_viewers/ex119/index.html`이고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)
- **viewer 생성기**: `integration/laya_imitation/viewer.py`. `integration/openai_decisions_battle/viewer.py`의 리플레이·턴 로그 경로를 재사용한다. 렌더러 판본과 소스 해시는 export manifest에 기록하고, 실행 전에 지원 여부를 확인해 EP-208에 남긴다.
- **viewer 확장 탭**: 압축 입력 원문과 후보별 확률
- **viewer 출력 판본과 변경일지**: v1, [변경일지](../../../shared/viewers/CHANGELOG.md)에 항목 추가
- **공유 상태 예외**: 없다.
- **재개**: 슬롯 원장을 기준으로 미실행 슬롯만 이어서 수행한다. 시도한 슬롯은 재경기하지 않는다.
- **과거 자료**: 없다.

## 절차

1. mock: CPU 모의 2경기로 서빙, player, 감사, viewer 전 경로를 확인한다. 결과는 성적 분모에 넣지 않는다.
2. prepare: EX-089 일정을 복사하고 봉인을 확인한다. source, 모델, protocol을 동결한다.
3. execute: 32슬롯을 순차 수행한다. 경기마다 입력, 선택, 실제 전송, 종료 감사를 한다.
4. export: 보고, 뷰어, 봉인을 만들고 Showdown, Abyssal, 포트, GPU를 반환한다.

## 승인·무효화·중단 조건

- **승인**: 32슬롯 처리 완료, 분모 산술, 봉인
- **무효 시도**: 입력 경계 위반, 모델이나 입력의 신원 불일치
- **안전과 시간 중단**: 단계 6시간 상한

## 테스트·평가 도구 결함 복구

- 공통 절차와 C-018을 적용한다.
- 관측, 전송, 감사 도구 결함으로 오염된 경기의 재수집은 결함 수정과 독립 검증 후 해당 슬롯에 한해 1회까지 허용한다. 원본은 보존하고 별도 판본으로 연결한다.
- 모델의 전략적 오답은 결함이 아니다.
- 결함 기록 위치: run `diagnostics/`

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-119` | `checksums.sha256` (sha256 `0fae39d6…`), 보고 `report.md` (sha256 `28a2bb28…`) | Sealed |
| 뷰어 | `/workspace/exports/battle_viewers/ex119/index.html` | `checksums.sha256`, `provenance.json` | Sealed, [오프라인 검사](../../../exec-plans/evidence/ep208/viewer-final-check.json), [리플레이 검사](../../../exec-plans/evidence/ep208/viewer-replay-check.json) |

## 결과

- **실행**: 2026-10-22, EX-118 선택 체크포인트(epoch 2, `model.safetensors` 등 identity는 `manifest.json`), GPU0 서빙, 포트 8107. 약 19분에 32슬롯을 모두 시도했다. 결함 복구와 재수집은 없다(mock v1 결함은 본 실행 전 `diagnostics/mock-v1`에 보존).
- **분모**: 예정 32, 정상 32, 실패·미완료·무효·미실행 0. 32경기 모두 경기별 감사를 통과했다.
- **성적**: **25승 0무 7패**, 평균 점수 0.7812. 진영교환쌍 16/16 완료, 쌍 bootstrap 95% 구간 [0.6562, 0.9062].
- **진영별**: p1 13승 3패, p2 12승 4패. 16쌍 중 10쌍은 양쪽 모두 승리, 6쌍은 1승 1패, 양쪽 모두 패한 쌍은 없다.
- **결정**: 총 1,433결정 중 모델 질의 1,420, 단일 후보 자동 제출 13. 전송 행동은 기술 904, 교체 529. HTTP 왕복 지연은 중앙값 0.118초, p95 0.140초다.
- **경기 길이**: 17~107턴, 중앙값 26턴. 300턴·600결정 제한에 걸린 경기는 없다.
- **같은 일정의 상속 근거**(이번 실행의 기준선 아님): EX-089 JEV-9B 6-0-26, EX-110 gpt-6-luna 16-0-16, EX-111 JevK5-9B 2-0-30.

## 분석 및 한계

- 고정된 4팀, 16쌍, 단일 상대에 대한 탐색 결과다. 일반 승률을 주장하지 않는다.
- 쌍 bootstrap은 16쌍만으로 계산한 구간이며 팀·상대 다양성의 불확실성은 포함하지 않는다.
- 확률은 사람 행동 모방 확률이며 승률이 아니다.

## 결론 및 후속 작업

- 압축 입력 laya 모방 모델(약 0.4B)은 이 일정에서 기존 상속 결과 중 가장 높은 성적을 냈다. 모델, 입력, 실행 시점이 모두 달라 원인은 분리하지 않았다.
- 단일 상대(Abyssal)와 고정 4팀이므로 상대 정책에 대한 적합 여부를 확인하지 못했다. 새 상대, 새 팀, 반복 시드로 일반화를 확인하는 실험은 새 승인 대상이다.
- 렌더러 v1 한계(날씨에 따른 Weather Ball 변화 등 기술 변형 미반영)와 자발 교체 일치율 21%(EX-118)가 개선 후보다.
