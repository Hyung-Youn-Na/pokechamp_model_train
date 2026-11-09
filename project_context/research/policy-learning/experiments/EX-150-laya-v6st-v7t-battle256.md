# EX-150 — laya v6st 대 v7t(상대 세트 추정) 같은 실행 256경기(GPU0, EX-120 일정)

- 상태: Completed
- 생성일: 2026-10-31
- 책임자: Claude Code
- 관련 exec plan: [EP-223](../plans/EP-223-laya-loop-break-opponent-sets.md)
- 관련 decision: [D-200](../decisions/D-200-laya-loop-break-opponent-sets.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: `laya-v6st`(EX-141) 대 `laya-v7t`(EX-149), 같은 실행
- 기준 연구선: `research/model-training`

## 질문 및 목적

상대 세트 추정 입력(v7)이 Abyssal 상대 성적을 떨어뜨리지 않는가?

## 가설 또는 qualification 목표

- **판정**(동결, EX-143과 같은 비퇴보 기준): 같은 슬롯 차이(v7t − v6st), 조합 클러스터 bootstrap 95%. 하한 > −0.05이면 "비퇴보", 아니면 "퇴보를 배제하지 못함". 정상 종료 120/128 미만이면 판정 보류.
- **보고 지표**: 승무패, 실패 기술 비율(Protean·Libero 사용 경기 포함), 5턴 이상 반복 수, 테라 사용
- 한계: Abyssal 한 상대다. 사람이 보편 세트를 쓰는 래더 효과는 이 실험으로 입증되지 않는다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| EX-120 일정 128슬롯 × 2모델 | 팀, 시드 20261041, Abyssal | 체크포인트·렌더(EX-141 v6s → EX-149 v7) | GPU0·8107 |

### 직접 대결(EX-150-H, 보고 지표)

- 학습 봉인 뒤 EX-120 일정 128슬롯에서 `laya-v7t`이 model 진영, `laya-v6st`가 반대 진영을 맡는다(EX-134 방식, GPU3·8106(EX-148-H2 뒤), 시드 20261045).
- 점수는 v7t 쪽 경기 점수이고 0.5와 비교한다(조합 클러스터 bootstrap). 정상 종료 120/128 미만이면 판정 보류다.
- 실행기 `scripts/laya-imitation h2h --study EX-150-H {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ep223b h2h150`

## 실행

- 실행기: `scripts/laya-imitation compare13 {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ep223 v7`(EX-149 평가 뒤)
- 상한 10시간. 자동 재실행 없음.

## 결과

- 2026-10-31 mock 2/2 정상(초기 체크포인트). 2026-11-01 04:29Z~07:09Z(GPU0·8107) 256/256 정상 종료·감사 통과. 보고 `runs/model-training/EX-150/report.md`, 뷰어 확인 통과(1440·390 폭, 256경기, 페이지 오류 0, `exec-plans/evidence/ep223/ex150-viewer-check.json`).
- **판정**: 같은 슬롯 차이(v7t − v6st) +0.0469, 95% [−0.0234, +0.1172] → **비퇴보**. v7t 우세 15, v6st 우세 9, 같음 104.

| 모델 | 승/무/패 | 평균 점수 | 95% | 기술 실패·무효 | 테라 사용 경기 | 지연 p50 |
|---|---|---:|---|---:|---:|---:|
| laya-v6st | 106/0/22 | 0.828 | [0.766, 0.891] | 86/3130 (2.75%) | 23/128 | 0.151초 |
| laya-v7t | 112/0/16 | 0.875 | [0.805, 0.938] | 171/3310 (5.17%) | 28/128 | 0.152초 |

- 같은 기술 3회 이상 연속 실패 경기 v6st 6, v7t 5. v7t 최장은 Whirlwind 32회(v7t-m09-s1-b, 상대 마지막 한 마리). v7t 실패 상위: Earthquake 32/197, Whirlwind 32/42, Spikes 29/66, Body Press 16/65, First Impression 15/16.
- 실패 증가 분석은 [EP-223 진행](../plans/EP-223-laya-loop-break-opponent-sets.md#진행) 2026-11-02 항목에 있다(5판에 142건, 표시된 실패 수 반복과 규칙 공백).
- Protean·Libero 사용 경기만 따로 본 실패율과 5턴 이상 같은 기술 반복 수는 이 실행의 보고에 집계되지 않았다.
- 직접 대결 EX-150-H(2026-11-02 00:03Z~02:21Z, GPU3·8106): mock 4/4 정상, 126/128 정상 종료(미완료 2). v7t 61-65, 점수 0.484, 95% [0.413, 0.555] → **구별되지 않음**. 실패·무효 v7t 235/5060(4.64%), v6st 272/5258(5.17%). 보고 `runs/model-training/EX-150-h2h/report.md`. 뷰어 `ex150-h2h` 자동 확인은 표 행 수 assertion에서 실패했다(직접 대결 뷰어의 기존 문제, 경기와 무관). 수동 확인 기록은 없다.

## 결론 및 후속 작업

- v7t는 Abyssal 상대로 v6st보다 6경기 더 이겼고, 하한 −0.0234 > −0.05라 "비퇴보"다. 개선은 입증되지 않았다.
- 실패 기술은 86 → 171로 늘었다. 표시된 실패 수 반복과 규칙 공백(마지막 한 마리 Whirlwind, 이미 행동한 First Impression)이 원인이다. 이것이 [EP-224](../plans/EP-224-laya-engine-judge-v8.md) 엔진 판정기의 동기다.
- 직접 대결에서도 v6st와 구별되지 않았다.
