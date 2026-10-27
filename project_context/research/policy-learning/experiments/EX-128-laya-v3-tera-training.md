# EX-128 — laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0)

- 상태: Completed
- 생성일: 2026-10-25
- 책임자: Claude Code
- 관련 exec plan: [EP-214](../plans/EP-214-laya-renderer-v3.md)
- 관련 decision: [D-189](../decisions/D-189-laya-renderer-v3-opponent-sets.md)
- 비교 대상: [EX-124](EX-124-laya-v2-tera-knowledge-training.md) selected(v2 + 테라 지식)
- 기준 연구선: `research/model-training`

## 질문 및 목적

행동 행의 입력을 v2에서 v3(상대 세트 추론: 유력 도구·특성·테라·기술, 먼저 행동할 확률, 미공개 유력 기술의 피해)로 바꾸면, 사람의 교체 판단 재현이 나아지고 전체 재현은 유지되는가?

## 가설 또는 qualification 목표

- **qualification**:
  - v3 자료의 길이 초과 제외가 0.5% 이하다.
  - 오프라인 자료와 서빙 렌더가 validation 512행에서 같다(`v3 parity`).
  - 사전검사 loss가 줄고 저장 후 재로딩 logit이 같다.
- **판정**(실행 전 동결, 잠긴 test 1,024, 같은 행 차이 EX-128 selected − EX-124 selected, replay 클러스터 bootstrap 95%, 10,000회, 시드 20261027):
  - **주 지표 S**: 사람 라벨이 교체(voluntary_switch, forced_switch, pivot_switch)인 행의 NLL 차이. 95% 상한 < 0이면 "교체 판단 개선"이다.
  - **비열등 N**: 전체 행 NLL 차이의 95% 상한 ≤ +0.02(EX-124/126과 같은 여유)
  - **판정 문구**: S와 N 순서로 "교체 판단 개선 / 교체 차이 불분명" + ", 전체 비열등 / , 전체 저하"
  - **EX-129 진행 조건**: S 개선 또는 N 충족. 이 조건은 사용자 지시에 따라 사람 승인 대신 쓴다.
- **보조 지표**(판정 외):
  - 라벨 종류별, 결정 종류별 차이
  - 상대 활성 포켓몬의 공개 기술 수 버킷(0–1 / 2–3 / 4 / 상대 없음)별 차이
  - 사람 테라 test 행의 테라 확률 합(EX-124 대비)
  - 테라 지식 held-out A/B 정답률(EX-124 대비 퇴보 확인)
- EX-124 쪽 값은 EX-124의 저장된 test 예측과 지식 평가 결과를 쓴다. 다시 추론하지 않는다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-128 selected | EX-124와 같은 시작 모델 `e929ae5c`, 설정, EX-071 분할(train, validation, test 그대로), 테라 지식 train 57,143행(바이트 동일), head 512 | 행동 행 렌더러 v2 → v3 | `runs/model-training/EX-128/checkpoints/selected/` |

### 렌더러 v3 (`compact_v3.py`, `features_v3.py`)

- **근거 자료**: `usage_sets_v3.json`
  - Smogon chaos gen9ou 2026-08, 1695를 처리한 파일을 고정했다. 291종이고, 1e-4 미만 항목과 0.001 미만 spread는 뺐다.
  - 원본 sha256은 `a929e77c…`, 고정본 sha256은 `b9fd19d1…`이다.
  - 종족 별칭: `mimikyubusted` → `mimikyu`, `ogerpon*tera` → 테라 이전 형태
  - 사용률 행이 없는 종족은 `opp set: no usage data`로 표시한다.
- **세트 추론**(`infer_set`)
  - 공개된 도구, 특성, 테라 타입은 확률 1로 둔다.
  - 테라했거나 상대 테라가 이미 쓰였으면 테라 후보를 비운다.
  - 기술: 미공개 기술의 포함 확률을 남은 칸(4 − 공개 수)에 맞춰 비율 조정하고 1에서 자른다(독립 가정). 상위 8개만 둔다.
