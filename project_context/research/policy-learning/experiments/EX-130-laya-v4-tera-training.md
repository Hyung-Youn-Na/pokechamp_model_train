# EX-130 — laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1)

- 상태: Completed
- 생성일: 2026-10-26
- 책임자: Claude Code
- 관련 exec plan: [EP-215](../plans/EP-215-laya-renderer-v4.md)
- 관련 decision: [D-192](../decisions/D-192-laya-renderer-v4-fail-out.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-124](EX-124-laya-v2-tera-knowledge-training.md) selected(v2 + 테라 지식)
- 기준 연구선: `research/model-training`

## 질문 및 목적

행동 행 입력을 v2에서 v4(확정 실패 표시 `fails`, 교체 후보 공격 피해 `out`)로 바꾸면 사람 선택 재현과 실패 선택지 확률이 어떻게 달라지는가? 배틀 효과는 [EX-131](EX-131-laya-v2t-v4t-battle256.md)이 본다.

## 가설 또는 qualification 목표

- **qualification**:
  - v4 자료의 길이 초과 제외가 0.5% 이하다.
  - 오프라인 자료와 서빙 렌더가 validation 512행에서 같다(`v4 parity`).
  - 사전검사 loss가 줄고 저장 후 재로딩 logit이 같다.
- **판정 없음(보고 전용)**: D-191에 따라 이 실험의 결과는 EX-131 실행 여부를 정하지 않는다.
- **보고 지표**(잠긴 test 1,024, EX-130 selected − EX-124 selected 같은 행 차이, replay 클러스터 bootstrap 95%, 10,000회, 시드 20261028):
  - 전체 NLL과 일치율, 교체 행(voluntary/forced/pivot) NLL
  - 실패 표시가 붙은 행과 붙지 않은 행별 차이
  - 실패로 정해진 선택지의 확률 합 평균과 1위 횟수(`evaluation_effects.fail_metrics`, 같은 규칙). 사람이 그 선택지를 고른 행 수를 함께 적는다.
  - 사람 테라 test 행의 테라 확률 합, 테라 지식 held-out A/B 정답률
- EX-124 쪽 값은 저장된 test 예측과 지식 평가 결과를 쓴다. 다시 추론하지 않는다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-130 selected | EX-124와 같은 시작 모델 `e929ae5c`, 설정, EX-071 분할, 테라 지식 train 57,143행(바이트 동일), head 512 | 행동 행 렌더러 v2 → v4 | `runs/model-training/EX-130/checkpoints/selected/` |

### 렌더러 v4 (`compact_v4.py`, `features_v4.py`)

- **`fails`**: 기술 선택지 끝에 `; fails`(Magic Bounce는 `; bounced`)를 붙인다.
  - `effect_knowledge.option_outcomes`(EX-126 규칙, 엔진 oracle 검증)의 결과가 `fails`/`immune`/`absorbed`/`reflected`일 때다.
  - 공개되지 않은 상대 특성·도구는 모든 경우가 같을 때만 표시한다. Tera Blast·Tera Starstorm의 테라 선택지는 표시하지 않는다.
- **`out`**: 교체 선택지 끝에 `; out b%`를 붙인다. 그 포켓몬의 공격기 중 상대 활성에 가장 큰 피해의 최댓값이다.
  - 공격 측은 `features._own_spec(mon, active=False)`, 상대는 v2 가정 세트(`features._opp_spec`), 계산기는 고정 `@smogon/calc` 0.11.0이다.
  - 계산 오류면 표시하지 않는다.
- **길이**(사전 측정, validation 512):
  - `out a-b%`: 507/512(5행 선택지 초과)
  - `out b%`: 512/512, 전체 최대 945, head 최대 470, 선택지 최대 48 → 동결
- 실패 표시가 붙는 행: validation 119/512(23%). 사람이 표시된 선택지를 고른 행은 3행이다.

### 자료 (`data_v4.py`)

- 정보 캐시 `laya-compact-features/v4`: 행마다 `features_v4.compute` 값(v2 사실 + `v4` 블록)
- 학습 자료 `laya-compact-imitation/v4-all`: 여섯 모듈 전부, 한도 1,024 / 512 / 48. 초과 행은 `exclusions.jsonl`에 남긴다.
- 학습 시 테라 지식 train 행을 더한다(`training.EX130.extra_train`). 보정 400행은 모방 행에서만 뗀다. validation과 선택은 `v4-all` validation 512다.

### 학습 설정

- EX-124와 같다: 3 epoch, soft-CE, 선택지 순서 섞기, lr, seed 0, `max_len=1024`, `head_max_len=512`
- 상한은 최초 GPU 시계부터 14시간이다.

## 환경 및 출처

