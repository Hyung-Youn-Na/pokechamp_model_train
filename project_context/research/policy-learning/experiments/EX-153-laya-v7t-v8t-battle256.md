# EX-153 — laya v7t 대 v8t(엔진 실패 표시) 같은 실행 256경기(GPU1, EX-120 일정)

- 상태: Completed
- 생성일: 2026-11-02
- 책임자: Claude Code
- 관련 exec plan: [EP-224](../plans/EP-224-laya-engine-judge-v8.md)
- 관련 decision: [D-201](../decisions/D-201-laya-engine-judge-v8.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: `laya-v7t`(EX-149) 대 `laya-v8t`(EX-152), 같은 실행
- 기준 연구선: `research/model-training`

## 질문 및 목적

엔진 판정기 실패 표시(v8)가 Abyssal 상대 성적을 떨어뜨리지 않고 실패 기술을 줄이는가?

## 가설 또는 qualification 목표

- **판정**(동결, EX-150과 같은 비퇴보 기준): 같은 슬롯 차이(v8t − v7t), 조합 클러스터 bootstrap 95%. 하한 > −0.05이면 "비퇴보", 아니면 "퇴보를 배제하지 못함". 상한·하한 모두 0보다 크면 "개선". 정상 종료 120/128 미만이면 판정 보류.
- **보고 지표**: 승무패, 실패 기술 수·비율(v7t 대비), 3회 이상 연속 실패 루프, 테라 사용, 결정 지연
- 한계: Abyssal 한 상대다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| EX-120 일정 128슬롯 × 2모델 | 팀, 시드 20261047, Abyssal | 체크포인트·렌더(EX-149 v7 → EX-152 v8) | GPU1·8109 |

## 실행

- 실행기: `scripts/laya-imitation compare14 {mock,prepare,execute,export}`, 연결 실행 `scripts/laya-imitation-ep224 abyssal`(EX-152 봉인 뒤)
- prepare 직전 `.pokechamp-data/battle-window/EX-153` 표시 파일 생성, export 뒤 삭제
- 상한 10시간. 자동 재실행 없음.

## 결과

- 2026-11-02 14:44Z mock 2/2 정상. 14:46Z battle-window 표시 생성, 14:46Z~17:04Z(GPU1·8109) 256/256 정상 종료·감사 통과, 17:09Z 표시 삭제. 보고 `runs/model-training/EX-153/report.md`, 뷰어 확인 통과(1440·390 폭, 256경기, 페이지 오류 0, `exec-plans/evidence/ep224/ex153-viewer-check.json`).
- **판정**: 같은 슬롯 차이(v8t − v7t) −0.0078, 95% [−0.0781, +0.0703] → **퇴보를 배제하지 못함**. v8t 우세 9, v7t 우세 10, 같음 109.

| 모델 | 승/무/패 | 평균 점수 | 95% | 기술 실패·무효 | 테라 사용 경기 | 지연 p50 |
|---|---|---:|---|---:|---:|---:|
| laya-v7t | 112/0/16 | 0.875 | [0.805, 0.938] | 171/3310 (5.17%) | 28/128 | 0.143초 |
| laya-v8t | 111/0/17 | 0.867 | [0.805, 0.922] | 126/3465 (3.64%) | 21/128 | 0.168초 |

- 3회 이상 연속 실패 루프 경기 v7t 5, v8t 6. 최장은 v7t Whirlwind 32회, v8t Stealth Rock 18회(v8t-m23-s1-b). v8t에서 Whirlwind는 실패 상위에서 빠졌고, Will-O-Wisp 22/66·Stealth Rock 18/76이 늘었다. Aurora Veil 실패 v7t 0/6, v8t 4/9.
- 팀 유형별로 공격형은 v8t가 낮고(0.875 → 0.750), 수비형(0.812 → 0.875)·밸런스(0.938 → 0.969)는 높다.

## 결론 및 후속 작업

- 엔진 실패 표시는 실패 기술을 171 → 126(5.17 → 3.64%)으로 줄였다. 성적 차이는 1경기이고 하한 −0.0781이 −0.05 아래라 "퇴보를 배제하지 못함"이다.
- v8t의 남은 실패 상위는 Earthquake 22, Will-O-Wisp 22, Stealth Rock 18이다. 이 실패들의 원인은 따로 분석하지 않았다.
- 직접 대결 [EX-154](EX-154-laya-head-to-head-v8t-v7t.md)는 실행되지 않았다. v8t는 사람 팀 비교([EX-159](EX-159-laya-human-teams-v7t-v8t-v9t.md))에 쓰였다.
