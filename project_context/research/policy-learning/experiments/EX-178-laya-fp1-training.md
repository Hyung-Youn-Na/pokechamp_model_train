# EX-178 — laya fp1 처음부터 전체 학습(GPU 4장 DDP, 약 24시간)

- 상태: Running
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

진행 중이다(2026-11-18).

- DDP 검사(`EX-178/check.log`): 64항목, loss DDP=단일 2.18331(차이 0), gradient 상대 차이 1.7e-6, 다시 읽은 logit 차이 0. 통과.
- 사전 측정(`EX-178/measure`, 60 update): checkpointing 없음 0.0236 s/행·최대 22.6 GiB, 있음 0.0285 s/행·10.0 GiB. checkpointing 없이 3 epoch(1,241,896행)는 약 24.4시간이다.
- 학습: 07:2xZ 시작(`train --checkpointing 0`, `scripts/mem-guard 100`, 로그 `EX-178/train.log`, 메모리 `EX-178-memory.log`). 예상 종료 2026-11-19 07~08Z.

## 결론 및 후속 작업

아직 없다.
