# EX-231 — EX-226 방식 B Offense 전용(4팀 순환, GPU 0 서빙) 공식 Showdown gen9ou 래더 대전

- 상태: Running
- 생성일: 2026-11-26
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-250](../plans/EP-250-ex226-wayb-offense-ladder.md)
- 관련 decision: [D-226](../decisions/D-226-ep250-ex226-wayb-offense-ladder.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md)
- 비교 대상: [EX-230](EX-230-laya-ex226-wayb-ladder.md) (28팀 전 아키타입 66판 `33승 33패`, `1522→1636`, 최고 `1648`)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`EX-227` Blim 128에서 가장 높은 승률(`offense 0.588`, 20승 14패)을 보인 **`offense` 아키타입(순수 4팀)**만 사용해 `EX-226` 방식 B 설정(`--v14 --way-b --two-ply --walled-duel --no-calc-duel --iterations 50000`)으로 `2026-11-26 13:30 KST`까지 공식 Showdown `gen9ou` 래더를 주행했을 때 고레이팅(`1636+`) 구간 도달 성능은 어떠한가?

## 조건 및 변수

- **체크포인트·서빙**: `EX-226/checkpoints/selected` + `EX-221/checkpoints/selected`, `--v14 --way-b --two-ply --walled-duel --no-calc-duel --iterations 50000 --model laya-ex226-wayb --device cuda --workers 4` (**물리 GPU 0 단독**, GPU 1·2·3 미접촉)
- **팀 순환 (순수 `offense` 4팀; 오분류 풀 막이 `td061dd6180`, `t71230b7e95` 제외)**:
  1. `ta199a565dc` (dragonite, greattusk, deoxysspeed, gholdengo, zamazenta, ironvaliant)
  2. `t04995ad0de` (kingambit, ironcrown, irontreads, ironvaliant, kommoo, kyurem)
  3. `tef21addf17` (ragingbolt, cresselia, glimmora, kingambit, ogerponwellspring, zamazenta)
  4. `t94a0e30d55` (zamazenta, ceruledge, deoxysspeed, glimmora, ironhands, ironvaliant)
- **종료·계정·로그**: `2026-11-26 13:30:00 KST` 판 경계 자동 종료, 계정 `nhy_test1629` (시작 ELO `1636`), 로그 `exports/laya-play/runtime/logs/ladder-loop-ex231-offense.log`

## 결과

진행 중.
