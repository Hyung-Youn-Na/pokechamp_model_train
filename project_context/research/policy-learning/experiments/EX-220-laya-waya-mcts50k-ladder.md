# EX-220 — EX-217 방식 A(Laya 메인 + MCTS 50k + EX-216 V_phi v2 + walled_duel, CPU 서빙) 공식 Showdown gen9ou 래더 대전 (EX-218 학습 완료까지)

- 상태: Stopped
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-245](../plans/EP-245-laya-main-blunder-veto-mcts50k-vphi-v2.md)
- 관련 decision: [D-221](../decisions/D-221-laya-main-waya-mcts50k-vphi-v2.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-215](EX-215-laya-search2bv2-ladder.md) (`2-B v2`, `t61731415d7` 8판 4승 4패 `1429→1446`, 상대 평균 `1497`), [EX-211](EX-211-laya-search2b-ladder.md) (`2-B v1`, 8판 2승 6패 `1517→1457`), [EX-203](EX-203-laya-engine-value-ladder.md) (`EX-200` v12 단일, 104판 53승 51패 `1332→1505`)
- 기준 연구선: `research/model-training`

## 질문 및 목적

사용자 지시(2026-11-24 16:24 KST): Blim 128에서 `0.391`(Laya 1순위 유지율 `89.2%`)을 기록한 [EX-217](EX-217-laya-main-waya-mcts50k-vphiv2-vs-foulplay.md)의 **방식 A(Laya 메인 합의형 블런더 가드 + MCTS 50k + EX-216 매치업 가치망 $V_\phi$ v2 + `walled_duel`)** 설정을 **CPU 서빙**(`0 GPU`, `OMP_NUM_THREADS=4`, `nice 10`)으로 공식 Showdown gen9ou 래더에 투입해 [EX-218](EX-218-laya-way-c1-v14-walled-teacher50k-train.md) GPU 0·1 DDP 학습 완료 시점까지 병행 평가한다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 모델·탐색 | `EX-217` 동일 (`EX-200` + `v13` + `walled_duel` + `MCTS 50,000 iterations` + `EX-216` $V_\phi$ v2 + `--way-a`). 서빙 모델명 `laya-waya`, 렌더러 라벨 `v13+waya50k` |
| 팀·계정 | 최근 사용 팀 **`t61731415d7` (`Spikestack`: Gliscor / Gholdengo / Dragonite / Ting-Lu / Darkrai / Zamazenta, `exports/laya-play/app/laya_play/teams.json`)**, 계정 `nhy_test1629` |
| 서빙·자원 | **CPU 서빙**(`CUDA_VISIBLE_DEVICES=''`, `OMP_NUM_THREADS=4 MKL_NUM_THREADS=4`, `nice 10`, `--workers 2`), `EX-218` 물리 GPU 0·1 DDP 학습과 병행(GPU 2·3 미접촉) |
| 종료 조건·기록 | `EX-218` 학습 완료(`checkpoints/selected/config.json` 생성 또는 `status.json` `trained`/`completed`) 감지 시 진행 중인 판을 기권 없이 마친 뒤 자동 종료(최대 10시간 안전 상한). 매 판 종료 시 `exports/laya-play/ladder/replays.md`·`replays.csv` 자동 갱신, 로그 `exports/laya-play/runtime/logs/ladder-loop-ex220.log` |

## 결과

**사용자 지시로 조기 종료 (`Stopped`, 2026-11-24 08:26Z / 17:26 KST)** — 진행 중이던 Run 11(`vs CE KsXRemix 1574`, 32턴 승)을 기권 없이 판 경계에서 정상 마감한 뒤 자동 종료·서빙 반환 완료.

### 최종 전적 요약 (총 11판 완료)
- **전적**: `11`판 **`5승 6패` (`45.5%`)** *(Run 6 `vs ceo o wo chien 1562` 1판은 Showdown `|badge|` 프로토콜 미구현 `NotImplementedError` 기권; 정상 대국 기준 `10`판 `5승 5패` `50.0%`)*, 레이팅 **`1448 → 1458` (`+10`)**, 상대 평균 레이팅 **`1483.3`**, `1500+` 구간 **`2승 3패`**(정상 대국 `2승 2패`) (`exports/laya-play/ladder/replays.md` `#679–#689`).
- **Way A 텔레메트리** (`351` 결정, 서빙 오류 `0`): Laya 1순위 유지 **`307/351` (`87.5%`)**, 오버라이드 `44`건 (`duel_lose_mcts_veto 12`, `walled_veto 9`, `vphi_blunder_veto 6`, `duel_lose_vphi_veto 5`, `forced_mcts_veto 4`, `consensus_veto 3`, `severe_mcts_veto 3`, `endgame_veto 2`; `walled` 감지 `36`턴).

### 조기 종료(실패) 원인 — 4개 층위의 HP 회복 · `Protect` 과대평가

실전 관전 진단(초기 7판 + 동일 팀 `EX-215` 8판 + 64팀 `EX-217` Blim 128판 `3,094`회 회복 턴 대조)에서 다음 4가지 구조적 결함이 확인되었다.

