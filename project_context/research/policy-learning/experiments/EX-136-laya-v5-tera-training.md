# EX-136 — laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0)

- 상태: Planned
- 생성일: 2026-10-27
- 책임자: Claude Code
- 관련 exec plan: [EP-218](../plans/EP-218-laya-renderer-v5-item-state.md)
- 관련 decision: [D-195](../decisions/D-195-laya-item-state-renderer-v5.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-130](EX-130-laya-v4-tera-training.md) selected(v4 + 테라, 변수 하나 차이), [EX-124](EX-124-laya-v2-tera-knowledge-training.md) selected(v2 + 테라, 현재 배틀 최고)
- 기준 연구선: `research/model-training`

## 질문 및 목적

상대 아이템의 미공개·들고 있음·제거를 구분하고 상태 카운터를 표시한 입력(v5)이 사람 선택 재현을 어떻게 바꾸는가? 특히 풍선이 공개된 상대에게 지면 기술을 고르는 확률이 줄어드는가? 배틀 효과는 [EX-137](EX-137-laya-v4t-v5t-battle256.md)과 [EX-138](EX-138-laya-head-to-head-v5t.md)이 본다.

## 가설 또는 qualification 목표

- **qualification**:
  - EX-071 재파싱에서 새 선택 필드 이외 스냅샷 필드가 전 행 같다.
  - v5 자료의 길이 초과 제외가 0.5% 이하다.
  - validation 512에서 오프라인 렌더와 서빙 렌더가 같다(`v5 parity`).
  - 사전검사 loss가 줄고, 저장 후 재로딩 logit이 같다.
- **판정 없음(보고 전용)**: D-191에 따라 이 실험의 결과는 EX-137·138 실행 여부를 정하지 않는다.
- **보고 지표**: 잠긴 test 1,024행에서 EX-136 − EX-130, EX-136 − EX-124 같은 행 차이를 낸다. 구간은 replay 클러스터 bootstrap 95%(10,000회, 시드 20261032)다.
  - 전체 NLL과 일치율, 교체 행 NLL
  - **아이템 상태별 차이**:
    - 상대 활성 아이템이 제거된 행(원인별 knockoff/popped/consumed)
    - 미공개이면서 가정 세트가 Air Balloon인 행
    - 풍선이 공개(들고 있음)되고 지면 기술 선택지가 있는 행: 지면 기술 확률 합 평균과 1위 횟수
  - **카운터 상태별 차이**: 내·상대 활성 잠듦(Rest 여부), 맹독, 날씨·필드·벽이 있는 행. 잠든 내 활성 행의 Sleep Talk 확률과 사람 선택
  - 실패로 정해진 선택지의 확률 합(`evaluation_effects.fail_metrics`), 사람 테라 행의 테라 확률 합, 테라 지식 held-out A/B 정답률
  - **사람 대전 국면 재추론**(고정 129결정, `/workspace/data/NHJ-20261027`):
    - 풍선 Gholdengo 상대 지면 기술 1위 횟수(기준 v2t 9, v4t 0)
    - Ice Spinner·Unaware Clefable 교체 확률
    - 23번 T13 Earth Power의 렌더 피해
    - 국면 비교만 하며 승패를 말하지 않는다.
- EX-130·EX-124 쪽 값은 저장된 test 예측을 쓴다. 다시 추론하지 않는다.
  - 단, 아이템 상태별 분류는 v5 자료의 `item_state`로 같은 행에 붙인다.
  - 사람 대전 국면은 세 모델을 새로 추론한다(v2t·v4t는 2026-10-27 재추론 값과 같아야 함).

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 예상 artifact 위치 |
|---|---|---|---|
| EX-136 selected | EX-130과 같다: 시작 모델 `e929ae5c`, 설정, EX-071 분할, 테라 지식 train 57,143행(바이트 동일), head 512, v4 모듈 전부 | 렌더러 v4 → v5(`items`, `counters` 모듈 추가) | `runs/model-training/EX-136/checkpoints/selected/` |

### 렌더러 v5 (`compact_v5.py`, `features_v5.py`)

D-195 결정 2를 따른다. 요약하면 다음과 같다.

- 상대 아이템 표시
  - 미공개: `item ?`
  - 들고 있음: `item <id>`
  - 제거됨: `item none (knocked off <id>)` / `item none (popped)` / `item none (used <id>)`
- 피해 계산
  - 제거된 아이템은 없음으로 계산한다.
  - 미공개는 가정 세트의 아이템을 쓰되 Air Balloon만 제외하고, 그 경우 지면 기술에 `balloon?`을 붙인다.
