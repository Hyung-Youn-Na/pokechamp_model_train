# EX-198 — laya v12 + 상대 예측(EX-196) argmax 대 foul-play, Blim 128경기(CPU)

- 상태: Completed
- 생성일: 2026-11-22
- 책임자: Claude Code
- 관련 exec plan: [EP-238](../plans/EP-238-laya-opponent-prediction-one-turn-read.md)
- 관련 decision: [D-216](../decisions/D-216-laya-opponent-prediction-one-turn-read.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

EX-197(한 턴 읽기)의 효과를 모델 변화와 나누는 비교군이다. 상대 예측을 함께 학습한 EX-196 모델을 읽기 없이 argmax로 두면 EX-193(EX-192 argmax)과 달라지는가?

## 조건

- EX-193과 같다(`laya_v12.battle_v12`, v12 서빙, argmax, EX-174 Blim 128슬롯). 모델만 EX-196 selected로 바꿨고, 포트는 8104~8107이다. EX-197과 동시에 돈다(CPU 128코어, 동시 경기 8개).
- 같은 슬롯 기준선: EX-193. 보고서에 EX-174 같은 슬롯 차이도 넣는다.

## 결과

보고: `runs/model-training/EX-198/report.md`, 뷰어 `exports/battle_viewers/ex198/index.html`. 실행 2026-11-21T23:27Z~2026-11-22T03:22Z.

- 40승 82패, 미완료 6(경기 1,200초 한도, 마지막 턴 176~225). 평균 0.328 [0.238, 0.417].
- 같은 슬롯 차이: EX-193 대비 −0.008 [−0.118, +0.105](122슬롯), EX-174 대비 0.000 [−0.111, +0.108]. 구별되지 않는다.
- 서빙 응답 중앙값 2.5초(EX-193 2.1초).

## 결론 및 후속 작업

상대 예측을 함께 배운 것만으로는 argmax 성적이 달라지지 않았다. EX-197의 비교 기준으로 쓴다.
