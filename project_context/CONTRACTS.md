# 계약 (Contracts)

이 문서는 아래에 나열한 semantic contract의 authoritative source다. Link된 code와 상세
reference document는 현재의 정확한 field catalog 및 initialization evidence다. Implementation
file을 변경해도 이 contract가 조용히 재정의되지는 않는다. 충돌은
[`INDEX.md`](INDEX.md)의 hierarchy를 따른다.

<a id="c-064-jev27b-continuation"></a>

## C-064 — EX-083 4GPU 계승 실행 경계

[D-132](decisions/D-132-jev27b-four-gpu-continuation.md)과
[EX-083](experiments/EX-083-jev27b-four-gpu-continuation.md)에 적용한다.
C-063의 입력/후보·무절단·HTTP 형식·중복 추론 방지 의미를 유지하고 EX-083에 한해
장치 배치·자원/서빙 identity·부모 계승·새 진입 gate를 명시 변경한다.
`jev27b continue --parent --directory`는 봉인된 EX-082의 정상23만 계승하고 원24–32번만
새로 실행한다. 원24번 추가1회 이외 재경기0, 기존 execute의 덮어쓰기/재개 거부는 유지한다.
네 GPU0–3의 잠금/UUID/유휴 확인 후 CUDA 초기화·40GiB allocator/44GiB 전체 사용량 감시와
소유 자원 회수를 같은 장치 집합에 적용한다. 부모 원자료·실패·봉인·Blocked는 불변이며
새 manifest에 전체32슬롯·계승/신규구간·각 시도 및 원자료 hash를 기록한다.
독립 재로딩·591응답 전수 대조·같은 서버 연속 메모리/일반턴 gate의 조건과 중단/집계 원문은
EX-083이다. 부모와 신규구간을 감사하고 실패를 포함한 총시도·고유경기 분모를 구분한다.

<a id="c-063-jev27b-local"></a>

## C-063 — JEV-27B 로컬 Choice 재현 경계

[D-130](decisions/D-130-jev27b-ex058-reproduction.md)과
[EX-082](experiments/EX-082-jev27b-ex058-reproduction.md)에만 적용한다. 기존 jev-choice-v4의
입력/명령/최신 rqid 경계와 choice-action-v3 실패 격리를 유지한다. 공식 bare formatter에
상태·지시문·후보 객체 전체와 순서를 보존하고 확률을 원 후보 ID에 대응한다. 입력 한도32768·
무절단, 단일 후보 무호출이다. loopback HTTP의 revision/서빙 identity를 확인하고 동일 본문·
request ID의 재전송에서 서버가 추론 결과를 재사용한다. 다른 본문에 같은 ID는 거부한다.
시간/자원·진입/중단 gate 원문은 EX-082다. GPU0·1만 소유하고 EX-080/GPU2·3·공유 환경·
기존 입력 source를 보존한다. 과거 HTTPS·재시도·시간 상한 계약을 소급 변경하지 않는다.

<a id="c-061-qwen-matrix"></a>

## C-061 — Qwen 고정 대진 행렬 탐색 경계

D-127/D-128/EX-080의 `integration/qwen_mcts`는 C-060의 공개 상태 정보 경계를 그대로 따른다.

- **정보 경계:** 렌더러(`fixed-matchup-qwen-text-v1`)는 `exportPublic(...).physical`만 읽는다.
  - 실제 경기의 매 결정과 탐색의 모든 자식은 공개 allowlist 검증을 통과해야 한다.
  - PRNG·미공개 선택·감사 로그는 모델 입력에 들어가지 않는다.
- **자식 seed:** 행렬 탐색의 자식 seed는 결정·행동 id로 정해진다. 실제 경기·행동·opponent RNG와 namespace(`qmcts-v1`)를 분리한다.
- **정책 타깃·추론:**
  - 정책 타깃은 정규화 균형 π다. 탐색 잡음은 타깃에 들어가지 않는다.
  - 서빙은 고정 shape(32행·길이 버킷)로 하며, 행의 출력은 배치 구성과 무관해야 한다(G3 비트 동일).
  - fla autotune은 설정 순서로 결정적으로 고르고, 교차 GPU 출력이 비트 동일해야 한다(G2).
- **재검증 범위:** 실행의 live 재검증 범위는 코드·의존성·모델·팀이다.
  - RD·CONTRACTS·CHARTER와 EX/D 문서는 준비 시점 사본만 보존한다. 다른 작업의 문서 편집이 실행을 막지 않게 하기 위해서다.
  - 다른 실험이 해시하는 경로(`integration/pokechamp/**` 등)는 vendoring으로 격리한다.
- **판정 위임:** 조건·예산·판정은 EX-080이 소유한다. 개발 리허설과 CPU 검증은 실험 gate나 효능 근거가 아니다.

<a id="c-060-fixed-matchup"></a>

## C-060 — 고정 대진 공개 상태 탐색 경계

D-126/EX079는 EX078 round1 완전 checkpoint·정상32·원시계를 새identity에 계승한다.
종료 판정은 전수 정상 개발 평가에만 적용하고 anchor/patience/target streak는 영속 기록으로
재구성한다. 최고 점수 선택과 유의미 개선 anchor를 분리하고 test 잠금 후 재선택하지 않는다.
기존 pilot gate 통과를 위조하지 않으며 별도 계승 기술 gate·종료 gate를 검증한다.

D-125 복구는 EX-078의 정상31/실패1 분모와 P0·optimizer/RNG·최초시각을 보존하고
새identity/무제한 시계에 연결한다. 지정 실패 슬롯 외 재수집은 허용하지 않는다.

D-124의 EX-078 후속 설정은 시간 예산에 null(무제한)을 사용한다. 원 시각/경과시간 기록과
취소/자원/무결성 검사는 유지하며 유한시간 원실행의 source/판정은 보존한다.

D-123/EX-078의1라운드 진단도 아래 정보·재현 경계를 유지하며 범위/예산/완료는 EX-078을 따른다.

D-122/EX-077은 아래 정보/재현 경계를 유지한다. 단일24시간 조건부 실행과 pilot 재시도 범위는 EX-077을 따른다.

D-119/EX-076의 fixed_matchup은 기존 C-055/056 입력/학습 의미와 별도다. 양측 세트와 현재
상태 공개는 명시적인 진단 조건이다. 실제 PRNG·미공개 선택·미실행 행동 queue·감사 로그를
탐색/모델 입력에 전달하지 않는다. 현재 상태의 허용 필드를 열거하고 미분류 필드는 거부한다.
공동 선택 전 barrier에서 양측을 독립 선택하며 숨은 pending 행동이 남으면 중단한다.
정책은 합법 행동 분포, 가치는 관점별 상태가치이며 기존 행동별 WDL과 구분한다.
Showdown 요청 기반 후보·명령/슬롯/Tera 정합성, 분기 독립성·RNG 격리·고정 평가를 검사한다.
checkpoint/최초 시계/원장·실패 분모와 과거 자료를 보존한다. 조건·예산·판정은 EX-076이 소유한다.
D-119의 구현과 D-120의 명시적인 실험 실행 승인을 구분한다. CPU 개발 검증은 실험 gate를 대신하지 않는다.

<a id="c-059-abyssal-rl-next"></a>

## C-059 — 82라운드 계승·단일 추가 주기

[D-118](decisions/D-118-abyssal-rl-next.md)/[EX-075](experiments/EX-075-abyssal-rl-next.md)의
`abyssal_rl_next`는 C-055/056/057 및 C-058의 복원·분산·슬롯·시계·알람/뷰어 경계를
유지하며 부모/실행 identity만 EX-074/EX-075로 변경한다. 지정 부모는 EX-074 local25/
전체82라운드와 정확히 일치하는 optimizer504상태·4rank RNG checkpoint여야 한다.
이전 누적2674=2164+510과 이번 추가 update를 분리하고 local1/전체83부터 기록한다.
과거 PPO buffer·최종 선택77라운드 모델을 출발 상태로 대체하지 않는다.

새 test128은 원 제외 대상과 EX-073/074 전체 split에서 격리한다. 팀/슬롯/seed를 첫 update
전에 동결하고 test는 정책/head 잠금 이후에만 생성한다. `run --resume`는 동결 EX-075 내부
identity·source·manifest·checkpoint·원 시계가 일치할 때만 허용한다. 부모 계승은 이전
실험의 재개가 아니다. source 동결 전에 문서를 완료하고 동결 중 변경하지 않는다.

C-058의 모델 비호출·영속 중복 방지 단계 알람, 정상 단계 응답 비대기, 전 경기 export와
최대12경기 오프라인 브라우저 표본 확인을 이번에도 적용한다. 전수/점진 브라우저 검사0,
원자료/독립 감사·봉인 유지다. 첫 GPU부터12시간/48GPU시간 **1회**만 실행하고 내부
재개·복구로 시계를 늘리거나 다음 주기를 자동 시작하지 않는다. 상세 protocol·완료는 EX-075다.

<a id="c-058-abyssal-rl-continue"></a>

## C-058 — 마지막 학습 상태 계승·별도 실험과 단계 알람

[D-117](decisions/D-117-abyssal-rl-continue.md)/[EX-074](experiments/EX-074-abyssal-rl-continue.md)의
`abyssal_rl_continue`는 C-055/056 입력·행동 확률과 C-057 분산·실패 격리 경계를 유지한다.
prepare는 CPU에서 지정 부모의 identity·해시·57라운드 가중치·optimizer504상태·4rank RNG를
검증하고 새 manifest에 연결한다. EX-073 final 선택/보정 checkpoint를 부모로 대체하지 않는다.
초기 계승은 가중치/optimizer/RNG와 train 순환만 이어받고 과거 PPO buffer를 재사용하지 않는다.
local/global round와 추가/기존 누적 update를 별도 기록한다. 새 test·모든 슬롯/seed는 update
이전에 동결한다. test는 완전 dev 기반 정책/head 잠금 이후에만 생성한다.

prepare/verify/run/status/finalize를 제공하며 `run --resume`는 이번 experiment identity·
source·manifest·checkpoint·원 시계가 일치하는 EX-074 내부 재개만 허용한다.
이번 최초 GPU 검사 시계와 절대 마감은 복구/재개에 불변이다. 단계 receipt와 전달 원장은
영속 저장하고 모델 비호출 감지기는 승인된 사건만 대화에 전달한다. 종료/마감은 중복 병합하며
알람 응답을 기다리는 단계 gate를 만들지 않는다. 전체 rank 장애 정지·소유 자원 정리를 유지한다.

C-047의 전 경기 export·원자료 연결·봉인은 유지하되 EX-074의 브라우저 확인만 명시적
표본 예외를 적용한다. 전수/점진 전수 브라우저 검사는 실행하지 않고 단계별 슬롯 ID 첫/마지막,
최대12경기만 확인한다. 원자료 연결 감사와 독립 통계는 생략하지 않는다.
예산·수치 기준·분모·완료 조건은 EX-074를 따르며 EX-073의 동결 자료와 당시 판정은 보존한다.

<a id="c-057-abyssal-rl"></a>

## C-057 — Abyssal 전용 동기 4GPU 정책 학습

D-116/EX-073의 별도 abyssal_rl 경로는 C-055 입력/명령·C-056 선택 행동 확률 의미를 유지한다.
GPU0–3 전체 공용 lock/UUID 확보, 동결 복제본당 직렬 추론·2동시 배틀, 전 요청 종료 후
snapshot 동일성 확인을 강제한다. 학습은 전역 RL16/BC4의 실제 표본 평균 손실에 대한
FP32 경사 NCCL SUM과 같은 step, 전역 KL의 같은 종료 결정을 적용한다.
rank·snapshot·global_update·slot 소유권을 기록하고 원자 슬롯 예약으로 재경기를 금지한다.
checkpoint는 완료 step의 모든 rank RNG·optimizer·cursor·동결 buffer·원 시계가 한 묶음이다.
한 rank 장애는 전 worker 종료, 부분 rank 계속 실행0. test는 완료 dev 기반 정책/head 잠금 후만
허용하며 불완전·실패를 W/D/L로 변환하지 않는다. 상세 허용오차·예산·완료 기준은 EX-073이다.
기존 EX-072/066 설정·실행·자료를 덮어쓰지 않는다.

<a id="c-056-selfplay"></a>

## C-056 — 자기대국 정책·선택 행동 승무패 확률

D-114/EX-072의 별도 selfplay 경로는 C-055의 입력/정보/명령 경계를 재사용한다.
모든 모델 선택은 temperature1 categorical sampling이며 greedy 규칙은 적용하지 않는다.
행동 ID·정책 확률·행동별 W/D/L 확률은 별도 필드다. WDL은 실제 선택 행동의 정상 결과에만
학습하며 미선택 행동 결과/반사실적 정확성을 주장하지 않는다. 같은 forward 표현·dropout0·
BF16 base/FP32 LoRA·두 head를 사용한다. 수집 당시 전체 log probability·WDL·baseline·
후보 순서·모델/RNG·입력 해시와 실제 전송을 보존한다. 자동 선택은 학습에서 제외한다.
상대 snapshot은 동결하며 PPO 재계산에서 입력/순서를 바꾸지 않는다. 실패를 결과로 바꾸거나
대체/재질의/재경기하지 않는다. 최초 절대 기한과 완료 step을 원자적으로 보존하고 재개로
시계를 새로 만들지 않는다. 상세 gate·분할·시간·학습·복구·분모는 EX-072가 소유한다.

<a id="c-055-imitation"></a>

## C-055 — 리플레이 모방 학습 입력·Choice 정책

D-113/EX-071의 `pokemon-imitation-input-v1`은 기존 q 계약과 별도다. 모델 전용 immutable
입력은 현재 상태·복원한 아군 원래 세트·현재 공개 상대 정보·필드·직전4턴/현재 턴 공개 이력과
후보만 포함한다. 관점/결정 위치는 감사 metadata에 보존하며 모델 입력에는 선수 이름·승패·
미래 공개 상대 정보·같은 턴 미공개 선택·라벨·seed·추정 출처를 넣지 않는다.
미래 자기 공개는 원래 자기 세트 복원에만 사용하고 도구 교환·호출 기술 등 동적 정보와 구별한다.
현재 상태는 결정 직전 prefix만으로 만들며 offline/live가 같은 직렬화 함수를 사용한다.

출력은 Kev Choice 질문1개다. criteria는 행동 ID와 설명, 타깃은 관측된 실제 선택 ID다.
기술 ID는 기술명과 Tera 여부, 선봉/교체 ID는 자기 팀의 고정 슬롯으로 구분한다.
슬롯은 실전 request의 명령 슬롯과 명시적으로 매핑하고 후보·라벨/셔플 정합성을 검증한다.
확률은 후보 전체의 정규화된 **행동 선택 확률**이며 승률/q가 아니다. 실제 선택에만 CE를
적용하고 미선택을 승률0으로 만들지 않는다. unknown 선택은 mask, 자동 행동은 새 선택이 아니다.

Base BF16, LoRA/head/loss FP32와 BF16 forward의 동일 unmerged 경로로 학습·평가·서빙한다.
상태 최대8,192토큰을 절단하지 않으며 준비 초과 표본은 사유와 함께 제외한다. 후보/질문을
붙인 전체 readout도 절단하지 않는다. live 초과/불량 응답은
무전송·해당 경기 실패, 공유 생성기 결함은 의존 단계 중단이다. 후보1개는 추론 없이 제출한다.
최대 확률을 선택하고 동률은 고정 후보 순서로 처리한다. 전송 직전 rqid·합법 후보를 다시 확인하며
stale/실행 불가능/기한 초과는 무전송, 재질의·대체0이다. 원 입력·확률·선택·명령·지연·분모와
provenance를 보존한다. 데이터/학습·재개·평가 잠금·시간·회복 한도는 EX-071을 따른다.

