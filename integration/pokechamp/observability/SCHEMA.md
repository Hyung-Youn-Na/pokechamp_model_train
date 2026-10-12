# PokéChamp research battle bundle schema v1

이 문서는 [`C-009`](../../../project_context/CONTRACTS.md)의 구현 field catalog다. 규범적 boundary와
변경 권한은 Contract와 [`D-010`](../../../project_context/decisions/D-010-adopt-pokechamp-battle-observability.md)이
우선한다.

## Bundle identity와 source evidence

경로는 `<POKECHAMP_DATA_ROOT>/experiments/<experiment_id>/battles/<battle_id>/`다. 두 ID는
`[A-Za-z0-9][A-Za-z0-9._-]{0,127}`을 만족하고 `.` 또는 `..`가 아니어야 한다.

Source evidence는 다음 파일뿐이다.

| 파일 | 역할 |
|---|---|
| `manifest.json` | Battle identity, configuration, source provenance, 시작·종료, result, completeness |
| `events.jsonl` | 한 줄에 한 event인 ordered append stream |
| `checksums.sha256` | Final `manifest.json`과 `events.jsonl`의 SHA-256 seal |

`showdown.log`, `replay.html`, `report.html`, experiment의 `catalog.sqlite`와 `index.html`은 derived
output이며 seal에 포함되지 않는다.

## Manifest

Required top-level fields는 다음과 같다.

| Field | Type / meaning |
|---|---|
| `schema_version` | integer `1` |
| `classification` | `research_observability` |
| `efficacy_evidence` | 항상 `false` |
| `experiment_id`, `battle_id` | bundle identity |
| `replacement_for` | correction 대상 battle ID 또는 `null` |
| `battle_format`, `showdown_battle_tag` | format과 실제 Showdown room identity |
| `teams`, `model`, `source`, `metadata` | team 원문/해시, model request 설정, source SHA, sealed run metadata |
| `started_at`, `ended_at` | UTC RFC 3339 timestamp; 진행 중이면 `ended_at=null` |
| `evidence_complete` | Recorder가 모든 event와 final manifest를 기록했는지 여부 |
| `sealed`, `seal` | source close/checksum 상태, algorithm, file 목록과 seal UTC |
| `logging` | event high-watermark/persisted count, decision/LLM call/error count |
| `result` | `outcome`과 battle 또는 failure detail |

`evidence_complete=false`는 battle 패배를 뜻하지 않는다. Logging gap/partial source를 뜻한다.
`player_lost`, `tied`, `interrupted`, `provider_failure`도 recorder가 모든 evidence를 보존했다면
complete일 수 있다. Checksum validity는 source byte integrity이며 completeness와 별도다.

현재 controlled research command는 `metadata.showdown_forcetimer=false`와
`metadata.battle_timer_requested=false`를 기록한다. Timed run을 새로 추가하면 실제 activation과
설정을 metadata 및 protocol evidence에 기록해야 하며 untimed identity를 재사용하지 않는다.

## Event 공통 필드

모든 `events.jsonl` object는 다음 field를 가진다.

| Field | Type / meaning |
|---|---|
| `schema_version` | integer `1` |
| `experiment_id`, `battle_id` | manifest와 동일한 identity |
| `event_type` | 아래 고정 enum 중 하나 |
| `event_seq` | battle 내 1부터 증가하는 integer; write failure가 있으면 gap이 남을 수 있음 |
| `timestamp_utc` | event wall-clock UTC |
| `monotonic_offset_ms` | recorder start 기준 monotonic milliseconds |

`decision_seq`는 battle 내 각 action 판단의 identity다. Team preview, 정상 turn action, 강제 교체와
server rejection 뒤 재판단은 각각 새 sequence를 받는다. `showdown_turn`은 UI 표시 값일 뿐 identity가
아니다. `llm_call_seq`는 battle-global 논리 호출 identity이며 상위 caller의 재질의/retry, SC 또는 ToT call을 별도 event로
남긴다. D-058의 동일 입력 HTTP 연결 재시도는 아래 추가 metadata에 별도 시도로 기록한다.

## Event type

| Type | 주요 payload |
|---|---|
| `battle_start` | format, teams, model, source, replacement identity |
| `protocol_in` | exact reconstructed inbound `protocol`, battle tag, display turn |
| `decision_start` | `decision_seq`, `decision_kind`, decision-time `battle_state` |
| `llm_call` | decision/call ID, effective prompts, reasoning, raw/parsed output, request/response metadata, validation |
| `decision_result` | canonical final output, validation과 player가 선택한 action |
| `wire_action` | action, exact `wire_payload`, room, `sent`/`failed` status |
| `battle_end` | terminal outcome, result/error와 final display turn |
| `logging_error` | 실패 operation/type 및 가능한 경우 실패 event identity |

## Security와 evolution

