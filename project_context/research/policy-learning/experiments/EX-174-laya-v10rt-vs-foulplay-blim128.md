# EX-174 — laya v10rt 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU)

- 상태: Completed
- 생성일: 2026-11-17
- 책임자: Claude Code
- 관련 exec plan: [EP-232](../plans/EP-232-laya-foulplay-v10rt.md)
- 관련 decision: [D-212](../decisions/D-212-laya-foulplay-blim-teams.md), [D-211](../decisions/D-211-laya-foulplay-opponent.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: 없음(같은 슬롯 기준선 없음). 참고로 [EX-145](EX-145-laya-play-teams-v5t-v6st-v6ht-battle.md)는 같은 Blim 팀 일부를 Abyssal 상대로 썼다.
- 기준 연구선: `research/model-training`

## 질문 및 목적

laya-play blimAI 봇이 쓰는 Blim 팀으로 양쪽이 같은 팀을 번갈아 잡을 때, v10rt는 foul-play를 상대로 얼마나 이기는가?

## 가설 또는 qualification 목표

- **판정 없음(보고 전용)**. 정상 종료가 120/128 미만이면 "판정 보류"를 적는다.
- **보고 지표**: v10rt 승무패, 평균 점수와 조합 클러스터 bootstrap 95%(10,000회, EX-120 요약기), 교환 쌍 분포(둘 다 승·나눔·둘 다 패), 팀 유형별 점수, 양측 테라 사용, v10rt 실패 기술, 결정 지연, 승리·패배 턴. 학습 자료에 있는 서명 15팀과 나머지 49팀을 나눈 점수도 적는다.
- 한계: foul-play 탐색은 재현되지 않는다. v10rt 서빙은 CPU다. 추론 통계는 2026-10 고정. 15팀은 학습 자료와 겹친다.

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| Blim 일정 128슬롯 × v10rt | foul-play `8f541f8`·3,000ms·병렬 4·스레드 1·2026-10 통계, 300턴/600결정, 경기당 1,200초, 렌더러 v10, EX-167 selected | 팀: `runs/model-training/EX-174/collection`(Blim 64팀, 32개 대진 × 시드 2 × 교환) | CPU, 포트 8100~8103, mem-guard 25 GB |

## 실행

- 일정: `integration/foulplay/blim.py`(실행 전 생성·봉인). 실행기: `integration/foulplay/battle.py`(`STUDIES['EX-174']`), 연결 실행 `scripts/foulplay-ep232 run EX-174`.
- 순서: mock(첫 쌍 2경기, 분모 밖) → prepare → execute → export. 상한 10시간, 자동 재실행 없음.

## 결과

- mock(분모 밖) 07:33Z~07:37Z: 2/2 정상·감사 통과, v10rt 2패(27턴, 20턴).
- execute 07:37Z~11:11Z(16:37~20:11 KST, 3.6시간), export·뷰어 확인 11:20Z. mem-guard 최대 15.0 GB. 보고 `runs/model-training/EX-174/report.md`, 봉인됨.
- 상태: 정상 127, 미완료 1(`fp-b20-s2-a`, 양쪽이 교체만 반복하며 244턴까지 가 경기당 1,200초 상한에 걸림. 규칙대로 집계 밖), 실패·무효 0. 정상 120 이상이므로 판정 보류 아님.

| 지표 | 값 |
|---|---|
| v10rt 승/무/패 | 42/0/85 |
| 평균 점수(조합 클러스터 95%) | 0.331 [0.250, 0.414] |
| 교환 쌍(63쌍) | v10rt 둘 다 승 4, 나눔 34, 둘 다 패 25 |
| 학습 자료 서명 팀 / 그 밖 | 10/30 (0.333) / 32/97 (0.330) |
| 팀 유형별(v10rt 쪽) | 밸런스 0.400(70), 공격 0.242(33), 날씨 0.200(20), 수비 0.500(4) |
| 시드 1 / 2 | 0.312 / 0.349 |
| v10rt 실패 기술 | 251/4,900 (5.12%), 77경기 |
| v10rt 테라 | 64경기, 결정당 1.13%(64/5,639), 테라 경기 20승 44패 |
| foul-play 테라 | 116경기(테라 결정 116개) |
| 결정 지연 | v10rt p50 2.34초·p95 4.96초(CPU), foul-play p50 7.35초·p95 8.24초·최대 9.97초 |
| 승리 턴 중앙값 / 패배 턴 중앙값 | 47 / 35 |

- v10rt가 잡았을 때 두 경기 모두 진 팀이 64개 중 36개다. 래더에 쓰던 `t6e257bdf5e`는 0/2, 20:00 이후 래더 팀 `t95bfb45561`은 2/2다.
- **보고서 정정**: `report.md`·`result.json`의 foul-play "테라 사용 경기 0"은 집계 결함이다. 선택 명령이 목록(`["/choose move x terastallize", rqid]`)인데 문자열 포함 대신 목록 원소 비교를 했다. 원 기록(`foulplay-events.jsonl`, 프로토콜의 `|-terastallize|`)에서 다시 센 값이 위 표의 116경기다. 봉인된 산출물은 고치지 않았고, 코드(`opponent_report`)는 이후 실행용으로 고쳤다.
- 뷰어 `/workspace/exports/battle_viewers/ex174/index.html`(128경기, 결정 7,537개). 브라우저 확인 통과(1440·390 폭, 페이지 오류 0, `project_context/exec-plans/evidence/ep232/ex174-viewer-check.json`).

## 결론 및 후속 작업

- foul-play(결정당 약 7초 탐색)는 v10rt에게 Abyssal보다 훨씬 어려운 상대다. v10rt 점수 0.331로, Abyssal 상대 0.86~0.88(EX-162·EX-168, 다른 팀 일정)과 차이가 크다. 같은 슬롯 비교가 아니므로 차이의 크기는 참고값이다.
- 포화되지 않은 상대이므로, v11rt·v11rtc 같은 후속 판본을 같은 일정(이 collection)으로 붙이면 판본 차이를 볼 여지가 있다. 실행은 따로 지시받는다.
- 공격·날씨 팀을 잡았을 때 특히 약하다(0.24, 0.20). 패배 판 원인 분석은 이 실험 범위 밖이다.
