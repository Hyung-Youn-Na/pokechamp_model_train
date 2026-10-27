# D-192 — laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해)와 GPU1 학습·배틀

- 상태: Accepted
- 날짜: 2026-10-26

## 맥락

- EX-122 v2의 실패 Spikes 74회는 7경기에 몰려 있었다(m29-s1-b 29회, m29-s2-b 18회, m23-s2-a 12회). v1의 Thunder Wave 34회(한 경기 30회)와 Aurora Veil 20회(한 경기 17회)도 같은 구조다. 기술별 실패 수는 소수 경기의 반복이 좌우한다.
- 반복 구조: 배틀은 argmax로 선택한다. 실패해도 상태가 거의 바뀌지 않아 같은 선택이 이어진다.
- 사람 리플레이(2,793경기)의 Spikes 실패는 333/2,454회, 28경기였다.
  - 쓴 포켓몬은 Poison Heal Gliscor가 73%이고, 상대 활성도 Gliscor가 64%다.
  - 83%는 내 쪽에 해저드가 있어 교체 비용이 컸다. 68%는 내 포켓몬이 5~6마리 살아 있었다.
  - 장기전에서 버티며 턴을 넘기는 수다. 학습 자료에서 상대가 3층일 때 사람이 Spikes를 고른 비율은 12.4%(169/1,360)다.
- EX-122 반복 경기는 이 조건과 달랐다. 내 쪽 해저드가 없었고, Abyssal은 매 턴 공격했다. 그리고 답이 입력 안팎에 있었다.
  - m23(패): 지금 포켓몬의 Earthquake가 `dmg 41-49% 2HKO`(확률 0.258)였는데 Spikes(0.347)를 골랐다. 교체 후보 Latios는 87~103%였다.
  - m27: Ruination 2HKO. 교체 후보 Kyurem은 Ice Beam 134~158%였다.
  - m29: Iron Treads Ice Spinner 72~85%, Moltres(Earthquake 무효, Overheat 43~51%)
- v2 입력에서 빠진 정보는 두 가지다. Spikes 선택지에 실패 표시가 없고, 교체 선택지에 그 포켓몬이 상대에게 줄 피해가 없다.
- 행동을 바꾼 개입은 선택지에 계산값을 붙인 v2뿐이었다(EX-122). 지식 행(EX-124/126)은 행동을 바꾸지 못했다.
- **사용자 지시**(2026-10-26): 이 문제를 고쳐 GPU1을 쓰는 실험을 계획한다. v2 위에 올리고 EX-124와 비교한다.

## 결정

1. 렌더러 v4는 v2 네 모듈에 두 모듈을 덧붙인다(`laya-compact-v4[damage,fails,moves,out,speed,switch]`). v4 모듈이 없으면 v2와 바이트 단위로 같다.
   - `fails`: 공개 상태로 결과가 정해지는 기술 선택지에 `; fails`를 붙인다(Magic Bounce는 `; bounced`).
     - 규칙은 EX-126의 엔진 검증 규칙(`effect_knowledge.option_outcomes`, `effect_rules.json`)을 그대로 쓴다.
     - 공개되지 않은 특성·도구는 모든 경우가 같을 때만 표시한다. Tera Blast·Tera Starstorm의 테라 선택지는 표시하지 않는다.
   - `out`: 교체 선택지에 `; out b%`를 붙인다. 그 포켓몬의 공격기 중 상대 활성에 가장 큰 피해의 최댓값이다(v2 가정 세트, 고정 계산기).
     - 사전 측정(validation 512)에서 `out a-b%`는 5행이 선택지 48토큰을 넘었다. 계획에서 정한 순서대로 최댓값 형식으로 동결했다(512/512 들어감, 선택지 최대 48).
2. 사람 라벨은 바꾸지 않는다. 표시가 있으면 "알고 넘기는 턴"과 "모르고 누른 실패"를 모델이 구분할 수 있다.
3. 학습은 EX-124와 같은 설정과 테라 지식 행에 행동 행만 v4로 바꿔 GPU1에서 한다([EX-130](../experiments/EX-130-laya-v4-tera-training.md)).
4. 배틀은 EX-124 대 EX-130, Abyssal 256경기로 GPU1·8109에서 한다([EX-131](../experiments/EX-131-laya-v2t-v4t-battle256.md)). [D-191](D-191-no-offline-battle-gate.md)에 따라 오프라인 결과와 관계없이 실행한다. 실행은 [EP-215](../plans/EP-215-laya-renderer-v4.md)가 소유한다.

## 거절한 대안

- **실패 지식 행**: EX-126에서 행동을 바꾸지 못했다.
- **사람의 실패 라벨 가중치 낮추기**: 장기전의 턴 넘기기는 맞는 수일 수 있다. 모방 정의를 바꾸게 된다.
- **서빙에서 실패 선택지 제거 또는 반복 차단 규칙**: 모델 개선이 아니고, 턴 넘기기가 맞는 상황도 막는다.
- **v3 위에 올리기**: EX-129가 "퇴보를 배제하지 못함"(v3t 104-24 대 v2t 111-17, −0.055 [−0.125, +0.008])이었다. 비교 변수를 하나로 두기 위해 v2 위에 올린다.
- **`out a-b%` 범위 형식**: 선택지 한도를 넘는다.

## 근거와 한계

- 실패 표시는 공개 상태로 정해지는 경우만이다. Whirlwind/Roar의 교체 대상 없음, Wish 중복은 규칙 밖이다.
- `out`은 상대 가정 세트(EX-071 corpus 최빈 세트)와 최댓값 기준이다. 상대 반격과 속도는 기존 `hit`과 `faster/slower`가 맡는다.
- validation 512행 중 119행(23%)에 실패 표시가 붙는다(이미 깔린 Stealth Rock, 땅 타입에 Thunder Wave 등). 사람이 표시된 선택지를 고른 행은 3행(교체 예측 Earthquake 등)이다.
- 단일 시드 학습이고, 상대는 Abyssal 하나다.

## 영향

- `integration/laya_imitation/`에 `features_v4.py`, `compact_v4.py`, `data_v4.py`, `evaluation_v4.py`, `tests/test_compact_v4.py`를 추가한다.
- 설정, 학습 Spec `EX130`, 서빙 `--render v4`, CLI `v4`·`compare5`, 비교 배틀 `EX131`을 추가한다. `comparison.failed_moves`에 반복 지표(실패가 나온 경기, 같은 기술 연속 실패 3회 이상 경기와 승패)를 더한다. 기존 v1~v3 동작은 바꾸지 않는다.
- GPU1(`GPU-c7e2d577-…`)과 포트 8109를 쓴다.

## 증거

- 현재 대화의 분석: `EX-122/games/*/events.jsonl`, 원본 리플레이(`exports/replay-eligibility/gen9ou-local-v1`)
- 사전 측정(validation 512, 2026-10-26): 범위 형식은 507/512, 최댓값 형식은 512/512(전체 최대 945, head 470, 선택지 48)
- `tests/test_compact_v4.py`: EX-122 m23·m27·m29 입력에서 Spikes `fails`, Latios `out 103%`, Kyurem `out 158%`, Iron Treads `out 85%`
