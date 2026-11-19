# D-213 — laya 입력을 foul-play 추적·poke-engine 계산으로 전부 바꾼 렌더러 fp1과 처음부터 전체 학습

- 상태: Accepted
- 날짜: 2026-11-18

## 맥락

- Abyssal 점수는 v7t 이후 0.86~0.88로 포화됐다([EX-162](../experiments/EX-162-laya-v7t-v10t-battle256.md), [EX-168](../experiments/EX-168-laya-v10t-v10rt-battle256.md)). v4~v11은 정보를 조금씩 더했고 배틀에서 판본이 구별되지 않았다.
- foul-play 상대로는 포화되지 않는다. Blim 128 기준 v10rt 0.331([EX-174](../experiments/EX-174-laya-v10rt-vs-foulplay-blim128.md)), v11rt 0.254·v11rtc 0.235(EX-175·176, 중지)다.
- 확인한 사실(2026-11-18 대화, 코드와 poke-engine 직접 호출):
  - foul-play는 경기 전체 관측으로 상대 범위를 좁힌다. 스피드 범위, Scarf·Boots 추론, 데미지 역산, 불가능 특성·도구가 있다. 그다음 세트 단위 표본으로 숨은 정보를 채운다(`fp/battle/inference.py`, `fp/search/standard_battles.py`).
  - poke-engine 0.0.48은 데미지와 명중·급소·추가 효과·KO 여부를 확률 갈래로 계산한다. 쓰러지지 않는 데미지 난수는 평균값 하나로 뭉친다. Good as Gold, Magic Bounce, Multiscale, Knock Off 등을 반영한다. 실수치를 직접 받고 노력치·성격은 데미지에 쓰지 않는다. 체중 0, 테라 `typeless`, 모르는 특성 이름은 오류 없이 결과를 바꾼다.
  - laya의 상대 추정은 usage 칸별 주변 확률이다. 상대 스피드는 이론상 전 범위로 적고, 관측으로 좁히지 않는다(`features.py` `_opp_speed`, `features_v7.py`).
- **사용자 지시(2026-11-18 대화)**: 극적인 비교를 위해 입력을 foul-play 기반으로 전부 바꿔 학습한다. 처음부터 전체 학습하고, 기록 문장은 뺀다. 초안을 확인하고 "이대로 등록하고 구현 시작"을 지시했다.

## 결정

1. **렌더러 fp1**: v1~v11의 laya 고유 정보를 쓰지 않는다. 입력은 다음 셋으로만 만든다.
   - foul-play `Battle` 추적 결과(commit `8f541f8`, 사본 `.tools/foul-play/src`)
   - foul-play 표본 채우기(D-211 결정 3의 봉인 자료)
   - poke-engine 0.0.48 계산
   - 내용과 빼는 것은 [EX-177](../experiments/EX-177-laya-fp1-data.md)에 적는다.
2. **MCTS 점수와 방문 분포는 넣지 않는다.** 입력 비교가 아니라 탐색 결합이 되기 때문이다.
3. **출발점과 학습 설정은 EX-167과 같다**: `laya-typed-decisions@e929ae5c`, 3 epoch, soft-CE, 선택지 순서 섞기, lr, seed 0, 전체 배치 64, 2,048 / head 768 / 선택지 64, GPU 4장 DDP.
4. **테라 지식 57,143행은 뺀다.** v2~v10 형식으로 쓴 laya 고유 지식이기 때문이다. EX-167의 테라 held-out 지표는 비교하지 않는다.
5. **행·순서·라벨·분할**은 `v11-ladder-merged`(train 1,242,187, validation 1,024)와 같다. 잠긴 test 두 개(EX-071 1,024, EX-166 1,024)도 같다. 추적기가 국면을 만들지 못한 행은 빼고 비율을 보고한다.
6. **비교 기준은 v10rt(EX-167 selected)다.** 같은 출발점·행·학습량이다. 차이는 렌더러·테라 지식 행·기록 문장이 함께 바뀐 전체 구성 차이로 해석한다.
7. **판정은 하지 않는다**([D-191](D-191-no-offline-battle-gate.md), 보고 전용). 배틀은 EX-174 Blim 일정으로 foul-play와 128경기를 두고 같은 슬롯에서 v10rt와 비교한다([EX-179](../experiments/EX-179-laya-fp1-vs-foulplay-blim128.md)).

## 거절한 대안

- **v10rt에서 1 epoch 이어 학습**: v10 형식에 익숙한 가중치가 남아 입력 교체 효과가 흐려진다. 사용자가 처음부터 학습을 골랐다.
- **기록 문장(`streak`·이전 턴 경과) 유지**: foul-play에는 기록 텍스트가 없다. 사용자가 빼기로 했다.
- **MCTS 값을 입력에 넣기**: 결정당 약 7초라 158만 행에 쓸 수 없고, 탐색 결합이 된다.
- **laya 안에 추론만 다시 구현**: "전부 교체"가 아니다. fp1 결과를 본 뒤 따로 정한다.

## 근거와 한계

- 래더 리플레이의 내 세트는 추정값이다(EX-166). 데미지 역산과 스피드 비교가 내 실수치에 의존하므로 상대 세트가 잘못 지워질 수 있다. 실서빙에서는 내 세트가 정확하다.
- foulplay.cc 세트(2026-11-17 받음)와 Smogon 2026-10 통계를 그 이전 경기에도 쓴다. 메타 시점이 어긋난다.
- poke-engine은 Showdown을 다시 구현한 엔진이라 누락이나 차이가 있을 수 있다. foul-play 스피드 추론은 특성을 무시한다(코드 주석).
- foul-play는 GPL-3.0이다. 연구용 실행만 하며, laya-play 공개 배포에 넣는 것은 범위 밖이다.
- 단일 시드 학습이다. foul-play 탐색은 재현되지 않는다.

## 영향

- 새 코드: `integration/laya_fp1/`, `scripts/laya-fp1-ep234`
- [EP-234](../plans/EP-234-laya-fp1-foulplay-input.md), [EX-177](../experiments/EX-177-laya-fp1-data.md), [EX-178](../experiments/EX-178-laya-fp1-training.md), [EX-179](../experiments/EX-179-laya-fp1-vs-foulplay-blim128.md)
