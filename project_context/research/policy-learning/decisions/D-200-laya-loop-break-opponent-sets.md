# D-200 — laya 손해 루프 탈출(학습 가중·결정 규칙)과 상대 세트 추정 v7 야간 동시 실험

- 상태: Accepted
- 날짜: 2026-10-31

## 맥락

- **사람 대전**(`/workspace/data/NHJ-20261101`, v6ht 3판·v6st 3판, 봇 2승 4패, NHJ 팀은 5판 동일)에서 두 약점이 보였다.
  1. **손해 루프**: 같은 상대 활성에게 같은 기술을 3턴 이상 쓴 구간이 7개다. 5개는 Poison Heal Gliscor(Protect·Toxic·Spikes), 2개는 Roost(Zapdos, Dragonite) 상대다. 예: 168번 T31~37 Iron Crown Tachyon Cutter ×7 대 Dragonite Roost ×5(상대 HP 67→100, 이후 DD·EQ로 기절), 166번 Tyranitar Ice Beam ×8 대 Zapdos Roost(내 HP 87→24).
     - 반복할수록 1위 확률이 오른다(Ice Beam 0.27→0.73, Tachyon Cutter 0.44→0.74). 반대로 차선은 내려간다(Ogerpon Knock Off 0.30→0.10).
     - 답이 되는 수는 후보에 있었다. "직전 2턴 같은 기술 + 상대 HP 순감소 10%p 미만이면 그 기술 제외, 확률 0.10 이상 차선" 규칙을 이 로그에 오프라인으로 적용하면 24결정에서 작동한다(대안 없음 4). 고른 수는 Gliscor에 Knock Off(Toxic Orb 제거) 5회, Dragonite Roost 루프에 Calm Mind 4회 등이다.
  2. **미공개 상대 세트**: Gholdengo Scarf Trick(usage item `choicescarf` 0.40, Trick 0.41)에 4판에서 당했다(168 T11, 178 T3, 179 T8, 177 T42). v4~v6 입력은 v2를 바탕으로 이어져 v3 `oppset`이 없다. v6 입력에서 미공개 Gholdengo는 `ability ? | item ?`뿐이다. v3 `oppset`도 기술을 4개까지만 보여 Trick(5위)은 빠진다. 활성 상대만 다루고 벤치는 다루지 않는다.
  3. **부수 결함**: `effect_knowledge.option_outcomes`는 어느 쪽이든 `typechange`(Protean·Libero 등)가 있으면 실패 표시를 모두 끈다. 179번 T14~16에서 Meowscarada가 Spikes 3층(입력에 `opp side: spikes3`)에서 Spikes를 3번 실패했다.
- **이전 결과**: EP-221에서 과거 턴 입력(v6s 반복 표시·v6h 긴 기록)은 반복을 줄이지 못했다(사람이 바꾼 행의 같은 기술 확률 0.288 → 0.306·0.311). EX-145(laya-play 팀 296슬롯)에서 v6st는 v5t 대비 비퇴보, v6ht는 퇴보를 배제하지 못함이다.
- **학습 자료 근거**: v6s 학습 행 130,327개 중 내 활성 반복 표시가 있는 행은 4,547개다. 그중 상대 HP가 10%p 이상 줄지 않은 정체 행은 2,962개이고, 사람이 다른 수를 고른 행은 1,456개(49%)다.
- **사용자 지시**(2026-10-31): 취침 중 GPU 4개로 최대한 많은 실험을 승인 없이 진행한다.

## 결정

세 질문을 GPU0~3에서 동시에 실험한다. 모두 D-191에 따라 오프라인 결과로 배틀을 거르지 않는다. 기존 렌더러·사실값 파일(`serving.V6_RENDER_FILES`, `effect_knowledge.py` 포함)은 바이트 단위로 바꾸지 않는다. 새 동작은 새 파일에만 둔다.

1. **루프 탈출 가중 학습 v6sl**(EX-146 학습 GPU1 → EX-147 배틀 GPU1·8109):
   - EX-141(v6s)과 같은 자료·분할·설정이다. 바뀌는 것은 모방 train 행 가중치뿐이다.
   - 정체 루프 행 중 사람이 반복 기술이 아닌 수를 고른 행(1,456행)에 원가중 4, 나머지 1을 주고 평균 1로 맞춘다. 정체 루프 행은 `streak` 표시가 있고 그 HP 열의 마지막 값이 첫 값 − 10 이상인 행이다. 테라 지식 행은 1이다.
   - 평가는 EX-141과 같은 잠긴 test 비교와 반복 확률이다. 배틀은 EX-120 일정 256경기에서 v6st 대 v6slt를 같은 실행으로 비교한다.
