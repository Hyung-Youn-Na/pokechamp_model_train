# 공통 실행·운영 측정 — 실행 계약

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="c-008--pokéchamp-qualification-environment"></a>
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

구현과 사용법: [`integration/pokechamp/README.md`](../../../integration/pokechamp/README.md),
[`D-007`](decisions/D-007-adopt-pokechamp-dotenv-credential.md),
[`D-009`](decisions/D-009-adapt-always-on-reasoning-output.md),
[`D-011`](decisions/D-011-default-untimed-showdown-battles.md).

<a id="c-010--benchmark-pilot-control-record"></a>
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

<a id="c-011--benchmark-병렬-실행과-요청-admission"></a>
## C-011 — Benchmark 병렬 실행과 요청 admission

[D-016](decisions/D-016-model-concurrency.md)에 따라 C-008의 8000 qualification은 유지하고
execution-config가 seal된 benchmark에 8100–8109 독립 loopback 서버 예외를 적용한다.
배틀/계정/모델 상한과 evidence는 run에서 변경할 수 없다. Unix socket broker는 요청 직전
계정·모델 permit을 동시에 부여하며 취소/장애는 신규 Cloud 요청을 차단한다.
Worker 유실은 timeout까지 보류하고 429는 계정 공통 Retry-After(없으면 30초) 대기다.
전역 실행 lock, source seal, 동일 slot transient 1회 retry와 모든 분모는 C-010을 따른다.
Batch 시간은 실제 시작–종료 경과 시간이며 중첩 attempt/actor 시간 합은 자원 지표다.
로컬 permit 대기·HTTP 경과·decision 지연을 구별하고 provider 내부 대기는 추정하지 않는다.

<a id="c-012--benchmark-식별-및-요청별-후보"></a>
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

<a id="c-013--원본-행동-생성-별도-benchmark-조건"></a>
## C-013 — 원본 행동 생성 별도 benchmark 조건

[D-018](decisions/D-018-upstream-fallback.md)에 따라 `action_policy="upstream"`에 한해
C-010/C-012의 출력 terminal·후보 prompt 규칙 대신 원본 프롬프트/추출/행동 변환/재시도/fallback을
적용한다. Provider·환경·무결성 종료는 유지한다. 필드 부재는 strict다. 정상 fallback 완료는
유효하며 전체/유효 각각 실제 전송 판단과 경기 분모를 보고한다. D-017 gate는 EX-016에
적용하지 않는다. 고정 fixture·로컬2판 후32슬롯10/10을 실행하며 Cloud4시간/신규3시간45분
중지와 retry_transient=0을 봉인한다. 이전 결과와 정상 minimax/효능/최대 처리량 주장은 분리한다.

<a id="c-029--새-cloud-기본-동시성8"></a>
## C-029 — 새 Cloud 기본 동시성8

[C-036](../../research/lead-policy/CONTRACTS.md#c-036-zai4)의 새 Z.ai 기본4 예외 외에는
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

<a id="c-034-provider"></a>

<a id="c-034--새-배틀-공급자-설정과-호환"></a>
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

<a id="c-038-transport-retry"></a>

<a id="c-038--새-전송-정책"></a>
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

<a id="c-044-jev"></a>

<a id="c-044--독립-jev-클라이언트"></a>
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

<a id="d-084--새-jev-provider-재시도3회"></a>
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

<a id="d-087--새-jev-재시도-대기-확대"></a>
## D-087 — 새 JEV 재시도 대기 확대

새 기본 jev-provider-retry-v2는 대기10/30/60초·최대3회 재시도를 사용한다.
D-084의 오류 분류·동일 본문·물리 원장·최초 시계/기한/취소 우선·중첩 방지는 유지한다.
v1은1/2/4초로 별도 보존하고 EX-054 고정 실행 identity/감사에 사용한다.
기존 재시도0과 모든 봉인 실험은 당시 정책을 유지한다. 유료 재개 권한을 부여하지 않는다.

<a id="c-078-openai-decisions"></a>

<a id="c-078--독립-openai-decisions-api-호출"></a>
## C-078 — 독립 OpenAI Decisions API 호출

[D-163](decisions/D-163-openai-decisions-environment.md)의 독립 클라이언트에만 적용한다.
공식 `https://api.openai.com/v1/decisions`와 `gpt-6-luna`를 사용한다. 루트 `.env`는 일반 파일·
권한600·Git 제외이며 OPENAI_API_KEY는 프로세스 설정(명시적 빈 값 포함)이 우선한다.
파일 변수 확장·shell 실행은 없다. dry-run은 키 열람과 네트워크 없이 요청 JSON을 출력한다.
실제 호출은 timeout60초·재시도0·redirect 금지이며 오류 본문/키는 출력하지 않는다.
응답 answers와 refusal은 JSON 원형으로 제공한다. 기존 배틀 공급자·실험 계약에는 적용하지 않는다.
