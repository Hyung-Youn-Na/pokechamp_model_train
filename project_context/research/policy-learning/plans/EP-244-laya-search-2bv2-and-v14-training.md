# EP-244 — 상대 회복·흡수 대면 대응: 2-B v2 탐색 개선(CPU 서빙) 및 v14 입력·MCTS-5k Q 재학습 병행 (GPU 0·1 전용)

- 상태: Paused
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-24 대화: "1.을 진행하면서 2. 도 같이 병행해서 진행하고 싶습니다. 1.은 cpu를 사용해서 서빙하면 2.과 병행이 가능한지 확인해주세요." → 자원 검증 보고 후 "넵 진행해주세요."), [D-220](../decisions/D-220-laya-recovery-matchup-2bv2-and-v14.md), [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-191](../decisions/D-191-no-offline-battle-gate.md). (1) 2-B v2 구현·오프라인 검증 → `EX-212`(CPU 서빙 Blim 128)과 (2) `v14` 렌더러 구현·데이터 재렌더링(CPU 16w `nice 19`) → `EX-213`(물리 GPU 0·1 DDP 학습·오프라인 검증)을 병행 실행한다. 외부 호출은 없다.
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-220](../decisions/D-220-laya-recovery-matchup-2bv2-and-v14.md), [EX-212](../experiments/EX-212-laya-search-2bv2-vs-foulplay-unlimited.md), [EX-213](../experiments/EX-213-laya-v14-data-and-mcts5k-training.md), [EX-214](../experiments/EX-214-laya-v14-search2bv2-vs-foulplay-unlimited.md), [EX-215](../experiments/EX-215-laya-search2bv2-ladder.md)
- 겹치는 등록 plan:
  - [EP-243](EP-243-laya-multiturn-search-value-distill.md)(Active): `EX-206~210` 완료·봉인, `EX-211` 조기 종료(`Stopped`). 기존 `integration/laya_search/{search_core,search_worker,search_2b,value_model,featurize}.py` 동작은 하위 호환으로 보존하고 새 모듈 `search_2b_v2.py`를 추가한다.
  - [EP-240](EP-240-laya-v13-input-bugfixes.md)(Completed): `render_v13`을 읽기/import 전용으로 래핑한다.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit: `research/model-training`, `a80cb51` 위
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(`.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python`), foul-play venv(`.tools/foul-play/.venv`, `PYTHONHASHSEED=0`), `scripts/laya-search-2bv2-ep244`, `scripts/laya-v14-ep244`
- 새 산출물:
  - 코드: `integration/laya_search/{search_2b_v2.py,battle_search_v2.py,tests/test_search_2b_v2.py}`, `integration/laya_v14/{__init__.py,render_v14.py,data_v14.py,train_v14.py,tests/test_v14.py}`, `scripts/laya-search-2bv2-ep244`, `scripts/laya-v14-ep244`
  - 자료: `datasets/generated/laya-v14-mcts5k-q/v1/` (`train.jsonl`, `heldout.jsonl`, `anchor/`, `foe-anchor.jsonl`)
  - 실행 산출물: `runs/model-training/EX-212`, `EX-213`, 뷰어 `exports/battle_viewers/ex212/`

## 범위와 불변 조건

- **보존**: 동결 패키지(`laya_imitation`, `laya_threat`, `laya_v10~v13`, `laya_foe`, `laya_value`, `laya_fp1`, `laya_regret`, `laya_distill`, `foulplay`, `.tools/foul-play/src`, `pokechamp`)와 기존 봉인·자료는 바이트 단위로 유지한다.
- **GPU 격리**: **물리 GPU 0(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`)·GPU 1(`GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`)만 사용**한다. GPU 2·3은 타 프로젝트 전용으로 일절 점유하지 않는다. `EX-212`는 **CPU 서빙**(`CUDA_VISIBLE_DEVICES=''`, `OMP_NUM_THREADS=4 MKL_NUM_THREADS=4`)으로 돌려 `EX-213`의 GPU 0·1 DDP와 완전 분리한다.
- **CPU / RAM**: `EX-213` 데이터 렌더링은 `16워커 nice 19, mem-guard 30`으로 제한해 `EX-212`의 `foul-play` 3,000ms 탐색(`p50 ~7.2s`)에 간섭이 없도록 한다.
- **봉인 무결성**: 배틀 실행 로그(`EX-212-lane.log`)는 반드시 실행 디렉터리 바깥에 기록한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] D-220·EP-244·EX-212~214 등록, catalog build/check
- [ ] **Track 1 (2-B v2)**: `search_2b_v2.py`·`battle_search_v2.py` 구현, 단위검증 및 `sleepman610`(T4~7 `Draining Kiss`)·`Xrlylyl`(T22~23 `Water Absorb`)·`EX-203` 오프라인 회귀 통과 → `EX-212` mock 2/2 → prepare → execute 128 (CPU 서빙) → export(보고·뷰어·봉인)
- [ ] **Track 2 (`v14`)**: `integration/laya_v14/` 구현·단위검증 및 라이브-오프라인 일치 확인 → `v14` 데이터 재렌더링(CPU 16w `nice 19`) → `EX-213` GPU 0·1 DDP 1에폭 학습 → held-out MCTS-5k Q·테라 지식 평가 완료
- [ ] `EX-212`·`EX-213` 결과 기록·catalog 동기화·보고(뷰어 링크 포함, C-047)

## 진행

- 2026-11-24T00:26Z — 사용자 승인으로 D-220·EP-244·EX-212~214 등록. Track 1(`2-B v2`)과 Track 2(`v14`) 구현·검증 착수.
- 2026-11-24T00:37Z — 구현·검증 완료(`laya_search` 23/23, `laya_v14` 2/2, `laya_v13` 19/19 총 44/44 통과; `Xrlylyl` T22 라이브 E2E `opp hp 0.06→0.31` 및 `absorb_penalties=0.15` 확인). Track 1 **`EX-212`**(CPU 서빙 `mock→prepare→execute 128→export`, `EX-212-lane.log`)와 Track 2 **`EX-213`**(`v14` 데이터 16w `nice 19` → 물리 GPU 0·1 DDP 학습 → GPU 0 평가, `EX-213/lane.log`) 병행 백그라운드 착수.
- 2026-11-24T02:02Z — 사용자 지시로 병행 실행했던 Track 3 **`EX-215`**(공식 Showdown 래더, CPU 서빙)을 진행 중이던 9번째 판(`vs yiht`, 41턴) 완료 시점에 기권 없이 정상 종료(`Stopped`). 9판 4승 5패(`1437→1446`, 교체 후 `t61731415d7` 8판 4승 4패 `1429→1446`, 1500+ 2승 2패, 오류 0, `replays.md` 678경기 동기화). Track 1 `EX-212` 및 Track 2 `EX-213`은 계속 진행 중.
- 2026-11-24T02:13Z — 사용자 지시로 `strategy.duel()` 전 공격기 무효 시 `duel: lose` 미발화 등 렌더러 입력 버그를 먼저 보완하기 위해 Track 1 **`EX-212`**(`18/128`, 7승 11패 `0.389`)와 Track 2 **`EX-213`**(`v14` 데이터 완료 후 DDP `step 4,500/34,857`)을 모두 조기 종료(`Stopped`)하고 물리 GPU 0·1 및 CPU 자원을 유휴 반환. `EP-244` 일시 정지(`Paused`), 후속 수정 지시 대기.
