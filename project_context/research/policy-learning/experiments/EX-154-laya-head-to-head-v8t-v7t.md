# EX-154 — laya v8t 대 v7t 직접 대결 128경기(GPU2, EX-120 일정)

- 상태: Stopped
- 생성일: 2026-11-02
- 책임자: Claude Code
- 관련 exec plan: [EP-224](../plans/EP-224-laya-engine-judge-v8.md)
- 관련 decision: [D-201](../decisions/D-201-laya-engine-judge-v8.md), [D-194](../decisions/D-194-laya-head-to-head-evaluation.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: `laya-v8t`(EX-152) 대 `laya-v7t`(EX-149)
- 기준 연구선: `research/model-training`

## 질문 및 목적

laya끼리 직접 두면 v8t가 v7t보다 나은가? Abyssal 천장 밖의 차이를 본다.

## 가설 또는 qualification 목표

- **판정**(EX-134 방식): v8t 쪽 경기 점수, 0.5 비교, 조합 클러스터 bootstrap 95%(10,000회). 하한 > 0.5이면 "v8t 우세", 상한 < 0.5이면 "v8t 열세", 그 밖은 "구별되지 않음". 정상 종료 120/128 미만이면 판정 보류.
- **보고 지표**: 승무패, 양쪽 실패 기술 수, 같은 슬롯 Abyssal 결과(EX-150 v7t, EX-153 v8t)와의 일치
- 알려진 문제: 직접 대결 뷰어의 browser_check는 표 행 수 assertion에서 실패하는 기존 문제가 있다(경기와 무관, 기록만).

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| EX-120 일정 128슬롯, v8t model 진영 / v7t 반대 진영 | 팀, 시드 20261048 | 양 진영 모델 | GPU2·8108 |

## 실행

- 실행기: `scripts/laya-imitation h2h --study EX-154 {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ep224 h2h`(EX-152 봉인 뒤)
- prepare 직전 `.pokechamp-data/battle-window/EX-154` 표시 파일 생성, export 뒤 삭제
- 상한 12시간. 자동 재실행 없음.

## 결과

실행되지 않았다. 경기 0, 판정 없음.

- 2026-11-02 04:48Z — GPU2를 EX-155 학습에 먼저 쓰기로 해 `ep224 gpu2` 레인을 멈추고, EX-154를 `scripts/laya-imitation-ep224b gpu2`의 마지막 단계로 옮겼다(`EP-224-gpu2.log`).
- 2026-11-02 15:43:58Z — EX-155 평가 뒤 첫 단계 `h2h --study EX-154 mock`이 인자 오류로 끝났다(`EP-224b-gpu2.log`): `argument --study: invalid choice: 'EX-154'`. `headtohead.STUDIES`에는 `EX-154`가 등록돼 있지만, `cli.py`의 `--study` choices에 빠져 있었다. mock 전에 멈췄으므로 battle-window 표시 파일은 만들어지지 않았고 `runs/model-training/EX-154`도 없다.
- 자동 재실행 규칙에 따라 다시 실행하지 않았다. 이후 GPU0~3은 EP-226(2026-11-02 23:45Z 시작)과 다음 계획에 쓰였다.

## 결론 및 후속 작업

- 실행기 결함(CLI 등록 누락)으로 중단됐다. v8t와 v7t의 직접 대결 결과는 없다.
- 두 모델의 비교는 Abyssal 같은 슬롯([EX-153](EX-153-laya-v7t-v8t-battle256.md), 퇴보를 배제하지 못함)과 사람 팀 중간 결과([EX-159](EX-159-laya-human-teams-v7t-v8t-v9t.md), 구별되지 않음)로만 남는다.
- 다시 하려면 `cli.py` `h2h --study` choices에 `EX-154`를 더하고 별도 지시로 실행한다.
