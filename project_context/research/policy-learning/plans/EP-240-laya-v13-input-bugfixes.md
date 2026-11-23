# EP-240 — laya 렌더러 v13 입력 결함 수정(폼 스펙·테라 방어·선공 Roost·Ivy Cudgel)과 검증

- 상태: Completed
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-23 대화: "실험으로 바로 들어가도록 하겠습니다. 일단 드러난 입력 버그를 수정하는 작업을 먼저 진행해주세요."), [D-218](../decisions/D-218-laya-v13-input-bugfixes.md). 새 래퍼 모듈 `integration/laya_v13/` 구현, 단위 검사, EX-203 실제 국면 재현·전수 토큰 회귀 검증 및 EX-200 무재학습 응답 대조 진단까지 수행한다. 자료 재생성·재학습·배틀 평가는 검증 보고 후 별도 EX로 등록한다.
- 관련 contract / decision / experiment: [D-218](../decisions/D-218-laya-v13-input-bugfixes.md), [D-191](../decisions/D-191-no-offline-battle-gate.md), [EP-237](EP-237-laya-observed-public-info-input.md), [EX-203](../experiments/EX-203-laya-engine-value-ladder.md), [EX-204](../experiments/EX-204-laya-engine-value-ladder-loss-analysis.md)
- 겹치는 등록 plan:
  - [EP-237](EP-237-laya-observed-public-info-input.md)(Active, v12 구현·평가 완료): `integration/laya_v12/`를 읽기·import만 하며 수정하지 않는다.
  - [EP-231](EP-231-laya-ladder-postmortem-v11.md)(Active)·[EP-234](EP-234-laya-fp1-foulplay-input.md)(Active)·[EP-229](EP-229-laya-opponent-model-search.md)(Active): 실행 중인 프로세스 및 파일 충돌 없음.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `ee13b70`(EP-234~239 미커밋 변경 존재; 건드리지 않음)
- 작업 checkout과 interpreter/launcher: `/workspace`, `exports/laya-play/env/laya/bin/python` (pytest·렌더 검증)
- 새 산출물: `integration/laya_v13/`(`__init__.py`, `render_v13.py`, `serve_v13.py`, `tests/test_v13.py`), 기록
- 참조 원자료(읽기 전용): `exports/laya-play/games/20261122-*`(EX-203 경기 기록), `integration/laya_v12/`

## 목표와 맥락

EX-203 고레이팅(1500+) 및 상위 봇 대국 감사에서 드러난 `v12` 입력·계산기 결함 4건(`formespec`, `teradefence`, `roostground`, `ivycudgel`)을 기존 패키지를 건드리지 않는 `laya_v13` 래퍼로 수정하고, 실제 EX-203 결정들에 대해 정확성·토큰 한도·기존 테스트 무퇴보를 검증한다(D-218).

## 범위와 불변 조건

- **포함**: `integration/laya_v13/`, `project_context/research/policy-learning/{decisions/D-218*,plans/EP-240*}`, `project_context/catalog/`, `STATUS.md`.
- **보존**: `laya_imitation`·`laya_threat`·`laya_v10`·`laya_v11`·`laya_v12`·`laya_foe`·`laya_value`·`exports/laya-play/` 파일과 기존 자료·실행 산출물·봉인은 바이트 단위로 유지한다.
- **외부 호출**: 없다. GPU 학습·배틀 실행은 이 계획 범위에 포함하지 않는다.
- **비실험 작업**: 복구·재수집·실험 시계·배틀 viewer는 해당 없음(오프라인 입력 수정·회귀 검증).

## 완료 기준

- [x] D-218·EP-240 등록 및 `scripts/context-catalog build`/`check` 통과
- [x] `integration/laya_v13/render_v13.py` 구현(4건 결함 수정, 멱등 `install()`, 판본 메타데이터) 및 `serve_v13.py` 추가
- [x] 단위 검사 `integration/laya_v13/tests/test_v13.py` 작성 및 통과(10/10), 기존 `laya_v11`(9/9)·`laya_v12`(21/21) 단위 검사 통과
- [x] EX-203 핵심 오판 턴 4건(`2718021055` T4, `2717998063` T16, `2717995159` T11, `2717939960` T26) 재현 검증 및 1500+ 35판(1,880결정) 전수 회귀·토큰 한도(상태 ≤ 2,048, head ≤ 768, 선택지 ≤ 64) 통과
- [x] EX-200 체크포인트로 수정된 입력의 무재학습 행동 변화 진단 기록(보고 전용, D-191)
- [x] 결과를 EP-240·STATUS·catalog에 갱신하고 보고

