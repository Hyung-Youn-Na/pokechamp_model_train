# 효과 규칙표 effect-rules-v1 (EX-126 지식 자료의 근거)

지식 행의 정답은 이 규칙, `effect_rules.json` 상수, 타입표(`dex_gen9_v2.json`), 고정 엔진에서 내보낸 `dex_gen9_effects.json`으로 계산한다.
1차 근거는 로컬 고정 Showdown 엔진(`pokemon-showdown` `e64915c0e`)이다.
A(개념) 행은 하나도 빠짐없이 `effects_oracle.cjs`로 엔진에서 실제 1:1 배틀을 만들어 정답을 다시 얻는다. 규칙 함수와 엔진이 다르면 자료 생성이 멈춘다.

## 결과 라벨과 엔진 표기

| 라벨 | 뜻 | 엔진 protocol(탐침 기술 직후, 다음 `|move|` 전) |
|---|---|---|
| `works` | 정상 작동 | 아래 어느 것도 아님(빗나감은 시드를 바꿔 다시 실행) |
| `fails` | 실패하거나 막힘 | `-fail`, `-activate … move: Psychic/Misty/Electric Terrain`, 상대 `cant … ability: Dazzling/Queenly Majesty/Armor Tail` |
| `immune` | 효과 없음 | `-immune`, `-block`(Sweet Veil 등), `-activate … item: Safety Goggles` |
| `absorbed` | 상대 특성이 흡수 | 흡수 특성(`[from] ability:` 또는 `-start … ability: Flash Fire`, Wind Rider `-ability … boost`) |
| `reflected` | 매직미러로 반사 | 다음 줄이 `|move|p2a … [from] ability: Magic Bounce` |
| `yes`/`no` | 이번 턴 선택 가능 여부 | `DisableMove` 이벤트 후 `getMoveRequestData().moves[].disabled` |

## 판정 순서 (엔진 `sim/battle-actions.ts` `hitStep*` 순서를 따른다)

