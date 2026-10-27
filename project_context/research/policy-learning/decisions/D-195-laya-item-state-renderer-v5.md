# D-195 — laya 렌더러 v5(상대 아이템 상태·상태 카운터)와 학습·배틀

- 상태: Accepted
- 날짜: 2026-10-27

## 맥락

- **사람 대전**(`/workspace/data/NHJ-20261027`, v2t, 4경기 1승 3패, 그 1승은 상대 무응답): 23번·25번에서 Air Balloon Gholdengo에게 지면 기술을 고른 결정이 9회였다(Clodsire 5, Great Tusk 4, 확률 0.52–0.75). 실제로 쓰인 8회가 모두 무효였고(23번 T8은 쓰기 전에 기절), 그사이 Gholdengo가 Nasty Plot +6을 쌓아 두 경기 모두 6:0으로 졌다.
  - 같은 129결정을 다시 추론했다. v2t는 기록과 같았고(최대 차이 1.2e-6, 선택 129/129 일치), v4t는 실패 표시(`; fails`) 덕분에 9회 모두 지면 기술을 피했다. 그러나 대신 Bulk Up·Stealth Rock을 골랐고, 풍선을 터뜨릴 Ice Spinner(0.12–0.18)나 Unaware Clefable 교체는 고르지 못했다.
- **구조 결함 1 — 제거된 상대 아이템을 미공개와 구분하지 못한다.**
  - 파서는 `-enditem`을 보고 poke-env 아이템을 `None`으로 바꾼다(`pokemon.py` `end_item`). 상대 아이템은 공개 집합에 있을 때만 값을 쓰므로(`replay.py` `_pokemon`) 제거된 아이템은 `item: None`이 되어 미공개와 같다.
  - 스냅샷 스키마는 최근 4턴 기록만 허용한다(`schema.py`). 그래서 제거 사실은 렌더러의 최근 2턴 기록(`opp lost …`)에만 잠깐 남는다.
  - 학습 자료(EX-071 파서)와 실전 플레이어(같은 파서 bridge)가 같은 스냅샷을 쓰므로 v1~v4 모든 버전에 해당한다.
  - 원본 리플레이 추정: 학습 130,411행 중 약 25,983행(19.9%)에서 상대 활성의 아이템이 이미 제거된 상태였다(Knock Off 14,392, Air Balloon 2,653, 기타 소모 8,938). 그중 25,696행이 `item ?`로 표시됐다. 정확한 수는 재파싱에서 확정한다.
- **구조 결함 1b — 효과로 공개된 아이템도 미공개로 남는다**(구현 중 확인, 2026-10-27).
  - 파서는 `-item`, `-enditem`, Life Orb 반동만 공개로 처리한다(`replay.py` `public_item`).
  - `[from] item: Leftovers` 회복이나 Black Sludge·Rocky Helmet 같은 효과로 공개된 아이템은 계속 `item ?`다. validation 상대 아이템 표시 2,367개 중 `leftovers`는 1개였다.
  - 사람 대전 26번에서 상대 Kingambit은 매 턴 Leftovers로 회복했지만 스냅샷에서는 내내 `item: None`이었다.
- **구조 결함 2 — 미공개 아이템 자리를 가정 세트의 Air Balloon으로 채운다.**
  - v2 피해 계산은 `item=mon['item'] or a['item']`이다(`features._opp_spec`). Gholdengo·Heatran·Tinkaton·Excadrill의 가정 세트(`assumed_sets_v2.json`) 아이템이 Air Balloon이다.
  - 그래서 아이템을 모르거나 이미 터진 경우에도 지면 기술이 `x2 …; dmg 0-0%`로 표시된다. 사람 대전 23번 T13: T10에 풍선이 터진 Gholdengo에게 Earth Power가 `dmg 0-0%`였다.
  - 학습 자료: 풍선이 공개된 상대에 지면 기술이 있는 행은 357행이고, 사람이 지면 기술을 고른 비율은 3.4%다. 반면 미공개인데 `x2; dmg 0-0%`로 표시된 행은 1,470행이고(Gholdengo 965), 사람이 지면 기술을 고른 비율이 36.0%다. 모델은 "0% 표시를 무시해도 된다"는 신호를 4배 더 많이 받았다.
- 타입 배율 표시(`x2`)는 타입표만 보고 계산해 공개된 Air Balloon·Levitate를 반영하지 않는다(`features.py` `dex_v2.multiplier`).
- **같은 부류의 다른 누락**(2026-10-27 점검): 공개 정보인데 스냅샷에 칸이 없거나 렌더러가 버리는 상태가 더 있다.
  - 스냅샷에 칸이 없음
    - 잠듦 턴 수와 Rest 여부: 내 활성 0.5%, 상대 활성 0.8% 행. EX-131 v2t의 Sleep Talk 실패 43회(사용 100회) 중 26회가 그 턴에 깨어나서 실패했다(v4t는 64회 중 실패 43회, 그중 깨어남 6회).
    - 맹독 카운터: 내 활성 7.2%, 상대 활성 7.7% 행
    - 날씨 시작 턴: 10.0% 행
  - 스냅샷에는 시작 턴이 있는데 렌더러가 이름만 냄
    - 필드(테라인·Trick Room): 3.1% 행
    - 벽(Reflect·Light Screen·Aurora Veil): 1.7% 행
  - 효과(taunt·encore 등)의 지속 값은 스냅샷에서 모두 0이다. 각 0.3~1.7% 행이라 범위 밖에 둔다.
  - 깨어 있는데 Sleep Talk를 쓴 실패(v2t 17회, v4t 37회)는 입력이 맞았던 모델 오류라 이 결정과 무관하다.
