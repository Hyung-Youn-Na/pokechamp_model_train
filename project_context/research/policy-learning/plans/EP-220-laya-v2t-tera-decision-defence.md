# EP-220 — laya v2+테라 fix 입력 테라 합산 결정·테라 방어 문구 배틀(재학습 없음, GPU1)

- 상태: Active
- 생성일: 2026-10-27
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-10-27). 결정 규칙 실험(1안)에 입력은 EX-139 fix로, 테라 방어 문구 간이 시험(A안)을 같은 실험 조건으로 추가한다. 구현, mock, 배틀, export를 이어서 진행한다. 커밋은 하지 않는다. 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [D-197](../decisions/D-197-laya-v2t-tera-decision-defence.md), [EX-140](../experiments/EX-140-laya-v2t-tera-decision-defence384.md), [EX-139](../experiments/EX-139-laya-v2t-corrected-input-battle256.md), [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher:
  - checkout은 `/workspace`이고, interpreter는 laya venv(서빙·컨트롤러), `pokechamp/.venv`(배틀 worker), node(계산기)를 쓴다.
  - 실행기는 `scripts/laya-imitation compare9 {mock,prepare,execute,export}`다. 실행기 파일은 고치지 않았다.
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-140`
  - 뷰어 `/workspace/exports/battle_viewers/ex140/`
- 참조 원자료(읽기 전용): EX-124 selected 체크포인트, EX-139 `manifest.json`·`result.json`·경기, EX-125 결과, EX-120 `collection/`, v2·v5 자료의 `generator-source/`

## 목표와 맥락

v2t가 테라를 꺼리는 원인 분석(D-197 맥락)에 따라, 재학습 없이 결정 규칙(tp1·tp3)과 테라 방어 문구(tdef)를 바꿨을 때 테라 사용과 Abyssal 배틀 성적이 어떻게 달라지는지 측정한다. 조건과 판정은 EX-140이 소유한다.

## 범위와 불변 조건

- **포함**:
  - 새 파일: `tera_decision.py`(합산 결정, 모델별 k, 방어 문구 렌더 `v2fixtd`, identity), `tera_battle.py`(EX140 Study, EX-139 같은 슬롯 판정, 규칙 작동·재현, 테라 선택 성격, 단계 함수, 보고), `tests/test_tera_decision.py`
  - 덧붙이기:
    - `serving.py`: `MODELS` 4개, `_dataset`·`renderer_matches_dataset`·렌더러 표의 `v2fixtd` 분기, `v2fixtd` identity, tp 모델일 때만 `predict`를 감싸고 identity `decision` 추가(그 외 모델은 같은 `policy.predict`)
    - `comparison.RENDER` 4개
    - `config.py`: `RUN_COMPARE9`, `VIEWER_COMPARE9`
    - `cli.py`: `--render v2fixtd`, `compare9`, status
- **보존**:
  - 수정하지 않는 파일: `features.py`, `features_v4.py`, `features_v5.py`, `compact*.py`, `item_state.py`, `data_v5.py`, `replay.py`, `schema.py`, `player.py`, `input_variants.py`, `variant_battle.py`, `scripts/laya-imitation`
  - `comparison.py`의 EX137과 `headtohead.py`의 EX138은 그대로다. 기존 서빙 경로와 identity는 같다.
  - EX-124·EX-125·EX-139 산출물과 봉인은 읽기만 한다.
- **자원**: GPU1·포트 8109만 쓴다. GPU0·GPU2(EP-218), GPU3(외부 프로세스)와 다른 포트는 건드리지 않는다. 프로세스 종료나 장치 reset을 하지 않는다.
- **동시 실행 제약**(EP-218이 같은 checkout에서 실행 중):
  - EX-137·EX-138 prepare가 `integration/laya_imitation/` 전체 해시를 동결한다. 그래서 코드 작업은 EX-136 stage가 `training`인 동안에 끝낸다(편집 전 확인).
  - EX-139 연결 실행이 끝난 뒤(05:20Z) 시작했다. 이후 수정은 `EP-218 chain finished` 뒤에만 한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] 합산 결정·방어 문구·서빙·Study·지표·CLI와 검사
  - pytest `integration/laya_imitation/tests` 99 통과(새 검사 9)
  - ruff(`--select=E9,F63,F7,F82,F401,F811 --line-length=120`)와 compileall 통과
- [x] mock(CPU 2경기, tp3, 분모 밖): 2/2 정상·감사 통과(둘 다 패배, 기본 체크포인트)
- [ ] EX-140 prepare·execute(384경기)·export, 뷰어 Playwright 검사, 봉인, 자원 반환
- [ ] STATUS, 뷰어 변경일지, catalog build/check

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 합산 결정 | 합성 분포: 합 1, 테라 여부 = k×합 > 최고 비테라, 테라 없음·0이면 그대로, 1순위가 이미 테라면 같음 | `test_tera_decision` | 통과 |
| 플레이어 호환 | 서버 `/evaluate` 응답을 `player.validate_response`로 검사(tp1·tp3·tdef) | `test_tera_decision` | 통과. tp는 `model_probabilities` 기록 |
| 방어 문구 | d195 사례 6개: 상태 텍스트 같음, 테라 선택지에만 `; terastallize` 뒤 `takes`·`worst` | `test_tera_decision`; EX-139 fix 입력 409개 시험 렌더 | 통과 |
| 기준 재현 | EX-139 fix 로그에 규칙 재적용: 처음 테라 47(k=1)·95(k=3)/128, rule_effect 128/128 같음 | `test_tera_decision` | 통과 |
| 기존 동작 | 기존 검사 90개 | `pytest integration/laya_imitation/tests` | 통과 |

## 진행

- 2026-10-27 05:00Z — 자원 확인: GPU0 EX-136 학습, GPU2 유휴(EX-138 예약), GPU3 외부 47.8GB, GPU1 EX-139 실행 중.
- 2026-10-27 — 계획 보고. 사용자가 입력을 v2fix로 바꾸고 테라 방어 문구(A안)를 세 번째 조건으로 추가하도록 지시했다.
- 2026-10-27 05:20Z — EX-139 연결 실행 종료(GPU1 반환). EX-136 `training` 확인 후 코드 반영과 검사를 마쳤다.
- 2026-10-27 05:28Z — mock(분모 밖) 2/2 정상 종료·감사 통과. 서빙 identity `decision` k=3, 경기마다 규칙이 1순위를 1회 테라로 바꿨고 플레이어 검사를 통과했다.
- 2026-10-27 05:28Z — prepare(384슬롯, 서빙 셋 모두 `12519d98…`, EX-139 `result.json` `58d449ec…` 동결) 후 execute를 시작했다. 연결 실행 로그는 `runs/model-training/EP-220-chain.log`다. 이후 `integration/laya_imitation`은 수정하지 않는다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-140을 참조한다. 자동 재실행은 없다. 배틀 실행 중에는 worker가 import하는 코드를 수정하지 않는다.

## 결과 및 증거

- 진행 전
