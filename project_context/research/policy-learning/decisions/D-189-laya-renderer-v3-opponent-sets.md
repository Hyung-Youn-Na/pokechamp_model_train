# D-189 — laya 렌더러 v3(상대 세트 추론)와 래더 대비 학습(GPU0)

- 상태: Accepted
- 날짜: 2026-10-25

## 맥락

- 최종 목표는 Showdown 래더(사람 상대)다. 지금까지 평가 상대는 휴리스틱 봇 Abyssal 하나였고, v2+테라([EX-125](../experiments/EX-125-laya-v2-tera-battle256.md))가 111-17로 천장에 가깝다. LLM 기반 시도(GLM 5.3 API 서빙 등)는 Abyssal보다 약했다.
- 지금까지 효과가 확인된 개입은 선택지에 계산값을 직접 붙인 렌더러 v2뿐이다([EX-122](../experiments/EX-122-laya-v1-v2-battle256.md), +0.102).
  - 지식 행(테라 [EX-124](../experiments/EX-124-laya-v2-tera-knowledge-training.md), 효과 [EX-126](../experiments/EX-126-laya-v2-tera-effect-training.md))은 지식 정답률만 올리고 행동 선택은 바꾸지 못했다.
- 래더에서는 상대의 숨은 세트와 아직 보지 못한 기술이 중요하다. v2의 상대 정보에는 다음 한계가 있다.
  - `features._assumed`: 팀 파일 corpus의 종족별 최빈 세트 하나를 쓴다. 108종이고, 50종은 등장 1~2회다. 없는 종족은 `default` 세트로 처리한다.
  - 가정 세트의 기술과 테라는 쓰지 않는다.
  - 교체 위험(`_worst_seen`, 교체 피해)은 공개된 기술만 본다.
- **사용자 지시**(2026-10-25):
  - 래더를 최종 목표로 렌더러 v3를 먼저 진행한다.
  - 기준선은 v2+테라(EX-124)로, 테라 지식 행을 함께 학습한다.
  - 세트 통계는 2026-08 gen9ou-1695를 쓴다.
  - GPU 학습과 배틀은 별도 승인 없이 이어서 진행한다.

## 결정

1. 상대 세트를 Smogon usage stats(chaos gen9ou 2026-08, 1695)의 marginal 분포로 추론한다.
   - 공개된 도구, 특성, 테라 타입, 기술은 확정값으로 둔다.
   - 기술은 남은 칸(4 − 공개 수)에 맞춰 미공개 기술 포함 확률을 다시 맞춘다(독립 가정).
   - 자료는 `integration/laya_imitation/usage_sets_v3.json`으로 고정한다(1e-4 미만 항목, 0.001 미만 spread 제외).
2. 렌더러 v3는 v2 출력 위에 세 모듈을 덧붙인다(`laya-compact-v3[damage,moves,oppset,speed,speedp,switch,threat]`).
   - `oppset`: 상태에 `opp set:` 한 줄(미공개 도구·특성·테라 상위 2개, 유력 기술 상위 4개, 0.15 이상)
   - `speedp`: 속도 줄에 `first p` — 내 활성 포켓몬이 먼저 행동할 확률(spread × Scarf × 특성, 트릭룸 반전)
   - `threat`: 상태에 `opp threat:` 한 줄(포함 확률 0.3 이상 미공개 공격기 중 내 활성에 최대 피해). 교체 선택지의 v2 `hit`은 공개·유력 기술 중 큰 값으로 바꾸고, 미공개 기술에서 나오면 `?`를 붙인다.
3. 학습은 EX-124와 같은 설정과 테라 지식 행에 행동 행만 v3로 바꿔 GPU0에서 한다([EX-128](../experiments/EX-128-laya-v3-tera-training.md)).
4. Abyssal 256경기는 비퇴보 확인용으로 둔다([EX-129](../experiments/EX-129-laya-v2t-v3t-battle256.md)). EX-128 판정이 진행 조건을 충족할 때만 이어서 실행한다. 실행은 [EP-214](../plans/EP-214-laya-renderer-v3.md)가 소유한다.

## 거절한 대안

- **세트 정보를 지식 행으로 가르치기**: EX-124와 EX-126에서 지식 행은 행동 선택으로 이어지지 않았다.
- **EX-071 corpus로 조건부 세트 만들기**: 같은 팀 파일 corpus가 test 경기와 겹친다(test 팀 서명 43/438). 공개 정보로 후보를 좁히면 실제 세트가 복원될 수 있다.
- **교체 선택지에 위협 기술 이름과 확률 붙이기**: laya 선택지 한도 48토큰을 넘었다(validation 109/512행 초과). `hit` 값을 바꾸는 방식으로 줄였다(초과 0/512).
- **head 한도 확대**: 비교 변수가 두 개가 된다.
- **래더 실전 평가**: 외부 서버이므로 이번 결정 범위 밖이다. 별도로 승인받는다.

## 근거와 한계

- usage 자료는 래더 전체 집계라 우리 리플레이에서 만든 것이 아니고 정확한 세트를 담지 않는다. split 사이의 누수 경로는 "그 경기도 집계에 포함됨" 수준이다.
- 시기 불일치: 리플레이는 2023-01~2026-08이고 통계는 2026-08이다. 래더 목표와는 시기가 맞는다.
- 기술 포함 확률을 독립으로 다룬다. 실제 세트의 기술 조합 상관은 반영하지 않는다.
- 소모·제거된 도구는 스냅숏에서 "모름"과 구별되지 않는다.
- 테라 B 지식 행은 EX-124와 같은 v2 상태 텍스트다. 바뀌는 변수를 행동 행 렌더러 하나로 유지하기 위해 그대로 둔다.
- 자기 세트(`original_set`)의 corpus 대입 한계([D-185](D-185-laya-modular-renderer-v2.md))는 그대로다.
- Abyssal은 숨은 정보를 노리지 않는다. 그래서 EX-129는 개선이 아니라 비퇴보를 본다. 래더 효과는 이번 실험으로 입증되지 않는다.

## 영향

- `integration/laya_imitation/`에 `features_v3.py`, `compact_v3.py`, `usage_sets_v3.json`, `data_v3.py`, `evaluation_v3.py`, `tests/test_compact_v3.py`를 추가한다.
- 설정, 학습 Spec, 서빙(`--render v3`), CLI(`v3`, `compare4`), 비교 배틀(EX-129, 비열등 여유 `margin`)을 확장한다. 기존 v1·v2 동작은 바꾸지 않는다.
- GPU0(`GPU-4f27dd5a-…`)과 포트 8107을 쓴다. EX-127(GPU2·8108)과 분리된다.

## 증거

- 현재 대화의 사용자 지시와 승인된 계획
- v3 렌더 사전 측정(validation 512, 2026-10-25): 전체 최대 984, head 최대 453, 선택지 최대 46, 초과 0
- usage 출처: `https://www.smogon.com/stats/2026-08/chaos/gen9ou-1695.json` (sha256 `a929e77c…`, 2026-09-18 수집)