| 단계 | 규칙 | 엔진 근거 |
|---|---|---|
| 1. 기술 자체 조건 | Aurora Veil은 눈(snow/snowscape)이 아니면 실패. 같은 벽이 이미 있으면 실패 | `data/moves.ts` `auroraveil.onTry`, side condition 재설치 실패 |
| | Sleep Talk·Snore는 잠들어 있지 않으면 실패(Comatose 예외) | `sleeptalk.onTry`, `snore.onTry` |
| | Rest는 HP 가득, 이미 잠듦, Insomnia/Vital Spirit/Comatose, 땅에 있는 상태의 Misty/Electric Terrain에서 실패 | `rest.onTry`, `onHit` → `setStatus` |
| | Substitute는 이미 있거나 HP가 최대의 1/4 이하이면 실패 | `substitute.onTryHit` |
| | Fake Out·First Impression은 나온 뒤 첫 행동이 아니면 실패 | `fakeout.onTry`(`activeMoveActions`) |
| | Future Sight·Doom Desire는 이미 예약되어 있으면 실패. 타입 무효는 실제로 맞을 때 본다 | `futuresight.onTry` |
| | Sucker Punch·Thunderclap은 상대가 공격기를 고르지 않았거나 이미 움직였으면 실패 | `suckerpunch.onTry` |
| | Counter·Mirror Coat는 그 턴에 상대의 물리/특수 공격을 실제로 맞지 않았으면 실패 | `counter.onTry`, `damageCallback` |
| | Spikes 3층, Toxic Spikes 2층, Stealth Rock·Sticky Web 1층이 최대 | side condition `onSideRestart` |
| 2. 상대 쪽 차단 | 우선도 > 0 기술(Prankster·Gale Wings·Triage 반영)은 Dazzling·Queenly Majesty·Armor Tail, 땅에 있는 상대의 Psychic Terrain에 막힘 | `onFoeTryMove`, `psychicterrain.onTryHit` |
| | Magic Bounce는 reflectable 기술(상대 진영 대상 압정 포함)을 반사 | `magicbounce.onTryHit`, `onAllyTryHitSide` |
| | 흡수 특성: Volt Absorb·Lightning Rod·Motor Drive(전기), Water Absorb·Storm Drain·Dry Skin(물), Flash Fire·Well-Baked Body(불), Sap Sipper(풀), Earth Eater(땅), Wind Rider(wind 기술). 변화기 포함 | 각 특성 `onTryHit` |
| | Good as Gold는 상대가 거는 변화기 무효. Soundproof(sound), Bulletproof(bullet), Overcoat(powder) | 각 특성 `onTryHit` |
| 3. 타입·면역 | 공격기는 타입표 0배면 무효(Scrappy·Mind's Eye는 노말·격투가 고스트에 맞음). 땅 기술은 비행·Levitate·Air Balloon 무효 | `hitStepTypeImmunity`, `isGrounded` |
| | 변화기는 타입표를 무시하되 Thunder Wave만 땅 타입에 무효 | `ignoreImmunity`(변화기 기본), `thunderwave.ignoreImmunity: false` |
| | powder 기술은 풀 타입·Safety Goggles 무효. Prankster 변화기는 악 타입 무효 | `hitStepTryImmunity` |
| | 상대의 Substitute는 sound·bypasssub가 아닌 변화기를 막는다 | `substitute` 조건(`hitStepMoveHitLoop`) |
| | Encore는 상대가 아직 기술을 쓰지 않았거나 이미 Encore 상태면 실패(휘발 상태 부여 시점) | `encore` 조건 `onStart` |
| 4. 상태이상 | 이미 상태이상이면 실패 → 타입 면역(마비: 전기, 화상: 불, 독: 독·강철, Corrosion 예외) → 특성 면역(Limber, Insomnia, Vital Spirit, Sweet Veil, Water Veil, Water Bubble, Thermal Exchange, Immunity, Pastel Veil, Purifying Salt, Comatose) → 땅에 있는 상대의 Misty Terrain(모든 상태이상)·Electric Terrain(잠듦)은 실패 | `pokemon.ts` `trySetStatus`/`setStatus`, `runStatusImmunity`, `onSetStatus` |
| 공통 | Mold Breaker·Teravolt·Turboblaze·Neutralizing Gas는 상대 특성을 무시(Comatose 제외). Mycelium Might는 변화기에서만 | `ignoringAbility`, `breakable` 플래그 |
| 선택 | Taunt·Assault Vest는 변화기 선택 불가. Choice 도구는 처음 쓴 기술에 고정. Encore는 그 기술만 | `DisableMove` 이벤트 |

## 공개 정보 원칙(B 실제 상태)

- 상대 특성이 공개되지 않았으면 그 종족의 가능한 특성 전부를 넣어 보고, 결과가 모두 같을 때만 정답을 쓴다.
- 상대 도구가 공개되지 않았으면 powder 기술에서만 Safety Goggles 가능성을 열어 둔다. Air Balloon은 등장 때 공개되므로 미공개면 없음으로 본다.
- 표시 HP가 23~27%이면 Substitute 결과를 쓰지 않는다(표시 반올림).
- 이전 턴 기록이 필요한 기술(Fake Out, Future Sight, Encore, Sucker Punch, Counter류)과 `typechange` 효과가 있는 상태는 B에서 뺀다.

## 엔진 시나리오의 고정 처리

- 날씨·필드는 시나리오 값으로 다시 둔다(입장 특성이 바꾼 것을 지운다). 속도는 실제 능력치 400 대 100으로 순서를 고정한다.
- 탐침 기술이 빗나가면 시드만 바꿔 최대 20회 다시 실행한다. 행동 불가(잠듦·풀죽음), 배틀 조기 종료는 오류로 버리고 `oracle-errors.jsonl`에 남긴다.
- HP 60% 미만이면 열매를 Leftovers로 바꾼다(핀치 열매가 먼저 발동). 여러 턴이면 Choice 도구, 변화기를 쓰면 Assault Vest를 바꾼다.

## 설명 행(C)

`dex_gen9_effects.json`의 `shortDesc`(엔진 텍스트 그대로)만 쓴다. 기술은 `타입 분류 위력:` 머리를 붙인다.
설명이 같은 항목(진화 도구 등)은 역방향 질문에서 빼고, 정방향 오답은 설명이 다른 항목에서만 고른다.
웹 문서 텍스트는 쓰지 않는다.
