# EX-022 상태 전달 감사

- 날짜: 2026-09-08
- 범위: protocol/request → pinned parser → 정규화 관측 → 계산/요약 입력.
- 관련: [D-024](../research/input-and-memory/decisions/D-024-state-summary-thinking.md),
  [EX-022](../research/input-and-memory/experiments/EX-022-state-summary-thinking.md), C-016.
- 원본: EX-016 io actor 12개 첫 요약 경계, 기존15장면, 독립 메모리 내 Showdown fixture.
  fixture의 simulator 내부 HP/slot truth는 검증에서만 사용하며 모델 입력에 포함하지 않는다.

## 오류 위치 → 재현 근거 → 수정 → 독립 검증

| 위치/오류 | 원본 재현 근거 | 수정 | 독립 검증 |
|---|---|---|---|
| calculations.compute: Future Sight 경과 counter를 시작 턴으로 전달 | Pokemon.start_effect는0으로 시작하고 end_turn마다 증가. Showdown moves.futuresight는 시전자 -start, conditions.futuremove는 대상 slot을 소유 | protocol 시작 행의 발생 턴·ref·시전자·대상 slot을 저장. pending/history를 parser counter와 분리 | state_lifecycle.cjs: 시전자/대상 교체 후 예약 유지, 면역, 중복 시전 실패, 기절 대상에 대한 무피해 만료. 원본 scene1/2/5/10 교차 대조 |
| state.hypotheses: 소모된 상대 item=None을 미상으로 처리하여 prior 아이템 재도입 | Pokemon 초기값 unknown_item, end_item은None; scene4/8의 Ruination 뒤 Balloon 소모 | None/빈 문자열은 알려진 아이템 없음. unknown_item에만 prior 적용 | 소모 이후 모든 hypothesis item="" 검사; 원본 Balloon→Ruination→Earthquake 대조 |
| public_revelations: 과거 -ability 보완값이 -endability/교체 뒤에도 현재값을 덮어씀 | parser는 -endability에None을 저장하지만 보완 dict는 과거 특성 유지 | 공개 억제는 빈 특성으로 명시, 알려진 원래 특성/임시 특성을 구별하고 교체 시 복구 또는 미상 처리 | 특성 변경→억제→양측 교체 fixture에서 이전 임시 특성 재사용 차단 |
| Pokemon.effects: 기절 후/가족 효과 종료 후 남은 marker를 현재 효과로 전달 | faint는 HP/status만 변경. -end Quark Drive는 QUARK_DRIVE만 제거할 수 있어 QUARKDRIVESPE 잔류 | parser_effects 원값 보존; effects에는 기절·명시 종료를 반영. Future Sight는 slot 상태로 이동 | 실제 parser counter 및 faint, Quark Drive 가족 종료 검사; 기존64개 난수/활성 특성 계산 비교 유지 |
| opponent_specs: 공개100/99 HP 범위와 ceil 경계 오류 | Showdown Pokemon.getHealth는 ceil(hp/max*100) 후 부상100을99로 낮춤. max100의 HP7도 부동소수점 순서로8 표시 | 서버 계산 순서와99 예외를 그대로 적용한 정수 HP 열거의 양 끝 사용. 빈 지원집합/다른 scale은 오류 | max100/301/349/383/513의 전체1..max HP를 실제 getHealth와 독립 대조 |
| normalize 강제 교체 원인: 이전 턴/상대 pivot·Eject 이벤트를 역검색할 수 있음 | 원본에는 turn 마커 이전 pivot 선택과 교체가 여러 packet에 분산 | 현재 행 턴 안의 해당 actor 사건만 원인 후보. 근거 없으면 UNKNOWN | 원본 forced/pivot 경계와 actor 교환 검사; 미래 pending action은 계속 UNKNOWN |
| ability_effects: 복수 boosted stat이 순회 순서로 덮어써짐 | 상충하는 QUARKDRIVESPE/SPA 상태를 주입하면 마지막 값 선택 | 복수 활성 stat은 CalculationError | 상충 상태가 계산 전에 거부됨 |
| cloud/report: 누락된 provider token을0으로 표시 | 기존 _field(...,0) or0이 누락/실제0을 합침 | 응답별 누락은None, 확정 token 합과 완전성 분리. 진단 worker는 metadata 실패로 중단 | 토큰 없는 fake response 보존 및 집계 missingness 검사 |
| EX-021 weather 의미/수기 턴 오류의 재발 위험 | scene1 시작8/마지막10, scene3 시작3/마지막9; packet 끝 다음 turn은 앞 사건의 턴이 아님 | parent protocol 공통 해석. 평가 기준은 원본에서 별도 작성한 exact row/turn/actor/self request assertion | 입력과 정답에 같은 잘못된 턴을 넣어도 각각 원본 비교에서 실패 |
| **Cloud 후 발견 / EX-022 무효화:** 공개 발동 특성 누락 | scene1 event58 line5, turn7: Supreme Overlord 발동. 당시 s01.json은 ability=null/ability_known=false. effects에는 SUPREME_OVERLORD/FALLEN3이 있어 내부 의미 모순 | halt를 먼저 봉인. 이후 로컬에서 검증된 세 발동 형식(Supreme Overlord/Quark Drive/Protosynthesis)을 holder에 전달. 임시 특성을 원래 특성으로 확정하지 않음 | 원본 12장면의 공개 발동 행/최종 필드 별도 대조, 세 특성의 억제·교체 수명 및 input/reference/annotation 동시 오염 검사. 당시 입력은 새 독립 검사에서 실패해야 함 |
| **중단 후 보고 경계:** 기존 invalid_report의 EX-021 원인·144슬롯 설명이 새 profile에 부적합 | EX-022 입력 오류를 기존 경로로 보고하면 weather 원인 및 다섯 대비 설명을 사용함 | thinking profile의 오류 원문·조건별 노출·유효0/미완료 분모·실측 비용 보고. 봉인 실패의 hash와 manifest/collection 연결 확인 | fake72 수집 후 input halt; 보고 재읽기 불변·평가 복구/재제출 거부·실패 근거 변조 거부 |

