# EX-121 — laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교

- 상태: Completed
- 생성일: 2026-10-22
- 책임자: Claude Code
- 관련 exec plan: [EP-210](../plans/EP-210-laya-renderer-v2.md)
- 관련 decision: [D-185](../decisions/D-185-laya-modular-renderer-v2.md)
- 비교 대상: [EX-118](EX-118-laya-compact-imitation-training.md) selected(v1)
- 기준 연구선: `research/model-training`

## 질문 및 목적

v1 압축 입력에 기술 변형, 속도 비교, 교체 판단, 피해량 추정을 더한 v2 입력으로 같은 시작 모델과 같은 설정으로 학습하면, 잠긴 test에서 사람 선택 재현이 v1보다 나아지는가? 특히 자발 교체에서 나아지는가?

## 가설 또는 qualification 목표

- **qualification**:
  - 길이 제외율이 0.5% 이하다.
  - `features=∅` 렌더가 v1과 같다.
  - parity가 일치한다.
  - 선택 모델의 test NLL이 v2 initial보다 낮다.
- **판정**(실행 전 동결): 잠긴 test 1,024행에서 행별 NLL(보정 후) 차이 `v2 selected − v1 selected`의 리플레이(group) 클러스터 bootstrap 95% 구간(10,000회, 시드 20261024)으로 판정한다.
  - 상한 < 0 → "v2가 사람 선택 재현을 개선"
  - 하한 > 0 → "v2가 악화"
  - 그 외 → "구별되지 않음"
  - 일치율 차이, 라벨 종류별 차이(특히 voluntary_switch)도 같은 방식으로 구간을 보고한다. 이들은 판정에 쓰지 않는다.
- v1 쪽 값은 EX-118의 저장된 test 예측(`evaluation/test-selected.jsonl`)을 쓴다. 다시 추론하지 않는다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| v2 initial | `v2-all` 자료, test 1,024 | `laya-typed-decisions@e929ae5c` 원본 | `EX-121/evaluation/test-initial.jsonl` |
| v2 selected | EX-118과 같은 시작 모델, 설정, 분할, 시드 | 렌더러 v2(4종), `head_max_len` 실측값 | `EX-121/checkpoints/selected/` |

### 렌더러 v2 (`integration/laya_imitation/compact_v2.py`, 판본 `laya-compact-v2[damage,moves,speed,switch]`)

- **moves**: 후보 기술의 실효 타입, 위력, STAB를 고정 목록 규칙으로 고치고 바뀐 경우 원래 값을 표시한다.
  - Weather Ball, Terrain Pulse
  - Pixilate, Aerilate, Refrigerate, Galvanize(×1.2), Normalize, Liquid Voice
  - Adaptability, Tera Blast, Technician, Facade, Hex, Acrobatics, Knock Off
- **speed**:
  - 내 실효 속도는 정확값이다.
  - 상대는 기본 능력치로 범위(0EV·하락 성격 ~ 252EV·상승 성격)를 구하고 가정 세트 추정값을 함께 적는다.
  - 랭크, 마비, Tailwind, Choice Scarf(내 도구 또는 공개된 상대 도구), Trick Room을 반영한다.
  - 상태 줄과 교체 후보에 표시한다.
- **switch**: 교체 후보마다 다음을 적는다.
  - 상대 활성이 공개한 공격 기술 중 최대 배율과 그 기술
  - 등장 시 해저드 피해 %(Stealth Rock, Spikes, Toxic Spikes, Sticky Web, Boots·비행·Levitate 예외)
- **damage**: `@smogon/calc` 0.11.0과 엔진 패치를 쓴다.
  - 기술 후보: 내 활성 → 상대 활성의 피해 % 범위와 KO 표시(OHKO/2HKO)
  - 교체 후보: 상대 활성의 공개 기술 → 그 후보의 최대 피해 % 범위
  - 상대 세트는 EX-071 corpus 종족별 최빈 세트로 가정한다. 공개된 도구, 특성, 테라, 기술은 관측을 우선한다.
  - 계산 실패는 `dmg ?`로 표시하고 집계한다.
