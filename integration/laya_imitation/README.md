# laya 압축 입력 모방 학습·배틀 (EP-208 · EX-118 · EX-119 · EP-209 · EX-120)

EX-071 리플레이 모방 스냅샷을 1,024토큰 이하 텍스트로 압축해 laya 0.4.13(ModernBERT-large 판정 헤드)을 사람 선택으로 학습한다. 선택 모델은 EX-089 표준 32경기에서 Abyssal 상대로 평가한다.

- **조건 원문**:
  - 결정 [D-183](../../project_context/research/policy-learning/decisions/D-183-laya-compact-imitation.md)
  - 실행 [EP-208](../../project_context/research/policy-learning/plans/EP-208-laya-compact-imitation.md)
  - 학습 [EX-118](../../project_context/research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md)
  - 배틀 [EX-119](../../project_context/research/policy-learning/experiments/EX-119-laya-compact-imitation-battle32.md)
  - 환경 [EP-207](../../project_context/shared/execution/plans/EP-207-laya-0413-environment.md)
  - 렌더러 v2 [D-185](../../project_context/research/policy-learning/decisions/D-185-laya-modular-renderer-v2.md), [EP-210](../../project_context/research/policy-learning/plans/EP-210-laya-renderer-v2.md), [EX-121](../../project_context/research/policy-learning/experiments/EX-121-laya-v2-all-training.md), [EX-122](../../project_context/research/policy-learning/experiments/EX-122-laya-v1-v2-battle256.md)
  - 새 팀 일반화 [D-184](../../project_context/research/policy-learning/decisions/D-184-laya-team-generalization.md), [EP-209](../../project_context/research/policy-learning/plans/EP-209-laya-team-generalization.md), [EX-120](../../project_context/research/policy-learning/experiments/EX-120-laya-team-generalization128.md)
- 수치, 판정, 중단 조건은 위 원문이 소유한다. 이 문서는 실행 안내만 한다.

## 구성

| 파일 | 역할 |
|---|---|
| `compact.py` | `ImitationInput`(C-055 경계) → 압축 텍스트 상태와 choice 질문. 결정적 순수 함수다. 자료 생성, 서빙, 뷰어가 모두 이것을 쓴다. |
| `dex.py`, `dex_gen9.json` | 기술의 타입·분류·위력·우선도와 타입표. poke_env에서 한 번 내보내 고정했고, 두 인터프리터가 같은 바이트를 읽는다. |
| `data.py` | EX-071 `prepared/`(읽기 전용) → `datasets/generated/laya-compact-imitation/v1`. 원본 해시, EX-089 팀 겹침, 길이를 감사하고 봉인한다. |
| `training.py` | GPU0 잠금 → 사전검사(256행) → laya `train_model` 3 epoch → epoch별 validation → 선택 → 온도 보정 |
| `evaluation.py` | 잠긴 test를 initial과 selected에 각 1회 평가 → 한국어 보고 → 봉인 |
| `policy.py` | 평가와 서빙의 공통 점수 경로(fp32 logit → 체크포인트 온도 → 반올림 없는 확률) |
| `serving.py` | EX-071 `/health`·`/evaluate` 계약의 loopback 서버. 렌더러가 자료 생성 때와 같은지 확인한다. |
| `battle.py` | EX-089 일정 변환, 서빙 관리, 경기 원장. 경기 worker, player, 감사는 EX-071 것을 그대로 쓴다. |
| `teams.py` | EX-120 팀 선정 규칙(제외 서명, 합법성, 유형 분류, 다양성)과 원형 대진 128슬롯 일정 |
| `generalization.py` | EX-120 단계와 조합 클러스터 bootstrap·팀/유형/시드 집계, 동결 판정 |
| `compact_v2.py` | 모듈형 렌더러 v2. `render(value, modules, facts)`이며 modules ⊆ {damage, moves, speed, switch}. 모듈이 없으면 v1과 바이트 단위로 같다. |
| `features.py`, `calc.cjs` | 모듈 원 계산값(기술 변형, 속도, 교체, 피해량)과 고정 `@smogon/calc` 0.11.0 워커 |
| `dex_v2.py`, `dex_gen9_v2.json`, `assumed_sets_v2.json` | v2 정적 자료(종족 능력치, 기술 flags)와 상대 가정 세트(EX-071 corpus 종족별 최빈) |
| `data_v2.py`, `evaluation_v2.py`, `comparison.py` | v2 측정·캐시·자료·parity, EX-121 test와 v1 쌍비교, EX-122 같은 실행 v1·v2 배틀 |
| `effects_export.cjs`, `dex_gen9_effects.json` | EX-126 효과 원자료. 고정 Showdown `e64915c0e`에서 한 번 내보낸 기술·도구·특성 `shortDesc`·플래그와 합법 종족(타입·가능 특성) |
| `effect_rules.md`, `effect_rules.json`, `effects_oracle.cjs` | 효과 규칙표(엔진 판정 순서)와 엔진 오라클(시나리오 → 1:1 배틀 → works/fails/immune/absorbed/reflected, yes/no) |
| `effect_knowledge.py`, `evaluation_effects.py` | 효과 지식 행 A(엔진 대조)·B(실제 상태, 공개 정보)·C(설명)과 EX-126 평가(실패 선택지 확률 합, EX-124 쌍비교) |
| `viewer.py/.html/.js`, `browser_check.py` | UI v1 오프라인 뷰어(`laya-imitation-researcher-v1`)와 이동 후 브라우저 검사 |
| `resources.py` | GPU0과 포트 8107의 공용 flock, UUID와 유휴 확인 |

