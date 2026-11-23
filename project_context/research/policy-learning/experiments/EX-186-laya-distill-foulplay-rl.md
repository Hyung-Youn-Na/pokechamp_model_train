# EX-186 — 증류 모델에서 시작하는 foul-play 상대 강화학습(KL 제약, 학습 팀)

- 상태: Paused
- 생성일: 2026-11-19
- 책임자: Claude Code
- 관련 exec plan: [EP-236](../plans/EP-236-laya-v11rtc-foulplay-distill-rl.md)
- 관련 decision: [D-215](../decisions/D-215-laya-foulplay-distill-then-rl.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-183](EX-183-laya-v11rtc-distill-training.md) selected(출발점·KL 기준)
- 기준 연구선: `research/model-training`

## 질문 및 목적

증류 모델을 foul-play 상대 경기의 승패로 몇 라운드 다듬으면 학습 팀 경기의 점수가 오르는가?

## 가설 또는 qualification 목표

- **qualification**(라운드 1 전): 표본 정책 경기 mock 2/2 정상, 기록된 선택 확률이 서빙 확률과 같다, 학습 행의 가중 합이 계획과 같다.
- **판정 없음(보고 전용)**. 라운드별 학습 팀 경기 점수(조합 클러스터 95%)와 KL(기준 정책 대비)을 보고한다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 시작·기준 정책 | EX-183 selected |
| 상대 | foul-play, EX-174와 같은 설정 |
| 팀 | laya-play `teams.json`·`teams_trained.json`·`teams_ex120.json`에서 EX-174 collection의 Blim 64팀(여섯 종이 같은 팀)을 뺀 팀. 대진·시드·진영 교환은 라운드마다 새로 뽑는다(seed 20261186 + 라운드) |
| 수집 | 라운드당 최대 192경기, laya는 서빙 분포에서 표본 추출(T=1, 경기별 seed), 결정마다 선택·확률 기록 |
| 갱신 | 정책 경사: 결정 행 `expected`=고른 수, 가중 = 경기 보상(승 +1 / 무 0 / 패 −1)에서 라운드 평균을 빼고 표준편차로 나눈 값. KL 제약: 같은 결정의 기준 정책 분포를 `gold`로 한 행을 가중 β=0.5로 더한다. `train_v11` 경로, 1 pass, lr은 EX-183의 0.2배 |
| 라운드 | 최대 4. 라운드 평균 점수가 라운드 1보다 0.1 넘게 낮으면 멈춘다 |
| 자원 | 수집 CPU(동시 경기 수는 구현 때 측정해 기록), 갱신 GPU 0~3, mem-guard 60 |

## 실행

- 실행기: `scripts/laya-distill-ep236 rl`(`integration/laya_distill/rl.py`). EX-185 뒤에 시작한다. 마지막 라운드 모델을 `checkpoints/selected`로 둔다(라운드 선택 없음).
- 동시 경기 수, 라운드당 경기 수가 시간 상한(라운드당 6시간)을 넘으면 경기 수를 줄이고 그 값을 진행 절에 적는다.

## 결과

아직 없다.

## 결론 및 후속 작업

아직 없다.
