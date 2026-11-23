# EX-201 — laya 엔진 가치 학습(EX-200) argmax 대 foul-play, Blim 128경기, 시간 제한 없음(CPU)

- 상태: Completed
- 생성일: 2026-11-22
- 책임자: Claude Code
- 관련 exec plan: [EP-239](../plans/EP-239-laya-engine-value-rerank-training.md)
- 관련 decision: [D-217](../decisions/D-217-laya-engine-value-rerank-training.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 기준 연구선: `research/model-training`

## 질문 및 목적

엔진 가치 target을 배운 모델이 foul-play 상대로 EX-196보다 나은가?

## 조건

- EX-198과 같다(v12 서빙, argmax, EX-174 Blim 128슬롯, foul-play 3초 × 4). 다만 시간 제한을 모두 해제한다. 경기 시간·턴 수·결정 수·실험 시간이 그 대상이고, Showdown 자체 규칙은 그대로 둔다.
- 같은 슬롯 기준선: [EX-202](EX-202-laya-v12-foe-vs-foulplay-unlimited.md)(EX-196, 같은 조건, 병행).

## 결과

2026-11-22T11:09Z mock 통과(1-1), 11:14Z 실행, 14:38Z export, 14:50Z lane 종료(`runs/model-training/EX-201/report.md`, 뷰어 `exports/battle_viewers/ex201`). 엔진 panic·미완료는 없었다.

- 128 완료. 48승 80패, 0.375, 조합 클러스터 95% [0.281, 0.477].
- 같은 슬롯 EX-202(EX-196, 제한 없음) 대비 +0.055 [−0.040, +0.156] (127슬롯; 나쁨 22, 나음 29, 같음 76).
- 같은 슬롯 EX-174 v10rt 대비 +0.039 [−0.070, +0.150].
- 결정 지연 p50 1.99초, p95 4.24초. foul-play 결정 7,220개, 테라 사용 경기 117.

## 결론 및 후속 작업

- EX-200은 foul-play 상대 점수가 지금까지 laya 판본 중 가장 높다(0.375). 그러나 대조군과의 같은 슬롯 차이는 신뢰구간이 0을 걸쳐 개선이 입증되지는 않았다(보고 전용, D-191).
- 사용자 지시로 공식 래더 [EX-203](EX-203-laya-engine-value-ladder.md)을 병행했다.