이 contract는 상속된 implementation이 남아 있는 동안 그것을 보호하고 설명한다. 원저자의
연구 목표, roadmap 또는 experiment backlog를 채택하지 않는다. 새로 승인된 연구 방향은
[`Decision`](DECISIONS.md)과 명시적인 contract 수정으로 변경을 제안할 수 있다.

<a id="current-rules"></a>

## 적용 범위와 읽기 경로

계약은 해당 schema·runtime 경로·정책 identity에 적용한다. 실험명·버전이 붙은 계약은
그 범위의 기술적 의미를 보존하며 새 작업에 당시 실행 계획 전체를 자동 추가하지 않는다.
새 실험의 공통 복구 경계는 [C-018](#c-018-recovery), 새 Cloud 기본값의 적용·호환 범위는
[C-029](#c-029--새-cloud-기본-동시성8), 새 기본 IO 설명 검토의 적용 경계는
[C-032](#c-032-io-explanation-review)에서 확인한다. EX-040 식별자·중단 경계는 [C-035](#c-035-ex040)를 따른다. 새 구조 설명·효과 사전 전송은 [C-037](#c-037-effect-reference), 선봉 독립 구성요소는 [C-040](#c-040-lead-components)을 따른다. 구체 값을 이 안내에 복제하지 않는다.

중복 참조는 EP-039의 2026-09-14 대조 시점에 지정한 원문 범위만 이 계약에 명시적으로 편입한다. 이 문서의 domain authority나
원문 소유권을 이전하지 않고 참조 문서의 이후 변경을 자동 채택하지 않는다. 과거 실행 승인·
중단·실패 판정은 유지하며 여기의 과거 명령·승인 기록을 현재 실행 또는 재개 지시로 읽지 않는다.

## C-001 — 상속된 AgenticSTS context와 layer write authority

- Reference agent는 이름이 있는 L1-L5 layer로 decision context를 구성하며, decision 사이에
  제한 없는 raw transcript를 계속 append하지 않는다.
- L1 system prompt와 L2 state-type prompt는 사람이 작성하며 postrun automation이 쓸 수
  없다. L3는 명시적인 game-update workflow를 통해 변경한다.
- L4 memory, L5 skill, dynamic evolution tool은 postrun에서 쓸 수 있는 surface다. Write는
  configuration, schema/validation logic, 해당 store lifecycle의 gate를 계속 적용받는다.
- 의도적으로 accumulating-context를 사용하거나 그 밖의 방식으로 contract를 깨는 비교는
  격리하고 experiment로 표시해야 하며 reference-agent path로 제시하면 안 된다.

현재 상세 내용: [`MEMORY_SYSTEM.md`](../AgenticSTS/docs/reference/MEMORY_SYSTEM.md) 및
[`SELF_EVOLUTION.md`](../AgenticSTS/docs/reference/SELF_EVOLUTION.md).

## C-002 — Game-mod transport

현재 server surface는
[`Router.cs`](../AgenticSTS-Mod/STS2AIAgent/Server/Router.cs)가 정의한다.

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
[`actions.py`](../AgenticSTS/src/mcp_client/actions.py)에 있다. Default address는 loopback port
8128이며 설정할 수 있다. Python client는 envelope을 unwrap하고 보고된 failure에 대해 typed
client/action error를 raise한다.

## C-003 — State 및 index 표현

- Mod는 `run_id`, `screen`, `session`, `in_combat`, `available_actions`와 활성 game surface의
  optional typed payload를 가진 versioned root state를 내보낸다. 정확한 producer는
  `GameStateService.BuildStatePayload`이며 Python mirror는
  [`upstream_models.py`](../AgenticSTS/src/mcp_client/upstream_models.py)다.
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

Regression coverage: [`test_upstream_api_contract.py`](../AgenticSTS/tests/test_upstream_api_contract.py)
및 [`test_upstream_state_parser.py`](../AgenticSTS/tests/test_upstream_state_parser.py).

## C-004 — LLM decision boundary

- Gameplay output은 마지막으로 유효한 `<decision>...</decision>` JSON block에서 parse한다.
  Raw/bare JSON recovery는 caller가 fallback을 명시적으로 enable할 때만 사용한다.
- Parse한 decision은 dispatch 전에 state별 local schema의 required field와 action enum을
  충족해야 한다. Selection index 같은 conditional requirement는 local에서 검증한다.
- Provider compatibility를 위해 nested `params` object를 flatten할 수 있으며 top-level key가
  우선한다. Mod action으로 변환하는 동안 알려진 integer index string을 coerce할 수 있다.
- Invalid output은 validation/repair condition이며, 그대로 game에 전달하지 않는다.

정확한 schema 및 parser 동작: [`tool_schemas.py`](../AgenticSTS/src/brain/tool_schemas.py),
[`decision_parser.py`](../AgenticSTS/src/brain/decision_parser.py),
[`models.py`](../AgenticSTS/src/brain/models.py).

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

정확한 path 및 run schema: [`paths.py`](../AgenticSTS/src/storage/paths.py) 및
[`history.py`](../AgenticSTS/src/runs/history.py).

## C-006 — Experiment identity, isolation 및 denominator

- 아래 condition name과 corpus rule은 상속된 AgenticSTS artifact를 재현하거나 비교할 때만
  적용한다. 새 연구 프로그램의 default requirement, baseline 또는 candidate work가 아니다.
- Experiment run은 비어 있지 않은 stable `experiment_tag`를 사용한다. 비교는 condition도
  식별한다. Resume logic은 기록된 tag/condition evidence를 key로 사용한다.
- Writable condition은 L4/L5/evolution state를 격리해야 한다. 현재 `self-evolve` condition은
  aggregation을 위한 shared run-history routing을 유지하면서 experiment별 data root를 쓴다.
- 현재 code-level condition name은 `baseline-strict`, `prompt-only`, `mode-a`, `self-evolve`,
  `full`이다. 공개된 frozen label은 `self-evolve`를 `mode-b-frozen`에, `full`을
  `full-frozen`에 대응시킨다. 분석은 이 이름들을 추측으로 join하면 안 된다.
- 모든 experiment record는 denominator와 stopping rule을 명시해야 한다. 공개 paper corpus에서
  completed game은 `victory` 또는 `defeat`이며, `max_steps`와 infrastructure outcome은 298-game
  completed corpus에 포함되지 않는다. Live ablation orchestrator는 현재 `max_steps`를 채워진
  non-victory slot으로 취급하지만 paper reproduction filter는 제외한다. Decision으로 조정할
  때까지 이 차이를 명시적으로 유지해야 한다.
- Evidence가 존재한 뒤에만 result를 기록한다. Interface, version, routing 또는 cadence가 다른
  operational comparison은 해당 caveat를 유지해야 하며 controlled single-variable ablation으로
  다시 label하면 안 된다.
- 새 연구 experiment는 `project_context/experiments/` 아래의 새 record에서 시작하며 legacy
  hypothesis, condition, metric 또는 stopping rule을 암묵적으로 상속하지 않는다.

현재 experiment 상세 내용: [`ABLATION.md`](../AgenticSTS/docs/reference/ABLATION.md),
[`run_ablation.py`](../AgenticSTS/scripts/run_ablation.py),
[`scripts/reproduce/`](../AgenticSTS/scripts/reproduce/).

## C-007 — Distribution 및 provenance 경계

최상위 component는 별도 license를 유지한다. Python agent는 Apache-2.0, mod fork는 AGPL-3.0,
data artifact는 CC-BY-4.0이다. Agent license는 mod나 data를 포괄하지 않는다. Repository의
ignore/export rule에 나열된 generated upstream 또는 proprietary game-knowledge file은 local에서
재생성하며, Apache-2.0으로 조용히 commit하거나 재배포하지 않는다.
[`release_exclusions.md`](../AgenticSTS/docs/release/release_exclusions.md)와
[`data/knowledge/README.md`](../AgenticSTS/data/knowledge/README.md)를 참조한다.

외부 submodule도 자체 license와 provenance를 유지한다. `pokemon-showdown/LICENSE`는 MIT다.
`pokechamp/pyproject.toml`과 classifier는 MIT라고 표시하지만 `pokechamp/LICENSE` 원문은 일본에서의
사용·배포·판매를 금지하는 추가 문구를 포함한다. 따라서 PokéChamp를 표준 MIT component로
축약하거나 현재 repository의 다른 license가 포괄한다고 해석하지 않는다. 재배포 또는 release
전에 원문 조건과 적용 가능성을 별도로 검토한다.

## C-008 — PokéChamp qualification environment

- External source identity는 `pokechamp/`의
  `0f84c460319ebe733f8c3028e58a2a5452c60d85`와 `pokemon-showdown/`의
  `e64915c0eab066db1d3e732b1280386468dd7415` Git submodule이다. URL과 checkout SHA가 함께
  일치하고 canonical submodule이 clean해야 qualification을 실행할 수 있다.
- PokéChamp dependency는 repository-local `uv 0.12.9`, Python 3.11.11과 upstream
  `uv.lock`의 `uv sync --locked`로 구성한다. Showdown dependency는 pinned `package-lock.json`의
  `npm ci`로 구성한다. 임의 upgrade나 audit fix는 이 contract를 조용히 바꿀 수 없다.
- Showdown은 parent가 소유한 marker-protected temporary Git worktree에서
  `127.0.0.1:8000`, 한 worker, `--no-security --ai-tournament`로만 실행한다. Python/NumPy seed는
  `100`, Showdown worker root PRNG seed는 `100,100,100,100`이다. Canonical external source를
  runtime state 저장소로 사용하지 않는다.
- Parent launcher는 server module 초기화 전에 process-local `Config.forcetimer=false`를 적용한다.
  별도 timed-run 지시가 없으면 Showdown turn/battle inactivity clock은 꺼져 있어야 한다. Timed
  run은 `/timer on` 또는 equivalent player setting을 명시하고 actual timer policy를 evidence에
  기록해야 한다. Provider request와 orchestration watchdog timeout은 별도 infrastructure safety
  경계이며 이 규칙이 제거하지 않는다.
- Server stop은 기록된 PID가 parent launcher, temporary worktree와 예상 process group에 속하는지
  확인한 뒤에만 signal을 보낸다. 알 수 없는 listener나 process는 중지하지 않는다.
- 새 배틀의 공급자·전송·credential·봉인 계약은 [C-034](#c-034-provider)를 따른다.
  Ollama 기존 자료 및 당시 설정은 보존한다. 작은 upstream max_tokens로 출력 예산을 줄이지 않는다.
  JSON 요청 형식 지정은 schema enforcement나 행동 유효성 보장이 아니며 기존 검증을 유지한다.
- JSON response는 parse 가능해야 한다. Battle response는 정확히 하나의 지원 action을 포함하고
  현재 available move/switch에 일치해야 한다. 위반은 첫 response에서 `output_contract` terminal
  failure로 처리하고 battle을 취소하며 upstream retry/local action fallback으로 qualification을
  통과시키지 않는다.
- Qualification artifact는 `.artifacts/pokechamp/<command>/<UTC timestamp>/manifest.json`에 source,
  toolchain, sealed configuration, credential 존재 여부, non-secret provider metadata와 outcome을
  기록한다. Prompt와 response content는 기록하지 않는다.
- Local/API/battle smoke 성공은 interface와 runtime 실행 가능성만 증명한다. 모든 artifact는
  `technical_qualification`, `efficacy_evidence=false`이며 baseline/treatment 성능 evidence로
  사용할 수 없다.

구현과 사용법: [`integration/pokechamp/README.md`](../integration/pokechamp/README.md),
[`D-007`](decisions/D-007-adopt-pokechamp-dotenv-credential.md),
[`D-009`](decisions/D-009-adapt-always-on-reasoning-output.md),
[`D-011`](decisions/D-011-default-untimed-showdown-battles.md).

## C-009 — PokéChamp research battle observability

- Full-fidelity logging은 비어 있지 않은 명시적 `experiment_id`와 별도
  `POKECHAMP_DATA_ROOT`를 가진 research command에서만 활성화한다. Recorder가 없는 C-008
  qualification path는 prompt, response와 reasoning content를 계속 저장하지 않는다.
- Bundle identity와 위치는
  `<POKECHAMP_DATA_ROOT>/experiments/<experiment_id>/battles/<battle_id>/`다. ID는 path component로
  안전한 값이어야 하며 기존 directory와 충돌하면 실패한다. 완료 bundle을 자동 삭제하거나 source
  evidence를 덮어쓰지 않는다. Correction은 새 `battle_id`와 optional `replacement_for`를 사용한다.
- Schema version 1 source evidence는 다음 세 파일이다.
  - `manifest.json`: experiment/battle identity, source SHA, format, team, model configuration,
    UTC start/end, outcome, completeness, seal 상태.
  - `events.jsonl`: battle-global `event_seq` 순서의 `battle_start`, `protocol_in`,
    `decision_start`, `llm_call`, `decision_result`, `wire_action`, `battle_end`, `logging_error`.
  - `checksums.sha256`: seal된 `manifest.json`과 `events.jsonl`의 SHA-256.
- 모든 event는 `schema_version`, `experiment_id`, `battle_id`, `event_type`, `event_seq`, UTC
  timestamp와 battle-start 기준 monotonic offset을 가진다. 판단은 battle-global `decision_seq`,
  provider 호출은 battle-global `llm_call_seq`로 연결하며 `showdown_turn`은 표시용 값이다.
- Research `llm_call`은 provider에 실제 전달한 wire-level system/user prompt, provider reasoning,
  raw content, canonical parsed output, request/model/token/latency/stop metadata와 validation 결과를
  기록한다. Parent integration은 inbound battle protocol과 실제 outbound `/team`, `/choose`,
  `/forfeit` action을 player/transport 경계에서 기록한다.
- Research command는 player/challenge를 만들기 전에 data root, 새 bundle, manifest와 event stream을
  열어야 한다. 이 단계가 실패하면 battle을 시작하지 않는다. 시작 후 record failure는 gameplay
  control flow에서 격리하고 warning, 가능한 `logging_error`, final
  `evidence_complete=false`로 드러낸다.
- Seal 전 source file은 진행 중 evidence이며 partial일 수 있다. Seal은 source file을 닫고 final
  manifest를 기록한 뒤 checksum을 exclusive-create한다. `showdown.log`, `replay.html`,
  `report.html`, experiment별 `catalog.sqlite`와 `index.html`은 source에서 재생성 가능한 derived
  output이며 checksum 대상이 아니다.
- Renderer는 malformed/missing/tampered source를 성공 evidence로 만들지 않고 partial/integrity
  warning과 함께 가능한 내용을 표시한다. HTML은 모든 untrusted text를 escape하고 CSP를 적용한다.
  Network animation asset을 읽지 못해도 report의 정적 protocol timeline은 local에서 완전하게
  열려야 한다.
- Bundle은 `classification=research_observability`, `efficacy_evidence=false`다. 자동 L4/L5
  retrieval/write, hypothesis 평가, denominator 결정 또는 efficacy claim의 authority가 아니다.
- Credential 값은 qualification 및 research evidence 양쪽 모두에서 금지한다. Full-fidelity
  source는 prompt/reasoning, username과 protocol을 포함할 수 있으므로 local-only sensitive research
  data로 취급한다.

구현과 rationale: [`integration/pokechamp/README.md`](../integration/pokechamp/README.md),
[`D-010`](decisions/D-010-adopt-pokechamp-battle-observability.md).

## Failure behavior 요약

| 경계 | 관찰된 동작 |
|---|---|
| Mod가 `ok: false`를 보고하거나 HTTP/connection failure 발생 | Python client가 error를 raise한다. Action error는 server의 `retryable` flag를 보존한다. |
| Wait 중 SSE를 사용할 수 없거나 실패 | Polling으로 fallback한다. Timeout은 계속 raise된다. |
| Strict state validation 실패 | `parse_state`가 raise한다. 명시적인 safe path만 `None`을 반환한다. |
| Default sibling data root 부재 | Path resolution이 `FileNotFoundError`를 raise하며 replacement store를 조용히 만들지 않는다. |
| Runtime run-history load에서 malformed line 발견 | Warning 후 해당 line을 건너뛴다. 계속 실행하기 위한 fail-open 동작이다. |
| Paper reproduction load에서 malformed JSONL 발견 | File과 line number를 포함해 raise한다. 분석을 위한 fail-closed 동작이다. |
| Monitor event emit 실패 | Monitoring error는 gameplay와 격리되며 agent를 crash하지 않는다. |
| PokéChamp source/tool/server preflight 실패 | Battle 또는 cloud call을 시작하지 않고 nonzero와 qualification artifact를 남긴다. |
| Cloud credential/configuration 부재 또는 불일치 | Client/network call 전에 fail-closed한다. |
| Cloud auth/model/rate-limit/timeout/transport 실패 | 분류한 failure를 기록하고 다른 endpoint, model 또는 local backend로 fallback하지 않는다. |
| Research data root/bundle initial open 실패 또는 ID 충돌 | Player/challenge를 만들기 전에 fail-closed하며 기존 bundle을 수정하지 않는다. |
| Battle 진행 중 research recorder write 실패 | Gameplay를 변경하지 않고 warning을 내며 가능한 경우 incomplete manifest와 `logging_error`를 남긴다. |
| Research checksum 불일치 또는 partial source | Renderer/catalog가 integrity/partial 상태를 표시하며 complete evidence로 분류하지 않는다. |

이 차이는 의도에 대한 주장이 아니라 관찰된 사실이다. 새 code에서 fail-open 또는 fail-closed를
일반적으로 선호하라는 지시가 아니다. 새 boundary는 자체 policy를 명시해야 한다.

## C-010 — Benchmark pilot control record

D-012/D-015 benchmark는 C-008의 qualification을 변경하지 않는 별도 경로다. 경기별 server seed,
actor별 local RNG, 방법/팀/순서와 source snapshot은 실행 전 checksum으로 고정한다.
데이터는 POKECHAMP_DATA_ROOT/benchmarks/<experiment_id>/에 두며 actor별 C-009 source
bundle 두 개를 match identity로 연결한다. Actor bundle은 계속 research_observability와
효능 false다. Control record가 pilot eligibility와 denominator를 정의하고 기존 source를
수정하거나 qualification/demo를 사후 연구 outcome으로 승격하지 않는다.

Benchmark backend는 call_role을 명시하며 self_action, opponent_action, tool_choice,
state_value를 구별한다. 상대 예측은 관찰/추정 상태만 사용하며 숨겨진 server truth를
행동 입력으로 읽지 않는다. Provider/output 오류는 first failure에서 중단하고 fallback
action 전송을 막는다. 정상 damage-calculator 선택과 예외 fallback은 구별해 기록한다.
경기별 process에 Cloud key가 필요하면 그 actor 안에서만 .env를 읽으며 부모가 child
환경에 key를 전달하지 않는다. Unknown process/server는 종료하지 않는다.

모든 attempt는 새 identity와 source bundle을 쓴다. 중복 완료 slot은 재실행하지 않는다.
원자료 integrity/completeness 실패는 유효 승패로 집계하지 않는다. Protocol과 result가
충돌하거나 source/configuration drift가 발견되면 분석·실행을 중단한다.

## C-011 — Benchmark 병렬 실행과 요청 admission

[D-016](decisions/D-016-model-concurrency.md)에 따라 C-008의 8000 qualification은 유지하고
execution-config가 seal된 benchmark에 8100–8109 독립 loopback 서버 예외를 적용한다.
배틀/계정/모델 상한과 evidence는 run에서 변경할 수 없다. Unix socket broker는 요청 직전
계정·모델 permit을 동시에 부여하며 취소/장애는 신규 Cloud 요청을 차단한다.
Worker 유실은 timeout까지 보류하고 429는 계정 공통 Retry-After(없으면 30초) 대기다.
전역 실행 lock, source seal, 동일 slot transient 1회 retry와 모든 분모는 C-010을 따른다.
Batch 시간은 실제 시작–종료 경과 시간이며 중첩 attempt/actor 시간 합은 자원 지표다.
로컬 permit 대기·HTTP 경과·decision 지연을 구별하고 provider 내부 대기는 추정하지 않는다.

## C-012 — Benchmark 식별 및 요청별 후보

[D-017](decisions/D-017-battle-identity-action-candidates.md)에 따라 parent actor의 식별은 진영별
정확한 ident와 details로 미리보기 객체를 재사용한다. 모호성·치명적 parser 예외는 environment
실패로 해당 경기만 취소한다. Prompt/validation/conversion은 동일 요청 후보를 사용한다.
공개 미리보기·관찰·추정 출처와 후보·검증 실패 이유를 기록한다. 자기 available/force/변신과
상대 자체 상태를 구별하며 숨겨진 상대 truth는 금지한다. 정확한 JSON 후보에서 유일 정규화만
허용한다. 첫 오류/후보 없음/변환 실패는 terminal이며 repair/fallback을 금지한다.
새 outcome에서 output_contract, environment, provider_failure를 구별한다.

D-017 새 execution record의 optional `retry_transient=0`은 동일 slot 재시도도 금지한다.
필드 부재는 C-011 기존1회 규칙이다. 값은 정수0/1만 허용한다. 상대 요청의 구조화된 관찰
state는 actor에 이미 공개된 상태이며 원본 상대 팀 파일로 채우지 않는다.

## C-013 — 원본 행동 생성 별도 benchmark 조건

[D-018](decisions/D-018-upstream-fallback.md)에 따라 `action_policy="upstream"`에 한해
C-010/C-012의 출력 terminal·후보 prompt 규칙 대신 원본 프롬프트/추출/행동 변환/재시도/fallback을
적용한다. Provider·환경·무결성 종료는 유지한다. 필드 부재는 strict다. 정상 fallback 완료는
유효하며 전체/유효 각각 실제 전송 판단과 경기 분모를 보고한다. D-017 gate는 EX-016에
적용하지 않는다. 고정 fixture·로컬2판 후32슬롯10/10을 실행하며 Cloud4시간/신규3시간45분
중지와 retry_transient=0을 봉인한다. 이전 결과와 정상 minimax/효능/최대 처리량 주장은 분리한다.

## C-014 — 개선 IO 조건의 입력·출력·실행 경계

[D-019](decisions/D-019-improved-io.md)의 B/C는 C-008 JSON-only 및 C-012 출력의 별도
명시적 조건이다. 고정 정책+영문 근거1–2문장+마지막 줄 단일 행동 JSON을 사용한다.
추가 JSON·중복 key·후보 밖 행동은 거부한다. A는 C-013 upstream을 유지한다.
최신 자기 request와 원래 자기 세트, 상대 공개 사실 및 별도 고정 prior 추정만 입력한다.
@smogon/calc 0.11.0 actor별 프로세스와 계산 identity/범위/미지원 검사를 LLM 전에 적용한다.
C의 요약은 같은 battle/actor의 결정 이후 반영된 protocol까지 참조하고 최신 관측을 덮어쓰지 않는다.
B/C 첫 입력·계산·출력·요약 오류는 해당 경기 중단이며 repair/fallback은 없다.
모든 역할·조건은 배틀10/계정10/모델10의 단일 broker를 공유한다. 실행 설정 부재나
순차 경로는 새 조건에서 거부하며 기존 설정 부재의 의미는 보존한다.
조건 ID 및 프롬프트/prior/계산기 lockfile/평가 source는 봉인한다. node_modules/빌드는 제외한다.

[D-020](decisions/D-020-project-owned-ruination-patch.md)에 따라 B/C 계산기 identity는
`@smogon/calc 0.11.0` + `ruination-v1` + 패치 JSON SHA-256 + 적용 파일별 SHA-256이다.
설치는 `npm ci --ignore-scripts` 다음 명시적 `npm run patch:calc`를 요구한다. Worker는
모듈 로드 전 읽기 전용 검증을 수행한다. 누락·버전·해시 불일치는 원인이 있는 CalculationError로
종료하며 어떤 LLM 역할도 호출하지 않는다. 응답 engine_patch를 Python 수신부와 입력 검증기에서
기대값과 대조하고 trace/오프라인 결과에 보존한다. 패치·적용/검증 코드를 source seal에 포함한다.

D-022 재개에서는 실제 발생 계산/입력 오류의 프로젝트 소유 후속 패치를 허용한다.
0.11.0과 engine_patch 응답 구조를 유지하고 새 ID/해시·설치/Node/Python 검증을 함께 갱신한다.
실행 중 패치는 금지하며 실패 source·입력·응답 및 receipt는 불변이다. 단계 receipt는 전체
분모·검증 결과·현재 source 및 선행 receipt/output seal과 연결하고 검증 실패 시 다음 단계를
거부한다. 최초 Cloud 시계는 독립 봉인하여 재시작에도 초기화하지 않는다.

재개 범위 보충: [D-026](decisions/D-026-continue-io-experiment.md)의 EX-023은 C-014/D-022
운영 경계를 유지하며 EX-022 후속 상태 교정을 사용한다. 과거 EX-020의 halt/clock은 불변이고,
새 사용자 승인에 연결된 별도 EX-023 시계와 source/단계 identity를 사용한다.

D-027/EX-024는 `evidence.io_summary_prompt_version`으로 요약/통합의 같은 버전·해시를
Cloud 검증과 실제 배틀에 고정한다. 필드 부재는 원본 v1.0.0이다. 검토 대기는 봉인 응답으로
재개하며 Cloud 검증에서 미검토 요약을 후속 요약/통합/행동에 사용하지 않는다. 버전별 halt와
전체 halt를 구별하고, 최대3개 유료 source/프롬프트 조합이 최초 제출 시계를 공유한다.

## C-015 — 독립 요약 harness 진단

[D-023](decisions/D-023-summary-harness-diagnostics.md)의 EX-021은 C-014/D-022 운영 경로와
분리한다. 모델 요약 사실·형식 오류에 한해 측정 결과로 보존하고144개 예정 표본을 계속 수집한다.
Provider·환경·무결성·입력 변환 오류는 전체 중단하며 재시도·보충·재질문·실행 중 수정은 없다.
prepare는 원자료·봉인 재구성 코드·48입력·144일정·독립 평가 기준 해시를 고정한다.
run은 호출별 독립 backend/context와 계정/모델10/10 broker, 제출 intent와 worker 응답 선봉인,
최초 제출 기준45분/60분 영속 시계를 사용한다. report --review는 가린 응답과 근거/검토
해시를 연결하며 미완료·미확정·대응 누락을 명시한다. 미래/상대 비공개 정보와 정답 문구는
입력 금지다. EX-020 halt/receipt/clock과 EP-011 Blocked를 변경하지 않는다.


C-015의 입력/평가 근거 무결성 실패가 수집 후 발견되어도 전체 비교 자격을 철회한다.
봉인된 halt와 실패 근거를 확인한 report는 효과 추정 없이 무효·미완료 보고서만 생성하고
--review로 정상 비교를 복구할 수 없다. run은 halt가 있는 디렉터리의 제출을 거부한다.
기존 receipt와 원자료는 당시 상태로 보존하며 후속 로컬 교정은 별도 provenance로 기록한다.

## C-016 — 상태 의미와 요약 thinking 진단

[D-024](decisions/D-024-state-summary-thinking.md)의 EX-022는 정비된 운영 경로로 생성한
장면당 하나의 입력·독립 원본 정답과 low/high72일정을 봉인한다. profile이 조건·분모·시계를
정의하며 EX-021의144 가정을 재사용하지 않는다. summary/summary_rollup만 검증된
summary_thinking_effort를 사용하고 기본/행동은 low다. 실제 think와 request 기록은 같은
요청별 결정값을 쓴다. 잘못된 설정은 네트워크 전에 거부한다.
시간 의미는 행 순서의 발생 턴/마지막 갱신 턴/경과 counter/설치 턴/겹 수를 구별한다.
Future Sight는 원본 시작 행이 있을 때만 observed_start_turn을 기록한다. 예약은 대상
위치에 유지되며 교체된 사용자 효과 counter와 분리한다. 근거 부재는 미상이다.
운영/진단 의미 주석은 parent 공통 해석을 사용하지만 평가 정답은 해당 변환을 사용하지 않는다.
C-015의 응답 선봉인·영속 시계·halt·미확정 보존을 적용한다. 모델 오류만 수집 계속이며
provider/환경/무결성/입력/평가 기준 오류는 전체 중단한다. EX-020/021의 과거 자료는 불변이다.

## C-017 — 고정 이전 메모리 low/max 요약 진단

[D-028](decisions/D-028-summary-max-diagnostic.md)의 EX-025는 summary-max-v1 profile로
22입력/132일정·v1.1.2·원문 검토된 고정 이전 요약·입력별 평가 기준을 봉인한다.
summary_thinking_effort는 low/high/max를 검증하고 summary/summary_rollup에만 적용한다.
운영 기본·행동은 low다. 진단의 low/max는 같은 SDK 호환 전송 어댑터를 사용하며
실제 직렬화 think·역할·prompt hash와 trace를 대조한다. SDK/canonical submodule은 변경하지 않는다.
C-015/016의 독립 context·선봉인·무결성·중복제출 거부·전체 무효화 정책을 유지하고,
profile의 최초 제출부터13500초 신규제출/14400초 총시간과132유료 상한을 적용한다.
모델 오류 응답은 다른 입력으로 전파하지 않고 수집 계속한다. 과거 중단 상태는 불변이다.

<a id="c-018-recovery"></a>

## C-018 — 새 실험의 테스트·평가 결함 복구 경계

[D-029](decisions/D-029-experiment-defect-recovery.md) 채택(2026-09-09) 후 새로 승인·등록하는
실험은 [RESEARCH_DESIGN §11.1](RESEARCH_DESIGN.md#defect-recovery)을 기본으로 적용한다.
별도 전체 중단 규칙은 해당 새 실험에 사유와 범위를 명시한다. 기존 실험의 C-014~C-017 등
개별 계약·중단·무효·halt/clock은 계속 유효하며 소급 수정하지 않는다.

- 결함 발견 시 영향받는 작업과 의존 단계 진입을 보류하고 원인·공유 의존성·전파 범위를
  입증한다. 불명확한 범위는 잠재 영향 전체를 중지하고, 입증할 수 없으면 해당 비교 전체를
  중단·무효 처리한다. 새 실험의 모델 판단 오류는 [C-046](#c-046-provider-judgment)을 따른다.
  Provider 재시도는 확대하지 않는다.
- 테스트만 잘못됐고 실제 실험이 온전하면 근거를 남겨 결과를 유지할 수 있다. 평가 구현
  오류는 사전 기준대로 모든 영향 조건·응답을 동일 재평가한다. 정답·rubric 교정은 원문 근거와
  결과 확인 후 변경 사실을 공개한 별도 수정 분석이다. 실제 입력·처치·수집 오류는 영향 실행과
  의존 결과를 무효 처리하고 필요한 비교 단위를 재수집한다.
- 수정 전후 source·기준, 재현·독립 검증, 영향받는 입력·조건·결과, 재평가/재실행 단위를
  plan/experiment에 기록한다. 독립 검증은 수정 구현의 기대값 복제가 아닌 원자료·별도 계산·
  독립 사례를 사용한다. 재현 검사와 관련 회귀 통과 전 의존 작업을 재개하지 않는다.
- 대응 조건 쌍·block 및 연쇄 메모리 후속 결과를 포함한 복구 단위를 등록한다. 좋은 표본
  선택 보존·실패 분모 삭제는 금지하며 무효·미확정·미실행·복구 시도를 계속 보고한다.
- 기존 원자료·봉인·보고서·halt는 보존한다. 수정 분석/새 실행은 별도 버전·identity로 원본에
  연결한다. 새 identity는 새 예산이 아니다. 최초 시계·누적 사용량 및 전후 source/기준을
  연결하고, 평가 기준 완화로 기존 실험을 통과시킨 것으로 보고하지 않는다.
- 새 실험은 실행 전에 재수집 허용 여부·단위·한도와 승인·예산·시간·호출 상한을 등록한다.
  같은 승인·상한 안의 허용 복구는 재승인을 요구하지 않는다. 상한 소진·미승인 복구는
  추가 실행 없이 보존·미완료 보고하고 INDEX의 절차를 따른다. 시계·상한을 초기화하지 않는다.
- 이 계약은 연구 운영 절차다. 현재 API·CLI·파일 schema·실행기와 source seal 검사는 불변이며,
  halt 후 제출/정상 비교 복구 차단을 유지한다. 선택적 재수집·수정 분석 등 지원되지 않는
  경로는 [매뉴얼](../integration/pokechamp/README.md#recovery-runtime-limits)에 명시한다.
  지원 부재를 halt 삭제·기존 실행 덮어쓰기·새 디렉터리의 시계 초기화로 우회하지 않는다.
  필요한 도구 구현은 별도 bounded plan과 해당 승인 범위에서 검증한 후에만 사용한다.


## C-019 — 요약 없는 A/B profile 및 복구 실행 경계

[D-030](decisions/D-030-io-battle-only.md)의 `io-battle-only-v1`은 C-014의 관측·prior·계산·
fixed 행동 출력 경계를 재사용하되 A/B만 허용한다. B는 요약 prompt 선택/품질 gate/cadence에
의존하지 않으며 summary=null, lesson_memory=[], 요약/통합 역할 호출과 archive0을 검증한다.
기존 A/B/C profile과 과거 receipt 검증은 보존한다. A는 C-013 upstream fallback이다.

준비/단계 receipt는 profile·조건·운영 입력/독립 평가/실제 prompt/계산/source identity를
연결한다. 전체 공개 prefix와 최근10결정 전송 window를 구별한다. 필수 판단 근거의 실제
입력 도달성을 원문과 별도로 대조한다. Cloud intent와 worker 선봉인 응답을 연결하고
모든 실제 HTTP 직전 요청을 최초 clock/누적4000상한에 원자적으로 예약한다. 미확정도
차감하지 않는다. Source는 수집 중 불변이다. 배틀10/계정10/모델10 및 provider retry0이다.

새 profile 복구는 별도 봉인 기록과 identity에서만 실행한다. 원인·영향·원본/수정 source·
기준·독립 검증·관련 회귀·무효/재평가/재수집 단위를 연결한다. 영향 대응은 양쪽을 포함하며
공유 결함의 영향 집합을 누락하지 않는다. 복구1차·180/16/64 및 최초4시간/4000요청을
공유한다. 기존 halt/receipt/clock을 삭제/덮어쓰기하지 않고 모델 오답을 복구 사유로 쓰지 않는다.
이 새 경로의 구현·검증 범위는 EP-018/EX-026에 기록하며 기존 실행기의 복구 한계는 유지한다.


C-019 평가 복구 보충: English 문장은 ASCII 문장 부호로 한정되지 않는다. D-030의 새 profile만
typographic 대시/따옴표를 언어 검사에 허용하며 정확한 JSON·후보·문장 수 계약은 유지한다.
평가 교정 e1은 원래 입력/처치/기준 동등성을 확인하고 온전한 응답을 재호출하지 않는다.
미확정 요청이 있으면 미실행 재개 경로를 거부한다. 별도 새 판정과 미제출 ID만 최초 시계·누적
상한에 연결하며 c0 halt/응답은 보존한다. 유료 재수집 차수와 평가 교정 재개는 구별한다.

C-019 필드 설명서 보충([D-031](decisions/D-031-battle-field-guide.md)): 새 요약 없는 B 준비는
행동 v1.1.0을 기본으로 선택하며 버전 부재의 과거 설정은 v1.0.0이다. A 및 요약 실험 선택은
유지한다. 단일 fields.json에서 경로/자료형/단위/시점/불확실성을 렌더링하고 기존 policy에
결합한다. prepare·Cloud worker·actor는 공통 조립 함수를 사용하며 매 시스템 메시지에 한 번
포함한다. 사용자 JSON·합법 후보·출력 계약은 유지한다. v1.1.0은 원문 request JSON까지
중첩 경로와 동적 키를 검사하고 미설명 필드를 제거하지 않고 경로를 보고하여 거부한다.
선택 버전·원본/설명서/완성 prompt hash는 manifest·execution·요청에 연결하며 불일치를
거부한다. 과거 receipt를 새 설명서 기준으로 소급 검증하지 않는다. EX-026 재개나 Cloud
gate 통과를 뜻하지 않으며 이번 승인 범위는 구현·로컬 검증이다.

## C-020 — 명시적 battle-guide-live-v1 실험 정책

[D-032](decisions/D-032-battle-guide-live.md)의 사용자 승인으로 C-019 새 정책 선택을 추가한다.
정책 없는 과거 자료는 D-030 상한·엄격한 의미 gate를 그대로 적용한다.

A는 upstream IO·fallback, B는 교정 관측·고정 prior·계산기·필드 설명서 v1.1.0이다.
B 요약·통합·메모리 주입0. 모델 glm-5.3-flash/low/temperature0/seed100/출력131072/
provider 기본 context, 요청 timeout300초·경기 watchdog1200초·provider retry0을 유지한다.
`battle-guide-live-v1` 정책을 prepare에서 선택하고 manifest·study·execution·receipt·보고서에
봉인한다. 정책 부재는 D-030이다. 새 정책의 전체 비용·시간·행동 요청 상한은 없으며
요청/시간 상한은 명시적 null이다. 알려진 정책과 identity 일치 없이 null을 인정하지 않는다.
최초 Cloud 시각·요청·실패·미확정·token·경과 시간은 계속 누적한다.

로컬 회귀·운영15장면 의미/입력 도달성·사후피해3·필드완전성/전달·fake32(32/32,
실제 동시10, 격리오류0, 설명서 요청당1회, 요약0; native library thread1) 후
Cloud90(15장면×요청동시성1/10×3반복)을 수집한다. 출력/합법행동90/90, provider오류/
미확정0, HTTP overlap10, 병렬p95≤순차p95×2와 전체 원문/실제입력/계산 대조 검토를 요구한다.
설명 사실·진영·시점·계산 오류는 측정값이며 기술 gate와 분리한다. 오류가 남으면 의미
검증 통과로 표시하지 않는다. 출력·합법행동·입력/증거무결성·검토 완전성은 필수다.

smoke8은 b04 Abyssal/OneStep×양쪽×A/B, 실제 동시8·유효8/8·구성/IO오류0·요약0·격리
검증을 요구한다. 본 비교32는 Abyssal/OneStep×b01–b04×양쪽16대진에 A/B 대응,
EX-016 팀/게임 seed 고정·순서 seed20260908·배틀최대10/계정·모델요청최대10이다.
smoke 기반32판 시간 및50% 여유 추정은 보고용이며 남은 전체 시간으로 진입을 막지 않는다.
smoke는 본 비교에 합치지 않는다.

Cloud 기술 gate 실패는 후속 배틀을 차단한다. 실제 배틀 출력/provider/환경 오류·watchdog은
신규 배틀 제출 중지와 진행 자료 보존·정리를 요구한다. 합법 완료 설명 오류는 승패 제외
사유가 아니다. 모델 오답 재추첨·실험 중 prompt 변경은 금지한다.
D-029/C-018 영향입증·독립재현·수정·회귀 후 복구한다. 입력/처치/수집 재수집 최대1차,
영향 A/B 대응 양쪽·공유영향 전체를 포함하며 누적 gate180/smoke16/compare64를 유지한다.
이는 전체 행동 요청 상한과 별개다. 평가 구현 오류는 온전 응답을 대칭 재평가하고 rubric
교정은 공개된 별도 수정 분석이다. 원자료/halt/최초시계/누적사용량을 초기화하지 않는다.
기존 EX-026 및 모든 실험의 응답·판정·halt·시계·Blocked는 보존한다.

상대별 (승+0.5×무)/유효완료, 두 상대 동일가중 평균, 완료대응 B−A·누락과 예정/시도/
완료/실패/무효/미실행/미확정/복구를 분리 보고한다. B gate·배틀 설명 전수검토의 오류 종류/
근거/분모, A fallback·호출/token/HTTP지연/배치시간/동시성·정리를 보고한다.
전체 B 구성의 개발 대진 탐색적 비교이며 설명서 단독 효과나 L1–L5 전체 효능으로 귀속하지 않는다.

## C-021 — battle-guide-direct32-v1 실행·출력 복구 경계

[D-033](decisions/D-033-battle-guide-direct32.md)의 명시적 사용자 변경을 새 EX-028에만 적용한다. C-014/C-019/C-020의 기존 엄격 gate·출력 중단 경로는 유지한다.

A는 EX-027의 upstream IO·fallback, B는 교정 관측·고정 prior·계산기·필드 설명서 v1.1.0이며 요약·통합·메모리 주입0이다.
모델 glm-5.3-flash, thinking low, temperature0, seed100, 출력131072, provider 기본 context,
요청 timeout300초·watchdog1200초·배틀/계정/모델 요청 최대10을 유지한다.
EX-027/EX-016 개발팀·게임 seed·Abyssal/OneStep×b01–b04×양쪽16대진의 A/B32판과 순서 seed20260908을 고정한다.

명시적 battle-guide-direct32-v1에서만 사전 회귀·15장면·fake32·Cloud90·smoke8을 skipped_by_user로 기록하고
설정·source·prompt·대진 봉인 후 compare32에 직접 진입한다. 생략한 gate 통과 receipt는 만들지 않는다.
전체 비용·시간·행동 요청 상한은 없고 provider retry·추가 재수집은0이다. 기존32 slot을 각1회 시도한다.
최초시계·원장·미확정과 사용량을 보존하며 수집 중 source/prompt를 수정하지 않는다.

B는 기존 출력 계약을 먼저 적용한다. 실패하면 원문에서 유일한 JSON 객체 행동을 중복 키 거부와
정확한 후보·강제교체·테라 조건으로 검사해 추출한다. JSON 없음/복수/중복 키/불법이면 봉인된 후보의
첫 행동을 사용한다. 원출력 판정·추출 행동·실제 실행 행동·선택 출처를 별도로 기록하며 재호출하지 않는다.
출력·설명 오류는 계속한다. Provider·timeout·watchdog·경기별 환경 실패는 해당 경기만 종료한다.
합법 후보 부재·공유 입력/계산 결함·설정 불일치·증거/격리 무결성 문제는 영향 범위를 중지한다.
범위 불명확은 잠재 영향 전체를 중지한다. C-018의 증거 보존·영향 분석을 적용하되 재수집0이며
기존 EX-027 및 다른 실험의 원자료·halt·시계·Blocked는 변경하지 않는다.

Viewer는 문제 턴 수·완료/실패·문제 목록·battle/actor/decision 링크를 제공한다.
출력 형식 오류/행동 추출/대체 행동/설명 오류/실행 실패를 텍스트와 색으로 구별하고 원문·오류·추출/전송 행동을 표시한다.
B 수집 설명은 원문·실제 입력·계산/공개 근거에 사후 전수 대조하고 사실·진영·시점·계산 오류를 별도 봉인 annotation으로 연결한다.
검토 전은 미검토다. 원자료를 수정하지 않는다.

자연 종료·실제 행동/입력/증거가 온전한 경기는 대체 행동·오류 표식을 포함해 성적에 포함한다.
정상 출력만 있었던 경기 수, 상대별 (승+0.5무)/유효완료, 두 상대 동일 가중 평균,
완료 대응 B−A·누락/실패/미확정·A/B fallback·호출/token/시간/동시성을 보고한다.
오류 처리 정책을 포함한 전체 구성의 개발 대진 탐색 비교이며 설명서 단독 효과나 L1–L5 효능으로 해석하지 않는다.

## C-022 — battle-guide-calcfix32-v1 계산기 교정 및 실행 경계

[D-034](decisions/D-034-calculator-entry-calcfix32.md)의 EX-029에서만 신규 정책을 선택한다.
C-021의 출력복구·실패격리·재수집0을 유지하되 결함재현·독립검증·회귀/source/설정 검증을 진입조건으로 봉인한다.
기존 정책의 hash/동작과 원자료는 보존한다. species fallback 억제는 인스턴스에만 적용하고 라이브러리/JSON/EV/IV/prior/prompt는 유지한다.
EX-028 대진과 정확히 대조하며 최초시계·원장·미확정1건을 참조하고 누적사용량을 보고한다. 상세조건은 D-034/EX-029를 따른다.

## C-023 — 계산기 입력 로컬 조사·수정 경계

[D-035](decisions/D-035-calculator-input-audit.md)/EX-030은 전체 입력 경로의 독립 로컬 진단이다.
발동·소비 이력은 battle별 Pokémon identity에 연결하고 최근10결정 이후에도 유지한다.
불명확한 이력을 미발동으로 가정하지 않는다. 매 등장/배틀당1회 특성을 구분한다.
새 상태·의미는 새 버전·입력 검증·필드 설명·provenance로 연결하며 과거 artifact의 의미는 보존한다.
원시/관측/worker/최종 입력을 별도 검증하고 지원하지 않는 상태는 정상 계산으로 제시하지 않는다.
기존 기능을 검사 통과 목적으로 제거하지 않는다. 명중 조건부 피해와 시점 경계를 유지한다.
기존636입력은 공개 cutoff까지 재생하고 영향은 별도 정정 분석한다. 유료 호출·재수집은0이다.


C-023의 구현 버전은 `calculator-input-v2`와 `battle-v1.2.0`이다. identity.input_version,
current_observation.calculator_semantics, calculation_bundle.semantics_version은 일치해야 한다.
Pokémon별 ability_history에는 battle/actor/ident, history_complete, entries, activations,
suppressed, qp_source, team_faints가 있다. battle_types와 effective_types를 분리한다.
worker는 source/context/output hash로 검증된 mechanics-v2 메모리 overlay를 사용한다.
request_sha256·bundle_sha256, scenario coverage, 최신 raw request 및 필수 이력/소유권 검증이
provider transport보다 앞선다. 필드 설명서는 원문 request JSON까지 경로를 확인한다.

scenario_state는 current_decision/after_selected_switch_entry/after_selected_terastallization을
구분하며 진입 hazard HP·status, 유효 weather/terrain, 활성화 후 items를 공개한다.
damage_variants는 hit수/위력 분기를 나타내고 확률값이 아니다. 선택 테라 incoming coverage는
어느 기술의 랭크 변화도 적용하기 전 상태다. Future Sight의 미래 target/field는 UNKNOWN이다.
역사적 v1.0/v1.1 자산·artifact는 원래 의미를 유지하며 v1.2에서 v2 상태를 생략하는 downgrade는
거부한다. 상세 지원 경계·독립 검증은 [EX-030 보고서](exec-plans/evidence/ep023/report.md)를 따른다.


D-037 기술명 정규화: worker는 검증한 pinned generation move의 canonical 이름으로 Move를 생성한다.
입력 ID/표시 이름/대소문자 차이가 날씨·아이템·지형·타입 변경 분기를 누락시키지 않아야 한다.
알 수 없는 기술은 기존처럼 실패한다. 이 bugfix는 schema/semantics 버전을 바꾸지 않으며 source hash로 구분한다.
과거 qualification/원자료는 보존하고 기존 source용 qualification을 새 source에서 재사용하지 않는다.
[검증 범위](exec-plans/evidence/ep025/report.md).

D-043 Protect 만료 교정: B는 전체 actor 공개 prefix의 발생 이후 turn/upkeep·교대·기절·해제로
입증된 만료 PROTECT만 effects에서 제거하고 parser_effects는 원형 보존한다. 공개 유효 활성의
parser 누락은 보완하고, 근거 부족·모순은 제거 근거로 삼지 않는다. 현재 PROTECT 계산 거부는 유지한다.
수명 근거는 내부 전달 및 별도 검증 기록에만 남기며 기존 JSON/프롬프트/calculator-input-v2는 유지한다.
수정본은 새 source hash와 protect-expiry-v1 검증으로 식별하고 EX-036 중단·과거 qualification은 보존한다.

D-062 입력 교정: 전체 actor 공개 prefix의 `-activate ... move: Court Change`로 입증된 실행
알림은 계산용 effects에서만 제외하고 parser_effects를 보존한다. `-swapsideconditions`는 pinned
Showdown의 교환 대상 진영 효과 기록을 설치 시점·원본 참조·중첩 그대로 이동한다. 명시적인
`-status ... [from] ability ... [of] holder`의 공개 특성은 그 보유자에 귀속하며 피해자에게 옮기지
않는다. 상대의 effective_types는 기절 시 pinned Showdown의 테라 해제를 반영한다. 기존 parser
표현과 관측 tera_type·CLI/schema/calculator-input-v2·계산 미지원 거부는 유지하고 source hash로
구분한다. 검증·과거 입력 영향은 [EP-051](exec-plans/completed/EP-051-court-change-input-audit.md)에서
별도 기록하며 과거 입력을 소급 교정하거나 기존 실험을 재개하지 않는다.

## C-024 — battle-guide-inputfix32-v1 교정 입력 실행 경계

[D-036](decisions/D-036-calculator-inputfix32.md)의 명시적 사용자 승인에 따라 EX-031에서 새 A16/B16을 실행한다.
C-021 출력복구·실패격리·재수집0을 유지하며 B만 calculator-input-v2/battle-v1.2.0/mechanics-v2다.
EX-028 봉인 대진·설정·순서를 유지하며 qualification과 semantics/runtime patch를 최종 source 및 실제 요청까지 연결한다.
기존 정책 정의/hash/과거 실험은 보존한다. 필수 로컬 검증 뒤 Cloud90/smoke8/별도fake32 없이 직접32판을 실행한다.
EX-028/029 사용량은 각 원본을 한 번씩 연결하고 미확정1건을 유지한다.
전수 검토·분모·보존·실패 정책·완료 판단의 사전 등록은 [EP-024](exec-plans/completed/EP-024-calculator-inputfix32.md)를 따른다.
성능 비교 완료는 유효32판/16대응에만 표시하며 과거 무효 결과 합산·계산기 단독/L1–L5 효과 귀속은 금지한다.


## C-025 — battle-guide-movefix32-v1 수정 완료본 실행 경계

D-038/EP-026/EX-032에만 적용한다. C-021의 출력복구·실패격리·재수집0과 C-024의 v2 전달 경계를 유지한다.
새 정책·qualification은 EP-025 봉인 기준 source/검증과 새 실행 연결 변경분 검사를 함께 연결한다.
593회귀·독립28조건/16roll·81재생은 반복하지 않으며 최종 전체 source 재검사로 주장하지 않는다.
과거 정책 hash/receipt는 불변, 새 source/config/manifest를 봉인한다. EX-028/029/031 자체 사용량을 각각 한 번 연결한다.
필수 연결 검사 후 fake32/Cloud90/smoke8 없이 새32판을 실행한다. 상세 조건·중단·완료 기준은 EP-026을 따른다.

## C-026 — 외부 환경 장애 후 동일 조건 새 반복

D-039/EP-027/EX-033의 명시적 새 실행 승인에 한해 C-025의 처치·검증 재사용·보고 경계를 적용한다.
새 battle-guide-external-repeat32-v1의 runtime identity는 EX-033/D-039이며 이전 정책/hash는 유지한다.
외부 요인 귀속은 사용자 보고이고 독립 OOM 확정과 구분한다. 기존 permit 코드를 수정한 것으로 표시하지 않는다.
기존 실행·halt를 보존하며 새 준비에 EX-032의 보고/원장/시계/halt·승인·동일조건 근거를 봉인한다.
EX-028/029/031/032 각각 자체 사용량+새 실행을 한 번씩만 누적하고 과거 미확정1건을 보존한다.
이번 전체32판 반복 외 추가 보충/재수집0이다. 재발 시 기존 공유 결함 중단 규칙과 실제분모 보고를 유지한다.


## D-041 원본 A64 진단 실행

[D-041](decisions/D-041-a-diagnostic64.md)의 명시적 사용자 승인으로 EX-034 준비에서 EX-035 실행으로 진행한다.
EX-034 평가 protocol v1은 유지하고 운영 watchdog만3600초로 변경한다.
새 a-diagnostic64-v1은 A-only, 첫10 검사 후54, 로컬/fake64 필수, Cloud90/smoke8 없음,
최초 요청부터20700초 수집/21600초 총시간·8000요청 원자 예약·동시성10·재수집0이다.
기존 정책/원자료는 보존하며 상세 사전등록은 [EP-029](exec-plans/completed/EP-029-a-diagnostic64.md)를 따른다.

## C-027 — ab-head-to-head32-v1 실행 경계

이 계약의 실행·분모·검토·보존 조건은 동일 원문을 유지한
[연구 설계 D-042](RESEARCH_DESIGN.md#d-042-원본-ab-직접-대결32) 절 전체를
이 계약의 규범 내용으로 참조 편입한다. C-027의 실행 경계 권한과 기존 적용 범위는 유지한다.

## C-028 — ab-head-to-head32-protectfix-v1 실행 경계

[D-044](decisions/D-044-ab-head-to-head32-protectfix.md)와 [EX-037](experiments/EX-037-ab-head-to-head32-protectfix.md)의 현재 명시적 지시를 채택한다.
이 계약의 중복된 실행·실패·보고·완료 조건은
[EP-032 §목표·범위·승인·불변조건](exec-plans/active/EP-032-ab-head-to-head32-protectfix.md#목표범위승인불변조건)의
“현재 사용자 제공 실행 계획을 명시적 승인 근거로 EX-037/EP-032/D-044를 등록한다.”부터
“중단 시에도 수집분 검토/보고/보존/정리와 실제분모·미완료 사유를 기록하며 중단처리 완료를 비교완료로 표시하지 않는다.”까지를
이 계약의 규범 내용으로 참조 편입한다. 해당 원문은 변경하지 않았으며 C-028의 권한을 이전하지 않는다.

## C-029 — 새 Cloud 기본 동시성8

[C-036](#c-036-zai4)의 새 Z.ai 기본4 예외 외에는
[D-045](decisions/D-045-cloud-concurrency-default8.md)에 따라 새 병렬 execution은 배틀·계정·모델 기본값8과
`evidence.concurrency_policy=cloud-default8-v1`을 봉인한다. 명시적인 execution의1–10 값이 기본값보다 우선한다.
이 정책은 C-014/C-019/C-020/C-027/C-028 등 기존 실험 정책의 동시성 고정값에만 새 실행에서 우선하며,
표식 없는 과거 execution은 기존 규칙으로 검증한다. 기존 정책 identity/hash 자체는 바꾸지 않는다.
실제 worker·port·permit 및 검증·보고·시간 추정은 봉인된 execution을 사용한다.
새 Cloud gate의 기본 비교는1/8이며 기존 gate의 선언된1/10과 명시적인 동시성 측정 조건은 보존한다.
표본 수·첫10 gate·실패/재시도·예산·시계·처치 규칙은 변경하지 않는다. 기존 run을 다시 봉인하거나 재개하지 않는다.

execution schema를 쓰지 않는 gate는 같은 `concurrency_policy`와 `parallel_concurrency`를 inputs/manifest/receipt에,
요약 진단은 config의 표식 및 `account_limit`/`model_limit`을 봉인한다.
순차/병렬 비교 gate의 병렬 조건은2–10이며 순차1과 중복된 조건을 만들지 않는다.

## C-030 — B 오프라인 전달 표현

D-046/EP-034의 B0–B3는 원본 battle-v1.2.0 및 calculator-input-v2를 먼저 검증한다.
후보 버전과 계산 의미 버전을 독립 필드로 봉인하고 누락·불일치는 거부한다.
원본 패치·state/request/bundle hash 검증은 유지한다. 원본 전체 + 후보 버전에서 생성한
system/user 문자열 및 원본 연결 정보와 실제 전달 값이 정확히 일치해야 한다.
B1의 명시적 제외 목록 외에는 모든 필드가 보존 또는 역변환 가능해야 한다.
B2 scenario 연결과 공유 참조는 유일하고 한 단계이며 시나리오 순서·타수/난수 분포를 유지한다.
B3는 window를 줄이지 않고 request 최초 상태/객체 변경분/삭제/배열 전체 교체를 사용한다.
null은 삭제가 아니며 미해석 protocol 행은 그대로 남긴다. 비어 있지 않은 메모리 및
Gen9 OU singles 외 범위는 거부한다. 이 인터페이스는 오프라인 전용이며 운영 기본값은 불변이다.


## C-031 — EX-038 B2 실제 전달 경계

D-047/EP-035의 명시적 사용자 지시에 따라 C-030의 오프라인 한정을 새 EX-038 B2 경로에서만 확장한다.
원본 전체 입력 검증 후 EP-034 B2를 생성하고 전송 직전 원본·후보·실제 system/user 문자열 일치를 검사한다.
출력 검증과 복구는 원본 전체 입력을 사용한다. calculator-input-v2와 전달 후보 B2를 독립 기록한다.
요청 전 원본 snapshot 및 actor/결정 연결을 trace에 보존하고 실제 전송 문자열·hash·버전을 기록한다.
뷰어와 검토는 실제 B2 전달 표현과 검증용 원본을 구분한다. B2 변환기/설명서 동결, 기존 기본값 불변이다.
실행 한도·실패·중단·코드검증/생략 조건은 EX-038 사전 protocol을 따른다.


<a id="c-032-io-explanation-review"></a>

## C-032 — 기본 IO 테스트의 설명 오류 기입 명시 선택

[D-050](decisions/D-050-io-explanation-review-opt-in.md)과
[연구 설계 §8.1](RESEARCH_DESIGN.md#io-explanation-review)에 따라 새 기본 IO 알고리즘 테스트는
설명 오류 사후 검토·annotation 신규 기입을 기본 제외한다. 사용자가 명시적으로 요청한 경우에만
해당 범위의 검토 자료를 작성·연결한다. 단순 IO 테스트·비교·viewer 생성 요청으로 확대하지 않는다.

- 새 plan에는 기본 제외 또는 명시 요청의 근거·범위를 기록한다. 설명 오류율·검토 완전성을
  별도 요청 없는 기본 테스트의 gate/완료 조건으로 추가하지 않는다.
- 원문/reasoning 기록·표시, 기술적 입력/출력/합법 행동/계산/실제 전달/실행 실패/무결성 검증은 유지한다.
- 검토하지 않은 설명은 미평가이며 정상이나 오류0으로 재분류하지 않는다. 기존 viewer의
  `unreviewed`는 검토 기록 부재를 나타내며 새 기본 테스트의 추가 작업 지시가 아니다.
- 기존 review/annotation의 읽기·표시는 유지한다. 기존 원자료·봉인·viewer·오류 집계·실험
  완료/미완료 판정과 Blocked는 변경하지 않는다.
- C-019/C-020/C-021 등 과거 명시적 설명/의미 gate와 정책 hash·전용 실행기는 보존한다.
  이 지침을 근거로 과거 receipt를 다시 봉인하거나 gate를 통과한 것으로 만들지 않는다.
  새 일반 IO 테스트 계획은 과거 실험의 설명 검토 요건을 자동 상속하지 않으며, 사용할 실행
  경로와 승인 범위가 맞는지 등록 시 확인한다.


<a id="c-033-llm-lead"></a>

## C-033 — B2 선봉 선택의 별도 경계

[D-052](decisions/D-052-llm-lead.md)의 새 `b2-llm-lead-v1`에서만 C-030의 오프라인 한정을 추가 확장한다.
C-031의 B2 원본 검증·전송 문자열/역변환/출력복구는 그대로 적용하며 기존 정책 정의/hash는 바꾸지 않는다.
이 정책의 준비는 수집 승인이 아니다. actor별 `team_preview_policy`는 생략 시 `seeded_random`, 새 값은 `llm_lead`다.
기존 설정/실험의 출력·RNG·무호출 및 identity를 보존한다. 새 정책에서만 명시적 선봉 조건을 봉인한다.

- Gen9 OU singles 6마리 유지. 자기 실제 제출 순서의 1-based 후보 ID를 최신 preview 자기 request와 대조한다.
  알려진 자기 기술·도구·특성·능력치·테라를 제공하고 누락을 기본 세트로 채우지 않는다.
  상대는 결정 시점까지의 공개 `poke` preview만 허용한다. 상대 원팀/actor 상태/비공개 세트/미래 protocol/결과는 입력에 쓰지 않는다.
- 별도 버전/hash prompt는 대면 상성, 초반 압박·설치기·피벗, 핵심 보존을 고려하고 공개 사실과 추정을 구분한다.
  출력은 정확히 `{"lead_slot": 정수}` 하나이며 중복/추가 키, bool·실수·문자열, 후보 밖 슬롯, 여분 텍스트를 거부한다.
- 기존 actor Python RNG의 동일한 shuffle을 한 번 수행하고 선택 슬롯만 앞으로 이동한다.
  나머지 상대 순서 및 RNG 소비를 유지하고 parent가 검증된 `/team` 명령을 생성한다.
- 경기/actor당 최초 요청은 최대1회다. 중복 preview는 저장된 요청 identity/결과를 재사용하고 재호출/중복 전송하지 않는다.
  실패·timeout·취소·예산 소진은 명시적 선발 실패이며 random fallback/재질의/대체 모델은 없다.
  실패 경기는 정상 선발/상대 승리/유효 승패로 집계하지 않는다.
- `call_role=team_preview`는 `self_action`과 구분한다. 현재 B2의 동일 backend/model/thinking/temperature/seed/출력 상한,
  공통 permit·timeout·취소·원자 예약·최초 유료 시계·전체 호출 상한을 사용한다.
  새 공급자의 모델 seed 적용 여부는 [C-034](#c-034-provider)를 따른다.
  동기 upstream preview 전송을 parent async 요청 경계에서 가로채고 backend 완료 후만 전송한다.
  취소 시 신규 전송을 막고 진행 요청의 응답 보존 및 permit 반환을 기다린다.
- actor/경기/결정/request ID, 실제 입력·prompt identity·모델 설정·원문/reasoning·검증·선택·최종 명령·wire 상태·지연/사용량/실패를
  원장/trace/manifest/viewer에서 연결한다. C-032 설명 오류 사후 annotation은 기본 제외다.

후속 실험은 같은 수정 source의 B2 seeded_random 대 B2 llm_lead, 동일 팀/게임 seed 대응과 조건/진영 교환을 등록한다.
표본·요청/금액·시간 예산·중단/복구·분모는 별도 승인 대상이다.
D-053은 EX-039 실제 수집을 명시 승인하되 최종 로컬 검증·봉인 후만 실행하도록 한다.
상세 한도·첫 대응쌍 gate·실패·분모는 EX-039 원문을 따른다. 기존 실험 재개는 금지한다.

<a id="c-034-provider"></a>

## C-034 — 새 배틀 공급자 설정과 호환

[D-054](decisions/D-054-zai-provider.md)에 따라 CLI·일반/B2 배틀은 POKECHAMP_PROVIDER의
ollama/zai를 선택한다. 미지정 기본은 ollama, 이 작업공간 .env의 명시 선택은 zai다.
POKECHAMP_MODEL은 glm-5.3-flash다. 관련 환경값은 프로세스 값(명시 빈 값 포함) 우선,
private regular .env 보조로 읽는다. 파일은 shell로 실행하지 않으며 0600을 유지한다.
ZAI_BASE_URL은 /chat/completions 앞까지의 HTTPS 기본 주소다. userinfo/query/fragment,
잘못된 주소·빈 주소·키·알 수 없는 공급자는 HTTP 전에 거부한다.
Ollama는 https://ollama.com/api/chat, Z.ai는 ZAI_BASE_URL/chat/completions로 요청한다.

Z.ai는 Bearer ZAI_API_KEY, stream=false, thinking.type=enabled, reasoning_effort=low,
max_tokens=131072, timeout은 [C-038](#c-038-transport-retry), JSON 시 response_format.type=json_object를 전송한다.
모델 seed는 전송하지 않고 seed_applied=false로 기록한다. 게임/대진/actor RNG seed는 유지한다.
Ollama는 기존 think/format/options 전송과 seed를 유지한다. context를 지정하지 않으며
실제 공급자·endpoint·전송 옵션·timeout·seed 적용 여부를 기록한다.
재시도는 [C-038](#c-038-transport-retry)을 따르며 공급자/모델 대체는 없다. 기존 upstream/B2 행동 출력복구와 provider 실패는 구분한다.
응답 content/reasoning/usage/finish_reason은 검증·viewer에 연결하고 누락 usage는 null로 남긴다.
양쪽 키는 오류·로그·artifact에서 마스킹하고 키가 불필요한 child에서는 제거한다.

새 배틀 준비 자료는 비밀 없는 provider_config를 봉인하고 실행 설정과 HTTP 전에 대조한다.
미기재 과거 자료는 Ollama 설정으로 해석한다. 기존 동결 정책 hash·source·halt·시계는 수정하지 않는다.
무호출 fake 및 과거 자료 읽기는 실제 공급자 성공/실험 재개 허가가 아니다.

<a id="c-035-ex040"></a>

## C-035 — EX-040 실행 식별자와 첫429 중단

D-055/EP-044/EX-040에 C-033/034의 B2·선봉·공급자 경계를 적용한다. 봉인 실험 식별자가 protocol과 독립 영속 binding을 선택하며 전역 변수 교체를 사용하지 않는다. 준비·승인·공급자·source·원장·최초 시계를 결합하고 같은 실험의 새 폴더 등록을 거부한다. EX-040에만 첫429 영속 halt와 신규 경기/요청 admission 차단을 적용한다. 진행 응답/미확정 보존, 자동 재개/재수집0이다. 실제 요청은 봉인 provider 설정과 대조하고 추출 결과와 합법 실행 결과·wire를 구분 검증한다. 기존 정책 hash·EX-039 binding/중단 상태는 불변이다.

<a id="c-036-zai4"></a>

## C-036 — Z.ai 기본4 및 EX-041 식별자

D-056/EP-045의 새 Z.ai 준비는 배틀·계정·모델 기본4와 zai-default4-v1 표식을 봉인한다.
명시1–10 설정은 실험별 제한 안에서 우선한다. Ollama 기본8 및 cloud-default8-v1/표식 없는 과거 검증을 유지한다.
기본값 선택은 준비 때 공급자를 결정한 후 수행하며 실행/검증/보고는 봉인값을 사용한다.
EX-041은4 고정이며 C-035의 독립 binding·원장·최초 시계·첫429 영속 중단·모델/요청 검증을 적용한다.
기존 EX-039/040 protocol/hash/binding/halt/최초 시계는 불변이고 자동 재개/유료 재수집0이다.

<a id="c-037-effect-reference"></a>

## C-037 — 새 배틀·선봉 효과 사전 전송

D-057의 새 버전은 C-030/031/033의 과거 동결 버전을 보존한 별도 선택이다.
effect_reference의 items/abilities/moves는 정규화 ID → name/desc이며 고정 Gen9 Dex 원문이다.
전송되는 자기 정보·공개 관측·기존 가설·계산 시나리오·이력에 등장한 항목만 요청별로 수록한다.
선봉은 C-033의 공개 cutoff를 유지하고 상대 종족으로 비공개 항목을 추정하지 않는다.
상태 sentinel은 제외하고 미해석 실제 ID/desc 누락은 경로·ID가 있는 input_contract 오류로 전송을 막는다.
원본·선택 버전으로 재생성한 system/user/identity와 실제 전송 문자열이 일치해야 한다.
원본 입력과 실제 문자열·사전/프롬프트/전달 버전은 준비·trace·viewer에 연결한다.
효과 설명은 일반 규칙이며 보유·발동·성공의 증거가 아니다. 계산에 반영된 효과를 재적용하지 않는다.
새 EX 미지정 준비는 개선 버전을 명시 봉인하고 과거 실행 승인·예산을 상속하지 않는다.

<a id="c-038-transport-retry"></a>

## C-038 — 새 전송 정책

D-060 이후 새 준비·직접 호출은 `provider-retry-v2`를 봉인한다. 기존 연결 오류와
연결/읽기/쓰기/pool timeout, HTTP5xx·429에 최대3회(총4시도), 고정1초/2초/4초 대기를 적용한다.
Retry-After는 기록만 하며 새 정책에 별도 cooldown/jitter를 추가하지 않는다.
첫429에서는 재시도하고 최종 실패429에서 전체 신규 수집을 영속 중단한다.
기타4xx·출력·계산·설정·무결성 오류는 제외한다. 과거 버전/실험에는 소급하지 않는다.

D-058의 `connect-retry-v1` 봉인은 그대로 읽고 실행한다. HTTP 읽기600초,
연결·쓰기·pool300초이며 최대2회 연결 재시도(총3시도), 대기1초/3초다.
httpx.ConnectError 및 Ollama SDK가 동일 예외에서 변환한 ConnectionError만 대상이다.
ReadTimeout/ConnectTimeout/429/인증/서버/출력 오류는 제외한다. 공급자·모델·입력·옵션은 불변이다.
각 시도 전 취소·halt·누적 호출 상한·기한을 확인하고 별도 원자 예약과 시도 번호를 기록한다.
동일 논리 요청의 승인된 연속 재시도만 허용하며 동일 결정의 다른 요청은 차단한다.
시도마다 permit을 획득·반환하고 대기 중 점유하지 않는다. 취소 가능한 대기와600초 읽기를
포괄하는 permit/정리 수명을 사용한다. 기한 직전 요청은 남은 시간으로 timeout을 제한한다.
오류 종류·비밀 제거 상세/원인·시간·재시도 결과를 보존하고 최종 논리 결과와 HTTP 시도 수를 구별한다.
정책/timeout/재시도/대기는 provider_config 및 호출 trace에 봉인한다. 새 provider_config의
전송 정책이 보존된 공통 실험 정책 identity 내부의 과거 timeout/retry 값보다 우선한다.
과거 정책 표식 부재·명시 과거 EX는300초/retry0이다. 기존 정책 hash·원자료·Blocked는 불변이다.
C-034/033의 새 호출 실패 처리에 봉인된 전송 재시도가 우선한다. 소진 후 최종429 전체 중단 또는 기존 개별 실패 처리를 따른다.
도구 결함 복구(C-018)는 이 정책을 추가 확대하지 않는다.

<a id="c-039-distributed-lead"></a>

## C-039 — EX-042 분산 실행 경계

D-059/EX-042는 공급자별 설정과 일정 provider_id를 봉인한다. 한 coordinator가 runtime 잠금·8100–8107·독립 배틀 큐/permit broker를 소유한다. 각 공급자 배틀/계정/모델 상한4·전체8이며 여유를 이전하지 않는다. worker에는 해당 설정을 명시 전달하고 병렬 coordinator의 전역 환경을 바꾸지 않는다.
공유 원장·최초 예약 시계·영속 halt를 EX-042 독립 binding에 준비·배정·source·승인과 연결한다. 실험별 call_limit=null은 무제한이고 과거8000/hash는 유지한다. 최초 예약+20100초에 양쪽 신규 경기/HTTP/재시도를 차단하고+21600초까지 소유 실행을 종료·정리한다. 별도1시간 watchdog은 없다.
C-037/038의 새 prompt/전송이 우선하며 재시도는 같은 입력/옵션·별도 예약/permit이다. 첫429·공유 결함·첫 네 경기 gate 실패는 전체 신규 수집을 영속 중단한다. 첫 네 경기와 재시도도 본 분모/원장에 포함한다. gate는 회복된 논리 요청을 과거 연결 실패 때문에 거부하지 않는다. 보충/재수집/자동 재개0, 과거 실행·봉인은 불변이다.

<a id="c-040-lead-components"></a>

## C-040 — 선봉 전략·규칙 독립 구성요소

D-061 새 준비는 `lead_strategy=matchup-v2`, `lead_rules=dex-v2`를 기본 봉인한다.
legacy-v1/effects-v1 조합은 v1.1 system/user를 byte 단위로 유지한다. 옵션 없는 과거 준비는 당시 identity로 해석한다.
전략 변경은 user를 바꾸지 않고 규칙 변경은 전략과 무관한 데이터·필드 설명만 추가한다.
구성요소 version/hash를 준비·요청·snapshot·전송 재검증·보고에 연결한다.
보강은 C-033의 완성된 입력만 받는다. 자기 기술 metadata는 해당 슬롯의 실제 목록만 따른다.
공개 종/폼의 기본 타입·비테라 배율·타입 상태면역과 OU 가능 특성/관련 기술을 별도 규칙에 둔다.
가능성은 실제 보유·확률·동시 합법 세트가 아니다. 모호한 폼은 공통 사실 및 조건별 가능성을 유지한다.
효과 desc는 요청별 한 번 제공한다. 고정 Dex commit/추출/hash/license와 범주 필터를 새 자산에 봉인한다.
B2·공급자·모델·전송·슬롯/RNG·엄격 JSON은 유지하며 기존 자산/실험을 수정하지 않는다.

## C-041 — EX-043 교정 선봉 분산 실행

D-064/EX-043에 C-039의 공급자4+4·독립 permit·원장/시계/binding·20100/21600초 경계를 새 identity로 적용한다. EX-042 봉인은 보존하며 EX-043은 matchup-v2/dex-v2 및 provider-retry-v2를 명시 봉인한다. 최종429·공유 입력 결함·첫4 gate 실패는 전체 신규 수집 중단이다. 종료 경기의 EP-051 기반 공개 cutoff 입력 감사 완료 전 해당 실행 자리를 재사용하지 않는다. 감사기/source/자산을 실행 봉인에 포함한다. schema·계산 의미 버전은 유지한다.

## C-042 — EX-044 직접 진입

D-065/EX-044에 C-041 실행·감사 경계를 새 identity로 적용한다. EX-044만 진입 receipt의 preflight_status=skipped_by_user 및 local_passed=false/wire_passed=false를 명시적으로 허용하고 기존 EX의 qualification 요구를 보존한다. 승인·설정·소스 봉인 및 본실험 gate/종료 입력 감사는 유지한다.

<a id="c-043-official-observation"></a>

## C-043 — 새 B/B2 공식 관측 경계

D-066/EP-056에서 observation_backend를 official-client-v1 / legacy-poke-env로 분리한다.
필드 부재는 과거 legacy 의미다. EP-056 필수 검증 후 새 B/B2 준비 기본값은 official-client-v1이며 빌드 identity와 v1.4.0/B2 b2-official-v1을 명시적으로 봉인한다. 명시적 legacy와 과거 EX 지정은 기존 버전을 유지한다.
공식 commit f2faebd6892b314d785a0038f77309afed36970c·의존성·공개 Dex·빌드 해시를 검증한다.
actor 수신 원문만 battle별 순서대로 결정 직전 행까지 반영한다. turn/decision/rqid/event/행과
공식 상태→정규화→계산→실제 문자열을 연결한다. 자기 정확값은 같은 request/자기 제출 세트,
상대 초기 표시값·미확인은 사실로 취급하지 않으며 prior/종 추론과 분리한다.
시작/소모/특성 활성·억제/지연 이력은 같은 원문에서 근거를 명시해 보완하고 legacy 상태를 병합하지 않는다.
효과 값·중첩·기간을 보존하며 계산 의미를 표현할 수 없는 상태는 명시적으로 거부한다.
request 슬롯·PP·제한·강제 교체·테라 조건과 공식 choice 검증에서 실제 제출까지 같은 슬롯을 쓴다.
Node 오류/timeout·필수 정보 누락·경계/해시 불일치 시 입력을 중단하고 자동 대체하지 않는다.
D-068/EP-058에서 정상 타이머 양보는 실패로 판정하지 않고 queue 종료 통지까지 기다린다.
자기 request 정규화와 마지막 행 snapshot은 앞선 공개 로그 종료 뒤에 수행한다. Node 명령은
직렬 처리하며 비동기 예외/기한 초과에는 부분 상태를 폐기한다. Python 동기 API·요청 전체30초
한도와 관측 schema/build identity는 유지하고 연결 source 해시를 별도 봉인한다.
upstream/Abyssal/C와 과거 설정/봉인/선봉 정책은 유지한다. 관측 소스와 계산 의미 버전은 독립이다.

<a id="c-044-official-lead"></a>

## C-044 — EX-045 공식 관측 분산 실행

D-067/EX-045에 C-039/041의 독립 공급자4+4·원장·20100/21600초 경계를 새 identity로 적용한다. 공식 관측 C-043의 backend/build 및 v1.4.0/b2-official-v1을 준비·등록·worker·요청에 봉인한다. 종료 감사 official-cutoff-v1은 기록된 actor 행 경계의 공식 상태와 정규화/계산/실제 문자열/응답/슬롯을 연결하고, 공개 원문/자기 request/미확인/누출을 별도 검사한다. 첫4 gate 및 종료 감사 전 자리 재사용 금지, 최종429·공유 결함 전체 중단, 각 경기1시도·재수집/재개0. 실패 증거는 요청 전 취소/전송 후 timeout/응답 수신을 구분한다. 과거 EX의 legacy 봉인과 당시 감사 버전은 보존한다.

D-069/EX-046에도 C-044 실행 경계를 적용한다. 비동기 교정본·새 EX identity/승인/원장/최초 시계를 봉인하고 EX-045의 중단·봉인은 보존한다. 사전 검증 참조 범위는 EX-046 원문을 따른다.

<a id="c-044-jev"></a>

## C-044 — 독립 JEV 클라이언트

D-070은 배틀 공급자 밖의 독립 JEV 호출을 추가한다. TYPESAFE_API_KEY,
TYPESAFE_BASE_URL(기본 https://api.typesafe.ai/v1), TYPESAFE_MODEL(기본 jev-latest)을
private regular root .env에서 읽으며 프로세스 값(명시 빈 값 포함)이 우선한다.
.env는 0600·비실행 파싱·Git 제외를 유지한다. 키는 공통 마스킹·불필요한 child 환경 제거에 포함한다.
주소는 /systemone 앞까지의 HTTPS base이며 userinfo/query/fragment·빈 값·잘못된 주소와
키가 포함된 주소를 전송 전에 거부한다. 키와 모델의 빈 값도 전송 전에 거부한다.
JevClient.from_env()와 evaluate(state=..., questions=...)를 제공한다. Bearer 인증으로
POST /systemone에 state/questions/model을 보내고 공식 Choice/Score/Noul 결과의
model/answers/usage 및 추가 응답 필드를 보존한다. 응답의 기본 구조·질문 ID/유형을 검증한다.
기본 timeout60초·redirect0·공급자/모델 fallback0이다. D-084의 새 기본 provider 재시도는 아래 절을 따른다.
실패는 비밀 없는 분류·HTTP 상태로 보고하며 raw 응답/인증 헤더를 오류에 노출하지 않는다.
context manager 또는 close()로 연결을 정리한다. 생성/설정 로딩은 요청을 보내지 않는다.
POKECHAMP_PROVIDER·배틀 모델·봉인·실험 정책은 유지한다. 실제 연결 검증은 별도 실행이다.

<a id="c-045-jev-battle"></a>

## C-045 — JEV Choice 배틀 프로필

D-071의 jev-choice-v1은 C-044 native state/questions를 사용한다. 공식 관측 actor·요청 cutoff와
합법 후보를 재사용하되 B/B2 정규화·계산·출력 계약과 독립한다. 모델에는 자기 요청·공개 관측·
최근 완료3턴 공개 이벤트만 투영한다. 상대 미공개 능력/아이템/HP는 unknown이다.
Choice 후보 ID는 요청 슬롯 기반이고 기술/테라기술/교체를 분리한다. 선봉도6후보 choice다.
D-072의 choice-values-v2는 확률의 유한0..1·전체 후보와 키 일치, confidence0..1 및 최댓값 선택을 검증한다. 확률 합계는 검사하지 않고 원값을 재정규화하지 않는다. D-075의 새 choice-action-v3는 [C-046](#c-046-provider-judgment)을 따른다. 새 manifest에 validation_version을 기록한다. 미기재 과거 manifest는 choice-sum-v1(합1 허용오차1e-4)로 감사하여 당시 판정을 보존한다.
단일 후보 자동 실행·대기 무호출, 요청ID/후보 재검증 후 명령 전송. 전송 실패/입력/응답 오류는
실패 폐쇄하며 대체 행동0이다. 입력/원응답/후보/선택/전송/모델/usage/지연을 보존한다.
초기 실행의 상한·복구·분모는 EX-047, D-073 수정본 재실행은 EX-048을 따른다. 기존 공급자 선택과 과거 정책 hash는 유지한다.

D-079의 새 `jev-choice-v2`는 자기 선봉을 request 슬롯으로 구성하며 공개 프리뷰와
종족·순서로 연결하지 않는다. 초기 상태는 teamPreview·turn0·init/teampreview 및
전투 이벤트 부재로 확인한 경계에만 적용한다. status는 자기 condition에서 판독하며
미확인 condition을 정상으로 간주하지 않는다. boosts/효과의 빈 객체는 변화/효과 없음,
status의 빈 문자열은 상태이상 없음, tera_type의 빈 문자열은 테라 미적용이다.
teraType은 설정 타입, terastallized/tera_type은 적용 타입이다. unknown은 근거 부재다.
일반 턴의 관측 연결은 유일한 자기 ident에 한정하고 모호성은 거부한다.
초기 PP는 검증된 고정 서버/Dex의 `showdown-gen9-max-pp-v1` 정책과 Gen9 OU 시작 전
경계가 함께 있을 때만 기본 PP×8/5(noPPBoosts 예외)로 채운다. 그 외 unknown의 이유를
명시하며 현재 active.moves의 PP가 우선한다. 상대 비공개 정보는 보강하지 않는다.
과거 감사는 manifest 버전의 v1 입력/prompt를 재현하며 과거 봉인·판정을 갱신하지 않는다.
D-080/EX-051은 v2의 실제2경기 검증 범위이며 EX-049/050의 choice-action-v3·상한·기술 중단·
경기 출력 실패 격리를 새 identity에 적용한다. 구체 조건과 승인 범위는 EX-051을 따른다.

D-082의 새 기본 `jev-choice-v3`는 v2 관측·PP 산출/검증·후보·명령·선택 검증을 유지한다.
사용자 제공 GENERATION 9 SINGLES MECHANICS 전문을 지시문에 그대로 추가한다.
`state.effect_reference`는 고정 `gen9-effects-v1`의 items/abilities/moves별 정규화 ID →
{name, desc} 영어 원문이며 자기 정보·확인된 상대·합법 후보·최근 공개 이력의 참조만 수록한다.
설명 재귀 확장·미확인 상대 세트 보강은 금지한다. 사전은 보유·발동 증거가 아님을 지시한다.
JEV 전용 수집기는 후보 move.id를 읽으며 불리언 terastallize를 효과로 해석하지 않는다.
실제 참조 설명 누락·사전 무결성 오류는 입력 생성 실패다. 새 모델 payload의 모든 위치에서
current_pp_source를 제거하되 current_pp_reason·PP 값은 유지한다. 원래 관측/request·manifest의
초기 PP 정책 및 사전 버전/hash/출처는 모델 밖 감사 기록으로 보존한다.
v1/v2 프롬프트·투영·과거 EX-051/052 원자료/봉인/뷰어는 보존하고 당시 버전으로 감사한다.

<a id="c-046-provider-judgment"></a>

## C-046 — 새 실험의 공급자 판단 오류 처리 경계

D-074 / [RD §11.2](RESEARCH_DESIGN.md#provider-judgment-errors)의 runtime 요구사항이다.
새 실행기는 판단 진단과 실행 불가능한 응답, 입력/통신/무결성 오류를 구분해야 한다.
실행 가능한 합법 선택은 보조 점수·설명 불일치에도 그대로 전송하고 원문·진단을 보존한다.
실행 불가능한 응답은 등록된 복구 범위 소진 후 해당 경기만 실패 처리하며 독립 경기의
admission이나 공유 halt를 변경하지 않는다. 기술적 공유 결함과 승인 상한은 기존 계약대로 처리한다.
경기별 실패 이유·시도/완료/실패·전송 여부와 대응 누락을 기록한다.

**지원 상태:** D-075/EP-066의 JEV `choice-action-v3`는 합법 choice를 실행하고 보조 확률/
confidence 이상을 진단으로 남긴다. 실행 불가능 응답은 경기별 실패로 격리하며 통신·입력·
전송·무결성 오류는 EX-049/050의 기술 중단 경계를 따른다. 검증 근거는 EP-066 receipt다.
C-045의 v1/v2와 EX-047/048 감사는 당시 기준을 유지한다. 기존 버전명을 재사용하거나
봉인된 실행 중 source를 바꾸지 않는다. 다른 실행기의 지원을 자동으로 주장하지 않는다.

<a id="c-047-viewer-export"></a>

## C-047 — 정상 종료 배틀 실험의 뷰어 내보내기

D-076부터 정상 종료한 새 배틀 실험은 완료 보고 전에
`/workspace/exports/battle_viewers/<실험ID 소문자>/index.html`에 열람용 뷰어를 제공한다.
현재 EX-050에도 적용한다. 상위 `battle_viewers/index.html`에서 각 실험으로 연결한다.
D-077부터 경기별 리플레이와 입력·응답을 함께 볼 수 있는 화면을 포함한다. 저장된 배틀
protocol로 생성하고 경기 구분·턴·승패를 원자료와 대조한다. 재생 자료가 없으면 그 한계를 명시한다.
필요한 로컬 자산은 실험 폴더 안에 두고 상대경로를 사용해 폴더 이동 후에도 열리게 한다.
외부 애니메이션 자산이 필요한 경우 명시하되 입력·응답·선택/결과는 오프라인에서 열람할 수 있어야 한다.
출처 실험·원본 위치·원본/복사본 해시·정상완료 분모를 함께 기록한다.
봉인된 원본을 이동·수정하거나 내보내기 복사본으로 대체하지 않는다. 기존 경로가 있으면
내용을 확인하고 다른 실험/버전을 덮어쓰지 않는다. 원본 봉인·링크·오프라인 열람을 확인하고
최종 보고에 내보내기 링크를 제공한다. 이는 완료 절차이며 모든 실행기의 자동 export 구현을 뜻하지 않는다.

D-078의 실험자용 화면은 입력 요청·응답·실제 선택을 우선 배치하고 관측/전송 기술 기록은
별도 영역에 둔다. JSON은 들여쓰기·구문 강조 및 복사/다운로드를 제공한다. 요청을 원자료로
복원하면 출처와 한계를 명시하며 필드값을 바꾸지 않는다. 자동 선택의 미호출을 실제 요청이나
모델 응답처럼 표시하지 않는다. 현재 JEV 내보내기는 jev_viewer.py/jev-researcher-v2가 담당한다.
EP-072의 뷰어 표시에서 좌우 방향키는 이전/다음 결정을 탐색하며 폼·탭 조작은 유지한다.
상대 HP 요약은 공개 비율(%)·미확인을 구분하고 자기 HP와 원래 요청/응답 JSON 값은 보존한다.
[D-101](decisions/D-101-viewer-action-names.md)의 현재/향후 Qwen·JEV 표시에서는 결정 당시
후보 설명·move_ref/현재 기술 슬롯으로 실제 기술명·교체/선봉 대상·테라 여부를 표시한다.
정보 부재는 미확인이며 원 ID·명령·입력/응답·q는 보존한다. 표시 갱신은 이전 봉인 버전을 보존하고 provenance로 연결한다.

## D-081 / EX-052 JEV 일정 실행 확장

C-045/046 입력·선택 의미를 유지하고 별도 일정 실행 경로에서 actor별 프로세스/RNG와
전체 누적 예산·일정 기반 감사를 적용한다. 원문 조건은 EX-052이며 과거2경기 기본값/감사는 보존한다.

## D-083 / EX-053 v3 일정 실행

명시 --experiment EX-053은 EX-052 봉인 manifest의 일정·팀·모델 설정을 직접 검증한다.
EX-053 receipt는 실험/입력/프롬프트·사전 identity·소스·공식 빌드·팀·일정·설정을 결합한다.
고정 ex053-live에 최초1회만 진입하며 과거 receipt/출력은 허용하지 않는다.
C-045 v3와 C-046을 유지한다. 조건·예산·중단 원문은 EX-053이며 과거 버전 감사는 보존한다.

## D-084 — 새 JEV provider 재시도3회

D-084의 jev-provider-retry-v1은 연결/timeout·HTTP429/5xx에 최초+최대3회(총4시도)를 적용한다.
대기1/2/4초, 동일 모델/endpoint/state/questions를 재전송하고 성공하면 종료한다.
인증401/403·그 외4xx·redirect·입력/응답 계약·모델 판단 오류는 재시도하지 않는다.
Session이 시도를 소유하며 내부 client 재시도는0으로 중첩을 막는다. 각 HTTP 예약을 누적
요청 수에 포함하고 최초 시계는 유지한다. 매 시도·대기에 남은 기한/상한/취소를 적용한다.
시도별 요청·응답·오류와 재시도 관계를 기록하고 한 결정의 성공 응답만 선택에 사용한다.
과거 manifest의 정책 누락은 jev-no-retry-v1(0회)로 감사한다. EX-053 및 과거 고정 유료
실행 경로는 당시0회·기존 receipt를 유지하며 이번 변경으로 재개하지 않는다.
Ollama/Z.ai의 provider-retry-v2는 이미3회이며 기존 의미를 유지한다.

## D-085 EX-054 실행 경계

명시 EX-054는 EX-053 봉인 manifest의 일정/팀/모델/처치를 확인하고 EX-052와 대조한다.
새 receipt는 EX-054 identity와 D-084 재시도3회·1/2/4초 대기를 결합한다. 고정 ex054-live에
최초1회만 진입하고 과거 receipt·출력으로는 진입하지 않는다. 전체 누적 물리 시도·시계·실패를 보존하며
시도별 원문·회복/소진 분모와 v2 비교를 감사한다. 조건·예산·중단 원문은 EX-054다.

## D-087 — 새 JEV 재시도 대기 확대

새 기본 jev-provider-retry-v2는 대기10/30/60초·최대3회 재시도를 사용한다.
D-084의 오류 분류·동일 본문·물리 원장·최초 시계/기한/취소 우선·중첩 방지는 유지한다.
v1은1/2/4초로 별도 보존하고 EX-054 고정 실행 identity/감사에 사용한다.
기존 재시도0과 모든 봉인 실험은 당시 정책을 유지한다. 유료 재개 권한을 부여하지 않는다.

## D-088 EX-056 직접 본실험

EX-056만 사전 검증 receipt 없이 승인/생략/실행 identity 기록으로 직접 진입한다. source/빌드/팀/일정/prompt/모델/재시도 정책을 기록하며 미실행 검사를 통과로 표시하지 않는다. 출력 중복·설정 일치·입력/합법성·원장/기한/취소·경기별 감사는 유지한다. 첫4 특별점검0, 고정 ex056-live, jev-provider-retry-v2(10/30/60초). 과거 진입 계약은 불변이다.

## D-089 EX-057 모델 고정 본실험

EX-057은 EX-056와 같은 직접 진입 기록을 사용하되 요청 모델은 jev-1.13.0으로 검증한다. endpoint·일정·팀·처치는 EX-056 봉인과 일치해야 한다. 고정 ex057-live와 ep081에 새 identity를 보존한다. 기존 모델 동일성 검사는 과거 경로에 유지하며 EX-057 비교만 alias에서 고정 ID로의 승인된 차이를 허용한다.

## D-092 — 별도 JEV 오프라인 입력

[D-092](decisions/D-092-jev-offline-input.md)의 `jev-offline-v1`은 C-045의 운영 v3를 변경하지 않는다.
`diagnostics/jev_offline.py`에서 같은 공식 actor/cutoff와 합법 후보/명령을 사용한다. 자기 출전 기술은
`current_move_slots`에 기본 메타데이터·일반 효과·피해량·PP/대상/제한을 통합하고 후보는 슬롯 참조로 연결한다.
슬롯이 없는 자기 포켓몬은 `known_move_set`을 사용하며 `moves`는 상대 공개 기술에 한정한다.
효과는 객체의 `general_effect`로 옮기고 별도 효과 사전은 모델에 보내지 않는다. 상태와 일반 규칙은 구분한다.

내부 ident·initial_state_source·전체 prefix/원래 관측은 감사 자료로 보존하고 모델에서 제외한다.
volatile의 다른 포켓몬 참조는 진영/팀 슬롯으로 바꿔 관계를 유지한다. 상대 HP는 hp_percent와 rounded
정밀도로 제공하며 unknown/확인된 부재/해당 없음을 구별한다. 현재 방어 타입·테라 사용 여부와
공격 STAB용 pre-Tera 타입·설정 테라 타입을 구분하고 전체18타입 상성 행렬을 제공한다.

자기 벤치는 기본 상세다. 비교 옵션은 일반 턴에서만 known_move_set·stats를 생략한다.
선봉/강제교체는 상세를 유지한다. 상대 벤치는 종별 조건부 역할·공개 HP/상태 중심으로 요약한다.
역할 DB의 가능성을 실제 미공개 세트로 확정하지 않으며 역할 prior를 스피드 확률로 전용하지 않는다.

피해량은 EP-082의 고정 추천 세트·공개 이력 필터·계산기를 재사용하되 현재 요청 기술과 상대 공개
기술만 전달한다. 대상/최대 HP 대비 단위/테라 분기/조건을 표시하고 null·사유와 계산된0을 구분한다.
스피드는 같은 계산기의 현재 유효 스피드 지원 범위와 `by_set`의 자기 기준 빠름/동속/느림을
제공한다. [D-093](decisions/D-093-speed-uncertainty.md)에 따라 확률 필드를 제거하고
`speed_certainty`로 세트에 따른 차이·세트 내부 불확실성·유한 지원 내 일치를 구별한다.
관측과 일치하는 후보가 없거나 일부라도 계산 불가하면 unavailable로 두고 우위를 확정하지 않는다.
선봉/강제교체는 not_applicable이다. 스피드 우위와 실제 선공을 동일시하지 않는다.

최근3완료턴 로그는 고정 공식 BattleTextParser와 고정 서버 텍스트로 변환한다. 버전 차이의
자리표시자·능력치 이름 테이블만 호환하며 원문 문구/공식 파서는 수정하지 않는다. HP/정밀도·대상·
능력 변화량을 보충하고 미지원 이벤트는 원문을 보인다. 전체 프로토콜과 변환 감사는 내부에 보존한다.
API·새 배틀·운영 전환은 이 계약의 범위가 아니다. 검증 원문은 EP-093이다.

## D-094 — EX-058 개선 입력 실행 경계

실험 전용 jev-choice-v4는 EP-093 생성 로직/지시문·상세 자기 벤치를 그대로 사용하고
모델 payload의 버전 표기만 변경한다. 자기 제출 팀/공개 cutoff만 계산에 사용한다.
세션 계산기·고정 자료를 재사용하고 비동기 수신을 막지 않으며 감사 자료를 payload 밖에 보존한다.
기존 null+사유는 유지하되 생성 예외/무결성 오류에 fallback0. 기본 v3·과거 재현은 불변.
[EX-058](experiments/EX-058-jev-improved32.md)의4사례·1요청 gate, 사전 요청에서 시작하는
공유6시간 시계·경기별 감사·실패 격리/전체 기술 중단을 적용한다.

## D-095 — EX-059 자기 벤치 축약 실행 경계

실험 전용 jev-choice-v5는 EP-093 compact=True를 사용한다. 일반 턴 비출전 자기 포켓몬의
known_move_set·stats만 생략하며 선봉/강제교체·출전 자기 상세·그 외 처치는 v4와 유지한다.
v5/compact 여부를 실행기·감사기·비교 및 동결 identity에 명시한다. 기본 v3·과거 v4 재현은 유지한다.
D-094의 비동기 계산·관측 경계·감사 분리·실패 폐쇄와 [EX-059](experiments/EX-059-jev-compact32.md)의
4사례·1요청 gate 및 최초 예약부터 공유6시간을 적용한다.

## C-048 — EX-060 독립 분기 실행 경계

[D-097](decisions/D-097-single-battle-branch-rollouts.md)과 [EX-060](experiments/EX-060-single-battle-branch-rollouts.md)의 신규 실행기는 원관측·후보·원명령 재현 gate를 거친 독립 snapshot만 사용한다. 정상 턴 제출 전 barrier와 턴중간 pending queue를 구별하고 양측 private stream·정책 mutable state·난수·후보 실행을 격리한다. simulator snapshot/상대세트/미래 seed는 학습 입력에서 제외한다. 과거 자료·canonical submodule·운영 기본값을 덮어쓰지 않으며 원재현 실패를 새 경기로 대체하지 않는다. 구현 API/산출물은 별도 README에 둔다.


<a id="c-048-action-value-training"></a>

## C-048 — 포켓몬 후보별 soft target 학습 경계

D-098/EX-061의 `pokemon-action-value-v1`은 후보별 레코드다. `input_ref`로 원관측/합법 후보를
읽고 모델에는 관측 전문·후보·평가 행동·이진 질문만 펼친다. `target_probabilities`, counts,
provenance, 원선택 ID, values, snapshot, 미래 seed/trace/상대 첫 선택은 토큰 입력에서 제외한다.
원관측의 공개 정보와 추천 세트 계산 가정의 원표현을 유지한다. max_len 초과는 오류이며 절단하지 않는다.
각 후보 두 결과만 합이1이다. q_values는 후보별 독립 값이며 choice는 최대값·동률 원순서의 합법 ID,
command는 해당 원후보 명령이다. 학습 loader는 기존 정수 answer 경로와 분리한다.
원자료 봉인·기존 EX-060 export는 읽기 전용으로 보존한다.

<a id="c-049-qwen-local"></a>

## C-049 — Qwen 로컬 행동가치 서빙

D-099의 새 `qwen-local-value-v1` 프로필은 EVE InputExample/render/ValuePolicy를 재사용한다.
GET /health는 ready/model/revision/adapter hash/max_len을, POST /evaluate는 원관측·순서 있는
합법 행동을 받아 후보별 q_values·최댓값 choice·command·token/prompt hash·처리 시간을 반환한다.
q는 독립 값이며 합계 검사는 없다. 동률은 원순서, 단일 후보도 forward한다.
FP32 base/adapter·BF16 forward·FP32 readout, eval/no_grad·업데이트0·직렬 GPU 처리다.
금지 필드·후보 매핑·유한 q·응답 coverage를 검사하고 길이 초과는 무절단 오류다.
전송 직전 rqid·합법 목록을 재확인하며 timeout/불완전/stale 응답은 전송하지 않는다.
소유 프로세스만 시작/종료한다. 조건·허용 자원·실패 격리 범위는 각 EX가 소유한다.
EX-062의 고정2경기와 D-100/EX-063의 학습 원대진1경기는 별도 schedule·probe·원장으로 연결한다.
원대진에서는 원세트/순서와 공개 preview 성별만 재구성하며 provenance/seed는 모델 입력 밖에 둔다.

<a id="c-050-qwen-candidate-state"></a>

## C-050 — Qwen 후보 상태 입력과 개발 진단

D-102의 `qwen-candidate-state-v1`은 명시 설정으로만 허용하는 새 입력 버전이다.
기존 JEV v4와 C-049의 요청/응답·독립 A/B q·동률·합법 명령·길이·최신 rqid 경계를 유지한다.
같은 후보 ID/명령/순서에서 직접 이름·사용자/교체 대상·테라, 계산 시점/대상/적용 조건,
지원되는 후보 후 상태·반격·교체 진입 및 일관된 가정 식별자를 제공한다.
미지원/조건부/확인된 부재를 구분하고 부분 계산을 전체 보장으로 표시하지 않는다.
관측 actor cutoff와 자기 제출 팀만 사용하며 숨은 실제 상대 세트/queue·미래를 추가하지 않는다.
공통 규칙을 한 번 유지하고 lead/turn_action/forced_switch 절차를 앞에 결합한다.

개발용 POST /diagnose는 별도 명시 설정에서만 제공한다. 동일 base+LoRA의 별도 prompt와
비사고 greedy 생성으로 검증 가능한 중간 상태 JSON을 출력하며 q·choice·command·전송을
제공하지 않는다. true/false 외 conditional/unknown을 허용하고 원출력/스키마 실패를 보존한다.
진단 결과는 q 입력에 재주입하지 않으며 GPU lock을 공유하지만 요청별 cache/config만 쓴다.
가중치/eval/설정 불변·진단 전후 q 대조를 검증한다. 토큰과 지연은 q/진단을 분리하여 기록한다.
구체적 호출 수·기한·복구·완료·해석은 EX-064가 소유한다. 기존 동결 버전은 변경하지 않는다.

<a id="c-051-joint-q"></a>

## C-051 — EX-065 공동 q 데이터

D-103의 pokemon-joint-q-input-v1은 공식 actor 관측·공개 cutoff·자기 제출 팀만 받아
공통 상태/규칙/계산 가정/결정 지침과 이름 있는 actions[]를 관측당 한 번 렌더링한다.
저장 학습 레코드와 모델 입력 타입을 분리하며 타깃·원선택·seed·private snapshot/상대 세트는
renderer에 허용하지 않는다. 후보 결과 배열/참조를 펼치고 unknown/단위/대상/조건을 유지한다.
타깃은 실제 숨은 상태·고정 후속 정책 조건의 독립 q, 후보 간 정규화0이다.
원재현/모든 snapshot의 복원·다음 경계 일치 후 분기하며 논리 rollout과 시도 ID를 구별한다.
트랜잭션·원자 저장·원본 불변·RNG checkpoint 재개를 요구한다. 후보별32완료가 하나라도
빠지면 관측 전체 미완료다. 로더는 ID 정렬·관측 단위 배치·마스크 손실/argmax를 사용한다.
세부 수집·자원·gate·복구는 EX-065가 소유하며 C-048/049/050의 과거 버전은 유지한다.

<a id="c-054-kev-battle"></a>

## C-054 — Kev pokechamp r1 배틀 연결

D-108의 `kev-joint-noul-v1`은 C-051의 생성기와 원 serializer/snapshot/RoleDB를 그대로 사용한다.
`JointInput.payload_json`을 문자열 state로 보내며 별도 system/chat template을 추가하지 않는다.
actions 원순서의 ID별 noul 질문은 Kev 학습 builder의 QUESTION/describe와 정확히 같다.
criteria·타깃·원선택·private·seed를 보내지 않는다. 모든 응답 ID/type/유한0..1 값을 검증하고
최대 p(true), 동률 원순서로 선택한다. 확률 합계 정규화0, 단일 후보도 호출한다.
원 commands로 매핑하고 전송 직전 rqid/합법 목록·만료를 재검증한다. 불완전/불량/stale/timeout은
무전송이며 fallback0이다. 입력 SHA-256·원 요청/응답·후보 p·선택/명령·지연·재검증/전송을 기록한다.
서버는 loopback HTTP만 사용하며 redirect/외부 proxy/재시도0이다. 모델 bf16·T1과
run/Base/revision/adapter/head provenance를 고정한다. 원 D-108 실행의 unmerged 설정은 보존하며,
D-109의 명시적 추가 승인에 따른 `ex068-v3`는 merged·fused 경로를 사용한다. 새 준비/프로세스
receipt에 이 조건과 원 실패·추가 호출 한도를 연결한다. 원 자원·gate·실행/중단 범위는 EX-068을 따른다.
D-110의 EX-069 본 테스트는 이 통과한 서빙·입력/선택 경로를 재사용하고 사용자 지시로 추가
사전검사를 생략한다. EX-065 test의 팀/seed 메타데이터만 새20경기에 사용하며 저장 test
입력/타깃을 모델에 전달하지 않는다. 별도 경기 admission과 본 실행 한도는 EX-069가 소유한다.

D-111의 명시적 `kev-continuation-noul-v1`은 EX-070의 정확한 한 줄 질문만 사용한다. 기존
`kev-joint-noul-v1`의 기본값·학습 질문 바이트는 유지한다. 설정→worker→Session→HTTP 요청
생성/검증에 profile을 전달하며 HTTP body 필드는 늘리지 않는다. 알 수 없는 profile과 선언에
맞지 않는 질문/순서는 요청·독립 감사·뷰어에서 거부한다. 같은 관측의 state 문자열·후보·명령,
서빙·선택 규칙·공용 생성기·학습 코드/타깃은 유지한다. 새 전용 admission·질문/소스/모델 동결과
실행 예산/중단 원문은 EX-070을 따른다.

<a id="c-052-joint-q-training"></a>

## C-052 — Base 공동 q 모델·학습 경계

D-104의 새 공동 readout은 C-051 JointInput만 받아 관측당 backbone forward 한 번으로
원순서 모든 후보의 독립 sigmoid q를 반환한다. 각 ACTION_ID의 Q_VALUE= 위치를 명시적으로
ID에 연결하며 저장 레코드·타깃·seed·private는 입력 밖이다. 새 renderer 버전과 Base tokenizer를
사용하고 토큰 추가0·무절단32768 한도·범위 초과 실패를 적용한다.
microbatch1의 전체 유효 prefix는 보존하고 마스크된 오른쪽 token-padding만 backbone 전에
제거하여 padding에 따른 readout 변화가 없도록 한다. 원 입력 토큰 절단은 허용하지 않는다.
text backbone LoRA와 별도 공유 value head만 학습하고 frozen base를 보존한다.
입력/타깃/위치의 ID 정합성·관측 평균 마스크 손실·원순서 동률·동일 학습/평가 경로를 검증한다.
checkpoint는 adapter/head/optimizer/RNG/cursor와 base/tokenizer/renderer/data/source 해시를
보존한다. test 진입은 선택 모델 재로딩 대조와 설정 잠금 뒤 모델별1회다.
정밀도·학습량·선택·평가·자원·복구의 실행 원문은 EX-066이며 기존 경로는 유지한다.

<a id="c-053-abyssal-tera"></a>

## C-053 — Abyssal Tera 정책·보완 수집

D-107/EX-067의 `abyssal-tera-v1`은 자기 요청·상대 공개 관측만 읽는 별도 정책이다.
기존 Abyssal을 결정마다 한 번 호출하고 추가 RNG 소비 없이 고정 규칙으로 주문을 바꾼다.
정책 ID·설정 해시는 생성/재현/snapshot/checkpoint에 보존하며 과거 필드 없는 snapshot은
기존 Abyssal로 복원한다. 첫 평가 후보 전 자기 후속 정책 호출은 금지한다.
정책 사유·실제 상대 세트·미래 RNG는 감사/private에만 저장하고 C-051 JointInput/로더를 유지한다.
공통 instructions에는 새 후속 정책의 q라는 전역 설명만 추가하며 개별 판단 사유는 포함하지 않는다.
EX-067의 `public-tera-v2` 입력은 공개 prefix에서 팀별 소모 여부를
`state.terastallization_used.{self,opponent}`로 기록한다. 기절 후 공식 관측기가 해제하는
현재 개체의 Tera 표시와 역사적 팀 소모를 구분하며, JointInput class와 공개 로더는 유지한다.
Tera 상성/피해는 정책 내부 독립 투영으로 계산하고 미지원 근사는 발동 근거로 쓰지 않는다.
수집/자원/검증/복구·봉인/복사·뷰어 규범은 EX-067이다. EX-066 봉인 소스/환경/입력은 보존한다.

<a id="c-062-joint-q-battle"></a>

## C-062 — EX066 공동 q 체크포인트 실제 배틀 경계

D-129/EX081은 C-052 모델·renderer를 읽기 전용 재사용하는 별도 로컬 서빙/배틀 경로다.
새 `/health`는 checkpoint/source/GPU identity를, `/evaluate`는 C-051 JointInput에 대한
원순서 독립 q·최대 q 선택·입력/token hash를 제공한다. 타깃/private/seed는 요청 밖이다.
배틀 player는 공식 관측·원 JointInput 생성·동률 원순서·전송 전 rqid/합법성 검증을 적용한다.
요청600초·무절단32768·fallback/재시도0과 경기별 실패 격리·공유 기술 결함 중지를 검증한다.
실험별 모델/검증 gate·GPU/시계/admission·분모·재수집/복구·봉인은 EX081이 소유한다.
원 EX066 config의 GPU1은 학습 provenance이며 새 자원 GPU0으로 metadata를 덮어쓰지 않는다.
기존 learning·Kev·Qwen 경로의 schema와 기본값, 환경·가중치·STOP은 유지한다.
