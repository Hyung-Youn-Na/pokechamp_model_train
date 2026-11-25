# EX-230 — EX-226 방식 B(calc-duel-free + 5단계 matchup & eval 프롬프트 주입, CPU 서빙) 공식 Showdown gen9ou 래더 대전

- 상태: Completed
- 생성일: 2026-11-25
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-249](../plans/EP-249-ex226-wayb-and-ex225-c1clean-blim128-and-ladder.md)
- 관련 decision: [D-225](../decisions/D-225-ep249-ex226-wayb-ex225-c1clean-blim128-ladder.md), [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md)
- 비교 대상: `EX-225` 58판 (`31승 27패`, `1398→1521`, 최고 `1557`), `EX-200 noduel` 50판 (`26승 24패`, 최고 `1566`)
- 기준 연구선: `research/model-training`

## 질문 및 목적

[EX-226](EX-226-laya-way-b-tool-inject-train.md) 방식 B (`laya-ex226-wayb`, `v14+wayb_noduel`, Laya 100% 단독 최종결정)를 공식 Showdown `gen9ou` 래더 28팀 비스톨 로테이션에 CPU 서빙(`0 GPU`)으로 투입해 `EX-227`·`EX-229` Blim 128 완료 시점까지 실전 전적·회복 텔레메트리·안정성을 검증한다.

## 조건 및 변수

- **체크포인트·서빙**: `EX-226/checkpoints/selected` + `EX-221/checkpoints/selected`, `--v14 --way-b --two-ply --walled-duel --no-calc-duel --iterations 50000 --model laya-ex226-wayb --device cpu --workers 2`
- **팀·계정·종료**: 28팀 비스톨 아키타입 교차 로테이션(풀 막이 4개 제외), 계정 `nhy_test1629`, `EX-227`·`EX-229` 양쪽 봉인 완료 시 판 경계 무몰수 자동 종료, 로그 `exports/laya-play/runtime/logs/ladder-loop-ex230-wayb.log`

## 결과

- **종료 상태**: **66판 정상 완료** (`MAX_SECONDS=28800` 8시간 상한 판 경계 무몰수 정상 종료, 기권 `0`, 서빙 에러 `0`), CPU 서빙 종료 및 자원 반환 완료.
- **전적 및 레이팅 (공식 Showdown `gen9ou`, 28팀 비-막이 로테이션)**:
  - **전적**: **33승 33패 (`50.0%`)**, 총 `2,516`턴 (경기당 평균 `38.1`턴, 최장 `263`턴)
  - **ELO**: **`1522 → 1636` (`+114`)**, **역대 최초 `1600+` 돌파 · 최고 `1648`** (최저 `1437`), **상대 평균 ELO `1578.6`** (최고 `1852`)
  - **`1600+` 고레이팅 상대 9승**: `nickgen6rbrlbot (1852, +34)`, `claudestopher (1794/+30, 1755/+32, 1709/+26, 1609/+28)`, `PPOrygon2 (1779, +30)`, `MissingNo.ZeroBot (1717, +28)`, `AnkleBiterGible (1640, +22)`, `chusei88 (1617, +19 → 1647)`
  - 선행 `EX-225` 58판(`31승 27패`, `1398→1521`, 최고 `1557`, 상대 평균 `1476.2`) 대비 상대 평균이 `+102.4` 높아진 구간에서 `+114` 추가 상승.
- **Way B 판단·회복 텔레메트리 (`66`경기 `2,858`결정)**:
  - 도구 주입 `2,680`턴, 에러 `0`, **Laya 자체 판단 변경 `23.4%` (`627/2,680`)**, `MCTS top-1` 일치 `63.5%` / `V_phi top-1` 일치 `53.7%`
  - 5단계 `matchup:` 분포: `very favorable 940`, `favorable 747`, `even 501`, `unfavorable 242`, `very unfavorable 250`
  - 회복(`HEAL`): `base 167 → final 195` (`7.3%`, `INTO:AWAY = 50:22`), 연속 `Protect`: `38`건(주로 263턴 장기전 `t70fc34c284` 발생 — 외부 `consec_protect_veto` 없이 Laya 단독 판단이므로 향후 프롬프트에 직전 턴 `Protect` 표시 보완 여지 확인).
- **산출물**: `exports/laya-play/runtime/logs/ladder-loop-ex230-wayb.log`, `exports/laya-play/ladder/replays.md` (`#807–#872`, `ex226-wayb` · `v14+wayb_noduel`).
