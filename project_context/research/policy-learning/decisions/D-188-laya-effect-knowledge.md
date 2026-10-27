# D-188 — laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2)

- 상태: Accepted
- 날짜: 2026-10-23

## 맥락

- 사용자가 학습 중인 모델의 배틀을 리뷰하다가, 모델이 기술의 실패 조건과 특수 효과를 잘 모른다고 판단했다.
  - 대표 사례: [EX-120](../experiments/EX-120-laya-team-generalization128.md)에서 나인테일(알로라)이 눈이 아닌 날씨에서 오로라 베일을 써서 계속 실패했다.
- EX-120 128경기를 다시 세어 보면 laya(v1, EX-118 selected) 쪽 상황은 다음과 같다.
  - 기술 3,895회 중 187회(4.8%)는 바로 뒤에 `-fail`/`-immune`이 나왔다.
  - 오로라 베일은 25회 중 20회 실패했다.
  - 실패·무효가 많았던 기술: Seismic Toss 38, Thunder Wave 34, Earthquake 25, Protect 9, Mirror Coat 9
- 현재 학습 자료(v2 모방 행, [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md) 테라 지식 행)에는 효과 지식이 없다. 렌더러 v1/v2도 효과 문구를 쓰지 않는다(`compact.py` 원칙).
- **사용자 지시**:
  - GPU2로 아이템·기술·특성 특수 효과 지식을 학습시킨다.
  - 구성은 v2 + 테라 + 효과 지식이다.
  - 범위는 효과 설명 전체(실패 조건 포함)이다.
  - 평가는 배틀 256경기까지 한다.

## 결정

1. 효과의 근거는 고정 Showdown 엔진(`e64915c0e`)이다. 효과 텍스트·플래그·합법 종족을 `dex_gen9_effects.json`으로 한 번 내보내 고정한다. 웹 텍스트는 쓰지 않는다.
2. 실패·무효·흡수·반사·선택 불가 규칙을 엔진 판정 순서대로 규칙표(`effect_rules.md`/`.json`)와 규칙 함수로 만든다.
3. 지식 행은 세 가지다. 전략 판단 라벨은 넣지 않는다.
   - **A 개념 카드**: 합성 상황이다. 모든 행을 고정 엔진에서 실제 1:1 배틀로 재현해 규칙 함수의 정답과 같은지 확인한다. 하나라도 다르면 생성을 멈춘다.
   - **B 실제 상태**: EX-071 상태에서 공개 정보만으로 결과가 정해지는 기술만 쓴다. 미공개 특성은 가능한 특성을 모두 넣어 본다.
   - **C 설명**: 기술·도구·특성의 엔진 `shortDesc`를 정방향(무엇을 하나)과 역방향(무엇이 이 효과인가)으로 묻는다.
4. v2-all 모방 행 + EX-124 테라 지식 행 + 효과 지식 행으로 학습한다([EX-126](../experiments/EX-126-laya-v2-tera-effect-training.md)).
   - 시작 모델과 설정은 EX-121/EX-124와 같다.
   - 장치는 GPU2다.
5. EX-120 일정에서 v2+테라(EX-124)와 v2+테라+효과(EX-126)를 256경기로 비교하고, 실패·무효 기술 비율을 함께 보고한다([EX-127](../experiments/EX-127-laya-v2t-v2te-battle256.md)).
6. 실행은 [EP-213](../plans/EP-213-laya-effect-knowledge.md)이 소유한다.

## 거절한 대안

- **실패·무효 중심으로만 범위 축소**: 계획 단계에서 권장했으나 사용자가 효과 설명 전체를 택했다. 실패 조건은 A·B에 그대로 포함된다.
- **렌더러에 효과 문구나 실패 표시 추가**: 렌더러가 바뀌면 EX-121/124와의 비교가 섞인다. 별도 실험 후보로 남긴다.
- **규칙만으로 정답 생성(엔진 검증 없음)**: 엔진과 어긋난 정답을 가르칠 위험이 있다. 개발 중 엔진 대조가 실제로 20여 종의 순서·예외 오류를 잡았다(`diagnostics/data-v1`).
- **EX-124 체크포인트에서 이어 학습**: EX-124와 비교할 때 차이가 효과 지식만이 되도록, 같은 시작점에서 처음부터 학습한다.

## 근거와 한계

- EX-124 대비 차이는 효과 지식 행 추가이며, 학습 행 수도 함께 늘어난다.
- 지식은 "무엇이 일어나는가"이고 "언제 써야 하는가"가 아니다. 지식을 알아도 1순위 선택이 바뀌지 않을 수 있다.
- 기록이 필요한 실패 조건(Fake Out 첫 턴, Encore, Future Sight 중복)은 카드의 이력 줄로만 가르친다. 실제 상태 행(B)에는 없다.

## 영향

- `integration/laya_imitation/`에 다음을 추가한다.
  - `effects_export.cjs`, `dex_gen9_effects.json`, `effects_oracle.cjs`, `effect_rules.*`
  - `effect_knowledge.py`, `evaluation_effects.py`
  - 학습 `Spec`의 다중 지식 자료, `comparison.EX127`, 실패 기술 집계
- 기존 EX-118~125 동작은 유지한다.
- GPU2(`GPU-c79ce3fd-…`)와 포트 8108을 쓴다. GPU0(EX-121)과 GPU1(EX-124)과 분리된다.

## 증거

- 현재 대화의 사용자 지시와 승인된 계획
- EX-120 `games/*/events.jsonl` protocol 재집계(모델 쪽 `|move|` 다음 줄 `-fail`/`-immune`)
- Showdown `e64915c0e` `sim/battle-actions.ts`(`hitStep*` 순서), `sim/pokemon.ts`(`setStatus`, `isGrounded`), `data/moves.ts`, `data/abilities.ts`, `data/items.ts`, `data/conditions.ts`
