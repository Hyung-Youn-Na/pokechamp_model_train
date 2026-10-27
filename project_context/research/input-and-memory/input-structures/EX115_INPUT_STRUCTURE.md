# EX-115 입력 필드 구조 — jev-choice-v7 + candidate-action-v1

- 정리일: 2026-10-21
- 적용 범위: [EX-115](../experiments/EX-115-candidate-action-v7.md)의 저장 입력과 실제 전송 요청.
- 입력 버전: `state.version = "jev-choice-v7"`.
- 입력 프로필: `state.input_profile = "candidate-action-v1"`.
- 후보 요약의 하위 버전: `current_matchup.version = "candidate-matchup-v1"`.
- [폴더 안내](README.md) · [이전 EX-112 구조](EX112_INPUT_STRUCTURE.md).

이 문서는 **사람이 입력 원문을 확인하기 위한 상세 설명서**다. 모델 프롬프트·자동 로딩 자료·
새 실행 계약이 아니다. 규범과 실험 조건은 [입력 계약](../CONTRACTS.md),
[D-179](../decisions/D-179-candidate-action-v7.md), EX-115에 유지한다.
아래 트리는 가능한 필드를 합친 설명이며 모든 결정에 모든 필드가 있다는 뜻은 아니다.
`[]`는 목록, `{}`는 객체/매핑을 나타낸다. 생략·빈 값·`null`·`unknown`의 의미를 구분한다.

## 1. 전체 구조와 읽는 순서

```text
논리 입력
├─ state                         공통 상태·자기/상대 팀·공개 기록·상성표·스피드
└─ questions
   └─ action
      ├─ type                    "choice"
      ├─ instructions            영어 지시문·계산 해석·공통 주석 정의
      └─ criteria                합법 후보 ID → 후보 설명 객체
         ├─ team_* / switch_*    대상 포켓몬 이름·자기 팀 슬롯
         └─ move_*               식별자·테라 여부
            ├─ move_ref          원래 포켓몬/기술 슬롯 식별
            ├─ move              해당 기술의 상세 정보
            ├─ damage            선택 분기 + 다른 모든 기존 가정 분기
            └─ current_matchup   현재 대면의 타입·차단·상태효과·선택 피해 요약
```

트리는 의미별 배치이며 JSON 키의 실제 출력 순서를 재정의하지 않는다.
읽을 때는 먼저 `decision_kind`와 `actor`를 확인하고, 공통 `state`에서 상황을 파악한 다음
각 후보의 `move`·`current_matchup`·`damage`를 함께 본다. 선봉/교체는 후보의 `slot`으로
`self_team`의 대상 포켓몬을 확인한다.

EX-112에서는 기술 상세를 `move_ref`로 상태에서 찾아야 했다. v7은 **합법 기술 후보마다
그 기술 정보를 직접 포함**한다. 일반/테라 후보 모두 자기 설명을 가지며, 이동된 기술은
상태의 `current_move_slots`에서 제거한다. 벤치 기술·현재 사용할 수 없는 기술·상대 공개 기술과
받는 피해 계산은 모델 입력에 유지한다. 감사 파일에만 남기는 방식이 아니다.

## 2. state — 현재 공통 상태


```text
state
├─ version                       "jev-choice-v7"
├─ input_profile                 "candidate-action-v1"
├─ format                        배틀 형식·규칙
├─ turn                          현재 턴
├─ actor                         조종 진영: p1 / p2
├─ request_id                    현재 행동 요청 식별자
├─ decision_kind                 lead / turn_action / forced_switch
├─ self_team[]                   자기 팀 정보
├─ opponent_team[]               상대 팀의 공개 정보
├─ weather                       날씨 관측과 관련 규칙 설명
├─ weather_duration              기록된 날씨 지속시간 정보
├─ field[]                       필드 효과
├─ side_conditions
│  ├─ p1                         p1 진영 효과
│  └─ p2                         p2 진영 효과
├─ recent_completed_turn_log[]   최근 완료 턴의 공개 기록
├─ type_matchups                 전체 타입 상성표
└─ speed_comparison              현재 대면의 조건부 스피드 비교
```

`lead`는 선봉 선택, `turn_action`은 일반 행동, `forced_switch`는 강제 교체다.
`side_conditions`는 자기/상대가 아니라 p1/p2로 나뉘므로 `actor`와 함께 읽는다.
지속시간·상태 카운터는 저장된 관측이며 모두 정확한 잔여 턴을 보장하는 값은 아니다.