## 명령

`scripts/laya-imitation`이 인터프리터를 고른다. `battle`은 `pokechamp/.venv`, 나머지는 `.tools/laya-0.4.13/.../.venv`를 쓴다.

| 명령 | 하는 일 | 쓰는 위치 |
|---|---|---|
| `status` | 저장된 JSON만 읽는다. 쓰기와 추론은 하지 않는다. | 없음 |
| `data` | 압축 자료 v1을 생성하고 감사한다(CPU). 이미 있으면 실패한다. | `/mnt/.../datasets/generated/laya-compact-imitation/v1`, `exports/laya-compact-imitation-v1` |
| `train [--preflight-only]` | GPU0 사전검사 후 본학습과 선택을 한다. 재개는 없다. | `/mnt/.../runs/model-training/EX-118` |
| `evaluate` | 잠긴 test를 모델별 1회 평가한다. 예약 파일이 있으면 다시 하지 않는다. | `EX-118/evaluation`, `report.md`, 봉인 |
| `serve --checkpoint P --model laya-selected [--device cpu]` | loopback 서빙. 보통은 `battle`이 직접 띄운다. | 없음 |
| `battle mock` | 시작 체크포인트로 CPU 2경기를 한다. 성적 분모에 넣지 않는다. | `EX-119/mock` |
| `battle prepare` | EX-089 일정 복사와 봉인 확인, source·체크포인트·protocol 동결 | `EX-119/manifest.json` 등 |
| `battle execute` | 32슬롯을 순차 진행한다(GPU0 서빙, 포트 8107). 이미 시도한 슬롯은 다시 하지 않는다. | `EX-119/games`, `ledger.jsonl`, `result.json` |
| `battle export` | 보고, 뷰어, 봉인 | `EX-119/report.md`, `exports/battle_viewers/ex119/` |
| `general collect` | EX-120 새 팀 32개 선정(제외 서명, 합법성, 유형, 다양성)과 128슬롯 일정 생성·봉인(CPU) | `EX-120/collection/` |
| `general mock` | 새 일정 첫 쌍을 시작 체크포인트로 CPU 2경기. 분모 밖 | `EX-120/mock` |
| `general prepare` / `execute` / `export` | EX-119와 같은 체크포인트·배틀 경로로 128슬롯, 조합 클러스터 판정, 보고·뷰어·봉인 | `EX-120/`, `exports/battle_viewers/ex120/` |
| `v2 measure` | v2(4종) 렌더 길이·선택지 48토큰·계산기 실패를 validation 512로 측정(CPU) | `EX-121/diagnostics/measure/` |
| `v2 features` | EX-071 전 행의 v2 모듈 원 계산값 캐시(16 프로세스, node 계산기) | `datasets/generated/laya-compact-features/v2` |
| `v2 data` / `v2 parity` | 캐시에서 `v2-all` 자료 텍스트화·감사·봉인 / 저장 자료와 실시간 렌더 대조 | `laya-compact-imitation/v2-all` |
| `v2 train [--preflight-only]` / `v2 evaluate` | EX-118과 같은 설정으로 v2 학습(head 512) / 잠긴 test와 v1 쌍비교 | `runs/model-training/EX-121` |
| `compare mock` / `prepare` / `execute` / `export` | EX-120 일정 × {v1, v2} 256경기를 같은 실행 안에서(두 서빙 동시) | `runs/model-training/EX-122`, `exports/battle_viewers/ex122/` |
| `effects data` | 효과 지식 자료 생성, 엔진 대조(불일치 시 중단), 감사, 봉인(CPU, node). 이미 있으면 실패한다. | `datasets/generated/laya-effect-knowledge/v1` |
| `effects train [--preflight-only]` / `effects evaluate` | GPU2에서 v2-all + 테라 지식 + 효과 지식 학습 / 효과·테라 held-out, 잠긴 test, EX-124 쌍비교 | `runs/model-training/EX-126` |
| `compare3 mock` / `prepare` / `execute` / `export` | EX-120 일정 × {v2+테라, v2+테라+효과} 256경기(GPU2, 포트 8108), 실패·무효 기술 집계 | `runs/model-training/EX-127`, `exports/battle_viewers/ex127/` |
| `regression build` / `baseline` / `score --endpoint URL --out P` | NHJ-20261028 사람 대전 고정 결정 27개(`regression.py`)를 한 번 추출·라벨링 / 기록된 v1.1 기준 집계 / 실행 중인 서빙에 한 번씩 질의해 v1.1과 나란히 채점(보고 전용, 배틀 게이트 아님) | `tests/nhj20261028_regression.json`, `--out` |

