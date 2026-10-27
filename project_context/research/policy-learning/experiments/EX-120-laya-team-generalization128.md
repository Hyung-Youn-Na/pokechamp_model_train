# EX-120 — laya 모방 모델 새 팀 128경기 일반화 평가

- 상태: Completed
- 생성일: 2026-10-22
- 책임자: Claude Code
- 관련 exec plan: [EP-209](../plans/EP-209-laya-team-generalization.md)
- 관련 decision: [D-184](../decisions/D-184-laya-team-generalization.md)
- 선행: [EX-119](EX-119-laya-compact-imitation-battle32.md)(25승 0무 7패), [EX-118](EX-118-laya-compact-imitation-training.md) selected checkpoint
- 기준 연구선: `research/model-training`

## 질문 및 목적

EX-119의 평균 점수 0.7812가 처음 보는 팀 조합에서도 유지되는가? 모델, 입력, 상대를 고정하고 팀과 대진만 바꿔 Abyssal 상대 일반 성능을 측정한다.

## 가설 또는 qualification 목표

탐색적 평가다. 판정 기준은 실행 전에 아래와 같이 동결한다.

- **분모**: 정상 종료 경기. 정상 종료가 120/128 미만이면 일반화 판정을 보류한다.
- **1차 판정**(조합 클러스터 bootstrap 95% 구간, 32개 조합, 10,000회, 시드 20261023):
  - 하한 > 0.5 → "새 팀에서도 Abyssal보다 우세"
  - 하한 ≤ 0.5이고 점추정 ≥ 0.5 → "우세 불확실"
  - 점추정 < 0.5 → "우세 유지 실패"
- **EX-119와 비교**(서로 다른 실행이므로 상속 근거로만 쓴다):
  - 조합 bootstrap 상한 < 0.7812 → "EX-089 4팀 결과는 일반 수준보다 높았다"
  - 그 외 → "EX-119 수준과 구별되지 않음"

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-selected | EX-118 selected(`model.safetensors` 포함 identity sha `403581f2…`), `laya-compact-v1`, 보정 확률 argmax, Abyssal, Gen9 OU, Tera 허용, timer off, 300턴/600결정 | 새 팀 32개, 32조합, 시드 2, 팀 교환 | `runs/model-training/EX-120/` |

### 팀 후보와 제외

- **후보**: `export/teams/gen9ou_reviewed108_teams.json`의 16,034팀. 팀 파일 sha256을 대조한다.
- **6종족 서명 제외**:
  1. EX-071 리플레이 2,793경기의 양측 팀(`preparation/replays.jsonl`)
  2. 과거 고정 팀과 예약 팀(`preparation/historical-teams.json`)
  3. EX-071 배틀 팀(`schedule.json`)
  4. EX-089 4팀
- **합법성**:
  - EX-071 `teams.cjs` 검증기(고정된 로컬 Showdown `gen9ou`)를 통과해야 한다.
  - 정규화 후 종족은 reviewed108 안에 있어야 한다.
  - 정규화 전후 서명이 같아야 한다.

### 유형 분류 (팀 단위, 아래 순서로 처음 해당하는 유형)

1. **weather**: 특성 `drought, drizzle, sandstream, snowwarning, orichalcumpulse, hadronengine, electricsurge, psychicsurge, grassysurge, mistysurge` 중 하나를 가진 포켓몬이 있거나, 팀 전체에 기술 `sunnyday, raindance, sandstorm, snowscape, chillyreception, electricterrain, psychicterrain, grassyterrain, mistyterrain`이 2개 이상 있다.
2. **offense**: 셋업 기술 보유 포켓몬이 3마리 이상이다. 또는 공격 도구(`choiceband, choicespecs, choicescarf, lifeorb, boosterenergy`) 보유 포켓몬이 4마리 이상이면서 회복 기술 보유 포켓몬이 1마리 이하다.
3. **defense**: 회복 기술 보유 포켓몬이 4마리 이상이다. 또는 3마리이면서 해저드 설치 기술과 해저드 제거 기술이 둘 다 팀에 있다.
4. **balance**: 나머지

기술 목록:

| 구분 | 기술 |
|---|---|
| 셋업 | `swordsdance, nastyplot, dragondance, calmmind, bulkup, quiverdance, shellsmash, agility, rockpolish, bellydrum, tidyup, victorydance, coil, shiftgear, curse, irondefense, filletaway, clangoroussoul, noretreat, workup, growth, geomancy, tailglow, cosmicpower, takeheart` |
| 회복 | `recover, roost, slackoff, softboiled, moonlight, morningsun, synthesis, wish, strengthsap, shoreup, milkdrink, rest, lunarblessing, junglehealing, healorder` |
| 해저드 설치 | `stealthrock, spikes, toxicspikes, stickyweb` |
| 해저드 제거 | `rapidspin, defog, mortalspin, tidyup, courtchange` |

### 선정과 대진