`information_rules` 필드는 v7 state에 없다. 기존 해석 규칙을 `instructions`에 통합했다.
`input_profile`은 전체 재배치 프로필이고 `current_matchup.version`은 기존 요약 방식의 버전이므로
두 이름이 다른 것은 정상이다. 날씨·필드·지속시간은 저장된 관측 형태를 유지하며,
원문이 빈 문자열/목록인지 규칙 설명이 붙은 객체인지를 그대로 읽는다.

## 3. self_team — 자기 포켓몬


```text
self_team[]
├─ slot                          자기 팀 슬롯 번호
├─ species                       포켓몬 종
├─ nickname                      닉네임 — 있을 때
├─ active                        출전/요청상 활성 슬롯 표시
├─ condition                     HP·상태 표현
├─ stats
│  ├─ atk / def                  공격 / 방어
│  ├─ spa / spd                  특수공격 / 특수방어
│  └─ spe                        스피드
├─ ability                       현재 특성 정보
├─ baseAbility                   원래 특성 정보
├─ item                          도구 정보
├─ status                        주요 상태이상
├─ status_data                   수면·맹독 등의 관측 카운터
├─ boosts                        능력치 변화 단계
├─ volatiles                     혼란 등 일시 효과
├─ turnstatuses                  턴 단위 효과
├─ movestatuses                  기술 관련 효과
├─ terastallized                 테라 사용 상태
├─ configured_tera_type          설정된 자기 테라 타입
├─ applied_tera_type             실제 적용된 테라 타입 — 해당할 때
├─ defensive_types[]             현재 방어 타입
├─ stab_types[]                  자속 보정 관련 타입
├─ role_summary                  종별 가능한 역할과 설명
├─ known_move_set[]              알고 있는 자기 기술 구성
└─ current_move_slots[]          후보로 이동하지 않은 현재 요청 기술 슬롯
```

선봉 선택의 `active`는 요청 슬롯 표시이며 이미 배틀에 출전했다는 뜻으로 읽지 않는다.
`role_summary`에는 `knowledge`, `roles[{id, description}]`, `scope`가 들어간다.
종의 가능한 역할 설명을 현재 역할·전략의 확정 판정으로 취급하지 않는다.

특성·도구 객체에는 보통 `id`, `name`, `general_effect`가 들어가며, 미확인 표현에는
`knowledge` 등이 사용된다. 효과 설명은 발동 증거가 아니다. 억제 여부 등 현재 효과 상태와
특성의 알려진 정체성을 구분한다. 일부 날씨·진영·일시 효과는 `observed`와
`general_rules[{kind, id, name, general_effect}]`로 관측과 규칙 설명을 함께 제공한다.


### 3.1 기술이 남는 위치

| 위치 | v7에서 읽을 내용 |
|---|---|
| `known_move_set[]` | 제공된 자기 기술 지식. 현재 요청 슬롯이 없을 때도 사용하며 조건에 따라 생략될 수 있음 |
| `current_move_slots[]` | 현재 요청 슬롯 중 합법 기술 후보로 옮기지 않은 기술. 비활성/사용 불가 기술 등이 남을 수 있음 |
| `criteria.<기술 후보>.move` | 그 후보에 해당하는 원래 현재 요청 기술 슬롯의 상세 정보 |

`current_move_slots: []`는 **자기 포켓몬이 기술을 모른다는 뜻이 아니다.** 사용 가능한 기술들이
모두 후보로 이동했을 수 있다. `known_move_set`과 후보를 함께 확인한다.
벤치의 기술 정보는 원래 제공된 위치/형태를 보존하며 새 벤치 피해 계산을 만들지 않는다.

`known_move_set`의 주요 필드는 `id`, `name`, `type`, `category`, `power`, `accuracy`,
`priority`, `general_effect`, `current_pp`, `current_pp_reason`이다.
미확인 PP는 `current_pp` 값과 사유를 같이 읽으며 0으로 바꾸어 해석하지 않는다.
상태에 남은 현재 요청 슬롯에는 §7의 기술 필드와, 원래 있었다면 기존 `damage.ranges`가 남는다.

## 4. opponent_team — 상대 공개 정보


```text
opponent_team[]
├─ preview_slot                  상대 팀 프리뷰 슬롯
├─ species / nickname
├─ active
├─ fainted                       기절 여부
├─ hp_percent                    마지막으로 공개된 HP 비율
├─ hp_precision                  HP 관측 정밀도
├─ status / status_data
├─ boosts
├─ volatiles / turnstatuses / movestatuses
├─ ability / baseAbility         공개된 특성 정보
├─ item                          공개된 도구 정보
├─ moves[]                       공개적으로 알려진 기술
├─ terastallized
├─ defensive_types[]
├─ stab_types[]
└─ role_summary
```

