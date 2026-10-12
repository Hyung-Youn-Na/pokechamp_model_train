# B 행동 입력 필드 설명서

## 새 공식 관측 버전 v1.4.0

새 B/B2 준비는 공식 관측 설명서 v1.4.0을 명시적으로 선택한다. 관측 출처·미확인 값·공식 효과 배열과 기간·행 경계 및 최근 창의 `line_offset`을 정의한다. 계산 의미 버전과 선봉 정책은 별도로 유지한다.

[공식 관측 안내](../integration/pokechamp/observation/README.md) · [fields.json](../integration/pokechamp/improved_io/prompts/battle-v1.4.0/fields.json) · [검증 보고](../project_context/exec-plans/evidence/ep056/report.md)

## 보존된 v1.3.0 설명·사전

명시적 legacy 새 B 준비는 v1.3.0을 선택한다. B2와 선봉에도 실제 전송 구조 설명과 요청별 상세 효과 사전을 추가했다. 아래 v1.1/v1.2 기록과 자산은 보존한다.
선봉의 추가 타입/기술/가능성 필드는 [D-061 규칙 안내](../integration/pokechamp/lead_rules/rules-guide.txt), 적용/보존 경계는 [C-040](../project_context/CONTRACTS.md#c-040-lead-components)을 따른다.

[상세 계약·생성법](../integration/pokechamp/effects/README.md) · [검증 보고](../project_context/exec-plans/evidence/ep046/report.md)


보존된 계산 의미 설명서의 근거는 [D-035](../project_context/decisions/D-035-calculator-input-audit.md)의 v1.2.0이다.
[새 fields.json](../integration/pokechamp/improved_io/prompts/battle-v1.2.0/fields.json)과
[provenance](../integration/pokechamp/improved_io/prompts/battle-v1.2.0/provenance.json)는
calculator-input-v2의 Pokémon 소비 이력·타입/테라·phase·진입 HP/아이템·damage_variants·해시를
설명한다. 새 필수 상태가 없으면 실제 호출 전에 거부한다. 기존 v1.1 자산·봉인은 보존하며
아래 D-031의 설명서 구성 원리는 새 버전에도 적용된다.
[검증·지원 경계](../project_context/exec-plans/evidence/ep023/report.md)를 함께 따른다.

[D-031](../project_context/decisions/D-031-battle-field-guide.md)의 행동 v1.1.0은 요약 없는
`io-battle-only-v1` B에서 입력 필드의 의미를 설명한다. 기술·특성·아이템의 효과 사전이나
장면 정답·추천 행동은 추가하지 않는다. 기존 policy 및 출력 계약은 그대로 결합한다.

## 단일 자산과 전달

[fields.json](../integration/pokechamp/improved_io/prompts/battle-v1.1.0/fields.json)이 해당 v1.1.0의
작성 원본이다. v1.2.0은 별도 자산을 사용한다. `roots`, 재사용 `definitions`, 동적 `key_rules`, 공통 해석 `rules`가 있으며
[battle_prompts.py](../integration/pokechamp/improved_io/battle_prompts.py)의 `render()`가
삽입 순서대로 전체 JSON 경로·자료형·설명을 출력한다. `$`는 행동 JSON, `RequestJSON`은
원문 `|request|` 뒤 JSON, `[]`는 배열 원소, `{kind}`는 명시된 동적 키 규칙이다.
각 자식은 별도 설명이 없으면 부모의 출처·시점·단위를 상속한다. 누락과 빈 값은 필드별
의미를 따르며 기존 runtime gate의 필수 필드·후보·계산 identity 계약을 대체하지 않는다.

`assemble()`는 기존 `battle_fixed.txt`와 설명서를 결합한다. prepare가 실제 문자열을
`battle-prompt.json`에 봉인하고 worker와 actor가 같은 함수로 요청마다 시스템 메시지를
구성한다. backend는 실제 system 문자열과 user JSON을 다시 대조한다. 사용자 JSON은
변경하지 않으며 시스템 설명서는 한 번만 전달된다.

`battle_prompt_version`과 `battle_prompt_identity`를 manifest와 execution evidence에 기록한다.
Identity에는 원본 정책·필드 자산·렌더링 설명서·완성 prompt의 SHA-256이 있다. request trace에도
같은 identity를 넣으며 선택·준비·전송의 불일치는 거부한다. 최종 `study.battle_checks`도
봉인된 버전으로 실제 system/요청 identity를 대조하며 과거 v1.0.0의 metadata 부재는 허용한다. 새 prepare 기본은 v1.2.0,
버전 없는 과거 설정 및 기존 요약 실험의 행동 선택은 v1.0.0이다. 과거 receipt의
`current=False` 검증은 당시 봉인 출력과 archive를 확인하며 새 필드 검사를 소급하지 않는다.

경로 검사는 배열·객체를 재귀 순회하고 효과·능력치 등 동적 키의 값에도 적용한다. 원문
문자열 자체에는 프로토콜 문법·행 순서·시점 규칙을 제공한다. 포함된 request JSON은 줄의
나머지 전체를 파싱하므로 이름 안 `|`를 손실시키지 않으며 중첩 필드도 검사한다. 새로운 필드를
추가하거나 기존 설명을 제거하면 경로를 보고하고 실패한다. 문자열의 모든 프로토콜 종류에
게임 의미를 부여하는 parser 확장은 아니며 미해석 행의 한계도 설명한다.

## 의미와 독립 근거

Pinned PokéChamp `0f84c460319ebe733f8c3028e58a2a5452c60d85`, Showdown
`e64915c0eab066db1d3e732b1280386468dd7415`, calculator `0.11.0+ruination-v1`을 대조했다.
기존 [상태 필드 감사](../project_context/experiments/ex022-state-audit.md)와
[입력 구조](pokechamp-input-summary.md)는 보조 근거이며 과거의 검증 한계도 유지한다.

| 구분 | 설명서 의미 | 구현·독립 검증 근거 |
|---|---|---|
| 턴·결정·요청·이벤트 | 현재 parser 턴과 행 발생 턴을 구별. decision/rqid/event_seq/line은 별도 축 | `state.normalize`, `protocol.protocol_rows`; Showdown `server/room-battle.ts`의 rqid 증가; 15장면 원문·도달성 감사 |
| 상대 types/tera_type | parser tuple의 원래 보조 타입 잔류를 현재 이중 타입으로 해석하지 않음 | pinned `Pokemon.types/type_1/type_2`와 실제 Gliscor 테라 fixture; 입력 교정 없이 한계 명시 |
| 정확한 자기/공개 상대 HP | 자기 condition은 정확한 HP, 상대 분모100은 공개 척도. 부상100→99 예외 및 float 순서 | Showdown `Pokemon.getHealth()` 직접 실행과 `public_hp_bounds` 대조; 가설마다 다른 최대 HP |
| 0과 효과 존재 | `CONFUSION: 0`도 존재. turn/action counter와 presence marker는 기간과 다름 | pinned `Pokemon.start_effect/end_turn`, `Effect` 분류 전체와 대조 |
| parser/current 효과 | parser 잔류와 기절·종료 가족·지연 효과를 제거한 현재 map 분리 | `protocol.live_effects`, 실제 parser 및 기존 수명 회귀 |
| 설치·갱신 | Spikes/Toxic Spikes는 층수, 다른 side/field는 설치 턴. weather는 upkeep 포함 최신 갱신 턴 | pinned `AbstractBattle._side_start`·weather/field 분기, 실제 3턴 설치→4턴 upkeep와 별도 원문 시작 ref 대조 |
| item/ability 빈 값 | unknown_item만 prior 미상. item None/빈 값은 소모·없음. 억제된 ability 빈 값과 null 미상 분리 | `Pokemon.end_item`, `state.public_revelations/hypotheses`; 기존 공개 item/ability 회귀 |
| 지연 효과 | 시전자/대상 slot/현재 occupant/미래 해소를 구별, start 없는 해소·무피해 만료·배틀 종료 포함 | 독립 `state_lifecycle.cjs`와 `protocol.observed_state` 분기, late-turn 만료 추론 한계 명시 |
| 계산 | HP 조건부 범위·시나리오 연결. 제외와 미지원과 null 확률은 서로 다름 | `calculations.py`, `calculator/worker.cjs`; 변화기·상대 미상 교체·다중타격 출력형 fixture |
| 원 request | move 슬롯/PP/제한·forceSwitch/wait/preview/tera 및 선택적 legacy mechanic 형태 | Showdown `Pokemon.getMoveRequestData/getSwitchRequestData`, `SideRequestData`, `Battle.makeRequest`; 별도 수기 fixture |

원문에 없는 시작 시점·남은 기간·미래 상대·행동 실행·KO/생존 확률은 설명서가 보충하지 않는다.
계산은 공개 범위와 대표 prior에 한정되며 전체 switch/entry/잔여 피해/회복 순서를 모사하지 않는다.
이 한계를 숨기지 않으며 계산기의 지원 범위나 가설을 이번 변경으로 확대하지 않았다.

## 검증 및 자원

[test_battle_field_guide.py](../integration/pokechamp/tests/test_battle_field_guide.py)는
15장면 사용자 입력 불변·선택적 분기·누락/추가 필드 음성 검사·pinned 수치 의미·실제
worker/actor 무네트워크 요청·버전/해시 거부·과거 receipt를 검증한다. 전체 회귀와
새 fake32 결과·보존·정리 증거는 [EP-019](../project_context/exec-plans/completed/EP-019-battle-field-guide.md)에 연결한다.

현재 시스템 입력은 72,980자/72,992 UTF-8 bytes이며 기존 대비 매 행동 요청당
64,751자/64,759 bytes 증가한다. 사용자 JSON 크기는 그대로이며 입력별 총량은 준비의
`battle-prompt.json.input_sizes`에 있다. 모델 tokenizer 비용/지연은 측정하지 않았다.
Cloud 호출·실제 배틀 재개는 0이며 EX-026의 4응답·halt·시계·Blocked를 보존한다.
필드 완전성과 로컬 전달 검증을 모델 오류 감소나 Cloud gate 통과로 해석하지 않는다.

최종388회귀와 새fake32 32/32·실제 동시10·64봉인·B400행동의 문자열/identity/설명서1회·
요약0을 검증했다. 첫 로컬 startup timeout 자료와 이후 구형 final checker의 v1.0.0 고정 비교
실패도 보존했고, 버전 비교 교정·음성 회귀 후 최종 source로 새32 전체를 검증했다.
Native library thread1 조건과44,000기존파일·credential/포트/프로세스 검증은
[종료 증거](../project_context/exec-plans/evidence/ep019/verification.json)에 있다.
[렌더링한 영문 설명서](../project_context/exec-plans/evidence/ep019/field-guide.txt)는
위 단일 JSON 자산의 검증된 파생물이다.