2. **루프 결정 규칙**(EX-148, 재학습 없음, GPU2·8108 v6st, GPU3·8106 v6ht):
   - 서빙 결정 단계에서 내 활성의 직전 연속 기술(`compact_v6.streak`, 4턴 창)이 n ≥ 2이고, 그동안 상대 HP가 10%p 이상 줄지 않았으면 그 기술(일반·테라)을 뺀다. 남은 선택지 중 정책 확률 0.10 이상인 것이 있으면 그중 최고를 고른다. 없으면 원래 argmax를 유지한다. 모델 분포는 `model_probabilities`로 함께 남긴다.
   - 배틀은 EX-120 일정에서 `laya-v6st-lp`·`laya-v6ht-lp`만 둔다. 같은 체크포인트의 결정적 경로인 EX-143 v6st와 EX-144 v6ht의 같은 슬롯과 비교한다(EX-139 방식).
   - 오프라인: EX-141 잠긴 test 예측에서 규칙이 작동하는 행의 사람 일치율을 argmax와 비교한다(재추론 없음).
3. **상대 세트 추정 v7**(EX-149 학습 GPU0 → EX-150 배틀 GPU0·8107):
   - v6s 모듈 전부 + 새 `oppset2` 모듈 + Protean·Libero 행의 타입 무관 실패 표시 보정. 시작 모델과 설정은 EX-141과 같다.
   - `oppset2`는 v3 세트 추정(EX-128 usage 고정본 `usage_sets_v3.json`)을 다음처럼 고친다.
     - 활성 상대: 미공개 칸만 표시한다. 기술은 개수 제한 대신 포함 확률 0.25 이상을 최대 6개 보인다. 아이템은 공개·제거 상태(v5 `item_state`)를 존중하고, 미공개일 때만 usage 분포를 쓴다.
     - 판을 뒤집는 요소(Choice Scarf, Trick·Switcheroo, Focus Sash 등)는 확률 0.15 이상이면 `watch` 줄에 따로 보인다.
     - 벤치 상대: 미공개 아이템·기술을 한 줄 요약(아이템 1위, 기술 상위 3개, 0.30 이상)으로 붙인다.
   - 길이는 전체 1,024 / head 512 / 선택지 48이다. validation 사전 측정에서 초과 행이 0.5%를 넘으면 벤치 요약을 줄인다(사전 등록 순서: 벤치 기술 3→2개, 그래도 넘으면 벤치 요약 제거).
   - 평가는 EX-141 대비 잠긴 test 같은 행 차이다. 배틀은 EX-120 일정 256경기에서 v6st 대 v7t를 같은 실행으로 비교한다.
4. **판정**: 배틀 판정은 EX-143과 같은 비퇴보 기준(margin 0.05, 조합 클러스터 bootstrap)과, 결정 규칙은 EX-139와 같은 개선·악화·구별되지 않음이다. 루프 지표(5턴 이상 반복 수, 정체 루프 수)를 함께 보고한다.
5. **실행 순서와 코드 동결**: 배틀 실행 중에는 `integration/laya_imitation`을 수정할 수 없다(`source changed` 검사와 worker import). 그래서 모든 코드를 먼저 끝내고 단위 검사를 통과시킨 뒤 배틀을 시작한다. 학습은 코드 작업 중에도 먼저 시작할 수 있다.
6. 학습 시간 상한은 EX-141과 같이 없다. 자동 재실행은 없고, 단계가 실패하면 그 레인만 멈춘다.

## 거절한 대안

- **반복 기술 확률을 temperature로 섞기**: 루프에서는 1위 확률이 0.7까지 올라가 temperature로는 거의 바뀌지 않는다. 확률이 낮은 다른 결정까지 흔든다.
- **위협 거부권(추정 세트의 확정 1타 위험으로 교체 거부)**: 세트 추정이 입력에 없으면 규칙이 혼자 판단해야 한다. v7 결과를 본 뒤 정한다.
- **v7을 v5 위에 쌓기**: 사용자가 실제로 쓰는 모델은 v6st다. EX-145에서 v6st는 v5t 대비 비퇴보였다. v6st 대비 변수 하나(세트 추정, Protean 보정 포함)로 둔다.
- **`effect_knowledge.py` 직접 수정**: v4~v6 서빙의 렌더러 동일성 검사가 깨진다. v7 전용 파일에서 보정한다.
- **v6h 계열 가중 학습**: 학습이 약 26시간 걸려 이번 밤에 배틀까지 끝나지 않는다.

## 근거와 한계

- 결정 규칙은 Abyssal 상대에서 거의 작동하지 않을 수 있다(EX-145 v5t 296경기 중 3턴 이상 반복 7회). 그 경우 배틀은 비퇴보 확인에 가깝다. 사람 대전에서의 효과는 이후 사람 테스트와 시나리오 대전으로 본다.
- 가중 학습의 원가중 4는 사전에 정한 값이다. 다른 값은 시험하지 않는다.
- usage 고정본은 2026-08(1695)이다. 세트 추정은 기술 독립 가정을 유지한다(조합 상관 없음).
- 단일 시드다.

## 영향

- 새 코드: `loop_weights.py`, `loop_decision.py`, `features_v7.py`, `compact_v7.py`, `data_v7.py`, `evaluation_v7.py`, `loop_battle.py`, `tests/test_loop_v7.py`
- 수정: `config.py`, `training.py`(Spec), `serving.py`·`comparison.py`·`battle.py`(모델 이름), `cli.py`, `scripts/laya-imitation-ep223`
- 자료: `laya-loop-weights/v1`, `laya-compact-features/v7`, `laya-compact-imitation/v7-all`