미공개 도구·특성·기술은 미확인으로 유지한다. `moves`는 미확인 문자열이거나 기술 목록일 수 있다.
공개된 상대 기술에는 `id`, `name`, `type`, `category`, `power`, `accuracy`, `priority`,
`knowledge`, `general_effect`, 해당할 때 `damage`가 들어간다.
공개 벤치의 기술·도구·특성은 이전 공개 관측을 보존하며, HP도 마지막 공개 값이다.
숨은 회복이나 상대 PP·비공개 세트를 추정해 실제 관측처럼 넣지 않는다.


상대 기술의 `damage`는 **상대가 자기 현재 출전 포켓몬에게 주는 피해**다.
이 위치의 피해 구조는 원래 `target_side/target_slot/target_species/unit/ranges/reason`을 유지한다.
자기 기술 후보의 `selected_range/other_assumptions` 형식으로 일괄 바꾸지 않는다.
상대 벤치 HP·도구·특성·기술은 공개 이력의 범위이며, 역할 설명/추천 세트를 실제 소지 정보로 읽지 않는다.

## 5. 전체 상성표·스피드·최근 로그


```text
type_matchups
├─ attack_types[18]              행의 공격 타입
├─ defense_types[18]             열의 방어 타입
└─ multipliers[18][18]           타입 상성 배율
```

`multipliers[i][j]`는 `attack_types[i]`가 `defense_types[j]`를 공격할 때의 타입 배율이다.
이 전체 상성표는 v7의 state에도 그대로 포함된다. 후보별 현재 대면 요약과 함께 존재한다.

```text
speed_comparison
├─ status                        available / unavailable / not_applicable
├─ speed_certainty               스피드 관계의 확실성
├─ meaning / assessment          의미·판정 설명
├─ self_speed_relation[]         faster / slower / tie
├─ self_effective_speed_range
├─ opponent_effective_speed_range
├─ compatible_set_count
├─ expanded_candidate_count
├─ by_set[]
│  ├─ set_name
│  ├─ self_effective_speed_range
│  ├─ opponent_effective_speed_range
│  └─ self_speed_relation[]
├─ support                       사용한 상대 세트 자료의 범위
├─ conditions                    계산 조건
└─ reason                        미제공 등의 사유
```

공개 정보와 양립하는 추천 세트 등 선언한 자료 범위의 조건부 비교다.
상대의 실제 비공개 스피드 확정값·세트 확률·선공 확률로 읽지 않는다.
선택한 기술이나 새 테라 적용 전의 조건이며 우선도 등 전체 행동 순서를 보장하지 않는다.

```text
recent_completed_turn_log[]
├─ turn
├─ text                          읽기 쉬운 공개 이벤트 설명
├─ participants[]                관련 포켓몬
└─ referenced_effects[]
   ├─ kind
   ├─ id
   ├─ name
   └─ general_effect
```

뷰어의 전체 경기 로그와 모델에 전달한 이 최근 기록은 범위가 다르다.
현재 결정 이후의 결과를 모델 입력에 소급해 포함하지 않는다.


상성표는 타입만의 기준표다. 상대 두 타입의 배율을 곱하는 기본 관계와, 도구·특성·접지·기술별 예외에
의한 실제 무효/변경을 구분한다. 표 전체를 남긴 상태에서 후보의 적용 결과도 함께 제공한다.
최근 로그는 최대3개 완료 턴의 공개 사건을 담으며, 현재 요청은 `state`가 기준이다.

## 6. questions.action — 질문과 합법 후보

| 필드 | 의미 |
|---|---|
| `type` | `"choice"` |
| `instructions` | 승리 목표·행동 비교·Gen9 규칙·공개 정보/계산 불확실성·공통 주석을 설명하는 영어 문자열 |
| `criteria` | 후보 ID를 키로 하는 객체. 현재 합법 후보의 순서를 유지 |

| 후보 종류 | ID 예시 | 필수적인 읽기 경로 |
|---|---|---|
| 선봉 | `team_1` | `kind="team"`, `slot`, `pokemon` → `state.self_team` |
| 교체 | `switch_5` | `kind="switch"`, `slot`, `pokemon` → `state.self_team` |
| 일반 기술 | `move_1` | `kind="move"`, `slot`, `terastallize=false`, `move`, `current_matchup`, 해당할 때 `damage` |
| 테라 기술 | `move_1_terastallize` | 같은 기술의 독립 후보, `terastallize=true`, 자기 테라 선택 분기 |

```text
move_ref
├─ self_team_slot                자기 포켓몬 slot
└─ current_move_slot             이동 전의 현재 기술 slot
```