- **사용자 지시**(2026-10-27): 미공개·Knock Off 제거·풍선 터짐을 구분하도록 고치는 학습 계획을 세운다. 사용자 선택은 다음과 같다.
  1. 미공개 아이템은 면역 아이템(Air Balloon)만 가정하지 않는다.
  2. v4 위에 올린다.
  3. 같은 재파싱에서 상태 카운터도 넣고, 렌더러에 별도 모듈로 표시한다(선택지 A).

## 결정

1. **스냅샷**: 상대 포켓몬에 선택 필드 `item_state`를 더한다. `{"state": "unknown"|"held"|"removed", "item": <id|null>, "cause": "knockoff"|"popped"|"consumed"|"other"|null}`
   - 공개된 사실만 쓴다. 다음 경우는 held로 기록한다.
     - `-item`
     - 인자의 `[from] item: X`(보유자는 `[of]`가 있으면 그쪽, 없으면 첫 인자)
     - `-activate`·`-block`·`-immune`·`-fail`의 `item: X`
   - `-enditem`이면 removed로 기록한다. 기존 `item` 필드의 공개 규칙은 바꾸지 않는다. cause는 다음과 같이 정한다.
     - `[from] move: Knock Off` → knockoff
     - Air Balloon → popped
     - `[eat]`, 소모형 아이템 → consumed
     - 그 외(Thief·Covet 등) → other
   - Trick·Switcheroo는 기존대로 `-item`이 새 아이템을 공개한다.
   - 포켓몬마다 상태 카운터 선택 필드 `status_counter`와 `status_source`를 더한다.
     - 잠듦: 잠든 뒤 행동을 시도한 횟수를 센다. Showdown은 잠든 상태의 모든 시도(Sleep Talk·Snore 포함)에 `cant|…|slp`를 출력하므로 이것만 센다. `status_source`는 Rest로 잠들었으면 `rest`다.
     - 맹독: 지금 등장한 뒤 맹독 피해를 받은 횟수를 센다. 교체하면 0으로 초기화된다.
   - 스냅샷 최상위에 선택 필드 `weather_turn`(날씨 시작 턴)을 더한다.
   - `SNAPSHOT_KEYS`와 `MON_KEYS`는 바꾸지 않는다. 새 필드는 모두 있으면 보존하는 선택 키다. v1~v4 렌더러는 이 키들을 읽지 않으므로 출력이 바이트 단위로 같아야 한다.
2. **렌더러 v5**는 v4에 `items`와 `counters` 두 모듈을 더한다(`laya-compact-v5[counters,damage,fails,items,moves,out,speed,switch]`). 두 모듈이 없으면 v4와 바이트 단위로 같다.
   - `counters`
     - 잠듦은 `slp t<n>`(Rest면 `slp t<n> rest`), 맹독은 `tox t<n>`으로 표시한다.
     - 날씨·필드·벽은 지난 턴 수를 붙인다(예: `weather snow t3`, `grassy_terrain t2`, `reflect t1`). 지속 연장 아이템을 알 수 없으므로 남은 턴이 아니라 지난 턴으로 쓴다.
     - 형식은 validation 512 길이 실측 뒤 동결한다.
   - `items`
     - 상대 아이템 표시
       - 미공개: `item ?`
       - 들고 있음: `item <id>`
       - 제거됨: `item none (knocked off <id>)` · `item none (popped)` · `item none (used <id>)`
       - 형식은 validation 512 길이 실측 뒤 동결한다.
     - 피해 계산
       - 제거된 아이템은 아이템 없음으로 계산한다.
       - 미공개 아이템은 가정 세트의 아이템을 쓰되, Air Balloon만 쓰지 않는다. 가정 세트에 풍선이 있으면 지면 기술 텍스트에 `balloon?`을 붙인다.
     - 타입 배율 표시: 공개된 Air Balloon(들고 있음)·Levitate 대상에게 지면 기술은 `x0`으로 표시한다.
   - 실패 규칙(`effect_knowledge.py`, `effect_rules.json`)은 수정하지 않는다. 입력만 바꾼다. 제거 상태를 규칙 입력에서 "아이템 없음"으로 줄 수 있으면 그렇게 하고, 지원하지 않으면 그대로 두고 기록한다.
3. **학습 자료**: EX-071 원본 리플레이를 수정한 파서로 다시 파싱해 새 선택 필드(`item_state`, `status_counter`, `status_source`, `weather_turn`)를 얻는다.
   - 기존 스냅샷 필드는 EX-071 `prepared`와 전부 같아야 한다(전수 비교).
   - 사람 라벨과 분할은 바꾸지 않는다. 테라 지식 행은 EX-130과 바이트 단위로 같다.
