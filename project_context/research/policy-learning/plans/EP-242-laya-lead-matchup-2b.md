# EP-242 — laya 2b 선봉 선택 모듈(`lead_policy.py`, 상대 선봉 추정 × 6×6 매치업 기대값 + 모델 사전확률 재가중) 구현

- 상태: Completed
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-23 대화, 오프라인 선봉 진단 보고 뒤 "그러면 일단 2b 선봉 선택 모듈을 구현해주세요."). 새 독립 모듈 `integration/laya_v13/lead_policy.py` 및 단위·회귀 검사 `integration/laya_v13/tests/test_lead_policy.py`를 구현하고 검증한다. 실행 중인 `EX-205`의 동결 파일(`render_v13.py`, `serve_v13.py`, `battle_v13.py`)과 기존 패키지는 수정하지 않는다. 배틀·래더 적용 실험은 별도 EX로 등록한다.
- 관련 contract / decision / experiment: [D-218](../decisions/D-218-laya-v13-input-bugfixes.md), [EP-240](EP-240-laya-v13-input-bugfixes.md), [EP-241](EP-241-laya-v13-zeroshot-vs-foulplay.md), [EX-203](../experiments/EX-203-laya-engine-value-ladder.md), [EX-204](../experiments/EX-204-laya-engine-value-ladder-loss-analysis.md)
- 겹치는 등록 plan:
  - [EP-241](EP-241-laya-v13-zeroshot-vs-foulplay.md)(Active, `EX-205` 실행 중): `render_v13.py`·`serve_v13.py`·`battle_v13.py`는 건드리지 않고 새 파일 `lead_policy.py`만 추가하므로 해시·실행 충돌이 없다.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `ee13b70`
- 작업 checkout과 interpreter/launcher: `/workspace`, `pokechamp/.venv/bin/pytest` · `exports/laya-play/env/laya/bin/python`
- 새 산출물: `integration/laya_v13/lead_policy.py`, `integration/laya_v13/tests/test_lead_policy.py`, 기록
- 참조 원자료(읽기 전용): `exports/laya-play/games/20261122-*`(EX-203 104판 선봉 기록), `integration/laya_v10/strategy.py`, `integration/laya_v13/render_v13.py`

## 목표와 맥락

EX-203 104판 오프라인 진단에서 현재 `argmax` 선봉은 `Raging Bolt`에 93.3%(상위 봇 16/16) 고정되어 1500+ 사람 구간에서 불리 선봉률 42.1%·최악 손실(MinMax) −0.534를 보였다. 단순 무작위 샘플링이나 순수 6×6 내쉬는 유리한 선봉까지 버려 기대값이 떨어졌고, **상대 선봉 휴리스틱($q_{\text{heur}}$) × 6×6 매치업 기대값으로 모델 확률을 재가중하고 `min_p` 필터로 샘플링하는 `2b` 방식**이 전체 기대값(+0.382 → +0.381)을 유지하면서 1500+ 사람 기대값(+0.157 → +0.190)·불리율(42.1% → 33.5%)·최악 손실(−0.534 → −0.317)을 동시에 개선했다.

이 `2b` 로직을 재사용 가능하고 테스트된 독립 모듈(`lead_policy.py`)로 구현한다.

## 범위와 불변 조건

- **포함**: `integration/laya_v13/lead_policy.py`, `integration/laya_v13/tests/test_lead_policy.py`, 기록(EP-242, STATUS, catalog).
- **보존**: `integration/laya_v13/{render_v13,serve_v13,battle_v13}.py`(EX-205 동결 파일) 및 모든 기존 패키지·`exports/laya-play/` 파일은 바이트 단위로 유지한다.
- **비실험 작업**: 외부 호출·GPU 학습·배틀 실행·뷰어는 해당 없음.

## 완료 기준

- [x] EP-242 등록 및 `scripts/context-catalog build`/`check` 통과
- [x] `integration/laya_v13/lead_policy.py` 구현(순수 표준 라이브러리, `cell_score`, `opp_lead_prior`, `reweight_lead`, `choose_lead`, `Lead2bSampler`, 서빙 래퍼 `with_lead_2b`)
- [x] 단위·회귀 검사 `integration/laya_v13/tests/test_lead_policy.py` 작성 및 통과(9/9, EX-203 1500+ 사람 19판 회귀 포함)
- [x] 기존 `test_v13.py`(10/10) 무퇴보 확인 및 EX-205 동결 파일(`render_v13.py`, `serve_v13.py`, `battle_v13.py`) 해시 무변경 확인
- [x] 결과를 EP-242·STATUS·catalog에 기록하고 보고

## 진행

- 2026-11-23 — 사용자 지시로 등록 및 `integration/laya_v13/lead_policy.py`·`tests/test_lead_policy.py` 구현 완료.
- 2026-11-23 — `test_lead_policy.py` 9/9, `test_v13.py` 10/10 통과, EX-205 동결 `laya_v13` 3개 파일 sha256 일치 확인, `context-catalog build/check` 통과.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 차단 사유 없음.

## 결과 및 증거

- [lead_policy.py](../../../../integration/laya_v13/lead_policy.py)(`laya-lead-2b-v1`, 순수 Python 표준 라이브러리):
  - `cell_score`, `opp_lead_prior`, `min_p_filter`, `reweight_lead`, `Lead2bSampler`, `choose_lead`, `with_lead_2b`(서빙 `/evaluate`의 `probabilities`·`choice`를 바꾸지 않고 `turn 0 | lead`에만 `lead_2b` 권고 필드를 덧붙이는 비침습 래퍼).
- 검증: `test_lead_policy.py` **9/9 통과**(`test_ex203_1500_human_aggregate_regression` 19판에서 `2b` 평균 상성 점수가 `argmax` 초과 확인), `test_v13.py` **10/10 통과**, 실행 중인 `EX-205` 동결 파일 sha256 전부 일치.
- 후속: `EX-205` 완료 후 래더/배틀 적용 여부와 결합 평가를 별도 EX로 정한다.
