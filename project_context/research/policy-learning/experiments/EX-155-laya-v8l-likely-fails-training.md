# EX-155 — laya 렌더러 v8l(v8 + `likely fails` 표시) 학습(GPU2)

- 상태: Completed
- 생성일: 2026-11-02
- 책임자: Claude Code
- 관련 exec plan: [EP-224](../plans/EP-224-laya-engine-judge-v8.md)
- 관련 decision: [D-201](../decisions/D-201-laya-engine-judge-v8.md)(추가 결정), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-152](EX-152-laya-v8-engine-fails-training.md) selected(v8), [EX-149](EX-149-laya-v7-opponent-sets-training.md) selected(v7)
- 기준 연구선: `research/model-training`

## 질문 및 목적

D-201은 확률 실패(`likely fails`, EX-151에서 176건 중 132건 실제 실패)를 v8에 표시하지 않았다. 사용자 지시(2026-11-02)로 이것까지 표시한 변형을 따로 학습한다. 표시가 Protect 연속·잠든 Sleep Talk 선택 확률과 사람 선택 재현을 어떻게 바꾸는가?

## 가설 또는 qualification 목표

- **qualification**: validation 512 사전 측정 초과 0.5% 이하(측정 1/512), `v8l-all` 제외 0.5% 이하, `v8l parity` 일치, 단위 검사, 사전검사 loss 감소·재로딩 logit 일치
- **판정 없음(보고 전용)**: D-191
- **보고 지표**: 잠긴 test에서 EX-155 − EX-152, EX-155 − EX-149 같은 행 차이(replay 클러스터 95%, 시드 20261049), `likely fails` 표시 행의 표시 선택지 확률 합·argmax(세 모델), 확정 실패 표시 확률 합, 테라 지식

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-155 selected | EX-152와 같다(시작 모델, 설정, 분할, 테라 지식 행, v8 표시) | 확정 실패 표시가 없는 선택지에 판정기 `likely fails`를 `; likely fails`로 추가(`render_v8l.py`) | `runs/model-training/EX-155/checkpoints/selected/` |

- `likely fails`: Protect류 기술을 직전 턴부터 연속 성공한 뒤(성공 확률 1/3^n), 또는 깨어날 확률 1/2 이상인 Sleep Talk·Snore(EX-151 정의).
- 자료 `laya-compact-imitation/v8l-all`, 렌더 동일성 `serving.V8L_RENDER_FILES`(v8 파일 + `render_v8l.py`·`data_v8l.py`).

## 실행

- 실행기: `scripts/laya-imitation v8l {measure,data,parity,train,evaluate}`, 연결 실행 `scripts/laya-imitation-ep224b gpu2`(EX-155 학습 → EX-152 봉인 대기 → 평가 → EX-154)
- GPU2(EX-154보다 먼저). 학습 시간 상한 없음. 자동 재실행 없음.
- 배틀: [EX-156](EX-156-laya-v8t-v8lt-battle256.md)(v8t 대 v8lt, Abyssal 256경기, 사용자 지시로 예약)

## 결과

- 2026-11-02 — `v8l-all` 생성: 제외 455행(0.345%, v8과 같음), likely 표시 train 1,956행·3,102선택지(사람이 표시된 수 선택 104행), validation 8행·11선택지, test 7행·12선택지. parity 511/511 일치. 사전검사 loss 2.166→2.046, 재로딩 logit 차이 0. 04:50Z GPU2 학습 시작.
- 2026-11-02 04:50Z 학습 시작(GPU2, epoch 3까지 경과 38,932초). EX-152 완료(15:41Z)를 기다려 평가, 15:43Z 완료. validation 원 NLL 2.1094 → 1.5366 / 1.5033 / **1.5012**(epoch 1/2/3), 선택 epoch 3(온도 1.1360, 보정 NLL 1.4841·일치율 45.2%). 보고 `runs/model-training/EX-155/report.md`.
- 잠긴 test 1,018행(같은 행, replay 클러스터 95%):

| 구분 | n | EX-155 − EX-152 NLL | 95% | EX-155 − EX-149 NLL | 95% |
|---|---:|---:|---|---:|---|
| 전체 | 1018 | +0.0123 (1.4227 → 1.4350) | [−0.0162, +0.0404] | +0.0018 (1.4332 → 1.4350) | [−0.0240, +0.0283] |
| 교체 행 | 364 | +0.0062 | [−0.0402, +0.0529] | +0.0279 | [−0.0201, +0.0756] |
| likely 표시 행 | 7 | +0.1943 | [−0.0590, +0.5998] | +0.1674 | [−0.1543, +0.4776] |
| 결정 lead | 31 | +0.1107 | [+0.0403, +0.1842] | +0.0582 | [−0.0026, +0.1295] |
| 결정 forced_switch | 116 | −0.0197 | [−0.0734, +0.0349] | −0.0644 | [−0.1145, −0.0122] |

- 일치율 46.66%(EX-152 46.76%, EX-149 45.78%). ECE 0.0533(EX-152 0.0358).
- `likely fails` 표시 test 7행(사람이 표시된 수 0): 표시 선택지 확률 합 EX-155 0.0812, EX-152 0.0765, EX-149 0.0815. argmax 세 모델 모두 0. 차이 95% EX-155 − EX-152 [−0.0328, +0.0398], EX-155 − EX-149 [−0.0369, +0.0284].
- 확정 실패(v8) 표시 220행: 확률 합 EX-155 0.0390, EX-152 0.0407(차이 95% [−0.0085, +0.0042]), EX-149 0.0512(차이 95% [−0.0183, −0.0065]). argmax EX-155 2, EX-152 2, EX-149 4. 근거 `evaluation/report.json`.
- 테라 지식 held-out(EX-155): A 전체 98.0%(A3 96.3%, A5 91.3%), B 전체 96.0%. EX-152는 A 97.4%, B 96.1%다.

## 결론 및 후속 작업

- `likely fails` 표시는 test에 7행뿐이고, 그 행의 확률 합·argmax는 EX-152·EX-149와 구별되지 않는다. 전체 재현도 구별되지 않는다.
- 선봉(lead) 행 NLL은 EX-152보다 나빠졌다(95% 구간이 0 위, 31행). 보정 ECE도 커졌다.
- 배틀 결과는 [EX-156](EX-156-laya-v8t-v8lt-battle256.md)에 있다. v8lt는 이후 EP-226(EX-160)·EP-228(EX-163·164)의 정책으로 쓰였다.
