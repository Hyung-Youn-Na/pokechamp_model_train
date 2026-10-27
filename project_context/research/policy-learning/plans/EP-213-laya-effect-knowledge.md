# EP-213 — laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2)

- 상태: Completed
- 생성일: 2026-10-23
- 책임자: Claude Code
- 승인 근거·범위: 현재 사용자 지시와 승인된 계획 / [D-188](../decisions/D-188-laya-effect-knowledge.md)
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-126](../experiments/EX-126-laya-v2-tera-effect-training.md), [EX-127](../experiments/EX-127-laya-v2t-v2te-battle256.md), [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md), [EP-212](EP-212-laya-tera-knowledge.md)
- 기준 연구선: `research/model-training`
- 실제 작업 branch, 시작 commit, 미커밋 변경: `research/model-training` `feda62f733c1b470364868262c789ec857ef67f5`. 기존 미커밋 변경은 보존한다.
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`, node(고정 Showdown `dist/sim`). 실행기는 `scripts/laya-imitation effects|compare3`다.
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-effect-knowledge/v1`
  - `.../runs/model-training/EX-126`, `.../runs/model-training/EX-127`
  - 뷰어 `/workspace/exports/battle_viewers/ex127/`
- 참조 원자료(읽기 전용):
  - `v2-all` 자료, EX-071 `prepared/`, 테라 지식 v1, EX-120 `collection/`·`games/`
  - EX-124 산출물, `pokemon-showdown` `e64915c0e`

## 목표와 맥락

기술·도구·특성 효과 지식 행을 v2+테라 학습에 더했을 때, 실패·무효 선택과 배틀 성적이 바뀌는지 측정한다. 조건과 판정은 EX-126과 EX-127이 소유한다.

## 범위와 불변 조건

- **포함**:
  - `effects_export.cjs`, `dex_gen9_effects.json`, `effects_oracle.cjs`, `effect_rules.md`, `effect_rules.json`
  - `effect_knowledge.py`, `evaluation_effects.py`
  - 학습 `Spec` 다중 지식 자료(`training.extras`), `comparison.EX127`·`failed_moves`, 보고 표, CLI, 테스트, 문서
  - `evaluation_tera.knowledge`의 자료·파트·파일명 인자화(EX-124 기본값 동작 유지)
- **보존**:
  - v1, v2 렌더러와 자료, 정보 캐시, 테라 지식 자료
  - EX-118~125 산출물, 봉인, 동작. EX-124 단일 지식 경로의 동결 파일명(`extra-train-manifest.json`)과 `train-config.json` 형식도 그대로 둔다.
  - 다른 작업의 자원(GPU0·8107, GPU1·8109)
- **자원**: GPU2와 포트 8108만 쓴다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **외부 호출**: 없다. 효과 근거는 로컬 고정 엔진뿐이다.

## 완료 기준

- [x] 효과 원자료 고정과 규칙표(엔진 근거, 판정 순서)
- [x] 엔진 오라클, 지식 생성기와 단위 검사, 자료 생성(엔진 대조 불일치 0), 감사, 봉인
- [x] EX-126 학습(GPU2), 선택, 효과·테라 held-out, 잠긴 test, EX-124 쌍비교, 보고, 봉인
- [x] EX-127 mock 후 256경기, 실패 기술·테라 지표, 보고, 봉인, 자원 반환
- [x] 뷰어(C-047), 상위 목록, 오프라인 검사, 변경일지 (리플레이 턴 이동 검사는 도구 부재로 미수행)
- [x] STATUS, catalog build/check (README·INDEX 변경 없음)

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 규칙 정확성 | A 행 전체 엔진 재현 대조, 규칙 예시 단위 검사 | `effect_rules.md` / `test_effect_knowledge` 7건, 자료 manifest `oracle` | 통과: 26,400건 불일치 0(첫 시도 20건 불일치는 원인 수정 후 재생성, `diagnostics/data-v1` 보존) |
| 공개 정보 원칙 | 미공개 특성·도구 열거, 표본 검사 | `test_unrevealed_ability_is_enumerated`, held-out B 표본 | 통과 |
| 기존 경로 회귀 | 기존 테스트, EX-124 Spec 동작 | `test_spec_extras`, 두 환경 테스트 | 통과: 43건(두 환경), ruff 통과 |

