# D-225 — EP-249: EX-226(방식 B) · EX-225(방식 C-1 정화판) Blim 128 병렬 배틀 평가 및 EX-226 공식 래더 병행

- 상태: Accepted
- 결정일: 2026-11-25
- 책임자: Antigravity (Gemini)
- 관련 계획: [EP-249](../plans/EP-249-ex226-wayb-and-ex225-c1clean-blim128-and-ladder.md)
- 선행 결정: [D-224](D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md), [D-223](D-223-vphi-v3-future-horizon-and-multiturn-search.md), [D-214](D-214-laya-foulplay-primary-ladder-final.md), [D-191](D-191-no-offline-battle-gate.md)

## 배경 및 결정

[EP-248](../plans/EP-248-batch-b-waya-v2-ladder-wayc1-clean-wayb.md)에서 오프라인 정화·학습을 마친 `EX-225`(방식 C-1 정화판)와 `EX-226`(방식 B: `calc-duel-free` + 5단계 `matchup:` + `eval:` + 35% Tool Dropout + Human Anchor)의 **실전 강도를 `foul-play` Blim 128 동일 슬롯과 공식 Showdown 래더로 확정**한다(D-191).

사용자 승인(2026-11-25 15:01Z)에 따라 물리 **GPU 0·1 격리(GPU 2·3 완전 미접촉)** 및 포트 분리(`8100..8103` vs `8104..8107`) 하에 3개 트랙을 동시 병행한다:
1. **트랙 1 ([EX-227](../experiments/EX-227-laya-ex226-wayb-vs-foulplay-blim128.md), GPU 0 단독, 포트 `8100..8103`)**: `EX-226` 방식 B (`--v14 --way-b --two-ply --walled-duel --no-calc-duel --iterations 50000`, 외부 veto 수식 없이 **Laya 100% 단독 최종결정**) 대 시간 무제한 `foul-play` Blim 128 (`EX-223 0.414` 대비).
2. **트랙 2-A → 2-B (GPU 1 단독, 포트 `8104..8107` 순차 연쇄)**:
   - [EX-228](../experiments/EX-228-laya-ex225-c1clean-standalone-vs-foulplay-blim128.md): `EX-225` **단독 무탐색**(`--v14 --walled-duel --no-search`) Blim 128 (`EX-205 0.315` 대비 순수 증류 효과 측정).
   - [EX-229](../experiments/EX-229-laya-ex225-waya-v2-noduel-vs-foulplay-blim128.md): `EX-228` 봉인 직후 자동 진입 — `EX-225 + calc-duel-free + Way A v2 (MCTS 50k + EX-221 V_phi v3 2-ply + 5단계 matchup_eval)` Blim 128 (`EX-223 0.414` 대비 1:1 비교).
3. **트랙 3 ([EX-230](../experiments/EX-230-laya-ex226-wayb-ladder.md), CPU 전용 `0 GPU`)**: `EX-226` 방식 B (`laya-ex226-wayb`, `v14+wayb_noduel`) 공식 Showdown `gen9ou` 래더 (28팀 비스톨 로테이션, `EX-227`·`EX-229` 완료 봉인 시 판 경계 무몰수 자동 종료).
