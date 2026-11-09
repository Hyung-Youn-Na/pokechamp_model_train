# EX-160 — laya v8lt 사람이 짠 완성 팀 123개 대 Abyssal(EX-159 일정, GPU3)

- 상태: Stopped
- 생성일: 2026-11-03
- 책임자: Claude Code
- 관련 exec plan: [EP-226](../plans/EP-226-laya-human-teams-v7-v8-v9.md)
- 관련 decision: [D-203](../decisions/D-203-laya-human-teams-v7-v8-v9.md)
- 비교 대상: `laya-v8lt`(EX-155) 대 [EX-159](EX-159-laya-human-teams-v7t-v8t-v9t.md)의 v8t·v7t·v9t, 같은 기본 슬롯. EX-120 일정 결과 [EX-156](EX-156-laya-v8t-v8lt-battle256.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

사람이 짠 완성 팀에서 v8lt(`likely fails` 표시)가 v8t·v7t·v9t보다 떨어지지 않는가? EX-156(EX-120 일정, 비퇴보)과 같은 방향인가?

## 가설 또는 qualification 목표

- **판정**(실행 전 동결, EX-159와 같은 규칙): v8lt − v8t(시드 20261059), v8lt − v7t(20261060), v8lt − v9t(20261061). 같은 기본 슬롯 점수 차이의 조합(123) 클러스터 bootstrap 95%, 10,000회. 하한 > 0 "개선", 하한 > −0.05 "비퇴보", 그 외 "퇴보를 배제하지 못함". 정상 종료가 EX-159의 최소 기준(467/492) 미만이면 보류.
- **보고 지표**: 승무패, 팀 묶음·학습 노출·유형별 점수율, 실패·무효 기술과 연속 실패(특히 Stealth Rock·해저드, EX-156에서 늘었다), 테라 사용

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 위치 |
|---|---|---|---|
| laya-v8lt | EX-159 봉인 일정 492 기본 슬롯(같은 팀·진영·시드·진행 순서), Abyssal, 300턴/600결정 | EX-155 selected, `v8l` | `runs/model-training/EX-160/games/v8lt-*` |

## 환경 및 출처

- GPU3(`GPU-fd337c1e…`)·8106, 서빙 1개. 실행기 `python -m integration.laya_teamset_v8l.battle {mock,prepare,execute,compare,export}`, 연결 실행 `scripts/laya-imitation-ep226b gpu3`
- `integration/laya_teamset`은 EX-159가 해시를 동결했으므로 별도 패키지 `integration/laya_teamset_v8l/`에 둔다.
- 출력 `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-160`, 뷰어 `/workspace/exports/battle_viewers/ex160/`([변경일지](../../../shared/viewers/CHANGELOG.md#ex160-laya-v1))

## 격리 및 오염 통제

- 일정은 EX-159 collection(봉인)을 그대로 읽는다. prepare가 laya_imitation `source_identity`와 이 패키지 해시를 동결하고 execute·compare가 확인한다.
- 한계: 비교 모델 경기는 EX-159(GPU0~2)에서 다른 시점에 두었다. 슬롯 시드는 같다.

## 절차

mock(CPU, `laya-v8lt-initial` 2경기, 분모 밖) → prepare → execute → EX-159 combine 대기 → compare → export·뷰어 확인. 자동 재실행 없음, 상한 12시간.

## 결과

진행 중 중지. 판정 보류(정상 종료 467/492 미만).

## 중단 결과

2026-11-03 04:28:44Z에 사용자 직접 요청으로 중지했다. 사용자 판단: 지금까지 Abyssal 상대 결과(EX-125 이후 v2t~v9t가 0.87~0.89에서 구별되지 않음)로 보아 이 비교는 성능이 포화돼 의미가 적고, 다음 개선 학습에 GPU0~3을 쓰기 위함이다. 도구 결함이나 중단 조건 때문이 아니다.

- 진행: 342/492. 끝난 경기는 모두 completed·감사 통과, 실패·무효 0. 중지 순간 두던 `v8lt-m054-s2-a`는 미완료로 분모 밖이다.
- v8lt(중간): 302-40(0.883, 342경기).
- EX-159 중간 결과와 같은 슬롯 차이(임시 계산, seed 0, 조합 클러스터 bootstrap 10,000회): v8lt − v8t +0.009 [−0.044, +0.061](342슬롯/115조합), v8lt − v7t −0.012 [−0.056, +0.033], v8lt − v9t −0.009 [−0.054, +0.037].
- compare·export·뷰어는 하지 않았다. 중간 집계는 `runs/model-training/EX-160/stopped.json`에 두었다. 원장과 경기 디렉터리는 그대로 두었고, 중지한 슬롯의 Showdown worktree 등록만 제거했다. battle-window 표시 `EX-160`을 지웠고 GPU3과 포트 8106을 반환했다.

## 결론 및 후속 작업

중간 결과로는 v8lt가 다른 세 모델과 구별되지 않았다(EX-156과 같은 방향). 정식 판정은 없고, 재개는 별도 지시가 있을 때만 한다.