- branch, commit: `research/model-training` `feda62f7…`. 소스 identity는 run `source/`에 둔다.
- 장치: GPU1(`GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`, `gpu1.lock`, UUID와 유휴 확인)
- 실행기: `scripts/laya-imitation v4 {measure,features,data,parity,train,evaluate}`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-130`

## 격리 및 오염 통제

- 실패 규칙과 계산기는 사람 라벨이나 test를 보지 않는다. 사람 라벨은 바꾸지 않는다.
- 잠긴 test(`v4-all` test)는 학습과 선택에 쓰지 않는다.
- **viewer**: 비배틀이므로 해당 없다.
- **재개**: 지원하지 않는다. 자동 재실행은 없다.

## 절차

1. v4 사전 측정(CPU), 정보 캐시 생성(CPU 16 프로세스), 봉인
2. `v4-all` 자료 생성, 제외 비율 확인, 봉인
3. `v4 parity`(validation 512)
4. GPU1 사전검사 → 본학습 → 선택과 보정
5. 테라 지식 held-out 평가(EX-130 selected 1회)
6. 잠긴 test(EX-130 selected 1회) → EX-124 쌍비교 → 보고, 봉인, GPU1 반환

## 승인·무효화·중단 조건

- **승인**: 1~6 완료와 봉인
- **무효**: parity 불일치, 자료 해시 불일치, 재로딩 불일치
- **중단**: 제외 비율 > 0.005, 14시간 상한, GPU 오류

## 테스트·평가 도구 결함 복구

C-018과 EX-118 절차를 적용한다. 원본을 `diagnostics/<단계>-vN`에 보존하고, 수정과 독립 검증 뒤 해당 단계만 1회 재시도한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| v4 정보 캐시 | `/mnt/.../datasets/generated/laya-compact-features/v4` | `checksums.sha256` | 생성·봉인 |
| v4 자료 | `/mnt/.../datasets/generated/laya-compact-imitation/v4-all` | `checksums.sha256` | 생성·봉인 |
| 학습 run | `/mnt/.../runs/model-training/EX-130` | `checksums.sha256`, `report.md` | 완료·봉인 |

## 결과

- 2026-10-26 자료: v4 정보 캐시 train 130,411 · validation 512 · test 1,024(46.5초). 실패 표시 행 train 33,855 · validation 119 · test 234. `v4-all` 길이 제외 85행(0.064%, train 84 · test 1). parity 512행 불일치 0.
- 2026-10-26 학습 02:43Z~12:12Z(GPU1). 사전검사 loss 2.1543 → 1.9894, 재로딩 logit 차이 0. validation 원 NLL 2.1221 → 1.5907 / **1.4954** / 1.5128(epoch 1/2/3), 선택 epoch 2(온도 0.9789, 보정 NLL 1.4968·일치율 45.1%). 평가 12:12~12:15Z. 보고 `runs/model-training/EX-130/report.md`.
- 잠긴 test 1,023행(길이 제외 1행, EX-130 − EX-124, 같은 행, replay 클러스터 95%):

| 구분 | n | NLL 차이 | 95% | 일치율 차이 |
|---|---:|---:|---|---:|
| 전체 | 1023 | −0.0283 (1.4506 → 1.4229) | [−0.0595, +0.0023] | +0.78%p (47.85 → 48.58%) |
| 교체 행 | 365 | −0.0662 | [−0.1167, −0.0144] | +4.66%p |
| 자발 교체 라벨 | 203 | −0.1132 | [−0.1919, −0.0319] | +6.40%p |
| 강제 교체 | 116 | −0.0213 | [−0.0859, +0.0429] | +2.59%p |
| pivot 교체 | 46 | +0.0283 | [−0.0727, +0.1282] | +2.17%p |
| 기술 라벨 | 627 | −0.0087 | [−0.0508, +0.0332] | −1.44%p |
| 실패 표시가 붙은 행 | 234 | −0.0527 | [−0.1197, +0.0132] | +0.85%p |
| 실패 표시가 없는 행 | 789 | −0.0211 | [−0.0557, +0.0132] | +0.76%p |

- 실패로 정해진 선택지가 있는 test 234행(사람이 그 선택지를 고른 행 8): 확률 합 평균 0.0562 → 0.0312(차이 −0.0250, 95% [−0.0356, −0.0156]), 1위 6 → 1행.
- 사람 테라 test 20행의 테라 확률 합 0.1762 → 0.1723.
- 테라 지식 held-out: A 전체 96.9 → 96.6%(A3 91.0 → 94.3%, A5 87.3 → 81.7%), B 전체 95.8 → 95.6%. ECE 0.0365 → 0.0330.

## 분석 및 한계

- 실패 표시는 공개 상태로 정해지는 경우만이다(Whirlwind/Roar 교체 대상 없음, Wish 중복은 빠진다).
- `out`은 가정 세트 기준 최댓값이다.
- 테라 B 지식 행은 v2 상태 텍스트다.
- 단일 시드 학습이다.

## 결론 및 후속 작업

- 실패 표시는 의도대로 작동했다. 실패로 정해진 선택지의 확률 합이 0.0562 → 0.0312로 줄고 1위가 6 → 1행이 됐다.
- 교체 행 재현이 좋아졌다(NLL −0.0662, 자발 교체 −0.1132). 전체 NLL 차이 구간은 0을 포함한다.
- 테라 지식 A5가 떨어졌다(87.3 → 81.7%).
- 배틀 결과는 [EX-131](EX-131-laya-v2t-v4t-battle256.md)(Abyssal, 퇴보를 배제하지 못함)과 [EX-135](EX-135-laya-head-to-head-v2tw-v4t.md)(직접 대결, 구별되지 않음)에 있다.
