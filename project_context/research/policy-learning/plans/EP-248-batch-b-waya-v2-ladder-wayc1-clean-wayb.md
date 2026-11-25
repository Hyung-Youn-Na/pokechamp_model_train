# EP-248 — 배치 B: EX-223 방식 A v2 공식 래더 병행 + 정화 방식 C-1 → 방식 B GPU 0·1 DDP 자동 연쇄

- 상태: Completed
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-24 23:40Z, "배치 B로 진행해주세요." — 공식 Showdown 래더 CPU 병행 + GPU 0·1 DDP로 정화 C-1 완료 후 방식 B 자동 연쇄 실행), [D-224](../decisions/D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md), [D-223](../decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md), [D-191](../decisions/D-191-no-offline-battle-gate.md). 래더 트랙(`EX-224`)만 공식 Showdown 서버(`sim3.psim.us`)에 접속하며 학습 트랙(`EX-225`·`EX-226`)은 외부 호출이 없다.
- 관련 contract / decision / experiment: [D-224](../decisions/D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md), [EX-224](../experiments/EX-224-laya-waya-v2-vphiv3-2ply-ladder.md), [EX-225](../experiments/EX-225-laya-way-c1-clean-vphiv3-2ply-train.md), [EX-226](../experiments/EX-226-laya-way-b-tool-inject-train.md)
- 겹치는 등록 plan:
  - [EP-247](EP-247-vphi-v3-future-horizon-and-multiturn-search.md)(Completed): `EX-221` 체크포인트와 `way_a_v2.py`·`search_multiturn.py`를 읽기 전용으로 사용.
  - [EP-246](EP-246-laya-way-c1-v14-walled-teacher50k-distill.md)(Paused): `EX-218`의 `v14w_*_base.jsonl`, `infer-hard.jsonl`, `search50k/`를 읽기 전용 입력으로 재활용하며 기존 `EX-218` 산출물은 수정하지 않는다.
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit: `research/model-training`, `a80cb51` 위
- 작업 checkout과 interpreter/launcher: `/workspace`, laya venv, foul-play venv(`PYTHONHASHSEED=0`), `scripts/laya-ladder-ex224`, `scripts/laya-batch-b-ep248`
- 새 산출물:
  - `EX-224`: `scripts/laya-ladder-ex224`, `exports/laya-play/runtime/logs/ladder-loop-ex224.log`, `exports/laya-play/games/2026112*-laya-waya-v2-*`
  - `EX-225`: `integration/laya_v14/{data_way_c1_v3.py,train_way_c1_v3.py}`, `datasets/generated/laya-v14w-c1v3/v1/`, `runs/model-training/EX-225/`
  - `EX-226`: `integration/laya_v14/{data_way_b.py,train_way_b.py,tests/test_way_b_and_c1v3.py}`, `datasets/generated/laya-v14w-wayb/v1/`, `runs/model-training/EX-226/`

## 범위와 불변 조건

- **보존**: 동결 패키지 및 `EX-216`·`EX-217`·`EX-218`·`EX-221`·`EX-223` 기존 산출물과 봉인 자료는 수정하지 않는다.
- **GPU 격리**: **물리 GPU 0(`GPU-4f27dd5a-...`)·GPU 1(`GPU-c7e2d577-...`)만 사용**한다. GPU 2·3은 일절 점유하지 않는다. `EX-224` 래더는 **CPU 전용(`CUDA_VISIBLE_DEVICES=''`)**으로 실행한다.
- **메모리·공정성**: 데이터·학습 단계는 `mem-guard` (`40~55 GB`) 아래에서 실행하고, 래더 CPU 서빙(`nice 10, OMP=4, --workers 2`)과 2-ply 재채점(`nice 19, 32w`)이 서로 방해하지 않도록 격리한다.
- **기권 방지**: `EX-224`는 `EX-226` 완료 감지 시 진행 중인 판 경계에서만 종료하며, `bot.py`에 `|badge|` 프로토콜 방어를 적용한다.

## 완료 기준

- [x] D-224·EP-248·EX-224·EX-225·EX-226 등록 및 catalog 동기화
- [x] `data_way_c1_v3.py`·`train_way_c1_v3.py`·`data_way_b.py`·`train_way_b.py`·`matchup_eval.py` 및 단위 테스트 47/47 통과
- [x] (`EX-224`·병행 래더) 공식 Showdown CPU 래더 무몰수 완료 (`EX-224` 9판 `3W-6L` → `EX-200 calc-duel-free` 50판 `26W-24L` 최고 `1566` → `EX-225 calc-duel-free` 58판 `31W-27L` `1398→1521` `+123`, 최고 `1557`, 1,901턴 에러 0·회복 override `10:11` 중립)
- [x] (`EX-225`) `EX-221 V_phi v3 + 2-ply` 28k 재채점 + 정화 교사 회복률 검증 → GPU 0·1 DDP 1에폭 학습 → GPU 0 오프라인 평가 완료 (`Hard gold_kl 0.3587`, `match_gold 55.70%`, `walled 81.08%`, Tera `A 97.10% / B 95.99%`)
- [x] (`EX-226`) `EX-225` 완료 직후 자동 진입 → `calc-duel-free` + `MCTS50k/V_phi v3` 5단계 `matchup:` + `eval:` + 35% Tool Dropout + 인간 앵커 보존 → GPU 0·1 DDP 1에폭 학습 → GPU 0 오프라인 평가 완료 (`with_eval`: Hard `gold_kl 0.1174`·`match_gold 83.23%`·`changed 81.35%`·`walled 89.86%`; `no_eval`: Hard `match_human 45.97%`·Gen `58.35%` 지름길 붕괴 0; Tera `A 97.24% / B 96.31%`)

## 진행

- 2026-11-24T23:41Z — 사용자 배치 B 승인으로 D-224·EP-248·EX-224·EX-225·EX-226 등록 및 구현·실행 착수.
- 2026-11-25T13:58Z — 배치 B 전체 트랙(`EX-224`·`EX-225`·`EX-226` + `EX-225` 58판 CPU 병행 래더) 무결 완료, 물리 GPU 0·1 전부 유휴 반환(`0 MiB`). 후속 Blim 128 배틀 평가(Way C-1 Clean vs Way B) 사용자 지시 대기.
