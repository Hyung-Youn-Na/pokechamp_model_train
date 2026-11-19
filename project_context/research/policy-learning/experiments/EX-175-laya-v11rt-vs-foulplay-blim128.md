# EX-175 — laya v11rt 대 foul-play(MCTS 3초 × 병렬 4), Blim 팀 64개 128경기(CPU)

- 상태: Stopped
- 생성일: 2026-11-18
- 책임자: Claude Code
- 관련 exec plan: [EP-233](../plans/EP-233-laya-foulplay-v11.md)
- 관련 decision: [D-212](../decisions/D-212-laya-foulplay-blim-teams.md), [D-211](../decisions/D-211-laya-foulplay-opponent.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md)의 v10rt(같은 슬롯, 42/0/85, 0.331)
- 기준 연구선: `research/model-training`

## 질문 및 목적

v11rt(v11 입력 수정만, EX-171)는 foul-play를 상대로 EX-174의 v10rt보다 많이 이기는가?

## 가설 또는 qualification 목표

- **판정 없음(보고 전용)**. 정상 종료가 120/128 미만이면 "판정 보류"를 적는다.
- **보고 지표**: EX-174와 같은 지표(승무패, 평균 점수와 조합 클러스터 bootstrap 95%, 교환 쌍 분포, 팀 유형별 점수, 양측 테라, 실패 기술, 결정 지연, 승패 턴, 학습 서명 팀/그 밖). 더해서 **같은 슬롯 차이(EX-175 − EX-174 v10rt)** 의 평균과 조합 클러스터 bootstrap 95%(10,000회, 시드 20261073), 나음/나쁨/같음 슬롯 수.
- 해석 규칙: 같은 슬롯 차이 구간이 0을 포함하면 "구별되지 않음"으로 적는다. foul-play 탐색은 재현되지 않아 같은 모델끼리도 슬롯 결과가 달라질 수 있다(잡음은 구간에 포함된다).
- 한계: v11 서빙은 CPU이며 usage extension과 guard 없이 argmax로 둔다(EX-174 v10rt와 같은 조건). EX-174와 실행 시각·CPU 부하가 달라 foul-play 탐색 반복 수가 다를 수 있다(탐색 시간 분포로 기록).

## 조건 및 변수

| Condition | 통제 입력 | 변경 입력 | 자원 |
|---|---|---|---|
| EX-174 Blim 일정 128슬롯 × v11rt | EX-174와 같음: 팀·진영·시드(`runs/model-training/EX-174/collection`), foul-play `8f541f8`·3,000ms·병렬 4·스레드 1·2026-10 통계, 300턴/600결정, 경기당 1,200초 | 모델: v10rt(EX-167) → v11rt(EX-171 selected), 입력: v10 → v11(`render_v11`) | CPU, 포트 8100~8103, mem-guard 25 GB |

## 실행

- 실행기 `integration/foulplay/battle.py`(`STUDIES['EX-175']`), 서빙 `integration/foulplay/serve_v11.py`, 연결 실행 `scripts/foulplay-ep232 run EX-175`.
- 순서: mock(첫 쌍 2경기, 분모 밖) → prepare(소스·foul-play 사본·추론 자료·체크포인트 해시 동결, 문서 동결) → execute → export. 상한 10시간, 자동 재실행 없음.

## 결과

- mock(분모 밖) 2/2 정상·감사 통과. execute 00:09Z(09:09 KST) 시작, **2026-11-18 01:52Z(10:52 KST) 사용자 지시로 중지**("드라마틱한 성능 개선은 안 되는 것 같다"). 끝난 슬롯 60/128(정상 59, 미완료 1 `fp-b30-s1-a`: 경기당 1,200초 상한, EX-174에서도 146턴까지 간 대진). 진행 중이던 4슬롯(`fp-b14-s1-a`, `fp-b14-s1-b`, `fp-b26-s1-b`, `fp-b26-s2-b`)은 프로세스 종료로 결과 없이 끊겼다.
- execute 결과(`result.json`)·export·뷰어는 만들지 않았다. 끝난 판의 집계는 같은 요약기로 `runs/model-training/EX-175/partial-summary.json`에 남겼다. 정상 120 미만이므로 **판정 보류**다.

| 지표(끝난 판만) | 값 |
|---|---|
| v11rt 승/무/패 | 15/0/44 |
| 평균 점수(조합 클러스터 95%) | 0.254 [0.143, 0.370] |
| 같은 슬롯 − EX-174 v10rt | −0.051 [−0.211, +0.105](59슬롯; 나쁨 10, 나음 7, 같음 42) |
| 실패 기술 | 98/2,046 (4.79%), 29경기 |
| 테라 | 28경기, 결정당 1.22%(28/2,286), 테라 경기 6승 22패 |
| 결정 지연 | v11rt p50 2.83초(CPU), foul-play p50 7.50초·p95 8.36초 |

## 결론 및 후속 작업

- 중지 시점까지 같은 슬롯 차이의 구간이 0을 포함한다. v10rt보다 나아졌다는 근거는 없다(점 추정은 약간 낮음). 표본이 절반 이하라 퇴보 여부도 판정하지 않는다.
- 후속 실행은 따로 지시받는다.