## 전달 필드 전체의 의미·출처·경계

배열의 `[]`와 통계/효과의 `*`는 모든 원소/키를 뜻한다. `self_team`의 원 request 필드는
추가·삭제·값 변경 없이 전달하며 독립 검증기가 최신 원 request의 모든 키를 대조한다.
아래 표와 최종 field-inventory.json은 전달 필드 목록/검증 근거다. 미지원 상태를 계산 가능으로
분류하지 않는다.

| 필드 | 원본 및 parser | 정규화·계산/요약 의미 | 검증/제한 |
|---|---|---|---|
| identity.battle_id/actor_id | actor bundle/원 player 행 | 배틀·진영 identity; 모든 경계에 동일 | actor seal·외국 actor request 거부·원 player 행/decision 연결 |
| identity.decision_seq/request_id/showdown_turn | decision_start, request.rqid, parser.turn | 결정 순서/요청 식별/현재 턴. 서로 대체하지 않음 | 첫10 sent / decision12 경계. 실제 사건 턴은 별도 행 순서 |
| identity.state_id | 직전 normalized core SHA256 | 계산 응답 freshness/동일 state 확인 | gate의 재계산 hash 및 calculator identity 검사 |
| request.kind/force_switch_cause/pending_opponent_action | 최신 forceSwitch 및 현재 actor 원본 사건 | 행동/강제 교체; 기절·pivot·item·UNKNOWN; 상대 미실행 행동은UNKNOWN | 살아 있는 forced target과 양측 기절 후 상대 미상 구별 |
| request.can_tera/legal_actions | 최신 available moves/switches/request와 player 후보 | 후보 JSON과 order 변환이 동일 목록 사용 | 기존 후보·중복·tera/강제교체 회귀 |
| self_team[].ident/details/species | 자기 request 원문/원래 자기 set과 유일 match | nickname·forme·gender·level identity 보존; species 정규화 | 정확 ident, 동종/모호성 거부. 상대 원본 세트 접근 없음 |
| self_team[].condition/active/hp_precision | 최신 자기 request | 정확 HP/최대HP/status 및 active. faint active는 강제 교체 대기 | 모든 raw 키 일치; HP 계산은 원 request condition 사용 |
| self_team[].stats.atk/def/spa/spd/spe | 최신 자기 request.stats | 원래 set의 IV/EV/nature로 계산한 rawStats와 대조 | Node expectedStats; 강화는 별도 boosts로 한 번 적용 |
| self_team[].moves[] | 자기 request.moves 및 원래 자기 set | 원 세트 기술. 현재 사용 가능 여부는 별도 후보 | 원래 기술 목록 변형은 명시적 미지원 |
| self_team[].ability/baseAbility | 최신 request | 현재 특성과 원래 특성 별도; 계산은 ability | 공개 활성 효과와 중복 적용 금지 |
| self_team[].item | 최신 request.item | 현재 보유/빈 문자열=소모 | 원래 세트 아이템으로 덮어쓰지 않음 |
| self_team[].teraType/terastallized | request | 선택 가능한 tera type과 실제 변신 분리 | 계산은 실제 terastallized만 반영 |
| self_team[].commanding/reviving/pokeball | request 원문 | parser 추정값으로 대체하지 않는 전달 정보 | singles 범위의 현재 값 보존; 새 doubles/부활 계산 지원 아님 |
| self_team[].original_set.nature/evs.*/ivs.*/level/tera_type | 자기 원래 team만 파싱 | 원래 자기 능력치 근거. 현재 상태를 덮어쓰지 않음 | 자기 rawStats 대조; 상대 원본 team 미사용 |
| self_team[].boosts.* | 공개 boost/unboost/set/clear 및 parser | 현재 단계. hp marker는 계산 옵션에서 제외 | 교체 clear; Node 범위 검사. entry 특성 중복 적용 억제 |
| self_team[].effects.*/parser_effects.* | parser 원값 + 공개 종료/faint 행 | 현재 유효 효과와 raw parser counter 분리 | Future Sight 경과 counter는 현재 slot 예약의 authority가 아님 |
| opponent_confirmed[].ident/species/level/types[] | 공개 switch/details/forme/tera와 parser | 공개 identity·현재 타입. 자기 exact HP와 분리 | 원본 protocol만 참조; 비공개 팀 주입 인터페이스 없음 |
| opponent_confirmed[].active/fainted/hp/max_hp/status/hp_precision | 공개 switch/damage/heal/status/faint | 마지막 공개 HP fraction. 교체된 bench의 숨겨진 회복을 채우지 않음 | 공개 범위 열거; 실 HP 정답과 구별 |
| opponent_confirmed[].item | 공개 item/enditem/발동 태그와 parser | unknown_item과 알려진 소모None 구별 | fixed prior는 미상일 때만 사용 |
| opponent_confirmed[].ability/ability_known | 공개 -ability/회복 귀속/억제/검증된 세 -activate 형식 및 parser | 알려진 absence/현재 특성/미상을 구별 | 다른 actor 회복을 자기 특성으로 귀속하지 않음. 공개 발동 검증은 중단 후 추가됐으며 당시 입력에는 누락 |
| opponent_confirmed[].moves[] | 공개 직접 move와 parser | 공개된 세트 기술. called/copied/Struggle/Recharge는 세트 근거 아님 | 기존 Knock Off·Future Sight 공개 전달 회귀 |
| opponent_confirmed[].boosts.*/effects.*/parser_effects.*/tera_type | 공개 변화와 parser | 현재 강화·정리된 효과·원 counter·실제 tera | 종료/교체/기절 경계; 추정 기술/세트는 별도 hypotheses |
| weather.* | parser는 upkeep마다 현재 turn 저장 | 마지막 weather protocol 턴 | 실제 시작은 protocol_state.weather.*.observed_start_turn |
| field.* | parser.field_start/end | field 설치/갱신 턴. 잔여 duration 아님 | terrain 교체 및 field 종료; 미지원 field는 계산 오류 |
| self_side_conditions.*/opponent_side_conditions.* | sidestart/end와 parser | Spikes/Toxic Spikes는 겹 수; 그 외 설치 턴 | 계산 field boolean/겹 수 변환; sides actor 방향 검증 |
| protocol_state.weather/field/sides | 원본 시작/유지/종료 행과 행 ref | 시작·마지막 갱신·겹 설치 각각 분리 | source row/turn 직접 대조; 시작 행 없으면None |
| protocol_state.pending_effects/delayed_history | move/-start/-end/turn/win 행 | 시전자와 대상 위치 분리, 교체 후 유지. 해결 관측/공개 해결 없이 만료/배틀 종료 구별 | 피해0·명중·미래 상대 상태를 임의 단정하지 않음; Gen9 turn255 overflow 예외 보존 |
| protocol_state.ended_ability_effects | -start/-end family 행 | 명시적 가족 종료가 남은 boostedStat marker보다 우선 | raw parser_effects 불변 |
| order_assessment.* | 고정 불확실성 문구 | 우선도/동률/미관측 세트 조건부이며 실행 순서UNKNOWN | raw speed로 실행 확정 금지 |
| opponent_hypotheses[].spread/item/ability/moves/confirmed_moves/ivs/source/coverage/joint_probability | 고정 prior + 공개값 제한 | marginal 조합, 대표 범위, joint_probability=None | 확정 공개값 보존; 미지원/빈 prior fail; 원 상대 truth 미사용 |
| recent_events/source_events/source_event_ids | actor의 경계 이전 protocol_in | 원문·event_seq·원 metadata 보존. request 반복 축소 없음 | 정확 prefix 대조, 미래/외국배틀/actor 차단 |
| calculation_bundle.identity/engine/version/patch/generation/status | Node wrapper 응답 | 고정0.11.0+ruination-v1 및 파일 hash | Python/Node handshake 및 결과 identity 검사 |
| calculation_bundle.entries[].damage_range_hp/damage_rolls/defender_max_hp/move | Node의 해당 scenario 계산 | hit 조건부 uncapped 수치. HP 감소/KO율과 별도 | 사후3건·기존 기술/Quark/Supreme/중복회귀 |
| calculation_bundle.entries[].conditional_order/excluded_with_reason/effect_assessment/ko_chance_given_hit/survival_given_hit | Node wrapper | 우선도·속도 조건/미지원 원인. KO/생존확률None | status 기술0피해를 지원 성공으로 바꾸지 않음 |
| calculation_bundle.coverage/pending_effects/uncertainty/elapsed_ms | scenario 생성/공개 slot 상태/단조 시계 | 공격자·방어자와 양 side를 함께 교환, 미래 피해 별도, 계산 경과 | 허용 기술 범위 확대 없음; Protect/Substitute/Roost 등 계속 거부 |
| condition_id/lesson_memory/battle_summary/previous_summary/summaries | parent condition/동일 actor BattleMemory | 조건C, 배틀간 lesson 없음, 이전 요약 동일 배틀만 | 이번 first-summary는 previous=None;31행동 cadence 회귀 |
| output_identity_format/harness_annotations | 공통 memory.summary_context/protocol.annotate | 원본 보존 설명·HP 차감/행 참조·숫자 의미 | 정답/평가 rubric import 금지. 독립 oracle로 원본 대조 |
| role/summary_thinking_effort/실제think/request.thinking_effort | FixedBackend의 요청별 선택 | summary/rollup에만 low/high. 행동과 default low | 동일 backend high→행동low→rolluphigh→행동low 검증 |
| response prompt_tokens/completion_tokens/http_elapsed_ms/elapsed_ms | 실제 provider 응답/transport 시계 | 확정 token 합과 미확정 개수, 실제HTTP/요청 latency 분리 | 토큰 누락None; 환경/metadata 오류 전체 중단 |

