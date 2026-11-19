# D-212 — foul-play 대전을 Blim 팀 일정으로 바꾸고 EX-173을 중지

- 상태: Accepted
- 날짜: 2026-11-17

## 맥락

- [D-211](D-211-laya-foulplay-opponent.md) 결정 4는 EX-120 일정을 정했다. [EX-173](../experiments/EX-173-laya-v10rt-vs-foulplay128.md)은 16:28 KST(07:28Z)에 시작했다.
- 사용자 지시(2026-11-17 대화): "blimAI 팀으로 테스트". 이어진 질문에서 "EX-173 중단, blim으로 교체"와 "양쪽 다 blim, 팀 교환"을 골랐다.

## 결정

1. EX-173을 중지한다(Stopped). 중지 시점에 끝난 슬롯은 0개였다. 진행 중이던 4슬롯(`fp-m13-s1-a/b`, `fp-m30-s1-a/b`)은 결과 없이 끊겼다. 기록은 그대로 보존하고 집계하지 않는다.
2. 새 실험 [EX-174](../experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md)는 laya-play `teams_blim.json`(sha256 `286691e0…`)의 팀을 양쪽에 쓴다. EX-145와 같은 검사(고정 Showdown 검증기, 6마리 서명당 1팀, EX-120 유형 분류)를 거친 64팀을 digest 순서(시드 20261074)로 둘씩 묶어 32개 대진을 만든다. 대진마다 시드 2 × 팀 교환으로 128슬롯이다. 각 팀은 양쪽 봇이 두 번씩 잡는다.
3. 그 밖의 조건은 D-211과 같다(foul-play 설정, 봉인한 추론 자료, CPU 서빙, 포트, 메모리 상한, 300턴/600결정, 보고 전용).

## 거절한 대안

- **EX-173을 끝까지 돌린 뒤 이어서 실행**: 사용자가 중지를 골랐다.
- **EX-145처럼 고리(ring) 대진**: 팀 64개면 256슬롯이다. 128슬롯에 맞추려고 서로 겹치지 않는 대진으로 묶었다.

## 근거와 한계

- Blim 팀 64개 중 15개는 6마리 구성이 v10rt 학습 자료에 있다(`train_games` > 0). EX-120 팀과 달리 학습에서 빼지 않았다.
- 같은 슬롯의 Abyssal 기준선은 없다. 비교는 이 실험 안의 대진·유형별 점수로 한다.

## 영향

- `integration/foulplay/blim.py`(일정), `battle.py`의 `STUDIES`, `scripts/foulplay-ep232 run EX-174`
- [EP-232](../plans/EP-232-laya-foulplay-v10rt.md), [EX-173](../experiments/EX-173-laya-v10rt-vs-foulplay128.md), [EX-174](../experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md)

## 증거

- 대화(2026-11-17)의 선택, `runs/model-training/EX-174/collection/`(`selection.json`, `manifest.json`, 봉인), `runs/model-training/EX-173/ledger.jsonl`