1. **`EX-216` $V_\phi$ v2의 1-ply "즉시 HP+ / Multiscale 풀피" 착시**:
   - `EX-217` Blim 128판에서 $V_\phi$ v2는 회복기 1순위 비율 `25.5%` (Laya `20.2%`), 특히 **`HP ≥ 90%`에서 `7.5%`(Laya 2.0배)**·**`HP 70–89%`에서 `23.3%`(Laya 2.2배)**이며, **`vphi_blunder_veto`가 회복기로 덮어쓴 비율이 `34회` vs 말린 비율 `3회`(`11.3 : 1`)**로 극단적 회복 편향을 보였다.
   - `EX-220` [gen9ou-2718691689](https://replay.pokemonshowdown.com/gen9ou-2718691689-aluw2a6811qq63dy5bteaqjasenjhj8pw)(`073833`, 승) T20–T24에서 상대 `Garchomp(Rough Skin)`가 **HP 1.0%**인데 `Dragonite`가 4턴 연속 `Roost`를 눌렀고, 특히 **T23 (`HP 96.0%`)**에 Laya(`Extreme Speed 0.378`)를 **`vphi_blunder_veto`(`Roost 0.805` vs `Extreme Speed 0.737`, `dv=+6.88%`)로 덮어써 96% HP `Roost`를 강제**했다. T24(`HP 100.0%` 풀피)에서도 `V_phi v2`는 여전히 `Roost (0.801)`를 1순위로 평가했다 (`matchup_features.py`의 `full_hp = (hp >= 0.999)` + `multiscale_intact` 이진 스텝 보너스 + 1-ply 근시안).
   - `featurize.py`에 **남은 PP(회복기 PP)** 및 **연속 `Protect` 카운터**가 누락되어 있으며, 인간 정상 궤적만으로 학습해 반사실적(템포 포기) 회복 수에 대한 페널티가 없다.
2. **`MCTS 50k` (`poke-engine` `evaluate.rs`)의 고HP 회복 편향**:
   - `EX-217` 기준 **`HP ≥ 90%`에서 `11.3%`(Laya `3.7%`의 3.1배)**, **`HP 70–89%`에서 `20.3%`(Laya의 1.9배)**로 리프 HP 가중치에 따른 과대평가가 존재하며, 상대 랭업(Setup) 턴(`248`턴)에서도 `24.2%`(Laya `14.5%`)나 회복을 1순위로 평가했다.
3. **`EX-200` Laya 본체의 `Dragonite` `Multiscale` 유지 강박 및 반복 루프 무감각**:
   - `EX-220` 초기 7판 기준 `HP 70–89%` `Roost` 선택률이 Laya `76.7%` (`Dragonite` 47턴 중 61.7%), `Gliscor` `Protect` 선택률 `48.8%`(연속 `Protect` 15회 중 실제 `|-fail|` 6회, 상대 랭업 18턴 중 11턴 `Protect`).
   - [gen9ou-2718693021](https://replay.pokemonshowdown.com/gen9ou-2718693021)(`074335`, 패) T4–T11에서 `Dragonite (HP 83–87%)`가 `Araquanid`의 `Lunge` 앞에서 **8턴 연속 `Roost`**를 눌러 `Atk -5` + `Roost` PP 전량 소진.
4. **`Way A` (`integration/laya_search/way_a.py`) 규칙 결함 3건**:
   - **`walled_veto`의 `Protect` 덮어쓰기**: [gen9ou-2718688955](https://replay.pokemonshowdown.com/gen9ou-2718688955-dcf8f53he26vnjf83a1vss94yb7png1pw)(`072713`, 패) T22–T23에서 Laya의 `Spikes`/`switch:3`를 `walled_veto`가 `Protect`로 덮어써 15턴 연속 `Protect` 루프(`|-fail|` 5회)를 유발.
   - **`vphi_blunder_veto`의 고HP 회복기 무제한 허용**: `active_hp ≥ 85%`에서도 1-ply `dv ≥ 0.06`으로 킬각을 `Roost`로 덮어씀.
   - **`consensus_veto`의 `pr_ratio` 페널티 과다**: `074335` T8–T10에서 `MCTS 50k`와 `V_phi v2`가 둘 다 `switch:6`로 만장일치 합의(`dm=+5.8%`, `dv=+3.1%`)했으나 Laya 확률 쏠림(`ln(p/p0)`) 페널티가 합의를 무효화해 `Roost` 루프 탈출 실패.

### 후속 조치 방향
- 가치함수 $V_\phi$ v3 업그레이드(PP·연속 `Protect` 피처 추가, `full_hp` 이진 스텝 완화, 미래 3~5턴 TD($\lambda$) 보조 타겟 + 반사실적 순위 손실) 및 **2-ply Top-K / Laya-Guided Batch PUCT** 탐색으로 미래 영향력 반영.
- `Way A v2` 가드레일(고HP 회복기 veto 제한, `walled_veto` `Protect` 제외, 연속 `Protect` 가드, MCTS+V_phi 만장일치 시 `pr_ratio` 완화) 반영.
