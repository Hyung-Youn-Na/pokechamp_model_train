# D-224 — 배치 B 병행 실행: EX-223 방식 A v2 공식 래더(EX-224) + 정화 교사 방식 C-1(EX-225) → 프롬프트 도구 주입 방식 B(EX-226) DDP 자동 연쇄

- 상태: Accepted
- 결정일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-248](../plans/EP-248-batch-b-waya-v2-ladder-wayc1-clean-wayb.md)
- 관련 experiment: [EX-224](../experiments/EX-224-laya-waya-v2-vphiv3-2ply-ladder.md), [EX-225](../experiments/EX-225-laya-way-c1-clean-vphiv3-2ply-train.md), [EX-226](../experiments/EX-226-laya-way-b-tool-inject-train.md)
- 선행 결정: [D-223](D-223-vphi-v3-future-horizon-and-multiturn-search.md), [D-222](D-222-laya-way-c1-v14-walled-teacher50k.md), [D-221](D-221-laya-main-waya-mcts50k-vphi-v2.md), [D-214](D-214-laya-foulplay-primary-ladder-final.md), [D-191](D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 배경 및 근거

[EP-247](../plans/EP-247-vphi-v3-future-horizon-and-multiturn-search.md)의 [EX-221](../experiments/EX-221-laya-state-value-v3-future-train.md)($V_\phi$ v3) · [EX-222](../experiments/EX-222-multiturn-2ply-waya-v2-ab.md)(2-ply + `Way A v2`) · [EX-223](../experiments/EX-223-laya-waya-v2-vphiv3-2ply-vs-foulplay.md)(Blim 128 **53승 75패 `0.414` 역대 최고**, 실패 기술률 `4.95%`, `vphi_blunder_veto` 회복 편향 `34:3 → 6:7` 완전 해소)를 통해 상태가치망의 HP 회복 과대평가 오염이 실전 128경기에서 교정됨을 확인했다.

사용자 지시(2026-11-24 23:40Z, "배치 B로 진행해주세요.")에 따라, [DESIGN.md#laya-main-abc-roadmap](../DESIGN.md#laya-main-abc-roadmap)의 세 트랙(A·C·B)을 **물리 GPU 0·1 제약(GPU 2·3 미접촉)** 안에서 최대 효율로 동시/연쇄 실행한다.

## 결정

1. **트랙 1 — 공식 Showdown 래더 재검증 ([EX-224](../experiments/EX-224-laya-waya-v2-vphiv3-2ply-ladder.md), CPU 서빙 `0 GPU`)**:
   - `EX-223` 동일 설정(`EX-200` + `v13` + `walled_duel` + `EX-221 V_phi v3` + `2-ply Top-K` + `MCTS 50k` + `Way A v2`)을 `t61731415d7` 팀으로 공식 Showdown `gen9ou` 래더에 투입한다.
   - `EX-220` Run 6에서 발생한 Showdown `|badge|` 프로토콜 `NotImplementedError` 기권을 방지하기 위해 `bot.py` 인터셉터에 `|badge|` 필터 1건을 추가한다.
   - `EX-225`·`EX-226` 학습이 모두 완료되면 진행 중인 판을 기권 없이 마감하고 자동 종료한다(최대 14시간 안전 상한).
2. **공유 정화 데이터 생성 (~15분, `EX-218` `MCTS 50k` 재활용)**:
   - `EX-218`에 이미 계산된 `v14+walled_duel` 및 `Hard 28k` `MCTS 50k` 결과를 그대로 재활용하고, **`V_phi`만 `EX-221 V_phi v3 + 2-ply`로 재채점**(CPU 32워커 `nice 19` + GPU 1 `ValueScorerV3` `<300 MiB`)한다.
3. **트랙 2 — 방식 C-1 오염 제거판 ([EX-225](../experiments/EX-225-laya-way-c1-clean-vphiv3-2ply-train.md), 물리 GPU 0·1 DDP ~5.5시간)**:
   - 정화 교사(`Q_teacher = 0.45*Q_mcts50k_adj + 0.55*Q_vphi3_2ply` + `Way A v2` 고HP 회복/`Protect` 승격 가드)로 `datasets/generated/laya-v14w-c1v3/v1/`을 구축하고, DDP 학습 전 `hard_train.jsonl`의 구간별 HP 회복률 정화 검증을 자동 기록한다.
   - `EX-196` 출발점에서 물리 GPU 0·1 DDP 1에폭 학습 → 물리 GPU 0 오프라인 평가(일반 2k + Hard 3k + `walled` + 테라 + HP 구간별 회복률).
4. **트랙 3 — 방식 B 프롬프트 도구 주입 ([EX-226](../experiments/EX-226-laya-way-b-tool-inject-train.md), `EX-225` 완료 직후 자동 연쇄, 물리 GPU 0·1 DDP ~5.5시간)**:
   - `v14+walled_duel` 입력 끝에 상대 격차 기반 **`eval: mcts ... || vphi ...`** 한 줄을 주입해 Laya가 **100% 단독 최종 결정권자**로 도구 수치와 보드 문맥을 종합하도록 학습한다.
   - **지름길 붕괴 방지**: (a) `hard_train`/`general_train`의 **`35%` Tool Dropout** + `150k` 인간 앵커(`100%` 무도구)로 도구 없는 보드 독해력 유지, (b) 비블런더 턴(`gap < 0.030`, 비`walled`/비`absorb`)에서는 인간 프로 정답을 보존·혼합하고 명백한 전술 블런더에서만 교사 타깃을 적용한다.
   - GPU 0 오프라인 평가에서 **도구 포함(`with_eval`)**과 **도구 생략(`no_eval`, Tool Dropout 강건성)**을 모두 측정한다.

## 판정 기준

[D-191](D-191-no-offline-battle-gate.md)에 따라 오프라인 지표와 래더/배틀 지표는 보고 전용이며, `EX-225`·`EX-226` 완료 후 Blim 128 배틀 비교 진행은 사용자 확인을 받는다.
