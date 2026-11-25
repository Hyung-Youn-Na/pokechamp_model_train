# EX-211 — 2-B 온라인 다중턴 탐색 + 상태가치 V_phi(EX-208) 공식 Showdown gen9ou 래더 대전(GPU 1 서빙, 2026-11-24 13:00 KST까지)

- 상태: Stopped
- 생성일: 2026-11-24
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-243](../plans/EP-243-laya-multiturn-search-value-distill.md)
- 관련 decision: [D-219](../decisions/D-219-laya-multiturn-search-and-value.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-203](EX-203-laya-engine-value-ladder.md)(EX-200 v12 단일 forward, 104판 53승 51패, 1332→1505, 상대 평균 1472), [EX-194](EX-194-laya-v12-ladder.md)(v12, 40판 20승 20패), 같은 계정(`nhy_test1629`)·같은 팀(`t95bfb45561`)의 기존 래더 기록
- 기준 연구선: `research/model-training`

## 질문 및 목적

사용자 지시(2026-11-24 08:39 KST, "EX208 실험 모델의 레더 대전을 KST 13:00 까지 수행해주세요."): Blim 128경기에서 역대 최고 점수(`0.406`, 52승 76패)를 기록한 [EX-208](EX-208-laya-search-2b-vs-foulplay-unlimited.md) 2-B 모델(`EX-200` + `v13` + MCTS 5k + `EX-207` $V_\phi$)이 공식 Showdown gen9ou 사람·봇 래더(1500+ 출발)에서 어떤 전적과 레이팅 변화를 보이는지 측정한다. [EX-210](EX-210-laya-mcts5k-q-rerank-1b-vs-foulplay-unlimited.md)(GPU 0)과 GPU 분리 병행한다.

## 가설 또는 qualification 목표

- **판정 없음(보고 전용, D-191)**: 판 수, 승패, 레이팅 변화, 상대 평균 레이팅, 1500+ 구간 및 상위 래더 봇 상대 전적, 탐색 적용률(`with_vphi`/override/지연)을 [EX-203](EX-203-laya-engine-value-ladder.md)과 나란히 보고한다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 모델·탐색 | `EX-208` 동일 구성(`EX-200` selected + `v13` 입력 + Rust MCTS `5,000 iters` + `EX-207` `clean_deepsets_v2` $V_\phi$, `alpha=0.50`, `lambda=0.03`, `margin=0.015`, `turn_action`·`forced_switch`). 서빙 모델명 `laya-search2b`, 렌더러 라벨 `v13+search2b` |
| 팀·계정 | `t95bfb45561` (`balance`, `EX-203`·`EX-194`와 동일), 계정 `nhy_test1629` |
| 서빙·자원 | **물리 GPU 1 전용**(`GPU-c7e2d577-573f-0412-1ed6-ad6648efa454`, `--workers 2`, GPU 0은 `EX-210`, GPU 2·3 미사용), `laya-play` `official.sh` 1판씩 반복 (`early_history=True` + `fp1` 페이로드 전달) |
| 분량 | 시작(`2026-11-24 08:4x KST`)부터 **`2026-11-24 13:00 KST`**(`2026-11-24T04:00:00Z`)까지. 연속 3회 실패 시 중단 |
| 기록 | 매 판 종료 시 `exports/laya-play/ladder/replays.md`·`replays.csv` 자동 갱신, 로그 `exports/laya-play/runtime/logs/ladder-loop-ex211.log`·`serving-search2b.log` |

## 실행

- 실행기: `scripts/laya-ladder-ex211` (물리 GPU 1 핀 고정, `EX-203` 루프 구조 계승, 종료 시 서빙·`serving.ready.json` 자동 원복).

## 결과

- **종료 상태**: 사용자 지시(2026-11-24 09:15 KST, "일단 레더 대전을 종료해주세요.")로 조기 종료(`Stopped`). 서빙·봇 프로세스 및 `runtime/serving.ready.json` 원복, GPU 1 자원 반환 완료.
- **래더 성적 (`2026-11-24 08:44 ~ 09:13 KST`, 8판 완료, 보고 전용 D-191)**:
  - **8판 2승 6패**, 레이팅 **`1517 → 1457` (`-60`, 최고 `1509`, 최저 `1457`)**, 상대 평균 레이팅 **`1541.0`**(`EX-203` 평균 `1472` 대비 상위 구간 매칭).
  - 상대 레이팅대별: 1500 미만 3판 2승 1패(`Xrlylyl 1322` 승, `Unikoorn 1281` 승, `otaviov1 1434` 패), 1500 이상 5판 0승 5패(`claudestopher 1747`, `MissingNo.ZeroBot 1593/1573`, `sleepman610 1626`, `nickgen6rbrlbot 1752`).
- **탐색 텔레메트리**: 총 `338`회 탐색 중 **`311`회(`92.0%`) $V_\phi$ 적용**, override **`32`회(`9.5%`)**, 오류 **`0`**, 결정 지연 **`p50 0.910초 / p95 1.936초`**.
- **주요 패인·진단 발견**:
  1. `Draining Kiss` 교환(`sleepman610` T4~T7): `v13`과 $V_\phi$는 교체를 1위로 판정했으나 `EX-200` 사전확률(`0.827`, `0.03·ln(p)`)과 `Q_mcts`(스케일 우위 + 미관측 기술 샘플링)에 눌려 override 미발동; 후반 `foe_options`에서 관측된 `drainingkiss`가 `foe:move:other`로 누락.
  2. `Dondozo` vs `Water Absorb`(`Xrlylyl` T22~T26): `Ogerpon-Wellspring`의 3턴 주기 `Taunt`로 비공격기가 봉인된 상태에서, 외부 `poke-engine v0.0.48`이 `Water Absorb`의 `+25%` 회복 명령(`Heal SideTwo`)을 생성하지 않고 `v13`도 `fails`만 표기해 6%→100% 회복을 초래.
- **기록**: `exports/laya-play/ladder/replays.md`·`replays.csv` 동기화 완료(총 669판 중 8판 `search2b / v13+search2b`).
