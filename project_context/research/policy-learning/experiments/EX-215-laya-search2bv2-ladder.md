# EX-215 — 2-B v2 탐색 개선(EX-212 동일 설정, CPU 서빙) 공식 Showdown gen9ou 래더 대전(2026-11-24 13:00 KST까지)

- 상태: Stopped
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-244](../plans/EP-244-laya-search-2bv2-and-v14-training.md)
- 관련 decision: [D-220](../decisions/D-220-laya-recovery-matchup-2bv2-and-v14.md), [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-211](EX-211-laya-search2b-ladder.md)(2-B v1, 8판 2승 6패, 1517→1457, 상대 평균 1541), [EX-203](EX-203-laya-engine-value-ladder.md)(EX-200 v12 단일 forward, 104판 53승 51패, 1332→1505)
- 기준 연구선: `research/model-training`

## 질문 및 목적

사용자 지시(2026-11-24 09:47 KST, "추가로 Track 1과 동일한 설정으로 레더 대전을 병행 진행할 수 있을지 확인해주세요... 일단 13:00까지 진행해주세요."): Track 1([EX-212](EX-212-laya-search-2bv2-vs-foulplay-unlimited.md))과 동일한 **2-B v2** 설정(`foe_options_clean` PP 수정·스케일 매칭 `alpha=0.65`·`duel: lose` 완화·`Taunt` 흡수 보정)을 **CPU 서빙**(`0 GPU`, `OMP_NUM_THREADS=4`, `nice 10`)으로 공식 Showdown gen9ou 래더에 투입해 `2026-11-24 13:00 KST`까지 성적 및 회복/흡수 대면 대응 변화를 측정한다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 모델·탐색 | `EX-212` 동일 (`EX-200` + `v13` + MCTS 5k + `EX-207` $V_\phi$ + `--v2`, `alpha=0.65`, `duel: lose` `lam=0.012`). 서빙 모델명 `laya-search2bv2`, 렌더러 라벨 `v13+search2bv2` |
| 팀·계정 | 1판(`09:49 KST`): `t95bfb45561`(`teams_blim.json`) → 사용자 지시(09:56 KST)로 판 경계에서 `laya-play` `smogon` 밸런스 팀 **`t61731415d7` (`Spikestack`: Gliscor / Gholdengo / Dragonite / Ting-Lu / Darkrai / Zamazenta, `teams.json`)**으로 교체, 계정 `nhy_test1629` |
| 서빙·자원 | **CPU 서빙**(`CUDA_VISIBLE_DEVICES=''`, `OMP_NUM_THREADS=4 MKL_NUM_THREADS=4`, `nice 10`, `--workers 2`), `EX-212`(CPU) 및 `EX-213`(v14 데이터 → GPU 0·1 DDP)과 병행(GPU 2·3 미사용) |
| 분량·기록 | `2026-11-24 13:00 KST`(`2026-11-24T04:00:00Z`)까지. 매 판 종료 시 `exports/laya-play/ladder/replays.md`·`replays.csv` 자동 갱신, 로그 `exports/laya-play/runtime/logs/ladder-loop-ex215.log` |

## 결과

사용자 지시(2026-11-24 10:57 KST, "진행중인 경기가 있다면 끝나고 종료")에 따라 8번째 교체 경기(`vs yiht`, 41턴)가 기권 없이 정상 종료·리플레이 업로드된 시점(`11:02:13 KST`)에 `laya-ladder-ex215` 루프 및 `laya-search2bv2` CPU 서빙을 정상 종료했다. `exports/laya-play/ladder/replays.md`·`replays.csv`에 총 9경기 전부 반영(누적 678경기).

### 종합 성적 (`09:49–11:02 KST`, 9판, 오류 0)

| 구간 | 팀 | 판수 | 전적 | 승률 | 레이팅 변화 | 상대 평균 레이팅 |
|---|---|---:|---|---:|---|---:|
| 전체 (`EX-215`) | `t95bfb45561` (1) + `t61731415d7` (8) | 9 | **4승 5패** | 44.4% | `1437 → 1446` (`+9`, 최고 `1482`) | 1518.2 |
| 교체 전 (1판) | `t95bfb45561` (`teams_blim.json`) | 1 | 0승 1패 | 0.0% | `1437 → 1429` (`-8`) | 1691.0 |
| 교체 후 (8판) | `t61731415d7` (`Spikestack`, `teams.json`) | 8 | **4승 4패** | **50.0%** | **`1429 → 1446` (`+17`)** | 1496.6 |

