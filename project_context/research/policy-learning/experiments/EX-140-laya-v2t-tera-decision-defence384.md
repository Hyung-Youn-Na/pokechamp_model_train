# EX-140 — laya v2+테라(EX-124) fix 입력 테라 합산 결정(k=1·3)과 테라 방어 문구 384경기(GPU1, EX-120 일정)

- 상태: Completed
- 생성일: 2026-10-27
- 책임자: Claude Code
- 관련 exec plan: [EP-220](../plans/EP-220-laya-v2t-tera-decision-defence.md)
- 관련 decision: [D-197](../decisions/D-197-laya-v2t-tera-decision-defence.md), [D-196](../decisions/D-196-laya-v2t-corrected-input-battle.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행: [EX-124](EX-124-laya-v2-tera-knowledge-training.md)(체크포인트), [EX-139](EX-139-laya-v2t-corrected-input-battle256.md)(같은 슬롯 기준), [EX-125](EX-125-laya-v2-tera-battle256.md)(참고), [EX-120](EX-120-laya-team-generalization128.md)(일정)
- 기준 연구선: `research/model-training`

## 질문 및 목적

v2t는 테라 확률을 사람만큼 매기지만 1순위 선택 때문에 거의 쓰지 않는다. 재학습 없이 다음 두 가지를 바꾸면 테라 사용과 배틀 성적이 어떻게 달라지는가?

- 결정 규칙: 테라 선택지 확률을 합쳐(k배) 한 번의 결정으로 본다(tp1, tp3).
- 입력: 테라 선택지에 테라 후 방어 상성(교체 후보와 같은 `takes`·`worst` 문구)을 넣는다(tdef).

## 가설 또는 qualification 목표

- **진행 조건**: 없다(D-191).
- **qualification**: 조건마다 128슬롯이 처리되고, 분모 산술이 맞고, 봉인된다. tp 조건에서 규칙이 작동하지 않은 슬롯은 EX-139 fix와 결과·턴 수가 같다.
- **판정**(실행 전 동결): 조건별 같은 EX-120 슬롯 점수 차이(조건 − EX-139 `laya-v2t-fix`), 조합(32) 클러스터 bootstrap 95%(10,000회, 시드 20261040).
  - 하한 > 0 → "배틀 성적을 개선", 상한 < 0 → "악화", 그 외 → "구별되지 않음"
  - 정상 종료 120/128 미만인 조건은 판정을 보류한다.
- **보고 지표**(판정 외):
  - tp3 − tp1 쌍비교, 조건별 EX-125 v2t 대비 차이
  - 테라 사용 경기·첫 테라 턴·테라 경기 승패·결정당 선택(`comparison.tera_usage`)
  - 테라 선택의 성격: 방어(테라 순간 상대 공개 공격의 최악 배율, 없으면 상대 타입 배율의 전→후: 개선/같음/악화), 공격(테라 선택지 v2fix 문구가 일반 선택지와 태그 밖에서 다름), 규칙이 1순위를 바꾼 선택 수
  - 규칙 작동 슬롯 수와 재현 검사
  - 실패·무효 기술(`comparison.failed_moves`)
  - 기준 행: EX-139 fix에 같은 함수로 센 값
- **사전 계산**(EX-139 fix 로그에 규칙을 다시 적용, 보고 전용): 테라를 처음 고르는 경기 k=1 47/128, k=3 95/128(실제 1순위 24/128). EX-139 fix의 테라 24회는 방어 개선 8·같음 9·악화 7, 공격 변화 16이다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 | 예상 artifact 위치 |
|---|---|---|---|
| laya-v2t-fix-tp1 | EX-124 selected(`12519d98…`), `v2fix` 입력, EX-120 봉인 일정 128슬롯, Abyssal, 300턴/600결정, GPU1 서빙 | 테라 합산 결정 k=1 | `runs/model-training/EX-140/games/v2t-fix-tp1-*` |
| laya-v2t-fix-tp3 | 같음 | 테라 합산 결정 k=3 | `…/games/v2t-fix-tp3-*` |
| laya-v2t-fix-tdef | 같음 | 테라 선택지에 `takes`·`worst`(render `v2fixtd`), 1순위 | `…/games/v2t-fix-tdef-*` |
| (기준) laya-v2t-fix | 같음, EX-139에서 실행, 1순위 | — | `runs/model-training/EX-139/games/v2t-fix-*`(읽기 전용) |

- **진행 순서**: EX-120 쌍마다 세 조건의 쌍을 연달아 둔다. 순서는 시드 20261040의 digest로 정방향/역방향을 정한다.
- **fallback, 재질의, 재경기**: 없다. 단일 후보는 자동 제출한다.
- **분모**: 조건별 예정 128(합계 384)
- **단계 상한**: 10시간

## 환경 및 출처

- 배틀: `pokechamp/.venv` worker, `BattleServer`, 포트 8109(`port8109.lock`)
- 서빙: laya venv, GPU1(`gpu1.lock`, UUID `GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`와 유휴 확인), node 계산기. 세 조건 서빙은 같은 체크포인트를 따로 띄운다.
  - tp: `/health` identity에 `decision`(규칙 `tera-pooled-argmax`, k)을 기록한다. 응답 `probabilities`는 결정 분포, `model_probabilities`는 모델 분포다.
  - tdef: identity `render`는 `laya-compact-v5[damage,moves,speed,switch]+tera-defence-v1`, `trained_render`는 v2, `renderer_sources`에 `tera_decision.py`를 더한다.
- 실행기: `scripts/laya-imitation compare9 {mock,prepare,execute,export}`, 코드 `integration/laya_imitation/tera_decision.py`·`tera_battle.py`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-140`

## 격리 및 오염 통제

- 일정: EX-120 collection 봉인을 확인한 뒤 복사한다.
- 기준: EX-139 완료·봉인을 확인하고 prepare 때 `result.json`·`manifest.json` 해시를 `baseline.json`에 동결한다. execute 시작 때 다시 대조한다.
- 자원 분리: GPU0·GPU2와 포트 8107·8108은 EP-218, GPU3은 외부 프로세스가 쓰므로 쓰지 않는다.
- 소스 동결: prepare 때 `source/identity.json`을 기록하고 execute 시작 때 대조한다. 코드 작업은 EX-136 학습 중에 끝냈다.
- k=3은 같은 일정의 EX-125·EX-139 테라 사용 횟수로 정했다(승패는 보지 않음).
- **viewer 출력과 완료 요건**: [C-047](../../../CONTRACTS.md#c-047-viewer-export)에 따라 `/workspace/exports/battle_viewers/ex140/index.html`에 두고 상위 목록에 연결한다.
- **viewer 적용 규격**: [battle-viewer-ui-v1](../../../shared/viewers/CONTRACTS.md#battle-viewer-ui-v1), 생성기 `laya-imitation-researcher-v1`. 압축 입력 탭은 조건별 렌더러(v2fix / v2fixtd)로 복원한다. tp 경기의 확률 탭은 결정 분포다.
- **재개**: 원장 기준으로 미실행 슬롯만 진행한다.

## 절차

1. mock: `laya-v2t-fix-tp3-initial`(기본 체크포인트, k=3)로 CPU 2경기. 분모 밖이다. tdef 렌더와 서빙 응답 검사는 단위 검사로 확인한다.
2. prepare: EX-124 완료·봉인, 렌더러 일치, 일정 봉인, EX-139 봉인을 확인한 뒤 동결한다.
3. execute: 384슬롯을 진행하고 경기별로 감사한다.
4. export: 테라 선택 분석, 보고, 뷰어, 봉인

## 승인·무효화·중단 조건

- **승인**: 384슬롯이 처리되고, 분모 산술이 맞고, 봉인된다.
- **무효**: 입력 경계 위반, 신원 불일치, 감사 실패(그 경기만)
- **중단**: 10시간 상한, 수집 결함(phase 오류)

## 테스트·평가 도구 결함 복구

C-018과 EX-119 절차를 적용한다. 도구 결함으로 오염된 슬롯만 수정과 독립 검증을 거친 뒤 1회 재수집할 수 있다. 원본은 `diagnostics/`에 보존한다. 코드 수정이 필요하면 EP-218 연결 실행이 끝난 뒤에 한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 배틀 run | `/mnt/.../runs/model-training/EX-140` | `checksums.sha256`, `report.md`, `result.json` `b3be1c1c…` | 봉인 |
| 뷰어 | `/workspace/exports/battle_viewers/ex140/index.html` | `checksums.sha256` | 생성·Playwright 통과(`exec-plans/evidence/ep220/ex140-viewer-check.json`) |

## 결과

- **실행**: 2026-10-27 05:28Z prepare(384슬롯, 서빙 셋 모두 `12519d98…`, 기준 EX-139 `result.json` `58d449ec…`·`manifest.json` `fd9e564c…`를 `baseline.json`에 동결), 05:29:12Z ~ 09:19Z execute, 09:20Z export, 09:24Z 뷰어 Playwright 검사·봉인. GPU1·포트 8109. 결함 복구 없음.
- **분모**: 조건별 128/128 정상 종료, 실패·무효·미완료·미실행 0, 전 경기 감사 통과.
- **qualification**: 규칙이 작동하지 않은 tp 슬롯은 EX-139 fix와 결과·턴 수가 모두 같다(tp1 99/99, tp3 44/44).

| 조건 | 승/무/패 | 평균 점수 | 조합 클러스터 95% | 지연 p50 |
|---|---|---:|---|---:|
| laya-v2t-fix-tp1 | 104/0/24 | 0.812 | [0.742, 0.875] | 0.135초 |
| laya-v2t-fix-tp3 | 101/0/27 | 0.789 | [0.719, 0.852] | 0.135초 |
| laya-v2t-fix-tdef | 101/0/27 | 0.789 | [0.719, 0.859] | 0.143초 |
| (기준) EX-139 laya-v2t-fix | 110/0/18 | 0.859 | [0.797, 0.914] | 0.143초 |

- **판정**(동결, 조건 − EX-139 fix 같은 슬롯):
  - tp1: −0.0469, 95% [−0.0938, −0.0078], 조건 우세 1 / 기준 우세 7 / 같음 120 → **"악화"**
  - tp3: −0.0703, 95% [−0.1328, −0.0078], 4 / 13 / 111 → **"악화"**
  - tdef: −0.0703, 95% [−0.1484, +0.0078], 6 / 15 / 107 → **"구별되지 않음"**
- **보고 전용 비교**:
  - tp3 − tp1: −0.0234, 95% [−0.0781, +0.0312], 5 / 8 / 115
  - EX-125 v2t 대비: tp1 −0.0547 [−0.1016, −0.0156](1 / 8 / 119), tp3 −0.0781 [−0.1406, −0.0156](3 / 13 / 112), tdef −0.0781 [−0.1562, +0.0000](6 / 16 / 106)
- **테라 사용**:

| 조건 | 테라 경기 | 그 경기 승/패 | 테라 가능 결정 | 테라 선택 | 첫 테라 턴 중앙값 |
|---|---:|---|---:|---:|---:|
| tp1 | 47 | 35/12 | 4360 | 47 | 22 |
| tp3 | 95 | 68/27 | 3453 | 95 | 19 |
| tdef | 5 | 3/2 | 4943 | 5 | 25 |
| (기준) EX-139 fix | 24 | 22/2 | 4718 | 24 | 20 |

- 테라 경기 수(tp1 47, tp3 95)는 사전 계산(k=1 47/128, k=3 95/128)과 같다.
- **테라 선택의 성격**(방어 개선/같음/악화, 공격 변화, 규칙이 바꾼 선택):
  - tp1: 19/15/13, 공격 21, 규칙 29
  - tp3: 29/39/27, 공격 37, 규칙 84
  - tdef: 3/1/1, 공격 4, 규칙 0
  - 기준 EX-139 fix: 8/9/7, 공격 16. 판단 불가는 모든 조건에서 0이다.
- **규칙 작동과 재현**: 규칙이 작동한 슬롯 tp1 29(그중 기준과 결과·턴 수가 같음 6), tp3 84(17). tdef는 규칙이 없고, 기준과 같은 슬롯이 21/128이다.
- **실패·무효 기술**: tp1 213/4,048(5.26%), tp3 198/3,823(5.18%), tdef 264/4,144(6.37%), 기준 228/4,112(5.54%). tdef에서는 Whirlwind 실패가 66/81로 가장 많고, 32회 연속 실패 경기가 2개다(m09-s1-b, m22-s2-b).
- 산출물: `runs/model-training/EX-140/report.md`, `result.json` `b3be1c1c…`, `tera-choices.json`, 연결 실행 로그 `runs/model-training/EP-220-chain.log`, 뷰어 `/workspace/exports/battle_viewers/ex140/index.html`(384경기, 1440px·390px 페이지 오류 0, `exec-plans/evidence/ep220/ex140-viewer-check.json`)

## 분석 및 한계

- 재학습 없는 서빙 변경이다. tdef 문구는 테라 선택지에서 학습 때 본 적 없는 위치라 분포 이동이 섞인다.
- 규칙이 작동한 뒤의 경기 전개는 기준과 달라진다. 테라 효과는 그 경기 전체의 결과로만 본다.
- 상대 Abyssal은 테라를 쓰지 않는다. 상대 테라에 대응하는 테라는 볼 수 없다.
- 테라 경기의 승률은 이기고 있을 때 쓰는 선택 편향이 섞일 수 있다.
- 128쌍 차이로 작은 효과는 구별되지 않을 수 있다.

## 결론 및 후속 작업

- 테라 합산 결정은 의도대로 테라 사용을 늘렸다(테라 경기 24 → tp1 47, tp3 95). 그러나 Abyssal 성적은 두 조건 모두 기준보다 낮고 구간 상한이 0 아래라 동결 규칙상 "악화"다(tp1 −0.0469, tp3 −0.0703).
- 규칙이 고른 테라는 방어 상성 기준으로 개선·같음·악화가 고르게 섞였다(tp3 29/39/27). 1순위가 아닌 테라를 더 고르게 하는 것만으로는 성적이 오르지 않았다.
- 테라 방어 문구(tdef)는 테라를 오히려 덜 썼고(24 → 5경기) 점수는 낮은 쪽이지만 "구별되지 않음"이다. 학습 때 본 적 없는 문구라 경기 전개가 크게 바뀌었다(기준과 같은 슬롯 21/128). 기술 실패율도 5.54 → 6.37%로 높다.
- 재학습 없는 결정 규칙·문구 변경으로는 v2t의 테라 활용을 성적 향상으로 바꾸지 못했다.
