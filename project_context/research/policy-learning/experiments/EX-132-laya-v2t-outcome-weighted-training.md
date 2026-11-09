# EX-132 — laya v2+테라 승패 가중 모방 학습(GPU0)

- 상태: Completed
- 생성일: 2026-10-26
- 책임자: Claude Code
- 관련 exec plan: [EP-216](../plans/EP-216-laya-outcome-weighted-imitation.md)
- 관련 decision: [D-193](../decisions/D-193-laya-outcome-weighted-imitation.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-124](EX-124-laya-v2-tera-knowledge-training.md) selected(v2 + 테라 지식)
- 기준 연구선: `research/model-training`

## 질문 및 목적

이긴 쪽 결정에 더 큰 무게를 주는 모방 학습이 사람 선택 재현을 어떻게 바꾸는가? 배틀 효과는 [EX-133](EX-133-laya-v2t-v2tw-battle256.md)이 본다.

## 가설 또는 qualification 목표

- **qualification**:
  - 학습 행 전부가 리플레이 승패와 매칭된다.
  - 분할 크기가 EX-124와 같다(학습 187,154, 보정 400, validation 512, 지식 57,143).
  - 사전검사 loss가 줄고 저장 후 재로딩 logit이 같다.
- **판정 없음(보고 전용)**: D-191에 따라 이 실험의 결과는 EX-133 실행 여부를 정하지 않는다.
- **보고 지표**: 잠긴 test 1,024행으로 EX-132 selected − EX-124 selected 같은 행 차이를 낸다. 구간은 replay 클러스터 bootstrap 95%(10,000회, 시드 20261029)다.
  - 전체 NLL과 일치율, 교체 행 NLL
  - **그 시점의 승패별**(win/loss) 차이: 가중이 의도대로 작동했는지 보는 결함 점검이다. 이긴 쪽 행이 진 쪽보다 더 나아져야 한다.
  - 실패로 정해진 선택지의 확률 합(`evaluation_effects.fail_metrics`), 사람 테라 행의 테라 확률 합, 테라 지식 held-out A/B 정답률
- EX-124 쪽 값은 저장된 test 예측과 지식 평가 결과를 쓴다. 다시 추론하지 않는다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-132 selected | EX-124와 같다: 시작 모델 `e929ae5c`, 설정, `v2-all` 자료와 분할, 테라 지식 train 57,143행, head 512 | 모방 학습 행 target × 승패 가중치 | `runs/model-training/EX-132/checkpoints/selected/` |

### 가중치 (`outcome_weights.py`, `laya-outcome-weights/v1`)

- **매칭**: 행 `sample_id`(`<replay_id>:<perspective>:…`)를 원본 리플레이와 맞춘다.
  - 원본 경로는 EX-071 `preparation/replays.jsonl`의 `raw_path`(gzip JSON)다.
  - 원본의 `|player|p1|`·`|player|p2|` 이름과 `|win|` 이름을 Showdown id로 비교한다.
- **원값**: 이긴 쪽 1.0, 진 쪽 0.5, 무승부 0.75
- **정규화**: 모방 학습 행 평균 1(배율 1.3302)
- **행 수**: 학습 130,411행 = 승 65,360 + 패 64,434 + 무 617, 매칭 실패 0
- **적용**:
  - `training.train`에서 `split_calibration` 뒤 학습 항목의 target에만 곱한다(soft-CE가 target에 선형).
  - 보정과 validation은 가중하지 않는다. 테라 지식 행은 1.0이다.
  - 사전검사 256행에도 같은 경로로 곱한다.

### 학습 설정

- EX-124와 같다: 3 epoch, soft-CE, 선택지 순서 섞기, lr, seed 0, `max_len=1024`, `head_max_len=512`
- 선택은 가중 없는 validation 원 NLL 최소 epoch다(EX-124와 같은 규칙).
- 상한은 최초 GPU 시계부터 14시간이다.
- EX-124는 GPU1에서 학습했고, 이번은 GPU0(같은 기종 RTX A6000)이다.

## 환경 및 출처

