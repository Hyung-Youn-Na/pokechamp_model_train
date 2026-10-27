# 공통 실행·운영 측정 — 구성 설명

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="환경과-qualification"></a>
## 환경과 qualification

[EP-096](plans/EP-096-laya-training-environment.md)의 별도 LAYA-RLCD source는
`.tools/laya-rlcd/upstream`, 학습 준비 worktree는 `.tools/laya-rlcd/worktrees/pokemon-training`이다.
고정 upstream source와 독립 `.venv-train`·공개 모델·로컬 캐시를 사용하며 현재 PokéChamp runtime에
연결하지 않는다. 설치·GPU/모델 검증 범위와 재진입은 [환경 안내](../../../.tools/laya-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md)를 따른다.

[EP-207](plans/EP-207-laya-0413-environment.md)의 원본 laya 0.4.13 source는 `.tools/laya-0.4.13/upstream`(고정 `6f0496f7`),
worktree는 `.tools/laya-0.4.13/worktrees/pokemon-training`(branch `pokemon-training-env`, `.venv`)이다. LAYA-RLCD(laya 0.3.4) 환경과 분리하며
EX-118/119의 학습·서빙만 이 환경을 쓴다. 재진입은 [환경 안내](../../../.tools/laya-0.4.13/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md)를 따른다.

[EP-097](plans/EP-097-eve-rlcd-environment.md)의 별도 EVE-RLCD source는
`.tools/eve-rlcd/upstream`, worktree는 `.tools/eve-rlcd/worktrees/pokemon-training`이다.
upstream lock의 Python3.12 환경을 `.venv-eve-rlcd`에 구성하며 LAYA와 import/cache 경로를 분리한다.
공개 Qwen3 환경 검증에 이어 EX-061 포켓몬 가치 학습과 아래 D-099 로컬 서빙 경로를 연결했다. 실제 배틀 검증은 EX-062 중단으로 미완료다.
환경 선택과 재진입은 [환경 구분 안내](../../../.tools/eve-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md)를 따른다.

[EP-098](plans/EP-098-rlcd-lite-environment.md)의 별도 RLCD-Lite source는
`.tools/rlcd-lite/upstream`, worktree는 `.tools/rlcd-lite/worktrees/pokemon-training`이다.
`.venv-rlcd-lite`에 Python3.11 환경과 CUDA12.8 호환 lock을 설치하며 원본 CUDA13 lock은 보존한다.
공개 Qwen2.5 모델의 로컬 구조화 추론만 검증했고 PokéChamp runtime·학습/평가에는 연결하지 않았다.
차이와 재진입은 [환경 구분 안내](../../../.tools/rlcd-lite/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md)를 따른다.

Decision [`D-007`](decisions/D-007-adopt-pokechamp-dotenv-credential.md)이 다음 current boundary를
채택했고 [`EP-001`](plans/EP-001-pokechamp-reproducible-environment.md)이 구현했다.

```text
scripts/pokechamp-env
  -> process 공급자 설정 또는 ignored root .env (process 우선)
  -> repository-local uv 0.12.9 -> pokechamp/.venv + upstream uv.lock
  -> npm ci -> canonical pokemon-showdown build
  -> marker-protected temporary Showdown worktree
       -> Node preload seals Showdown worker PRNG
       -> 127.0.0.1:8000 only
  -> local gen9ou qualification battle
  -> parent OllamaCloudBackend -> Ollama SDK 또는 ZaiChatClient(httpx) / glm-5.3-flash
  -> .artifacts/pokechamp/<command>/<timestamp>/manifest.json
```

Server runner는 fork의 tracked `0.0.0.0` 및 host 전용 SSL config를 사용하지 않고 explicit port,
loopback address와 한 worker를 전달한다. Showdown이 runtime config를 갱신할 수 있으므로 실제
server는 pinned commit의 `.artifacts/` 내 temporary Git worktree에서 실행한다. Canonical
submodule의 source, `node_modules`와 build identity는 bootstrap/preflight가 검증한다.
Pinned fork의 `Config.forcetimer=true`는 parent launcher가 server module 초기화 전에 process-local
`false`로 바꾼다. 따라서 기본 battle에는 Showdown inactivity countdown이 없으며, timed condition은
player가 명시적으로 `/timer on`을 전송할 때만 활성화된다. Provider/request와 orchestration
watchdog timeout은 이 gameplay clock과 별도다.