- **순서**: 후보를 `digest([20261023, 'ex120_team', 팀 경로])` 오름차순으로 훑는다.
- **선정 조건**: 유형마다 8팀까지, 다음 조건을 모두 만족하면 선택한다.
  - 이미 고른 팀과 서명이 겹치지 않는다.
  - 이미 고른 어느 팀과도 공유 종족이 3마리 이하다.
  - 한 종족은 최대 8팀까지만 등장한다.
  - 합법성 검증을 통과한다.
- **부족분 처리**: 어떤 유형이 8팀에 못 미치면 같은 순서로 다른 유형의 팀을 골라 32팀을 채운다. 부족 수는 manifest에 기록한다.
- **대진**: 32팀을 `digest([20261023,'ex120_ring',서명])` 순서로 원형 배열한다. 조합 m은 (팀 m, 팀 m+1 mod 32)이다. 각 팀은 서로 다른 두 팀과 한 번씩 만난다.
- **슬롯 구성**: 조합 × 시드 s∈{1,2} × 교환 {a,b}로 128슬롯을 만든다.
  - `a`: laya가 팀 A를 맡고 Abyssal이 팀 B를 맡는다.
  - `b`: 두 팀을 바꾼다.
  - laya의 자리는 s=1이면 p1, s=2이면 p2다.
  - pair_id는 `조합-시드`(64쌍)다.
- **시드**: `digest([20261023,'ex120_seeds',조합,s,교환])`에서 simulator seed 4개와 상대·모델 seed를 만든다. 방식은 EX-071 `make_schedule`과 같다.
- **진행 순서**: 쌍 순서는 `digest([20261023,'ex120_order',pair_id])`, 쌍 안에서는 a 다음 b다.

### 지표와 규칙

- **지표**:
  - 승/무/패, 평균 점수, 정상 완료율
  - 진영교환쌍 bootstrap과 조합 클러스터 bootstrap
  - 팀별 점수: laya가 맡았을 때와 Abyssal이 맡았을 때
  - 유형 × 유형 점수
  - 시드별 점수와 시드 간 엇갈림 비율
  - 교환쌍 결과 분포(2승, 1승 1패, 2패)
  - 패배 경기의 턴 수와 남은 포켓몬 수
  - 결정 수, 자동 제출 수, 지연
- **분모**: 예정 128 = 정상 + 실패 + 미완료 + 무효 + 미실행
- **fallback, 재질의, 재경기**: 없다. 실행 불가능한 선택은 실패다(C-046). 단일 후보는 자동 제출한다.
- **중단 규칙**: 수집 결함(입력 경계, 관측, 전송, 무결성)이 생기면 중지한다. 단계 상한은 8시간이다.

## 환경 및 출처