- **`oppset`**: OPP 줄 다음에 `opp set:` 한 줄을 넣는다.
  - 확정되지 않은 도구, 특성, 테라 중 0.15 이상인 상위 2개를 보인다.
  - 유력 기술은 0.15 이상인 상위 4개를 보인다.
- **`speedp`**: 속도 줄에 `| first p.NN`을 붙인다.
  - 0.001 이상 spread, Scarf 확률(공개 도구면 확정), 0.01 이상 특성으로 상대 실속을 계산한다(v2 `_speed_mods`).
  - 내 실속보다 느리면 1, 같으면 0.5를 준다. 트릭룸이면 반전한다.
- **`threat`**: 포함 확률 0.3 이상인 미공개 공격기를 위협으로 본다. 공격 측은 최빈 spread와, 공개되지 않았으면 최빈 도구·특성을 쓴다.
  - `opp threat: <기술> p.NN hit a-b%`: 내 활성 포켓몬에게 최대 피해인 기술이다. 피해 0(무효)은 뺀다.
  - 교체 선택지: v2 `hit`(공개 기술 최대)보다 위협 피해가 크면 그 값으로 바꾸고 `?`를 붙인다. 선택지 48토큰 한도 때문이다.
- **길이**(사전 측정, validation 512): 초과 0, 전체 p50 741 / 최대 984, head 최대 453, 선택지 최대 46. v2는 전체 최대 930, 선택지 최대 45였다.

### 자료 (`data_v3.py`)

- 정보 캐시 `laya-compact-features/v3`: 행마다 `features_v3.compute` 값(v2 사실 + `v3` 블록)을 저장한다.
- 학습 자료 `laya-compact-imitation/v3-all`: v3 일곱 모듈 전부, 한도 1,024 / 512 / 48. 초과 행은 `exclusions.jsonl`에 남긴다.
- 학습 시 `v3-all` train에 테라 지식 train 행을 더한다(`training.EX128.extra_train`).
  - 보정 400행은 모방 행에서만 뗀다(EX-124와 같은 시드와 방식).
  - validation과 선택은 `v3-all` validation 512다.

### 학습 설정

- EX-124와 같다: 3 epoch, soft-CE, 선택지 순서 섞기, lr, seed 0, `max_len=1024`, `head_max_len=512`
- 상한은 최초 GPU 시계부터 14시간이다.

## 환경 및 출처

