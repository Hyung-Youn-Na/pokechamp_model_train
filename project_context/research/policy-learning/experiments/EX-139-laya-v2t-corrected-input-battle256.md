# EX-139 — laya v2+테라(EX-124) 보정 입력 fix·info 같은 실행 256경기(GPU1, EX-120 일정)

- 상태: Completed
- 생성일: 2026-10-27
- 책임자: Claude Code
- 관련 exec plan: [EP-219](../plans/EP-219-laya-v2t-corrected-input-battle.md)
- 관련 decision: [D-196](../decisions/D-196-laya-v2t-corrected-input-battle.md), [D-195](../decisions/D-195-laya-item-state-renderer-v5.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행: [EX-124](EX-124-laya-v2-tera-knowledge-training.md)(체크포인트), [EX-125](EX-125-laya-v2-tera-battle256.md)(같은 슬롯 기준), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

v2t(EX-124)를 재학습하지 않고 상대 아이템 상태로 바로잡은 입력을 주면, 같은 일정과 같은 상대(Abyssal)에서 배틀 성적이 원래 v2 입력(EX-125)과 달라지는가? 두 가지를 나눠서 본다.

- 같은 형식에서 값만 바로잡는 경우(fix)
- 학습 때 보지 못한 문구를 더하는 경우(info)

## 가설 또는 qualification 목표

- **진행 조건**: 없다. 재학습이 없고 오프라인 결과로 진행 여부를 정하지 않는다(D-191).
- **qualification**: 변형마다 128슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **판정**(실행 전 동결): 변형별로 같은 EX-120 슬롯의 점수 차이(변형 − EX-125 `laya-v2t`)를 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261035)로 본다.
  - 하한 > 0 → "변형 입력이 배틀 성적을 개선"
  - 상한 < 0 → "악화"
  - 그 외 → "구별되지 않음"
  - 정상 종료가 120/128 미만인 변형은 판정을 보류한다.
- **보고 지표**(판정 외):
  - info − fix 같은 실행 쌍비교(같은 bootstrap)
  - 실패·무효 기술 비율과 반복(`comparison.failed_moves`), 테라 사용
  - Sleep Talk 실패 원인: 그 턴에 깨어남 / 잠든 채 부를 기술 없음 / 깨어 있는데 사용
  - 지면 공격 기술의 무효 횟수와 공개된 풍선을 든 상대 대상 횟수
  - 입력 변화: 실전 입력을 v2와 변형 렌더러로 다시 렌더해 달라진 결정 수
  - 사람 대전 132결정 재추론: 선택 변화, 풍선 국면 지면 기술 1순위
  - 모든 지표는 EX-125 v2t 128경기에 같은 함수로 센 값을 기준 행으로 둔다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| laya-v2t-fix | EX-124 selected(`12519d98…`), EX-120 봉인 일정 128슬롯, Abyssal, 300턴/600결정, GPU1 서빙 | `laya-compact-v5[damage,moves,speed,switch]`(v2 형식, `features_v5` 값) | `runs/model-training/EX-139/games/v2t-fix-*` |
| laya-v2t-info | 같음 | `laya-compact-v5[counters,damage,items,moves,speed,switch]` | `runs/model-training/EX-139/games/v2t-info-*` |
| (기준) laya-v2t | 같음, EX-125에서 실행 | `laya-compact-v2[damage,moves,speed,switch]` | `runs/model-training/EX-125/games/v2t-*`(읽기 전용) |

- **진행 순서**: EX-131과 같은 구조다. EX-120 쌍마다 두 조건의 쌍을 연달아 두고, 어느 조건을 먼저 둘지는 시드 20261035의 digest로 정한다.
- **fallback, 재질의, 재경기**: 없다. 단일 후보는 자동 제출한다.
- **분모**: 조건별 예정 128
- **단계 상한**: 10시간

## 환경 및 출처