`move_ref`는 원래 위치를 식별하는 기록이다. **v7에서는 참조된 기술이 state에서 제거됐을 수 있으므로
이를 따라가서 상세를 찾지 않고 같은 후보의 `move`를 읽는다.** 슬롯 번호는 배열 인덱스가 아니다.
후보 ID·순서와 별도 실행 명령 매핑은 기존 그대로이며 후보를 제거하거나 점수순으로 정렬하지 않는다.
`terastallize=true`는 선택 시 새 테라를 사용하는 행동이고, 상태의 `terastallized`는 이미 사용한 사실이다.

## 7. 기술 후보의 move — 행동 자체의 설명

```text
move
├─ id                            정규화된 기술 식별자
├─ name / move                   실제 기술명과 요청에 있던 기술명
├─ type                          기본 기술 타입
├─ category                      Physical / Special / Status
├─ power                         기본 위력
├─ accuracy                      기본 명중률 표현
├─ priority                      기본 우선도
├─ general_effect                기술의 일반적인 Gen9 효과 설명
├─ slot                          원래 현재 요청 기술 슬롯
├─ pp / maxpp                    현재 PP / 최대 PP
├─ target                        요청의 기술 대상 종류
└─ disabled                      현재 요청의 사용 불가 표시
```

원 기술 슬롯의 다른 필드가 있다면 그것도 유지한다. 원래 `move.damage`에 있던 계산은
후보 바로 아래 §8의 `damage`로 분리하므로 같은 `move` 안에서 찾지 않는다.

`type/category/power/accuracy/priority`는 기본 메타데이터다. 동적 타입·능력/필드·HP·행동 순서 등의
예외까지 적용한 최종 결과라고 읽지 않는다. 적용 공격 타입은 `current_matchup.type_matchup.attack_type`,
차단/예외는 `public_effects`, 기술 자체의 실행 조건은 `general_effect`와 개별 사유를 함께 읽는다.
일반 효과 설명은 현재 발동/성공을 보장하지 않는다. 일반/테라 후보 각각에 이 기술 설명을 포함한다.

## 8. 기술 후보의 damage — 선택 분기와 나머지 가정

```text
candidate.damage
├─ selected_branch               "current" 또는 "self_tera"
├─ selected_range                선택한 분기만 담은 객체, 또는 null
│  └─ current / self_tera        [최소, 최대], 또는 원래의 null
├─ other_assumptions             나머지 기존 분기를 모두 담은 객체, 또는 null
│  └─ current / self_tera /
│     opponent_tera / both_tera   선택 분기를 제외하고 원래 있던 분기
├─ target_side                   피해 대상 진영
├─ target_slot                   대상 포켓몬 슬롯
├─ target_species                대상 포켓몬 종
├─ unit                          "percent_of_target_max_hp"
└─ reason                        기존 계산의 미제공 등 사유
```

| 후보 | 먼저 읽는 분기 | 나머지 분기 위치 |
|---|---|---|
| 일반 기술 | `selected_range.current` | `other_assumptions` 안의 self_tera/opponent_tera/both_tera 등 |
| 새 자기 테라 + 기술 | `selected_range.self_tera` | `other_assumptions` 안의 current/opponent_tera/both_tera 등 |

`selected_range`는 숫자 배열 자체가 아니라 **분기 이름 → 범위** 객체다.
아직 사용하지 않은 상대 테라·양측 테라 가정은 현재 관측으로 확정된 효과가 아니다.
분기 이름의 자기/상대는 `state.actor` 기준이며, 상대 기술의 받는 피해 계산에서도 동일한 기준이다.
이미 적용된 테라는 `current`에 반영돼 있다.

| 값/형태 | 의미 |
|---|---|
| `{"current": [0, 0]}` | 선택 분기에서 계산된 피해0. 원인까지 나타내는 것은 아님 |
| `{"current": [28.1, 57.4]}` | 대상 최대HP의28.1~57.4%인 조건부 범위 |
| `{}` | 원래 ranges 객체에 선택 분기 키가 없었음. 피해0이 아님 |
| `{"self_tera": null}` | 그 분기 키는 있으나 원래 값이 null인 경우의 보존 형태 |
| `selected_range: null`, `other_assumptions: null` | 원래 ranges 자체가 null인 경우. 기존 reason을 함께 확인 |
| 후보의 `damage` 필드 없음 | 원 기술 슬롯에 옮길 피해 계산 객체가 없었던 경우 |