## 독립 평가 감사

기존122개 필수 사실의 문장을 12개 원본 prefix 전체에 대조했다. HP·생존·피격 연결·actor·
발생 턴·효과·아이템 문장에 새 사실 오류를 발견하지 않았다. 과거 EX-021에서 교정된 sun
문구(8/10 및3/9)는 다시 검증했다. 일부 사실이 설치 행과 다음 turn 행을 함께 참조하므로
각 evidence에 실제 행의 `turn`과 `parts`를 명시적으로 고정했다. 모든 자기 HP 사실은
`self_request`의 ident/details/condition/active를 원 request와 직접 대조한다. identity 사실은
별도 원 decision/request identity와 연결한다. 이122개 단위와 rubric은 응답을 보기 전에 봉인한다.

입력 annotator·평가 authoring·평가 검사기는 별도 코드다. oracle은 입력과 정답 사이의 일치만
보지 않고 각자를 원본과 대조한다. annotation turn/actor/HP/숫자 의미, reference turn/actor/
자기HP, 양쪽 동시 턴 오염, 미래 원본을 주입한 실패 검사가 포함된다. retained/incorrect/
omitted를 분리하며 모순된 참/거짓 문장이 같이 있어도 단순 retained로 통과시키지 않는다.

최종 명령·분모·source/output hash·실행 결과는 EX-022 verification receipt와 실험 보고서에
연결한다. 이 감사는 계산기 전체 기술 지원이나 운영 Cloud 자격을 주장하지 않는다.

