# EX-156 — laya v8t 대 v8lt(`likely fails` 표시) 같은 실행 256경기(GPU1, EX-120 일정)

- 상태: Completed
- 생성일: 2026-11-02
- 책임자: Claude Code
- 관련 exec plan: [EP-224](../plans/EP-224-laya-engine-judge-v8.md)
- 관련 decision: [D-201](../decisions/D-201-laya-engine-judge-v8.md)(추가 결정), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: `laya-v8t`(EX-152) 대 `laya-v8lt`(EX-155), 같은 실행
- 기준 연구선: `research/model-training`

## 질문 및 목적

확률 실패(`; likely fails`: Protect 연속, 깨어날 확률이 높은 Sleep Talk·Snore)까지 표시해 학습한 v8lt가 v8t보다 Abyssal 상대 성적을 떨어뜨리지 않고, 그런 수의 실패를 줄이는가? 사용자 지시(2026-11-02)로 예약했다.

## 가설 또는 qualification 목표

- **판정**(동결, EX-150·EX-153과 같은 기준): 같은 슬롯 차이(v8lt − v8t), 조합 클러스터 bootstrap 95%. 하한 > −0.05이면 "비퇴보", 아니면 "퇴보를 배제하지 못함", 하한 > 0이면 "개선". 정상 종료 120/128 미만이면 판정 보류.
- **보고 지표**: 승무패, 실패 기술 수·비율(v8t 대비), Protect류 연속 실패·Sleep Talk 실패 수, 3회 이상 연속 실패 루프, 테라 사용
- 한계: Abyssal 한 상대다. `likely fails` 상황은 경기당 드물어 차이가 작을 수 있다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| EX-120 일정 128슬롯 × 2모델 | 팀, 시드 20261050, Abyssal | 체크포인트·렌더(EX-152 v8 → EX-155 v8l) | GPU1·8109 |

## 실행

- 실행기: `scripts/laya-imitation compare15 {mock,prepare,execute,export}`
- 연결 실행 `scripts/laya-imitation-ep224c gpu1`(로그 `runs/model-training/EP-224c-gpu1.log`): EX-153과 EX-155가 모두 completed가 되면 mock → `.pokechamp-data/battle-window/EX-156` 표시 파일 → prepare/execute/export → 표시 파일 삭제 → 뷰어 검사
- 상한 10시간. 자동 재실행 없음. mock 실패 시 prepare 전에 멈춘다.

## 결과

- 2026-11-02 17:13Z EX-153·EX-155 완료 확인, mock 2/2 정상. 17:14Z battle-window 표시 생성, 17:14Z~19:34Z(GPU1·8109) 256/256 정상 종료·감사 통과, 19:42Z 표시 삭제. 보고 `runs/model-training/EX-156/report.md`, 뷰어 확인 통과(1440·390 폭, 256경기, 페이지 오류 0, `exec-plans/evidence/ep224/ex156-viewer-check.json`).
- **판정**: 같은 슬롯 차이(v8lt − v8t) +0.0078, 95% [−0.0469, +0.0703] → **비퇴보**(하한 > 0이 아니므로 개선은 아니다). v8lt 우세 11, v8t 우세 10, 같음 107.

| 모델 | 승/무/패 | 평균 점수 | 95% | 기술 실패·무효 | 테라 사용 경기 | 지연 p50 |
|---|---|---:|---|---:|---:|---:|
| laya-v8t | 111/0/17 | 0.867 | [0.805, 0.922] | 126/3465 (3.64%) | 21/128 | 0.168초 |
| laya-v8lt | 112/0/16 | 0.875 | [0.812, 0.930] | 148/3350 (4.42%) | 22/128 | 0.168초 |

- Protect 실패(원인 구분 없음) v8t 4/109, v8lt 9/115. Sleep Talk 실패 v8t 4/38, v8lt 1/55. Protect류 연속 실패만 따로 센 값은 보고에 없다(`metrics.json` 실패 상위 15개 기준).
- 3회 이상 연속 실패 루프 경기 v8t 6, v8lt 8. 최장은 v8t Stealth Rock 18회, v8lt Stealth Rock 31회(v8lt-m29-s1-b). v8lt 실패 상위: Stealth Rock 39/112, Toxic Spikes 23/30.

## 결론 및 후속 작업

- `likely fails` 표시는 Abyssal 성적을 떨어뜨리지 않았다(비퇴보). Sleep Talk 실패는 줄었지만 Protect 실패는 늘었고, 전체 실패는 126 → 148로 늘었다.
- 늘어난 실패는 Stealth Rock(18 → 39), Toxic Spikes(v8t 상위 15개에 없음 → 23), Thunderclap(1 → 15)이다. 원인은 따로 분석하지 않았다. 해저드 실패 증가는 [EX-160](EX-160-laya-human-teams-v8lt.md) 보고 지표에 반영됐다.