범위는 모든 명중 판정 성공, 현재 효과, 고정2026-09-18 Smogon 추천 세트 중 공개 정보와
양립하는 경우, 반올림된 공개 HP 및 기술별 히트수 등의 조건을 전제로 한다. 평균·확률·보장치가 아니다.
범위는0.1% 단위 바깥쪽 반올림이며100%를 넘을 수 있다. 일반 급소 확률·빗나감·미지의 예정 행동·
상대 교체·향후 행동 순서 변화는 포함하지 않는다. Sucker Punch 등의 성공 요구도 조건부다.
유한 추천 세트는 모든 합법 세트가 아니며 상대의 실제 비공개 세트라는 증거가 아니다.

상대 공개 기술이나 상태에 남은 비후보 기술의 피해는 기존 `damage.ranges` 구조를 유지한다.
이 재배치는 수치/조건/이유를 변경하거나 새로운 교체 피해를 계산하는 기능이 아니다.

## 9. current_matchup — 현재 대면의 적용 결과


일반 행동(`turn_action`)의 기술(`kind: move`) 후보에만 붙는다.

```text
current_matchup
├─ version                       "candidate-matchup-v1"
├─ move                          실제 기술명
├─ target                        현재 상대 species·preview_slot 객체,
│                                또는 자기/진영 등 기술 대상 문자열
├─ scope                         요약이 적용되는 조건
├─ selected_self_tera             이 후보에서 자기 테라를 선택했는지
├─ type_matchup
│  ├─ attack_type                적용 공격 타입
│  ├─ target_types[]             상대 방어 타입
│  ├─ multiplier                 합산 상성 배율
│  ├─ factors[]                  defense_type·multiplier의 목록
│  ├─ result                     immune / resisted / neutral /
│  │                             super_effective / unknown / not_applicable
│  ├─ scope
│  └─ reason / unknown_reasons / move_rule / damage_scaling
│                                상황별 사유·예외 설명
├─ public_effects
│  ├─ result                     blocked / reflected /
│  │                             no_known_blocker / unknown / not_applicable
│  ├─ blocking_conditions[]      공개적으로 확인한 차단 근거
│  ├─ overrides[]                면역 해제 등 예외 근거
│  ├─ unknown_reasons[]
│  ├─ resolved_type_multiplier
│  └─ note / reason
├─ status_effect
│  ├─ effect                     상태이상 종류
│  ├─ component                  주요 효과·부가 효과 구분
│  ├─ result                     상태효과 적용 가능성 판정
│  ├─ blocking_conditions[]
│  ├─ unknown_reasons[]
│  └─ note / reason
└─ damage
   ├─ branch                     current / self_tera
   ├─ percent_of_target_max_hp    기존 계산에서 복사한 [최소, 최대]
   ├─ result                     calculated_zero /
   │                             conditional_positive_range /
   │                             unknown / not_applicable
   ├─ reason
   └─ scope
```

중첩 필드도 결과에 따라 형태가 달라진다. 예를 들어 자기/진영 대상 기술의 타입 요약에는
`not_applicable`과 `reason`만 중심적으로 들어가며 상대 대상의 `factors` 등을 요구하지 않는다.
차단/예외 근거에는 해당할 때 `source`, `id`, `description`을 기록한다.

현재 상대가 유지되고 상대 교체·새 테라·다른 행동에 의한 중간 상태 변화가 없는 대면을 전제로 한다.
v7에서도 이 요약의 damage에는 `current` 또는 선택한 자기 테라 분기 `self_tera`만 들어간다.
모든 다른 피해 분기는 후보 바로 아래의 `damage.other_assumptions`에 남는다.
상대 테라 가정 피해를 현재 확정 피해로 읽지 않는다.

- `blocked`: 지원하는 공개 규칙에서 충분한 차단 근거를 확인했다.
- `reflected`: 해당 효과가 반사되는 경우이며 후속 연쇄 효과까지 예측한 것은 아니다.
- `no_known_blocker`: 알려진 차단 근거가 없다는 뜻으로 실행 성공을 보장하지 않는다.
- `unknown`: 근거 부족·미지원 등의 미확정 상태다. 효과 없음·면역 해제를 뜻하지 않는다.
- 피해와 상태이상 성분은 별개다. 부가 상태이상이 막혀도 피해 기술 자체는 유효할 수 있다.
- 고정/비율 피해에는 약점·저항 배율을 그대로 곱하지 않는다는 별도 설명이 있을 수 있다.


### 9.1 두 damage 필드의 차이

- `candidate.damage`: 선택 분기와 **나머지 모든 기존 가정 분기**, 대상·단위·사유를 보존한 계산 정보.
- `candidate.current_matchup.damage`: 이 후보에 대응하는 **current 또는 self_tera 한 분기**의 값·판정 요약.