- 공개된 Air Balloon·Levitate 대상에게 지면 기술 배율은 `x0`이다.
- 상태 카운터(`counters`)
  - 잠듦은 `slp t<n>`(Rest면 `slp t<n> rest`), 맹독은 `tox t<n>`으로 표시한다.
  - 날씨·필드·벽에는 지난 턴 수를 붙인다.
- 두 모듈이 없으면 v4와 바이트 단위로 같다. 표시 형식은 validation 512 길이 실측 뒤 동결한다.

### 자료 (`item_state.py`, `data_v5.py`)

- `laya-item-state/v1`: EX-071 원본 리플레이를 수정한 파서로 다시 파싱한 `sample_id`별 새 선택 필드(상대 6슬롯 `item_state`, 12슬롯 `status_counter`·`status_source`, `weather_turn`), 전수 비교 결과(`parity.json`), 제거·카운터 행 집계
- 정보 캐시 `laya-compact-features/v5`(v4 사실 + `items`·`counters` 블록)와 학습 자료 `laya-compact-imitation/v5-all`(한도 1,024 / 512 / 48, 초과 행은 `exclusions.jsonl`)
- 학습 시 테라 지식 train 행을 더한다. 보정 400행은 모방 행에서만 뗀다.

### 학습 설정

- EX-130과 같다: 3 epoch, soft-CE, 선택지 순서 섞기, lr, seed 0, `max_len=1024`, `head_max_len=512`
- 선택은 validation 원 NLL 최소 epoch다.
- 상한은 최초 GPU 시계부터 14시간이다.
- EX-130은 GPU1에서 학습했고, 이번은 GPU0(같은 기종 RTX A6000)이다.

## 환경 및 출처

- branch: `research/model-training`. 소스 identity는 run `source/`에 둔다.
- 장치: GPU0(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, `gpu0.lock`, UUID와 유휴 확인)
- 실행기: `scripts/laya-imitation v5 {reparse,measure,features,data,parity,train,evaluate,probe}`, 연결 실행 `scripts/laya-imitation-ep218`
- 출력: `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-136`

## 격리 및 오염 통제

- 새 선택 필드는 공개 protocol(`-item`, `-enditem`, `-status`, `cant`, `-damage … psn`, `-weather`)만 쓴다. 사람 라벨, 승패, test를 보지 않는다.
- 잠긴 test(`v5-all` test)는 학습과 선택에 쓰지 않는다.
- 사람 대전 4경기는 학습·선택에 쓰지 않는다. 보고용 국면 재추론에만 쓴다.
- **viewer**: 비배틀이므로 해당 없다.
- **재개**: 지원하지 않는다. 자동 재실행은 없다.

## 절차

1. 파서 새 선택 필드 구현과 단위 검사, EX-071 재파싱(CPU), 전수 비교, 봉인
2. v5 사전 측정, 형식 동결, 정보 캐시(CPU 16 프로세스), `v5-all` 자료, 제외 비율, 봉인
3. `v5 parity`(validation 512)
4. GPU0 사전검사 → 본학습 → 선택과 보정
5. 테라 지식 held-out(EX-136 selected 1회)
6. 잠긴 test(1회) → EX-130·EX-124 쌍비교 → 사람 대전 국면 재추론 → 보고, 봉인

## 승인·무효화·중단 조건

- **승인**: 1~6 완료와 봉인
- **무효**: 재파싱 필드 불일치, parity 불일치, 자료 해시 불일치, 재로딩 불일치
- **중단**: 제외 비율 > 0.005, 14시간 상한, GPU 오류

## 테스트·평가 도구 결함 복구

C-018과 EX-118 절차를 적용한다. 원본을 `diagnostics/<단계>-vN`에 보존하고, 수정과 독립 검증 뒤 해당 단계만 1회 재시도한다.

## 증거

| Artifact | Path | Checksum | 상태 |
|---|---|---|---|
| 아이템 상태 | `/mnt/.../datasets/generated/laya-item-state/v1` | `checksums.sha256` | 예정 |
| v5 정보 캐시 | `/mnt/.../datasets/generated/laya-compact-features/v5` | `checksums.sha256` | 예정 |
| v5 자료 | `/mnt/.../datasets/generated/laya-compact-imitation/v5-all` | `checksums.sha256` | 예정 |
| 학습 run | `/mnt/.../runs/model-training/EX-136` | `checksums.sha256`, `report.md` | 예정 |

## 결과

진행 전.

## 분석 및 한계

- 미공개 아이템은 여전히 가정 세트에 기댄다(Air Balloon만 제외).
- 제거 원인은 protocol 표기에 기댄다. 표기가 없는 경우는 `other`로 둔다.
- 두 모듈을 함께 바꾸므로 배틀 차이를 한쪽 효과로 나누지 않는다.
- 단일 시드 학습이다.

## 결론 및 후속 작업

진행 전.
