# EX-118 — laya 압축 입력 리플레이 모방 학습

- 상태: Completed
- 생성일: 2026-10-22
- 책임자: Claude Code
- 관련 exec plan: [EP-208](../plans/EP-208-laya-compact-imitation.md), 환경 [EP-207](../../../shared/execution/plans/EP-207-laya-0413-environment.md)
- 관련 decision: [D-183](../decisions/D-183-laya-compact-imitation.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

EX-071 스냅샷을 1,024토큰 이하 텍스트로 압축해 laya(ModernBERT-large 판정 헤드)를 학습했을 때, 같은 잠긴 test에서 사람 선택을 얼마나 재현하는가? 이 실험은 배틀 평가(EX-119)에 쓸 모델을 정한다.

## 가설 또는 qualification 목표

탐색적 실험이다.
- **qualification**: 압축 자료의 전체 행이 1,024토큰 이하이고 EX-089 팀과 겹침이 0이다. 학습 후 선택 모델의 test NLL이 초기 체크포인트보다 낮다.
- EX-071 Qwen 선택 모델(NLL 1.7168, 일치율 31.25%)과의 비교는 같은 test 표본의 참고 비교다. 모델, 입력, 학습량이 모두 다르므로 전체 구성 차이로 해석한다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| initial | 압축 자료 v1, test 1,024 | `laya-typed-decisions@e929ae5c` 원본(학습 없음) | `runs/model-training/EX-118/evaluation/test-initial.jsonl` |
| selected | 같은 자료와 test | 아래 설정으로 학습하고 validation으로 선택한 epoch | `runs/model-training/EX-118/checkpoints/selected/` |

- **자료**: EX-071 `prepared/{train 130,411, validation 512, test 1,024}`를 `integration/laya_imitation/compact.py` v1로 변환한다. 분할과 표본은 바꾸지 않는다.
- **학습 설정**: laya 0.4.13 `train_model`을 쓴다. 학습 전에 동결한다.
  - `max_len=1024`, `head_max_len=384`(EX-071 표본 실측: 질문·선택지 최대 318토큰, 전체 최대 795토큰), `loss="soft-ce"`, `shuffle_options=("choice",)`
  - `epochs=3`, `micro_batch=8`, `grad_accum=8`
  - `encoder_lr=2.5e-5`, `head_lr=1e-4`, cosine 감쇠, `min_lr=1e-6`, `weight_decay=0.01`, `grad_clip=1.0`
  - `seed=0`, AMP bf16, gradient checkpointing
- **보정**: train에서 laya `split_calibration`(최대 400행, 시드 20260922)으로 뗀 행에 `fit_temperature_map`을 적용한다. 이 행은 학습에서 빠진다.
- **선택**: epoch마다 checkpoint를 저장하고 validation 512의 NLL(보정 전 원 logits)로 최솟값 epoch를 고른다. 동률이면 앞 epoch를 고른다.
- **test**: 잠긴 test 1,024를 initial과 selected에 각 1회 평가한다. test 결과로 설정이나 epoch를 바꾸지 않는다.
- **지표**:
  - NLL(보정 전, 보정 후)
  - 행동 일치율(argmax)
  - 결정 종류, 라벨 종류, Tera 사용별 분모와 지표(EX-071과 같은 분류)
  - ECE
  - 행당 추론 지연
- **분모**: 전체 표본. 1,024를 넘어 제외된 행은 별도 분모로 보고한다(목표 0).
- **중단 규칙**: 최초 GPU 시계부터 12시간 상한. 넘으면 그 시점의 기록을 보존하고 Stopped로 처리한다.
- **실행 순서**: 고정 시드. train 순서는 laya `Random(seed+epoch)`이다.

## 환경 및 출처

- 실제 branch, commit, 미커밋 변경: `research/model-training` `feda62f7…`. 새 파일과 미커밋 변경 목록은 실행 시 `source/`에 보존한다.
- checkout, interpreter, 실행기: `/workspace`, `.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python`, `scripts/laya-imitation`
- 지원 출력 인자: `--output`. 기본값 `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-118`. 단계별로 쓰는 위치는 README를 따른다.
- 자료: `/mnt/.../datasets/generated/laya-compact-imitation/v1`. 원본 SHA는 EX-071 `prepared/manifest.json`이며 변환 manifest에 연결한다.
- 모델: `convaiinnovations/laya-typed-decisions` `e929ae5cf69bc34259cd2f95c9e91145b818b1f0`. 파일 SHA는 EP-207 증거에 둔다.
- 장치: 물리 GPU0(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, RTX A6000). 다른 GPU는 쓰지 않는다.

## 격리 및 오염 통제

- **태그와 출력**: 태그 `ex118`, 출력은 위 run 디렉터리다. 원자료(EX-071, EX-089)는 읽기만 한다.
- **입력 경계**: C-055 `ImitationInput`이 금지 필드를 차단한다. 렌더러는 스냅샷 밖의 정보를 쓰지 않는다. 라벨, 승패, 이름, metadata는 모델 입력에 들어가지 않는다.
- **오염**: EX-089 네 팀의 서명이 EX-071 세 분할에 없음을 등록 시 확인했고, 자료 생성 시 다시 검증한다. test는 학습과 선택에 쓰지 않는다.
- **viewer**: 비배틀 실험이므로 해당 없다.
- **재개**: 지원하지 않는다. 실패하면 원인을 보존하고 새 승인 없이 재실행하지 않는다.
- **과거 자료**: EX-071 결과는 비교 참고로만 쓴다.

## 절차

1. 자료 v1 생성과 감사(CPU). 길이, 겹침, 1:1 대응을 확인한다.
2. GPU0 잠금, UUID, 유휴 확인 후 사전검사를 한다. 256행 짧은 학습에서 loss가 줄어드는지, 저장 후 재로딩한 예측이 일치하는지 본다.
3. 본학습 3 epoch와 epoch별 validation을 수행한다.
4. epoch를 선택하고 보정한 뒤 selected를 저장한다.
5. test를 initial과 selected에 각 1회 평가한다.
6. 한국어 보고, 봉인(`checksums.sha256`), GPU0 반환.

## 승인·무효화·중단 조건

- **승인**: 1~6 완료와 봉인.
- **무효**: 입력 경계 위반, 자료 해시 불일치, 재로딩 예측 불일치.
- **중단**: 12시간 상한, GPU 오류, 외부 점유. 장치 reset과 외부 프로세스 종료는 금지한다.

## 테스트·평가 도구 결함 복구

- 공통 절차와 C-018을 적용한다.
- 재수집(재학습)은 0회다. 평가 도구에 결함이 있으면 저장된 checkpoint로 재평가를 1회까지 허용한다. 원 결과는 보존하고 별도 판본으로 연결한다.
- 결함 기록 위치: run `diagnostics/`

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 자료 v1 | `/mnt/.../datasets/generated/laya-compact-imitation/v1` | `checksums.sha256` | Sealed |
| 학습 run | `/mnt/.../runs/model-training/EX-118` | `checksums.sha256` (sha256 `86dab78c…`) | Sealed |
| 한국어 보고 | `/mnt/.../runs/model-training/EX-118/report.md` | sha256 `7bc6f08c…` | Produced |

## 결과

- **실행**: 2026-10-22, GPU0. 최초 시계부터 선택 저장까지 5.51시간(12시간 상한 이내). 결함 복구는 사전검사 v1 1건(`diagnostics/preflight-v1`, 판정 무관 도구 결함)이다.
- **validation 512 (원 logit)**:

| epoch | train loss | NLL | 일치율 |
|---:|---:|---:|---:|
| 0 | - | 2.1315 | 15.04% |
| 1 | 1.6441 | 1.6276 | 39.26% |
| 2 | 1.4674 | **1.5445** | **44.14%** |
| 3 | 1.3023 | 1.6140 | 41.60% |

- **선택**: 사전 규칙(validation 원 logit NLL 최소)에 따라 epoch 2. 보정 온도 `[0.9665, 1.0, 1.0]`(보정 400행).
- **잠긴 test 1,024 (모델별 1회)**:

| 모델 | NLL(보정) | 일치율 | ECE |
|---|---:|---:|---:|
| initial | 2.1311 | 20.12% | 0.0485 |
| selected | **1.4716** | **46.78%** | 0.0534 |
| 참고: EX-071 Qwen 4B selected | 1.7168 | 31.25% | - |

- 결정 종류별(selected): turn_action 831행 45.97%, forced_switch 116행 50.00%, pivot_switch 46행 56.52%, lead 31행 41.94%. 라벨 종류별로 move 628행 53.98%, voluntary_switch 203행 21.18%(NLL 2.2000).
- 단일 행 추론 지연(GPU0, fp32): 중앙값 40.7 ms, p95 50.3 ms.
- **qualification**: 충족. 길이 초과 0, EX-089 팀 겹침 0, 선택 test NLL < 초기 test NLL.

## 분석 및 한계

- 라벨은 사람 선택의 모방이며 승률이나 q가 아니다.
- 상대 미공개 정보와 자신의 세트 보완 한계는 EX-071과 같다.

## 결론 및 후속 작업

- 압축 입력 laya(ModernBERT-large)는 같은 test 표본에서 EX-071 Qwen 4B보다 낮은 NLL과 높은 일치율을 보였다. 모델, 입력, 학습량이 모두 다른 전체 구성 차이이며 원인을 분리하지 않았다.
- epoch 3에서 validation NLL이 다시 올라 과적합 징후가 있다.
- 자발 교체(voluntary_switch)는 일치율 21%로 가장 약하다.
- 렌더러 한계: 날씨에 따른 Weather Ball 타입·위력 변화 등 기술 변형을 반영하지 않는다(v1 동결).
- 후속: [EX-119](EX-119-laya-compact-imitation-battle32.md)에서 선택 체크포인트의 EX-089 32경기 배틀을 평가한다.
