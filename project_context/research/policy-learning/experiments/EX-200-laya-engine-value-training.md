# EX-200 — laya 엔진 가치 target 이어 학습(EX-196에서 1 epoch, GPU 4장)

- 상태: Completed
- 생성일: 2026-11-22
- 책임자: Claude Code
- 관련 exec plan: [EP-239](../plans/EP-239-laya-engine-value-rerank-training.md)
- 관련 decision: [D-217](../decisions/D-217-laya-engine-value-rerank-training.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

EX-199 soft target을 배우면 사람 재현을 유지하면서 후보 순위가 엔진 평가 쪽으로 옮겨 가는가?

## 조건

- 출발: EX-196 selected. 자료: EX-199 target 행 + v12 모방 행 + EX-195 상대 예측 행(혼합 비율은 EX-199 결과와 함께 기록). `train_v11` 경로, 4 validation 지점 중 NLL 최저 선택.
- 평가: 잠긴 test(v12), EX-195 held-out 모방·상대 예측, 테라 지식, held-out target 경기에서 target 1순위 일치율.

- 실제 혼합(`train_value.py`): anchor 사람 행 150,000(v12-fresh train, EX-199 held-out 335경기 제외, 시드 20261200) + EX-199 gold 행 153,029 전부 + EX-195 상대 예측 행 100,000 + 테라 지식 행. measure 기준 train 459,772행이다. validation은 v12-fresh validation이다.
- measure(2026-11-22T07:07Z): 행당 0.0221초 → 약 2.8시간 예상, GPU 최대 22.3 GiB, 재적재 logit 차이 0, host 예상 10.9 GB.

## 결과

2026-11-22T07:13Z~10:28Z 학습, 평가 보고는 `runs/model-training/EX-200/evaluation/report.md`. 선택 지점 4(validation NLL 1.2957, 출발 1.2791), 온도 1.031.

| 평가 | EX-196 | EX-200 | 차이(경기 클러스터 95%) |
|---|---:|---:|---|
| 엔진 target 1순위 일치(held-out 6,000결정) | 50.80% | 66.90% | +0.161 [+0.147, +0.175] |
| 같은 결정에서 사람 선택 일치 | 42.28% | 38.77% | |
| 상대 예측 NLL / 1순위(EX-195 held-out) | 1.4290 / 48.18% | 1.4454 / 48.22% | NLL +0.016 [+0.009, +0.024] |
| 사람 모방 NLL / 1순위 | 1.1729 / 55.13% | 1.1792 / 54.68% | NLL +0.006 [−0.001, +0.013] |
| 잠긴 test EX-071 NLL | 1.2413 | 1.2525 | +0.011 [−0.002, +0.025] |
| 잠긴 test EX-166 NLL | 1.2432 | 1.2529 | +0.010 [−0.007, +0.026] |
| 테라 지식 A / B | 95.52% / 96.03% | 96.90% / 96.41% | |

- 엔진 target 쪽으로는 확실히 옮겨 갔다(1순위 일치 +16%p). 사람 모방·잠긴 test는 조금 나빠졌지만 신뢰구간이 0을 걸친다. 상대 예측 NLL은 조금 나빠졌다.

## 결론 및 후속 작업

아직 없다.
