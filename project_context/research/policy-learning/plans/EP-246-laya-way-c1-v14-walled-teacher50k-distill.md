# EP-246 — 방식 C-1: v14+walled_duel 입력 및 Hard-Example MCTS 50k + EX-216 V_phi v2 교사 증류 학습 (GPU 0·1 전용)

- 상태: Paused
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-24 13:24 KST, "1. 으로 진행해주세요." — `EX-217`과 병행하여 C-1 데이터·50k 교사 생성 완료 후 `EX-217` 종료 즉시 GPU 0·1 DDP 1에폭 학습 자동 진입), [D-222](../decisions/D-222-laya-way-c1-v14-walled-teacher50k.md), [D-221](../decisions/D-221-laya-main-waya-mcts50k-vphi-v2.md), [D-191](../decisions/D-191-no-offline-battle-gate.md). 외부 호출은 없다.
- 관련 contract / decision / experiment: [C-047](../../../CONTRACTS.md#c-047-viewer-export), [D-222](../decisions/D-222-laya-way-c1-v14-walled-teacher50k.md), [EX-218](../experiments/EX-218-laya-way-c1-v14-walled-teacher50k-train.md), [EX-219](../experiments/EX-219-laya-way-c1-vs-foulplay-unlimited.md)
- 겹치는 등록 plan:
  - [EP-245](EP-245-laya-main-blunder-veto-mcts50k-vphi-v2.md)(Active): `EX-217`이 물리 GPU 0에서 Blim 128 실행 중. C-1 데이터·교사 생성은 CPU(`nice 19`)와 **물리 GPU 1 전용**으로 격리해 병행하며, GPU 0·1 DDP 학습은 `EX-217`이 GPU 0을 반환한 뒤에만 시작한다.
  - [EP-244](EP-244-laya-search-2bv2-and-v14-training.md)(Paused): `datasets/generated/laya-v14-mcts5k-q/v1/`는 읽기 전용 입력으로 보존하고, 새 출력은 `datasets/generated/laya-v14w-c1/v1/`에 작성한다.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit: `research/model-training`, `a80cb51` 위
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv(`.tools/laya-0.4.13/worktrees/pokemon-training/.venv/bin/python`), foul-play venv(`.tools/foul-play/.venv`, `PYTHONHASHSEED=0`), `scripts/laya-way-c1-ep246`
- 새 산출물:
  - 코드: `integration/laya_v14/{data_way_c1.py,train_way_c1.py,tests/test_way_c1.py}`, `scripts/laya-way-c1-ep246`
  - 자료: `datasets/generated/laya-v14w-c1/v1/` (`hard_train.jsonl`, `general_train.jsonl`, `hard_heldout.jsonl`, `heldout.jsonl`, `anchor/`, `foe-anchor.jsonl`, `manifest.json`)
  - 실행 산출물: `runs/model-training/EX-218/{checkpoints/selected,validation-curve.jsonl,selection.json,evaluation/summary.json}`

## 범위와 불변 조건

- **보존**: 동결 패키지, `EX-209`/`EX-213`/`EX-216` 기존 산출물과 `EX-217` 실행 중 파일은 수정하지 않는다.
- **GPU 격리**: **물리 GPU 0(`GPU-4f27dd5a-...`)·GPU 1(`GPU-c7e2d577-...`)만 사용**한다. GPU 2·3은 일절 점유하지 않는다. 준비 단계(추론·$V_\phi$ v2 채점)는 **GPU 1 단독**, 본 DDP 학습은 `EX-217` 종료·GPU 0 유휴(`<100 MiB`) 확인 후 **GPU 0·1**로 실행한다.
- **CPU 공정성**: `EX-217`의 `foul-play` 탐색(`p50 ~7.1s`)을 방해하지 않도록 모든 CPU 워커는 `nice -n 19` · `≤28워커` · `mem-guard` 아래에서 실행한다.
- **누수 통제**: `EX-209`의 2,200 train / 335 held-out 게임 분할과 Blim 64팀 제외를 100% 계승한다.

## 완료 기준

- [x] D-222·EP-246·EX-218·EX-219 등록 및 catalog 동기화
- [x] `data_way_c1.py`·`train_way_c1.py`·`test_way_c1.py` 구현 및 단위 테스트 통과 (`4/4`)
- [x] (`EX-217` 병행) `v14+walled_duel` 갱신(`3,400`행) + Hard-Example `28k`턴(`25k` train / `3k` held-out) `MCTS 50k + EX-216 V_phi v2` 교사 타깃 생성 완료
- [ ] (`EX-217` 종료 후 자동 진입 → **조기 중단**) `EX-218` 물리 GPU 0·1 DDP 1에폭 학습 `step 7,500 / 36,419`에서 사용자 지시로 조기 종료(`Stopped`). 사유: `EX-216` $V_\phi$ v2(1-ply) + `MCTS 50k` 결합 교사의 중·저HP 회복기 과대평가 오염(`40–69% HP` 교사 `45.2%` vs 인간 `27.7%`, `<40% HP` 교사 `40.4%` vs 인간 `28.1%`).

## 진행

- 2026-11-24T04:26Z — 사용자 승인으로 D-222·EP-246·EX-218·EX-219 등록. `data_way_c1.py`·`train_way_c1.py` 구현 및 `EX-217` 병행 준비 단계 착수.
- 2026-11-24T06:56Z — `v14+walled_duel`·Hard `25k+3k` 교사 타깃 생성 완료, `EX-217` 종료 후 GPU 0·1 DDP 학습 자동 진입.
- 2026-11-24T08:23Z — [EX-220](../experiments/EX-220-laya-waya-mcts50k-ladder.md) 실전 진단에서 `EX-216` $V_\phi$ v2 + `MCTS 50k`의 HP 회복 과대평가 편향 및 `EX-218` `hard_train.jsonl` 오염 확인. 사용자 지시로 `EX-218` DDP(`step 7,500/36,419`) 조기 종료(`Stopped`), `EP-246` 일시 정지(`Paused`), 물리 GPU 0·1 유휴 반환. 후속으로 미래 영향력 반영 가치함수($V_\phi$ v3) / 다수 턴 탐색 보강 후 새 계획으로 재설계 예정.