- branch, commit: `research/model-training` `feda62f7…`. 소스 identity는 run `source/`에 둔다.
- 장치: GPU0(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, `gpu0.lock`, UUID와 유휴 확인)
- 실행기: `scripts/laya-imitation v3 {measure,features,data,parity,train,evaluate}`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-128`

## 격리 및 오염 통제

- usage 자료는 래더 집계 marginal이다. 우리 리플레이에서 만들지 않았고 정확한 세트가 없다.
- EX-071 팀 파일 corpus는 v3 상대 세트에 쓰지 않는다. v2 모듈의 기존 사용은 그대로다.
- 잠긴 test(`v3-all` test)는 학습과 선택에 쓰지 않는다.
- **viewer**: 비배틀이므로 해당 없다.
- **재개**: 지원하지 않는다. 자동 재실행은 없다.

## 절차

1. v3 정보 캐시 생성(CPU 16 프로세스), 봉인
2. `v3-all` 자료 생성, 제외 비율 확인, 봉인
3. `v3 parity`(validation 512)
4. GPU0 사전검사 → 본학습 → 선택과 보정
5. 테라 지식 held-out 평가(EX-128 selected 1회)
6. 잠긴 test(EX-128 selected 1회) → EX-124 쌍비교 → 판정과 EX-129 진행 조건
7. 보고, 봉인, GPU0 반환

## 승인·무효화·중단 조건

- **승인**: 1~7 완료와 봉인
- **무효**: parity 불일치, 자료 해시 불일치, 재로딩 불일치
- **중단**: 제외 비율 > 0.005, 14시간 상한, GPU 오류

## 테스트·평가 도구 결함 복구

C-018과 EX-118 절차를 적용한다. 원본을 `diagnostics/<단계>-vN`에 보존하고, 수정과 독립 검증 뒤 해당 단계만 1회 재시도한다. 판정 기준은 바꾸지 않는다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| usage 고정본 | `integration/laya_imitation/usage_sets_v3.json` | sha256 `b9fd19d1…` | 고정 |
| v3 정보 캐시 | `/mnt/.../datasets/generated/laya-compact-features/v3` | `checksums.sha256` | 봉인 |
| v3 자료 | `/mnt/.../datasets/generated/laya-compact-imitation/v3-all` | `checksums.sha256` | 봉인 |
| 학습 run | `/mnt/.../runs/model-training/EX-128` | `checksums.sha256`, `report.md` | 봉인 |

## 결과

2026-10-25 완료(학습 10:20Z–20:15Z, 평가 20:19Z). qualification은 모두 통과했다: 제외 3행(2.27e-5), parity 512/512 일치, 사전검사 loss 2.153 → 1.996, 재로딩 차이 0.0. 선택 epoch 2(validation NLL 1.4851).

| 모델 | 잠긴 test NLL | 일치율 | ECE |
|---|---:|---:|---:|
| EX-124 v2+테라 | 1.4506 | 47.85% | 0.0365 |
| EX-128 v3+테라 | 1.4391 | 48.05% | 0.0471 |

| 같은 행 차이(EX-128 − EX-124) | n | NLL 차이 | 95% | 일치율 차이 |
|---|---:|---:|---|---:|
| **S 교체 행** | 365 | −0.0341 | [−0.0854, +0.0162] | +1.92%p |
| **N 전체** | 1024 | −0.0115 | [−0.0431, +0.0200] | +0.20%p |
| forced_switch | 116 | −0.0443 | [−0.0943, +0.0056] | +4.31%p |
| pivot_switch | 46 | −0.1077 | [−0.2182, +0.0017] | +6.52%p |
| voluntary_switch | 203 | −0.0117 | [−0.0960, +0.0715] | −0.49%p |
| move | 628 | −0.0020 | [−0.0401, +0.0344] | −0.48%p |
| lead(상대 없음) | 31 | +0.0612 | [−0.0166, +0.1462] | −6.45%p |
| 상대 공개 기술 0–1 | 470 | +0.0059 | [−0.0387, +0.0516] | −1.49%p |
| 상대 공개 기술 2–3 | 440 | −0.0322 | [−0.0785, +0.0138] | +3.41%p |
| 상대 공개 기술 4 | 83 | −0.0278 | [−0.1252, +0.0655] | −4.82%p |

- **판정**: "교체 차이 불분명, 전체 저하". N의 95% 상한은 +0.020034로 기준 +0.02를 0.000034 넘었다. 문구의 "저하"는 비열등 미확인이라는 뜻이며 저하가 관측된 것은 아니다.
- **EX-129 진행 조건**: 미충족(`battle_gate: false`). 연결 실행은 EX-129를 시작하지 않았다. 이후 사용자 결정으로 [D-190](../decisions/D-190-laya-ex129-gate-override.md)에 이탈을 기록하고 EX-129를 실행한다. 이 판정은 바꾸지 않는다.
- 테라 지식 held-out: A 96.9% → 95.8%(A3 91.0 → 85.0%), B 95.8% → 95.3%
- 사람 테라 test 20행의 테라 확률 합: 0.1762 → 0.1925

## 분석 및 한계

- 기술 포함 확률을 독립으로 다뤘다. 리플레이 시기(2023~2026)와 통계 시기(2026-08)의 메타가 다르다.
- 소모·제거된 도구는 "모름"과 구별되지 않는다.
- 테라 B 지식 행은 v2 상태 텍스트다.
- 단일 시드 학습이다.

## 결론 및 후속 작업

- v3는 모든 주요 점추정이 개선 방향이지만 사전 등록 기준으로는 교체 개선도 전체 비열등도 확인하지 못했다. 신호가 가장 큰 곳은 pivot·강제 교체다.
- ECE가 0.0365 → 0.0471로 나빠졌다.
- 후속: [EX-129](EX-129-laya-v2t-v3t-battle256.md)(D-190에 따른 이탈 실행). 추가 시드 학습은 미정이다.
