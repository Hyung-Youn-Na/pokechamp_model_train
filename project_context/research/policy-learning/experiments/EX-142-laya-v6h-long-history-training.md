# EX-142 — laya 렌더러 v6h(긴 과거 기록, 2048토큰) + 테라 지식 학습(GPU1)

- 상태: Completed
- 생성일: 2026-10-29
- 책임자: Claude Code
- 관련 exec plan: [EP-221](../plans/EP-221-laya-past-turn-input-v6.md)
- 관련 decision: [D-198](../decisions/D-198-laya-past-turn-input-v6.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-136](EX-136-laya-v5-tera-training.md) selected(v5 + 테라)
- 기준 연구선: `research/model-training`

## 질문 및 목적

입력 한도를 2,048로 늘리고, 직전 1턴뿐이던 기록을 한도 안에 들어가는 만큼(4턴보다 이전 포함) 넣은 입력(v6h)이 사람 선택 재현과 같은 기술 반복을 어떻게 바꾸는가? 배틀 효과는 [EX-144](EX-144-laya-v5t-v6ht-battle256.md)가 본다.

## 가설 또는 qualification 목표

- **qualification**:
  - `laya-early-history/v1` 재파싱에서 기존 스냅샷 필드가 전 행 같다(완료: 131,947/131,947).
  - `v6h-all` 길이 초과 제외가 0.5% 이하다.
  - validation 512에서 오프라인 렌더와 서빙 렌더가 같다(`v6 parity --variant v6h`, 길이 맞춤 포함).
  - 사전검사 loss가 줄고, 저장 후 재로딩 logit이 같다.
- **판정 없음(보고 전용)**: D-191에 따라 이 결과는 EX-144 실행 여부를 정하지 않는다.
- **보고 지표**: 잠긴 test 1,024행에서 EX-142 − EX-136 같은 행 차이. 구간은 replay 클러스터 bootstrap 95%(10,000회, 시드 20261036)다.
  - 전체 NLL과 일치율, 교체 행
  - v6h 기록 턴 수별(`0-2`, `3-8`, `9-20`, `21+`). `0-2`는 v5와 같은 텍스트라 한도 변경만의 효과다.
  - 내 활성 반복 표시별(v6s 자료 기준 분류)과 **같은 기술 반복 확률**(EX-141과 같은 정의)
  - 테라 지식 held-out A/B 정답률, 사람 테라 행의 테라 확률 합
  - 학습 시간, 최대 메모리, 결정당 지연

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-142 selected | EX-136과 같다: 시작 모델 `e929ae5c`, 설정, EX-071 분할, 테라 지식 train 57,143행, head 512, v5 모듈 전부, 사실값(`laya-compact-features/v5`) | 렌더러 v5 → v6h(`longhist` 모듈), `max_len` 1,024 → 2,048, 입력에 `early_history` | `runs/model-training/EX-142/checkpoints/selected/` |

### 파서 선택 필드 `early_history`

- `replay.Timeline(..., early_history=True)`일 때만 스냅샷에 T−4보다 앞선 공개 기록 이벤트를 `history`와 같은 형식으로 넣는다.
- 스키마는 이 필드를 받고, 4턴 창과 겹치는 이벤트를 거부한다. 요청하지 않은 입력은 바이트 단위로 같다.
- 학습 자료: `laya-early-history/v1`(EX-071 원본 리플레이 재파싱, 2,344 리플레이, 198초). 학습 행 130,411개 중 113,571행에 이전 기록이 있다(최대 361턴).
- 실전: 배틀 워커가 `laya-v6ht`(와 `-initial`) 쪽만 bridge에 `early_history: true`를 보낸다.

### 렌더러 v6h (`compact_v6.py` `longhist`, `data_v6.fitter`)

- v5 텍스트에서 `T<n>:` 기록 줄을 `early_history + history`로 다시 만든다. T−1·T는 항상 넣는다.
- 그보다 오래된 턴은 최근 쪽부터 넣고, 전체(질문·선택지 포함)가 2,048을 넘지 않는 가장 많은 턴 수를 이분 탐색으로 정한다. 길이는 학습과 같은 토크나이저·계산(`measure_row`)으로 잰다.
- 사전 측정(validation 512): 전체 p50 1,220 / p95 2,024 / 최대 2,047, 기록 턴 p50 15 / p95 36 / 최대 51.

### 학습 설정

- EX-136과 같다: 3 epoch, soft-CE, 선택지 순서 섞기, lr, seed 0, `head_max_len=512`, micro batch 8 × 누적 8. `max_len=2048`만 다르다.
- 선택은 validation 원 NLL 최소 epoch다.
- **시간 상한 없음**(사용자 지시 2026-10-29). 입력이 평균 약 1.8배 길어 EX-136(약 9.4시간)보다 오래 걸린다.