## 진행

- 2026-10-23 — 승인과 등록.
  - EX-120 128경기 재집계: laya 기술 4.8% 실패·무효, Aurora Veil 20/25 실패
  - 고정 엔진에서 효과 원자료(기술 685, 도구 223, 특성 310, 합법 종족 834)를 내보냈다.
- 2026-10-23 — 구현과 자료.
  - 엔진 오라클로 규칙 함수의 판정 순서를 맞췄다.
    - Protean 타입 변화, 면역 상태이상, Infiltrator
    - Future Sight의 사용 시점 판정, Encore 부여 시점
    - Safety Goggles·Sweet Veil 표기
  - 지식 자료를 만들었다: train 64,396(A 23,572, B 15,000, C 25,824), held-out 5,931, 초과 0. 봉인했다.
  - 테스트 43건이 통과했다.
- 2026-10-23 — EX-126 GPU2 사전검사 통과, 본학습 시작(학습 행 약 251,550).
- 2026-10-23 — EX-127 mock 1차가 도구 결함으로 경기 없이 끝났다(서빙 모델 이름 허용 목록에 `laya-v2te` 없음).
  - 기록은 `EX-127/diagnostics/mock-v1`에 보존했다.
  - 허용 목록과 검사(`test_every_compared_model_can_be_served`)를 더한 뒤 mock을 1회 다시 했다.
  - 재시도도 도구 결함으로 경기 전에 멈췄다. 공용 배틀 실행기는 포트 8100~8109만 받는데 EX-127이 8110을 지정했기 때문이다.
  - 기록은 `diagnostics/mock-v2`에 보존했다.
  - 포트를 비어 있는 8108로 바꿨다. 8108은 완료된 EP-172/176/181이 쓰고 반납한 포트이고, EP-181에도 같은 교정 선례가 있다.
  - 2026-10-23 사용자가 mock 3차 실행을 승인했다(현재 대화).
- 2026-10-23 — EX-127 mock 3차(포트 8108, CPU, 시작 체크포인트)에서 2경기가 정상 종료하고 감사를 통과했다(분모 밖). 실패 기술 집계 경로도 확인했다(36회 중 0회).

- 2026-10-25 — EX-126 평가 완료: "개선 없음"(실패 선택지 확률 +0.0011, 지식 held-out 96~99%). EX-127 prepare 후 256경기 실행 시작(GPU2, 8108).
- 2026-10-25 11:33Z — EX-127 256경기 종료(정상 256/256, 감사 전수 통과). 판정 "구별되지 않음"(v2te − v2t −0.070 [−0.148, +0.008]). 실행 세션은 export 전에 끝났다.
- 2026-10-26 — EP-216 작업 중 EX-127 export(보고·뷰어·봉인)와 뷰어 오프라인 검사를 했다. GPU2와 포트 8108은 사용 중인 프로세스가 없음을 확인하고 반환 처리했다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-126과 EX-127을 참조한다. 자동 재실행은 없다.

- EX-126 평가는 EX-124 완료·봉인 뒤에 한다(EX-124 test 예측 재사용).
- EX-127 prepare는 EX-124·EX-126 완료 뒤에 한다.

## 결과 및 증거

- EX-126: 효과 지식 held-out 96~99%, 실패 선택지 확률 개선 없음(+0.0011)
- EX-127: v2t 111-17, v2te 102-26, 차이 −0.070 [−0.148, +0.008] → 구별되지 않음. [보고](../experiments/EX-127-laya-v2t-v2te-battle256.md#결과) · [뷰어](../../../../exports/battle_viewers/ex127/index.html) · [뷰어 검사](../../../exec-plans/evidence/ep213/viewer-check.json)
