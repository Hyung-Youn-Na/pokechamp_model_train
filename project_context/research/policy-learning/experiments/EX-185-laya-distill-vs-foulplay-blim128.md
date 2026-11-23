# EX-185 — 증류 모델(EX-183) 대 foul-play, Blim 팀 64개 128경기(CPU)

- 상태: Stopped
- 생성일: 2026-11-19
- 책임자: Claude Code
- 관련 exec plan: [EP-236](../plans/EP-236-laya-v11rtc-foulplay-distill-rl.md)
- 관련 decision: [D-214](../decisions/D-214-laya-foulplay-primary-ladder-final.md), [D-215](../decisions/D-215-laya-foulplay-distill-then-rl.md), [D-191](../decisions/D-191-no-offline-battle-gate.md)
- 비교 대상: [EX-184](EX-184-laya-v11rtc-vs-foulplay-blim128.md) v11rtc, [EX-174](EX-174-laya-v10rt-vs-foulplay-blim128.md) v10rt(같은 슬롯)
- 기준 연구선: `research/model-training`

## 질문 및 목적

foul-play 탐색을 증류한 v11rtc는 같은 Blim 일정에서 foul-play에게 얼마나 이기는가? v11rtc·v10rt와 같은 슬롯에서 얼마나 다른가?

## 가설 또는 qualification 목표

- **판정 없음(보고 전용)**. 정상 종료가 120/128 미만이면 "판정 보류"를 적는다.
- **보고 지표**: EX-184와 같다. 같은 슬롯 차이는 EX-184와 EX-174 두 가지로 적는다. 교체·테라 선택 비율과 실패 기술 종류(랭크 최대·면역·실패)를 따로 적는다.

## 조건 및 변수

| 항목 | 조건 |
|---|---|
| 일정·상대·서빙 | EX-184와 같다 |
| laya | EX-183 `checkpoints/selected` |

## 실행

- 실행기: `scripts/laya-distill-ep236 battle EX-185`. EX-183 완료 뒤, EX-184와 겹치지 않게 돈다. 순서·상한은 EX-184와 같다.

## 결과

- 2026-11-20 15:29 KST(06:29Z) 사용자 지시("시간을 아끼기 위해 EX185는 조기 종료를 해주세요")로 중지. 끝난 슬롯 91/128(정상 89, 미완료 2: `fp-b30-s1-a`·`fp-b26-s2-b` 경기당 1,200초 상한). 진행 중이던 4슬롯은 결과 없이 끊겼다. export·뷰어는 만들지 않았고 집계는 `runs/model-training/EX-185/partial-summary.json`. 정상 120 미만이라 **판정 보류**.

| 지표(끝난 판만) | 값 |
|---|---|
| v11d 승/무/패 | 22/0/67 (0.247) |
| 같은 슬롯 − EX-184 v11rtc | −0.080 [−0.186, +0.024] (88슬롯; 나쁨 16, 나음 9) |

- 증류 모델이 v11rtc보다 낫다는 근거는 없고 나쁜 쪽으로 기울었다.

## 결론 및 후속 작업

아직 없다.
