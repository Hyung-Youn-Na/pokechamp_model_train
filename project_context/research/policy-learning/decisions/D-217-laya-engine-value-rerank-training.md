# D-217 — foul-play 엔진 평가로 laya 후보 순위를 다시 매긴 target 학습

- 상태: Accepted
- 생성일: 2026-11-22
- 책임자: Claude Code
- 관련: [D-216](D-216-laya-opponent-prediction-one-turn-read.md), [EX-196](../experiments/EX-196-laya-v12-foe-training.md), [EX-197](../experiments/EX-197-laya-one-turn-read-vs-foulplay.md), [EX-198](../experiments/EX-198-laya-v12-foe-argmax-vs-foulplay.md), [D-191](D-191-no-offline-battle-gate.md)

## 맥락

EX-197(대국 중 한 턴 읽기)은 foul-play 상대 성적을 구별되게 바꾸지 못했다(EX-198 대비 +0.028 [−0.081, +0.132]). 한 턴 점수는 자체 설계였고, poke-engine 0.0.48 `src/genx/evaluate.rs`(foul-play MCTS의 말단 평가)보다 랭크·상태이상을 몇 배 작게 매겼다. 해저드·도구·대타·벽·테라도 없었다. 서빙 포화로 결정이 느려져 긴 경기 15개가 1,200초 한도에 잘렸다.

## 결정

사용자 지시(2026-11-22 대화: "해당 점수를 기준으로 학습을 다시 진행 할 수 있을까요?"에 대한 답 뒤 "EX-197 끝나면 그 순서대로 계획 등록하고 진행해주세요", "그리고 성능을 보기 위한 실험은 시간 제한을 모두 해제하고 테스트 해주세요")에 따른다.

1. **점수**: foul-play 엔진의 평가 함수를 그대로 쓴다. 같은 판(0.0.48, `terastallization` 기능)을 따로 빌드하고 `evaluate`만 Python에 연다. foul-play의 venv와 소스는 바꾸지 않는다. 빌드가 안 되면 Python으로 옮기고 대조 검증한다.
2. **target**: 사람 래더 경기(held-out 400경기 밖)의 turn_action 결정마다 laya(EX-196) 후보를 정한다. 후보는 p ≥ 0.5 × 최대 p인 행동이고 최대 3개다. 후보마다 한 턴 가치를 구한다. 상대 분포는 EX-196 q, 상대 세트는 foul-play 표본이고, 값은 엔진 평가 점수 변화의 기대값이다. 후보 묶음의 laya 확률 합을 softmax(가치/τ)로 후보끼리 다시 나눈다. 후보 밖은 laya p를 그대로 둔다. 이것이 soft target(`gold`)이다.
3. **학습**: EX-196에서 1 epoch 이어 학습한다. target 행에 사람 모방 행과 상대 예측 행을 섞어 원래 능력을 붙잡는다.
4. **평가**: 성능 평가 대전은 시간·턴·결정 수·실험 시간 제한을 모두 해제한다(Showdown 자체 규칙은 그대로). 같은 조건으로 EX-196 argmax 대조군도 다시 돌린다.

- 단계 사이에 사용자 확인을 기다리지 않는다. 큰 문제(누수, 학습 실패, 서빙 오류, 자원 충돌)가 생기면 멈추고 기록한다.
- 모든 배틀 결과는 보고 전용이다(D-191).

## 결과

아직 없다.
