# EX-147 — laya v6st 대 v6slt(루프 탈출 가중) 같은 실행 256경기(GPU1, EX-120 일정)

- 상태: Completed
- 생성일: 2026-10-31
- 책임자: Claude Code
- 관련 exec plan: [EP-223](../plans/EP-223-laya-loop-break-opponent-sets.md)
- 관련 decision: [D-200](../decisions/D-200-laya-loop-break-opponent-sets.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: `laya-v6st`(EX-141) 대 `laya-v6slt`(EX-146), 같은 실행
- 기준 연구선: `research/model-training`

## 질문 및 목적

루프 탈출 행 가중 학습(EX-146)이 Abyssal 상대 성적을 떨어뜨리지 않는가? 반복 지표가 줄어드는가?

## 가설 또는 qualification 목표

- **판정**(동결, EX-143과 같은 비퇴보 기준): 같은 슬롯 차이(v6slt − v6st), 조합 클러스터 bootstrap 95%. 하한 > −0.05이면 "비퇴보", 아니면 "퇴보를 배제하지 못함". 정상 종료 120/128 미만이면 판정 보류.
- **보고 지표**: 승무패, 5턴 이상 같은 기술 반복 수, 실패 기술 비율, 테라 사용

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| EX-120 일정 128슬롯 × 2모델 | 팀, 시드 20261039, Abyssal, v6s 렌더 | 체크포인트(EX-141 → EX-146) | GPU1·8109 |

### 직접 대결(EX-147-H, 보고 지표)

- 학습 봉인 뒤 EX-120 일정 128슬롯에서 `laya-v6slt`이 model 진영, `laya-v6st`가 반대 진영을 맡는다(EX-134 방식, GPU2·8108(EX-148 Abyssal 레인 뒤), 시드 20261044).
- 점수는 v6slt 쪽 경기 점수이고 0.5와 비교한다(조합 클러스터 bootstrap). 정상 종료 120/128 미만이면 판정 보류다.
- 실행기 `scripts/laya-imitation h2h --study EX-147-H {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ep223b h2h147`

## 실행

- 실행기: `scripts/laya-imitation compare12 {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ep223 v6sl`(EX-146 평가 뒤)
- 상한 10시간. 자동 재실행 없음.

## 결과

- 2026-11-01 02:47Z mock 2/2 정상. 02:48Z~05:45Z(GPU1·8109) 256/256 정상 종료·감사 통과. 보고 `runs/model-training/EX-147/report.md`, 뷰어 확인 통과(1440·390 폭, 256경기, 페이지 오류 0, `exec-plans/evidence/ep223/ex147-viewer-check.json`).
- **판정**: 같은 슬롯 차이(v6slt − v6st) −0.0625, 95% [−0.1484, +0.0234] → **퇴보를 배제하지 못함**. v6slt 우세 13, v6st 우세 21, 같음 94.

| 모델 | 승/무/패 | 평균 점수 | 95% | 기술 실패·무효 | 테라 사용 경기 | 지연 p50 |
|---|---|---:|---|---:|---:|---:|
| laya-v6st | 106/0/22 | 0.828 | [0.766, 0.891] | 86/3130 (2.75%) | 23/128 | 0.193초 |
| laya-v6slt | 98/0/30 | 0.766 | [0.703, 0.828] | 52/2883 (1.80%) | 10/128 | 0.186초 |

- 같은 기술 3회 이상 연속 실패 경기 v6st 6, v6slt 4. 최장은 v6st Spikes 6회, v6slt Whirlwind 6회.
- 5턴 이상 같은 기술 반복 수는 이 실행의 보고에 집계되지 않았다. 같은 v6st 경기(EX-143, 결정적 경로)의 값은 EX-148 보고에 있다(75회, 47경기).
- 팀 유형별로 v6slt는 날씨·필드(0.781 → 0.688)·공격형(0.844 → 0.719)에서 낮고 수비형은 같다(0.812).
- 직접 대결 EX-147-H(2026-11-01 02:53Z~05:40Z, GPU2·8108): mock 4/4 정상, 128/128 정상 종료. v6slt 60-68, 점수 0.469, 95% [0.383, 0.555] → **구별되지 않음**. 실패·무효 v6slt 248/4888(5.07%), v6st 218/4879(4.47%). 보고 `runs/model-training/EX-147-h2h/report.md`. 뷰어 `ex147-h2h` 자동 확인은 표 행 수 assertion에서 실패했다(직접 대결 뷰어의 기존 문제, 경기와 무관). 수동 확인 기록은 없다.

## 결론 및 후속 작업

- 루프 탈출 가중은 실패 기술(86 → 52)과 테라 사용(23 → 10경기)을 줄였지만 Abyssal 성적은 8경기 낮았다. 하한이 −0.05 아래라 "퇴보를 배제하지 못함"이다.
- 직접 대결에서도 v6st와 구별되지 않았다. v6slt를 기본 모델로 바꿀 근거는 없다.