- 배틀: `pokechamp/.venv` worker, `BattleServer`, 포트 8109(`port8109.lock`)
- 서빙: laya venv, GPU1(`gpu1.lock`, UUID `GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`와 유휴 확인), node 계산기
  - 두 조건 서빙은 같은 체크포인트를 따로 띄운다.
  - 서빙 identity의 `render`는 실제 렌더 이름이고, `trained_render`는 v2 자료 렌더다.
  - v2 자료와 v5 자료의 원본 파일 일치를 모두 확인한다.
- 실행기: `scripts/laya-imitation compare8 {mock,probe,prepare,execute,export}`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-139`

## 격리 및 오염 통제

- 일정: EX-120 collection 봉인을 확인한 뒤 복사한다.
- 기준: EX-125 봉인을 확인하고, prepare 때 `result.json`·`manifest.json` 해시를 `baseline.json`에 동결한다. execute 시작 때 다시 대조한다.
- 자원 분리: GPU0·GPU2·GPU3과 포트 8107·8108은 EP-218이 쓰므로 쓰지 않는다.
- 소스 동결: prepare 때 `source/identity.json`을 기록하고 execute 시작 때 대조한다. 같은 checkout의 EP-218(EX-137·138)도 같은 방식으로 동결하므로 코드 작업은 EX-136 학습 중에 끝냈다.
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex139/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1), 생성기 `laya-imitation-researcher-v1`. 압축 입력 탭은 조건별 렌더러(v2fix/v2info)로 복원한다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. mock: `v2info` 렌더러와 기본 체크포인트로 CPU 2경기. 분모 밖이다. `v2fix`는 같은 경로의 모듈 부분집합이라 단위 검사로 확인한다.
2. probe: 사람 대전 132결정을 GPU1에서 재추론한다(보고 전용). v2t는 기록된 입력으로, fix·info는 재파싱 입력으로 추론한다.
3. prepare: EX-124 완료·봉인, 렌더러 일치, 일정 봉인, EX-125 봉인을 확인한 뒤 동결한다.
4. execute: 256슬롯을 진행하고 경기별로 감사한다.
5. export: 입력 변화 집계, 보고, 뷰어, 봉인

## 승인·무효화·중단 조건

- **승인**: 256슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **무효**: 입력 경계 위반, 신원 불일치, 감사 실패(그 경기만)
- **중단**: 10시간 상한, 수집 결함(phase 오류)

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯만 수정과 독립 검증을 거친 뒤 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다. 코드 수정이 필요하면 EP-218 연결 실행이 끝난 뒤에 한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-139` | `checksums.sha256`, `report.md`, `result.json` `58d449ec…` | 봉인 |
| 뷰어 | `/workspace/exports/battle_viewers/ex139/index.html` | `checksums.sha256` | 생성·Playwright 통과(`exec-plans/evidence/ep219/ex139-viewer-check.json`) |
| 사람 대전 재추론 | `EX-139/diagnostics/nhj-probe.json` | — | 보고 전용 |

## 결과

- **실행**: 2026-10-27 02:36Z prepare, 02:36:58Z ~ 05:16Z execute, 05:20Z export·봉인. GPU1·포트 8109. 결함 복구 없음.
- **분모**: 조건별 128/128 정상 종료, 실패·무효·미실행 0, 전 경기 감사 통과.

| 조건 | 승/무/패 | 평균 점수 | 조합 클러스터 95% | 교환쌍 2승/1승1패/2패 | 지연 p50 |
|---|---|---:|---|---|---:|
| laya-v2t-fix | 110/0/18 | 0.859 | [0.797, 0.914] | 46/18/0 | 0.143초 |
| laya-v2t-info | 108/0/20 | 0.844 | [0.773, 0.914] | 44/20/0 | 0.135초 |
| (기준) EX-125 laya-v2t | 111/0/17 | 0.867 | [0.805, 0.922] | 47/17/0 | — |

- **판정**(동결, 변형 − EX-125 v2t 같은 슬롯):
  - fix: −0.0078, 95% [−0.0234, +0.0000], 변형 우세 0 / v2t 우세 1 / 같음 127 → **"구별되지 않음"**
  - info: −0.0234, 95% [−0.0625, +0.0156], 2 / 5 / 121 → **"구별되지 않음"**
  - info − fix(보고 전용): −0.0156, 95% [−0.0547, +0.0234], 2 / 4 / 122
