# EP-224 — laya 엔진 판정기(고정 Showdown 실패 판정)와 렌더러 v8 학습·배틀(GPU1·GPU2)

- 상태: Completed
- 생성일: 2026-11-02
- 책임자: Claude Code
- 승인 근거·범위: 사용자 지시(2026-11-02, 엔진 판정기 구축 → 실전 검증 → 통과 시 v8 학습·배틀까지 별도 승인 없이)와 [D-201](../decisions/D-201-laya-engine-judge-v8.md). 오프라인 결과로 배틀을 거르지 않는다([D-191](../decisions/D-191-no-offline-battle-gate.md)). 판정기 검증(EX-151) 정밀도 99% 미만이면 EX-152 이후로 가지 않는다.
- 관련 contract / decision / experiment: [C-055](../CONTRACTS.md#c-055-imitation), [EX-151](../experiments/EX-151-laya-engine-judge-validation.md), [EX-152](../experiments/EX-152-laya-v8-engine-fails-training.md), [EX-153](../experiments/EX-153-laya-v7t-v8t-battle256.md), [EX-154](../experiments/EX-154-laya-head-to-head-v8t-v7t.md), [EX-155](../experiments/EX-155-laya-v8l-likely-fails-training.md), [EX-156](../experiments/EX-156-laya-v8t-v8lt-battle256.md), [EX-149](../experiments/EX-149-laya-v7-opponent-sets-training.md), [EX-150](../experiments/EX-150-laya-v6st-v7t-battle256.md)
- 기준 연구선: `research/model-training`
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, `pokechamp/.venv`, node. 실행기 `scripts/laya-imitation`, 연결 실행 `scripts/laya-imitation-ep224 <lane>`
- 새 산출물과 검증 출력 위치:
  - `/mnt/digicap/combined/hyna/backup/pokechamp-research/datasets/generated/laya-engine-judge/v1`, `.../laya-compact-imitation/v8-all`
  - `.../runs/model-training/EX-151` ~ `EX-154`, 연결 실행 로그 `.../runs/model-training/EP-224-<lane>.log`
  - 뷰어 `/workspace/exports/battle_viewers/ex153/`, `ex154/`
- 참조 원자료(읽기 전용): fail-survey(`exec-plans/evidence/ep223/fail-survey/`), EP-221~223 배틀 경기, EX-071 `prepared/`·원본 리플레이, `laya-compact-features/v5`, `laya-item-state/v1`, EX-149 산출물

## 목표와 맥락

선택지 실패 표시의 근거를 사람이 쓴 예외 규칙에서 고정 엔진 시뮬레이션으로 바꾸고(D-201), 그 표시로 학습한 v8이 v7보다 실패 기술을 덜 쓰고 성적이 떨어지지 않는지 본다.

## 범위와 불변 조건

- **포함**: `integration/laya_engine/` 새 코드와 단위 검사, laya_imitation 연결(config·serving·training·cli·comparison·headtohead), 연결 실행 스크립트, 기록
- **보존**:
  - `serving.V7_RENDER_FILES` 전체(특히 `effect_knowledge.py`·`features_v7.py`·`compact_v7.py`·`data_v7.py`)는 바이트 단위로 같다. v4~v7 서빙과 EX-118~150 산출물·봉인은 그대로다.
  - 파서(replay.py·schema.py·player.py)는 바꾸지 않는다. 사람 라벨과 분할도 바꾸지 않는다.
  - 다른 세션의 새 파일(예: `fail_decision.py`)과 실험 번호는 건드리지 않는다.
- **자원**: GPU1·8109(EX-152 학습, EX-153), GPU2·8108(EX-154)만 쓴다. GPU0, GPU3, 포트 8106·8107은 쓰지 않는다. 외부 프로세스 종료와 장치 reset은 금지한다.
- **코드 수정 규칙**: laya_imitation·파서·`scripts/laya-imitation`은 `.pokechamp-data/battle-window/`에 다른 세션의 표시 파일이 없을 때만 고친다. 이 계획의 배틀은 prepare 직전에 표시 파일(파일명 = 실험 ID, 내용 = 시작 시각·GPU)을 만들고 export 뒤 지운다. 실행 중인 bash 연결 스크립트는 고치지 않는다.
- **외부 호출**: 없다.

## 완료 기준

- [x] 판정기 구축, 단위 검사, EX-151 검증(정밀도 99.84%), `laya-engine-judge/v1` 생성·봉인
- [x] D-201, EP-224, EX-151~154 등록, catalog build/check
- [x] laya_imitation 연결, v8 렌더러 동일성(v2~v7 동일 유지), 단위 검사(laya_imitation·laya_engine 125 통과·5 skip)
- [x] EX-152 길이 사전 측정 → `v8-all` 생성 → parity → 학습 → 평가
- [ ] EX-153·EX-154 mock·배틀·보고·뷰어 (EX-153 완료, EX-154는 실행되지 않음: Stopped)
- [x] 결과를 EX 문서, STATUS, catalog에 기록

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| 판정기 정밀도 | 9개 실행 모델 기술 전수 | `runs/model-training/EX-151/validation/` | 99.84%(EX-151) |
| 기존 렌더 보존 | `renderer_matches_dataset('v4'…'v7')` | laya_imitation 단위 검사 | 통과(`V7_RENDER_FILES` 바이트 동일, v2~v7 참, 단위 검사 125 통과·5 skip) |
| v8 렌더 동일성 | `renderer_matches_dataset('v8')`(laya_imitation v7 파일 + 판정기 파일) | `v8-all/generator-source` | 진행 기록: v8l 연결 때 v4~v8 렌더 동일 유지, EX-156 연결 때 v7·v8·v8l 렌더 동일. parity 통과 |
| 오프라인·서빙 일치 | `v8 parity` validation 512행 | `EX-152/diagnostics/parity.json` | 511행 불일치 0(길이 초과 1행 제외). v8l도 511행 불일치 0 |

## 진행

- 2026-11-02 — 사용자 지시로 시작. nvidia-smi: GPU0만 사용 중(다른 작업), GPU1·2·3 비어 있음. battle-window 표시 파일 없음. EP-223 레인은 모두 끝났다(EX-150-H completed).
- 2026-11-02 — 판정기 구축(`integration/laya_engine/`), 단위 검사 11건. 파서 변경 없음.
- 2026-11-02 — EX-151 검증: 1차 92.6% → 상대 선공 경우 확장 → 99.84%. 사람 리플레이 오판 원인 보완(미공개 압정·벽 제거기, 대타 HP, 얼음) 뒤 최종 99.84%, 사람 선택 표시 수의 실제 실패 736/749(교체 제외). `laya-engine-judge/v1` 생성(행 131,947, 97초)·봉인.

- 2026-11-02 — battle-window 표시 파일 없음을 확인하고 laya_imitation 연결 수정(config·serving·training·cli·comparison·headtohead). `V7_RENDER_FILES` 전체 바이트 동일, `renderer_matches_dataset` v2~v7 참. 단위 검사 125 통과·5 skip. 린트(E9,F63,F7,F82,F401,F811) 통과.
- 2026-11-02 — EX-152 사전 측정: validation 초과 1/512(0.20%), 표시 행 116(규칙 119), 표시 선택지 229(규칙 238, 추가 24·제거 33), 규칙 대체 26선택지·10결정. EX-071 턴 결정의 1.8%(1,985/111,119)에서 일부 선택지가 엔진에서 선택 불가(사람 리플레이 자기 세트 추정, 예: Assault Vest인데 변화기 선택지)라 그 선택지만 규칙 표시를 쓴다.
- 2026-11-02 03:43Z — `scripts/laya-imitation-ep224 gpu1`(EX-152 → EX-153), `gpu2`(EX-152 완료 대기 → EX-154) 시작. 로그 `runs/model-training/EP-224-gpu1.log`·`-gpu2.log`.

- 2026-11-02 04:4xZ — 사용자 지시로 `likely fails` 표시 변형 v8l 학습(EX-155, GPU2)을 추가했다(D-201 추가 결정). battle-window 표시 파일 없음을 확인하고 laya_imitation에 v8l 연결(config·serving·training·cli·comparison)을 더했다(v4~v8 렌더 동일 유지). 사전 측정 초과 1/512(0.20%), validation likely 표시 8행·11선택지. 대기 중이던 자기 레인 `ep224 gpu2`를 멈추고 `scripts/laya-imitation-ep224b gpu2`(EX-155 data→parity→train → EX-152 봉인 대기 → EX-155 평가 → EX-154)로 바꿨다. 로그 `runs/model-training/EP-224b-gpu2.log`.

- 2026-11-02 — 사용자 지시로 v8lt Abyssal 배틀(EX-156, v8t 대 v8lt 256경기, 시드 20261050)을 예약했다. battle-window 표시 파일 없음을 확인하고 laya_imitation에 `EX156` Study·`compare15`·v8l 뷰어 렌더러를 더했다(v7·v8·v8l 렌더 동일, 단위 검사 114 통과·5 skip). `scripts/laya-imitation-ep224c gpu1`이 EX-153·EX-155 completed를 기다린 뒤 GPU1·8109에서 실행한다(로그 `EP-224c-gpu1.log`).

- 2026-11-02 14:44Z — `gpu1` 레인: EX-152 `v8-all` 생성 03:43Z(제외 455행, 0.345%), parity 511/511, 학습 03:45Z~14:41Z, 평가 완료.
- 2026-11-02 15:43Z — `ep224b gpu2` 레인: EX-152 완료(15:41Z)를 확인하고 EX-155 평가를 마쳤다. 15:43:58Z EX-154 mock이 인자 오류로 끝나 레인이 멈췄다. `headtohead.STUDIES`에는 `EX-154`가 있지만 `cli.py`의 `h2h --study` choices에 빠져 있었다. mock 전이라 battle-window 표시와 `runs/model-training/EX-154`는 만들어지지 않았다. 자동 재실행하지 않았다.
- 2026-11-02 17:09Z — `gpu1` 레인 종료: EX-153 mock 2/2, 14:46Z 표시 생성, 14:46Z~17:04Z 256/256 정상, 17:09Z 표시 삭제, 뷰어 확인 통과.
- 2026-11-02 19:42Z — `ep224c gpu1` 레인 종료: 17:13Z EX-153·EX-155 완료 확인, EX-156 mock 2/2, 17:14Z 표시 생성, 17:14Z~19:34Z 256/256 정상, 19:42Z 표시 삭제, 뷰어 확인 통과. 이로써 EP-224 레인이 모두 끝났다. EX-154는 다시 실행하지 않았고 Stopped로 기록한다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. 자동 재실행은 없다. 각 레인은 실패한 단계에서 멈춘다. 학습 결함(재로딩·parity·해시 불일치, 학습 중단)이나 mock 실패만 배틀 전에 멈출 수 있다(D-191).

## 결과 및 증거

- EX-151: [결과](../experiments/EX-151-laya-engine-judge-validation.md#결과)
- [EX-152](../experiments/EX-152-laya-v8-engine-fails-training.md): 잠긴 test NLL 1.4332 → 1.4227(−0.0104, 95% [−0.0381, +0.0170]), 일치율 45.78 → 46.76%. v8 표시 선택지 확률 합 0.0512 → 0.0407(95% [−0.0158, −0.0053]), argmax 4 → 2. 테라 지식 A 96.9 → 97.4%.
- [EX-153](../experiments/EX-153-laya-v7t-v8t-battle256.md): v7t 112-16, v8t 111-17, 차이 −0.0078 [−0.0781, +0.0703] → 퇴보를 배제하지 못함. 기술 실패율 5.17 → 3.64%(171 → 126), 테라 사용 경기 28 → 21.
- [EX-154](../experiments/EX-154-laya-head-to-head-v8t-v7t.md): Stopped. `cli.py` `h2h --study` choices에 `EX-154`가 없어 mock 단계 인자 오류로 레인이 멈췄다. 경기 0, 판정 없음.
- [EX-155](../experiments/EX-155-laya-v8l-likely-fails-training.md): 잠긴 test NLL 1.4350(EX-152 대비 +0.0123 [−0.0162, +0.0404], EX-149 대비 +0.0018 [−0.0240, +0.0283]). `likely fails` 표시 test 7행의 확률 합·argmax는 EX-152·EX-149와 구별되지 않는다.
- [EX-156](../experiments/EX-156-laya-v8t-v8lt-battle256.md): v8t 111-17, v8lt 112-16, 차이 +0.0078 [−0.0469, +0.0703] → 비퇴보. 기술 실패 126 → 148(Stealth Rock 18 → 39).
- 결론: 엔진 판정기 표시(v8)는 실패 기술을 줄였지만 Abyssal 성적은 v7과 구별되지 않는다(퇴보를 배제하지 못함). `likely fails`(v8l)는 v8 대비 비퇴보다. v8t 대 v7t 직접 대결은 실행기 결함으로 결과가 없다.
