# EP-245 — Laya 메인 합의형 블런더 가드(방식 A): 상성·도구·특성·기술 반영 V_phi v2 보강 및 MCTS 50k 결합 (GPU 0·1 전용)

- 상태: Completed
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-24 11:28 KST: "좋아 방식 A로 일단 가자. 이때 MCTS는 깊이를 50k로 하도록 하고, V_phi는 상성, 도구, 특성, 기술을 반영하여 정확한 평가가 가능할 수 있도록 보강하는 실험을 먼저 진행하자."), [D-221](../decisions/D-221-laya-main-waya-mcts50k-vphi-v2.md), [D-191](../decisions/D-191-no-offline-battle-gate.md). 1단계로 $V_\phi$ v2 매치업 피처 추출·학습·오프라인/실전 회귀 검증([EX-216](../experiments/EX-216-laya-state-value-v2-matchup-train.md), 물리 GPU 0 전용)을 먼저 완료해 보고하고, 검증 후 2단계로 방식 A(Laya 메인 + MCTS 50k + $V_\phi$ v2 + 렌더러 무효 대면 수정) Blim 128경기([EX-217](../experiments/EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md))로 진행한다. 외부 호출은 없다.
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-221](../decisions/D-221-laya-main-waya-mcts50k-vphi-v2.md), [EX-216](../experiments/EX-216-laya-state-value-v2-matchup-train.md), [EX-217](../experiments/EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md)
- 겹치는 등록 plan:
  - [EP-244](EP-244-laya-search-2bv2-and-v14-training.md)(Paused): `EX-212/213/215` 조기 종료(`Stopped`). 기존 `search_2b_v2.py`·`render_v14.py`는 보존한다.
  - [EP-243](EP-243-laya-multiturn-search-value-distill.md)(Active): `EX-207`(`value_model.py`, `featurize.py`, `datasets/generated/laya-state-value/v1/`)은 읽기 전용으로 보존하고 새 모듈(`matchup_features.py`, `value_model_v2.py`, `train_value_v2.py`)을 추가한다.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit: `research/model-training`, `a80cb51` 위
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(`.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python`), foul-play venv(`.tools/foul-play/.venv`, `PYTHONHASHSEED=0`)
- 새 산출물:
  - 1단계(`EX-216`): `integration/laya_search/{matchup_features.py,value_model_v2.py,train_value_v2.py,tests/test_value_v2.py}`, `runs/model-training/EX-216/{checkpoints/selected,selection.json,diagnostics.json}`
  - 2단계(`EX-217`): `integration/laya_search/way_a.py`(합의형 블런더 가드 + MCTS 50k), 렌더러 `duel: walled -> lose` 보강, `runs/model-training/EX-217`, 뷰어 `exports/battle_viewers/ex217/`

## 범위와 불변 조건

- **보존**: 동결 패키지(`laya_imitation`, `laya_v10~v13`, `laya_foe`, `laya_value`, `laya_fp1`, `foulplay`, `.tools/foul-play/src`, `pokechamp`)와 `EX-207` 산출물·봉인 자료는 수정하지 않는다.
- **GPU 격리**: **물리 GPU 0(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`)·GPU 1(`GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`)만 사용**한다. GPU 2·3은 일절 점유하지 않는다.
- **누수 통제**: `EX-216`은 `EX-207`과 동일한 게임 단위 분할(train 5,470 / calib 304 / val 304, Blim 64팀 제외)을 사용하며, 원시 종족·도구·기술 ID 임베딩이 아닌 팀-독립적 기계적 매치업 피처로 일반화를 검증한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] D-221·EP-245·EX-216·EX-217 등록 및 catalog 동기화
- [x] **1단계 (`EX-216`)**: `matchup_features.py`·`value_model_v2.py`·`train_value_v2.py` 구현 및 단위·반대칭·실전 메커니즘 검증 통과 → 물리 GPU 0 학습·캘리브레이션 → held-out(`EX-207`·`evaluate.rs` 비교) 및 실전 회귀 3종(`Air Balloon Gholdengo` T10~11, `Draining Kiss` T4~6, `Water Absorb` T22) 결과 보고
- [x] **2단계 (`EX-217`)**: `EX-216` 확인 후, 방식 A(Laya 메인 + MCTS 50k + $V_\phi$ v2 + 렌더러 `duel: walled` 수정) 구현·검증 → Blim 128경기 실행·봉인·뷰어 출력([C-047](../../../CONTRACTS.md#c-047-viewer-export))·보고

## 진행

- 2026-11-24T02:31Z — 사용자 지시로 D-221·EP-245·EX-216·EX-217 등록. 1단계 `EX-216`(상성·도구·특성·기술 반영 $V_\phi$ v2) 구현 및 GPU 0 학습 착수.
- 2026-11-24T02:42Z — **1단계 `EX-216` 완료**: 절제 실험에서 정적 키트 플래그(팀 지문화)를 제외한 `pair_only(38)+global(47)`(`54,529` params, 정확한 반대칭성)가 held-out 304경기(`17,699`행)에서 `AUC 0.75362` (`EX-207 0.73893` 대비 **`+0.01469`**, `evaluate.rs 0.72346` 대비 **`+0.03016`**), `LogLoss 0.58475` (`-0.01199`), 종반 `AUC 0.85286` (`+0.02459`) 달성. `Air Balloon` T10~11에서 `switch:5/2`를 2·3위로 복원. 2단계(`EX-217`: 방식 A + MCTS 50k + 렌더러 `duel: walled` 수정) 진행 준비 완료.
- 2026-11-24T07:11Z — **2단계 `EX-217` 완료·봉인 (`Completed`)**: Blim `128/128` 정상 완료(`verify_seal == []`, `2,955`파일, 오류 `0`), **50승 0무 78패(`0.391 [0.312, 0.461]`)**. 같은 슬롯 `EX-208`(`0.406`) 대비 `-0.016 [-0.133, +0.102]`(`25/27/76`), `EX-205` 대비 `+0.079`, `EX-174` 대비 `+0.063`, `EX-206` 대비 `+0.055`, `EX-201` 대비 `+0.016`. 실패 기술률 `5.72%`, `foul-play p50 7.163s`, 뷰어 `exports/battle_viewers/ex217/index.html`. `EP-245` 완료(`Completed`).