- **경기 재현**: 결과와 턴 수가 EX-125와 같은 슬롯은 fix 116/128, info 84/128이다. 결과가 달라진 슬롯은 fix 1개(m11-s1-a 패), info 7개(패 5, 승 2)다.
- **입력 변화**(실전 입력을 v2와 변형 렌더러로 다시 렌더): fix 5,843결정 중 501(8.6%, 모두 선택지 문구, 상태 텍스트 0), info 5,798결정 중 3,620(상태 3,600, 선택지 450).
- **풍선·지면**: 공개된 풍선을 든 상대에게 지면 기술 사용은 v2t 9회(모두 무효)에서 fix 0, info 0으로 사라졌다. 지면 기술 무효는 20 → 10(fix), 9(info)이다. 남은 무효는 상대가 그 턴에 교체해 들어온 비행 타입(Gliscor 등)·Levitate(Hydreigon)다(채팅 분석, 약 100경기 시점).
- **Sleep Talk**: 사용/실패(그 턴에 깨어남/깨어 있는데 사용) v2t 100/43(26/17), fix 95/40(24/16), info 91/35(21/14). 잠든 채 실패는 모두 0이다.
- **실패·무효 기술**: v2t 240/4,177(5.75%), fix 228/4,112(5.54%), info 235/4,053(5.80%).
- **테라**: v2t 22경기(21승 1패), fix 24경기(22승 2패), info 25경기(22승 3패). 결정당 선택률 0.46~0.54%.
- **사람 대전 132결정 재추론**(보고 전용): 텍스트가 v2와 다른 결정 fix 20, info 115. v2t와 선택이 다른 결정은 fix 10, info 10이고 모두 텍스트가 바뀐 결정이다. 풍선 든 상대 앞 11결정에서 지면 기술 1순위는 v2t 9 → fix 0, info 0이다.
- 산출물: `runs/model-training/EX-139/report.md`, `metrics.json`, `input-changes.json`, 뷰어 `/workspace/exports/battle_viewers/ex139/index.html`(256경기, 11,782결정, 1440px·390px 페이지 오류 0)

## 분석 및 한계

- 재학습 없는 입력 변형이다. info의 문구는 EX-124의 학습 분포 밖이다. 따라서 성적 차이는 "정보가 쓸모 있는가"와 "분포 이동에 견디는가"가 섞인 값이다. fix는 형식이 같아 분포 이동이 작다.
- 기준 v2t는 이번 실행이 아니라 EX-125 경기다. 결정적 경로로 다섯 번 재현됐지만, 같은 실행 대조군은 없다.
- 상대는 Abyssal 하나이고 테라를 쓰지 않는다. Abyssal 팀의 Air Balloon·Knock Off 사용 빈도에 따라 보정이 드러나는 결정 수가 제한된다(입력 변화 지표로 센다).
- 128쌍 차이로 작은 효과는 구별되지 않을 수 있다.

## 결론 및 후속 작업

- 재학습 없이 상대 아이템 상태로 값을 바로잡은 입력(fix)은 의도한 결정(공개된 풍선 상대 지면 기술 9 → 0)을 고쳤지만 Abyssal 성적은 기준과 구별되지 않았다. 128슬롯 중 127슬롯의 결과가 같다. 보정이 드러나는 결정이 적어 승패로 이어지는 경우가 드물다.
- 학습 때 보지 못한 문구를 더한 info는 경기 전개가 더 많이 바뀌었고(같은 경기 84/128) 점수는 낮은 쪽이었지만 구별되지 않음이다.
- 후속: 테라를 거의 쓰지 않는 원인 분석에 따라 fix 입력에서 테라 합산 결정·테라 방어 문구를 [EX-140](EX-140-laya-v2t-tera-decision-defence384.md)([D-197](../decisions/D-197-laya-v2t-tera-decision-defence.md))에서 시험한다. 이 실행의 fix 128경기가 그 기준이다.
