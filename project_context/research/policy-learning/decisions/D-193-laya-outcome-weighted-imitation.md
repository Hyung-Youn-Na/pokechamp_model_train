# D-193 — laya v2+테라 승패 가중 모방(GPU0 학습·배틀)

- 상태: Accepted
- 날짜: 2026-10-26

## 맥락

- laya 학습 목표는 사람이 고른 수의 soft-CE 모방이다. 같은 리플레이의 이긴 쪽과 진 쪽 결정을 같은 무게로 배운다.
- 행동을 바꾼 개입은 선택지에 계산값을 붙인 v2뿐이었다([EX-122](../experiments/EX-122-laya-v1-v2-battle256.md), +0.102 [0.023, 0.180]).
  - 지식 행(EX-124/126)과 v3 입력(EX-128)은 Abyssal 256경기에서 구별되지 않았다.
  - 각 결과: [EX-125](../experiments/EX-125-laya-v2-tera-battle256.md) +0.070, EX-127 −0.070, [EX-129](../experiments/EX-129-laya-v2t-v3t-battle256.md) −0.055
- 원본 리플레이(EX-071 `preparation/replays.jsonl`의 `raw_path`)에는 승자가 있다.
  - 2,793경기 중 2,791경기에 `|win|`이 있고, 2경기는 무승부다.
  - rating은 60경기에만 있어 쓰지 않는다.
- **사용자 지시**(2026-10-26): 남는 GPU0·GPU2로 에이전트를 개선할 방향을 찾고, 그중 승패·rating 가중 모방과 laya 직접 대결 평가를 고른다. 이 결정은 앞의 것만 다룬다.

## 결정

1. **가중치**: EX-124(v2+테라)의 모방 학습 행에 그 시점 쪽의 리플레이 승패 가중치를 준다.
   - 값: 이긴 쪽 1.0, 진 쪽 0.5, 무승부 0.75
   - 모방 학습 행 평균이 1이 되게 정규화한다. 실질 학습률을 EX-124와 같게 두기 위해서다.
   - 테라 지식 행, 보정 400행, validation은 가중하지 않는다.
2. **적용 방식**: soft-CE는 target에 선형이므로, 보정 분할 **뒤** 학습 항목의 target에 가중치를 곱한다.
   - laya 라이브러리(`laya.train`)는 바꾸지 않는다.
   - 분할 크기는 EX-124의 `split.json`과 같아야 한다.
3. **학습과 비교**:
   - 학습은 [EX-132](../experiments/EX-132-laya-v2t-outcome-weighted-training.md), GPU0이다.
   - 배틀은 EX-124 대 EX-132, EX-120 일정의 Abyssal 256경기로 [EX-133](../experiments/EX-133-laya-v2t-v2tw-battle256.md)에서 GPU0·8107로 한다.
   - [D-191](D-191-no-offline-battle-gate.md)에 따라 오프라인 결과와 관계없이 실행한다.
   - 실행은 [EP-216](../plans/EP-216-laya-outcome-weighted-imitation.md)이 소유한다.
4. **진 쪽 가중 0.5의 근거**: 승자만 남기는 필터(0)는 학습 행을 절반으로 줄인다. 그러면 학습량 효과와 섞이므로 0.5로 동결한다.

## 거절한 대안

- **rating 가중**: rating이 있는 경기가 60/2,793(2%)뿐이다.
- **승자만 학습(필터 BC)**: 학습 행 수가 절반이 되어 비교 변수가 둘이 된다.
- **결정 단위 가치 추정(advantage) 가중**: 가치 모델이 없다. 먼저 경기 단위 승패의 효과를 본다.
- **laya `rlcd` 손실 사용**: 사람 라벨과의 proper scoring이라 승패 정보를 쓰지 않는다.

## 근거와 한계

- 승패는 경기 전체의 결과다. 진 쪽의 좋은 수와 이긴 쪽의 실수를 구분하지 않는다.
- 사람 재현 지표(test NLL)는 승·패 전체가 기준이라, 가중의 목적과 어긋날 수 있다. 이긴 쪽과 진 쪽 행으로 나눠 보고한다.
- 단일 시드이고, 상대는 Abyssal 하나다. 직접 대결 평가는 별도 결정에서 다룬다.

## 영향

- `integration/laya_imitation/`
  - `outcome_weights.py`와 `evaluation_v2tw.py`를 추가한다.
  - `training.Spec`에 `weights`와 `same_split_as`를 추가하고, `EX132`를 정의한다.
  - `comparison.EX133`, 서빙 이름 `laya-v2tw`, CLI `weighted`·`compare6`, 테스트 `tests/test_outcome_weights.py`를 추가한다.
  - 기존 Spec과 Study의 동작은 바꾸지 않는다.
- 가중치 자료: `datasets/generated/laya-outcome-weights/v1`(봉인)
- GPU0(`GPU-4f27dd5a-…`)과 포트 8107을 쓴다.

## 증거

- 가중치 생성(2026-10-26): 학습 행 130,411개가 전부 매칭됐다.
  - 승 65,360행, 패 64,434행, 무 617행
  - 정규화 배율 1.3302(이긴 쪽 1.330, 진 쪽 0.665, 무승부 0.998)
  - validation은 승 253행·패 259행, test는 승 478행·패 546행이다.
- `tests/test_outcome_weights.py`: 로그 파싱, 평균 1, soft-CE가 가중치 배수로 커지는지 확인