- branch, commit: `research/model-training` `feda62f7…`. 소스 identity는 `source/`에 기록한다.
- **배틀**: `pokechamp/.venv`, `BattleServer`, 포트 8107(`port8107.lock`)
- **서빙**: laya venv, loopback, GPU0(`gpu0.lock`, UUID 확인)
- **모델**: EX-118 `checkpoints/selected/`
- **출력**: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-120`
  - `collection/`(팀, 일정, 봉인)
  - `mock/`(분모 밖)
  - 본 실행 원장
- **실행기**: `scripts/laya-imitation general {collect,mock,prepare,execute,export}`

## 격리 및 오염 통제

- **결과 전 동결**: 팀 선정과 일정은 결과를 보기 전에 생성하고 봉인한다.
- **학습 노출 한계**: 개별 세트는 EX-071 결측 보완 corpus(같은 풀)에 들어 있었을 수 있다. 6종족 조합과 대진은 학습과 기존 평가에 없었다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex120/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)
- **viewer 생성기**: `laya-imitation-researcher-v1`(EX-119와 같다). 확장 탭은 `압축 입력 → 선택지 확률 → 선택·전송`이다.
- **viewer 출력 판본과 변경일지**: v1, [변경일지](../../../shared/viewers/CHANGELOG.md)에 항목을 추가한다.
- **공유 상태 예외**: 없다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다. 시도한 슬롯은 다시 하지 않는다.

## 절차

1. **collect**: 팀 선정, 감사, 일정을 만들고 봉인한다.
2. **mock**: 첫 쌍을 시작 체크포인트로 CPU 2경기 진행한다. 분모에는 넣지 않는다.
3. **prepare**: EX-118 봉인, 렌더러 일치, collection 봉인을 확인한다. protocol, source, 체크포인트를 동결한다.
4. **execute**: 128슬롯을 순차로 진행하고 경기별로 감사한다.
5. **export**: 보고, 뷰어, 봉인을 만들고 자원을 반환한다.

## 승인·무효화·중단 조건

- **승인**: 128슬롯 처리, 분모 산술, 봉인
- **무효 시도**: 입력 경계 위반, 모델이나 입력의 신원 불일치
- **중단**: 단계 8시간 상한, 수집 결함

## 테스트·평가 도구 결함 복구

- C-018과 EX-119 절차를 적용한다.
- 도구 결함으로 오염된 경기는 수정과 독립 검증을 거친 뒤 해당 슬롯만 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다.
- 모델의 전략적 오답은 결함이 아니다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| collection | `/mnt/.../runs/model-training/EX-120/collection` | `checksums.sha256` (sha256 `c707c734…`) | Sealed (결과 전) |
| 배틀 run | `/mnt/.../runs/model-training/EX-120` | `checksums.sha256` (sha256 `dc253742…`), `report.md` (sha256 `62e47c4a…`) | Sealed |
| 뷰어 | `/workspace/exports/battle_viewers/ex120/index.html` | `checksums.sha256`, `provenance.json` | Sealed, [오프라인 검사](../../../exec-plans/evidence/ep209/viewer-check.json), [리플레이 검사](../../../exec-plans/evidence/ep209/viewer-replay-check.json) |

## 결과

### 팀 선정 (결과 전 봉인)

- 후보 16,034팀 중 제외 서명 일치 5,010팀을 뺐다. 제외 서명은 EX-071 리플레이 3,184개, 과거·예약 34개, EX-071 배틀 10개, EX-089 4개다.
- 남은 후보는 11,024팀이다. 검증 중 거부는 2팀으로, 정규화 형태가 reviewed108 밖이었다.
- 유형별 8팀씩 32팀을 골랐고 부족분은 없다. 최대 공유 종족은 3마리, 종족 최대 등장은 8팀이다. 4개 제외 집합과의 교집합은 0이다.
- mock 2경기(분모 밖)는 정상 종료하고 감사를 통과했다.

### 본 실행

- **분모**: 예정 128, 정상 128, 실패·미완료·무효·미실행 0. 전 경기 감사를 통과했다. 체크포인트는 EX-119와 같다(`403581f2…`).
- **성적**: **89승 0무 39패**, 평균 점수 **0.6953**
  - 조합 클러스터 bootstrap 95%(판정용): **[0.6172, 0.7734]**
  - 진영교환쌍 bootstrap 95%(참고): [0.6250, 0.7656]
- **팀 교환쌍(64쌍)**: 2승 28, 1승 1패 33, 2패 3
- **시드**: 시드 1(laya p1) 0.688, 시드 2(laya p2) 0.703. 두 시드의 쌍 점수가 다른 조합은 14/32다.
- **laya 팀 유형별**(각 32경기): 밸런스 0.781, 날씨·필드 0.719, 수비형 0.688, 공격형 0.594
- **팀별**(laya가 맡은 4경기):
  - 1.0인 팀 11개, 0.75 8개, 0.5 8개, 0.25 5개, 0.0은 없다.
  - 0.25 팀은 수비형 2, 날씨 2, 공격형 1이다.
- **지연**: 결정 5,559개, HTTP 왕복 중앙값 0.118초, p95 0.143초

### 동결 판정

- **1차**: 하한 0.6172 > 0.5 → **"새 팀에서도 Abyssal보다 우세"**
- **EX-119 비교**: 상한 0.7734 < 0.7812 → "EX-089 4팀 결과는 일반 수준보다 높았다"
  - 상한과 기준의 차이는 0.008로 경계에 가깝다.
  - EX-119(32경기) 쪽의 불확실성은 이 비교에 반영되지 않았다.

## 분석 및 한계

- 상대는 Abyssal 하나뿐이다.
- 팀별 점수는 laya 4경기 기준이라 개별 승률이 아니라 편차 탐지용이다.
- 확률은 행동 선택 확률이며 승률이 아니다.
- **유형 분류 한계**: 동결 규칙은 Curse, Calm Mind 같은 내구형 강화 기술도 셋업으로 센다. 그래서 수비 성향 팀이 공격형으로 분류된 사례가 있다(예: Blissey, Dondozo, Clefable 팀). 결과를 본 뒤 규칙을 바꾸지 않았다.
- 조합 클러스터는 서로 다른 조합이 팀을 공유하므로 완전히 독립이 아니다.

## 결론 및 후속 작업

- 처음 보는 32팀에서도 laya 모방 모델은 Abyssal에 우세했다(0.695, 하한 0.617). 성능이 일부 팀에 몰린 것도 아니다. 2패 교환쌍은 3/64이고, 팀별 0.0은 없다.
- EX-119의 0.78은 이번 일반 수준(약 0.70)보다 다소 높게 나온 값으로 보인다. 다만 경계에 가깝다.
- 공격형 팀을 맡았을 때 점수가 가장 낮았다(0.594). 아래 분류 한계를 감안해 방향성 관찰로만 둔다.
- **후속 후보**(별도 승인): 다른 상대(Abyssal-Tera, OneStep)에 대한 일반화, 렌더러 v2(기술 변형, 교체 판단 정보)를 이 128경기 일정에서 v1과 같은 실행 안에서 비교