- **길이**:
  - 선택지당 48토큰을 넘거나 전체 1,024를 넘는 행은 제외하고 분모에 남긴다.
  - `head_max_len`은 CPU 사전측정 후 아래 칸에 동결한다.
  - 제외율이 0.5%를 넘으면 학습 전에 중지한다.
  - **사전측정 기록**(validation 512, CPU, 2026-10-22):
    - 1차 문안: 선택지 48토큰 초과 행 153/512, 전체 최대 1,009였다. 학습 전에 축약 규칙을 바꿨다.
      - 피해 %와 해저드 %를 정수로 반올림했다.
      - 교체 후보에서 기술 이름을 뺐다(`worst x배율`, `hit a-b%`).
      - 속도 순서를 `faster`, `slower`, `faster?`, `slower?`, `tie?`로 줄였다.
      - 기술 변형 사유만 괄호로 표시했다.
    - 2차 문안: 전체 p50 672, p95 810, 최대 930. 질문·선택지 최대 453. 선택지 최대 45. 초과 0, 계산기 실패 0이다(`EX-121/diagnostics/measure/`).
  - **동결값**: `head_max_len=512`(실측 최대 453 + 여유), 선택지 48, 전체 1,024

### 학습 설정 (EX-118과 같음)

- `max_len=1024`, `loss="soft-ce"`, `shuffle_options=("choice",)`
- `epochs=3`, `micro_batch=8`, `grad_accum=8`
- `encoder_lr=2.5e-5`, `head_lr=1e-4`, `min_lr=1e-6`, `weight_decay=0.01`, `grad_clip=1.0`
- `seed=0`, 보정 400행(시드 20260922)
- **선택**: validation 원 logit NLL 최소, 동률이면 앞 epoch
- **test**: initial과 selected를 각 1회 평가한다. test 결과로 아무것도 바꾸지 않는다.
- **상한**: 최초 GPU 시계부터 12시간

## 환경 및 출처

