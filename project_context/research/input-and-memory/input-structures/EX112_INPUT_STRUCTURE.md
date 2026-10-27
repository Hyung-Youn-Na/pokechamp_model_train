# EX-112 입력 필드 구조 — jev-choice-v6 + candidate-matchup-v1

- 정리일: 2026-10-21
- 적용 범위: [EX-112](../experiments/EX-112-openai-candidate-matchup-battle.md)의 저장 입력과 실제 OpenAI Decisions 요청.
- 기반 입력: `state.version = jev-choice-v6`.
- 추가 프로필: `candidate-matchup-v1`. 각 `current_matchup.version`과 실험 manifest에 기록한다.
- 문서화 근거: [EP-194](../plans/EP-194-ex112-input-structure-reference.md).

이 문서는 사람이 입력 원문을 읽을 때 참고하는 **버전별 상세 설명서**다. [폴더 안내](README.md) · [EX-115 v7 구조](EX115_INPUT_STRUCTURE.md). 새 입력 규격이나
연구 조건을 정의하지 않는다. 규범 원문은 [입력 계약](../CONTRACTS.md)의 C-067/C-081/C-082와
관련 실험에 유지한다. 아래 트리는 가능한 필드를 합쳐 보여 주며 모든 결정에 모든 필드가
존재한다는 뜻은 아니다. 결정 종류·관측·적용 가능성에 따라 생략, `unknown`, `null` 등이 나타난다.

## 1. 전체 구조와 EX-112의 추가 범위

```text
논리 입력
├─ state                         현재 상태·팀·참조 지식·계산 결과
└─ questions
   └─ action
      ├─ type                    "choice"
      ├─ instructions            행동 선택 지시문
      └─ criteria                현재 결정의 합법 후보 ID → 후보 설명
```

EX-112는 **기존 v6 전체 입력을 유지하고 일반 행동의 기술 후보에 `current_matchup`만 추가**한다.
전체 18×18 타입 상성표, 기존 피해/스피드 계산, 지시문, 후보 ID·순서·기존 필드는 보존한다.
`current_matchup`을 제거하면 기반 입력을 정확히 복원할 수 있다.
선봉·교체 후보에 상대 대면 기술 요약을 추가하지 않는다.

## 2. state — 현재 상태

```text
state
├─ version                       "jev-choice-v6"
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
├─ information_rules             공개 정보·미확인 값의 해석 규칙
├─ recent_completed_turn_log[]   최근 완료 턴의 공개 기록
├─ type_matchups                 전체 타입 상성표
└─ speed_comparison              현재 대면의 조건부 스피드 비교
```