## 사전 통과의 한계와 중단 후 교정

415개 경로 inventory와289검사 통과는 상대의 공개 특성 발동과 최종 `ability/ability_known`
일치를 증명하지 못했다. 행 참조가 보존되고 계산용 SUPREME_OVERLORD marker가 맞아도,
요약용 특성 필드에는 원문과 상충하는 미상이 남을 수 있었다. 따라서 위 사전 감사만으로
상태 의미 전체가 검증됐다는 결론을 철회한다. 단일 필드 열거 또는 raw roundtrip을 의미
정확성 검사로 대신하지 않는다.

중단 후 검사는 운영 `public_revelations`를 호출하여 정답을 만들지 않는다. 별도 oracle이
원본 `-ability`, 지정된 세 `-activate`, 억제·교체 행을 직접 따라가 현재 공개 특성과 대조한다.
scene1의 누락 및 다른 actor의 Quark Drive로 바꾼 입력, 입력/주석/수기 기준을 함께 잘못
만든 경우 모두 거부한다. 검사 범위는 명시된 원문 형식이며 Wandering Spirit 등 다른 actor의
특성까지 교환하는 activation을 일반화하지 않는다.

당시 manifest·12입력·122기준·72응답·289회귀 receipt·첫 시계는 불변이다. 공개 특성 누락
발견 후 중단 봉인보다 먼저 코드를 수정하지 않았다. 중단 후 수정 source는 보고서의
`analysis_source_differences`와 별도 로컬 검증 receipt로 식별한다. 무효 초안6/72 및 검토
중단66/72를 보존하며 low/high 효과와 조건별 오류 재현율은 산출하지 않는다.

최종 로컬296회귀(기존244+추가52,90.86초), Ruff·compileall·Node11,
15장면 구조/의미 및 사후3건이 통과했다. 추가 회귀의 첫51/52 통과에서 나머지1건은
불변 seal을 덮어쓰려던 테스트의 변조 주입 방식 오류였다. 임시 fixture의 기존 파일과
sidecar를 제거한 뒤 재봉인해 halt evidence mismatch를 실제 검증하도록 고쳤으며
실제 봉인 자료는 수정하지 않았다. 실패 로그와 최종 통과 로그를 함께 보존한다.
