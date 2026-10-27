# L1–L5 이식 연구의 보존 맥락 — 실행 계약

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="c-001--상속된-agenticsts-context와-layer-write-authority"></a>
## C-001 — 상속된 AgenticSTS context와 layer write authority

- Reference agent는 이름이 있는 L1-L5 layer로 decision context를 구성하며, decision 사이에
  제한 없는 raw transcript를 계속 append하지 않는다.
- L1 system prompt와 L2 state-type prompt는 사람이 작성하며 postrun automation이 쓸 수
  없다. L3는 명시적인 game-update workflow를 통해 변경한다.
- L4 memory, L5 skill, dynamic evolution tool은 postrun에서 쓸 수 있는 surface다. Write는
  configuration, schema/validation logic, 해당 store lifecycle의 gate를 계속 적용받는다.
- 의도적으로 accumulating-context를 사용하거나 그 밖의 방식으로 contract를 깨는 비교는
  격리하고 experiment로 표시해야 하며 reference-agent path로 제시하면 안 된다.

현재 상세 내용: [`MEMORY_SYSTEM.md`](../../../AgenticSTS/docs/reference/MEMORY_SYSTEM.md) 및
[`SELF_EVOLUTION.md`](../../../AgenticSTS/docs/reference/SELF_EVOLUTION.md).

<a id="c-002--game-mod-transport"></a>
## C-002 — Game-mod transport

현재 server surface는
[`Router.cs`](../../../AgenticSTS-Mod/STS2AIAgent/Server/Router.cs)가 정의한다.

- `GET /health`는 service, protocol, mod, game, readiness data를 반환한다.
- `GET /state`는 현재 state payload를 반환한다.
- `GET /actions/available`은 action descriptor를 반환한다.
- `GET /events/stream`은 server-sent event envelope을 내보낸다. 15초 간격 comment가 stream을
  유지한다.
- `POST /action`은 하나의 flat action object를 받는다.
- `GET /debug/nodes`는 diagnostic endpoint이며 이 문서에서는 stable research interface로
  선언하지 않는다.

JSON 성공 response의 형태는
`{ "ok": true, "request_id": "...", "data": ... }`다. JSON error의 형태는
`{ "ok": false, "request_id": "...", "error": { "code": "...", "message": "...", "details": ..., "retryable": bool } }`다.
성공한 action data는 현재 `action`, `status`, `stable`, `message`, `state`를 포함한다.

Action request는 `action` 이름과 `card_index`, `option_index`, `target_index` 같은
action별 parameter를 가진 flat object다. 정확한 builder는
[`actions.py`](../../../AgenticSTS/src/mcp_client/actions.py)에 있다. Default address는 loopback port
8128이며 설정할 수 있다. Python client는 envelope을 unwrap하고 보고된 failure에 대해 typed
client/action error를 raise한다.

<a id="c-003--state-및-index-표현"></a>
## C-003 — State 및 index 표현

- Mod는 `run_id`, `screen`, `session`, `in_combat`, `available_actions`와 활성 game surface의
  optional typed payload를 가진 versioned root state를 내보낸다. 정확한 producer는
  `GameStateService.BuildStatePayload`이며 Python mirror는
  [`upstream_models.py`](../../../AgenticSTS/src/mcp_client/upstream_models.py)다.
- Python raw-state model은 frozen이며 알 수 없는 extra field를 무시한다. 이는 forward-tolerant
  동작이지만, 누락된 required field나 잘못된 type을 유효하게 만들지는 않는다.
- `parse_state`는 state object 또는 그 response envelope을 받아 검증하고 state type을 파생한
  뒤 frozen `GameState`를 반환한다. Validation failure에는 `StateParseError`를 raise한다.
  `safe_parse_state`는 recovery path를 위해 그 failure를 `None`으로 변환한다.
- Local schema/builder가 명시한 choice 및 card index는 zero-based다. Target이 필요한 card와
  potion은 state가 제공한 target index space와 유효한 target index를 사용해야 한다.
- `available_actions`는 coarse action-type capability list이며 action이 실행 가능하다는 완전한
  option-level 증거가 아니다. Caller는 `is_enabled`, `can_proceed`, `playable`, valid target
  index 같은 field도 따라야 한다.

Regression coverage: [`test_upstream_api_contract.py`](../../../AgenticSTS/tests/test_upstream_api_contract.py)
및 [`test_upstream_state_parser.py`](../../../AgenticSTS/tests/test_upstream_state_parser.py).

<a id="c-004--llm-decision-boundary"></a>
## C-004 — LLM decision boundary

- Gameplay output은 마지막으로 유효한 `<decision>...</decision>` JSON block에서 parse한다.
  Raw/bare JSON recovery는 caller가 fallback을 명시적으로 enable할 때만 사용한다.
- Parse한 decision은 dispatch 전에 state별 local schema의 required field와 action enum을
  충족해야 한다. Selection index 같은 conditional requirement는 local에서 검증한다.
- Provider compatibility를 위해 nested `params` object를 flatten할 수 있으며 top-level key가
  우선한다. Mod action으로 변환하는 동안 알려진 integer index string을 coerce할 수 있다.
- Invalid output은 validation/repair condition이며, 그대로 game에 전달하지 않는다.

정확한 schema 및 parser 동작: [`tool_schemas.py`](../../../AgenticSTS/src/brain/tool_schemas.py),
[`decision_parser.py`](../../../AgenticSTS/src/brain/decision_parser.py),
[`models.py`](../../../AgenticSTS/src/brain/models.py).

<a id="c-005--persistent-state-및-provenance"></a>
## C-005 — Persistent state 및 provenance

- `AgenticSTS/src/storage/paths.py`가 dynamic-data path authority다. 현재 우선순위는
  `STS2_DATA_REPO`, legacy `STS2_DATA_DIR`, 필수 sibling `AgenticSTS-Data/` 순이다.
  `STS2_RUNS_HISTORY_REPO`는 isolated experiment를 위해 run history만 별도로 redirect할 수
  있다.
- Dynamic memory, skill, evolution artifact, run은 해석된 data root 아래에 속한다. Static
  knowledge, patch manifest, version compatibility, seed definition은 `AgenticSTS/`에 남는다.
- `runs/history.jsonl`은 append-only primary run evidence이며 aggregate cache는 derived data다.
  Run record에는 가능한 경우 identity, model attribution, game context, outcome, metric, feature
  flag, experiment tag, data/machine provenance가 포함된다. Append 시 game, mod, data-schema
  version을 추가한다.
- 저장된 evidence는 이후 schema나 claim에 맞추기 위해 재작성하지 않는다. Migration과
  correction에는 provenance를 보존하는 audit trail 또는 replacement artifact가 필요하다.

정확한 path 및 run schema: [`paths.py`](../../../AgenticSTS/src/storage/paths.py) 및
[`history.py`](../../../AgenticSTS/src/runs/history.py).