같은 선택 피해 숫자가 두 위치에 나타날 수 있다. 독립 계산 두 개가 아니라 기존 계산을 재배치하고
요약한 것이다. 타입 배율0, 계산 피해0, 전체 기술 차단, 주요/부가 상태이상 차단은 서로 다른 항목이다.

## 10. 공통 주석과 instructions

반복되는 정확히 등록된 `scope`/`note` 문구는 아래 식별자로 표시한다.
정의는 영어 지시문의 `COMMON ANNOTATIONS`에 한 번 들어가며, 외부 파일을 모델이 추가로
읽어야 하는 구조가 아니다. 개별 차단 조건·예외·미확정 이유는 후보에 그대로 남는다.

| 식별자 | 해석 |
|---|---|
| `@roles` | 조건부 능력/역할 설명이며 현재 역할이나 유리한 대면을 보장하지 않음 |
| `@matchup` | 현재 상대 유지, 선택한 자기 테라 포함. 상대 교체/새 테라/중간 상태 변화 제외 |
| `@damage` | 기존 v6의 명중·유한 추천세트 조건부 계산 복사. 피해0으로 면역 원인을 단정하지 않음 |
| `@types` | 지원한 기술별 타입 규칙까지 적용한 타입표 결과. 도구/특성/접지 예외는 별도 |
| `@success` | unknown은 우회 증거가 아니며 no_known_blocker도 성공 보장이 아님 |
| `@status` | 상태 성분만의 판정. 부가 상태가 막혀도 피해는 줄 수 있음 |
| `@bypass` | unknown을 면역 우회의 증거로 보지 않음 |

지시문에는 승리 목표와 합법 후보 선택, Gen9 규칙, 공개 정보 경계, 피해/스피드 계산의 불확실성,
전체 상성표와 Tera/STAB의 해석, 공개 로그 해석도 유지된다. `information_rules`가 state에서
없어졌다고 규칙까지 모델 입력에서 빠진 것은 아니다.

## 11. 실제 API 요청 포장

다음은 필드 위치를 보여 주는 구조 예시다. 꺾쇠 부분은 실제 값의 생략 표시다.
**input과 description은 객체가 아니라 JSON을 직렬화한 문자열**이다.

```json
{
  "model": "gpt-6-luna",
  "input": "<v7 state 전체의 JSON 문자열>",
  "questions": [
    {
      "name": "action",
      "type": "choice",
      "instructions": "<영어 지시문과 공통 주석 정의>",
      "choices": [
        {"value": "move_1", "description": "<move_1 전체: move_ref, current_matchup, move, damage 등>"},
        {"value": "switch_2", "description": "<kind, slot, pokemon 객체의 JSON 문자열>"}
      ]
    }
  ]
}
```

| 논리 입력 | 실제 요청 |
|---|---|
| `state` | `input`의 JSON 문자열 내부 |
| `questions.action.instructions` | `questions[0].instructions` |
| 후보 ID | `questions[0].choices[].value` |
| 후보 전체 설명 | 동일 choice의 `description` 문자열 내부 |
| 사용할 기술의 상세·전체 피해 분기 | 기술 choice의 `description` 안 `move`·`damage` |
| 전체 상성표·공통 상태·상대 기술/받는 피해 | `input` 내부의 해당 state 필드 |

후보가 하나뿐이면 API 요청 없이 자동 선택한다. 이때 저장된 논리 입력은 있지만 실제
HTTP 요청이나 모델 응답은 없다. `questions.action`은 내부 객체이며 실제 API의 `questions`는 배열이다.

## 12. 저장 자료로 읽는 예시

아래 예시는 EX115 본수집의 선봉·일반 행동·강제교체 첫 사례에서 필요한 부분을 발췌했다.
각 예시가 전체 payload는 아니며, 없는 필드를 임의로 채우지 않았다.

### 12.1 선봉

결정 `jeva569e13de63e-2-6`, `turn=0`, `actor=p1`.

후보 일부:

```json
{
  "team_1": {
    "kind": "team",
    "slot": 1,
    "pokemon": "Lokix"
  },
  "team_2": {
    "kind": "team",
    "slot": 2,
    "pokemon": "Pecharunt"
  }
}
```

팀 상세·알려진 기술·도구·특성은 state에 있다. 선봉 후보 자체에는 move/current_matchup을 붙이지 않는다.

### 12.2 일반 기술과 테라 기술

결정 `jeva569e13de63e-4-17`, `turn=1`, `actor=p1`.

이 일반 기술 후보의 **전체 설명 객체**는 다음과 같다.

