# EX-183 — v11rtc + foul-play 탐색 증류 학습(1 epoch, GPU 4장)

- 상태: Completed
- 생성일: 2026-11-19
- 책임자: Claude Code
- 관련 exec plan: [EP-236](../plans/EP-236-laya-v11rtc-foulplay-distill-rl.md)
- 관련 decision: [D-215](../decisions/D-215-laya-foulplay-distill-then-rl.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-172](EX-172-laya-v11rtc-training.md) selected(출발점)
- 기준 연구선: `research/model-training`

## 질문 및 목적

v11rtc에 사람 행과 foul-play 교사 행을 섞어 1 epoch 더 학습하면, 교사 분포와 얼마나 가까워지고 사람 선택 재현은 얼마나 바뀌는가?

## 가설 또는 qualification 목표

- **qualification**: 사전 측정(60 update) loss 감소, 재로딩 logit 일치, 교사 행이 laya에서 모두 쓰인다(`skipped` 0).
- **판정 없음(보고 전용)**: D-191.
- **보고 지표**: 교사 validation의 CE·1순위 일치(EX-172 대비), 사람 validation·잠긴 test 두 개의 NLL·일치율(EX-172 대비 같은 행 차이, replay 클러스터 bootstrap 95%), 교체·테라 선택 비율.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 시작 | EX-172 `checkpoints/selected` |
| 학습 경로 | `laya_v11.train_v11`(soft-CE, 1 epoch, 4지점 validation·체크포인트, cosine lr, 전체 배치 64 = micro 8 × 누적 2 × 4장, 2,048 / head 768 / 선택지 64) |
| 사람 행 | EX-172 train 행 중 무작위 25%(seed 20261183), EX-172 가중 그대로. EX-172 교정 행은 학습 행의 약 2%(EX-172와 같은 규칙), 테라 지식 행 그대로 |
| 교사 행 | EX-182 교사 train 행 × 2 |
| validation(선택) | EX-182 교사 validation 행(`gold`). 4지점 중 CE가 가장 낮은 지점, 같으면 앞 지점. 온도는 EX-172와 같은 보정 행으로 다시 맞춘다 |
| 자원 | GPU 0~3, `scripts/mem-guard 60` |

## 실행

- 실행기: `scripts/laya-distill-ep236 train`(`integration/laya_distill/train_distill.py`).
- 중단: GPU 오류, loss NaN, 교사 행 skipped > 0. 자동 재실행 없음.

## 결과

- 학습 행 480,876(사람 가중 > 0 307,283 · 테라 지식 · 교정 행 · 교사 53,462 × 2), GPU 4장 15,028 step, 2026-11-20 00:34Z~03:46Z(3.2시간). 사전 측정 60 update 손실은 1.338 → 1.395로 줄지 않았다(EX-171·172와 같은 모양, EP-236 기록). 재로딩 logit 차 0.
- validation(교사 2,364행, raw CE / 1순위 일치): 지점 0 1.993/0.462 → 1 1.840/0.470 → 2 1.818/0.477 → 3 1.805/0.487 → 4 1.8045/0.481. **선택 지점 4**(CE 최저).
- 보고(`runs/model-training/EX-183/evaluation/report.md`, 온도 보정 후):

| 항목 (EX-183 − EX-172) | 행 | 차이 | 95% |
|---|---:|---:|---|
| 교사 CE | 2364 | −0.0909 | [−0.0993, −0.0822] |
| 교사 1순위 일치 | 2364 | +0.0161 | [+0.0055, +0.0270] |
| 대회 test NLL | 1024 | +0.0064 | [−0.0083, +0.0215] |
| 대회 test 일치 | 1024 | +0.0137 | [−0.0051, +0.0327] |
| 래더 test NLL | 1024 | +0.0086 | [−0.0080, +0.0248] |
| 래더 test 일치 | 1024 | −0.0029 | [−0.0215, +0.0157] |

- 교사 validation에서 사람 선택 일치 0.513 → 0.508, argmax 교체 0.288 → 0.275(교사 교체 몫 0.371), argmax 테라 0.009 → 0.011(교사 0.058).

## 결론 및 후속 작업

교사 분포 쪽으로 구별되게 움직였고(CE −0.091, 1순위 +1.6%p) 사람 재현은 구별되게 나빠지지 않았다. 움직임은 작다: 1순위 일치 48%로 탐색과 절반 넘게 다르고, 교체·테라 비율은 교사 쪽으로 가지 않았다. 배틀 효과는 EX-185(EX-184와 같은 슬롯)로 본다.
