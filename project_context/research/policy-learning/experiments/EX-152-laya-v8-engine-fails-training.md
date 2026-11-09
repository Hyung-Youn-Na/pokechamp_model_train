# EX-152 — laya 렌더러 v8(v7 + 엔진 판정기 실패 표시) 학습(GPU1)

- 상태: Completed
- 생성일: 2026-11-02
- 책임자: Claude Code
- 관련 exec plan: [EP-224](../plans/EP-224-laya-engine-judge-v8.md)
- 관련 decision: [D-201](../decisions/D-201-laya-engine-judge-v8.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-149](EX-149-laya-v7-opponent-sets-training.md) selected
- 기준 연구선: `research/model-training`

## 질문 및 목적

선택지의 `; fails` 표시를 엔진 판정기([EX-151](EX-151-laya-engine-judge-validation.md))로 바꾸면 사람 선택 재현과 실패 표시 선택지의 확률이 어떻게 바뀌는가? 배틀 효과는 [EX-153](EX-153-laya-v7t-v8t-battle256.md)·[EX-154](EX-154-laya-head-to-head-v8t-v7t.md)가 본다.

## 가설 또는 qualification 목표

- **qualification**:
  - validation 512 사전 측정에서 길이 초과 0.5% 이하, `v8-all` 제외 0.5% 이하
  - validation 512에서 오프라인 렌더와 서빙 렌더가 같다(`v8 parity`, 판정기 재계산 포함)
  - 단위 검사 통과, 사전검사 loss 감소, 재로딩 logit 일치
- **판정 없음(보고 전용)**: D-191.
- **보고 지표**: 잠긴 test 1,024행에서 EX-152 − EX-149 같은 행 차이(replay 클러스터 bootstrap 95%, 10,000회, 시드 20261046)
  - 전체 NLL·일치율, 교체 행, 표시 변화 묶음(v8에서 표시가 생긴 행·사라진 행·같은 행)
  - 실패 표시 행에서 표시된 선택지의 확률 합(EX-152는 v8 표시, EX-149는 같은 행의 v8 표시와 자기 v7 표시), argmax가 표시 선택지인 행 수
  - 테라 지식 held-out A/B 정답률
  - 판정기가 국면을 재현하지 못해 기존 규칙으로 대신한 결정·선택지 비율

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-152 selected | EX-149와 같다: 시작 모델, 설정, EX-071 분할, 테라 지식 train 행, `max_len=1024`, head 512, v7 모듈 전부 | 선택지 실패 표시: 규칙(`facts['v4']['fails']` + v7 압정 보정) → 판정기 확정 실패(`laya-engine-judge/v1`) | `runs/model-training/EX-152/checkpoints/selected/` |

### 렌더러 v8 (`integration/laya_engine/render_v8.py`)

- v7 텍스트(`compact_v7.render`, 모든 모듈)에 판정기의 확정 실패만 `; fails`(`fails`·`immune`·`absorbed`) 또는 `; bounced`(`reflected`)로 붙인다.
- 엔진 오류로 판정하지 못한 선택지는 기존 규칙 표시를 쓴다. `likely fails`는 표시하지 않는다.
- 사실값은 `laya-compact-features/v5`, 판정은 `laya-engine-judge/v1`(서빙은 둘 다 실시간 계산).

## 실행

- 실행기: `scripts/laya-imitation v8 {measure,data,parity,train,evaluate}`, 연결 실행 `scripts/laya-imitation-ep224 train`
- 학습 시간 상한 없음. 중단: 제외 비율 > 0.005, GPU 오류, parity 불일치
- 자동 재실행 없음.

## 결과

- 2026-11-02 사전 측정 초과 1/512(0.20%). `v8-all` train 129,963 · validation 511 · test 1,018(제외 455행, 0.345%). parity 511행 불일치 0. 사전검사 loss 2.1668 → 2.0539, 재로딩 logit 차이 0, 최대 7.8 GiB.
- 2026-11-02 03:45Z~14:41Z 학습(GPU1). validation 원 NLL 2.1103 → 1.5326 / 1.5053 / **1.4846**(epoch 1/2/3), 선택 epoch 3(온도 1.1605, 보정 NLL 1.4633·일치율 46.0%). 보고 `runs/model-training/EX-152/report.md`.
- 잠긴 test 1,018행(EX-152 − EX-149, 같은 행, replay 클러스터 95%):

| 구분 | n | NLL 차이 | 95% | 일치율 차이 |
|---|---:|---:|---|---:|
| 전체 | 1018 | −0.0104 (1.4332 → 1.4227) | [−0.0381, +0.0170] | +0.98%p (45.78 → 46.76%) |
| 교체 행 | 364 | +0.0216 | [−0.0254, +0.0685] | +0.00%p |
| 실패 표시 v8에서 생김(v8 only) | 19 | +0.0329 | [−0.1806, +0.2430] | +5.26%p |
| 실패 표시 v8에서 사라짐(v7 only) | 33 | +0.0251 | [−0.1333, +0.1908] | +0.00%p |
| 실패 표시 같음 | 185 | −0.0501 | [−0.1122, +0.0105] | +0.54%p |
| 실패 표시 다름 | 16 | +0.0657 | [−0.1331, +0.2637] | +0.00%p |
| 실패 표시 없음 | 765 | −0.0051 | [−0.0371, +0.0276] | +1.05%p |

- 실패 표시 선택지의 확률 합(test):
  - v8 표시 220행(사람이 표시된 수 8): EX-152 0.0407, EX-149 0.0512, 차이 95% [−0.0158, −0.0053]. argmax 2 대 4.
  - v7 표시 234행(사람이 표시된 수 8): EX-152 0.0450, EX-149 0.0479, 차이 95% [−0.0087, +0.0034]. argmax 3 대 4.
- 테라 지식 held-out: A 전체 96.9 → 97.4%(A3 93.7 → 98.0%), B 전체 95.9 → 96.1%. ECE 0.0302 → 0.0358.
- 판정기 대신 기존 규칙을 쓴 경우(재현 실패 0): train 1,961결정(1.51%)·4,609선택지, validation 10결정(1.96%)·26선택지, test 13결정(1.28%)·35선택지. 비율은 분할 행 수 대비다.

## 결론 및 후속 작업

- v8 실패 표시로 학습하면 v8 표시 선택지의 확률 합이 0.0512 → 0.0407로 줄었다(95% 구간이 0 아래). 전체 재현은 EX-149와 구별되지 않는다.
- 배틀 결과는 [EX-153](EX-153-laya-v7t-v8t-battle256.md)에 있다. 직접 대결 [EX-154](EX-154-laya-head-to-head-v8t-v7t.md)는 실행되지 않았다.