4. **학습**은 EX-130과 같은 설정에서 렌더러만 v4 → v5로 바꿔 GPU0에서 한다([EX-136](../experiments/EX-136-laya-v5-tera-training.md)).
5. **배틀**([D-191](D-191-no-offline-battle-gate.md)에 따라 오프라인 결과와 관계없이 실행한다)
   - [EX-137](../experiments/EX-137-laya-v4t-v5t-battle256.md): v4t 대 v5t, Abyssal 256경기, GPU0·8107. 변수 하나의 효과를 본다.
   - [EX-138](../experiments/EX-138-laya-head-to-head-v5t.md): v5t 대 v2t·v4t 직접 대결 256경기, GPU2·8108. 현재 최고 모델과 직접 비교한다.
   - 실행은 [EP-218](../plans/EP-218-laya-renderer-v5-item-state.md)이 소유한다.

## 거절한 대안

- **기록 창 늘리기**(4턴 → 전체): 입력 길이가 커지고 1,024 한도를 넘는다. 사실 하나를 위해 기록 전체를 넣을 이유가 없다.
- **가정 아이템 전부 쓰지 않기**: Choice·Assault Vest 가정으로 계산되던 피해가 모두 바뀌어 변수가 커진다(사용자 선택).
- **v2 위에 올리기**: 비교 변수가 하나라 깔끔하다. 하지만 사용자가 실패 표시를 포함하는 v4를 선택했다. v2t와의 비교는 EX-138 직접 대결과 EX-125 같은 슬롯 결과로 보완한다.
- **서빙에서 지면 기술 차단 규칙**: 모델 개선이 아니다. 교체를 예측한 지면 기술처럼 맞는 수도 막는다.
- **풍선 지식 행 추가**: 지식 행은 행동을 바꾸지 못했다(EX-124·126).
- **카운터는 스냅샷에만 넣고 렌더링은 다음 실험으로(선택지 B)**: 이번 실험의 변수는 하나로 유지된다. 하지만 사용자가 같은 재학습에 함께 넣는 쪽을 골랐다. 모듈을 나눠 두어 나중에 분리 실험을 할 수 있다.

## 근거와 한계

- 제거 추정치(19.9%)는 원본 로그 줄 단위 추정이다. 정확한 수는 재파싱이 확정한다.
- 미공개 상태는 여전히 가정에 기댄다. Air Balloon 이외의 면역 아이템은 범위 밖이다.
- 두 모듈(`items`, `counters`)을 함께 바꾸므로 배틀 차이를 어느 한쪽 효과로 나누지 않는다. 오프라인 보고는 상태별 행으로 나눠 낸다.
- 효과 지속 턴, 특성 무효화·교체, 렌더 기록 창(2턴)은 범위 밖이다.
- 사람 대전 근거는 상대 한 명, 같은 팀, 4경기다. 단일 시드 학습이고, 배틀 상대는 Abyssal과 laya다.

## 영향

- `integration/pokechamp/imitation/replay.py`, `schema.py`: 선택 필드 `item_state`, `status_counter`, `status_source`, `weather_turn`. 모든 laya 모델의 실전 입력에 더해지지만 v1~v4 렌더러 출력은 같다(검사로 보장). 요청 본문 해시(`input_sha256`)는 바뀐다.
- `integration/laya_imitation/`: `item_state.py`, `features_v5.py`, `compact_v5.py`, `data_v5.py`, `evaluation_v5.py`, `tests/test_compact_v5.py`, 설정, 학습 Spec `EX136`, 서빙 `--render v5`, CLI `v5`·`compare7`·`h2h3`
- GPU0(`GPU-4f27dd5a-…`)·포트 8107, GPU2(`GPU-c79ce3fd-…`)·포트 8108

## 증거

- 사람 대전: `/workspace/data/NHJ-20261027/NHJ-20261027/battle-gen9ou-{23..26}`, 재추론 결과 `/root/.claude/projects/-ref-laya/nhj_v4_replay.json`
- 코드: `replay.py:170`(상대 아이템 공개 조건), `schema.py:68`(4턴 기록), `features.py:262`(가정 아이템), `features.py:295`(배율), `assumed_sets_v2.json`(Gholdengo `airballoon`)
- 자료 집계(2026-10-27, `v2-all` train): 공개 풍선 + 지면 357행·3.4%, 미공개 `x2; dmg 0-0%` 1,470행·36.0%, 제거 추정 25,983행
- 상태 카운터 집계(같은 자료): 잠듦 내 705·상대 1,072행, 맹독 내 9,389·상대 9,995행, 날씨 13,037행, 필드 4,028행, 벽 2,203행. EX-131 laya 진영의 Sleep Talk: v2t 사용 100·실패 43(그 턴 깨어남 26, 깨어 있는데 사용 17), v4t 사용 64·실패 43(깨어남 6, 깨어 있음 37)