```json
{
  "move_1": {
    "kind": "move",
    "slot": 1,
    "terastallize": false,
    "move_ref": {
      "self_team_slot": 1,
      "current_move_slot": 1
    },
    "current_matchup": {
      "version": "candidate-matchup-v1",
      "move": "First Impression",
      "target": {
        "species": "Zapdos",
        "preview_slot": 1
      },
      "scope": "@matchup",
      "selected_self_tera": false,
      "type_matchup": {
        "attack_type": "Bug",
        "target_types": [
          "Electric",
          "Flying"
        ],
        "multiplier": 0.5,
        "factors": [
          {
            "defense_type": "Electric",
            "multiplier": 1
          },
          {
            "defense_type": "Flying",
            "multiplier": 0.5
          }
        ],
        "scope": "@types",
        "result": "resisted"
      },
      "public_effects": {
        "result": "unknown",
        "blocking_conditions": [],
        "overrides": [],
        "unknown_reasons": [
          "additional_move_execution_conditions_not_evaluated",
          "target_ability_or_suppression_unknown",
          "target_item_unknown"
        ],
        "resolved_type_multiplier": 0.5,
        "note": "@success"
      },
      "status_effect": {
        "result": "not_applicable",
        "reason": "secondary_effects_not_predicted"
      },
      "damage": {
        "branch": "current",
        "percent_of_target_max_hp": [
          28.1,
          57.4
        ],
        "result": "conditional_positive_range",
        "reason": null,
        "scope": "@damage"
      }
    },
    "move": {
      "id": "firstimpression",
      "type": "Bug",
      "category": "Physical",
      "power": 90,
      "accuracy": 100,
      "priority": 2,
      "slot": 1,
      "move": "First Impression",
      "pp": 16,
      "maxpp": 16,
      "target": "normal",
      "disabled": false,
      "name": "First Impression",
      "general_effect": "Fails unless it is the user's first turn on the field."
    },
    "damage": {
      "selected_branch": "current",
      "selected_range": {
        "current": [
          28.1,
          57.4
        ]
      },
      "other_assumptions": {
        "self_tera": [
          38.1,
          76.7
        ],
        "opponent_tera": [
          28.1,
          67.9
        ],
        "both_tera": [
          38.1,
          90.9
        ]
      },
      "target_side": "opponent",
      "target_slot": 1,
      "target_species": "Zapdos",
      "unit": "percent_of_target_max_hp",
      "reason": null
    }
  }
}
```

같은 기술의 테라 후보에서는 기술 설명을 다시 포함하고 피해를 다음처럼 배치한다(피해 필드 발췌).

```json
{
  "move_1_terastallize": {
    "terastallize": true,
    "damage": {
      "selected_branch": "self_tera",
      "selected_range": {
        "self_tera": [
          38.1,
          76.7
        ]
      },
      "other_assumptions": {
        "current": [
          28.1,
          57.4
        ],
        "opponent_tera": [
          28.1,
          67.9
        ],
        "both_tera": [
          38.1,
          90.9
        ]
      },
      "target_side": "opponent",
      "target_slot": 1,
      "target_species": "Zapdos",
      "unit": "percent_of_target_max_hp",
      "reason": null
    }
  }
}
```

이 장면의 선택 피해는 일반28.1~57.4%, 새 자기 테라38.1~76.7%다. 계산 가정 안의 범위이며 실제 피해 예측의 보장치가 아니다.

### 12.3 강제 교체

결정 `jeva569e13de63e-6-28`, `turn=1`, `actor=p1`.

후보 일부:

```json
{
  "switch_2": {
    "kind": "switch",
    "slot": 2,
    "pokemon": "Pecharunt"
  },
  "switch_3": {
    "kind": "switch",
    "slot": 3,
    "pokemon": "Zamazenta"
  }
}
```

강제교체 요청에서도 후보는 이름·슬롯으로 대상을 식별한다. 이 결정에 합법인 교체 후보 중 선택하며 새 교체 피해 계산은 없다.

같은 장면의 EX112→v7 재배치 전후 전체 비교는
[오프라인 전후 예시](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115/offline/examples.json)에 있다.
이 자료는 EX112 저장 입력의 변환 비교이며, 위 EX115 실제 경기를 동일한 경기 전개로 간주하지 않는다.

## 13. 모델 입력과 감사·실행 기록의 경계

