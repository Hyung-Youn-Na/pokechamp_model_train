# EP-219 — laya v2+테라 보정 입력 배틀(재학습 없음, GPU1)

- 상태: Completed
- 생성일: 2026-10-27
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-10-27). 사용자가 계획을 승인하면 구현, mock, 배틀, export를 별도 승인 없이 이어서 진행한다. 커밋은 하지 않는다. 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)).
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [D-196](../decisions/D-196-laya-v2t-corrected-input-battle.md), [EX-139](../experiments/EX-139-laya-v2t-corrected-input-battle256.md), [D-195](../decisions/D-195-laya-item-state-renderer-v5.md), [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md), [EX-125](../experiments/EX-125-laya-v2-tera-battle256.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher:
  - checkout은 `/workspace`이고, interpreter는 laya venv(서빙·컨트롤러), `pokechamp/.venv`(배틀 worker), node(계산기)를 쓴다.
  - 실행기는 `scripts/laya-imitation compare8 {mock,probe,prepare,execute,export}`다. 실행기 파일은 고치지 않았다. compare7처럼 laya venv 컨트롤러로 돈다.
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-139`
  - 뷰어 `/workspace/exports/battle_viewers/ex139/`
- 참조 원자료(읽기 전용):
  - EX-124 selected 체크포인트
  - EX-125 `manifest.json`·`result.json`·경기
  - EX-120 `collection/`
  - v2·v5 자료의 `generator-source/`
  - 사람 대전 국면 `runs/model-training/EX-136/diagnostics/nhj-probe-inputs.json`

## 목표와 맥락

최고 성적 모델 v2t(EX-124)를 재학습하지 않고 D-195 보정 입력으로 서빙했을 때 Abyssal 배틀 성적이 어떻게 달라지는지 측정한다. 입력 변형은 두 가지다.

- fix: 같은 형식에 값만 보정한다.
- info: 학습 때 본 적 없는 문구를 추가한다.

조건과 판정은 EX-139가 소유한다.

## 범위와 불변 조건

- **포함**:
  - 새 파일: `input_variants.py`(렌더 `v2fix`/`v2info`, 원본 대조, identity), `variant_battle.py`(EX139 Study, EX-125 같은 슬롯 요약·판정, Sleep Talk·풍선 지표, 단계 함수, 보고), `tests/test_input_variants.py`
  - 덧붙이기:
    - `serving.py`: `MODELS` 3개, `_dataset`·`renderer_matches_dataset`·렌더러 표의 새 렌더 분기, `variant_renderer`, 새 렌더일 때만 identity 필드 추가
    - `comparison.RENDER` 3개
    - `config.py`: `RUN_COMPARE8`, `VIEWER_COMPARE8`
    - `cli.py`: `--render v2fix|v2info`, `compare8`, status
- **보존**:
  - 다음 파일은 수정하지 않는다: `features.py`, `features_v4.py`, `features_v5.py`, `compact*.py`, `item_state.py`, `data_v5.py`, `replay.py`, `schema.py`, `player.py`, `scripts/laya-imitation`
  - `comparison.py`의 EX137과 `headtohead.py`의 EX138은 그대로다.
  - v1~v5 서빙 경로와 identity는 바이트 단위로 같다.
  - EX-124·EX-125 산출물과 봉인은 읽기만 한다.
- **자원**:
  - GPU1·포트 8109만 쓴다.
  - GPU0·GPU2·GPU3과 다른 포트(EP-218 EX-136~138 포함), 외부 프로세스는 건드리지 않는다. 프로세스 종료나 장치 reset을 하지 않는다.
- **동시 실행 제약**(EP-218이 같은 checkout에서 실행 중):
  - EX-137·EX-138의 prepare는 `integration/laya_imitation/` 전체 해시를 동결하고, execute 시작 때 대조한다. 배틀 worker는 경기마다 코드를 새로 import한다.
  - 그래서 모든 코드 작업은 `runs/model-training/EX-136/status.json`의 stage가 `training`인 동안에 끝낸다. 편집 전마다 stage를 확인했다.
  - 그 뒤의 수정은 `EP-218-chain.log`에 `EP-218 chain finished`가 찍힌 뒤에만 한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] 새 렌더·서빙·Study·지표·CLI와 검사
  - pytest `integration/laya_imitation/tests` 90 통과(새 검사 9)
  - ruff(`--select=E9,F63,F7,F82,F401,F811 --line-length=120`)와 compileall 통과
- [x] Sleep Talk 분류를 D-195 수치로 확인: EX-131 v2t 사용 100·실패 43·깨어남 26·깨어 있음 17(EX-125 v2t 동일)
- [x] mock(CPU 2경기, `v2info`, 분모 밖): 2/2 정상 종료·감사 통과(둘 다 패배, 기본 체크포인트). 실전 입력 94/94에 D-195 필드가 있고, 서빙 렌더는 `laya-compact-v5[counters,damage,items,moves,speed,switch]`, `trained_render`는 v2다.
- [x] 사람 대전 132결정 재추론(GPU1, 보고 전용, `EX-139/diagnostics/nhj-probe.json`)
- [x] EX-139 prepare·execute(256경기)·export, 뷰어 Playwright 검사, 봉인, 자원 반환(05:20Z, GPU1·8109 반환)
- [x] STATUS, 뷰어 변경일지·상위 목록, catalog build/check

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| fix는 v2 형식 | d195 사례 6개: 줄 라벨·선택지 키가 v2와 같고 v5 문구가 없다. 실전 입력(EX-137 mock 59개) 렌더 비교 | `test_input_variants` | 통과. mock 입력 59개 중 fix가 v2와 다른 7개는 모두 Knock Off `65 → 98 (target item)`(효과로 공개된 Leftovers)이다. 이 문구는 v2 어휘 안에 있다 |
| fix 값 보정 | 23번 T13 Earth Power `dmg 0-0%` 사라짐, 25번 T10 Earthquake `x0`, `; fails` 없음 | `test_input_variants` | 통과 |
| info 문구 | `item none (popped)`, `slp t1 rest`, `grassy_terrain t2` | `test_input_variants` | 통과 |
| 서빙 identity | 새 렌더는 v5 렌더 이름, `trained_render`, `renderer_sources`. 기존 v2 identity에는 새 키가 없다 | `test_input_variants` | 통과 |
| 판정 함수 | 합성 결과로 개선·악화·구별되지 않음·보류 | `test_input_variants` | 통과 |
| 기존 동작 | 기존 검사 81개 | `pytest integration/laya_imitation/tests` | 통과 |

## 진행

- 2026-10-27 02:16Z — 상태 확인: EX-136 `training`, GPU1 유휴, `EP-218 chain finished` 없음.
- 2026-10-27 — 계획을 보고했고 사용자가 승인했다. 구현과 검사를 마쳤다(EX-136 `training` 동안).
- 2026-10-27 — 재추론 첫 실행에서 결함을 찾았다. 텍스트 비교를 `decision` id로 묶었는데, 이 id가 네 경기 사이에서 겹쳐(132결정 중 고유 92) 다른 경기의 텍스트와 비교됐다. 선택 비교는 영향이 없었다. 위치 기준으로 고쳐 다시 실행했다. 잘못된 출력은 run 밖으로 옮겼다.
- 2026-10-27 — 서빙 identity의 `render`를 기존 서빙과 같은 형식(`compact_v5.version` 사전)으로 맞췄다. mock은 그 전 형식(이름 문자열)으로 실행됐다. 분모 밖이며 경로는 같다.
- 2026-10-27 — 사전 점검: mock 경기 사본으로 export 경로(요약·보고·뷰어·입력 변화)를 scratch에서 실행했고, 사본 뷰어의 Playwright 검사를 통과했다. 실전 입력 이벤트는 결정당 하나다(31/31, 63/63).
- 2026-10-27 02:36Z — prepare(256슬롯, 서빙 둘 다 `12519d98…`, EX-125 `result.json` `c6d362d2…` 동결). 02:36:58Z에 execute를 시작했다. 연결 실행 로그는 `runs/model-training/EP-219-chain.log`다. 이후 `integration/laya_imitation`은 수정하지 않는다.
- 2026-10-27 05:16Z — execute 종료(256/256 정상, 감사 전부 통과). 05:20Z export·봉인·뷰어 Playwright 검사(1440px·390px, 페이지 오류 0) 완료, 연결 실행 종료.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 결함 복구와 중단은 EX-139를 참조한다. 자동 재실행은 없다. 배틀 실행 중에는 worker가 import하는 코드를 수정하지 않는다.

## 결과 및 증거

- 판정(EX-125 v2t 같은 슬롯): fix 110승 18패, −0.0078 [−0.0234, +0.0000] **구별되지 않음**; info 108승 20패, −0.0234 [−0.0625, +0.0156] **구별되지 않음**. info − fix −0.0156 [−0.0547, +0.0234].
- 공개된 풍선 상대 지면 기술 v2t 9 → fix 0·info 0, 지면 무효 20 → 10·9, Sleep Talk 실패 43 → 40·35, 테라 경기 22 → 24·25.
- 상세 수치는 [EX-139](../experiments/EX-139-laya-v2t-corrected-input-battle256.md#결과).
- 증거: `runs/model-training/EX-139/`(`report.md`, `result.json` `58d449ec…`, `checksums.sha256`), 연결 실행 로그 `runs/model-training/EP-219-chain.log`, 뷰어 `/workspace/exports/battle_viewers/ex139/index.html`, 뷰어 검사 `exec-plans/evidence/ep219/ex139-viewer-check.json`.
- 후속: [EP-220](EP-220-laya-v2t-tera-decision-defence.md)(EX-140)이 이 실행의 fix 경기를 기준으로 쓴다.
