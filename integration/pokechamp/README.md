# PokéChamp 기술 자격 검증 환경

## 분리된 연구선에서 읽는 방법

현재 checkout의 작업·환경 선택은 [연구 매뉴얼](../../project_context/RESEARCH_MANUAL.md), 실행 여부는
[STATUS](../../project_context/STATUS.md#active-work)를 먼저 확인한다. 아래 실행 명령은 `/workspace`의 기존 환경을
기준으로 한 기술 참조다. L1–L5 worktree는 보존·설계용이며 실행용 환경이 구성되어 있지 않다.
D/EX가 지정된 조건·경로·재개 명령은 해당 실험의 범위로 읽고, 공통 규칙은 기존 적용 범위를
유지한다. 새 실험의 입력·출력·실행 범위는 등록된 작업에서 정한다.


## 고정 대진 공개 상태 MCTS

EX-076의 작은 전용 모델·동시행동 탐색·학습/평가 실행기는 별도
[fixed_matchup 사용법](fixed_matchup/README.md)을 따른다. 기존 Qwen 경로와 독립이며
구현·CPU 개발 검증과 실제 GPU 실험 실행을 구분한다.
D-126/EX-079는 완료된 첫라운드에서 정기 개발 평가·목표/정체/라운드 종료조건을 적용하고
최고 모델을 잠근 뒤 독립 시험한다. `stopping-prepare`/`stopping-run`의 범위는 해당 사용법과 EX079를 따른다.

## 새 B/B2 공식 관측 기본값

새 준비는 `official-client-v1`과 설명서 v1.4.0/B2 b2-official-v1을 봉인한다.
과거 필드 부재·EX 지정·명시적 legacy는 기존 의미다.
[정보 경계·빌드·실행 안내](observation/README.md)와
[검증/로컬 viewer](../../project_context/exec-plans/evidence/ep056/report.md)를 참조한다.

## 기본 IO 테스트의 설명 오류 기입

별도 사용자 지시가 없으면 기본 IO 알고리즘 테스트에 설명 오류 사후 검토·annotation 기입을
추가하지 않는다. 설명 정확성 평가를 명시적으로 요청한 경우에만 해당 범위에서 수행한다.
IO 기술 검사와 응답/reasoning 기록·표시는 유지하며, 미평가는 오류0이나 검토 통과를 뜻하지 않는다.
새 기본 테스트는 설명 미검토만으로 완료를 막지 않는다. 기존 오류 기록·viewer·Blocked 및
아래 과거 실험별 명시 gate는 보존한다. [규범 기본값](../../project_context/RESEARCH_DESIGN.md#io-explanation-review).

이 디렉터리는 [`D-007`](../../project_context/shared/execution/decisions/D-007-adopt-pokechamp-dotenv-credential.md)과
[`EP-001`](../../project_context/shared/execution/plans/EP-001-pokechamp-reproducible-environment.md)의
repository-owned integration이다. 외부 submodule을 수정하지 않고 pinned PokéChamp baseline을
bootstrap하고 local/선택된 Cloud 공급자의 실행 가능성을 확인한다. Battle 결과는 technical qualification
evidence일 뿐 성능 평가 결과가 아니다.

## 새 Cloud 실행의 동시성 기본값

[D-056](../../project_context/research/lead-policy/decisions/D-056-zai-concurrency4.md)/
[C-036](../../project_context/research/lead-policy/CONTRACTS.md#c-036-zai4)에 따라 Z.ai를 지원하는 새 준비는
공급자 확정 후 배틀·계정·모델 기본 동시성 **4**와 `zai-default4-v1`을 봉인한다.
명시 동시성은 실험별 제한 안에서 우선하며 실행·검증·보고는 봉인값을 사용한다.
Z.ai 기본 소유 포트는8100–8103이다. 기존 Z.ai 동시성8의 봉인 자료도 당시 선언으로 검증한다.

[D-045](../../project_context/shared/execution/decisions/D-045-cloud-concurrency-default8.md)/
[C-029](../../project_context/shared/execution/CONTRACTS.md#c-029--새-cloud-기본-동시성8)에 따라 Ollama 및 기존 공급자 전용 경로의 새 병렬 실행은
배틀·계정·모델 요청 기본값이 각각 **8**이다. A 진단/A·B 직접대결, IO 비교, 행동/요약 요청 검증과
Cloud gate에 적용한다. 준비 CLI의 `--concurrency 10`처럼 명시한1–10 값은 그대로 사용한다.
순차/병렬 비교 gate의 병렬 조건은2–10이며 기본 비교는1/8이다.

`execution.evidence.concurrency_policy=cloud-default8-v1`과 선택한 한도를 준비 시 봉인한다.
Gate에는 같은 표식과 `parallel_concurrency`, 요약 진단에는 config의 표식과
`account_limit`/`model_limit`을 보존한다. 실행 중 값 변경은 허용하지 않으며 worker·포트·공유 permit,
집계와 시간 추정은 봉인된 값을 읽는다. 기본 포트는8100–8107, 명시10은8100–8109다.

표식 없는 과거 설정·gate는 원래10 및1/10 기준으로 검증한다. 아래 개별 실험의 고정10 설명은
그 실험의 등록 조건이며 새 준비에는 C-029가 동시성 항목에 우선한다. 별도 calibration의 명시1–10,
첫10경기 검토의 표본 수, 요청/경기 timeout·retry·예산·입출력 규칙은 유지한다.
이 변경은 기존 Blocked 실험 재개나 새 유료 호출의 승인이 아니다.

## 고정 경계

| 항목 | 값 |
|---|---|
| PokéChamp | `pokechamp/`의 pinned Git submodule |
| Showdown | `pokemon-showdown/`의 pinned Git submodule |
| Python | `/opt/conda/bin/python3`, `3.11.11` |
| Resolver | repository-local `uv 0.12.9`, upstream `uv.lock` |
| Battle | `gen9ou`, team ID `1` 대 `2`, Python seed `100` |
| Showdown RNG | `100,100,100,100` root seed |
| Server | `127.0.0.1:8000`, `--no-security --ai-tournament` |
| Showdown battle timer | 기본 off; 명시적 timed-run에서만 opt-in |
| Cloud | 명시적 `ollama`/`zai` 선택, 모델 `glm-5.3-flash` |
| Request | 읽기 timeout600초·연결/쓰기/pool300초 ([C-038](../../project_context/shared/execution/CONTRACTS.md#c-038-transport-retry)), output 상한 131072 (128K), Cloud 기본 최대 context, fallback 없음 |
| JSON action | thinking low, 131072-token cap, compact JSON 지시, available action 검증, 첫 위반 시 fail-closed |

Showdown은 `.artifacts/pokechamp/runtime/` 아래의 marker-protected 임시 Git worktree에서 실행한다.
따라서 server가 날짜별 config를 갱신해도 canonical submodule은 clean 상태를 유지한다. Stop은 이
CLI가 만든 PID와 worktree만 제거한다.

### Battle 시간 정책

Decision [`D-011`](../../project_context/shared/execution/decisions/D-011-default-untimed-showdown-battles.md)에
따라 별도 timed-run 지시가 없는 qualification 및 research battle은 **시간 제한 없이** 실행한다.
여기서 시간 제한 없음은 Pokémon Showdown의 turn별·battle 전체 inactivity countdown이 꺼진다는
뜻이다. Pinned fork의 `forcetimer=true`는 parent launcher가 server process 안에서 `false`로
override하며 canonical submodule은 수정하지 않는다.

Timer가 연구 변수인 run만 실행 전에 condition과 설정을 선언하고 `/timer on` 또는 player의
`start_timer_on_battle_start=True`로 명시적으로 켠다. Timer activation 여부를 run evidence에
기록하며 timed와 untimed 결과를 같은 condition으로 합치지 않는다. Provider request timeout과
CLI의 battle watchdog은 hung process를 종료하기 위한 infrastructure safety 경계로 계속 적용되고,
Showdown timeout loss나 efficacy defeat로 해석하지 않는다.

## 환경 구성·자격 검증 명령 (기술 참조)

현재 연구 주기의 기존 환경을 이용할 때는 [환경 선택](../../project_context/RESEARCH_MANUAL.md#environment)을
따른다. 아래 bootstrap은 설치 작업이며 server·probe·smoke는 각각 서버/모델 호출·배틀을
포함할 수 있다. 기본 시작 확인 명령으로 일괄 실행하지 않는다.

```bash
scripts/pokechamp-env bootstrap
scripts/pokechamp-env server start
scripts/pokechamp-env preflight --scope local
scripts/pokechamp-env smoke --local-only
scripts/pokechamp-env server stop
```

[D-054](../../project_context/shared/execution/decisions/D-054-zai-provider.md)에 따라 로컬 기본 공급자는 Z.ai다.
루트 `.env`에 자신의 API 기본 주소와 키를 입력한다. 기존 키·다른 설정은 보존하고 권한은 `0600`으로 유지한다.
새 checkout에서는 `.env`가 없을 때만 `.env.example`을 복사한다.

```dotenv
POKECHAMP_PROVIDER=zai
POKECHAMP_MODEL=glm-5.3-flash
ZAI_BASE_URL=
ZAI_API_KEY=
```

`ZAI_BASE_URL`은 `/chat/completions` 앞까지의 HTTPS API 기본 주소다.
예를 들어 공식 일반 API 기본 주소는 `https://api.z.ai/api/paas/v4`이며 자신의 계정·상품에 맞는 주소를 입력한다.
키·query·fragment를 URL에 넣지 않는다. API 경로와 요청 항목은
[공식 Chat Completions 계약](https://docs.z.ai/api-reference/llm/chat-completion)을 따른다.
실제 계정의 `glm-5.3-flash` 사용 가능 여부와 연결 성공은 이번 무API 구현 검증으로 확인하지 않았다.

프로세스 환경값은 명시 빈 값까지 `.env`보다 우선한다. 공급자 설정 자체가 없을 때의 코드 기본값은 Ollama다.
Ollama를 선택하려면 `POKECHAMP_PROVIDER=ollama`와 `OLLAMA_API_KEY`를 사용한다.
Ollama 주소는 `https://ollama.com`으로 고정한다. 로더는 파일을 shell로 실행하지 않으며,
양쪽 키는 오류·로그·artifact에서 마스킹하고 Git·Node/Showdown 등 키가 불필요한 자식에게 전달하지 않는다.
Cloud actor에는 선택된 공급자의 키만 전달하여 프로세스 override를 보존한다.

Z.ai 요청은 비스트리밍, thinking enabled, reasoning_effort low, max_tokens 131072,
읽기 timeout600초이며 JSON 요청에는 response_format을 쓴다. 모델 seed는 전송하지 않고
`seed_applied=false`로 기록한다. 게임·대진 seed는 유지하며 연결 오류에만 아래 제한된 재시도를 적용한다. 공급자 대체는 없다.
일반/B2 새 준비 자료는 `provider_config`를 봉인한다. 과거 공급자 미기재 자료는 Ollama로 해석하고,
실행 설정이 다르면 HTTP 전에 차단한다. 새 공급자 설정으로 과거 중단 실험을 재개하지 않는다.

아래 `probe`와 `smoke --cloud-only`는 실제 API를 호출한다. 주소·키 입력 후 연결을 확인할 때 사용한다.
이번 구현 검증에서는 실행하지 않았다. 무호출 설정·환경 확인은 `preflight --scope cloud`다.

```bash
scripts/pokechamp-env server start
scripts/pokechamp-env preflight --scope all
scripts/pokechamp-env probe
scripts/pokechamp-env smoke --cloud-only
scripts/pokechamp-env server stop
```

`smoke`에 mode flag를 주지 않으면 local smoke 뒤 cloud smoke를 실행한다. Cloud auth, model,
rate-limit, timeout 또는 transport failure는 다른 model/provider나 local inference로 fallback하지
않고 nonzero로 끝난다. JSON 또는 battle-action contract 위반도 첫 provider response에서 battle을
취소하며 PokéChamp의 반복 재호출이나 max-damage fallback을 성공으로 인정하지 않는다.

각 command는 `.artifacts/pokechamp/<command>/<UTC timestamp>/manifest.json`에 source SHA,
toolchain, sealed configuration, outcome과 비밀이 아닌 provider metadata를 기록한다. Prompt,
response content와 API key 값은 기록하지 않는다. `.artifacts/`와 `.tools/`는 local generated
state이며 Git에서 제외된다.

## Research battle observability

Qualification과 별도로, 사람이 LLM output·실제 action·이후 battle 전개를 함께 검토할 때만
[`D-010`](../../project_context/shared/viewers/decisions/D-010-adopt-pokechamp-battle-observability.md)의 opt-in
research command를 사용한다. 이 경로는 prompt, raw response와 provider reasoning까지 저장하므로
local sensitive research data로 취급한다. `experiment_id`와 별도 data root가 모두 명시되지 않으면
활성화되지 않는다. `POKECHAMP_DATA_ROOT`는 credential `.env` parser의 대상이 아니므로 command를
실행하는 shell/IDE environment에 설정한다.

```bash
export POKECHAMP_DATA_ROOT=/workspace/.pokechamp-data
scripts/pokechamp-env server start
scripts/pokechamp-env research run --experiment-id manual-review-001
scripts/pokechamp-env server stop
```

`research run`은 기존 controlled-local `gen9ou` team 1 대 2, IO-vs-Abyssal matchup을 사용한다.
Data root와 새 source bundle을 먼저 exclusive-open하므로 root가 없거나 쓸 수 없거나 같은
`battle_id`가 이미 있으면 player/challenge를 만들지 않는다. `--battle-id`를 생략하면 새 ID를
생성한다. 잘못된 bundle을 정정할 때 원본을 수정하지 않고 다음처럼 새 identity를 연결한다.

```bash
scripts/pokechamp-env research run \
  --experiment-id manual-review-001 \
  --battle-id correction-002 \
  --replacement-for original-001
```

Bundle 위치와 파일 역할은 다음과 같다.

정확한 v1 field catalog는 [`observability/SCHEMA.md`](observability/SCHEMA.md)에 있다.

```text
$POKECHAMP_DATA_ROOT/experiments/<experiment_id>/
├── catalog.sqlite                 # derived; rebuild 가능
├── index.html                     # derived; browser 검색 UI
└── battles/<battle_id>/
    ├── manifest.json              # source evidence
    ├── events.jsonl               # source evidence
    ├── checksums.sha256            # source seal
    ├── showdown.log               # derived
    ├── replay.html                # derived; network animation + local fallback
    └── report.html                # derived; offline decision/timeline viewer
```

`report.html`은 battle state, final parsed output, validation, 실제 wire action과 후속 protocol을
decision card로 표시한다. Effective prompt, raw response, provider reasoning 및 token/latency metadata는
접힌 세부 영역에 있다. 리플레이 패널은 넓은 화면에서 오른쪽, 좁은 화면에서 상단에 고정되어
decision을 스크롤하면서 계속 재생할 수 있다. `replay.html`의 animation은 official Pokémon Showdown asset에 접근할 수 있을
때만 동작하지만, report의 전체 static timeline과 replay의 protocol fallback은 network 없이도
동작한다.

Derived output은 source seal을 바꾸지 않고 다시 만들거나 검증할 수 있다.

```bash
scripts/pokechamp-env research verify --experiment-id manual-review-001
scripts/pokechamp-env research verify \
  --experiment-id manual-review-001 --battle-id correction-002
scripts/pokechamp-env research rebuild --experiment-id manual-review-001
```

진행 중 logging write가 실패하면 gameplay를 변경하지 않고 warning을 내며 가능한 bundle을
`evidence_complete=false`로 seal한다. Checksum 불일치와 partial bundle은 viewer/catalog에서
incomplete로 표시한다. 이 경로는 automatic L4/L5 write나 efficacy 평가를 수행하지 않으며 모든
bundle은 `research_observability`, `efficacy_evidence=false`다. Recorder를 전달하지 않는 기존
`probe`/`smoke` qualification artifact에는 계속 prompt, response 또는 reasoning이 들어가지 않는다.

<a id="completed-viewer-export"></a>

## 정상 종료 실험의 뷰어 생성 위치

정상 종료한 배틀 실험은 완료 보고 전에 **`/workspace/exports/battle_viewers`**에 뷰어를
생성한다. [C-047](../../project_context/CONTRACTS.md#c-047-viewer-export)을 따른다.

1. 실험별 폴더 `exports/battle_viewers/<실험ID 소문자>/`를 만들고 진입점을 `index.html`로 둔다.
2. 경기별 입력·응답과 배틀 리플레이를 함께 볼 수 있게 구성한다. 기존 뷰어·리플레이를
   복사하거나 저장된 protocol에서 별도 생성하고 경기 구분·턴·승패를 대조한다. 로컬 링크는 폴더
   안의 상대경로로 연결한다. 원자료·기존 뷰어·봉인은 보존한다.
3. 출처·체크섬·정상완료 분모를 기록하고 폴더 이동 후 오프라인 입력·응답·결과 열람을 검증한다.
4. `exports/battle_viewers/index.html` 목록에 추가하고 최종 답변에 해당 실험 뷰어 링크를 제공한다.

실험자용 결정 화면은 **요청 JSON → 응답 JSON → 상태·후보 요약 → 기술 기록** 순서로
구성한다. 요청은 model/state/questions를 한 객체로 보여주고 들여쓰기·구문 강조·복사·다운로드를
제공한다. 선택과 실제 전송·응답 시간·token을 상단에 표시하며 로그 메타데이터를 기본 화면에
나열하지 않는다. 기록 기반 복원 여부와 자동선택의 API 미호출을 명확히 구분한다.
요약은 원문 JSON을 대체하지 않고 후보 확률을 배틀 승률로 해석하지 않는다.

자동 내보내기가 없는 실행기는 보고 단계에서 위 작업을 수행한다. 별도 재실험이나 API 호출은
필요하지 않다. 현재 EX-050은 [경기 목록](../../exports/battle_viewers/ex050/index.html)에서
입력·응답+고정 리플레이 패널 또는 리플레이 단독 화면을 열 수 있다. 애니메이션은 공식
Showdown 자산을 사용하므로 인터넷 연결이 필요하며 경기 로그는 오프라인 fallback으로 제공한다.

## 외부 source 주의사항

`pokechamp/LICENSE`에는 MIT 문구 외에 일본에서의 사용·배포·판매를 금지하는 비표준 문구가
있다. 표준 MIT dependency로 축약하거나 재배포하지 말고 원문을 검토한다. Pinned Showdown
lock을 2026-09-04에 `npm ci`했을 때 audit summary는 31 vulnerabilities(critical 4 포함)를
보고했다. 이 qualification 환경은 loopback-only로 유지하며 `npm audit fix`로 pin을 조용히
변경하지 않는다.

## 기준선 pilot (D-012 / EP-004)

`benchmark`는 5개 방법의 40-slot pilot 전용 경로다. 본 실험은 자동 실행하지 않는다.
기존 `research run`은 고정 IO 관찰용이며 benchmark와 다른 경로다.

```bash
export POKECHAMP_DATA_ROOT=/workspace/.pokechamp-data
scripts/pokechamp-env benchmark plan --experiment-id baseline-pilot-v3
scripts/pokechamp-env benchmark run --experiment-id baseline-pilot-v3
scripts/pokechamp-env benchmark analyze --experiment-id baseline-pilot-v3
scripts/pokechamp-env research rebuild --experiment-id baseline-pilot-v3
```

`baseline-pilot-v3`는 완료된 EX-002의 identity다. 기존 자료는 `analyze`와 `research rebuild`로
재생성한다. 새 실행은 새 experiment ID를 사용해야 하며, 실행 중 source를 바꾸지 않는다.
실행기 수정 후 이전 source의 미완료 실험을 같은 identity로 재개할 수 없다.

`plan`은 network call 없이 팀 분할, seed, 방법, 순서, parent source snapshot을 exclusive-create한다.
`--config`는 승인된 pilot JSON을 입력할 수 있으며 규범 설정과 다르면 거부한다. `run` 전에
기존 server를 종료해야 한다. Runner가 각 경기의 임시 server와 두 actor process를 생성·정리한다.
각 actor는 key가 필요한 경우 자신의 process 안에서만 `.env`를 읽는다.

현재 설정은 `benchmark.DEFAULT_CONFIG`다: seed 20260906, 5개 방법, 대진당 2개 블록,
블록당 팀/진영 교환 2경기. 정상 damage-calculator 분기는 minimax의 일부이며 예외 fallback과
구별한다. Caller AST의 두 고정 call site에 역할을 부착하고 pinned 형태가 바뀌면 거부한다.
행동/출력 오류는 첫 실패부터 terminal이며 이후 wire action 전송을 막는다. 새 공급자 연결 오류는 아래 전송 재시도 소진 후 terminal이다.

데이터 구조:

```text
$POKECHAMP_DATA_ROOT/
  benchmarks/<experiment_id>/
    plan.json + plan.json.sha256
    source/                         # 실행 전 parent source snapshot
    attempts/<slot_id>-a<N>/
      request.json + request.json.sha256
      battle-seed.jsonl             # 실제 simulator 시작 seed
      p1.log / p2.log               # local-only diagnostic output
      p1.result.json / p2.result.json
      result.json + result.json.sha256
    report.json / report.md          # 재생성 가능한 분석
  experiments/<experiment_id>/battles/<slot_id>-a<N>-p1|p2/
    manifest.json / events.jsonl / checksums.sha256
```

양측 관찰 bundle의 `metadata.actor_id`와 control record의 `slot_id`가 연결 기준이다.
`llm_call.request.call_role/target_state`가 실제·모의·상대 예측 상태를 구분한다. Source bundle의
`research_observability`, `efficacy_evidence=false`는 유지하고 pilot 분석 권한은 C-010이 정의한다.
기존 smoke/demo는 포함하지 않는다. Method별 raw reasoning은 agent 입력으로 공유하지 않는다.

이 기준선 pilot의 Resume은 같은 command로 한다. 이미 처리된 성공/비재시도 slot을 건너뛰고 일시 provider 장애만
동일 slot의 새 attempt로 한 번 재시도한다. 불완전한 attempt, source drift, checksum 손상,
auth/model failure는 자동 덮어쓰기·제외 없이 중단한다. 이런 상태에서는 원자료를 보존하고
별도 원인 기록과 새 실험 identity를 사용한다. 승패가 좋은지에 따라 sample 수를 늘리지 않는다.
이 설명은 C-010/C-011의 기존 설정에 한정한다. `retry_transient=0`인 후속 실험에는 적용하지
않으며 [도구 결함 복구 절차](#defect-recovery)가 provider 재시도를 추가하지 않는다.

Report는 예정 slot/처리 slot/attempt/유효 완료 분모와 실패 이유를 함께 표시한다.
IO/minimax 종합 점수는 Abyssal와 OneStep 상대 draw-adjusted score의 동일 가중 평균이다.
Pilot 2개 shared block의 분산은 불안정하다. Main 규모별 자원 추정과 보수적 block 수 계산은
계획 자료이며 정밀도나 작은 개선 검출을 보장하지 않는다. 본 실험 N은 보고서 이후 결정한다.

Peer failure/watchdog에서는 먼저 backend를 terminal로 바꾸고 cancellation marker를 공유한다.
이미 진행 중인 요청의 응답·사용량은 기록하되 다음 호출과 action 전송은 막는다. Server runtime
lock은 서로 다른 experiment ID의 benchmark도 동시에 포트 8000을 점유하지 못하게 한다.

`report.json`/`report.md`는 원 match summary와 별도로 actor 자체 오류·상대 중단, 역할별 호출,
유효 완료 경기의 실제 action fallback, 대진별 자원 추정을 제공한다. 분석 코드 사본
`analysis_source.py`와 SHA256도 보존한다. 과거 summary 분류를 소급 수정하지 않는다.
Worker가 polling 사이에 종료해도 최종 actor 결과의 auth/timeout/output 등의 원인을 다시
합쳐 batch 중단·재시도 여부를 판단한다.


D-013 이후 모든 Cloud 호출은 모델 공식 출력 최대 128K를 사용한다. Upstream의 작은
max_tokens 인자는 출력 예산을 줄이지 않으며, num_ctx를 생략한다. Metadata의
context_window=null/context_window_policy=provider_default는 실제 용량을 측정한 값이 아니다.
기존 EX-002의 512-token 설정·결과는 그대로 보존한다. Timeout과 provider 자체 제한은
남아 있어 응답 완결을 절대 보장하지 않는다.


### 반복 연구: 8판 빠른 점검 / 32판 기본 테스트

D-015에 따라 `--config`로 고정 설정을 선택한다. 옵션을 생략하면 기존 40판 설정과 일정이
유지된다. `--config`는 plan 단계에만 적용되며 run/analyze는 seal된 plan을 읽는다.

```bash
export POKECHAMP_DATA_ROOT=/workspace/.pokechamp-data
scripts/pokechamp-env benchmark plan --experiment-id core-smoke-128k-300s-v1 --config /workspace/integration/pokechamp/configs/core-smoke.json
scripts/pokechamp-env benchmark run --experiment-id core-smoke-128k-300s-v1
scripts/pokechamp-env benchmark analyze --experiment-id core-smoke-128k-300s-v1
```

32판은 새 실험 기록/ID와 `configs/core-repeat.json`을 사용한다. 4개 핵심 대진은
minimax/IO 각각 Abyssal/OneStep 상대다. 8판은 공통 team/seed block 1개, 32판은 4개이며
각 block에서 두 방법을 p1/p2 사이에 교환하므로 방법별 팀과 진영이 함께 바뀐다.
개발 팀·확증 팀 분할, seed 20260906, 무작위 일정, 실패/재시도 규칙은 고정한다.
Random 및 IO–minimax 직접 대진은 40판 전체 점검에서만 실행한다.

128K 출력·300초 요청의 시간은 새 8판으로 먼저 측정한다. `report.json.repeat_budget`과
보고서의 32판 시간 예산은 모든 핵심 예정 slot을 처리한 뒤 대진별 시간을 선형 확장한다.
50% 여유는 운영 가정이며 통계적 상한이 아니다. 경기 watchdog은 20분이며 정리·재시도로
4시간을 넘길 수 있다. 유효 완료율, 출력 오류/timeout, 완료 조건부 성적, 유효 완료 행동의
fallback 분율과 시간·호출량을 함께 해석한다. 32판은 탐색 규모이며 오류 없는 minimax나
작은 승률 차이의 확증 표본이 아니다.

## 모델 동시성과 병렬 benchmark (D-016)

`benchmark plan --experiment-id ID --config PATH --execution-config PATH`는 일정과 실행 설정을
각각 검증하여 같은 plan에 seal한다. `run`에서는 변경할 수 없다. 실행 설정이 없는 과거 plan은
계속 8000 순차 경로다. 새 설정은 `version=1`, `battle_concurrency` (1–10),
`account_request_limit` (1–10), `model_request_limits` (`glm-5.3-flash`만 활성), `evidence`,
`stop_new_work_at` (UTC epoch seconds 또는 null)을 포함한다. `evidence`는 공식 계정 한도와
모델 공식 한도 unknown, 조건별 실측 상한·출처 hash를 분리한다.

`benchmark calibrate --experiment-id ID`는 EX-003 개발 성공 trace의 20개 prompt와 조건,
순서·예산·source를 먼저 seal한 뒤 최대 30분/600회 측정한다. 실패 보충 호출은 없다.
결과는 `POKECHAMP_DATA_ROOT/calibrations/ID/`에 저장된다.

`benchmark study --experiment-id ID`는 D-016 전체 절차를 실행한다. ID에 `-calibration`,
`-sequential8`, `-parallel8`, `-parallel32` suffix를 부여하고 각 단계를 분리한다.
C*>=2, 8판 비교 통과, 대진별 32판 일정 추정×1.5의 남은 시간 적합을 차례로 검사한다.
총 실측 3시간45분에 신규 요청/배틀을 차단하고 실행 중 배틀을 정리한다. 전체 4시간에
마지막 15분의 정리 여유를 포함하며 구현·로컬 테스트는 제외한다.

동일 계정의 다른 Cloud 작업은 측정 중 중지해야 한다. 이 broker는 해당 coordinator에 연결된
actor/worker 요청만 제어한다. 전역 benchmark lock으로 다른 coordinator의 실행을 막는다.
8100–8109의 필요한 포트가 사용 중이면 시작 전 실패한다. 서버는 127.0.0.1에 bind하고
pinned client에는 localhost 주소를 전달한다. Qualification 8000은 유지한다.

보고서는 실제 batch wall time, 겹치는 attempt 자원 시간, 로컬 permit 대기, HTTP 지연,
decision 지연과 실제 client HTTP overlap을 구별한다. Provider 내부 queue/병렬 처리는
추정하지 않는다. C*는 해당 계정·모델·고정 corpus 조건의 운용 관측이며 자동 승계하지 않는다.

구현 보완으로 중단한 study를 새 ID로 명시적으로 이어갈 때는
`benchmark study --experiment-id NEW_ID --calibration-id PREVIOUS_CALIBRATION_ID`를 쓴다.
원래 calibration의 protocol/corpus와 요청 경로 source hash가 같아야 하며, 최초 실측 시계와
정리 기한을 그대로 유지한다. Calibration을 추가 호출하거나 과거 중단 경기의 ID를 재사용하지
않는다. 계정·모델·요청 조건을 바꾼 실행에 운용 상한을 자동 승계하는 기능이 아니다.

## 요약 low/max 독립 진단 (D-028)

아래는 D-028/EX-025의 당시 protocol과 구현 설명이다. EX-025는 전체 무효·미완료이며
이 명령 안내는 재개 승인이 아니다. 새 실험의 [도구 결함 복구 절차](#defect-recovery)와
[실행기 지원 한계](#recovery-runtime-limits)를 확인한다. EX-025에는 소급 적용하지 않는다.

`python -m integration.pokechamp.summary_diagnostics prepare DIR --profile summary-max-v1`은
EX-024 원자료의22경계/역할과 원문 검토한14고정 메모리를 봉인한다. 같은 DIR의 `run`은
manifest에 연결된 검증 receipt 후 low/max 각66회를 독립 제출한다. `report`의 blind.json을
원문과 대조한 review를 `report DIR --review PATH`로 연결한다. 기존 profile은 보존한다.

두 조건은 같은 `compat.DiagnosticClient`를 사용한다. Ollama SDK의 전송·인증·timeout과
응답 parser를 유지하고, SDK0.6 enum에 없는 max만 검증 후 요청 본문에 넣는다. 실제 직렬화
본문과 trace를 검사하며 summary/summary_rollup 외 역할과 기본값은 low다. 동시성10/10,
timeout300초, 재시도0, 최초 제출부터4시간·132호출 상한이다. 모델 오류는 수집하고,
provider/환경/입력/평가/무결성 오류는 전체 중단하며 기존응답을 보존한다.

보고서는 입력별3반복→원배틀별 평균→원배틀 동일 가중으로 집계한다. 고정 이전메모리에서의
탐색적 비교이며 운영 적용·연쇄 오류누적·배틀 효능 자격을 자동 부여하지 않는다. 현재 실행
상태는 [EX-025](../../project_context/research/input-and-memory/experiments/EX-025-summary-max-diagnostic.md)를 따른다.

<a id="provider-judgment-errors"></a>

## 공급자 판단 오류 발생 시 운영 절차

새 실험은 [연구 설계 §11.2](../../project_context/RESEARCH_DESIGN.md#provider-judgment-errors)와
[C-046](../../project_context/CONTRACTS.md#c-046-provider-judgment)을 따른다.

1. 합법 선택을 실행할 수 있으면 그대로 진행한다. 나쁜 전략·설명 오답·확률 합계/반올림·
   선택과 최댓값 불일치·보조 점수 이상은 원문과 진단으로 남기며 전체 중단하지 않는다.
2. 선택 누락·파싱 불가·불법 선택은 등록된 출력 복구만 적용한다. 복구가 없거나 실패하면
   해당 경기만 실패로 기록하고 남은 독립 경기를 계속한다. 임의 재질의·대체 선택은 추가하지 않는다.
3. 입력·관측·실행 후보·전송·무결성 오류와 통신 오류는 별도 기술 규칙으로 처리한다.
   전체 중단에는 공유 영향 또는 승인 상한 등 구체적인 근거와 범위를 남긴다.
4. 실패와 미완료도 분모에 보존한다. 남은 경기의 진행은 승인된 기존 일정 안에서 수행하며
   보충 경기나 재시도 예산을 늘리지 않는다.

예를 들어 합계0.99 또는 선택0.24/다른 후보0.25라는 이유로 경기를 끊지 않는다.
선택이 합법이면 그 선택을 실행하며 확률 재정규화나 최댓값으로의 교체도 하지 않는다.

**지원 범위:** JEV 새 `choice-action-v3`/EX-050는 합법 choice 실행·보조 점수 진단·경기
출력 실패 격리를 구현한다. 검증은 [EP-066](../../project_context/research/model-evaluation/plans/EP-066-jev-judgment-repeat.md)을
따른다. 기존 v1/v2 및 EX-047/048 감사는 당시 기준을 보존한다. 다른 실행기의 지원은 별도 확인한다.

<a id="defect-recovery"></a>

## 테스트·평가 도구 결함 발견 시 운영 절차

[D-029](../../project_context/shared/governance/decisions/D-029-experiment-defect-recovery.md) 채택(2026-09-09) 후
**새로 승인·등록하는 실험부터** 적용한다. 규범 판단은
[RESEARCH_DESIGN §11.1](../../project_context/RESEARCH_DESIGN.md#defect-recovery), 실행·보존 경계는
[C-018](../../project_context/CONTRACTS.md#c-018-recovery)을 따른다.
기존 실험은 당시 전체 중단·재시도·재개 규칙을 유지한다. EX-020~025의 원자료·halt·clock,
무효·미완료 판정 및 EP-011/012/013/015의 `Blocked`를 이 절차로 복구하지 않는다.

1. **발견:** 실패 로그와 발견 단계·시점·결과 확인 여부를 기록하고 당시 source·입력·기준·
   응답·보고서를 보존한다. 새 실험의 모델 판단 오류는 [위 절](#provider-judgment-errors)에 따라
   전체 중단에서 제외한다.
2. **일시 중지:** 결함에 의존하는 단계 진입·신규 수집·분석을 보류한다. 공유 변환·평가 코드·
   메모리를 포함해 잠재 영향 범위를 중지하며 이미 진행 중인 응답은 실행기 규칙 안에서 보존·정리한다.
3. **원인·영향 확인:** 원문과 실제 입력/출력으로 재현하고 아래 표로 분류한다. 비영향 조건을
   유지하려면 source·입력·의존성으로 영향이 없음을 입증한다. 여러 결함은 함께 기록한다.
4. **수정·독립 검증:** 실행 중인 source를 바꾸지 않고 별도 버전에서 교정한다. 원자료·별도
   계산·독립 사례로 검증한다. 수정 구현의 기대값을 복제한 검사만으로 통과시키지 않는다.
   결함 재현 검사와 관련 회귀 검사 통과, 영향 단위 확정 후에만 의존 작업 재개를 판단한다.
5. **필요한 범위 복구·보고:** 등록된 허용 범위·상한·실행기 지원을 확인해 재평가 또는
   재수집한다. 수정 분석/새 실행을 원본과 연결하고 무효·미실행·미확정·대응 누락을 계속 보고한다.

| 결함 유형 | 중지 범위와 기본 복구 |
|---|---|
| 단위 테스트·fixture·경로만 잘못됨 | 의존 단계 진입을 보류하고 수정·재검증한다. 실제 실험에 영향이 없다는 근거가 있으면 결과를 유지한다. |
| 평가 코드가 사전 기준을 잘못 구현함 | 관련 분석을 보류하고 구현 수정 후 모든 영향 조건·응답을 사전 기준으로 동일 재평가한다. 수집이 온전하면 재호출은 하지 않는다. |
| 정답·rubric 자체가 잘못됨 | 관련 분석을 보류하고 원문 근거로 교정한다. 결과 확인 후 기준 변경 사실을 공개하고 모든 영향 조건·응답의 별도 수정 분석으로 보고한다. |
| 실제 입력·처치·수집이 잘못됨 | 영향 실행과 의존 결과를 무효 처리하고 수정된 조건에서 필요한 비교 단위를 재수집한다. 기존 응답 재채점만으로 복구하지 않는다. |
| 영향 불명 또는 증거 무결성 훼손 | 공유 의존성을 포함한 잠재 영향 전체를 중지한다. 범위를 입증할 수 없으면 해당 비교 전체를 중단·무효 처리한다. |

결함 기록에는 발견 단계·재현 원문, 영향받는 입력/조건/결과와 공유 의존성, 비영향 근거,
수정 전후 source·평가 기준의 버전/해시와 사유, 독립 검증·재현/회귀 결과, 재평가/재실행
단위와 원본/수정 identity, 승인·남은 상한을 남기고 개별 plan/experiment에서 연결한다.
사전 요구가 실제 입력에 도달했는지 확인하여 입력 누락을 rubric 완화로 처리하지 않는다.

대응 비교의 필요한 조건 쌍·block은 함께 다룬다. 연쇄 메모리 오류는 검증된 오염 전 경계나
clean state부터 후속 요약·행동·배틀/공유 store까지 포함한다. 좋은 결과만 보존하거나 실패
분모를 삭제하지 않는다. 원자료·봉인·보고서는 유지하고 수정 분석과 새 실행은 별도 버전·
identity로 연결한다. 평가 기준 완화로 기존 실험을 통과시킨 것으로 보고하지 않는다.

새 실험 등록 시 재수집 허용 여부·단위·한도(금지이면 0), 승인·예산·시간·호출 상한과
정리 여유, 별도 전체 중단 규칙의 사유·범위를 명시한다. 같은 승인·상한 안의 허용 복구는
재승인하지 않는다. 수정·검증·재수집에도 최초 시계와 누적 사용량을 유지하며 새 identity로
상한을 초기화하지 않는다. 상한 소진이나 미승인 행동은 보류하고 보존·검증·미완료 보고를
완료한 뒤 필요한 추가 범위만 INDEX 절차로 다룬다. Provider 재시도 정책은 확대하지 않는다.

### 사례별 중지 범위와 복구 조건

아래 1~7은 새로 등록한 실험을 가정한 절차 검토용 예시다. 실제 실험 결과나 재개 승인이 아니다.
모든 복구는 위 검증·승인·상한과 아래 실행기 지원 조건을 함께 충족해야 한다.

| 사례 | 중지·보존 판단 | 복구 조건과 보고 |
|---|---|---|
| 1. 단위 테스트가 잘못된 cwd에서 fixture를 읽어 실패 | 해당 검증에 의존하는 다음 단계 진입 보류. 실패 로그와 실제 수집의 경로·입력 identity 보존 | 경로 수정 후 재현·관련 회귀 통과. 실제 수집 경로가 독립이고 입력/평가에 영향 없음을 확인하면 기존 결과 유지 |
| 2. 평가 코드가 사전 rubric의 누락 수를 잘못 집계 | 해당 코드에 의존한 모든 조건 분석·claim 보류. 원응답과 기존 보고서 보존 | 원문 수기 집계 또는 별도 계산으로 검증하고 모든 영향 응답을 같은 사전 기준으로 재평가. 수정 보고서를 별도 버전으로 연결 |
| 3. rubric의 사건 턴 정답이 원문과 다름 | 관련 분석 보류. 원문 행·실제 입력 도달성·기존 기준과 결과 확인 시점 보존 | 원문으로 정답 교정·독립 검증 후 모든 영향 조건을 같은 기준으로 수정 분석. 결과 확인 후 변경임을 공개하고 기존 평가와 구분 |
| 4. 공개 특성이 실제 모델 입력에서 누락 | 영향 입력의 실행·의존 분석 중지 및 무효. 다른 조건도 같은 변환을 쓰는지 조사 | 변환 수정·독립 원문 대조·회귀 후 필요한 대응 조건 쌍/block을 새 identity로 재수집. 누락을 허용하는 재채점으로 대체하지 않음 |
| 5. 도구의 메모리 병합 오류가 이후 요약·행동으로 전파 | 최초 오염 이후 의존 결과와 공유 store까지 중지·무효. 마지막 응답만 교체하지 않음 | 검증된 오염 전 경계/clean state에서 필요한 연쇄와 대응 비교 단위를 재수집. 실패·무효·후속 미실행 분모 보존 |
| 6. source seal 손상으로 적용된 변환 버전을 모름 | 공유 source의 잠재 영향 비교 전체 중지. 남은 원자료와 손상 증거 보존 | 원자료로 경계를 입증할 수 없으면 해당 비교 전체 중단·무효. 온전한 표본만 임의 선택하지 않음 |
| 7. 교정은 검증됐으나 재수집 호출 한도 또는 신규 제출 시간이 소진 | 추가 수집 보류. 수정·검증 evidence와 누적 비용·미완료 보존 | 같은 승인에서는 재수집하지 않음. 새 ID로 시계/한도 초기화 금지. 추가 범위가 필요하면 구체적인 단위·비용을 기록해 별도 승인 대상으로 제시 |
| 8. 기존 EX-025의 입력·평가 불일치를 지금 발견·재검토 | D-028/C-017의 당시 전체 무효·halt, 132응답·무효 초안126·미검토6과 EP-015 Blocked 보존 | D-029 소급 적용 불가. 기존 실험을 재채점하여 통과시키거나 halt 삭제로 재개하지 않음. 새 실험은 별도 승인·등록 필요 |

<a id="recovery-runtime-limits"></a>

### 현재 실행기의 지원 한계

D-029 채택 당시 변경은 문서·상위 규정에 한정했다. 이후 D-030/D-032의 전용 A/B 복구 경로는
아래 새 정책 절과 C-019/C-020을 따르며 기존 경로의 제한은 유지한다.
공통 절차를 채택했다고 아래 도구가 선택적 복구를 지원하는 것은 아니다.

| 경로 | 현재 동작과 제한 |
|---|---|
| 요약 진단 `run` | halt가 있는 디렉터리는 제출 거부. 수집 봉인 후 재실행·대체 호출도 거부한다. 기존 시계가 있는 coordinator 재시작은 보존·종료하며 재수집하지 않는다. |
| 요약 진단 `report --review` | 입력/평가 오류로 무효화된 비교를 정상 비교로 복구하지 않는다. 기존 EX-021/022/025의 수정 rubric 분석을 같은 report 경로로 실행하는 기능이 아니다. |
| improved IO 단계/검토 gate | 영속 연구 halt와 source/선행 receipt 검증을 유지한다. D-027의 미검토 응답 검토 대기 후 진행 및 허용 버전 전환은 당시 최대3조합·동일 시계·gate 범위에 한정한다. EX-024는 한도 소진으로 중단됐다. |
| 새 실험의 선택적 재수집·별도 수정 분석 | 현재 실행기에 공통 복구 기능으로 구현되지 않았다. 등록 시 지원 여부를 확인하고 필요한 구현은 승인된 별도 bounded plan에서 검증해야 한다. |

halt 삭제, 기존 입력·기준·receipt·보고서 덮어쓰기, 다른 디렉터리에서 시계를 새로 만드는
방법은 복구 절차가 아니다. 연구 절차상 허용되어도 도구가 거부하는 경로는 의존 실행을 보류하고
지원 부재를 기록한다. 도구 구현과 새 실험 승인은 별도 판단이며 문서화 완료로 대신하지 않는다.
실행 근거: [진단 runner](summary_diagnostics/runner.py), [진단 report](summary_diagnostics/report.py),
[low/max report](summary_diagnostics/maximum_report.py), [IO receipt](improved_io/receipts.py),
[IO 검토 gate](improved_io/review_gate.py). Improved IO 사용법은 [별도 안내](improved_io/README.md)를 따른다.


## 필드 설명서 실제 Cloud 정책 (D-032 / EP-020 / EX-027)

사용자 승인된 새 연구만 `battle-guide-live-v1`을 prepare에서 선택한다. 정책 이름·정의/hash와
명시적 null 요청/시간 상한을 manifest·study·execution evidence·receipt·원장·보고서에 봉인한다.
정책 부재의 과거 자료에는 D-030의4000요청/4시간·엄격한 의미 gate를 적용한다.
설명 사실/진영/시점/계산 오류는 전수 검토·측정하며 기술 gate 통과를 막지 않는다.
출력/합법행동/입력·증거무결성/검토 누락은 계속 차단한다. 의미 오류가 있으면
semantic_review=failed이며 passed는 배틀 진입 기준에 관한 별도 값이다.

```bash
export PYTHONPATH=/workspace
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_MAX_THREADS=1
export TOKENIZERS_PARALLELISM=false
pokechamp/.venv/bin/python -m integration.pokechamp.improved_io.battle_only prepare \
  --experiment-policy battle-guide-live-v1 \
  --output .pokechamp-data/battle-guide-live/ex027-preflight/prepare
```

같은 CLI의 register → fake32 → collect → review → smoke8 → compare32 → report 순서다.
register에는 `--prepared .../prepare/result.json --study-root .../ex027`, fake32에는
`--prepared`와 `--previous .../prepare/result.json`, collect에는 `--previous .../fake32/result.json`,
smoke8에는 `--previous .../gate/result.json`, compare32에는 `--previous .../smoke8/result.json`을
사용한다. 각 단계 `--output`은 새 디렉터리다. review만 수집 디렉터리를 `--output`으로 받고
원문·입력·계산 근거의 봉인 JSON을 `--review`로 연결한다. 정책을 후속 명령에서 바꾸지 못한다.

Cloud90 기술 gate·검토완전성 → 동시smoke8 유효8/8 → 병렬compare32가 순서다.
smoke 기반32판 추정과50% 여유는 보고용이며 전체 경과 시간으로 진입을 막지 않는다.
요청300초/경기1200초 watchdog, 배틀·계정·모델최대10, provider retry0은 유지한다.
Cloud 기술 실패는 후속 배틀을 막고 배틀 출력/provider/환경/watchdog은 신규 배틀 제출을
중지한다. 합법 완료 설명 오류로 승패를 제외하지 않는다.

복구는 D-029/C-018 및 C-020을 따른다. 별도 봉인 defect·원본/수정source·독립재현·회귀·
영향 양쪽 A/B/공유영향 집합을 연결하는 recover 경로만 사용한다. 유료 재수집1차와
누적 gate180/smoke16/compare64는 유지하며 전체 행동 요청 상한과 구별한다.
최초시계·누적요청·실패/미확정·token·halt는 삭제/초기화하지 않는다. 평가 구현 교정은
온전 응답 대칭 재평가 및 미제출 ID만 e1로 연결하고, rubric 교정은 공개된 별도 수정 분석이다.
이 정책은 EX-026 재개나 기존 Blocked의 소급 변경을 허용하지 않는다.

## D-033 사전 gate 생략 direct32

`battle-guide-direct32-v1`은 EX-028에만 명시 선택한다. 준비는 source·설정·대진·prompt를
봉인하고 사전 회귀/15장면/fake32/Cloud90/smoke8은 `skipped_by_user`다. 검증 통과를
위조하지 않으며 `compare32`만 32 slot 각1회 실행한다. Provider retry와 재수집0,
전체 시간/요청/비용 상한 없음, 요청300초·경기1200초·배틀/계정/모델 최대10이다.

```bash
PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m integration.pokechamp.improved_io.battle_only prepare --experiment-policy battle-guide-direct32-v1 --output .pokechamp-data/battle-guide-direct32/ex028-prepared
PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m integration.pokechamp.improved_io.battle_only register --prepared .pokechamp-data/battle-guide-direct32/ex028-prepared/result.json --study-root .pokechamp-data/battle-guide-direct32/ex028
PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m integration.pokechamp.improved_io.battle_only compare32 --prepared .pokechamp-data/battle-guide-direct32/ex028-prepared/result.json --study-root .pokechamp-data/battle-guide-direct32/ex028 --output .pokechamp-data/battle-guide-direct32/ex028/compare32
```

B는 엄격한 원출력 판정 후 유일한 합법 JSON 추출 또는 첫 합법 후보를 사용한다.
원출력 오류는 계속 실패로 기록하고 선택 출처·추출 행동·실행할 행동을 별도로 남긴다.
경기별 provider/timeout/watchdog/환경 실패는 다음 slot을 막지 않으며 공유 입력/계산·설정·
무결성 결함은 영향 범위를 중지한다. 수집 중 source/prompt 수정이나 실패 경기 보충은 금지한다.

`report`는 별도 봉인 전수 검토를 `--review`로 받는다. annotation은 actor source 밖의
`experiments/<id>/annotations/`에 events hash·battle/actor/event identity로 연결하며 원자료를
수정하지 않는다. `matches.html`은 32 slot의 완료/실패/미실행·문제 턴과 actor viewer를 연결한다.
사후 tests와 원문 검토를 마치고 32 slot 처리와 32 자연 종료를 별도로 보고한다.

## D-034 계산기 교정 동일32판

`battle-guide-calcfix32-v1`은 EX-029 전용이다. `prepare --verification <봉인 검증 JSON>`은
결함재현·독립 Showdown16난수·worker불변성·EX-028 B435재계산·전체회귀·정적/Node/source/설정
검증이 현재 source와 일치해야 성공한다. 검증자료와 EX-028 manifest/최초시계/원장/보고서를
참조하며 기존 팀원문·32 slot순서·진영·게임/actor seed·prompt/prior/config를 대조한다.
Cloud90/smoke8/fake32/기존15장면은 생략하고 검증봉인 후 곧바로 compare32를 실행한다.
기존 direct32 정책 identity와 재수집금지0은 보존한다. 새 실행도32 slot각1회/추가재수집0이다.
실패격리·출력복구는 D-033과 같고 source/prompt는 수집 중 고정한다. 보고서는 EX-029로 표시하고
원본 미확정 요청과 누적사용량을 연결하며 전후 성적을 독립 표본으로 합산하지 않는다.


### 교정 입력 동일32판 정책 (D-036)

`battle-guide-inputfix32-v1`은 새 `calculator-input-audit-independent-regression-v1` 검증 receipt를
`--verification`으로 요구한다. `prepare --battle-prompt-version v1.2.0`에서 EX-028 대진·seed·팀 원문을
대조하고 v2 의미·mechanics-v2 identity를 준비/실행/actor/요청에 봉인한다. 과거 정책의 버전·hash는 보존한다.
EX-030 독립 검증·636입력 재생과 새 정책 전달·전체회귀·정적 검증 evidence를 확인한 뒤 register/compare32를
각1회 실행한다. 별도 fake32/Cloud90/smoke8의 통과 receipt는 만들지 않는다.
기존 EX-028/029 원장·미확정1건은 각각 한 번만 누적하며 기존 중단을 해제하지 않는다.
출력 복구/실패격리/재수집0과 전체 상한 없음은 D-033의 직접32판 동작을 따른다.

## EX-037 Protect 수정본 직접32

D-044의 명시적 승인에 따른 새 정책 `ab-head-to-head32-protectfix-v1`이다.
`ab-head-to-head prepare --policy ab-head-to-head32-protectfix-v1 --directory .pokechamp-data/ab-head-to-head32/ex037`
후 `run --directory ... --data-root .pokechamp-data`를 사용한다.
`run/report`는 봉인 plan 정책을 따른다. 이 정책은 qualification 인자를 소비하지 않고
로컬 회귀·Protect 재생·fake32·Cloud gate·smoke·첫10 gate를 `skipped_by_user`로 보존한다.
최대10에서 빈 자리를 즉시 채우며 실행중 입력/계산 거부·원장/시계·공유결함 중단은 유지한다.
기존 정책의 prepare 기본값·qualification·첫10 gate는 유지한다. EX-036 schedule과 팀을 그대로 복사하고
새 ex037-cloud identity/원장/시계/study link/run claim과 이전 EX-036 사용량을 연결한다.
시작 전 검사 통과를 주장하지 않으며 EP-031 source와 새 실행 연결 source는 따로 봉인한다.
종료후 전체 무결성·양측 판단 검토와 보고·보존·정리가 필요하다.


## B0–B3 프롬프트 오프라인 최적화

D-046/C-030의 `improved_io.delivery`는 전체 원본 검증 후 별도 전달 표현을 생성한다.
운영 기본 프롬프트/계산 의미/출력복구는 유지하며 후보를 실제 배틀에 연결하지 않는다.
[명령·검증 경계·필드 매핑·비교 결과](../../docs/pokechamp-b-prompt-optimization.md)를 따른다.
`generate`와 `audit-ex037`는 모델 호출 없이 새 출력 디렉터리만 만든다.


### EX-038 B2 직접대결

D-047/EP-035의 `ab-head-to-head32-b2-v1`은 EP-034 B2 표현을 실제 B 요청에 연결한다.
원본 전체 입력은 검증·출력복구 및 `input_snapshot` trace에 보존하고 실제 B2 system/user와
`delivery_identity`·`input_snapshot_event_seq`를 연결한다. 기존 정책과 운영 기본값은 유지한다.
EX-037 팀/32행을 복사하며 기본 동시성8, 동일 8000요청/수집20700초/정리21600초, 재수집0이다.
현재 source의 `local_passed`·`wire_passed`가 참인 봉인 code receipt를 `run --verification`에 제공한다.
fake32/Cloud gate/smoke/첫10 gate는 사용자 지시로 생략하고 연속 실행한다.

```bash
python -m integration.pokechamp.ab_head_to_head prepare --directory /workspace/.pokechamp-data/ab-head-to-head32/ex038 --policy ab-head-to-head32-b2-v1 --concurrency 8
python -m integration.pokechamp.ab_head_to_head run --directory /workspace/.pokechamp-data/ab-head-to-head32/ex038 --data-root /workspace/.pokechamp-data --verification /workspace/project_context/exec-plans/evidence/ep035/code-verification.json
```


<a id="llm-lead"></a>

## B2 LLM 선봉 선택

[C-033](../../project_context/research/lead-policy/CONTRACTS.md#c-033-llm-lead)의 `b2-llm-lead-v1`에서 actor별
`team_preview_policy`를 `seeded_random` 또는 `llm_lead`로 선택한다. 생략 시 기존 무작위 선발을 그대로 사용한다.
예를 들어 동일 B2의 두 actor를 비교하는 slot은 다음 설정을 가진다.

```json
{
  "methods": ["io", "io"],
  "actor_conditions": ["B", "B"],
  "actor_settings": [
    {"team_preview_policy": "seeded_random"},
    {"team_preview_policy": "llm_lead"}
  ]
}
```

새 선봉 설정을 EX-038 정책에 넣으면 거부한다. 새 정책은 과거 정책 hash를 유지하면서 B2 전달을 별도로 허용한다.
전투 중 관측·압축·계산·출력복구는 같다. glm-5.3-flash/low/temperature0/model seed100/출력131072/
provider 기본 context/timeout300을 현재 B2에서 상속한다.

다음 명령은 credential을 읽거나 모델에 접속하지 않는다. 새 경로를 지정한다.

```bash
cd /workspace/pokechamp
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.team_preview_study prepare --directory /tmp/b2-lead-prepared
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.team_preview_study verify --directory /tmp/b2-lead-prepared
PYTHONPATH=/workspace .venv/bin/python -m pytest /workspace/integration/pokechamp/tests/test_team_preview.py -q
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.diagnostics.team_preview --output /tmp/b2-lead-local
```

`prepare --transport cloud`도 설정만 봉인하며 호출0이다. 준비는 팀4종·대응 일정32행·source·B2/선봉 prompt hash·
모델/동시성 및 미승인 요청/시간 제안을 포함한다. 준비 파일의 `execution_authorized=false`는 준비 시점에
유료 실행을 승인하지 않았다는 뜻이다. 기존 폴더는 덮어쓰지 않는다.
로컬 진단은 fake backend만 사용하는2대응 경기/4 actor를 실제 loopback Showdown과 실행하며,
원장/실제전송/최초 출전/전투 B2 입력/viewer를 검사한다. fake의 슬롯3은 검증 응답이고 전략 정책이 아니다.
외부 모델을 사용하는 `run` 명령은 이 준비 CLI에 없다.

실제 수집을 승인한 후에는 `team_preview_study.register_execution(prepared_root, approval_record=...)`로
등록된 EX/승인 근거 파일을 최종 source·모델·선봉 prompt·8000요청/20700초 수집/21600초 정리 상한에 연결한다.
이 API는 **명시적 실험 승인과 예산 결정 후에만** 호출하며 prepare/verify는 호출하지 않는다.
승인 문서는 provenance이고 API가 사용자 승인을 인증하거나 자동 부여하지 않는다.
전역 study binding과 별도 execution-registration seal로 동일 준비의 새 폴더/시계 초기화를 거부한다.
등록 후 기존 `benchmark.run_attempt`와 actor 생성·Cloud backend가 같은 source에서 동작하며 별도 선봉 모델은 필요 없다.
`POKECHAMP_LEAD_STUDY_ROOT`의 양쪽 actor 요청은 같은 원자 예약 원장에 들어간다.
후속 표본·단계·가격/금액 상한·실제 coordinator 실행·완료 분모는
[EX-039](../../project_context/research/lead-policy/experiments/EX-039-b2-lead-proposal.md)와 D-053/EP-041이 규정한다.
D-053은 실제32경기 수집을 승인했고 후속 사용자 지시로 금액 상한을 제외했다. 실행 상태는 STATUS/EP-041을 참조한다.

기술 경계:

- Gen9 OU singles 6마리만 지원한다. 모델은 선봉 하나를 고르고 팀/세트/나머지 순서를 생성하지 않는다.
- 공개 preview와 첫 자기 preview request가 모두 도착한 시점에만 호출한다. 이 두 신호는 어느 순서나 같은 packet으로
  도착할 수 있다. 상대 입력은 공개 `poke` details뿐이며 미공개 기술/도구/특성/능력치/테라·원팀 파일·미래 결과를 쓰지 않는다.
  자기 기술·도구·특성·실제 능력치·HP/테라는 제출 세트/자기 request에 알려진 값만 담는다. 누락은 추정으로 채우지 않는다.
- upstream 초기 avatar 선택이 Python RNG를 먼저 소비한다. 선봉은 기존 preview 시점에 같은 shuffle을 정확히 한 번 호출하고
  선택 슬롯만 앞으로 옮긴다. 후보 ID/제출 순서/request details·기술을 대조하며 모호하거나 달라지면 실패한다.
- 단일 `{"lead_slot": 정수}`만 허용하며 bool·실수·이름·추가/중복 키·여분 텍스트·후보 밖 값을 거부한다.
  실패/timeout/취소/전송 실패에 fallback·재질의·대체 모델·재전송은 없다. 같은 경기의 중복 preview는 최초 task/결과를 재사용한다.
- 동기 Cloud를 별도 thread에서 실행하고 parent async 경계가 완료를 기다린 뒤 전송한다.
  취소 시 전송을 막고 진행 HTTP의 원응답 보존·permit 반환을 기다린다. provider timeout은 기존300초 경계를 그대로 사용하며
  강제 process kill 이후 응답 복원을 보장하지 않는다. 기존 EX-032의 broker ACK 한계는 이 작업에서 수정하지 않았다.
- manifest의 선봉 정책/결과와 trace의 `call_role=team_preview`, 입력/버전/hash·원응답/reasoning·검증·`wire_action`을 연결한다.
  viewer의 준비 탭에서 확인한다. 설명 오류 사후 annotation은 C-032 기본 제외이며 설명 정확성·전략적 개선·provider 성능은 미평가다.

### EX-039 실행·보고 (D-053)

`team_preview_run`은 같은 C-033 worker/backend와 공통 원장을 사용한다. 최초 제출 슬롯의
대응쌍 전체2경기를 먼저 실행하고 양쪽 유효 종료·정보 경계·엄격 선봉 출력·실제 팀/선봉 전송·최초 출전·
B2 입력/합법 행동·원장/trace/viewer·permit 반환을 검사한다. 승패·전략·설명 정확성은 gate가 아니다.
통과한 경우 같은 source·원장·최초 시계로 남은30을 원래 상대 순서로 제출한다. 추가 유료 smoke0이다.
8000예약(양쪽 선봉/전투/실패/미확정 포함), 최초 요청부터 수집20700초/정리21600초, 동시성8,
경기 watchdog3600초, HTTP min(300초,남은 수집시간), 재시도·보충·재수집0을 유지한다.

최종 source에 대한 `source_files`, `local_passed`, `wire_passed`, `execution_protocol`,
검증 원자료 `evidence`(path/sha256)를 담은 봉인 receipt가 필요하다. prepare는 승인하지 않으며,
별도 등록이 승인 근거 hash·D-053 실행 protocol을 전역 binding에 묶는다. run-claim/dispatch는 배타적으로
생성되어 재실행·중복 슬롯을 거부한다. 요청 원장도 같은 actor의 선봉 재호출/같은 전투 결정 중복 예약을 거부한다.

```bash
cd /workspace/pokechamp
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.team_preview_run run --directory /workspace/.pokechamp-data/b2-lead/ex039 --data-root /workspace/.pokechamp-data --verification /workspace/project_context/exec-plans/evidence/ep041/entry-verification.json
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.team_preview_run report --directory /workspace/.pokechamp-data/b2-lead/ex039
```

report는 원자료를 바꾸지 않는 새 파생 보고서를 만든다. 조건별/팀 block·실제 진영별 승/무/패·점수,
완료쌍 동일가중 점수와 누락 사유, 모든 경기·선봉 분모, 선봉/전투별 사용량·지연·오류·기술 연결을 보존한다.
지연 p95는 nearest rank다. 실제 청구액/캐시별 사용량이 API에 없으면 확정 비용은 미확정이며
공식 token 단가 구간은 수신 token만의 추정이다. C-032 설명 annotation0·설명 정확성/전략적 최적성 미평가다.


## EX-040 Z.ai 선봉 정책 비교

[EX-040](../../project_context/research/lead-policy/experiments/EX-040-b2-lead-zai.md)의 명시적 승인 범위에서만 실행한다.
`python -m integration.pokechamp.team_preview_study prepare --experiment-id EX-040 --transport cloud --directory .pokechamp-data/b2-lead/ex040-zai`로 준비한다.
로컬 검증 receipt와 승인 기록을 등록한 뒤 `team_preview_run run --directory ... --data-root .pokechamp-data --verification ...`을 사용한다.
실험 식별자에서 protocol과 영속 binding을 선택한다. 기존 EX-039 기본값·binding은 보존한다.
첫429는 응답 hook에서 halt를 영속 기록하며 요청 예약/HTTP admission과 경기 제출을 차단한다.
시계 binding·원장·halt 삭제, 폴더 이동 및 재등록으로 수집을 재개하지 않는다.
`--transport fake --experiment-id EX-040`은 테스트 전용 Z.ai MockTransport와 실제 로컬 actor/Showdown을 사용하며 유료 요청·효능 분모0이다.

## EX-041 Z.ai 동시성4 선봉 정책 재실험

[EP-045](../../project_context/research/lead-policy/plans/EP-045-zai-concurrency4.md)와
[EX-041](../../project_context/research/lead-policy/experiments/EX-041-b2-lead-zai4.md)을 따른다.
`team_preview_study prepare --experiment-id EX-041`은 별도 ex041-zai identity/binding을 사용하며
동시성4만 허용한다. 첫429 영속 중단·최초 시계·원장·source 보존은 실험 protocol을 선택해 적용한다.
EX-039/040의 중단·binding을 삭제하거나 재등록하여 이어 실행하지 않는다.

## 배틀·선봉 상세 효과 사전 (D-057)

새 일반 B 준비는 battle-v1.3.0, EX 미지정 새 선봉 준비는 b2-effects-v1/선봉 v1.1.0을
명시 봉인한다. `effect_reference.items/abilities/moves`는 요청에 등장한 항목의 고정 Gen9 Dex
상세 설명이며 항목당 한 번만 제공한다. 구조 설명·원본 보존·전송 직전 검증·버전/라이선스는
[effects/README.md](effects/README.md), 검증·전후 예시는
[EP-046](../../project_context/exec-plans/evidence/ep046/report.md)을 따른다.

```bash
cd /workspace/pokechamp
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.team_preview_study prepare \
  --directory /path/to/new-prepare --transport fake
PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.team_preview_study verify \
  --directory /path/to/new-prepare
```

`--experiment-id EX-039/040/041`은 각 과거 버전을 유지한다. EX 미지정 준비의 등록 EX와 유료
예산은 없으며 과거 실행 등록·시계·예산을 상속하지 않는다. 로컬 통과는 승률 개선 검증이 아니다.

<a id="transport-retry"></a>

## 새 응답 대기·공급자 오류 재시도

[D-060](../../project_context/shared/execution/decisions/D-060-provider-retry-viewer.md) 이후 새 준비·직접 호출은
[C-038](../../project_context/shared/execution/CONTRACTS.md#c-038-transport-retry)의 provider-retry-v2를 기본 봉인한다.
읽기600초·연결/쓰기/pool300초다. 연결 오류·네 단계 timeout·HTTP5xx·429에
1초/2초/4초 대기 후 최대3재시도(총4시도)를 적용한다. Retry-After는 기록만 하고 고정 대기를 바꾸지 않는다.
첫429에서는 재시도하며 최종 실패429에서 전체 신규 수집을 중단한다. 기타4xx·출력·계산·설정·무결성 오류는 제외한다.
각 시도는 같은 입력/옵션·별도 예약/permit을 사용하고 취소·halt·누적 상한·기한을 확인한다.
대기 중 permit을 반환하고 취소는50ms 간격 이하로 확인한다. 새 permit·worker 정리는
한 진행 시도의 네 timeout 단계 합1500초를 허용한다. 취소 후 새 재시도는 없다.
보고/viewer의 논리 요청 최종 결과와 HTTP 시도 수를 따로 읽는다. attempt 원자료와
retry 후속 기록은 요청 원장에 연결되고 상세/원인 메시지는 credential을 제거한다.
과거 legacy 봉인은300초/retry0, connect-retry-v1 및 EX-042는 연결 오류만1/3초·2재시도와 첫429 중단을 유지한다.
도구 결함 복구는 이 재시도를 추가 확대하지 않는다. 기존 중단 실험을 재개하지 않는다.

무외부호출 검증: `PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.diagnostics.transport_retry --output <새 경로>`
(pokechamp 디렉터리에서 실행). 각 공급자 SDK에 MockTransport를 주입하고 로컬 Showdown1경기씩 검증한다.

## EX-042 공급자4+4 실행

`team_preview_study prepare --experiment-id EX-042 --transport fake|cloud --directory <새경로>`는 공급자별 설정과 대응쌍 배정을 봉인한다. `verify`, `register_execution`, `team_preview_run run/report`의 기존 경로를 사용한다. 조건은 [EX-042](../../project_context/research/lead-policy/experiments/EX-042-distributed-lead.md), 계약은 [C-039](../../project_context/research/lead-policy/CONTRACTS.md#c-039-distributed-lead)다.
최종 source의 fake32와 공급자별 로컬 대응2경기 검증 receipt·승인 기록을 등록한 뒤만 실제 수집한다. 첫 네 경기 gate가 후속28 진입을 제어한다. 호출 상한 없음·최초예약20100초 신규 중단/21600초 정리·첫429 전체 halt·보충/재수집/재개0이다. 중단·원자료를 삭제하거나 폴더를 바꿔 시계를 초기화할 수 없다.

## 정상 완료 경기 목록

봉인된 선봉 보고서에서 정상 완료 경기만 골라 기존 양쪽 viewer/replay를 연결한다.
기존 원자료·viewer·보고서는 재생성하지 않으며 새 출력 경로만 허용한다.

```bash
PYTHONPATH=/workspace pokechamp/.venv/bin/python -m integration.pokechamp.team_preview_run viewer --report-directory <봉인 보고서 디렉터리> --output <새 index.html>
```

EX-042 목록: [.pokechamp-data/experiments/ex042-cloud/index.html](../../.pokechamp-data/experiments/ex042-cloud/index.html).
정상26경기·52 actor 관점이며 전체 비교 미완료 및 짝 경기 미완료를 표시한다. 설명 오류 사후 annotation은 추가하지 않는다.

### 선봉 전략·규칙 독립 선택 (D-061)

새 EX 미지정 준비는 `--lead-strategy matchup-v2 --lead-rules dex-v2`가 기본값이다.
각각 `legacy-v1`, `effects-v1`을 선택할 수 있으며 네 조합을 준비/검증/오프라인 재생한다.
`legacy-v1/effects-v1`은 기존 v1.1 선봉 system/user 문자열을 그대로 만든다.
전략만 바꾸면 user가 같고, 규칙만 바꾸면 전략은 같으며 규칙 데이터/필드 설명만 추가된다.

```bash
PYTHONPATH=/workspace:/workspace/pokechamp /workspace/pokechamp/.venv/bin/python -m integration.pokechamp.team_preview_study prepare --directory /tmp/lead-comparison --lead-strategy matchup-v2 --lead-rules dex-v2
PYTHONPATH=/workspace:/workspace/pokechamp /workspace/pokechamp/.venv/bin/python -m integration.pokechamp.team_preview_study verify --directory /tmp/lead-comparison
PYTHONPATH=/workspace:/workspace/pokechamp /workspace/pokechamp/.venv/bin/python -m integration.pokechamp.diagnostics.lead_components --output /tmp/lead-offline-replay
```

과거 옵션 없는 준비는 당시 봉인 identity를 사용한다. 과거 EX 지정 준비에 새 옵션을 혼합하면 거부한다.
새 준비는 과거 실행 승인·예산을 승계하지 않는다. [C-040](../../project_context/research/lead-policy/CONTRACTS.md#c-040-lead-components),
[자산 설명](lead_rules/README.md), [EP-050 검증](../../project_context/exec-plans/evidence/ep050/report.md)을 참조한다.

## EX-043 교정 선봉 비교

`team_preview_study prepare --experiment-id EX-043`은 별도 namespace 일정·matchup-v2/dex-v2·provider-retry-v2를 봉인한다. 기존 등록/실행 CLI를 사용하며 EX-043 승인·사전 검증 receipt가 필요하다. 종료 경기의 공개 입력 감사 실패는 전체 신규 수집을 중단한다. 과거 EX-039–042 봉인/중단과 결과를 보존한다. 조건·한도·분모 원문은 [EX-043](../../project_context/research/lead-policy/experiments/EX-043-corrected-lead.md)다.

## EX-045 공식 관측 선봉 비교

[D-067/EX-045](../../project_context/research/lead-policy/experiments/EX-045-official-lead.md)는 공식 관측을 공통 입력으로
새 identity에서 선봉 정책을 비교한다. `team_preview_study prepare --experiment-id EX-045`는
공급자별 official-client-v1/빌드·v1.4.0/b2-official-v1·최신 선봉 및 전송 설정을 봉인한다.
기존 EX 지정은 legacy 관측/당시 감사 버전을 유지한다.
`diagnostics.official_cutoff`의 official-cutoff-v1 감사는 actor 행 경계·공식 재생·정규화·계산·
실제 문자열/원장/숫자 슬롯을 연결하고 공개 원문과 자기 request를 독립 검사한다.
요청 전 취소·전송 후 미수신·응답 수신 및 관측/snapshot 부재 사유를 남긴다.

무유료 사전4경기는 pokechamp cwd에서
`PYTHONPATH=/workspace .venv/bin/python -m integration.pokechamp.diagnostics.official_lead --output <새경로>`로
실행한다. 실제 coordinator/worker/계산기·결정적 모의 HTTP, 경기당600초·각1시도이며 실패 시
원자료를 보존하고 유료 진입을 차단한다. 자동 재경기하지 않는다. 전체32행 일정의 공급자별
첫 대응쌍만 실행하며 이 결과의28미실행은 로컬 분모 밖이다.
본실험은 통과한 검증 receipt와 source/승인 봉인·별도 등록 후 기존 `team_preview_run run`을 사용한다.
첫4 gate·매 경기 감사·20100/21600초·공유 중단·재수집0은 EX-045를 따른다.

## JEV 독립 호출 환경

JEV는 TypeSafe의 상태·질문 기반 API다. 배틀 공급자 설정과 독립적으로 사용한다.
루트 `.env`에 아래 항목을 설정하고 권한 `0600`을 유지한다. 실제 키는 이 파일에만 저장하고
Git에 추가하지 않는다. 프로세스 환경이 `.env`보다 우선하며 명시적 빈 값도 우선한다.

```dotenv
TYPESAFE_API_KEY=
TYPESAFE_BASE_URL=https://api.typesafe.ai/v1
TYPESAFE_MODEL=jev-latest
```

주소는 `/systemone` 앞까지의 HTTPS API base다. 기본 모델 alias는 공급자 업데이트에 따라
변할 수 있으며 고정 모델이 필요하면 `TYPESAFE_MODEL`에 모델 ID를 지정한다.
[공식 API](https://docs.typesafe.ai/api)의 Choice·Score·Noul 질문 사전을 그대로 사용한다.
기존 `httpx`를 사용하므로 추가 SDK 설치는 필요 없다.

아래 예제는 저장소 루트에서 실행한다. 실행하면 실제 API 요청 1건이 발생한다.

```bash
PYTHONPATH="$PWD:$PWD/pokechamp" pokechamp/.venv/bin/python - <<'PY'
from integration.pokechamp.jev import JevClient

with JevClient.from_env() as client:
    result = client.evaluate(
        state="서비스 연결이 실패합니다. 긴급한 도움이 필요합니다.",
        questions={
            "urgent": {
                "type": "noul",
                "instructions": "긴급한 도움을 요청하고 있는가?",
            }
        },
    )
    print(result["answers"])
    print(result["model"], result["usage"])
PY
```

`from_env()`는 설정만 읽고 네트워크 요청을 보내지 않는다. `evaluate()`가 호출을 수행하며
원본 JSON 응답의 model/answers/usage와 추가 필드를 보존한다. 응답의 기본 구조와 질문
ID/유형을 검사하고, 개별 확률의 활용·행동 선택은 호출자 코드에서 결정한다.
기본 timeout은60초이며 `from_env(timeout=...)`로 변경할 수 있다. 새 provider 재시도는 D-084의 최대3회이며 redirect는
없다. 실패는 `JevRequestError.category` 및 `status_code`로 구분한다.
context manager 또는 `close()`로 연결을 정리한다.

독립 클라이언트 준비 단계는 모의 HTTP로 검증했다. 이후 EX-047에서 실제17호출·16행동 전송을 확인했으며 확률합 검증으로 첫 경기를 중단했다.
`POKECHAMP_PROVIDER=jev`는 지원하지 않는다. 배틀에는 아래 별도 JEV Choice 경로와 C-045 계약을 사용한다.
계약은 [C-044](../../project_context/shared/execution/CONTRACTS.md#c-044-jev),
검증은 [EP-061](../../project_context/shared/execution/plans/EP-061-jev-client.md)을 참조한다.

## JEV Choice 배틀 진단

`jev-choice-v3`는 공식 관측의 간결한 상태와 합법 후보를 native Choice로 보낸다. 선봉도 JEV가
선택하며 Gen9 기본 지식 원문·요청별 상세 효과 사전을 포함한다. 상세 피해 계산·요약은 제외한다. `POKECHAMP_PROVIDER`는 변경하지 않는다.

```bash
cd /workspace/pokechamp
PYTHONPATH=/workspace:/workspace/pokechamp .venv/bin/python -m integration.pokechamp.jev_battle local --output /workspace/.pokechamp-data/jev/local-new
PYTHONPATH=/workspace:/workspace/pokechamp .venv/bin/python -m integration.pokechamp.jev_battle live
```

local은 모의 HTTP를 사용하는2경기이며 외부 호출0이다. live는 EX-051 전용으로 유효한
검증 receipt를 요구하고 고정된 `.pokechamp-data/jev/ex051-live`를 한 번만 생성한다.
팀1/2·Abyssal 상대·진영/팀 교환2경기,300요청/30분 상한·재시도0이다. 합법 선택의 판단 진단은 계속하며 실행 불가능한 출력은
해당 경기만 실패 처리한다. 입력·통신·전송·무결성 오류는 신규 수집을 중단한다.
기존 실행 폴더를 지워 재실행하지 않는다. 새 실험에는 별도 등록과 실행 identity가 필요하다.
`report.html`은 오프라인 입력·응답·확률·선택/전송 viewer, `result.json`은 실제 분모와 사용량,
`events.jsonl`은 원문이다. 확률을 배틀 승률로 해석하지 않는다.

EX-047은 당시 합계 검사로0.99 응답에서 중단했으며 정상완료0/2다. 이후 D-072에 따라 새 choice-values-v2는 합계를 검사하지 않고 개별 값·후보·최상위 선택만 검증한다. 과거 원문과 당시 기준은 보존한다. [실제 검증 보고](../../project_context/exec-plans/evidence/ep062/report.md).

EX-048은 첫 경기 JEV 승리·두 번째 선택/최댓값 불일치 중단으로 정상완료1/2다. 실행 폴더를 재사용하지 않는다. [재실행 보고](../../project_context/exec-plans/evidence/ep064/report.md).

EX-050은 판단 오류 비중단 적용 후2경기 정상완료·JEV1승1패다. EX-049 API0 준비 실패는 보존했다. [최종 보고/viewer](../../project_context/exec-plans/evidence/ep066/report.md).


EP-070/D-079의 v2는 선봉 자기 팀을 요청 슬롯으로 구성한다. 공개 프리뷰와 종족/순서로
연결하지 않으며 상태이상 없음(`status=""`), 효과/변화 없음(`{}`), 테라 미적용(`tera_type=""`),
근거 부재(`unknown`)를 구분한다. `teraType`은 설정 타입이며 적용 상태가 아니다.
초기 PP는 검증된 고정 서버/Dex·Gen9 OU 시작 전 경계에서만 계산한다. 근거가 없으면
`current_pp_reason`과 unknown을 유지하고 일반 턴의 active 요청 PP가 우선한다.
과거 감사는 manifest의 jev-choice-v1/v2와 당시 prompt를 재현한다.
EP-071/EX-051에서 v2 실제2경기·전수 감사·뷰어·정리를 완료했다.
[실제 검증 보고](../../project_context/exec-plans/evidence/ep071/report.md).
기존 EX-050은 보존하며 완료된 실행 경로를 재사용하지 않는다.
[교정·검증 보고](../../project_context/exec-plans/evidence/ep070/report.md).

배틀/API 없이 저장 입력만 대조하는 명령(출력은 새 디렉터리):

```bash
PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m integration.pokechamp.diagnostics.jev_lead_input --output /tmp/jev-lead-offline-new
```


JEV 실험자 뷰어는 ←/→로 이전/다음 결정을 탐색할 수 있다. 같은 턴의 강제 교체도 순서대로
표시하며 드롭다운·입력칸·탭 조작과 리플레이 프레임의 키 조작은 독립이다.
상태·후보 요약의 상대 HP는 반올림된 공개 백분율이고 미공개는 미확인이다.
자기 HP와 요청/응답 JSON·복사/다운로드는 원값을 유지한다. EX-051 내보내기에 적용했다.

## EX-052 JEV 대 Abyssal32

`jev_study`는 EX-046의 봉인된 팀/seed/32행 일정에 JEV와 Abyssal을 배정한다.
완료된 EX-052의 JEV는 v2 입력을 사용했다. 새 입력 기본값은 v3이며 기존 실행을 변경하지 않는다.
Abyssal은 별도 프로세스에서 actor seed를 사용한다.
순차 실행·최초 HTTP부터20100초 수집/21600초 정리·호출 수 상한 없음이며 재시도/보충0이다.
과거 `jev_battle`의2경기 기본값/실행 경로와 봉인은 유지한다.

```bash
# cwd=/workspace/pokechamp. local은 실제 API0, 블록별 r1 양진영8경기다.
PYTHONPATH=/workspace:/workspace/pokechamp .venv/bin/python -m integration.pokechamp.jev_study local --output /workspace/.pokechamp-data/jev/local32-new
# 승인·현재 source와 일치하는 EP-073 receipt 필수, 고정 ex052-live 한 번만 생성
PYTHONPATH=/workspace:/workspace/pokechamp .venv/bin/python -m integration.pokechamp.jev_study live
```

조건·중단·복구·분모는 [EX-052](../../project_context/research/model-evaluation/experiments/EX-052-jev-abyssal32.md),
검증·실행 근거는 [EP-073](../../project_context/research/model-evaluation/plans/EP-073-jev-abyssal32.md)이다.

## JEV v3 오프라인 입력 검증

[EP-074 보고](../../project_context/exec-plans/evidence/ep074/report.md)에서 EX-052 저장 입력의
v2 정확 재현과 v3 허용 차이·전후 예시·크기 증가를 확인할 수 있다.
사전은 `state.effect_reference.items/abilities/moves`의 ID별 `{name, desc}`다.
원문에 언급된 항목을 재귀 확장하거나 상대 비공개 세트를 추론하지 않는다.
`current_pp_source`는 새 모델 입력에서 제외하며 PP 값·`current_pp_reason`은 유지한다.
manifest와 input 이벤트의 `effect_reference_identity`, 원래 관측/request와 초기 PP 정책으로 감사한다.

```bash
PYTHONPATH=/workspace:/workspace/pokechamp pokechamp/.venv/bin/python -m integration.pokechamp.diagnostics.jev_v3 --output /tmp/jev-v3-offline-new
```

이 명령은 저장 관측을 오프라인 재생성하며 API·새 배틀을 수행하지 않는다.

## EX-053 JEV v3 동일32경기와 v2 전후 비교

EX-052 봉인 manifest의 팀/seed/순서/모델 설정을 직접 사용한다. 과거 기본 일정 명령은 v2로
해석하며 새 실험은 명시 선택한다. 조건·상한·중단·분모는
[EX-053](../../project_context/research/input-and-memory/experiments/EX-053-jev-v3-abyssal32.md)이다.

```bash
# cwd=/workspace/pokechamp, PYTHONPATH=/workspace:/workspace/pokechamp
.venv/bin/python -m integration.pokechamp.jev_study local --experiment EX-053 --output /workspace/.pokechamp-data/jev/ex053-local-final
# EP-075 사전 receipt 필수, 고정 새 디렉터리에 최초1회 진입
.venv/bin/python -m integration.pokechamp.jev_study live --experiment EX-053
```

결과는 [EP-075](../../project_context/research/input-and-memory/plans/EP-075-jev-v3-abyssal32.md)에 연결한다.

## D-084/D-087 provider 재시도3회·대기 확대

새 JEV 독립 클라이언트와 Session/StudySession은 `jev-provider-retry-v2`를 기본으로 사용한다.
연결 오류·timeout·HTTP429/5xx는 10/30/60초 대기 후 최대3회 재시도한다(최초 포함 총4시도).
성공하면 조기 종료한다. 인증401/403·그 외4xx·입력/응답/판단 오류는 재시도하지 않는다.
Session의 모든 물리 HTTP 시도는 원장/상한에 포함되며 최초 시계·남은 기한·취소를 유지한다.
내부 client는 단일 전송으로 사용하여 중첩 재시도를 막고 요청/응답/오류/재시도 관계를 보존한다.
Ollama/Z.ai의 `provider-retry-v2`도 기존대로3회다. 과거 고정 EX 유료 명령과 봉인·감사는
각각 당시 정책을 유지한다(기존0회, EX-054 v1은1/2/4초). 이번 변경은 과거 실행 재개나 새 유료 수집을 수행하지 않는다.
[최초 검증](../../project_context/exec-plans/evidence/ep076/report.md) · [대기 확대 검증](../../project_context/exec-plans/evidence/ep079/report.md).

## EX-054 동일 조건 재실험

EX-053의 봉인 일정/처치와 D-084 재시도3회를 결합한다. 새 EX-054 receipt·출력은 독립하며
조건·새6시간·중단·분모는 [EX-054](../../project_context/research/input-and-memory/experiments/EX-054-jev-v3-retry32.md)를 따른다.

```bash
# cwd=/workspace/pokechamp, PYTHONPATH=/workspace:/workspace/pokechamp
.venv/bin/python -m integration.pokechamp.jev_study local --experiment EX-054 --output /workspace/.pokechamp-data/jev/ex054-local
.venv/bin/python -m integration.pokechamp.jev_study live --experiment EX-054
```

실행·검증 근거는 [EP-077](../../project_context/research/input-and-memory/plans/EP-077-jev-v3-retry32.md)에 연결한다.

## EX-056 사전 검증 생략 직접32

D-088의 사용자 승인 범위에서 cwd=/workspace/pokechamp,
`PYTHONPATH=/workspace:/workspace/pokechamp .venv/bin/python -m integration.pokechamp.jev_study live --experiment EX-056`을 사용한다.
고정 ex056-live 최초1회만 허용하며 entry-record.json에 사전 검사 생략·승인·identity를 기록한다.
모의/probe/첫4 특별점검0, 재시도10/30/60초. 경기별 및 종료 감사·보고·뷰어는 유지한다.
조건은 [EX-056](../../project_context/research/input-and-memory/experiments/EX-056-jev-direct32.md)을 따른다.

## EX-057 jev-1.13.0 고정 직접32

`TYPESAFE_MODEL=jev-1.13.0 PYTHONPATH=/workspace:/workspace/pokechamp .venv/bin/python -m integration.pokechamp.jev_study live --experiment EX-057`
(cwd=/workspace/pokechamp). EX-056 봉인 대진·같은 endpoint·새 시계로 직접 진입한다.
사전 검사0·경기별/종료 감사 유지. [EX-057](../../project_context/research/input-and-memory/experiments/EX-057-jev-pinned32.md).

### EX-058 개선 입력 동일 대진 재현

실험 전용 `jev-choice-v4`는 EP-093 상세 입력 생성기·지시문을 그대로 재사용하며 버전 표기만 다르다.
자기 벤치 상세·상대 벤치 요약을 사용한다. 일반 기본 v3·과거 재현은 유지한다.
`jev_study live --experiment EX-058`은 EX-057의 봉인32행·팀·seed·진영을 읽으며,
EP-094의 동결 source/data 및4개 저장 사례 receipt를 확인한 뒤 재시도 없는 실제 요청1회를 수행한다.
통과하면 같은 source/config로 순차 수집한다. 사전 요청의 최초 wall/monotonic 시계를 본수집에 이어서
+20100초 신규 수집 차단·+21600초 정리 한도를 적용한다. 사전 요청은 성적/본수집 사용량에서 분리한다.
고정 출력 경로 또는 사전 요청 경로가 이미 있으면 재실행하지 않는다. 이 명령 설명은 재수집 승인이 아니다.
모든 조건·중단·완료 기준은 [EX-058](../../project_context/research/input-and-memory/experiments/EX-058-jev-improved32.md),
결과·검증은 [EP-094 보고](../../project_context/exec-plans/evidence/ep094/report.md)를 따른다.

### EX-060 한 경기 행동 분기 데이터

`branch_rollouts`는 EX-058 battle-19의 원관측·명령·seed로 원경기를 재현한 뒤,
저장된22개 결정에서 후보별로 양측 Abyssal 후속 경기를 수집한다.
원경기·모든 root 복원 검증, 후보 공통 난수, 누적 예산 원장, private state와 학습 export 분리,
후보별 통계·오프라인 뷰어·감사/봉인을 포함한다.
[실행 안내](branch_rollouts/README.md) · [동결 조건](../../project_context/research/action-value/experiments/EX-060-single-battle-branch-rollouts.md).
반복 실행으로 예산을 초기화하지 않으며 이 안내는 새 수집 승인이 아니다.
# Qwen 최종 LoRA 로컬 서빙과 배틀

EX-062는 EX-061 최종 어댑터의 연결 검증이다. 후보 q는 양측 Abyssal 후속 조건으로 학습한
독립 값이며, 새2경기의 승패로 학습 효과나 일반 성능 개선을 판정하지 않는다.
서버는 EVE 환경·물리 GPU1, 배틀은 기존 PokéChamp 환경을 사용한다.

```bash
cd /workspace
scripts/pokechamp-qwen start
scripts/pokechamp-qwen status
scripts/pokechamp-qwen probe --output /workspace/project_context/exec-plans/evidence/ep103/gpu-probe
scripts/pokechamp-qwen battle
scripts/pokechamp-qwen stop
```

`start`는 고정 base revision·어댑터 seal을 확인하고 모델을 한 번 로딩한다.
`status`는 소유 PID와 `/health`를 표시하고, `stop`은 PID 시작 시각·명령·소유 token이 일치하는
프로세스만 종료한 뒤 가중치 불변 closure를 반환한다. 다른 프로세스는 종료하지 않는다.
probe/battle의 기본 경로는 덮어쓰기를 거부한다. EX-062 완료 후에는 승인된 실행을 자동 반복하지
않는다. 새 연결 실행의 `battle --output PATH`는 새 사용자 승인 범위와 별도 기록으로 사용한다.

`GET http://127.0.0.1:8765/health`는 ready/model/revision/adapter_sha256/max_len을 반환한다.
`POST /evaluate`의 JSON은 `{ "observation": <JEV v4 payload>, "actions": [
{ "action_id": "move_1", "command": "move 1", "description": <동일 criteria> } ] }`이다.
actions는 criteria 순서 그대로다. 응답은 q_values/choice/command/candidates(token 및 prompt hash)/
total_tokens/elapsed_seconds를 포함한다. 최대 q와 원순서 동률을 사용하고 단일 후보도 평가한다.
합계 정규화는 하지 않는다. 입력16384토큰 초과는 무절단400, 요청600초 초과는408이며 재시도0이다.
FP32 가중치·BF16 forward·FP32 A/B readout·eval/no_grad를 유지한다.
서빙 원자료는 `.pokechamp-data/qwen/ex062-server/<owner>/`, 배틀은 `ex062-live/`에 보존한다.
모델·입력·팀·시간·실패 범위 원문은 [EX-062](../../project_context/research/action-value/experiments/EX-062-qwen-local-battle.md),
규범 경계는 [C-049](../../project_context/research/action-value/CONTRACTS.md#c-049-qwen-local)이다.

### EX-063 학습 원대진 1경기

사용자 지정 원대진은 Abyssal p1/team6·Qwen p2/team2다. 원 성별·game/actor seed를
재사용하며 학습 자료의 개발 진단으로 분류한다. 기존 EX-062 중단 원장은 보존한다.
새 실행 경로는 존재하면 덮어쓰기를 거부한다. 완료 후 배틀 반복에는 새 승인/EX가 필요하다.

```bash
cd /workspace
scripts/pokechamp-qwen start
scripts/pokechamp-qwen probe --output /workspace/project_context/exec-plans/evidence/ep104/gpu-probe
scripts/pokechamp-qwen battle --experiment EX-063
scripts/pokechamp-qwen stop
```

배틀 cwd는 upstream 상대 경로 세트 자료를 읽도록 `/workspace/pokechamp`를 사용한다.
[실험 조건](../../project_context/research/action-value/experiments/EX-063-qwen-training-matchup.md).

## Qwen 후보 상태 입력과 저장 입력 비교

명시 프로필 `qwen-candidate-state-v1`은 기존 상세 입력에 공통＋결정별 지침,
행동 순서에 따른 지원 상태 전이·재계산·교체 시점·진입 후 상태를 추가한다.
공개 정보와 자기 제출 팀만 사용하며 각 시나리오의 상대 세트·속도·내구·화력을 연결한다.
미지원 전이는 `unknown`과 이유를 제공한다. 상세 지원 범위와 한국어 지침 검토는
[설명 문서](../../docs/qwen-candidate-state-instructions.md)를 따른다.

기본 서버와 기존 EX-062/063 배틀 명령은 원 프로필을 사용한다. 개발 서버는
`start --candidate-state --diagnostics`에서 새 입력과 별도 JSON 진단을 활성화한다.
Python `qwen_player.Session(directory, input_version='qwen-candidate-state-v1')` 및
`qwen_temporal.Adapter`가 명시 버전을 연결한다. q의 합법 ID·A/B forward·최댓값 선택·
명령 매핑은 동일하다. 진단 결과는 q에 추가하지 않는다.

EX-064 준비와 무절단 토큰 사전 검사는 CPU/tokenizer만 사용한다. 출력은 각각 새 경로를
요구하며 원자료나 완료 단계의 결과를 덮어쓰지 않는다.

```bash
scripts/pokechamp-qwen state-study prepare --output /workspace/.pokechamp-data/qwen/ex064-candidate-state
scripts/pokechamp-qwen state-study token-preflight --output /workspace/.pokechamp-data/qwen/ex064-candidate-state
scripts/pokechamp-qwen study-run --output /workspace/.pokechamp-data/qwen/ex064-candidate-state
```

`study-run`은 사전 검사 후 파일을 동결하고 새 소유 서버에서 기존 모델의 저장 입력만
평가한다. q 비교 뒤 별도 진단과 전후 q 무변경 대조를 실행하고 서버 정리·보고·봉인을
완료한다. 새 배틀 명령 전송과 모델 업데이트는 없다. 실행 조건·분모·시간 상한·실패·
해석 원문은 [EX-064](../../project_context/research/action-value/experiments/EX-064-qwen-candidate-state.md)이며,
후속 재수집이나 독립 배틀 평가는 별도 등록 범위다.

Qwen/JEV 실험자 뷰어는 선택·결정 목록·후보를 실제 기술명과 교체/선봉 대상명으로 표시한다.
테라 선택에는 `테라스탈`을 붙이며 원 행동 ID·명령은 상세 JSON에서 확인한다. 이름 해석은
해당 결정의 관측만 사용한다. EX-063의 이전 표시 버전은 `exports/battle_viewers/ex063-v1`에 보존한다.

## Kev-4B pokechamp r1 연결

별도 공동 입력/noul 실시간 연결은 [Kev 안내](KEV.md)를 따른다. 기존 Qwen 서빙·EX-066
학습과 독립하며, 현재 수락 범위는 EX-068의 validation 재현·1경기 smoke다.