## 환경 및 출처

- 장치: GPU1(`GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`, `gpu1.lock`, UUID와 유휴 확인)
- 실행기: `scripts/laya-imitation v6 {reparse,measure,data,parity,train,evaluate} --variant v6h`, 연결 실행 `scripts/laya-imitation-ep221`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-142`

## 격리 및 오염 통제

- `early_history`는 공개 protocol 기록만 쓴다(`history`와 같은 정규화, 닉네임·플레이어 이름 제거). 사람 라벨, 승패, test를 보지 않는다.
- 잠긴 test는 학습과 선택에 쓰지 않는다.
- **viewer**: 비배틀이므로 해당 없다.
- **재개**: 지원하지 않는다. 자동 재실행은 없다.

## 절차

1. 파서 필드 구현·검사, EX-071 재파싱, 전수 비교, 봉인(완료)
2. 사전 측정과 형식 동결, `v6h-all` 자료, 제외 비율, 봉인
3. `v6 parity --variant v6h`(validation 512)
4. GPU1 사전검사 → 본학습 → 선택과 보정
5. 테라 지식 held-out(1회), 잠긴 test(1회) → EX-136 쌍비교 → 보고, 봉인

## 승인·무효화·중단 조건

- **승인**: 1~5 완료와 봉인
- **무효**: 재파싱 필드 불일치, parity 불일치, 자료 해시 불일치, 재로딩 불일치
- **중단**: 제외 비율 > 0.005, GPU 오류(메모리 부족 포함)

## 테스트·평가 도구 결함 복구

C-018과 EX-118 절차를 적용한다. 원본을 `diagnostics/<단계>-vN`에 보존하고, 수정과 독립 검증 뒤 해당 단계만 1회 재시도한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 이전 기록 | `/mnt/.../datasets/generated/laya-early-history/v1` | `checksums.sha256`, `parity.json` | 완료 |
| v6h 자료 | `/mnt/.../datasets/generated/laya-compact-imitation/v6h-all` | `checksums.sha256` | 예정 |
| 학습 run | `/mnt/.../runs/model-training/EX-142` | `checksums.sha256`, `report.md` | 예정 |

## 결과

- 학습: 3 epoch 95,024초(26.4시간, GPU1, 시간 상한 없음). epoch당 약 8.8시간으로 EX-136의 약 2.8배. 최대 메모리 21.3GiB.
  - validation 원 NLL 1.5680 → 1.5179 → **1.5032**(일치율 42.0% → 45.1% → 46.5%). EX-136·EX-141과 달리 3 epoch까지 계속 낮아져 선택 epoch 3이다.
- 잠긴 test(1,023행): NLL 1.4186(EX-136 1.4358, EX-141 1.4286), 일치율 46.82%(46.14%), ECE 0.0416(0.0403).
  - 같은 행 차이 EX-142 − EX-136: NLL −0.0173 [−0.0443, +0.0096], 일치율 +0.68%p. 전체 구간은 0을 포함한다.
  - **교체 행(365) NLL −0.0683 [−0.1185, −0.0186]**, 그중 자발 교체(203) −0.1124 [−0.1954, −0.0322]로 구간이 0 아래다.
  - 기록 턴 수별 NLL 차이: 0-2턴 −0.057, 3-8턴 +0.005, 9-20턴 −0.015, 21턴 이상 −0.021(모두 구간이 0 포함).
- **같은 기술 반복 확률**(EX-141과 같은 93행): 사람이 다른 수를 고른 58행 0.288 → 0.311(1위 18 → 23), 또 쓴 35행 0.670 → 0.631(1위 29 → 27). 반복을 줄이지 않았다.
- 단일 결정 지연(test, GPU1): p50 0.089초, p95 0.181초.
- 보고: `runs/model-training/EX-142/report.md`

## 분석 및 한계

- 한도(1,024→2,048)와 기록 창을 함께 바꿨다. 기록 턴 수별 분해로 일부를 나눈다.
- 긴 경기에서는 2,048을 채우는 지점에서 오래된 턴이 빠진다.
- 기반 체크포인트가 1,024까지 학습됐으므로, 그보다 뒤 위치의 학습은 이 실험이 처음이다.
- 단일 시드 학습이다.

## 결론 및 후속 작업

- 사람 선택 재현은 세 모델 중 NLL이 가장 낮지만 전체로는 EX-136과 구별되지 않는다. 교체 결정에서는 구간이 0 아래로 나아졌다.
- 긴 기록도 같은 기술 반복 확률은 줄이지 않았다.
- validation이 3 epoch까지 낮아졌으므로 epoch를 늘리면 더 나아질 여지가 있다(이번 범위 밖).
- 배틀은 [EX-144](EX-144-laya-v5t-v6ht-battle256.md).