`lead`는 선봉 선택, `turn_action`은 일반 행동, `forced_switch`는 강제 교체다.
`side_conditions`는 자기/상대가 아니라 p1/p2로 나뉘므로 `actor`와 함께 읽는다.
지속시간·상태 카운터는 저장된 관측이며 모두 정확한 잔여 턴을 보장하는 값은 아니다.

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
└─ current_move_slots[]          현재 요청의 기술 슬롯·PP·사용 가능 여부
```

선봉 선택의 `active`는 요청 슬롯 표시이며 이미 배틀에 출전했다는 뜻으로 읽지 않는다.
`role_summary`에는 `knowledge`, `roles[{id, description}]`, `scope`가 들어간다.
종의 가능한 역할 설명을 현재 역할·전략의 확정 판정으로 취급하지 않는다.

특성·도구 객체에는 보통 `id`, `name`, `general_effect`가 들어가며, 미확인 표현에는
`knowledge` 등이 사용된다. 효과 설명은 발동 증거가 아니다. 억제 여부 등 현재 효과 상태와
특성의 알려진 정체성을 구분한다. 일부 날씨·진영·일시 효과는 `observed`와
`general_rules[{kind, id, name, general_effect}]`로 관측과 규칙 설명을 함께 제공한다.

## 4. 기술 정보와 기존 피해 계산

| 위치 | 주요 필드 |
|---|---|
| `known_move_set[]` | `id`, `name`, `type`, `category`, `power`, `accuracy`, `priority`, `general_effect`, `current_pp`, `current_pp_reason` |
| `current_move_slots[]` | `id`, `name`, `move`, `type`, `category`, `power`, `accuracy`, `priority`, `general_effect`, `slot`, `pp`, `maxpp`, `target`, `disabled`, `damage` |

`known_move_set`은 현재 요청 슬롯이 없을 때도 자기 기술 지식을 보존한다.
기술이 알려져 있어도 현재 PP가 확인되지 않으면 그 상태·사유를 유지한다.
`current_move_slots`는 현재 요청의 기술 슬롯이므로 배열 위치 대신 명시적인 `slot`으로 연결한다.

```text
damage
├─ target_side                   피해 대상 진영
├─ target_slot                   대상 슬롯
├─ target_species                대상 포켓몬
├─ unit                          "percent_of_target_max_hp"
├─ ranges
│  ├─ current                    현재 조건
│  ├─ self_tera                  자기 테라 가정
│  ├─ opponent_tera              상대 테라 가정
│  └─ both_tera                  양측 테라 가정
└─ reason                        미제공 등의 사유
```

각 범위는 `[최소값, 최대값]`으로, 대상 최대 HP 대비 피해 비율이다.
기존 계산의 명중·상대 세트 등 조건을 함께 읽는다. 모든 공격의 실제 결과를 보장하지 않는다.
상대 기술에도 자료가 있는 경우 같은 `damage` 구조가 붙는다.
**계산된 0, 미제공, 적용 대상 아님을 구분하며 피해 0으로 면역 원인을 역추정하지 않는다.**

## 5. opponent_team — 상대 공개 정보

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

## 6. 전체 타입 상성표·스피드·최근 로그

```text
type_matchups
├─ attack_types[18]              행의 공격 타입
├─ defense_types[18]             열의 방어 타입
└─ multipliers[18][18]           타입 상성 배율
```

`multipliers[i][j]`는 `attack_types[i]`가 `defense_types[j]`를 공격할 때의 타입 배율이다.
이 전체 상성표는 EX-112에도 그대로 포함된다. 후보별 현재 대면 요약과 함께 존재한다.

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

## 7. questions.action — 행동 지시와 합법 후보

`type`은 `choice`, `instructions`는 기존 v6의 행동 선택 지시문이다.
`criteria`는 현재 결정에 합법인 후보만 가진 ID → 설명 객체 매핑이다.
아래 행은 결정 종류별 가능한 형태이며 모든 후보 종류가 한 결정에 함께 있다는 뜻은 아니다.

| 종류 | 후보 ID 예시 | 후보 내부 필드 |
|---|---|---|
| 선봉 | `team_1` | `kind: "team"`, `slot`, `pokemon` |
| 교체 | `switch_5` | `kind: "switch"`, `slot`, `pokemon` |
| 기술 | `move_1` | `kind: "move"`, `slot`, `terastallize`, `move_ref`, `current_matchup` |
| 테라 + 기술 | `move_1_terastallize` | 기술 후보와 같으며 `terastallize: true` |

```text
move_ref
├─ self_team_slot                자기 포켓몬의 slot
└─ current_move_slot             그 포켓몬 current_move_slots의 slot
```

슬롯은 배열 인덱스가 아니다. 기술명은 해당 결정의 자기 포켓몬·기술 슬롯과 연결한다.
후보 ID와 실제 전송 명령의 매핑은 실행기가 별도로 유지하며 후보 ID/순서/명령을 요약 추가로 바꾸지 않는다.

## 8. current_matchup — EX-112에서 추가한 후보별 요약

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
기존 v6 피해 계산의 네 가지 분기를 유지하면서 후보 요약에는 `current` 또는 해당 후보의
자기 테라 분기 `self_tera`만 복사한다. 상대 테라 가정 피해를 현재 확정 피해로 읽지 않는다.

- `blocked`: 지원하는 공개 규칙에서 충분한 차단 근거를 확인했다.
- `reflected`: 해당 효과가 반사되는 경우이며 후속 연쇄 효과까지 예측한 것은 아니다.
- `no_known_blocker`: 알려진 차단 근거가 없다는 뜻으로 실행 성공을 보장하지 않는다.
- `unknown`: 근거 부족·미지원 등의 미확정 상태다. 효과 없음·면역 해제를 뜻하지 않는다.
- 피해와 상태이상 성분은 별개다. 부가 상태이상이 막혀도 피해 기술 자체는 유효할 수 있다.
- 고정/비율 피해에는 약점·저항 배율을 그대로 곱하지 않는다는 별도 설명이 있을 수 있다.

## 9. 실제 OpenAI Decisions 요청 포장

다음은 값 일부를 생략한 구조 예시다. `input`과 각 `description`의 실제 자료형은 **JSON 문자열**이다.

```json
{
  "model": "gpt-6-luna",
  "input": "<state 전체를 직렬화한 JSON 문자열>",
  "questions": [
    {
      "name": "action",
      "type": "choice",
      "instructions": "<기존 행동 선택 지시문>",
      "choices": [
        {
          "value": "move_1",
          "description": "<move_1 후보 전체의 JSON 문자열>"
        },
        {
          "value": "switch_5",
          "description": "<switch_5 후보 전체의 JSON 문자열>"
        }
      ]
    }
  ]
}
```

| 논리 입력 | 실제 요청 위치 |
|---|---|
| `state` 전체 | `input`을 JSON 해석한 값 |
| `questions.action.type` | `questions[0].type` |
| `questions.action.instructions` | `questions[0].instructions` |
| `criteria`의 후보 ID | `questions[0].choices[].value` |
| 각 후보 설명 객체 | 같은 항목의 `description`을 JSON 해석한 값 |
| 기술 후보의 `current_matchup` | 해당 기술 후보 `description` 내부 |

따라서 전체 타입 상성표·팀·현재 상태·기존 계산 정보는 `input`에,
후보별 요약은 각 기술 후보의 `description`에 들어간다.
합법 후보가 하나뿐인 결정은 원래 정책대로 자동 선택하므로 API 요청을 만들지 않는다.

manifest의 프로필/출처, `input_audit`, 실제 전송 명령, 뷰어의 전체 공개 로그는 별도 기록이다.
뷰어에서 응답 ID에 붙인 실제 기술·포켓몬 이름은 표시용이며 수집 당시 요청/응답을 변경하지 않는다.

## 10. 해석 규칙과 근거

`unknown`은 증거 부재, `confirmed_absent`는 확인된 부재,
`not_applicable`은 적용 대상 아님이다. 빈 주요 `status`, 빈 능력 변화/일시 효과 맵의 의미는
해당 `information_rules`·지시문을 따른다. 타입 배율 0, 계산 피해 0, 공개 효과 차단,
상태이상 차단은 서로 다른 항목이다.

- [EX-112 입력 프로필·실험 기록](../experiments/EX-112-openai-candidate-matchup-battle.md)
- [C-081 후보 요약 계약](../CONTRACTS.md#c-081--후보별-현재-대면-요약)
- [구현 설명](../../../../integration/candidate_matchup/README.md)
- [v6 입력 생성](../../../../integration/pokechamp/jev_v6.py) · [v6 지시문](../../../../integration/pokechamp/prompts/jev-choice-v6.txt)
- [요약 추가·제거](../../../../integration/candidate_matchup/summary.py) · [적용 어댑터](../../../../integration/candidate_matchup/adapter.py)
- [API 요청 변환·역변환](../../../../integration/openai_decisions_battle/core.py)
- [저장 입력 예시](../../../../exports/battle_viewers/ex112-ui-v1-names/battle-1/decisions.json): `decisions[].observation`과 `decisions[].request`를 구분해 읽는다.
- [원자료 출처](../../../../exports/battle_viewers/ex112-ui-v1-names/provenance.json)

이 설명은 입력의 구성과 해석 범위에 관한 것이다. 모델이 모든 필드를 활용했다거나,
이 구조가 전략적 사고·일반 승률을 향상시킨다는 검증으로 사용하지 않는다.