- branch, commit: `research/model-training` `feda62f7…`. 소스 identity는 run `source/`에 둔다.
- 장치: GPU0(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, `gpu0.lock`, UUID와 유휴 확인)
- 실행기: `scripts/laya-imitation weighted {weights,train,evaluate}`, 연결 실행 `scripts/laya-imitation-ep216`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-132`

## 격리 및 오염 통제

- 가중치는 학습 행의 승패만 쓴다. validation·test 행의 승패는 보고용 분류(`sides.jsonl`)에만 쓴다.
- 잠긴 test(`v2-all` test)는 학습과 선택에 쓰지 않는다.
- **viewer**: 비배틀이므로 해당 없다.
- **재개**: 지원하지 않는다. 자동 재실행은 없다.

## 절차

1. 가중치 생성(CPU), 봉인
2. GPU0 사전검사 → 본학습 → 선택과 보정
3. 테라 지식 held-out 평가(EX-132 selected 1회)
4. 잠긴 test(EX-132 selected 1회) → EX-124 쌍비교(승패별) → 보고, 봉인

## 승인·무효화·중단 조건

- **승인**: 1~4 완료와 봉인
- **무효**: 가중치·자료 해시 불일치, 분할 크기 불일치, 재로딩 불일치
- **중단**: 매칭 실패 > 0, 14시간 상한, GPU 오류

## 테스트·평가 도구 결함 복구

C-018과 EX-118 절차를 적용한다. 원본을 `diagnostics/<단계>-vN`에 보존하고, 수정과 독립 검증 뒤 해당 단계만 1회 재시도한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 가중치 | `/mnt/.../datasets/generated/laya-outcome-weights/v1` | `checksums.sha256` | 생성·봉인 |
| 학습 run | `/mnt/.../runs/model-training/EX-132` | `checksums.sha256`, `report.md` | 완료·봉인 |

## 결과

- 2026-10-26 가중치: 학습 행 130,411(승 65,360 · 패 64,434 · 무 617), 매칭 실패 0, 배율 1.3302. 분할은 EX-124와 같다(학습 187,154, 보정 400, validation 512, 지식 57,143). 학습 분할 가중 평균 1.0000.
- 2026-10-26 학습 05:05Z~14:10Z(GPU0). 사전검사 loss 2.1521 → 1.9695, 재로딩 logit 차이 0. validation 원 NLL 2.1232 → 1.6277 / **1.5162** / 1.5686(epoch 1/2/3), 선택 epoch 2(온도 0.9587, 보정 NLL 1.5185·일치율 43.2%). 평가 14:10~14:14Z. 보고 `runs/model-training/EX-132/report.md`.
- 잠긴 test 1,024행(EX-132 − EX-124, 같은 행, replay 클러스터 95%):

| 구분 | n | NLL 차이 | 95% | 일치율 차이 |
|---|---:|---:|---|---:|
| 전체 | 1024 | +0.0003 (1.4506 → 1.4509) | [−0.0247, +0.0246] | −1.07%p (47.85 → 46.78%) |
| 교체 행 | 365 | −0.0107 | [−0.0469, +0.0248] | +0.27%p |
| 이긴 쪽 행(win) | 478 | +0.0031 | [−0.0315, +0.0375] | +0.84%p |
| 진 쪽 행(loss) | 546 | −0.0021 | [−0.0371, +0.0322] | −2.75%p |
| 자발 교체 라벨 | 203 | −0.0263 | [−0.0826, +0.0330] | +0.49%p |
| 기술 라벨 | 628 | +0.0074 | [−0.0262, +0.0400] | −1.91%p |

- 승패별 결함 점검: NLL로는 이긴 쪽 행이 진 쪽보다 더 나아지지 않았다(win +0.0031, loss −0.0021). 일치율만 이긴 쪽이 나았다(+0.84%p 대 −2.75%p). 두 구간 모두 0을 포함한다.
- 실패로 정해진 선택지가 있는 test 234행(사람이 고른 행 8): 확률 합 평균 0.0562 → 0.0638(차이 +0.0076, 95% [−0.0005, +0.0167]), 1위 6 → 6행.
- 사람 테라 test 20행의 테라 확률 합 0.1762 → 0.1866.
- 테라 지식 held-out: A 전체 96.9 → 96.8%(A3 91.0 → 94.0%, A5 87.3 → 83.7%), B 전체 95.8 → 95.9%. ECE 0.0365 → 0.0367.

## 분석 및 한계

- 승패는 경기 전체의 결과다. 진 쪽의 좋은 수와 이긴 쪽의 실수를 구분하지 않는다.
- 사람 재현 지표는 승·패 전체가 기준이다.
- 단일 시드 학습이다.

## 결론 및 후속 작업

- 승패 가중은 사람 선택 재현을 바꾸지 않았다. 전체 NLL 차이 +0.0003이고 구간이 0을 포함한다.
- 이긴 쪽 행이 더 나아져야 한다는 결함 점검은 NLL로는 확인되지 않았다. 가중 효과가 이 지표에서 보이지 않는다.
- 실패로 정해진 선택지 확률이 조금 늘었다(+0.0076, 하한 −0.0005).
- 배틀 결과는 [EX-133](EX-133-laya-v2t-v2tw-battle256.md)(Abyssal, 악화)과 [EX-135](EX-135-laya-head-to-head-v2tw-v4t.md)(직접 대결, 구별되지 않음)에 있다.
