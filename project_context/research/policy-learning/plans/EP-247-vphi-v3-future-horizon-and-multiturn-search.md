# EP-247 — 미래 영향력 반영 가치함수 V_phi v3 및 2-ply 다수 턴 탐색 · Way A v2 검증 (GPU 0·1 전용)

- 상태: Completed
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-24 17:30 KST, "진행해주세요." — 미래 영향력을 반영한 가치함수 $V_\phi$ v3 학습·검증 및 2-ply Top-K 다수 턴 탐색기 + `Way A v2` 가드레일 오프라인 A/B 검증), [D-223](../decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md), [D-191](../decisions/D-191-no-offline-battle-gate.md). 외부 호출은 없다.
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-223](../decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md), [EX-221](../experiments/EX-221-laya-state-value-v3-future-train.md), [EX-222](../experiments/EX-222-multiturn-2ply-waya-v2-ab.md), [EX-223](../experiments/EX-223-laya-waya-v2-vphiv3-2ply-vs-foulplay.md)
- 겹치는 등록 plan:
  - [EP-245](EP-245-laya-main-blunder-veto-mcts50k-vphi-v2.md)(Completed): `matchup_features.py`, `value_model_v2.py`, `way_a.py`, `EX-216`/`EX-217` 산출물은 수정하지 않고 보존한다.
  - [EP-246](EP-246-laya-way-c1-v14-walled-teacher50k-distill.md)(Paused): `EX-218` `hard_heldout.jsonl`은 오프라인 A/B 진단 입력으로 읽기 전용 참조만 한다.
  - [EP-243](EP-243-laya-multiturn-search-value-distill.md)(Active): `featurize.py`, `datasets/generated/laya-state-value/v1/`은 읽기 전용으로 보존한다.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit: `research/model-training`, `a80cb51` 위
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(`.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python`), foul-play venv(`.tools/foul-play/.venv`, `PYTHONHASHSEED=0`)
- 새 산출물:
  - 1단계(`EX-221`): `integration/laya_search/{featurize_v3.py,data_value_v3.py,value_model_v3.py,train_value_v3.py,tests/test_value_v3.py}`, `datasets/generated/laya-state-value/v3/`, `runs/model-training/EX-221/{checkpoints/selected,selection.json,ablation.json}`
  - 2단계(`EX-222`): `integration/laya_search/{search_multiturn.py,way_a_v2.py,eval_ab_v3.py,tests/test_multiturn_waya_v2.py}`, `runs/model-training/EX-222/{ab_summary.json,ex220_replay_audit.json}`

## 범위와 불변 조건

- **보존**: 동결 패키지 및 기존 `EX-207`/`EX-216`/`EX-217`/`EX-218` 코드·산출물은 수정하지 않는다.
- **GPU 격리**: **물리 GPU 0(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`)·GPU 1(`GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`)만 사용**한다. GPU 2·3은 일절 점유하지 않는다.
- **누수 통제**: `EX-221`은 `EX-207`/`EX-216`과 완전히 동일한 게임 단위 분할(`SEED=20261207`, train 5,470 / calib 304 / val 304, Blim 64팀 제외)을 사용하며, 반사실적 쌍(`train_cf.npz` / `val_cf.npz`)도 동일한 게임 분할을 엄격히 따른다.
- **외부 호출**: 없다.

## 완료 기준

- [x] D-223·EP-247·EX-221·EX-222 등록 및 catalog 동기화
- [x] **1단계 (`EX-221`)**: `featurize_v3.py`·`data_value_v3.py`·`value_model_v3.py`·`train_value_v3.py` 구현 및 단위·반대칭 테스트 통과 → `datasets/generated/laya-state-value/v3/` 추출(`356,514` 상태 + `43,586` 반사실 쌍) → 물리 GPU 0 단독 학습·절제·캘리브레이션 완료(`v3_cf_06` 선택: `val LL 0.58985`, `AUC 0.74820`, `ECE 0.02381`, `rh70 64.1%→71.0%`, `rh40_69 38.3%→45.6%`, `acc_low 73.7%` 보존)
- [x] **2단계 (`EX-222`)**: `search_multiturn.py`(2-ply Top-K Expectiminimax) + `way_a_v2.py` 가드레일 구현·테스트 → `EX-220` 4대 실패 장면 교정 확인 및 `EX-217` Blim 240턴 A/B 완료(`HEAL 34.5%→27.5%`, `HP≥90% 8.0%→2.0%`, 2-ply `p50 424ms`)
- [x] **3단계 (`EX-223`)**: `EX-221`·`EX-222` 확인 직후 `battle_way_a_v2.py` (`EX-221` $V_\phi$ v3 + `2-ply` + `Way A v2` + `MCTS 50k` + `walled_duel`, 물리 GPU 0 단독)로 Blim 128경기 실행·봉인·뷰어 출력([C-047](../../../CONTRACTS.md#c-047-viewer-export)) 및 `EX-217`·`EX-208` 대비 보고 — **`128/128` 완료(`verify_seal == []`), 53승 0무 75패 `0.414 [0.328, 0.492]` (Blim 128 역대 최고점)**

## 진행

- 2026-11-24T08:33Z — 사용자 승인으로 D-223·EP-247·EX-221·EX-222 등록. 1단계(`EX-221` $V_\phi$ v3) 구현·데이터 추출·학습 착수.
- 2026-11-24T08:45Z — 사용자 추가 지시("고친 상태함수로 기존 상태함수를 대체하여 foulplay 테스트도 이어서 진행해주세요.")에 따라 3단계 `EX-223` 등록 및 `search_worker.py`·`serve_search.py`·`battle_way_a_v2.py`·`scripts/laya-way-a-v2-ep247` 구현 완료.
- 2026-11-24T10:25Z — 1단계 `EX-221` 및 2단계 `EX-222` 완료 확인. 3단계 `EX-223` foul-play Blim 128경기(`scripts/laya-way-a-v2-ep247 all`, 물리 GPU 0 단독) 착수.
- 2026-11-24T14:52Z — **3단계 `EX-223` 완료·봉인 (`Completed`)**: Blim `128/128` 정상 완료(`verify_seal == []`, 오류 `0`), **53승 0무 75패 `0.414 [0.328, 0.492]`** (기존 최고 `EX-208 0.406` 및 `EX-217 0.391` 상회; `EX-217` 대비 같은 슬롯 `+0.023 [-0.070, +0.117]`, `EX-208` 대비 `+0.008 [-0.102, +0.109]`, `EX-205` 대비 `+0.102 [+0.000, +0.205]`, 실패 기술률 `5.72% → 4.95%`, 뷰어 `exports/battle_viewers/ex223/index.html`, 물리 GPU 0·1 유휴 반환). `EP-247` 완료(`Completed`).
