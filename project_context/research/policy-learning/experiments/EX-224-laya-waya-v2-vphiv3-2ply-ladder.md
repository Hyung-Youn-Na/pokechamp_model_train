# EX-224 — EX-223 방식 A v2(V_phi v3 + 2-ply + MCTS 50k + 회복/Protect 가드레일, CPU 서빙) 공식 Showdown gen9ou 래더 대전

- 상태: Stopped
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-248](../plans/EP-248-batch-b-waya-v2-ladder-wayc1-clean-wayb.md)
- 관련 decision: [D-224](../decisions/D-224-batch-b-waya-v2-ladder-wayc1-clean-wayb.md), [D-223](../decisions/D-223-vphi-v3-future-horizon-and-multiturn-search.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md)
- 비교 대상: [EX-220](EX-220-laya-waya-mcts50k-ladder.md) (`Way A v1 + EX-216 V_phi v2`, `t61731415d7` 11판 5승 6패 `1448→1458`, 평균 상대 `1483.3`), [EX-215](EX-215-laya-search2bv2-ladder.md) (`2-B v2`, `t61731415d7` 8판 4승 4패 `1429→1446`)
- 기준 연구선: `research/model-training`

## 질문 및 목적

Blim 128에서 역대 최고점(`0.414`)과 HP 회복·`Protect` 편향 해소를 확인한 [EX-223](EX-223-laya-waya-v2-vphiv3-2ply-vs-foulplay.md) 설정을 공식 Showdown `gen9ou` 래더에 투입했을 때(CPU 서빙 `0 GPU`, `EX-225`·`EX-226` 학습과 병행), `EX-220`에서 관측된 고HP `Roost`·연속 `Protect` 루프가 실전 래더에서도 해소되며 전적·텔레메트리가 어떻게 나타나는가?

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 모델·탐색 | `EX-223` 동일 (`EX-200` + `v13` + `walled_duel` + `EX-221 V_phi v3` + `2-ply Top-K` + `MCTS 50,000` + `--way-a-v2`). 모델명 `laya-waya-v2`, 렌더러 라벨 `v13+waya_v2_2ply` |
| 팀·계정·방어 | Run 1~4: `t61731415d7` (`Spikestack`, `teams.json`), **Run 5~9(사용자 지시 전환): `teams.json` 32개 팀 아키타입 교차 로테이션(`TEAM=rotate`)**, 계정 `nhy_test1629`, `bot.py` `|badge|` 프로토콜 필터 적용 |
| 자원·종료 조건 | **CPU 서빙(`CUDA_VISIBLE_DEVICES=''`, `OMP=4, nice 10, --workers 2`)**, 사용자 요청에 따라 9번째 판 종료 후 `stop-ex224`로 무몰수 정상 종료 (`09:46:39 KST`), 로그 `exports/laya-play/runtime/logs/ladder-loop-ex224.log` |

## 결과 (2026-11-25, 9판 무몰수 완료, 보고 전용)

- **총 전적**: **9판 3승 6패** (`1458 → 1413`, 평균 상대 레이팅 `1481.6`, 1689~1722 상위권 상대 3판 포함). 크래시·`|badge|` 오류·몰수 **0건**, 서빙 에러 **0건**.
  - 고정 팀 `t61731415d7` (4판, `#690`~`#693`): **1승 3패** (`1458 → 1424`)
  - 32팀 로테이션 (5판, `#694`~`#698`): **2승 3패** (`1424 → 1413`)
- **회복·`Protect` 텔레메트리 (비리드 283턴)**:
  - Laya 원안 유지율 **`84.5%` (`239/283`)**, override 44건 (`forced_mcts_veto 12`, `duel_lose_vphi_veto 9`, `unanimous_veto 7`, `severe_mcts_veto 5`, `vphi_blunder_veto 4`, `walled_veto 4`, `endgame_veto 3`).
  - **전체 override INTO:AWAY `HEAL` = `0 : 1`** (`vphi_blunder_veto` INTO:AWAY `HEAL` = `0 : 1`) — `EX-220`의 탐색 주도 고HP 회복 강제 편향 완전 소멸.
  - **전체 override INTO:AWAY `Protect` = `1 : 2`**, **`walled_veto -> Protect` = `0`건**, **연속 `Protect` = `0`건**.
  - CPU 서빙 탐색 지연: `worker_seconds p50 = 1.64s`, `p95 = 2.49s`, `max = 3.04s`.

| # | 팀 (아키타입) | 결과 | 상대 (ELO) | 레이팅 변화 | 턴 | 리플레이 |
|---|---|---|---|---|---|---|
| 690 | `t61731415d7` (balance) | 패 | `nickgen6rbrlbot` (1689) | 1458 → 1450 (-8) | 36 | `gen9ou-2718997187` |
| 691 | `t61731415d7` (balance) | 승 | `theyubero` (1351) | 1450 → 1464 (+14) | 2 | `gen9ou-2718999402` |
| 692 | `t61731415d7` (balance) | 패 | `nickgen6rbrlbot` (1722) | 1464 → 1457 (-7) | 23 | `gen9ou-2719000773` |
| 693 | `t61731415d7` (balance) | 패 | `DUVBOT9_04` (1188) | 1457 → 1424 (-33) | 44 | `gen9ou-2719002732` |
| 694 | `t637fcf81c3` (balance) | 승 | `freedomafter20yrs` (1488) | 1424 → 1448 (+24) | 30 | `gen9ou-2719006239` |
| 695 | `ta199a565dc` (offense) | 패 | `claudestopher` (1712) | 1448 → 1441 (-7) | 25 | `gen9ou-2719008196` |
| 696 | `tbaa95137e3` (weather) | 승 | `popozao` (1299) | 1441 → 1453 (+12) | 18 | `gen9ou-2719010033` |
| 697 | `t70f22aee0a` (defense) | 패 | `skypiaisland` (1341) | 1453 → 1427 (-26) | 38 | `gen9ou-2719011900` |
| 698 | `tcd9f36174b` (balance) | 패 | `georgiebird2` (1544) | 1427 → 1413 (-14) | 35 | `gen9ou-2719015513` |
