# EX-187 — 강화학습 모델(EX-186) 대 foul-play, Blim 팀 64개 128경기(CPU)

- 상태: Paused
- 생성일: 2026-11-19
- 책임자: Claude Code
- 관련 exec plan: [EP-236](../plans/EP-236-laya-v11rtc-foulplay-distill-rl.md)
- 관련 decision: [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-215](../decisions/D-215-laya-foulplay-distill-then-rl.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-185](EX-185-laya-distill-vs-foulplay-blim128.md) 증류 모델, [EX-184](EX-184-laya-v11rtc-vs-foulplay-blim128.md) v11rtc, [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) v10rt(같은 슬롯)
- 기준 연구선: `research/model-training`

## 질문 및 목적

강화학습으로 다듬은 모델은 평가 Blim 일정에서 증류 모델보다 foul-play에게 더 이기는가?

## 가설 또는 qualification 목표

- **판정 없음(보고 전용)**. 정상 종료가 120/128 미만이면 "판정 보류"를 적는다.
- **보고 지표**: EX-185와 같다. 같은 슬롯 차이는 EX-185·EX-184·EX-174 대비로 적는다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 일정·상대·서빙 | EX-184와 같다(argmax) |
| laya | EX-186 `checkpoints/selected` |

## 실행

- 실행기: `scripts/laya-distill-ep236 battle EX-187`. 순서·상한은 EX-184와 같다.

## 결과

아직 없다.

## 결론 및 후속 작업

아직 없다.
