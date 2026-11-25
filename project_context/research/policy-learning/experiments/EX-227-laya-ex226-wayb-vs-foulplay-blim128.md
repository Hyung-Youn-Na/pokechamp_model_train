# EX-227 — EX-226 방식 B(calc-duel-free + 5단계 matchup & eval 프롬프트 주입, Laya 단독 최종결정) 대 foul-play Blim 128 (GPU 0)

- 상태: Completed
- 생성일: 2026-11-25
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-249](../plans/EP-249-ex226-wayb-and-ex225-c1clean-blim128-and-ladder.md)
- 관련 decision: [D-225](../decisions/D-225-ep249-ex226-wayb-ex225-c1clean-blim128-ladder.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-223](EX-223-laya-waya-v2-vphiv3-2ply-vs-foulplay.md) (`EX-200 + Way A v2`, `0.414 [0.328, 0.492]` 역대 최고)
- 기준 연구선: `research/model-training`

## 질문 및 목적

[EX-226](EX-226-laya-way-b-tool-inject-train.md)(Way B: `calc-duel-free` + `MCTS 50k / EX-221 V_phi v3 2-ply` 5단계 `matchup:` + `eval:` 주입)을 외부 veto 수식 없이 **100% Laya 단독 최종결정권자**로 시간 무제한 `foul-play` Blim 128 동일 슬롯에 투입했을 때, 역대 최고 기록인 `EX-223 (0.414)`을 상회하는가?

## 조건 및 변수

- **체크포인트·서빙**: `EX-226/checkpoints/selected` + `EX-221/checkpoints/selected`, `--v14 --way-b --two-ply --walled-duel --no-calc-duel --iterations 50000 --workers 4`
- **자원·포트**: **물리 GPU 0 단독**, 포트 `8100..8103`, 실행기 `scripts/laya-blim-ep249 track1`

## 결과

- **완료·봉인**: `128/128` 정상 완료 (`failed=0, incomplete=0, invalid=0`, `verify_seal == []`), `foul-play` `7,849`결정(`p50 7.262s, p95 7.991s`), `EX-226` Way B 결정 지연 `p50 6.681s, p95 10.045s`
- **전적 및 점수 (보고 — 역대 최고치 갱신)**: **57승 0무 71패**, 평균 점수 **`0.445`** (조합 클러스터 95% **`[0.352, 0.539]`**)
- **동일 슬롯 비교 (D-191 보고 전용)**:
  - vs `EX-205` (`EX-200 v13` 단독 `0.315`, 127슬롯): **`+0.126 [+0.031, +0.228]`** (나음 32, 나쁨 16, 같음 79 — **95% CI가 0을 엄격히 상회**)
  - vs `EX-223` (`EX-200 + Way A v2` 직전 역대 최고 `0.414`, 128슬롯): **`+0.031 [-0.047, +0.117]`** (나음 24, 나쁨 20, 같음 84 — 95% CI가 0 포함)
  - vs `EX-208` (`search-2b` `0.406`, 128슬롯): **`+0.039 [-0.086, +0.172]`** (나음 32, 나쁨 27, 같음 69)
  - vs `EX-228` (`EX-225` 단독 `0.367`, 128슬롯): **`+0.078 [-0.031, +0.188]`** (나음 27, 나쁨 17, 같음 84)
  - vs `EX-174` (`v10rt` 단독 `0.331`, 127슬롯): **`+0.110 [-0.016, +0.242]`** (나음 32, 나쁨 18, 같음 77)
- **세부 진단**: 실패 기술률 `5.50%` (`307/5,577`, `75/128`경기), 테라 사용 `83/128`경기(`37승 46패`, `choice_rate 1.54%`), 팀 유형별 **`offense 0.588 (n=34, 20승 14패)`** · `balance 0.400 (n=70)` · `weather 0.400 (n=20)` · `defense 0.250 (n=4)`.
- **산출물**: `runs/model-training/EX-227/report.md`, `seal.json`, C-047 뷰어 `exports/battle_viewers/ex227/index.html` (`7,924`결정, `128`경기). 물리 GPU 0 유휴 반환(`0 MiB`).
