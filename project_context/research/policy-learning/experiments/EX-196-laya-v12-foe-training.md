# EX-196 — laya v12 + 상대 예측 이어 학습(EX-192에서 1 epoch, GPU 4장)

- 상태: Completed
- 생성일: 2026-11-22
- 책임자: Claude Code
- 관련 exec plan: [EP-238](../plans/EP-238-laya-opponent-prediction-one-turn-read.md)
- 관련 decision: [D-216](../decisions/D-216-laya-opponent-prediction-one-turn-read.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

v12 모델(EX-192)에 상대 행동 예측을 함께 학습시키면 상대 예측이 얼마나 맞고, 사람 선택 재현은 유지되는가?

## 조건

| 항목 | 조건 |
|---|---|
| 시작 | EX-192 `checkpoints/selected` |
| 학습 경로 | `laya_v11.train_v11`(EX-172의 이어 학습 경로: 1 epoch, 25·50·75·100% 지점 validation, 최저 NLL 지점 선택, 온도 재적합)을 `integration/laya_foe/train_foe.py`로 감싼다. GPU 0~3, 전체 배치 64 |
| 행 | `v12-fresh` train(새 모방 행) + EX-195 상대 train 행 + 테라 지식 행(EX-167과 같음) |
| validation | v12-ladder-merged validation(사람 모방, EX-192와 같음) |
| 평가 | (1) 상대 예측 held-out: 1순위 일치·NLL, 기준은 EX-192(같은 질문, 학습 전) (2) 잠긴 test v12 대회·래더: EX-192와 같은 행 차이 (3) 테라 지식 held-out (4) held-out 경기의 모방 행 NLL |
| 중단 | GPU 오류, loss NaN, 학습 실패. 자동 재실행 없음 |

## 결과

보고: `runs/model-training/EX-196/evaluation/report.md`. 학습은 2026-11-21T16:13Z~22:42Z, 평가는 23:21Z에 끝났다.

- 선택 지점 4/4, validation NLL 1.2791(시작 1.2847), 일치율 50.20% → 52.15%.
- 상대 행동 예측(held-out 400경기, 6,000행, 평균 선택지 9.4개): NLL 2.4128 → 1.4290(차이 -0.984 [-1.018, -0.948]), 1순위 15.23% → 48.18%, 상위 3 41.27% → 81.82%. 라벨 종류별 1순위는 기술 56.37%, 교체 31.93%, 아직 안 쓴 기술 35.03%다.
- 사람 모방(같은 held-out 경기, 6,000행): NLL 1.1991 → 1.1729(-0.026 [-0.035, -0.017]), 일치율 54.20% → 55.13%.
- 잠긴 test(v12): 대회 EX-071 1.2531 → 1.2413(-0.012 [-0.034, +0.012]), 래더 EX-166 1.2304 → 1.2432(+0.013 [-0.011, +0.037]). 둘 다 구별되지 않는다.
- 테라 지식 held-out: A 91.43% → 95.52%, B 94.96% → 96.03%.

## 결론 및 후속 작업

상대 예측 질문을 배웠고(1순위 3배 이상), 사람 선택 재현은 떨어지지 않았다. 이 모델로 EX-197(한 턴 읽기)·EX-198(argmax 대조) 대전을 진행한다.