- **1500+ 상대(`t61731415d7` 구간)**: 2승 2패 (`VectorSchruffer 1617` 승 `+30`, `achbeet 1559` 승 `+26`, `toraflora! 1509` 패 `-18`, `yiht 1504` 패 `-18`).
- **탐색·서빙 텔레메트리 (462결정)**: `with_vphi 422/462 (91.3%)`, `overrides 65/462 (14.1%)`(EX-211 2-B v1 `9.5%` 대비 개입률 상승), `duel_lose` 발동 `161/462 (34.8%)`, `absorb_penalties` 발동 `0`, 오류 **`0`**, CPU 서빙 응답 `p50 5.478s` / `p95 7.735s` (`0 GPU`).
- **개별 관찰 (Air Balloon Gholdengo, `gen9ou-2718581763`)**: Turn 20 지진은 `Air Balloon` 미인식이 아니라 `Roost` PP 0/8·HP 9.7% 망나뇽의 정상 희생(sack) 턴이었으나, Turn 10~11에서 전 공격기 무효 시 `strategy.duel()`이 `None`을 반환해 `duel: lose` 경고가 사라지고, MCTS 5k의 근시안(`50k`에서는 즉시 `switch` 선택)과 $V_\phi$의 pure-state-dynamics 구조(도구·상성 미입력)가 겹쳐 `Dragon Dance`를 2회 쌓은 한계를 확인했다.

### 경기별 목록

| 시각 (KST) | 리플레이 | 팀 | 결과 | 상대 (레이팅) | 레이팅 변화 | 턴 |
|---|---|---|---|---|---:|---:|
| 10:00 | [gen9ou-2718571628](https://replay.pokemonshowdown.com/gen9ou-2718571628) | `t95bfb45561` | 패 | `claudestopher` (1691) | `1437→1429 (-8)` | 106 |
| 10:07 | [gen9ou-2718575836](https://replay.pokemonshowdown.com/gen9ou-2718575836-voqdye8vw5lmj9iippb7ksqlmqbyd4fpw) | `t61731415d7` | **승** | `yiht` (1451) | `1429→1450 (+21)` | 23 |
| 10:13 | [gen9ou-2718578439](https://replay.pokemonshowdown.com/gen9ou-2718578439) | `t61731415d7` | **승** | `achbeet` (1559) | `1450→1476 (+26)` | 36 |
| 10:17 | [gen9ou-2718580223](https://replay.pokemonshowdown.com/gen9ou-2718580223) | `t61731415d7` | 패 | `coast ghost` (1432) | `1476→1453 (-23)` | 32 |
| 10:21 | [gen9ou-2718581763](https://replay.pokemonshowdown.com/gen9ou-2718581763) | `t61731415d7` | 패 | `freedomafter20yrs` (1448) | `1453→1433 (-20)` | 30 |
| 10:33 | [gen9ou-2718583232](https://replay.pokemonshowdown.com/gen9ou-2718583232-5tati97y8qtgii2n4ltkjvav4v8w241pw) | `t61731415d7` | **승** | `VectorSchruffer` (1617) | `1433→1463 (+30)` | 48 |
| 10:45 | [gen9ou-2718586915](https://replay.pokemonshowdown.com/gen9ou-2718586915-6a5i7ocaec4cde4dv7n4buonwctd31ypw) | `t61731415d7` | **승** | `Scizor is tough` (1453) | `1463→1482 (+19)` | 51 |
| 10:53 | [gen9ou-2718591026](https://replay.pokemonshowdown.com/gen9ou-2718591026-v1ew6qf7aj4nv6qt6rw73739hdo19t0pw) | `t61731415d7` | 패 | `toraflora!` (1509) | `1482→1464 (-18)` | 56 |
| 11:01 | [gen9ou-2718593764](https://replay.pokemonshowdown.com/gen9ou-2718593764-vlrs8xfiqgvli0m4lay3ykb4ucwkkc2pw) | `t61731415d7` | 패 | `yiht` (1504) | `1464→1446 (-18)` | 41 |
