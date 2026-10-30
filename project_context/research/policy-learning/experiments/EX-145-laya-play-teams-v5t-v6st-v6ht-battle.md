# EX-145 — laya-play 완성 팀 74개로 v5t·v6st·v6ht 대 Abyssal(GPU2)

- 상태: Planned
- 생성일: 2026-10-30
- 책임자: Claude Code
- 관련 exec plan: [EP-222](../plans/EP-222-laya-play-teams-abyssal-battle.md)
- 관련 decision: [D-199](../decisions/D-199-laya-play-teams-abyssal-battle.md), [D-198](../decisions/D-198-laya-past-turn-input-v6.md)
- 선행: [EX-136](EX-136-laya-v5-tera-training.md), [EX-141](EX-141-laya-v6s-streaks-training.md), [EX-142](EX-142-laya-v6h-long-history-training.md)(모두 학습 완료), 비교 [EX-143](EX-143-laya-v5t-v6st-battle256.md)·[EX-144](EX-144-laya-v5t-v6ht-battle256.md)(EX-120 일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

사람이 짠 완성 팀(Smogon gen9ou 샘플, Blim pokepaste)으로 Abyssal과 두었을 때, v6st와 v6ht가 v5t보다 배틀 성적이 나은가? EX-120 재구성 팀 결과(EX-143·EX-144)와 같은 방향인가?

## 가설 또는 qualification 목표

- **qualification**: 모델별 296슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **판정**(실행 전 동결): 쌍마다 같은 슬롯 점수 차이를 조합(74) 클러스터 bootstrap 95%(10,000회)로 본다. 시드는 v6st − v5t 20261037, v6ht − v5t 20261038이다.
  - 하한 > 0 → "개선"
  - 하한 > −0.05 → "비퇴보"
  - 그 외 → "퇴보를 배제하지 못함"
  - 어느 모델이든 정상 종료가 280/296 미만이면 판정을 보류한다.
- **보고 지표**(판정 외):
  - 모델별 승패, 팀 묶음별(smogon / blim) 승률, 학습 노출 여부별(`train_games` 0 / 그 외) 승률
  - EX-143·EX-144(EX-120 일정)와의 방향 비교
  - 같은 활성 포켓몬의 같은 기술 3턴 이상 연속 구간 수, 실패·무효 기술 비율(`comparison.failed_moves`), 테라 사용, 결정 지연

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-v5t | EX-145 일정 296슬롯, Abyssal, 300턴/600결정, GPU2 서빙 | EX-136 selected, `v5` | `runs/model-training/EX-145/games/v5t-*` |
| laya-v6st | 같음 | EX-141 selected, `v6s` | `runs/model-training/EX-145/games/v6st-*` |
| laya-v6ht | 같음 | EX-142 selected, `v6h`(2,048토큰, `early_history`) | `runs/model-training/EX-145/games/v6ht-*` |

### 일정 (`teamset_battle.collect`)

- 팀: laya-play v1.6.0 `teams.json`(11)과 `teams_blim.json`(65). 6종족 서명이 같은 팀은 처음 나온 하나만 남겨 74팀이다. 고정 로컬 Showdown `gen9ou` 검증기를 다시 통과해야 한다.
- 원형 배열: `digest([20261037, 'ex145_ring', 서명])` 순서. 조합 m은 (팀 m, 팀 m+1 mod 74)다.
- 조합마다 시드 2개, 팀 교환(a/b)이고, 시드는 EX-120과 같은 방식(`digest`)으로 정한다. 진행 순서는 EX-120처럼 쌍 단위 digest 순서이고, 같은 쌍에서 세 모델을 연달아 둔다(첫 모델 순서는 digest).
- **fallback, 재질의, 재경기**: 없다. 단일 후보는 자동 제출한다.
- **분모**: 모델별 예정 296
- **단계 상한**: 16시간

## 환경 및 출처

- 배틀: `pokechamp/.venv`, `BattleServer`, 포트 8108(`port8108.lock`)
- 서빙: laya venv, GPU2(`GPU-c79ce3fd-81e7-454b-75ce-e63fad63baa4`, `gpu2.lock`), node 계산기. 서빙 3개를 함께 띄운다(v6ht 약 20 GB 확보).
- 실행기: `scripts/laya-imitation teamset {collect,mock,prepare,execute,export}`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-145`

## 격리 및 오염 통제

- 일정은 결과를 보기 전에 만들고 봉인한다.
- 자원 분리: GPU0·GPU1·GPU3과 그 포트는 쓰지 않는다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex145/index.html`에 둔다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1), 생성기 `laya-imitation-researcher-v1`. 압축 입력 탭은 모델별 렌더러(v5/v6s/v6h)로 복원한다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. collect: 팀 수집·검증·일정, 봉인
2. mock: v6h 렌더러와 기반 체크포인트(`laya-v6ht-initial`, CPU)로 첫 쌍 2경기. 분모 밖이다.
3. prepare: 세 체크포인트의 완료·봉인, 렌더러 일치, 일정 봉인을 확인한 뒤 동결한다.
4. execute: 888슬롯을 진행하고 경기별로 감사한다.
5. export: 보고, 뷰어, 봉인

## 승인·무효화·중단 조건

- **승인**: 888슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **무효**: 입력 경계 위반, 신원 불일치, 감사 실패(그 경기만)
- **중단**: 16시간 상한, 수집 결함(phase 오류)

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯만 수정과 독립 검증을 거친 뒤 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 일정 | `/mnt/.../runs/model-training/EX-145/collection` | `checksums.sha256` | 예정 |
| 배틀 run | `/mnt/.../runs/model-training/EX-145` | `checksums.sha256`, `report.md` | 예정 |
| 뷰어 | `/workspace/exports/battle_viewers/ex145/index.html` | `checksums.sha256` | 예정 |

## 결과

진행 전.

## 분석 및 한계

- 상대는 Abyssal 하나이고 테라를 쓰지 않는다.
- 74팀 중 24팀은 같은 6종족 조합이 학습 리플레이에 있다(노출 여부로 나눠 보고한다).
- 팀 유형이 고르지 않다.

## 결론 및 후속 작업

진행 전.
