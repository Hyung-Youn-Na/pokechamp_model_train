# EX-178 — laya fp1 처음부터 전체 학습(GPU 4장 DDP, 약 24시간)

- 상태: Completed
- 생성일: 2026-11-18
- 책임자: Claude Code
- 관련 exec plan: [EP-234](../plans/EP-234-laya-fp1-foulplay-input.md)
- 관련 decision: [D-213](../decisions/D-213-laya-fp1-foulplay-input.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-167](EX-167-laya-v10-ladder-training.md) selected(v10rt)
- 기준 연구선: `research/model-training`

## 질문 및 목적

같은 출발점·행·학습량에서 입력을 fp1로 바꾸면 사람 선택 재현이 어떻게 달라지는가? 배틀 효과는 [EX-179](EX-179-laya-fp1-vs-foulplay-blim128.md)가 본다.

## 가설 또는 qualification 목표

- **qualification**:
  - DDP 검사: 4장과 1장의 손실·기울기가 수치 오차 안에서 같다.
  - 사전 측정: 처리량이 EX-167의 0.0216초/행 근처인지 확인하고, 예상 시간을 적는다.
  - 사전검사 loss가 감소하고, 재로딩 logit이 일치한다.
- **판정 없음(보고 전용)**: D-191.
- **보고 지표**: EX-178 − EX-167 같은 행 차이, replay 클러스터 bootstrap 95%(10,000회)
  - 잠긴 test 두 개(EX-071 1,024, EX-166 1,024) 각각의 NLL·일치율·ECE, 결정 종류별 차이
  - 실패 선택지 확률 합

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 |
|---|---|---|
| EX-178 selected | EX-167과 같다: `laya-typed-decisions@e929ae5c`, 3 epoch, soft-CE, 선택지 섞기, lr(encoder 2.5e-5 · head 1e-4 → 1e-6 cosine), seed 0, 전체 배치 64(장당 micro 8 × 누적 2), 2,048 / head 768 / 선택지 64, validation 1,024 | 렌더러 fp1(EX-177), 테라 지식 행 없음 |

- 선택: epoch별 validation NLL이 가장 낮은 지점. 온도는 EX-167과 같은 방식으로 다시 맞춘다.

## 실행

- 실행기: `scripts/laya-fp1-ep234 train`(EX-167 DDP 경로 재사용, 이름은 구현 때 확정). GPU 0~3, `scripts/mem-guard 100`.
- 시작 조건: EX-177 완료, EP-231 래더 비교 종료(GPU 2·3 비움).
- 중단: GPU 오류, DDP 검사 불일치, loss NaN. 자동 재실행 없음.

## 결과

완료(2026-11-19). 보고 `runs/model-training/EX-178/evaluation/report.md`, 평가 코드 `integration/laya_fp1/evaluation_fp1.py`.

- DDP 검사(`EX-178/check.log`): 64항목, loss DDP=단일 2.18331(차이 0), gradient 상대 차이 1.7e-6, 다시 읽은 logit 차이 0. 통과.
- 사전 측정(`EX-178/measure`, 60 update): checkpointing 없음 0.0236 s/행·최대 22.6 GiB, 있음 0.0285 s/행·10.0 GiB. checkpointing 없이 3 epoch(1,241,896행)는 약 24.4시간이다.
- 학습: 07:2xZ 시작(`train --checkpointing 0`, `scripts/mem-guard 100`, 로그 `EX-178/train.log`, 메모리 `EX-178-memory.log`). 07:04Z 종료(84,860초).

- validation NLL(1,024행): epoch 0 2.0933, 1 1.4414, 2 **1.3806**, 3 1.4106(epoch 3에서 다시 오름; EX-167은 1.4729 → 1.3861 → 1.3681). 선택 epoch 2, 온도 0.889(보정 뒤 validation NLL 1.389, ECE 0.041).
- 잠긴 test(같은 sample id, EX-178 − EX-167, replay 클러스터 bootstrap 95%):

  | test | EX-167 NLL / 일치율 | EX-178 NLL / 일치율 | NLL 차이 | 일치율 차이 |
  |---|---|---|---|---|
  | EX-071 대회 1,024 | 1.3305 / 0.496 | 1.3679 / 0.469 | +0.037 [−0.005, +0.079] | −0.027 [−0.055, −0.001] |
  | EX-166 래더 1,024 | 1.3284 / 0.531 | 1.3524 / 0.501 | +0.024 [−0.018, +0.066] | −0.030 [−0.060, −0.002] |

  - 결정 종류별: 기술 선택(라벨 move)은 NLL −0.044 [−0.091, +0.003](대회)·−0.026 [−0.080, +0.028](래더)로 같거나 약간 낫다. 교체가 나쁘다: 강제 교체 NLL +0.228 [+0.116, +0.342]·+0.130 [+0.046, +0.220], 일치율 −0.155·−0.140. 자발 교체 NLL +0.168·+0.117, 피벗 교체 +0.118·+0.309.
  - 직전 실패 기술 반복(`repeat`) 확률 합은 0.593 → 0.429(대회), 0.557 → 0.453(래더)로 준다(구간이 0 아래). 실패 선택지(`fails`)·위험 선택지(`danger`) 확률 합은 차이가 없다.
  - ECE는 0.034 → 0.062(대회), 0.036 → 0.054(래더)로 나빠진다.

## 결론 및 후속 작업

- 입력을 foul-play·poke-engine 정보로만 바꿔도 사람 선택 재현은 v10과 거의 같은 수준이다(전체 NLL +0.02~0.04, 구간이 0을 포함). 기술 선택은 비슷하거나 약간 낫고, 교체 결정이 확실히 나쁘다. fp1의 교체 선택지는 들어올 때의 HP와 상대 예상 기술 한두 개에 대한 결과만 적고, v10의 상성·duel 요약은 없다.
- 직전 실패 반복 확률이 준 것은 기록 문장 없이 엔진 결과(실패하면 효과 없음)가 선택지에 보이기 때문으로 보인다(해석, 검증 안 함).
- 판정 없음(D-191). 후속: [EX-179](EX-179-laya-fp1-vs-foulplay-blim128.md) foul-play Blim 128경기.