## 규칙

- **자동 재실행 금지**: 실패하면 원인을 남기고 멈춘다. 다시 실행하려면 새 승인이 필요하다. 도구 결함은 `diagnostics/<단계>-vN/defect.json`에 원본과 함께 보존한다.
- **렌더러 고정**: `compact.py`, `dex.py`, `dex_gen9.json`을 바꾸면 서빙이 자료 생성기와 다르다며 시작을 거부한다. 렌더러를 바꾸려면 새 자료 판본(v2)과 새 EX가 필요하다.
- **자원**: GPU0(`GPU-4f27dd5a-…`)과 포트 8107만 쓴다. EP-213(EX-126/127)은 GPU2(`GPU-c79ce3fd-…`)와 포트 8108을 쓴다. EP-203은 GPU1~3을 쓴다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **해석**: 확률은 행동 선택 확률이며 승률이 아니다. QA나 모방 지표와 배틀 성적을 구분한다.

## 검사

```bash
cd /workspace
L=.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python
PYTHONPATH=/workspace:/workspace/pokechamp $L -m pytest -q integration/laya_imitation/tests/test_compact.py integration/laya_imitation/tests/test_serving.py
PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m pytest -q -p no:cacheprovider integration/laya_imitation/tests/
$L -m ruff check integration/laya_imitation --select=E9,F63,F7,F82,F401,F811,F841 --line-length=120
# 뷰어 이동·오프라인 검사 (Playwright 인터프리터)
PYTHONPATH=/workspace /tmp/ep037/tools/bin/python -m integration.laya_imitation.browser_check exports/battle_viewers/ex119 /tmp/ex119-browser.json
```
