# EX-229 — EX-225 방식 C-1 정화판 + Way A v2(calc-duel-free + MCTS 50k + V_phi v3 2-ply) 대 foul-play Blim 128 (GPU 1)

- 상태: Completed
- 생성일: 2026-11-25
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-249](../plans/EP-249-ex226-wayb-and-ex225-c1clean-blim128-and-ladder.md)
- 관련 decision: [D-225](../decisions/D-225-ep249-ex226-wayb-ex225-c1clean-blim128-ladder.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 선행·비교 대상: [EX-228](EX-228-laya-ex225-c1clean-standalone-vs-foulplay-blim128.md)(GPU 1 선행 완료 직후 자동 연쇄), [EX-223](EX-223-laya-waya-v2-vphiv3-2ply-vs-foulplay.md)(`EX-200 + Way A v2`, `0.414`)
- 기준 연구선: `research/model-training`

## 질문 및 목적

`EX-225` 정화 증류 가중치 위에 `calc-duel-free` + `Way A v2` (`MCTS 50k + EX-221 V_phi v3 2-ply` + 5단계 `matchup_eval` 가드)를 결합했을 때, `EX-223 (0.414)` 및 `EX-227 (EX-226 Way B)` 대비 Blim 128에서 어떤 성능을 보이는가?

## 조건 및 변수

- **체크포인트·서빙**: `EX-225/checkpoints/selected` + `EX-221/checkpoints/selected`, `--v14 --way-a-v2 --two-ply --walled-duel --no-calc-duel --iterations 50000 --workers 4`
- **자원·포트**: **물리 GPU 1 단독**, 포트 `8104..8107`, `EX-228` 봉인 직후 자동 진입

## 결과

- **종료·봉인 (판정 보류)**: `80/128` 정상 완료(`completed=80, failed=1, invalid=1, unattempted=46`, `verify_seal == []`), `fp-b05-s1-b`에서 `p1`이 정상 패배 JSON 출력 후 결과 파일 경합(`RuntimeError: actor exited without a result: p1`)으로 `phase_halt` → 자동 내보내기·봉인 완료, 물리 GPU 1 유휴 반환(`0 MiB`).
- **전적 및 점수 (80경기, 판정 보류)**: **26승 0무 54패**, 평균 점수 **`0.325`** (조합 클러스터 95% **`[0.211, 0.438]`**).
- **동일 80슬롯 비교 (D-191 보고 전용)**:
  - vs `EX-223` (`EX-200 + Way A v2` `0.414`, 80슬롯): **`-0.125 [-0.230, -0.014]`** (나음 8, 나쁨 18, 같음 54 — 95% CI가 0 미만)
  - vs `EX-228` (`EX-225` 단독 `with duel:`, `0.367`, 80슬롯): **`-0.113 [-0.234, +0.011]`** (나음 11, 나쁨 20, 같음 49)
  - vs `EX-227` (`EX-226` Way B `calc-duel-free`, `0.445`, 80슬롯): **`-0.100 [-0.250, +0.051]`** (나음 12, 나쁨 20, 같음 48)
  - vs `EX-174` (`v10rt` `0.331`, 80슬롯): **`-0.013 [-0.143, +0.111]`**
- **원인 분석**: 서빙 오류 `0`, override 비율 `10.8%`로 기술적 결함은 없으나, `EX-225`는 `duel:` 라인 포함 입력(`laya-v14w-c1v3`)으로 학습된 모델인 반면 `EX-229`는 추론 시 `--no-calc-duel`로 `duel:`을 제거해 학습-추론 입력 분포 불일치가 발생했다. 반대로 학습부터 `calc-duel-free` + `matchup:`·`eval:`로 통합 학습한 `EX-226` (`EX-227`)은 `0.445` 역대 최고치를 기록했다.
- **세부 진단**: 결정 지연 `p50 4.689s, p95 8.788s`, 실패 기술률 `5.30%` (`181/3,412`), 테라 `65/82`경기(`19승 44패`), 팀 유형별 `balance 0.333 (n=48)` · `weather 0.385 (n=13)` · `offense 0.313 (n=16)` · `defense 0.000 (n=3)`.
- **산출물**: `runs/model-training/EX-229/report.md`, `seal.json`, C-047 뷰어 `exports/battle_viewers/ex229/index.html` (`5,706`결정, `82`경기).
