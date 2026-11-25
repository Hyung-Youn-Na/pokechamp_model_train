# EX-228 — EX-225 방식 C-1 정화판 단독 무탐색(v14+walled_duel) 대 foul-play Blim 128 (GPU 1)

- 상태: Completed
- 생성일: 2026-11-25
- 책임자: Antigravity (Gemini)
- 관련 exec plan: [EP-249](../plans/EP-249-ex226-wayb-and-ex225-c1clean-blim128-and-ladder.md)
- 관련 decision: [D-225](../decisions/D-225-ep249-ex226-wayb-ex225-c1clean-blim128-ladder.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-205](EX-205-laya-v13-zeroshot-vs-foulplay-unlimited.md) (`EX-200` `v13` 단독 `0.315`), [EX-201](EX-201-laya-rerank-vs-foulplay-unlimited.md) (`EX-200` `v12` 단독 `0.375`)
- 기준 연구선: `research/model-training`

## 질문 및 목적

[EX-225](EX-225-laya-way-c1-clean-vphiv3-2ply-train.md)(Way C-1 정화 증류)을 **실시간 탐색 없이 단독 추론(`--v14 --walled-duel --no-search`)**으로 시간 무제한 `foul-play` Blim 128에 투입했을 때, 순수 가중치 증류만으로 `EX-205 (0.315)` / `EX-201 (0.375)` 대비 얼마나 향상되는가?

## 조건 및 변수

- **체크포인트·서빙**: `EX-225/checkpoints/selected`, `--v14 --walled-duel --no-search` (MCTS/V_phi 미사용)
- **자원·포트**: **물리 GPU 1 단독**, 포트 `8104..8107`, 실행기 `scripts/laya-blim-ep249 track2` (완료 직후 `EX-229` 자동 연쇄)

## 결과

- **완료·봉인**: `128/128` 정상 완료 (`failed=0, incomplete=0, invalid=0`, `verify_seal == []`), `foul-play` `6,810`결정(`p50 7.307s, p95 7.952s`), `EX-225` 단독 결정 지연 `p50 0.304s, p95 0.815s`
- **전적 및 점수 (보고)**: **47승 0무 81패**, 평균 점수 **`0.367`** (조합 클러스터 95% **`[0.273, 0.461]`**)
- **동일 슬롯 비교 (D-191 보고 전용)**:
  - vs `EX-205` (`EX-200 v13` 단독 `0.315`, 127슬롯): **`+0.055 [-0.047, +0.164]`** (나음 26, 나쁨 19, 같음 82 — 95% CI가 0 포함)
  - vs `EX-174` (`v10rt` 단독 `0.331`, 127슬롯): **`+0.039 [-0.055, +0.127]`** (나음 21, 나쁨 16, 같음 90 — 95% CI가 0 포함)
- **세부 진단**: 실패 기술률 `6.00%` (`290/4,831`, `69/128`경기), 테라 사용 `72/128`경기(`16승 56패`, `choice_rate 1.31%`), 팀 유형별 `balance 0.386 (n=70)` · `weather 0.400 (n=20)` · `defense 0.500 (n=4)` · `offense 0.294 (n=34)`.
- **산출물**: `runs/model-training/EX-228/report.md`, `seal.json`, C-047 뷰어 `exports/battle_viewers/ex228/index.html` (`7,118`결정, `128`경기).
