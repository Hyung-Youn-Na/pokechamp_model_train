# EX-173 — laya v10rt 대 foul-play(MCTS 3초 × 병렬 4), EX-120 일정 128경기(CPU)

- 상태: Stopped
- 생성일: 2026-11-17
- 책임자: Claude Code
- 관련 exec plan: [EP-232](../plans/EP-232-laya-foulplay-v10rt.md)
- 관련 decision: [D-211](../decisions/D-211-laya-foulplay-opponent.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-168](EX-168-laya-v10t-v10rt-battle256.md)의 v10rt 대 Abyssal(같은 슬롯, 110/0/18, 0.859)
- 기준 연구선: `research/model-training`

## 질문 및 목적

v10rt는 foul-play(탐색 봇)를 상대로 얼마나 이기는가? 같은 슬롯에서 Abyssal보다 얼마나 어려운 상대인가?

## 가설 또는 qualification 목표

- **판정 없음(보고 전용)**. 정상 종료가 120/128 미만이면 "판정 보류"를 적는다.
- **보고 지표**:
  - v10rt 승무패, 평균 점수와 조합 클러스터 bootstrap 95%(10,000회, 시드 20261023 — EX-120 요약기)
  - 같은 슬롯 차이(EX-173 − EX-168 v10rt)의 조합 클러스터 bootstrap 95%(10,000회, 시드 20261073), foul-play가 더 어려운/쉬운/같은 슬롯 수
  - 양측 테라 사용, v10rt 실패 기술 비율, 결정 지연(v10rt CPU 서빙, foul-play 탐색 시간), 승리·패배 턴, 팀 유형별 점수
- 한계: foul-play 탐색은 시간 기반이라 재현되지 않는다. v10rt 서빙은 CPU다(EX-168은 GPU). 추론 통계는 2026-10 고정.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| EX-120 일정 128슬롯 × v10rt | 팀, 진영, 시뮬레이터 시드, 300턴/600결정, 경기당 1,200초, 렌더러 v10(2,048, `early_history`), 체크포인트 EX-167 selected | 상대: Abyssal → foul-play(`8f541f8`, 3,000ms, 병렬 4, 스레드 1, 2026-10 통계) | CPU, 포트 8100~8103, mem-guard 25 GB |

## 실행

- 실행기: `integration/foulplay/battle.py`(`laya_imitation.battle.play_slot` 그대로, 상대 진영만 foul-play actor), 연결 실행 `scripts/foulplay-ep232 run`.
- 순서: mock(첫 조합 2경기, 분모 밖) → prepare(소스·foul-play 사본·추론 자료·체크포인트 해시 동결, 문서 동결) → execute → export.
- 상한 10시간. 자동 재실행 없음. phase 실패에서 멈춘다.

## 결과

- mock(분모 밖): 2/2 정상 종료·감사 통과, v10rt 2패(10턴, 48턴). foul-play 결정 65개, 탐색 시간 p50 7.13초·p95 7.50초, 테라 0경기.
- prepare 07:28Z(128슬롯, 체크포인트 `4ef5b1d2…`). execute 07:28Z 시작.
- **2026-11-17 07:30Z(16:30 KST) 사용자 지시로 중지했다**([D-212](../decisions/D-212-laya-foulplay-blim-teams.md)). 끝난 슬롯은 0개다. 진행 중이던 4슬롯(`fp-m13-s1-a/b`, `fp-m30-s1-a/b`)은 프로세스를 종료해 결과 없이 끊겼다. 원 기록은 `runs/model-training/EX-173/`에 그대로 있다.

## 결론 및 후속 작업

- 집계할 경기가 없다. 판정·보고를 하지 않는다.
- 같은 설정을 Blim 팀 일정으로 바꾼 [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)가 이어받는다.
