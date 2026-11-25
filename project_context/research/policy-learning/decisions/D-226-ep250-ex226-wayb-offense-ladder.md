# D-226 — EP-250: EX-226 방식 B Offense 전용 공식 Showdown 래더 대전 (13:30 KST까지)

- 상태: Accepted
- 결정일: 2026-11-26
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-250](../plans/EP-250-ex226-wayb-offense-ladder.md)
- 관련 experiment: [EX-231](../experiments/EX-231-laya-ex226-wayb-offense-ladder.md)
- 선행 결정: [D-225](D-225-ep249-ex226-wayb-ex225-c1clean-blim128-ladder.md), [D-214](D-214-laya-foulplay-primary-ladder-final.md)
- 기준 연구선: `research/model-training`

## 배경 및 결정

[EP-249](../plans/EP-249-ex226-wayb-and-ex225-c1clean-blim128-and-ladder.md)에서 `EX-226` 방식 B가 Blim 128 `offense` 아키타입에서 **`0.588` (20승 14패, n=34)** 및 공식 래더 최초 `1600+` 돌파(`1522→1636`, 최고 `1648`)를 기록했다.

사용자 지시(2026-11-25 23:41Z / 2026-11-26 08:41 KST)에 따라 **`offense` 팀만 사용해 `EX-226` 동일 설정으로 `2026-11-26 13:30 KST`까지 공식 Showdown `gen9ou` 래더**를 진행한다:
- `teams.json`의 `offense` 라벨 6개 중 오분류 풀 막이 2팀(`td061dd6180`, `t71230b7e95`)은 기존 사용자 지시에 따라 제외하고 **순수 `offense` 4팀(`ta199a565dc`, `t04995ad0de`, `tef21addf17`, `t94a0e30d55`)만 순환**한다.
- 유휴 상태인 **물리 GPU 0 단독**(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, `--device cuda`, `--workers 4`)으로 서빙하며 GPU 1·2·3은 미접촉한다.
- `2026-11-26 13:30:00 KST` 도달 시 진행 중인 판이 끝난 직후 판 경계에서 무몰수 자동 종료하고 GPU 0을 유휴 반환한다.