| 자료 | 모델에 전달되는가? | 용도 |
|---|---|---|
| state, instructions, 후보 설명 | API 호출 시 전달 | 판단 정보 |
| 후보 하나인 결정의 저장 payload | 실제 API 호출 없음 | 자동 선택 관측 기록 |
| input_audit의 원래 v6+matchup payload·계산 근거 | 이 감사 파일 자체는 별도 | 출처/재생성/전후 대조 |
| 후보 ID→실행 명령, 최신 요청 재검증 | 별도 실행기 기록 | 합법 선택을 실제 명령으로 연결 |
| 전체 경기 로그·선택 이후의 결과 | 미래 결과는 당시 입력에 포함하지 않음 | 사후 감사·리플레이 |
| HTTP 원문·응답 시도·usage | 별도 수집 기록 | 전송/응답/사용량 확인 |

실행 불가 응답의 재질의는 동일한 입력/본문을 사용한다. 이전 거부 응답이나 교정 프롬프트를
추가 입력으로 붙이지 않는다. 한 결정의 응답 시도는 최대3회이고 통신 재시도는 별도로 세지만,
이 정책은 입력 필드가 아니라 [EX115 실행 조건](../experiments/EX-115-candidate-action-v7.md)이다.

## 14. 자주 혼동하는 값

| 표현 | 해석 |
|---|---|
| `unknown` | 증거 부재/미지원 등 미확정. 0·없음·면역 해제가 아님 |
| `confirmed_absent` | 확인된 부재 |
| `not_applicable` | 해당 개념의 적용 대상이 아님 |
| 빈 주요 `status` | 주요 상태이상 없음 |
| 빈 `boosts` | 능력치 변화 단계0 |
| 빈 일시 효과 맵 | 해당 효과 없음 |
| `general_effect` | 일반 규칙 설명. 현재 발동 증거가 아님 |
| `no_known_blocker` | 지원하는 범위에 알려진 차단 없음. 성공 보장이 아님 |
| `current_move_slots: []` | 기술이 후보로 이동했을 수 있음. 기술 보유/PP 없음으로 해석하지 않음 |
| `move_ref` | 원슬롯 식별. v7 상태에 그 기술 상세가 남아 있다는 보장이 아님 |
| `speed_comparison` | 조건부 유효 스피드 비교. 선공 확률이 아님 |

## 15. 보존 검사와 길이 측정의 범위


[검증 receipt](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115/offline/verification.json):
913입력(선봉32·일반679·강제교체202), 기술후보5214개. 감사 파일 없이 모델 입력에서 원자료 복원 일치.
884논리 API 요청의 `input + instructions + 모든 description` UTF-8 길이를 측정했다.
총량 53,324,805→53,209,487바이트(0.2163% 감소), 중앙62,227→61,913.5, p95 68,267→68,247이다.
p95는 nearest rank다. 요청 JSON의 포장·이스케이프·ID 바이트는 전달 텍스트 길이에서 제외하며
전후 같은 방법을 쓴다. 토큰·모델 판단·성능 개선의 검증이 아니다.

별도로 [HTTP 포장 포함 길이](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115/offline/http-body-lengths.json)도 기록했다. JSON 이스케이프/포장까지 포함한 전송 본문은57,428,453→57,538,015바이트(0.1908% 증가), 중앙67,220→67,240, p95 73,392→73,784다. 모델이 읽는 파싱 후 문자열의 감소와 네트워크 본문 크기는 다르며, 본 실험의 입력 길이 gate는 위 모델 전달 텍스트 기준이다.

이 검사의913개 입력/884개 요청은 **EX112 보존 입력의 전후 변환 검사 분모**다.
EX115 본수집은 별도로1021개 입력/997개 API 요청을 기록했다. 입력 길이 비교 분모와
본실험 성적/사용량 분모를 혼합하지 않는다. 구조 설명은 모델이 모든 필드를 실제 활용했다는 증거가 아니다.

## 16. 원문·구현·실제 자료

- [EX115 실험 원문](../experiments/EX-115-candidate-action-v7.md) · [구현/검증 계획](../plans/EP-202-candidate-action-v7.md).
- [재배치 구현](../../../../integration/candidate_action/transform.py) · [수집 당시 동결 영어 지시문](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115/source/integration/candidate_action/prompt.txt).
- [입력 생성·감사 연결](../../../../integration/candidate_action/adapter.py) · [실제 API 변환](../../../../integration/openai_decisions_battle/core.py).
- [본수집 동결 소스](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115/source/integration/candidate_action/transform.py).
- [실제 요청·입력·리플레이](../../../../exports/battle_viewers/ex115/index.html) · [첫 경기 결정 JSON](../../../../exports/battle_viewers/ex115/battle-1/decisions.json).
- [실험 보고서](/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/EX-115/evidence/report.md).

개발용 지시문은 이후 [D-181](../decisions/D-181-v7-survival-switch-cost.md)에서 개정했다.
이 문서의 설명·길이 수치·예시는 EX-115 수집 당시 동결 지시문에 한정된다.