[D-054](decisions/D-054-zai-provider.md)/[C-034](CONTRACTS.md#c-034-provider)의 `providers.py`가
공급자 설정·URL 검증·비밀 제거·Z.ai 전송을 담당한다. `dotenv.py`는 관련 설정만 비실행 파싱하며
프로세스 값(명시 빈 값 포함)이 우선한다. 로컬 `.env`는 zai를 선택하고 공급자 미지정 코드 기본은 ollama다.
`OllamaCloudBackend`는 기존 import/subclass 호환 이름을 유지하는 공통 admission·실패·출력 검증 경계다.
ZaiChatClient는 httpx 비스트리밍 Chat Completions 응답을 공통 content/thinking/token/done_reason으로 변환한다.
실제 endpoint·전송 옵션·미적용 모델 seed와 미확정 token을 call/trace에 기록한다.

[D-070](decisions/D-070-jev-client.md)/[C-044](CONTRACTS.md#c-044-jev)의 `jev.py`는
배틀 backend와 독립적인 TypeSafe 클라이언트다. 같은 dotenv 로더에서 TYPESAFE 설정을
읽고 httpx로 상태·질문을 POST /systemone에 전송한다. 생성 시 네트워크 호출은 없으며
응답은 native JSON으로 반환한다. TypeSafe 키도 공통 마스킹·child 환경 제외에 포함한다.

CLI·일반 benchmark·현재 B2 prepare는 provider_config를 봉인하고 actor와 실행 전 설정을 대조한다.
과거 미기재 설정은 Ollama로 해석한다. 봉인된 policy/hash·source·중단 상태는 변경하지 않는다.
공급자 키는 .env 또는 환경에서 받고, 필요한 Cloud actor에는 선택된 키만 전달한다.
Git·Node/Showdown·계산기 등 불필요한 자식에서는 제거하며 오류·artifact·응답의 양쪽 키를 마스킹한다.
Qualification은 prompt/response 본문을 보존하지 않고, opt-in 연구 trace만 원문/reasoning을 보존한다.

Decision [`D-009`](decisions/D-009-adapt-always-on-reasoning-output.md)에 따라 always-on reasoning
model의 Ollama JSON qualification call은 `think=low`를 사용한다. Z.ai 전송 항목은 C-034를 따른다. 새 호출에는 131072-token 출력 예산과
compact JSON-only 후행 지시를 적용한다. Response는 parse 가능해야 하고 action은 현재 available
move/switch와 일치해야 한다. 첫 위반은 `output_contract` terminal failure로 battle을 취소하므로
upstream의 반복 재호출이나 max-damage fallback이 qualification success로 분류되지 않는다.

Qualification artifact는 `technical_qualification`, `efficacy_evidence=false`로 분류한다.
실측 probe·배틀 검증 범위는 [EP-001](plans/EP-001-pokechamp-reproducible-environment.md)을 따른다.

별도 `jev_study.py`는 EX-052/053의 봉인32행 일정·공유 원장/시계·순차 제출과
독립 Abyssal 프로세스/RNG를 관리한다. `jev_battle_audit.py`는 일정별 actor/완료·실패를
감사하고 `jev_study_export.py`가 경기 목록/리플레이를 내보낸다. 기존2경기 기본값은 유지한다.

`jev_effects.py`는 JEV 모델 투영의 자기·확인된 상대·기술 ID/후보·최근 공개 이력을
고정 `effects/` 자산에 연결한다. state.effect_reference에는 영어 name/desc만 요청당 한 번
수록하고 별도 manifest/input 기록에 사전 identity를 남긴다. v3 모델 payload의 모든 위치에서
current_pp_source를 제거하며 원관측/request·초기 PP 정책은 감사용으로 보존한다.
기본 지식 원문과 사전 사용 지시는 jev-choice-v3.txt에 있다.

JEV 전용 `jev_battle.py`는 공식 관측의 간결한 투영→native Choice→요청 슬롯 전송을 수행한다.
별도 순차 실행·요청 원장·HTML 보고를 제공하며 기존 Chat 공급자/B2 경로를 변경하지 않는다.
EX-053 명시 선택은 EX-052 manifest를 직접 검증하고 v3 receipt·사전·실제 HTTP 요청 본문을 결합한다.
`jev_comparison.py`는 봉인된 두 실행을 slot_id로 연결해 공통 완료쌍의 탐색적 점수차를 산출한다.

새 기본 입력은 D-082의 jev-choice-v3다. D-079의 자기 요청 슬롯·검증된 시작 전 상태·고정 서버 PP 규칙을 유지한다.
과거 v1/v2 감사는 manifest 버전으로 분리한다. EP-070은 오프라인 교정 근거이며 EP-071/EX-051에서 같은 조건 실제2경기 검증을 완료했다.
계약은 [C-045](../../research/model-evaluation/CONTRACTS.md#c-045-jev-battle), 현재 완료된 v2 실행은 EX-051이고 과거 EX-050은 보존한다. choice-action-v3 판단 진단·경기 실패 격리는 [C-046](../../CONTRACTS.md#c-046-provider-judgment)이다.

별도 `diagnostics/jev_damage_samples.py`는 EX-057의 제한된 actor prefix와 자기 제출 세트를
재현하여, 출전 포켓몬 사이의 피해량 범위 프롬프트 샘플을 생성한다. `damage_sets.py`는
고정 추천 세트별 선택지와 공개 이력의 정합성을 처리하고, `jev_damage.py`는 기존 계산기와
보정을 재사용해 테라 분기·방향별 범위를 합산한다. `jev_damage_verify.py`는 개별 Smogon
계산과 합성 테라 관측을 대조한다. EP-082 자체는 오프라인 진단이며, D-094의 EX-058은
EP-093 투영을 거쳐 이 계산을 사용한다. 범위·재현·검증은 [EP-082 보고](../../exec-plans/evidence/ep082/report.md)를 따른다.

별도 `diagnostics/jev_offline.py`는 운영 v3를 생성한 뒤 효과 인라인·기술 슬롯·역할/HP/테라·
전체 상성표·공식 자연어 로그로 투영한다. `jev_text.cjs`는 기존 고정 클라이언트의 BattleTextParser와
고정 서버 text 데이터를 사용하며 자리표시자/능력치 테이블만 호환한다. `jev_speed.py`는 EP-082와
같은 공개 후보·계산기의 현재 유효 스피드 범위·세트별 비교·정성적 불확실성을 산출한다(D-093).
추천 세트 안의 일치와 전세트 확정을 구분하며 확률 필드는 제공하지 않는다.
`jev_offline_samples.py`는 일반/선봉/강제교체의 저장 prefix를 재생하고 상세/자기 벤치 축약 입력과
대리 토큰 비교를 생성한다. [EP-093](../../research/input-and-memory/plans/EP-093-jev-offline-input.md)은 오프라인 검증 범위다.
D-094의 실험 전용 jev_v4.Adapter가 같은 생성기를 재사용하여 EX-058에 연결하며 일반 기본 v3는 유지한다.

<a id="execution-boundaries"></a>

<a id="병렬-실행admission현재-제한"></a>
## 병렬 실행·admission·현재 제한

Parent `execution.py` coordinator가 seal된 순서대로 경기 자리를 배정한다.
`parallel_server.py`는 attempt별 Showdown process와 temporary worktree를 소유하고,
각 actor는 명시적인 localhost:8100–8109 ServerConfiguration을 사용한다.
`permits.py`의 private Unix socket broker가 계정·모델 admission/cooldown/cancellation을
공유한다. `cloud.py`는 HTTP 직전 permit을 받고 로컬 대기와 HTTP 시간을 분리 기록한다.
`calibration.py`는 고정 개발 corpus·조건·순서·예산을 seal하고 측정하며,
`concurrency_study.py`는 C*/8판 비교/남은 예산 gate를 통과할 때만 후속 단계를 실행한다.

`execution.py`는 C-036의 새 Z.ai 준비에 기본4·`zai-default4-v1`,
그 외 기존 경로에 기본8·`cloud-default8-v1`을 제공한다. A 진단과 A/B 직접대결 coordinator는
봉인된 execution에서 worker·port pool·계정/모델 permit 크기를 읽고 완료된 자리부터 다음 slot을
투입한다. 기존 Ollama 전용 IO battle·요약 진단·행동 요청 검증은 기본8을 사용한다. Gate의1/8 비교와 집계는
봉인된 `parallel_concurrency`를 따른다. 명시1–10 실행과 기존 표식 없는10 설정은 유지한다.
실험 정책 hash를 다시 정의하지 않고 새 execution의 동시성 항목만 C-029로 우선한다.
과거 실험의 source·원자료·시계·원장·중단 상태는 변경하지 않는다.

EX-032의 공유 permit 반환 실패는 미수정이다. 현재 `permits.py` 서버의 release 대기는
새 전송 정책에서1500+5초, 과거 봉인 실행에서300+5초이며 client ACK 대기는2초다. `cloud.py`는 응답 수신 후 반환 실패를
configuration으로 기록하고 원응답을 보존한 채 실행을 중지한다. 로컬에서 대기 만료 경로를
재현했으나 실제10건 모두의 세부 지연 원인은 확정되지 않았다.300초 요청 설정을
전체 벽시계 경과의 hard deadline으로 해석할 수 없다. 중단 snapshot의 orphan8과
실행 종료 뒤 프로세스/소켓 정리는 별개다. [EX-032 조사·보고](../../exec-plans/evidence/ep026/report.md).

EX-033 정상 완료는 EX-032 외부 RAM 원인의 독립 입증이나 기존2초 ACK 경계 제거가 아니다.
[EX-033 보고](../../exec-plans/evidence/ep027/report.md).

<a id="기준선행동-후보fallback-경로"></a>
## 기준선·행동 후보·fallback 경로

D-012/C-010의 benchmark는 `plan -> run -> analyze` 경로다. Plan은 parent source snapshot과
40-slot 또는 D-015의 8/32-slot 핵심 대진 order를 seal하고, run은 경기별 temporary Showdown과 독립 actor process 두 개를 만든다.
Benchmark-only BattleStream start hook이 seed를 주입하고 actual seed를 별도 기록한다.
Actor는 C-009 recorder를 사용하고 call-role adapter가 minimax의 행동·상대 예측·tool·score를
검증한다. 두 actor source bundle은 sealed match record로 연결되며 분석은 source를 읽기만 한다.
기존 qualification 및 고정 IO research 경로는 유지된다. Main experiment는 자동 시작하지 않는다.

Runner는 worker 종료 후 최종 actor 오류도 합쳐 중단·재시도 분류를 결정한다. 파생 분석은
원 match 분류와 actor 자체/peer 오류를 구별하고, pinned AST의 예외 경로와 실제 전송 행동으로
minimax fallback을 집계한다. 대진별 자원 추정, 분석 코드 사본/hash와 보고서를 원자료 밖에 쓴다.

`battle_adapter.py`는 benchmark actor 안에서만 pinned AbstractBattle의 식별/request 연결을
교체한다. 진영별 ident와 request details로 미리보기 객체를 재사용하며 모호성은 environment
오류다. `guard_parser`가 비동기 처리의 치명적 예외를 actor 감시 루프로 전달한다.
`benchmark_player.py`의 ActionCandidates가 동일 요청의 JSON prompt·validation·BattleOrder
변환을 담당한다. 자기 available 목록,상대 공개 미리보기/관찰 및 기존 기술 추정을 구별한다.
요청에 후보/출처,응답에 검증 실패 이유를 기록한다. 재질문·임의 행동 대체는 없다.
`action_validation.py`는 과거protocol/target snapshot의 읽기 전용 재현과로컬8판을 지원하고,
`action_study.py`는 봉인24상태×6회와엄격한Cloud8/32판 gate를 실행한다.
새execution의 `retry_transient=0`은 보충을 금지하며 과거설정 부재의 기본1회는 유지한다.
EX-015의 gate 실패·배틀 미실행은 [실험 기록](experiments/EX-015-action-candidate-validation.md)을 따른다.

봉인 execution의 `action_policy="upstream"`은 D-017 식별/parser 격리를 유지하면서
`benchmark_player.py`가 pinned IO와 minimax 함수의 AST에 계측을 붙이는 별도 경로다.
`cloud.py`는 원본 Ollama 접미사/추출을 적용하고 출력 오류를 terminal로 만들지 않는다.
Provider 종료는 유지한다. IO ID·시도·역할·실패와 fallback 단계는 요청/판단 및 actor
진단에 연결된다. 반환 객체 출처를 실제 wire 판단과 연결하고 `fallback_metrics.py`가
검색 이벤트와 실제 전송을 분리하여 전체/유효 집계한다. 필드 부재는 기존 strict 경로다.

<a id="d-060-전송-시도와-논리-요청"></a>
## D-060 전송 시도와 논리 요청

`transport_policy.py`의 provider-retry-v2는 새 provider_config에 timeout 네 단계와 재시도3·
대기1/2/4초를 봉인한다. 연결·timeout·HTTP5xx·429가 대상이며 최종 실패429만 전체 halt한다. `cloud.py`는 논리 요청마다 한 최종 call/trace를 기록하고
`http_attempts`에 개별 시도·시간·오류/내부 원인·예약 경로를 연결한다. 각 시도는 공통
admission/permit을 거치며 대기 중에는 permit을 점유하지 않는다.
`attempt-N.json`은 응답/오류 증거, `retry-N.json`은 대기 이후 재시도/취소 기록이다.
`team_preview_study.validate_reservation`은 동일 입력/논리 identity·연속 번호·직전 정책상 재시도 가능한 실패
봉인을 원자 원장 안에서 대조하고 그 외 중복 결정을 차단한다.
`concurrency_metrics`와 선봉 보고/viewer는 최종 요청 결과와 개별 HTTP 수를 구분한다.
과거 EX·정책 표식이 없는 봉인은 legacy-300-v1로 해석하고 기존 정책 hash를 유지한다.
connect-retry-v1/legacy와 과거 실행 봉인은 유지한다. 현재 구현·검증은 [EP-049](plans/EP-049-provider-retry-viewer.md)를 따른다.

<a id="jev-provider-재시도-d-084"></a>
## JEV provider 재시도 (D-084)

새 JevClient/Session/StudySession 기본은 jev-provider-retry-v1(최초+3회)이다.
Session이 각 시도를 예약·기록하고 단일 전송 client를 사용한다. 동일 payload/모델/endpoint와
기한/취소/누적 상한을 유지한다. 감사는 논리 결정과 물리 시도를 구분하며 과거0회 해석도 유지한다.
EX-053 등 고정 과거 유료 실행은 legacy를 명시한다. 새 수집 등록/receipt를 대신하지 않는다.

EX-054는 별도 실험 선택과 receipt에서 EX-053 일정/처치·EX-052 기준선·재시도3회를 결합한다.
물리 HTTP 시도와 논리 요청·회복/소진을 분리 집계하고 새 뷰어의 기술 기록에 시도별 원문을 포함한다.

<a id="독립-openai-decisions-api-환경"></a>
## 독립 OpenAI Decisions API 환경

[D-163](decisions/D-163-openai-decisions-environment.md) / [C-078](CONTRACTS.md#c-078-openai-decisions):
`scripts/openai-decisions` → `.tools/openai-decisions/.venv` →
`integration.openai_decisions` → 공식 `POST /v1/decisions` (`gpt-6-luna`).
프로세스 환경/루트 `.env`에서 키를 읽으며 `--dry-run`은 요청만 출력한다.
사용자 JSON 또는 predicate/choice/score 예제를 입력받는다. 기존 배틀 경로와 분리되며
환경 구성 검증은 모의 HTTP만 수행했다. [사용법](../../../integration/openai_decisions/README.md).
