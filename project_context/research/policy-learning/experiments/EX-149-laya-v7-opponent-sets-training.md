# EX-149 — laya 렌더러 v7(v6s + 상대 세트 추정 `oppset2`, Protean 실패 표시 보정) 학습(GPU0)

- 상태: Completed
- 생성일: 2026-10-31
- 책임자: Claude Code
- 관련 exec plan: [EP-223](../plans/EP-223-laya-loop-break-opponent-sets.md)
- 관련 decision: [D-200](../decisions/D-200-laya-loop-break-opponent-sets.md), [D-189](../decisions/D-189-laya-renderer-v3-opponent-sets.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-141](EX-141-laya-v6s-streaks-training.md) selected
- 기준 연구선: `research/model-training`

## 질문 및 목적

미공개 상대 칸의 usage 기반 추정(활성 상대의 아이템·특성·테라·기술, 판을 뒤집는 요소 `watch`, 벤치 요약)을 입력에 넣으면 사람 선택 재현이 어떻게 바뀌는가? 배틀 효과는 [EX-150](EX-150-laya-v6st-v7t-battle256.md)이 본다.

## 가설 또는 qualification 목표

- **qualification**:
  - `v7-all` 길이 초과 제외가 0.5% 이하다(사전 측정에서 넘으면 D-200의 사전 등록 순서로 벤치 요약을 줄인다).
  - validation 512에서 오프라인 렌더와 서빙 렌더가 같다(`v7 parity`).
  - 단위 검사 통과. 사전검사 loss 감소, 재로딩 logit 일치
- **판정 없음(보고 전용)**: D-191.
- **보고 지표**: 잠긴 test 1,024행에서 EX-149 − EX-141 같은 행 차이, replay 클러스터 bootstrap 95%(10,000회, 시드 20261040)
  - 전체 NLL·일치율, 교체 행
  - 활성 상대 미공개 칸 수별(아이템 미공개 여부, 공개 기술 0~1 / 2~3 / 4)
  - `watch` 표시가 있는 행
  - 테라 지식 held-out A/B 정답률

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-149 selected | EX-141과 같다: 시작 모델 `e929ae5c`, 설정, EX-071 분할, 테라 지식 train 57,143행, `max_len=1024`, head 512, v6s 모듈 전부 | 렌더러 v6s → v7(`oppset2` 모듈, Protean·Libero 행의 타입 무관 실패 표시) | `runs/model-training/EX-149/checkpoints/selected/` |

### 렌더러 v7 (`features_v7.py`, `compact_v7.py`)

- 사실값: v5 사실값(`laya-compact-features/v5`)에 `v7` 블록을 더한 `laya-compact-features/v7`
- `opp set:` 줄(OPP 줄 다음): 미공개 칸만. 아이템은 `item_state`가 `held`이면 공개값, `removed`이면 없음, 미공개이면 usage 상위 2개(≥0.15). 특성·테라 상위 2개(≥0.15, 확정이면 생략). 기술은 남은 칸 수로 재척도한 포함 확률 ≥ 0.25를 최대 6개
- `opp watch:` 줄: Choice Scarf·Choice Band·Choice Specs·Focus Sash·Booster Energy 아이템, Trick·Switcheroo·Encore·Destiny Bond·Memento 등 판을 뒤집는 기술의 미공개 확률 ≥ 0.15
- 벤치: `opp team:` 각 생존 벤치 항목 끝에 `| likely <아이템> <p>; <기술> <p>, …`(아이템 미공개일 때 1위, 기술 ≥ 0.30 상위 3개)
- Protean·Libero 등 `typechange`가 있는 행: v4 실패 표시가 꺼지는 대신, 대상 진영 압정 층수 최대(`foeSide` 압정)·자기 대상 기술(Rest·Substitute·벽 재설치)처럼 타입과 무관한 규칙만 적용한다

## 실행

- 실행기: `scripts/laya-imitation v7 {measure,features,data,parity,train,evaluate}`, 연결 실행 `scripts/laya-imitation-ep223 v7`
- 학습 시간 상한 없음. 중단: 제외 비율 > 0.005, GPU 오류, parity 불일치
- 자동 재실행 없음.

## 결과

- 2026-10-31 사전 측정(validation 512): 한도 내 511, 벤치 기술 2개 적용 뒤 초과 1/512(0.20%). `v7-all` train 129,964 · validation 511 · test 1,018(제외 454행, 0.344%). parity 511행 불일치 0. 사전검사 loss 2.1644 → 2.0477, 재로딩 logit 차이 0, 최대 7.8 GiB.
- 2026-10-31 17:30Z~2026-11-01 04:26Z 학습(GPU0). validation 원 NLL 2.1113 → 1.5506 / 1.4864 / **1.4784**(epoch 1/2/3), 선택 epoch 3(온도 1.2693, 보정 NLL 1.4632·일치율 47.4%). 보고 `runs/model-training/EX-149/report.md`.
- 잠긴 test 1,018행(EX-149 − EX-141, 같은 행, replay 클러스터 95%):

| 구분 | n | NLL 차이 | 95% | 일치율 차이 |
|---|---:|---:|---|---:|
| 전체 | 1018 | +0.0016 (1.4286 → 1.4332) | [−0.0274, +0.0300] | −2.46%p (48.29 → 45.78%) |
| 교체 행 | 364 | −0.0332 | [−0.0832, +0.0152] | −0.55%p |
| 강제 교체 | 116 | +0.0754 | [+0.0238, +0.1267] | −7.76%p |
| 피벗 교체 | 46 | −0.1048 | [−0.2042, +0.0003] | +10.87%p |
| 자발 교체 라벨 | 202 | −0.0793 | [−0.1589, +0.0014] | +0.99%p |
| 기술 라벨 | 623 | +0.0225 | [−0.0124, +0.0575] | −4.01%p |

- 활성 상대 미공개 칸 묶음(아이템 공개 여부 × 공개 기술 0 / 1~3 / 4, `watch` 유무, 설정 줄 없음 포함 13묶음)의 NLL 차이는 모두 95% 구간이 0을 포함한다. 아이템 공개·공개 기술 0(72행) +0.0692, 아이템 미공개·공개 기술 0·`watch`(22행) −0.1456.
- 테라 지식 held-out: A 전체 95.0 → 96.9%(A3 90.0 → 93.7%, A5 75.0 → 84.7%), B 전체 95.8 → 95.9%. ECE 0.0281 → 0.0302.
- 같은 기술 반복 확률(정체 행, 사람이 다른 수 9행) 0.4012 → 0.3831, 반복 1위 6 → 5.

## 결론 및 후속 작업

- 상대 세트 추정 입력은 사람 선택 재현을 EX-141과 구별되게 바꾸지 않았다. 일치율은 2.46%p 낮고, 강제 교체 행 NLL은 나빠졌다(95% 구간이 0 위).
- 미공개 칸이 많은 행에서 이득이 보이지 않는다. 배틀 결과는 [EX-150](EX-150-laya-v6st-v7t-battle256.md)에 있다.
- 이 체크포인트(v7t)는 EP-224~EP-227의 비교 기준으로 쓰인다.
