# EP-250 — EX-226 방식 B Offense 전용 공식 Showdown gen9ou 래더 (13:30 KST까지)

- 상태: Active
- 생성일: 2026-11-26
- 책임자: Antigravity (Gemini)
- 승인 근거·범위: 사용자 지시(2026-11-25 23:41Z / 2026-11-26 08:41 KST, `offense` 팀만 사용해 `EX-226` 설정으로 오후 1:30 KST까지 공식 래더 진행), [D-226](../decisions/D-226-ep250-ex226-wayb-offense-ladder.md). 공식 Showdown 서버(`sim3.psim.us`) `gen9ou` 래더 계정 `nhy_test1629` 사용.
- 관련 contract / decision / experiment: [D-226](../decisions/D-226-ep250-ex226-wayb-offense-ladder.md), [EX-231](../experiments/EX-231-laya-ex226-wayb-offense-ladder.md)
- 겹치는 등록 plan: [EP-249](EP-249-ex226-wayb-and-ex225-c1clean-blim128-and-ladder.md)(Completed, `EX-226` 체크포인트 및 `laya-ex226-wayb` 서빙 설정 상속).
- 기준 연구선: `research/model-training`
- 실제 작업 branch·시작 commit: `research/model-training`, `a80cb51` 위
- 작업 checkout과 launcher: `/workspace`, `scripts/laya-ladder-ex231-offense`
- 새 산출물: `exports/laya-play/runtime/logs/ladder-loop-ex231-offense.log`, `exports/laya-play/ladder/replays.md`

## 범위와 불변 조건

- **GPU 격리**: 물리 GPU 0 단독(`GPU-4f27dd5a-ef72-0d3b-4f50-fc6c360edfd4`, `--device cuda`, `--workers 4`). GPU 1·2·3 미접촉.
- **팀 구성**: 순수 `offense` 4팀 순환(`ta199a565dc`, `t04995ad0de`, `tef21addf17`, `t94a0e30d55`). 오분류 풀 막이 2팀(`td061dd6180`, `t71230b7e95`) 제외.
- **종료 조건**: `2026-11-26 13:30:00 KST` (`epoch 1795667400`) 이후 판 경계에서 무몰수 자동 종료 및 GPU 0 유휴 반환.

## 완료 기준

- [ ] `EX-231` (`EX-226` 방식 B, 순수 `offense` 4팀, GPU 0) 13:30 KST 판 경계 무몰수 정상 마감
- [ ] 전적·ELO 추이·팀별 승률·Way B 텔레메트리 보고 및 GPU 0 유휴(`0 MiB`) 확인

## 진행

- 2026-11-25T23:42Z (2026-11-26 08:42 KST) — D-226·EP-250·EX-231 등록 및 GPU 0 서빙 기동 착수.