- branch, commit: `research/model-training` `feda62f7…`. 소스 identity는 run `source/`에 둔다.
- interpreter: laya venv(`.tools/laya-0.4.13/worktrees/pokemon-training/.venv`)와 node(계산기)
- 실행기: `scripts/laya-imitation v2 {measure,features,data,train,evaluate}`
- 자료:
  - 정보 캐시 `/mnt/.../datasets/generated/laya-compact-features/v2`
  - 자료 `/mnt/.../datasets/generated/laya-compact-imitation/v2-all`
  - 원본은 EX-071 `prepared/`(SHA 확인)와 `preparation/corpus.jsonl`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-121`
- 장치: GPU0(`GPU-4f27dd5a-…`). 잠금, UUID, 유휴 확인을 거친다.

## 격리 및 오염 통제

- **입력 경계**: C-055 `ImitationInput`을 거친 스냅샷만 쓴다. 상대 미공개 정보는 가정 세트에서 오며 출처 표시가 붙는다. 실제 상대 세트는 쓰지 않는다.
- **분할**: EX-071의 분할과 고정 표본을 그대로 쓴다. test는 학습과 선택에 쓰지 않는다.
- **corpus 사용**: corpus는 EX-071 학습 측 지식이다. test 리플레이 팀의 세트가 corpus에 포함되었을 수 있다는 한계는 결과에 명시한다.
- **viewer**: 비배틀이므로 해당 없다.
- **재개**: 지원하지 않는다. 자동 재실행은 없다.

## 절차

1. 단위 검사, 계산기 대조
2. CPU 사전측정: validation 512의 길이, 제외, 계산기 실패 → `head_max_len` 동결
3. 정보 캐시와 `v2-all` 자료 생성, 감사, 봉인, parity
4. GPU0 사전검사(256행, 재로딩 일치) → 본학습 3 epoch → 선택과 보정
5. test(initial, selected 각 1회) → v1 쌍비교 → 한국어 보고 → 봉인 → GPU0 반환

## 승인·무효화·중단 조건

- **승인**: 절차 1~5 완료와 봉인
- **무효**: 입력 경계 위반, 자료 해시 불일치, parity 불일치, 재로딩 불일치
- **중단**: 12시간 상한, 제외율 0.5% 초과, GPU 오류

## 테스트·평가 도구 결함 복구

C-018과 EX-118 절차를 적용한다. 도구 결함은 원본을 `diagnostics/<단계>-vN`에 보존하고, 수정과 독립 검증 뒤 해당 단계만 1회 재시도한다. 판정 기준은 바꾸지 않는다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 정보 캐시 | `/mnt/.../datasets/generated/laya-compact-features/v2` | `checksums.sha256` | Sealed |
| 자료 v2-all | `/mnt/.../datasets/generated/laya-compact-imitation/v2-all` | `checksums.sha256` | Sealed |
| 학습 run | `/mnt/.../runs/model-training/EX-121` | `checksums.sha256` (sha256 `e287a881…`), `report.md` (`8926aa05…`) | Sealed |

## 결과

- **실행**:
  - 2026-10-22 23:50 ~ 2026-10-23 06:20 UTC, GPU0, 6.49시간
  - 선택 epoch 2, 보정 온도 `[0.9836, 1.0, 1.0]`
  - 결함 복구 없음
  - 운영 지연: 자료 완성 뒤 감시 명령 오류로 학습 시작이 약 10시간 늦었다(EP-210 기록)
- **validation 512 (원 logit)**:

| epoch | NLL | 일치율 | 참고: v1 같은 epoch |
|---:|---:|---:|---|
| 1 | 1.5712 | 39.65% | 1.6276 / 39.26% |
| 2 | **1.4819** | 44.34% | 1.5445 / 44.14% |
| 3 | 1.5092 | 45.12% | 1.6140 / 41.60% |

- **잠긴 test 1,024**:

| 모델 | NLL | 일치율 | ECE |
|---|---:|---:|---:|
| v1 selected (EX-118) | 1.4716 | 46.78% | 0.0534 |
| v2 initial | 2.0893 | 21.19% | 0.0535 |
| v2 selected | **1.4435** | 46.39% | **0.0267** |

- **판정**(동결): 행별 NLL 차이(v2 − v1) 리플레이 클러스터 95% [-0.0593, +0.0025] → **"구별되지 않음"**. 평균 차이 -0.0281, 일치율 차이 -0.39%p [-2.80, +2.00].
- **라벨 종류별**(판정 외):

| 라벨 | NLL 차이 [95%] | 일치율 차이 [95%] |
|---|---|---|
| forced_switch | -0.123 [-0.175, -0.072] | |
| voluntary_switch | -0.085 [-0.161, -0.010] | +1.5%p [-3.7, +6.7] |
| move | +0.000 | |
| pivot_switch | +0.032 | **-19.6%p [-32.7, -6.2]** |

- **테라**(판정 외): 테라 가능 test 546행에서 테라 1순위는 v1 5행, v2 8행이다. 사람 테라 20행에 준 테라 확률 합 평균은 v1 0.155, v2 0.175다.
- **qualification**: 충족. 제외율 0, `features=∅`가 v1과 같음, parity 512/512, 선택 test NLL < initial.

## 분석 및 한계

- 네 모듈을 함께 넣었으므로 개별 기여는 분리하지 않는다. 조합 실험은 별도로 한다.
- 상대 세트 가정은 최빈 세트 하나에 의존한다.
- 라벨은 사람 선택 모방이며 승률이 아니다.

## 결론 및 후속 작업

- v2(4종 정보)는 전체 NLL을 0.028 낮췄고 확률 보정(ECE 0.053 → 0.027)도 좋아졌다. 다만 95% 상한이 0을 조금 넘어 동결 판정은 "구별되지 않음"이다.
- 교체 판단(강제·자발 교체 NLL)은 개선 구간이 0 아래다.
- pivot_switch 일치율은 46행 표본에서 크게 낮아졌다.
- 배틀 효과는 [EX-122](EX-122-laya-v1-v2-battle256.md)에서 본다.
