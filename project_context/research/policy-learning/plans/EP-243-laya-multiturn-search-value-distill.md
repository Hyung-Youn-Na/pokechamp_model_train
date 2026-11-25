# EP-243 — 다중턴 온라인 탐색(2-A)·신경망 상태가치(2-B)·경량 MCTS-Q 재정렬 학습(1-B) (GPU 0·1 전용)

- 상태: Active
- 생성일: 2026-11-23
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-23 대화: GPU 2·3 타 프로젝트 배정으로 **GPU 0·1 전용**, "1. 먼저 진행해주세요. 2. 2-B도 포함해주세요. 3. 1-B로 해주시고 1-A는 일단 보류 해주세요."), [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-218](../decisions/D-218-laya-v13-input-bugfixes.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md). 2-A 구현·오프라인 검증 → EX-205 종료 후 EX-206(2-A Blim 128) → EX-207(2-B Value Head 학습) → EX-208(2-B Blim 128) → EX-209(1-B MCTS-5k Q 타깃·GPU 0·1 DDP 학습) → EX-210(1-B Blim 128) 순으로 진행한다. 외부 호출은 없다.
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [EX-205](../experiments/EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md), [EX-206](../experiments/EX-206-laya-search-2a-vs-foulplay-unlimited.md), [EX-207](../experiments/EX-207-laya-state-value-2b-train.md), [EX-208](../experiments/EX-208-laya-search-2b-vs-foulplay-unlimited.md), [EX-209](../experiments/EX-209-laya-mcts5k-q-rerank-1b-train.md), [EX-210](../experiments/EX-210-laya-mcts5k-q-rerank-1b-vs-foulplay-unlimited.md), [EX-211](../experiments/EX-211-laya-search2b-ladder.md)
- 겹치는 등록 plan:
  - [EP-241](EP-241-laya-v13-zeroshot-vs-foulplay.md)(Active, `EX-205` 실행 중): `EX-205`는 CPU 포트 `8100-8103`을 사용하며 완료 전까지 `laya_v13/{render_v13,serve_v13,battle_v13}.py`를 일절 수정하지 않고, 본 계획의 Blim 배틀·대량 CPU 타깃 작업은 `EX-205` 종료 뒤 시작한다.
  - [EP-240](EP-240-laya-v13-input-bugfixes.md)·[EP-242](EP-242-laya-lead-matchup-2b.md)(Completed): `render_v13`을 읽기/import 전용으로 재사용한다.
  - [EP-236](EP-236-laya-v11rtc-foulplay-distill-rl.md)(Paused): `laya_distill.data_distill.{choice_map,restrict}`를 import 전용으로 재사용한다.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit·미커밋 변경: `research/model-training`, `ee13b70`(EP-234~242 미커밋 변경 위)
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(`.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python`), foul-play venv(`.tools/foul-play/.venv`, `PYTHONHASHSEED=0`), `scripts/laya-search-battle-ep243`
- 새 산출물:
  - 코드: `integration/laya_search/`(`search_core.py`, `search_worker.py`, `serve_search.py`, `battle_search.py`, `value_model.py`, `data_value_2b.py`, `train_value_2b.py`, `data_mcts_1b.py`, `train_mcts_1b.py`, `tests/`), `scripts/laya-search-battle-ep243`
  - 자료: `datasets/generated/laya-state-value/v1/`(EX-207), `datasets/generated/laya-mcts5k-q/v1/`(EX-209)
  - 실행 산출물: `runs/model-training/EX-206~210`, 뷰어 `exports/battle_viewers/ex206`, `ex208`, `ex210`
- 참조 원자료(읽기 전용): `runs/model-training/EX-200/checkpoints/selected`, `runs/model-training/EX-205`(완료 후 기준선), `runs/model-training/EX-201`, `runs/model-training/EX-174`, `datasets/generated/laya-compact-imitation/v12-fresh/`, 리플레이 원자료, foul-play 봉인 자료

## 목표와 맥락

1턴 시야와 `evaluate.rs` 정적 가치 편향을 단계적으로 극복한다.