Prompt, reasoning, raw model content, username과 protocol은 untrusted text다. Renderer는 이 값을 HTML
markup이나 executable script로 삽입하지 않고 escape하며 CSP를 적용한다. `OLLAMA_API_KEY`의 현재
process 값이 payload에 우발적으로 포함되면 source write 전에 `[REDACTED]`로 치환한다.

Schema field를 추가하는 backward-compatible reader 변경은 새 minor implementation으로 처리할 수
있다. 의미 변경, source file/write authority 변경 또는 기존 reader가 안전하게 해석할 수 없는
변경은 새 schema version과 project decision이 필요하다. 원 bundle을 migration 결과로 덮어쓰지
않는다.

## D-012 benchmark consumer

C-010 benchmark는 v1 bundle을 actor별로 두 개 생성하며 `metadata.actor_id`, `slot_id`,
`battle_seed`, actor별 local seed를 기록한다. Source bundle의 기존 분류와 효능 false는 바뀌지
않는다. `llm_call.request`에는 `call_role`과 해당 호출의 `target_state`가 추가된다.
이는 현재 decision의 실제 상태와 search leaf/상대 예측 상태의 구별을 위한 additive metadata다.
두 actor 결과와 실제 simulator seed는 별도 sealed match record가 검증·연결한다.

Benchmark validation의 `role_contract_valid`는 역할별 JSON 계약 검증 결과다. `tool_choice`와
`state_value`는 실제 행동이 아니므로 `battle_action_valid=null`로 기록한다.

D-013 이후 max_output_tokens/requested_output_tokens는 131072다. context_window=null은
num_ctx 생략을 뜻하며 실제 provider context 용량 측정값이 아니다. Model manifest의
context_window_policy=provider_default가 이를 명시한다. 이전 bundle은 변경하지 않는다.

### D-016 추가 HTTP 관측 필드

`llm_call.response`에 `permit_wait_ms`, `network_called`, `http_started_at`,
`http_finished_at` (UTC epoch seconds), `http_elapsed_ms`, `http_status`,
`retry_after`, `cooldown_seconds`가 선택적으로 추가된다. 기존 bundle에는 없을 수 있다.
`elapsed_ms`는 backend 호출 전체(로컬 admission 포함), HTTP 시간은 `http_elapsed_ms`,
decision 시간은 decision_start→wire_action으로 구별한다. Provider 내부 대기는 알 수 없다.
Broker 반환 실패 뒤 이미 받은 응답은 raw_content/token과 함께 보존하되 configuration
failure로 기록하고 후속 호출을 차단한다. Broker 메시지에는 prompt/credential을 넣지 않는다.


## C-033 선봉 요청

새 `b2-llm-lead-v1`의 manifest metadata는 actor의 `team_preview_policy`와
`team_preview_prompt_identity`를 기록하고 `result.team_preview`는 최종 선발 상태/명령/실패를 연결한다.
기존 설정에는 이 필드를 소급 추가하지 않는다. `decision_kind=team_preview`, `showdown_turn=0`의
한 결정에 최초 `call_role=team_preview` 요청 최대1개가 연결된다. 중복 preview는 새 결정·호출·전송을 만들지 않는다.

요청 identity는 actor/battle/decision/request ID, actual side, input version/hash,
`public_preview_cutoff`, `self_request_ref`, 두 신호를 모두 받은 `protocol_cutoff`를 포함한다.
실제 system/user, prompt version/hash, model/options, 원문/reasoning, 엄격한 슬롯 검증과 사용량/지연은
기존 `llm_call` 필드에 보존한다. `decision_result.validation.team_preview`는 기존 seeded permutation과
선택 슬롯·생성 명령을 연결한다. 전송의 성공/실패는 `wire_action.send_status`로 별도 확인한다.
출력은 유효했어도 전송 실패·취소된 경기는 정상 선발·유효 승패로 집계하지 않는다.
Viewer는 준비 탭에 슬롯 설명을 추가하고 기존 실제 입력/응답/reasoning·전송 기록을 표시한다.

## D-058 논리 요청과 HTTP 시도

기존 `llm_call`은 backend 논리 호출의 최종 결과를 유지한다. `request`에
`transport_policy_version`, timeout 네 단계, `provider_retries`, `retry_delays_seconds`,
`logical_request_id`, `http_attempt_count`, `http_attempts`, `retry_outcome`을 추가한다.
HTTP 시도에는 1부터 시작하는 `http_attempt_number`, 원자 예약 `request_intent`,
permit/HTTP 시간, `network_called`, 상태·오류 종류·credential 제거 메시지와 내부 원인을 기록한다.
Admission 거부도 배열에 보존하며 `http_attempt_count`에는 실제 전송 시도만 센다.
동일 llm_call event와 logical_request_id가 모든 재시도 원장을 연결한다. 응답/token은 수신한
최종 응답에 한 번만 기록한다. 과거 필드 부재는 기존 단일 HTTP 시도로 해석한다.
추가 필드는 기존 논리 호출 결과·prompt·응답의 의미를 바꾸지 않는 schema1 확장이다.