## 진행

- 2026-11-23 — D-218·EP-240 등록(`catalog/records.json` build/check 662 records 통과).
- 2026-11-23 — `integration/laya_v13/{render_v13,serve_v13}.py` 및 `tests/test_v13.py` 구현 완료. 기존 `laya_imitation`·`laya_threat`·`laya_v10`·`laya_v11`·`laya_v12`·`exports/laya-play`는 바이트 단위 보존.
- 2026-11-23 — 단위·회귀 검사 통과: `test_v11.py` 9/9, `test_v12.py` 21/21, `test_v13.py` 10/10.
- 2026-11-23 — EX-203 1500+ 35판 전수 1,880결정 `v12` vs `v13` 회귀·토큰 예산 검사 및 EX-200 무재학습 응답 대조 완료.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 차단 사유 없음.

## 결과 및 증거

1. **핵심 오판 턴 재현 검증 (`tests/test_v13.py`)**:
   - `gen9ou-2718021055` T4 (Corviknight vs Tera-Water Ogerpon): `opp threat: worst ivycudgel` 31–37% → **45–54%**, `duel` 4 hits `even` → **3 hits `lose`**, Cinderace 교체 `worst x1` → **`worst x2`**, `sets.candidates` `embodyaspectwellspring` 매핑으로 0건 → 정상 복구.
   - `gen9ou-2717998063` T16 (Dondozo Tera Dark vs Tera-Water Ogerpon): `move:rest:tera`의 `tera takes hornleech 17-20%` → **`tera takes ivycudgel 43-51%`**로 교정.
   - `gen9ou-2717995159` T11 (Corviknight 선공 Roost vs Ting-Lu): `move:roost:normal`에 **`; grounded takes earthquake 43-51%`** 추가, `duel` `even` → **`lose`**로 교정.
   - `gen9ou-2718014378` T22 (Slowking-Galar Tera Grass vs Kyurem): `tera takes earthpower` 대신 테라 후 치명적 얼음 기술로 교정.
2. **EX-203 1500+ 35판 전수 회귀 및 토큰 예산 (1,880결정, 오류 0건)**:
   - 속도: `v12` 110.2 ms/결정 → `v13` 114.5 ms/결정 (+4.3 ms/결정).
   - 변화 건수: `state` 272건(14.5%; Ogerpon Tera 122건, `duel` 변화 80건), `criteria` 833건(44.3%; `tera takes` 변화 741건, 교체 변화 107건, `grounded takes` 추가 55건).
   - 토큰 예산(EX-200 tokenizer, `laya.common.build_head` 실측): `max_state=813`, `max_head=605/768`, `max_opt=55/64`, `max_total=1381/2048` (**한도 초과 0건**).
3. **EX-200 무재학습(Zero-Shot) 응답 대조 진단 (보고 전용, D-191)**:
   - `gen9ou-2717998063` T16: `v12` `move:rest:tera` 0.500(`swP=0.36`) → `v13` **`switch:4`(Corviknight) 0.459(`swP=0.74`)**로 재학습 없이도 자살 테라 즉각 회피.
   - `gen9ou-2717995159` T10·T11: `move:roost:normal` 0.792/0.803 → **0.719/0.718**(`bodypress`·`irondefense` 상승)로 소폭 반응했으나 argmax 유지 — 새 문구(`grounded takes`)를 모델이 학습한 적이 없어 정책 반영에는 후속 학습 또는 결정 보정이 필요함.
   - `gen9ou-2718021055` T4: `move:roost:tera`(0.106)는 사라졌으나 `move:roost:normal`은 0.591 → 0.661로 유지.
4. **후속**: 배틀 평가(무재학습 `v13` 대조 vs `v13` 자료 재렌더/이어 학습)는 별도 EX로 등록해 진행한다.