1. **2-A (`EX-206`)**: 재학습 없이 `EX-200` + `v13` GPU 0 서빙에 `poke-engine` MCTS(`5,000 iters`, `turn_action`·`forced_switch` 합법 수 전체) + KL-정규화 사전확률 융합($\lambda=0.03$)을 붙여 다중턴 수읽기 단독 효과를 Blim 128경기에서 검증한다.
2. **2-B (`EX-207` → `EX-208`)**: 실제 리플레이 승패로 `poke_engine.State` 신경망 가치 함수 $V_\phi(\text{State}) \in [0, 1]$을 학습하고(GPU 0·1), `q`-가중 1~2플라이 리프 평가 및 2-A 탐색과 결합해 `evaluate.rs` 편향(`USED_TERA=-75`, `Court Change` 자살) 교정 효과를 검증한다.
3. **1-B (`EX-209` → `EX-210`)**: `v13` 입력 + 경량 MCTS(`5,000 iters`) 루트 $Q$ 기반 후보 재정렬 타깃을 생성(CPU 48~64워커)하고 GPU 0·1 DDP로 단일 forward 모델을 학습·평가한다(`1-A`는 보류).

## 범위와 불변 조건

- **포함**: `integration/laya_search/`, `scripts/laya-search-battle-ep243`, `EX-206~210` 자료·학습·배틀·보고·뷰어·봉인, 기록.
- **보존**: `laya_imitation`·`laya_threat`·`laya_v10`·`laya_v11`·`laya_v12`·`laya_v13/{render_v13,serve_v13,battle_v13}.py`·`laya_value`·`laya_foe`·`laya_fp1`·`laya_regret`·`laya_distill`·`foulplay`·`.tools/foul-play/src` 및 기존 자료·봉인은 바이트 단위로 유지한다.
- **GPU 격리**: **물리 GPU 0(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`)·GPU 1(`GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`)만 사용**한다. GPU 2·3은 타 프로젝트 전용으로 일절 점유하지 않는다.
- **CPU / RAM**: 대량 CPU 작업은 48~64워커, `nice 19`, `mem-guard ≤ 50~60 GB`. 시간 기반 foul-play Blim 128경기(`EX-205`, `EX-206`, `EX-208`, `EX-210`)와 동시 실행하지 않는다.
- **분리**: Blim 평가 64팀(6종 집합 기준)과 held-out 경기는 `EX-207`·`EX-209` 학습 데이터에서 엄격히 제외한다.
- **외부 호출**: 없다.

## 완료 기준

- [x] D-219·EP-243·EX-206~210 등록, catalog build/check
- [x] **Phase 1 (2-A 구현·오프라인 검증)**: `integration/laya_search/{search_core,search_worker,serve_search,battle_search}.py`·실행기·단위검사 및 `EX-203` 1500+ 패배 핵심 턴 오프라인 검증 완료
- [x] **Phase 2 (2-A 배틀)**: `EX-205` 종료 후 `EX-206` mock 2/2 → prepare → execute 128 → export(보고·뷰어·봉인)
- [x] **Phase 3 (2-B 상태가치 + 탐색)**: `EX-207`(데이터 추출·GPU 0·1 학습·held-out AUC/Brier/EX-203 편향 점검) → `EX-208` Blim 128 + export
- [x] **Phase 4 (1-B 오프라인 MCTS-5k Q 재정렬)**: `EX-209`(GPU 0·1 `infer` + CPU MCTS-5k Q 타깃 + GPU 0·1 DDP 학습) → `EX-210` Blim 128 + export (96/128 정상 완료, `fp-b20-s1-a` 499턴 `auto-tie` 파서 한계로 `phase_halt` · 판정 보류 봉인)
- [ ] 전체 결과를 EX-206~210·EP-243·STATUS·catalog에 기록하고 보고(뷰어 링크 포함, C-047)

## 절차

1. (`EX-205` 실행 중) 2-A 모듈(`integration/laya_search/`) 구현, 단위 테스트(`test_search_core.py`, `test_serve_search.py`), `EX-203` 1500+ 핵심 턴 오프라인 검증 및 GPU 0 서빙 smoke 확인.
2. (`EX-205` 완료 후) `scripts/laya-search-battle-ep243 EX-206`으로 2-A mock → prepare → execute 128 → export 실행.
3. 2-B(`EX-207` → `EX-208`)와 1-B(`EX-209` → `EX-210`)를 GPU 0·1 및 비충돌 CPU 일정에 맞춰 순차 실행하고 각 단계 결과를 보고한다.

## 차단·중단

[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다. GPU 2·3 침범 징후, mock 실패·감사 불일치, `v13` 동결 해시 변경, `phase_error`, `mem-guard` 종료 시 즉시 멈추고 보고한다. foul-play 엔진 panic은 `actor_unlimited`가 해당 경기만 `incomplete`(`engine_panic`)로 격리한다.

## 진행

- 2026-11-23 — 사용자 지시(GPU 0·1 전용, 2-A 우선 → 2-B 포함 → 1-B 채택·1-A 보류)로 D-219·EP-243·EX-206~210 등록. Phase 1(2-A 구현 및 오프라인 검증) 시작.
- 2026-11-23 — Phase 1 완료: `integration/laya_search/{search_core,search_worker,serve_search,battle_search}.py`·`scripts/laya-search-battle-ep243` 구현. 단위검사 `test_search_core` 8/8 + `laya_v13` 19/19 (총 27/27) 통과. 실제 물리 GPU 0 단독(`{0: 1982 MiB, 1: 0, 2: 0, 3: 0}`) 라이브 HTTP E2E(`gen9ou-2718019409` 0~35턴 41결정) 통과: p50 `482ms`, `forced_switch` 4회 탐색(`unmapped=0.0`), 6회 override, 35턴 3v1 Kingambit 오판(`switch:2` 0.510) → `move:icebeam:normal`(delta `+0.0354`, `worker_s=34.4ms`, 오류 0) 교정 확인. `EX-205` 동결 해시 무변경 확인. `EX-205` 종료 즉시 `EX-206` mock → prepare → execute 128 실행 예정.
- 2026-11-23 — Phase 3(2-B) 코드 선행 구현·검증 완료: `integration/laya_search/{featurize,value_model,data_value_2b,train_value_2b,search_2b}.py`·`scripts/laya-value-2b-ep243` 및 `serve_search`/`battle_search`(`EX-208`) 연결 완료. 단위검사 `test_search_core`+`test_value_2b` 14/14(정확한 제로섬 반대칭성 `V(swap(s)) == 1 - V(s)` 및 Blim 64팀 제외 검증 포함) + `laya_v13` 19/19(총 33/33) 통과. 실제 `v12-fresh` 3경기 추출(164행, 오류 0), `EX-203` T8 `expand_turn1_features`(오류 0), 물리 GPU 0 `StateValueNet`(504,945 params, VRAM `11.4 MiB`, batch 128 추론 `1.24 ms`) 및 마이크로 학습·온도 보정 통과.
- 2026-11-23 — Phase 4(1-B) 코드 선행 구현·검증 완료: `integration/laya_search/{data_mcts_1b,train_mcts_1b,battle_1b}.py`·`scripts/laya-mcts-1b-ep243`·`test_mcts_1b.py` 구현(물리 GPU 0·1 전용 가드, `EX-196` 출발 MCTS-5k 루트 Q KL-정규화 후보 재정렬 + 전술 구제 승격, `turn_action`·`forced_switch` 포함, Blim 64팀 제외). 단위검사 전체 통과 및 실제 `v12-fresh` 1경기 `mcts_job` 스모크 통과.
- 2026-11-23 — 사용자 지시("1.을 진행해주세요.")로 `EX-205` 잔여 실행과 병렬로 `EX-209 infer` 단계(물리 GPU 0·1 전용, `mem-guard` 20×2, GPU 2·3 미사용) 선행 실행 시작.
- 2026-11-23T02:46Z — `EX-209 infer` 완료(약 33분): rank 0(GPU 0) `78,974`행(`40.2 rows/s`) + rank 1(GPU 1) `79,060`행(`39.9 rows/s`) = 총 `158,034`행(`2,200 train + 335 heldout` 경기, 오류 0), GPU 0·1 자원 반환 완료. 후속 스크립트 3종에 `OMP_NUM_THREADS=4 MKL_NUM_THREADS=4` 반영.
- 2026-11-23T05:15Z — 사용자 지시("2. 으로 진행해주세요.")로 `EX-206`(`v13` + GPU 0 단독 서빙 + MCTS 5k 사전확률 융합) mock 2/2 통과(`fp-b24-s2-a` 22턴 패, `fp-b24-s2-b` 54턴 승, 감사 통과 2/2, 오류 0) 및 prepare 완료. 본 실행(`execute` 128 → `export`) 시작.
- 2026-11-23T05:20Z — 사용자 지시("병행해주세요.") 및 실시간 자원 확인(CPU idle 72%, 가용 RAM 86 GB, GPU 1 유휴) 후 `EX-207`(`16워커 nice 19, mem-guard 25` 추출 → 빌드 → **물리 GPU 1 전용** 학습) `EX-206`과 병행 시작.
- 2026-11-23T07:42Z — `EX-207` 완료: 추출 356,514행(Blim 291경기 제외) → 1차 지문 과적합(`AUC 0.6446`) 교정 후 최종 `clean_deepsets_v2`(52k params, GPU 1 단독)에서 held-out 304경기 **`AUC 0.7389 · LogLoss 0.5967 · ECE 0.0258`**로 온도보정 `evaluate.rs`(`AUC 0.7235 · LogLoss 0.6147 · ECE 0.0319`)를 전 구간 상회. `EX-207/checkpoints/selected` 저장 완료(`EX-208` 투입 준비 완료).
- 2026-11-23T08:43Z — `EX-206`(2-A Blim 128) 완료·export·봉인 완료: **128/128 정상 완료**(`43승 0무 85패, 0.336 [0.258, 0.406]`), 같은 슬롯 EX-205 대비 `+0.016 [-0.064, +0.094]`, EX-201 대비 `-0.039`, EX-174 대비 `0.000 [-0.095, +0.095]`. GPU 0 결정 지연 `p50 0.669s`, 테라 사용 71경기(T1–9 14회)·공격 팀 `0.273→0.353` 회복했으나 실패 기술률 `4.26%→5.71%` 상승. 뷰어 `exports/battle_viewers/ex206/index.html` 생성 완료.
- 2026-11-23T11:22Z — 사용자 지시("3.으로 진행해주세요.")로 **`EX-208`**(2-B `V_phi` 결합 Blim 128, GPU 0 단독, 포트 `8100-8103`, `mem-guard 40`) mock 검증과 **`EX-209 mcts → targets → prepare`**(1-B MCTS 5k 루트 Q 타깃, CPU `16워커 nice 19`, `mem-guard 30`) 병행 시작.
- 2026-11-23T11:31Z — `EX-208` mock 2/2 통과(`fp-b24-s2-a` 59턴 패, `fp-b24-s2-b` 35턴 승, 감사 통과 2/2, `searched=102, with_vphi=94, avg_vphi_states=434.4, overrides=16.7%, unmapped=0.0, errs=0, p50=1.110s`) 및 prepare 완료(128슬롯 동결). `EX-208 execute 128 → export` 백그라운드 시작(`EX-208-lane.log` 외부 기록으로 봉인 무결성 유지). 병행 중인 `EX-209 mcts`는 `300/2,535`경기(오류 0, `eta ~57분`) 진행 중.
- 2026-11-23T12:30Z — **`EX-209 mcts → targets → prepare` 완료**(CPU `16워커 nice 19`, 67분 소요): 2,535/2,535경기 146,147행(오류 3건) → 골드 타깃 **145,679행**(`train` 125,481행·2,200경기 / `heldout` 20,198행·335경기, `gold_argmax_changed` 40,195건 `27.6%`, `forced_switch` 15,252건 `10.5%`, `human_is_laya_argmax` 58.1% / `human_is_gold_argmax` 53.4%), 앵커 `anchor/train.jsonl` 150,000행 + `foe-anchor.jsonl` 100,000행 준비 완료(`datasets/generated/laya-mcts5k-q/v1/`). `EX-208`(현재 `39/128`, `16W-23L`, GPU 0 점유) 종료 즉시 GPU 0·1 DDP `EX-209 train` 착수 예정.
- 2026-11-23T15:03Z — **`EX-208`(2-B `V_phi` 결합 Blim 128) 완료·export·봉인 완료**: **128/128 정상 완료**(감사 128/128, `verify_seal` 2,944파일 `[]`), **52승 0무 76패 · 평균 `0.406 [0.312, 0.500]`**(역대 Blim 128 최고 점수). 같은 슬롯 대비 EX-206(2-A) **`+0.0703 [-0.0312, +0.1719]`**(27나음/18나쁨), EX-205 **`+0.0866 [-0.0156, +0.184]`**(28/17), EX-201 **`+0.0312 [-0.0547, +0.1172]`**(26/22), EX-174 **`+0.0709 [-0.047, +0.183]`**(30/21). GPU 0 `p50 1.069s`, `with_vphi 6,410/6,853 (93.5%)`, `overrides 10.6%`, `offense 0.471`, 뷰어 `exports/battle_viewers/ex208/index.html` 생성 완료.
- 2026-11-23T15:06Z — GPU 0·1 유휴 확인 후 **`EX-209 train`**(1-B MCTS-5k Q 재정렬, 물리 GPU 0·1 DDP 전용, `mem-guard 55`) 백그라운드 시작(`EX-209/train-lane.log`).
- 2026-11-23T21:28Z — **`EX-209` 완료**: 1에폭 34,857스텝(5.8시간, GPU 0·1 DDP `22.9 GiB/GPU`) 완료, `point-4` 최적(`val NLL 1.3208`, 보정 `T=1.063`, `1.3094`). held-out MCTS-5k Q 2,000행에서 **`gold_CE 1.0751` / `gold top-1 80.15%` / 변경 턴 `38.92%` / `forced_switch 67.13%`**로 `EX-200`(`1.1238` / `77.35%` / `30.44%` / `62.04%`)·`EX-196`(`1.1536` / `74.05%` / `0%` / `61.57%`)을 크게 상회하고 테라 지식 `heldout-A 96.33% · B 95.94%` 보존. (`selection.json` 이름 충돌은 `game_selection.json`으로 이관·수정 완료.)
- 2026-11-23T21:29Z — **`EX-210`**(1-B 단일 forward `v13` GPU 0 서빙 Blim 128) mock 2/2 통과(`audit=true`, `foulplay p50 7.276s`) 및 prepare 완료(128슬롯 동결). `EX-210 execute 128 → export` 백그라운드 시작(`EX-210-lane.log` 외부 기록).
- 2026-11-23T23:42Z — 사용자 지시("EX208 실험 모델의 레더 대전을 KST 13:00 까지 수행해주세요.")로 [EX-211](../experiments/EX-211-laya-search2b-ladder.md) 등록 및 `scripts/laya-ladder-ex211`(물리 GPU 1 전용, `laya-search2b` = `EX-200` + `v13` + MCTS 5k + `EX-207` $V_\phi$, 팀 `t95bfb45561`, `2026-11-24 13:00 KST`까지) 착수. `laya-play/bot.py`에 `early_history + fp1` 동시 전달 및 `v13+search2b` 라벨 지원 반영.
- 2026-11-24T00:12Z — **`EX-210`(1-B 단일 forward Blim 128) 종료·export·봉인 완료**: `96/128` 정상 완료(`fp-b20-s1-a` 499턴에서 EX-205와 동일한 Showdown `auto-tie` 경고 클라이언트 오인으로 `phase_halt`, 감사 97/97, `verify_seal` 2,416파일 `[]`, 판정 보류). **33승 0무 63패 · 평균 `0.344 [0.231, 0.458]`**, 같은 슬롯(`n=96`) EX-205 대비 `+0.042`, EX-206(2-A) 대비 `+0.010`, EX-208(2-B) 대비 `-0.073`, EX-201 대비 `-0.042`. `balance 0.429` 강세 vs `offense 0.227` 취약, GPU 0 `p50 0.269s`, 뷰어 `exports/battle_viewers/ex210/index.html` 생성 완료. GPU 0 유휴 반환.
- 2026-11-24T00:15Z — 사용자 지시("일단 레더 대전을 종료해주세요.")로 **`EX-211`(EX-208 공식 래더)** 조기 종료(`Stopped`), 서빙·`serving.ready.json` 원복 및 GPU 1 유휴 반환. 8판 완료 **2승 6패**(`1517→1457`, `-60`, 상대 평균 `1541.0`, `with_vphi 92.0%`, `overrides 9.5%`, `errs 0`, `p50 0.910s`), `replays.md` 동기화 완료. 라이브 진단에서 (1) 2-B 융합 스케일 불일치(`Q_vphi` < `Q_mcts`+`prior`), (2) `foe_options` 관측 기술 `other` 누락, (3) `poke-engine v0.0.48`의 `Water Absorb` +25% 회복 명령 누락을 확인.

## 결과 및 증거

진행 중.
