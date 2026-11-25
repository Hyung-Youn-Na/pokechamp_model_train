# EP-249 — EX-226(방식 B) · EX-225(방식 C-1 정화판) Blim 128 병렬 배틀 평가 및 EX-226 공식 래더 병행

- 상태: Completed
- 생성일: 2026-11-25
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-25 15:01Z, 트랙 1 + 트랙 2-A→2-B 순차 연쇄 + 트랙 3 동시 병행 승인), [D-225](../decisions/D-225-ep249-ex226-wayb-ex225-c1clean-blim128-ladder.md), [D-224](../decisions/D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md), [D-191](../decisions/D-191-no-offline-battle-gate.md). 트랙 3(`EX-230`)만 공식 Showdown 서버(`sim3.psim.us`)에 접속하며 `EX-227`·`EX-228`·`EX-229`는 로컬 Showdown(`8100..8107`)으로 완결된다.
- 관련 contract / decision / experiment: [D-225](../decisions/D-225-ep249-ex226-wayb-ex225-c1clean-blim128-ladder.md), [EX-227](../experiments/EX-227-laya-ex226-wayb-vs-foulplay-blim128.md), [EX-228](../experiments/EX-228-laya-ex225-c1clean-standalone-vs-foulplay-blim128.md), [EX-229](../experiments/EX-229-laya-ex225-waya-v2-noduel-vs-foulplay-blim128.md), [EX-230](../experiments/EX-230-laya-ex226-wayb-ladder.md)
- 겹치는 등록 plan: [EP-248](EP-248-batch-b-waya-v2-ladder-wayc1-clean-wayb.md)(Completed, `EX-225`·`EX-226` 체크포인트를 읽기 전용 사용), [EP-247](EP-247-vphi-v3-future-horizon-and-multiturn-search.md)(Completed, `EX-221`·`EX-223` 참조).
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit: `research/model-training`, `a80cb51` 위
- 작업 checkout과 launcher: `/workspace`, `integration/laya_search/battle_ep249.py`, `scripts/laya-blim-ep249`, `scripts/laya-ladder-ex230`
- 새 산출물:
  - `EX-227`: `runs/model-training/EX-227/` (봉인), `exports/battle_viewers/ex227/index.html`
  - `EX-228`: `runs/model-training/EX-228/` (봉인), `exports/battle_viewers/ex228/index.html`
  - `EX-229`: `runs/model-training/EX-229/` (봉인), `exports/battle_viewers/ex229/index.html`
  - `EX-230`: `exports/laya-play/runtime/logs/ladder-loop-ex230-wayb.log`, `exports/laya-play/ladder/replays.md` (`ex226-wayb` · `v14+wayb_noduel`)

## 범위와 불변 조건

- **GPU·포트 격리**: `EX-227`은 **물리 GPU 0 단독** + 포트 `8100..8103`, `EX-228`→`EX-229`는 **물리 GPU 1 단독** + 포트 `8104..8107`, `EX-230`은 **CPU 전용(`0 GPU`)**. 물리 GPU 2·3은 절대 점유하지 않는다.
- **로그 격리**: 배틀 런 디렉터리 내부에 외부 로그를 쓰지 않고 `runs/model-training/EX-227.lane.log`, `EX-228-229.lane.log`에 기록한다.
- **동일 슬롯·봉인·뷰어**: Blim 128 전 경기 `mock → prepare → execute → export`, `verify_seal == []` 및 C-047 뷰어 생성까지 완결한다.

## 완료 기준

- [x] `serve_search.py` `--way-b` · `--no-search` 구현 및 단위 테스트 통과 (`48 passed`)
- [x] `EX-227` (`EX-226` Way B Blim 128, GPU 0) `128/128` 완료·봉인(`verify_seal == []`)·뷰어 생성 — **57승 71패 `0.445 [0.352, 0.539]` 역대 최고** (`EX-205` 대비 `+0.126 [+0.031, +0.228]`)
- [x] `EX-228` (`EX-225` 단독 무탐색 Blim 128, GPU 1) `128/128` 완료·봉인(`verify_seal == []`)·뷰어 생성 — **47승 81패 `0.367 [0.273, 0.461]`** (`EX-205` 대비 `+0.055 [-0.047, +0.164]`)
- [x] `EX-229` (`EX-225 + Way A v2 noduel` Blim 128, GPU 1) `80/128` `phase_halt` 판정 보류·봉인(`verify_seal == []`)·뷰어 생성 — **26승 54패 `0.325 [0.211, 0.438]`** (`EX-223` 대비 `-0.125 [-0.230, -0.014]`, `duel:` 학습-추론 불일치 확인)
- [x] `EX-230` (`EX-226` Way B 공식 래더, CPU) **66판 무몰수 정상 마감 (`33승 33패`, ELO `1522→1636` `+114`, 역대 최고 `1648`, 상대 평균 `1578.6`, 1600+ 상대 9승)**

## 진행

- 2026-11-25T15:02Z — 사용자 승인으로 D-225·EP-249·EX-227~230 등록 및 구현·기동 착수.
- 2026-11-25T18:48Z — `EX-228` `128/128` 완료·봉인 (`0.367`), `battle_ep249.py:177` `study.experiment` 수정 후 `EX-229` GPU 1 착수.
- 2026-11-25T20:22Z — `EX-227` `128/128` 완료·봉인 (**`0.445` 역대 최고**), GPU 0 유휴 반환.
- 2026-11-25T21:53Z — `EX-229` `80/128` `phase_halt` 판정 보류 봉인 (`0.325`), GPU 1 유휴 반환.
- 2026-11-25T23:29Z — `EX-230` 66판 무몰수 정상 마감 (`1522→1636`, 최고 `1648`). 물리 GPU 0·1·2·3 및 CPU 서빙 전 자원 유휴 반환(`0 MiB`), EP-249 완료.
