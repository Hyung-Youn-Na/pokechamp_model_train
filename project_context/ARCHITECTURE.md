# 아키텍처 (Architecture)

`research/model-training`은 `/workspace`에서 모델 학습·정책 개선·독립 평가를 개발하는
연구선이다. [D-131](decisions/D-131-research-branch-preservation.md)의 분리는 공통 코드 기준선을 유지하고 목적·작업 안내를 구분한다.
기존 Python API·CLI·모델 입출력·학습 알고리즘과 submodule pin은 이번 단계에서 변경하지 않는다.

현재 실행 환경·interpreter·가상환경·캐시는 `/workspace`의 원경로에 둔다. 새 실험은 출력 경로를
선택할 수 있는 기존 CLI의 명시적 인자로 `/mnt/digicap/combined/hyna/backup/pokechamp-research/runs/model-training/<새 실험 ID>`를
사용하며 과거 실행기의 고정 출력 경로를 바꾸지 않는다. 현재 실행 중인 연구 실험은 없다.
보존본·별도 Git 저장소·모델 blob·복원 연결은 [연구선 작업·출력·복원 안내](RESEARCH_WORKFLOW.md)를 따른다.

L1-L5 구조 이식은 별도 `research/l1-l5-port`의 보존·후속 설계 목적이다.
이 문서의 AgenticSTS와 기존 학습·JEV 구성 설명은 공통 기준선의 사실이며 자동 실행 목록이 아니다.
상세 AgenticSTS 구조는 [상속 아키텍처](../AgenticSTS/docs/reference/ARCHITECTURE.md)와
[repository layout](../AgenticSTS/docs/reference/REPO_LAYOUT.md)에 보존한다.

현재 공통 경로와 특정 정책의 실행 경로를 구별한다. 실행 승인·조건은 [CONTRACTS](CONTRACTS.md)와
[RESEARCH_DESIGN](RESEARCH_DESIGN.md), 단계별 자격·결과는 [STATUS](STATUS.md)와 개별 EX 기록을 따른다.
기능이 존재한다는 사실은 중단 실험의 재개 권한이 아니다.

## 고정 대진 공개 상태 정책 학습

[D-119/EX-076](experiments/EX-076-fixed-matchup-mcts.md)의 독립 구현은
`integration/pokechamp/fixed_matchup/`과 `scripts/pokechamp-fixed-matchup`이다.
D-126/EX-079의 `stopping_prepare`는 완료된 EX078 round1과32경기·optimizer/RNG를
새identity에 검증 계승한다. `stopping_run`은 정기 개발 평가 기록에서 종료 상태를 재구성하고,
정체 anchor와 실제 최고 모델을 분리한다. 정상 종료·최고 모델 잠금 이후에만 독립test에 진입하며
`stopping_finalize`가 실제 경기 결과와 종료/선택 기록을 독립 대조한다. 시간 상한은 적용하지 않는다.
D-123/EX-078의 `first_round`는 P0·worker설정만 계승하여 새32경기를 감사·학습하고
round1 체크포인트의 저장/재로딩을 검증한 뒤 종료한다. D-124 이후 별도 protocol의 무제한 경과시간 기록과
진단 완료 판정을 사용하며 기존 전체평가 경로는 유지한다.
D-122/EX-077의 새 기본값은24시간이며 `day-prepare`가 EX-076 정상uniform32와 P0의
출처·봉인을 검사하여 계승한다. CPU 입력 packing은 검증된 행을 모아 tensor별로 한 번 변환한다.
Node의 실제 경기 프로세스만 비공개 로그·원 RNG를 보유한다. 열거된 공개 현재 상태를
새 RNG의 탐색 프로세스에서 복원하며 양측 공동 행동을 한 RPC로 전이한다. Python의 Exp3
선택기는 양측을 독립 표본화하고 확률 분기를 통해 주변 방문 타깃을 생성한다.

정책은 무작위 초기화한 PyTorch TransformerEncoder 4층(hidden128/head4/FFN512)이다.
범주 embedding과 숫자32개 projection을 더한 상태 토큰을 인코딩하고 유효 토큰 평균으로
상태를 집계한다. 상태·후보 표현의 MLP가 합법 행동 logits를, 별도 tanh MLP가 상태가치를 낸다.
토큰 순서 위치 embedding은 없고 관점·종류 범주와 원래 팀/기술 슬롯 숫자가 관계를 나타낸다.
모델 특징은 구조화된 요약이며 시뮬레이터의 공개 상태 직렬화 전체를 무손실 입력하는 것은 아니다.
현재 Dex vocabulary5106개 기준 학습 파라미터는1,500,674개이며 Qwen 가중치를 사용하지 않는다.

CPU worker가 경기/탐색을 수행하고 주 프로세스의 배치 추론 스레드가 단일 소유 GPU를 사용한다.
완료 라운드 checkpoint에 optimizer·난수·replay 식별자·최초 시계를 저장한다.
선택은 dev, 개선 판정은 잠긴 test640경기로 분리한다. 원자료 감사는 실제 Showdown의 정규화된
명령 로그와 기록을 대조하며 오프라인 입력/응답/protocol 뷰어를 내보낸다.
실행·재개와 제약은 [사용법](../integration/pokechamp/fixed_matchup/README.md)을 따른다.
GPU 수치·처리량·실험 성공은 CPU 개발 검증에서 확정하지 않는다.

## Repository 경계

| 경계 | 관찰된 책임 |
|---|---|
| [`AgenticSTS/`](../AgenticSTS/) | Python agent runtime, prompt/context 조합, L3 조회, L4/L5 로직, 실험·재현 script, test, monitor backend/frontend, 정적 leaderboard |
| [`AgenticSTS-Mod/`](../AgenticSTS-Mod/) | .NET 9/Godot/Harmony mod fork. 실행 중인 game state를 직렬화하고 action을 검증·주입하며 HTTP/SSE를 제공한다. |
| [`AgenticSTS-Data/`](../AgenticSTS-Data/) | 공개 분석에 사용된 고정 dynamic store와 run/evolution/experiment artifact |
| [`docs/`](../docs/) 및 [`assets/`](../assets/) | Root release/site 자료·figure 및 PokéChamp 입력·요약 설명 문서. Agent runtime의 일부가 아니다. |
| [`pokechamp/`](../pokechamp/) | Decision D-007에서 pin한 외부 PokéChamp source submodule. Parent integration은 이 worktree를 수정하지 않는다. |
| [`pokemon-showdown/`](../pokemon-showdown/) | Local battle server용으로 pin한 외부 Showdown fork submodule. Canonical worktree는 실행 중에도 clean하게 유지한다. |
| [`integration/pokechamp/`](../integration/pokechamp/) 및 [`scripts/pokechamp-env`](../scripts/pokechamp-env) | Parent-owned bootstrap, 명시 선택 Cloud adapter, deterministic server wrapper, qualification CLI와 test |

Release는 세 개의 최상위 component directory를 포함한 하나의 Git repository로 묶여 있다.
Python component에서 data와 mod directory는 sibling path다. Dynamic-data path 해석은
`AgenticSTS/src/storage/paths.py`에 집중되어 있다.

## 환경과 qualification

[EP-096](exec-plans/completed/EP-096-laya-training-environment.md)의 별도 LAYA-RLCD source는
`.tools/laya-rlcd/upstream`, 학습 준비 worktree는 `.tools/laya-rlcd/worktrees/pokemon-training`이다.
고정 upstream source와 독립 `.venv-train`·공개 모델·로컬 캐시를 사용하며 현재 PokéChamp runtime에
연결하지 않는다. 설치·GPU/모델 검증 범위와 재진입은 [환경 안내](../.tools/laya-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md)를 따른다.

[EP-097](exec-plans/completed/EP-097-eve-rlcd-environment.md)의 별도 EVE-RLCD source는
`.tools/eve-rlcd/upstream`, worktree는 `.tools/eve-rlcd/worktrees/pokemon-training`이다.
upstream lock의 Python3.12 환경을 `.venv-eve-rlcd`에 구성하며 LAYA와 import/cache 경로를 분리한다.
공개 Qwen3 환경 검증에 이어 EX-061 포켓몬 가치 학습과 아래 D-099 로컬 서빙 경로를 연결했다. 실제 배틀 검증은 EX-062 중단으로 미완료다.
환경 선택과 재진입은 [환경 구분 안내](../.tools/eve-rlcd/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md)를 따른다.

[EP-098](exec-plans/completed/EP-098-rlcd-lite-environment.md)의 별도 RLCD-Lite source는
`.tools/rlcd-lite/upstream`, worktree는 `.tools/rlcd-lite/worktrees/pokemon-training`이다.
`.venv-rlcd-lite`에 Python3.11 환경과 CUDA12.8 호환 lock을 설치하며 원본 CUDA13 lock은 보존한다.
공개 Qwen2.5 모델의 로컬 구조화 추론만 검증했고 PokéChamp runtime·학습/평가에는 연결하지 않았다.
차이와 재진입은 [환경 구분 안내](../.tools/rlcd-lite/worktrees/pokemon-training/docs/POKEMON_ENVIRONMENT.md)를 따른다.

Decision [`D-007`](decisions/D-007-adopt-pokechamp-dotenv-credential.md)이 다음 current boundary를
채택했고 [`EP-001`](exec-plans/completed/EP-001-pokechamp-reproducible-environment.md)이 구현했다.

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
실측 probe·배틀 검증 범위는 [EP-001](exec-plans/completed/EP-001-pokechamp-reproducible-environment.md)을 따른다.

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
계약은 [C-045](CONTRACTS.md#c-045-jev-battle), 현재 완료된 v2 실행은 EX-051이고 과거 EX-050은 보존한다. choice-action-v3 판단 진단·경기 실패 격리는 [C-046](CONTRACTS.md#c-046-provider-judgment)이다.

별도 `diagnostics/jev_damage_samples.py`는 EX-057의 제한된 actor prefix와 자기 제출 세트를
재현하여, 출전 포켓몬 사이의 피해량 범위 프롬프트 샘플을 생성한다. `damage_sets.py`는
고정 추천 세트별 선택지와 공개 이력의 정합성을 처리하고, `jev_damage.py`는 기존 계산기와
보정을 재사용해 테라 분기·방향별 범위를 합산한다. `jev_damage_verify.py`는 개별 Smogon
계산과 합성 테라 관측을 대조한다. EP-082 자체는 오프라인 진단이며, D-094의 EX-058은
EP-093 투영을 거쳐 이 계산을 사용한다. 범위·재현·검증은 [EP-082 보고](exec-plans/evidence/ep082/report.md)를 따른다.

별도 `diagnostics/jev_offline.py`는 운영 v3를 생성한 뒤 효과 인라인·기술 슬롯·역할/HP/테라·
전체 상성표·공식 자연어 로그로 투영한다. `jev_text.cjs`는 기존 고정 클라이언트의 BattleTextParser와
고정 서버 text 데이터를 사용하며 자리표시자/능력치 테이블만 호환한다. `jev_speed.py`는 EP-082와
같은 공개 후보·계산기의 현재 유효 스피드 범위·세트별 비교·정성적 불확실성을 산출한다(D-093).
추천 세트 안의 일치와 전세트 확정을 구분하며 확률 필드는 제공하지 않는다.
`jev_offline_samples.py`는 일반/선봉/강제교체의 저장 prefix를 재생하고 상세/자기 벤치 축약 입력과
대리 토큰 비교를 생성한다. [EP-093](exec-plans/completed/EP-093-jev-offline-input.md)은 오프라인 검증 범위다.
D-094의 실험 전용 jev_v4.Adapter가 같은 생성기를 재사용하여 EX-058에 연결하며 일반 기본 v3는 유지한다.

## 연구 관측·봉인·viewer

정상 종료 실험의 열람용 복사본은 [C-047](CONTRACTS.md#c-047-viewer-export)에 따라
`exports/battle_viewers/<실험ID>/index.html`에 둔다. 원본 봉인과 분리된 완료 산출물이며
상위 index에서 탐색한다. EX-050은 경기별 입력·응답과 고정 리플레이 패널을 제공한다.
기존 replay renderer로 actor protocol을 재생하며 애니메이션은 공식 외부 자산,
입력·응답·턴 탐색·protocol fallback은 로컬 파일을 사용한다.
`jev_viewer.py`는 봉인된 input.payload와 transport.model을 단일 요청 객체로 복원하고
실험자용 요청/응답·상태 요약·기술 기록 탭과 JSON 복사/다운로드를 생성한다.
API 미호출 결정은 관측/후보로 표시하며 원본 전체 기록을 별도로 유지한다.
jev-researcher-v2는 좌우 방향키 결정 탐색과 상대 HP의 공개 백분율 요약을 제공하며,
원래 요청 JSON과 자기 HP 절대값은 그대로 표시한다.

Decision [`D-010`](decisions/D-010-adopt-pokechamp-battle-observability.md)은 qualification과 분리된
opt-in logging path를 정의한다.

```text
scripts/pokechamp-env research run --experiment-id <tag>
  -> required POKECHAMP_DATA_ROOT + exclusive battle bundle open
  -> parent TraceablePlayerMixin
       inbound Showdown protocol -> protocol_in
       each request -> decision_start / decision_result
       actual transport send -> wire_action
  -> OllamaCloudBackend(trace_sink=...)
       effective prompt + reasoning/raw/parsed output + validation -> llm_call
  -> manifest.json + events.jsonl -> final manifest -> checksums.sha256
  -> derived showdown.log / replay.html / report.html
  -> experiment catalog.sqlite / index.html rebuild
```

Source evidence와 write authority는
`<POKECHAMP_DATA_ROOT>/experiments/<experiment_id>/battles/<battle_id>/`에만 있다. Qualification은
trace sink를 전달하지 않으므로 기존 `.artifacts/pokechamp/` content 최소화 동작을 유지한다.
Renderer와 catalog builder는 source를 read-only input으로 사용하며 derived output만 교체한다.
Showdown animation은 official network asset을 선택적으로 사용하지만 report의 decision card와 turn
timeline은 embedded static HTML이므로 offline에서도 동작한다. 이 경로는 자동 memory write나
efficacy 분석을 수행하지 않는다.
Report는 sandbox iframe으로 replay를 표시하고 CSS sticky 패널을 사용해 decision 스크롤 중에도
재생 화면을 유지한다. 넓은 화면은 오른쪽 패널, 좁은 화면은 상단 패널을 사용한다.
[D-049](decisions/D-049-viewer-turn-tabs.md)의 새 생성 report는 기록된 `showdown_turn`으로
준비/턴/턴 미상 탭을 구성하고 같은 턴의 결정은 순서대로 함께 표시한다. 바로가기·이전/다음,
키보드 탭 이동과 기존 decision/issue fragment 및 URL history 복원을 내장 JavaScript로 제공한다.
각 LLM 호출의 reasoning/원문 답변은 항상 펼치고 입력·B2 원본·metadata와 전체 protocol은
별도 details로 열람한다. 스크립트는 CSP SHA-256으로 허용하며 비활성 시 모든 결정이 정적으로
표시된다. 기존 실험 viewer는 재생성하지 않았고 source schema/parser/계산 경로는 유지한다.

<a id="execution-boundaries"></a>

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
실행 종료 뒤 프로세스/소켓 정리는 별개다. [EX-032 조사·보고](exec-plans/evidence/ep026/report.md).

EX-033 정상 완료는 EX-032 외부 RAM 원인의 독립 입증이나 기존2초 ACK 경계 제거가 아니다.
[EX-033 보고](exec-plans/evidence/ep027/report.md).

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

<a id="battle-input"></a>

## 관측·계산·행동 설명서

`integration/pokechamp/improved_io/`는 관측·고정 prior·계산기·고정 행동 출력 및 배틀 내 요약을 제공한다.
`posthoc.py`만 검토용 상대 정답을 읽는다. 전체 공개 prefix의 상태 복원과 최근10결정 전송 window를
구별한다. 실제 입력·요약 lifecycle은 [입력·요약 구조](../docs/pokechamp-input-summary.md),
prompt 원문은 [부록](../docs/pokechamp-prompt-originals.md)에 있다.

`protocol.py`가 원본 행 순서·HP·필드 시점·Future Sight slot을 해석한다. `state.py`는
raw parser_effects와 현재 effects를 구분하며 소비 item을 prior로 되살리지 않는다.
`public_revelations`는 공개 특성 holder, 자기 귀속 item 발동·획득·제거를 시간순 반영한다.
Drought는 명시적인 `[of]` holder를 사용하며 upkeep/holder 없는 날씨행으로 특성을 추론하지 않는다.
`oracle.py`는 원문에서 공개 특성·item·정답을 별도로 확인한다. weather 숫자 의미는
last_weather_protocol_turn이며 실제 시작 턴은 protocol event annotation에서 확인한다.
`calculations.py`는 pinned getHealth의99/100 예외와 float 순서를 따른다.

[D-034](decisions/D-034-calculator-entry-calcfix32.md)의 worker는 명시적 무특성/관측 완료 등장 특성에서
인스턴스 ability와 인스턴스 species 기본 특성 fallback을 함께 비워 clone 후 복구를 막는다.
공유 종 데이터와 설치 라이브러리는 변경하지 않는다.
[D-035](decisions/D-035-calculator-input-audit.md)의 `lifecycle.py`는 최근 창과 별도로 전체 공개
prefix에서 Pokémon별 소비·억제·QP 원천·팀 기절 이력을 재구성한다. `state.py`가 v2 상태를
정규화하고 `calculations.py`가 현재/선택 교대/선택 테라 시나리오를 만든다. worker의
`scenarios-v2.cjs`가 진입 hazard·필드·소모 아이템을 투영하고 `state-patch.cjs`는 검증된
mechanics-v2 overlay를 메모리에서만 컴파일한다. 설치 라이브러리·공유 종 데이터는 보존한다.

`gate.py`와 backend는 state/request/bundle identity·내용·coverage·최신 원문 request·필수 이력을
검증하며 새 `battle-v1.2.0` 설명서는 모든 추가 필드를 포함한다. 미래 전체 턴·실행 확률은
계산하지 않으며 지연 공격·미공개 교체·지원하지 않는 이력 기술은 명시적 경계를 유지한다.
EX-029의 당시 source와 중단 결과는 보존하며 교정으로 과거 실험을 유효화하지 않는다.
[전체 조사·수정 보고서](exec-plans/evidence/ep023/report.md)와
[별도 영향 분석](exec-plans/evidence/ep023/impact.md)이 현재 검증 범위를 정의한다.

기술명 생성은 [D-037](decisions/D-037-calculator-move-names.md)에 따라 pinned Gen9 canonical
이름을 사용하며 Weather Ball 및 동일 원인 기술을 처리한다. [EP-025 검증](exec-plans/evidence/ep025/report.md).
Protect 만료는 raw 효과를 보존하면서 현재 효과만 교정한다. [EP-031 검증](exec-plans/evidence/ep031/protect-expiry-v1/report.md).
Court Change 실행 알림도 전체 공개 prefix로 확인한 보유자의 계산용 효과에서만 제거한다.
공개 `-swapsideconditions`는 원래 설치 기록을 유지해 해당 진영 효과만 교환한다. 공개 상태이상
행의 특성 보유자는 명시적 `[of]`로 연결하고, 상대 기절 후 effective_types는 테라 전 타입으로
돌아간다. parser 원문 표현·관측 tera_type은 보존한다. [D-062](decisions/D-062-court-change-input-audit.md).
지연 기술의 슬롯 없는 대상은 공개 switch/drag/replace/faint 근거의 유일한 슬롯으로만 복구하고
명시 슬롯을 우선한다. 근거 부족·모호함은 기존 오류를 유지하며 Doom Desire 시작 표기를 지원한다.
[EP-036 검증](exec-plans/evidence/ep036/report.md). 이 수정은 전수 과거 계산 재생 완료나 EX-038 유효화가 아니다.


`improved_io/battle_prompts.py`는 선택 버전의 `fields.json` 경로/자료형/의미를
일정 순서로 렌더링하고 원본 policy와 조립한다. 현재 새 B prepare는 D-066의 공식 관측 v1.4.0, 명시적 legacy는 D-057의 v1.3.0, 과거 버전 부재는
v1.0.0이며 summary 버전 선택 및 A 경로는 유지한다. `battle-prompt.json`에 전체 system·
identity·입력별 크기를 봉인하고 manifest·execution evidence·worker/actor 요청에 같은
identity를 연결한다. Backend가 실제 system/user를 대조하며 v1.1.0의 재귀 경로 검사는
원문 request JSON까지 포함한다. 15장면 외 선택적 request·지연 효과·미상 교체 분기는
fixture로 확인한다. 기존 v1.1.0/v1.2.0 설명서는 입력 해석 문서이며 사전 게임효과 지식이나 평가 정답이 아니다.
D-057의 v1.3.0은 아래 일반 게임 효과 사전을 별도로 추가한다.
구현·로컬 검증 결과는 [EP-019](exec-plans/completed/EP-019-battle-field-guide.md),
자세한 의미 근거는 [필드 설명서](../docs/pokechamp-battle-field-guide.md)를 따른다.

새 관측 준비 기본값은 [observation](../integration/pokechamp/observation/__init__.py)의
`PREPARATION_DEFAULT`와 B/B2 prepare의 명시적 버전 봉인에서 확인한다. 범용 prompt 함수의
`DEFAULT_VERSION=v1.3.0`은 legacy 호환용이며 새 공식 준비 선택과 구분한다. D-031/EP-019의 v1.1.0은 당시 구현 범위이며 과거 명시 버전은 그대로 검증한다.

## 전달 표현과 B2 전송

`integration/pokechamp/improved_io/delivery/`는 현재 관측 생성과 live FixedBackend 사이에
자동 삽입되지 않는 별도 오프라인 변환/검증 경로다. 원본 전체를 기존 v2 schema·memory·
patch·state/request/bundle hash로 검증한 후 B0/B1/B2/B3를 선택한다.
원본 B0 prompt, 제외 목록, 공통 의미 설명서, 계산 scenario join·반복문장/배열 공유,
최근10결정 request 변경분 및 독립 역변환이 분리되어 있다.
`Delivery`는 system/user 문자열과 별도 원본 연결 로그를 제공한다. `capture_request`가
원본을 다시 검증하고 재생성 결과와 완전 일치를 확인해 최종 messages를 네트워크 없이 포착한다.
`audit-ex037`는 원본 bundle 봉인·actor/decision/event·최근10결정 window까지 대조한다.
후보 버전과 calculator-input-v2 의미 버전은 독립적이며 운영 selector·계산식·출력복구는 불변이다.
[설명·CLI·필드 매핑](../docs/pokechamp-b-prompt-optimization.md).

D-047/C-031의 opt-in 경로는 FixedPlayer의 검증된 전체 입력에서 EP-034 B2를 생성한다.
FixedBackend는 원본·B2·실제 문자열 일치를 검사하고 요청 전 `input_snapshot`을 필수 보존한다.
provider에는 B2 system/user를 보내며 원본은 출력 검증·복구에 사용한다. 요청 metadata의
`delivery_identity`와 `input_snapshot_event_seq`가 원본 및 실제 전달 trace를 연결한다.
뷰어/검토 inventory는 검증용 원본과 실제 전달 입력을 구분한다. 기존 정책의 전체 입력 전송은 유지한다.

## B2 선봉 선택

[D-052](decisions/D-052-llm-lead.md)/[C-033](CONTRACTS.md#c-033-llm-lead)의
`team_preview_study.py`는 기존 정책 hash를 보존한 새 `b2-llm-lead-v1` 준비·검증을 제공한다.
양쪽 actor는 B2이며 slot의 `actor_settings[].team_preview_policy`로 조건을 구분한다.
필드 부재는 기존 `seeded_random` 동작과 identity를 유지한다. actor 생성은 같은 `FixedPlayer`와
`FixedBackend`를 사용하고 기본 모델 설정은 바꾸지 않는다.

`team_preview.py`의 parent mixin은 공개 preview 알림 때 기존 Python RNG shuffle을 한 번 실행한다.
Pinned Player 생성자의 avatar 선택도 기존 RNG 소비에 포함된다. 자기 상세 request가 나중에 도착할 수
있으므로 양쪽 신호가 준비된 뒤 자기 제출 슬롯과 request를 대조한다. 입력은 자기 알려진 정보와
상대 공개 `poke` details만 포함하고 두 신호 이후 protocol/상대 객체·원팀을 읽지 않는다.

경기별 task 하나가 결정 context·선봉 요청·전송을 소유한다. `asyncio.to_thread`에서 기존 동기 Cloud
backend를 실행하고 event loop에서 완료를 기다린 뒤 선택 슬롯만 기존 순열 맨 앞으로 옮겨 전송한다.
중복 preview는 같은 task/결과를 재사용하며 중복 호출/전송하지 않는다. timeout·출력/전송 실패·취소는
명시적 실패이고 random fallback/재질의/대체 모델0이다. 취소 시 진행 호출의 보존·permit 반환을 기다린다.

`call_role=team_preview`의 실제 prompt·input identity/hash·원문/reasoning·검증·선택과 `wire_action`은
기존 recorder/viewer의 준비 결정에 연결된다. 자기 request와 공개 preview의 각각의 cutoff 및 두 신호의
완료 시점을 기록한다. `self_action`은 기존 B2 원본 검증·전달·출력복구를 그대로 거친다.
`POKECHAMP_LEAD_STUDY_ROOT`는 양쪽 요청을 기존 원자 예약/최초 시계/상한 코드에 연결한다.

prepare/verify는 호출0이며 실제 수집을 승인하지 않는다. 명시적 후속 실험 승인 후 등록 API가
EX/승인 근거 hash·고정 예산·source를 별도 실행 등록과 전역 study binding에 연결한다.
기존 actor/worker/backend 경로는 이를 검증하고 등록 부재·변조·동일 identity의 새 폴더를 거부한다.
[EP-040](exec-plans/completed/EP-040-llm-lead.md)의 구현·무유료 로컬 검증을 완료했으며
[EX-039](experiments/EX-039-b2-lead-proposal.md)는 종료·비교 미완료 상태로 보존한다.
D-055/EP-044의 EX-040은 봉인 실험 식별자에서 별도 protocol/binding을 선택한다.
EX-040의 첫429는 HTTP 응답 hook에서 halt를 기록해 다음 예약·HTTP admission·경기 제출을 막는다.
최초 시계는 별도 전역 hash binding으로 검증하며 기존 EX-039 binding/hash는 유지한다.
`team_preview_run.py`가 첫 대응쌍 기술 gate 후 나머지30을 같은 원장/시계로 실행한다.
`team_preview_report.py`가 선봉 조건별·완료쌍별 점수/누락·사용량과 기술 연결을 보고한다.
`a_diagnostic` 원자 예약의 선택적 hook은 C-033에서만 선봉/전투 결정 중복을 거부한다.

## 요청별 상세 효과 사전

[D-057](decisions/D-057-effect-reference.md)/[C-037](CONTRACTS.md#c-037-effect-reference)의
`effects/`는 pinned Showdown Gen9 Dex `desc` 자산과 B/B2·선봉 모델용 projection을 제공한다.
원본 관측·가설·계산은 유지하고 실제 전송 필드/최근 이력에서 등장한 item/ability/move를
요청별 `effect_reference`에 한 번 수록한다. 선봉의 상대 공개 종족으로 비공개 세트를 조회하지 않는다.
새 schema는 공통 타입을 한 번 렌더링하고 B2의 scenarios/result/shared_text 및 선봉 하위 필드까지 검사한다.
원본+선택 버전으로 전송 직전 재생성하며 일반 B와 선봉에도 input_snapshot/hash/identity를 연결한다.
viewer는 실제 문자열·프롬프트/사전 identity·원본 snapshot을 표시한다. 개별 gate도 원본을 전송 전에 파일로 봉인한다.

EX 미지정 새 선봉 준비는 `preparation_version=official-observation-v1`, 배틀 v1.4.0·B2 b2-official-v1·
선봉 v1.2.0의 독립 구성요소·사전 gen9-effects-v1을 봉인한다. 선봉 구성요소의 현재 선택 경계는
[C-040](CONTRACTS.md#c-040-lead-components)을 따른다. 이전 정책의 실행기/RNG/출력복구는 재사용하되
새 프롬프트 선택이 명시적으로 우선한다. 등록 EX·유료 예산은 없고 과거 실행 등록으로 전환할 수 없다.
과거 EX 지정·봉인은 기존 prompt/정책 hash를 유지한다. [자산·API](../integration/pokechamp/effects/README.md).

## 요약·독립 진단 경로

`summary_diagnostics/`는 운영 improved_io와 분리된 prepare/run/report 경로다. EX-020 archive의
H0 복원과 H1–H3 변환, 독립 truth, 호출별 process/backend, 영속 clock·intent·응답 선봉인을 사용한다.
입력/평가 실패 halt에서는 효과 추정을 차단하고 비용·실패 근거·미완료 분모를 보존한다.
`memory.summary_context/summary_window`는 live actor와 Cloud에 같은 구간 의미를 제공하며
원문·주석은 현재 window만 전송한다. `prompt_versions.py`가 원본/후속 버전의 byte·hash를 연결한다.
`review_gate.py`는 응답 검토 후에만 같은 연쇄의 후속 입력을 구성하고 기존 halt·시계·receipt를 보존한다.
`maximum.py`의 고정 이전메모리는 이번 응답을 다른 호출의 입력으로 재사용하지 않는다.
`compat.py`는 원본 SDK를 보존하며 max 직렬화와 HTTP 본문 포착을 담당한다.

| 특정 진단·운영 경로 | 구현·검증 한계의 원문 |
|---|---|
| D-019/D-022 A/B/C 단계 receipt·offline/Cloud gate | [EP-011](exec-plans/active/EP-011-improved-io.md), [EX-020](experiments/EX-020-resume-io.md) |
| H0–H3 독립 요약 진단, weather 입력/기준 오류 | [EX-021](experiments/EX-021-summary-harness-diagnostics.md) |
| 상태 의미·low/high 및 공개 특성 입력 교정 | [EX-022](experiments/EX-022-state-summary-thinking.md) |
| 후속 window·공개 item 입력 교정 | [EX-023](experiments/EX-023-continue-io.md) |
| 요약 prompt 버전별 검토 연쇄 | [EX-024](experiments/EX-024-low-summary-prompt-reexperiment.md) |
| low/max 고정 메모리, 실제 전송 입력의 필수 사실 도달성 미보장 | [EX-025](experiments/EX-025-summary-max-diagnostic.md) |

과거 입력·기준 실패/무효/중단 자료는 현재 source와 구별한다. 수정된 의미 검사로 과거 입력을
정상으로 인정하거나 이미 실패한 gate를 통과로 바꾸지 않는다.

## 실험 정책별 실행 연결

`battle_only.py`는 요약 없는 A/B, `battle_only_budget.py`는 원자적 HTTP 전 예약과 최초 시계를
관리한다. `battle_only_recovery.py`는 기존 halt를 보존한 평가 교정과 영향 대응 재수집 경로를 구분한다.
지원·허용 범위는 선택한 정책과 기존 receipt에 한정되며 공통 예산 초기화·중복 제출을 거부한다.
`experiment_policy.py`는 정책 정의/hash를 manifest·execution·actor·receipt·원장·보고서에 연결한다.
정책 부재와 명시 정책의 gate/상한을 혼용하지 않으며 C-029는 새 execution 동시성에만 우선한다.
`direct32.py`는 별도 정책의 준비 봉인에서 본32판으로 연결한다. FixedBackend는 원출력 계약 판정과
행동 복구 결과를 분리하고 실제 send trace에 출처를 기록한다. `observability/issues.py`는 source 밖
annotation을 검증해 viewer에 연결한다. 새 기본 IO 설명 검토 제외는 [C-032](CONTRACTS.md#c-032-io-explanation-review)를 따른다.

| 정책별 연결 | 원문·실행 당시 한계 |
|---|---|
| D-030 요약 없는 A/B 및 평가 e1 | [EX-026](experiments/EX-026-io-battle-only.md) |
| D-032 명시 null 상한·기술/설명 판정 분리 | [EX-027](experiments/EX-027-battle-guide-live.md) |
| D-033 direct32와 출력 복구 | [EP-021](exec-plans/completed/EP-021-battle-guide-direct32.md) |
| D-036 inputfix32, v2/실제 요청 identity | [EP-024](exec-plans/completed/EP-024-calculator-inputfix32.md) |
| D-038 movefix32, 기준 source 봉인과 변경분 연결 | [EP-026](exec-plans/completed/EP-026-battle-guide-movefix32.md) |
| D-039 외부 환경 보고 후 새 identity 반복, 각 실험 자체 사용량만 합산 | [EP-027](exec-plans/completed/EP-027-external-memory-repeat32.md) |

`ab_head_to_head.py`가32행/16대응쌍·정책·팀/source를 봉인하고 EX-035의
`a_diagnostic.run/reserve/collection_deadline/inspect_batch`를 명시적 protocol 인자로 재사용한다.
기존 A-only 기본 경로의 정책 identity와 A/B 대 기준봇 경로는 유지한다.
`benchmark.actor_condition`은 새 `actor_conditions`에서 진영별 A/B를 읽고, 필드가 없으면
기존 경기 단위 `condition_id`를 사용한다. 각 actor는 별도 process·관측·계산기·bundle을 쓴다.
A는 upstream IO, B는 기존 battle-v1.2.0/calculator-input-v2/mechanics-v2와 출력복구다.
`POKECHAMP_AB_HEAD_TO_HEAD_ROOT`가 양쪽 Cloud 요청을 같은 원자 예약 원장에 연결한다.
`ab_head_to_head_report.py`는 조건/진영별 결과와 양쪽 모든 결정의 실제입력/원응답/선택/전송을
기록하고16대응쌍의 B점수 및 불완전쌍 누락을 보고한다. Method `io`로 조건을 합산하지 않는다.

## 상속 시스템과 미정 목표 아키텍처

상속 AgenticSTS는 game/mod HTTP·SSE → typed state → AgentLoop → L1/L2 prompt·L3 knowledge·
L4 memory·L5 skill → backend/검증 → action → gated postrun 흐름이다. SSE 불가 시 polling을 쓰며,
monitor EventBus/WebSocket은 별도 관측 경로다. CombatConversation의 외부 메시지는 시작 cache anchor,
`ok` anchor, 최신 self-contained user state이고 이전 round plan을 다시 보내지 않는다.

Mod는 직렬화/action 실행, `src/state/`는 typed boundary, `src/storage/paths.py`는 dynamic store의
path authority를 소유한다. 정적 L3는 Python component에 남고 frozen comparison store는 새 mutable
실험의 쓰기 대상이 아니다. 세부 module·입출력·dependency는
[상속 아키텍처](../AgenticSTS/docs/reference/ARCHITECTURE.md)와
[repository layout](../AgenticSTS/docs/reference/REPO_LAYOUT.md),
[Python dependency](../AgenticSTS/pyproject.toml)를 따른다.

PokéChamp qualification은 Python3.11.11·uv0.12.9·Node18+/npm·pinned submodule·local disk30GiB 이상을
전제로 한다. Cloud에는 direct Ollama Cloud credential이 필요하지만 local battle에는 필요하지 않다.
상속 game/mod 재빌드는 적법한 game 설치본·.NET9·Godot/Harmony/game assembly가 필요하다.

L1-L5의 `pokechamp` layer mapping과 treatment architecture는 여전히 **TBD**다. D-007의
qualification environment는 채택됐지만 이를 목표 treatment architecture로 해석하지 않는다.
상속된 모든 TODO, roadmap, Future Work, 날짜가 있는 plan은 현재 planning에서 제외한다. 새 목표
아키텍처는 새 연구 목표를 승인한 뒤,
추적 가능한 [`decision`](DECISIONS.md)과 exec plan이 변경을 정의할 때만 도입할 수 있다.

## D-056 공급자 기본 동시성과 EX-041

`execution.py`는 새 준비의 공급자별 기본값을 선택하며 Z.ai 준비는4·zai-default4-v1을 봉인한다.
A 진단·A/B 직접대결·선봉 정책 준비 CLI/API가 공급자 선택 후 이 결정을 사용한다.
실행/검증/보고는 현재 환경의 기본값이 아닌 봉인 선언을 읽으며 기존 표식도 검증한다.
`team_preview_study.py`의 EX-041 protocol은 별도 binding/원장/최초 시계와 동시성4를 사용한다.
첫429/model halt와 admission은 봉인 식별자로 선택한다. EX-039/040 protocol과 기존 binding은 보존한다.

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
connect-retry-v1/legacy와 과거 실행 봉인은 유지한다. 현재 구현·검증은 [EP-049](exec-plans/completed/EP-049-provider-retry-viewer.md)를 따른다.

## EX-042 공급자별 큐와 공유 수집 상태

`distributed_lead.py`는 EX-042의 버전·공급자 배정·worker별 설정을 관리한다. 선봉 CLI는 기존 준비/검증/등록/보고에서 이 식별자를 선택한다. coordinator의 공급자별 배틀 큐·독립 broker와 공통 원장/최초 시계/halt가 분리된다. 공급자 선택은 worker 입력/환경 복사본으로 전달하며 coordinator의 전역 선택을 교체하지 않는다. 과거 단일 공급자 경로·정책 hash를 유지한다.

정상 경기 목록 CLI는 봉인된 matches/summary에서 유효 경기만 읽고 기존 actor viewer/replay에 상대경로로 연결한다. EX-042 index 신규 생성은 기존52 viewer와 source/봉인 파일을 변경하지 않는다.

## 선봉 전략·Dex 규칙 구성

`lead_rules/`는 기존 `team_preview.build_input`의 완성된 자기 제출·공개 cutoff 입력만 받는다.
고정 Gen9 Dex/OU validator 추출 자산을 별도로 읽어 슬롯 기술 metadata와 종/폼 규칙·주변적 가능성을 추가한다.
`effects/`의 기존 상세 desc와 합쳐 요청별 ID 중복을 제거한다. 새로운 opponent actor/원팀/이후 기록 접근은 없다.
`team_preview_study`는 두 옵션과 결합 identity를 봉인하고 `FixedBackend`는 전송 직전에 같은 구성요소로 재생성한다.
원본 snapshot·요청 원장·wire와 보고에 같은 version/hash를 연결한다. B2 배틀 경로는 그대로이며 옵션 없는 과거 준비는 당시 봉인을 사용한다.

## EX-043 교정 B2 비교

분산 준비·CLI·실행·원장 경로는 EX-043을 별도 식별자로 선택한다. namespace 일정과 matchup-v2/dex-v2, provider-retry-v2를 봉인하고 과거 EX-042 분기는 유지한다. `diagnostics/corrected_lead.py`가 EP-051 공개 cutoff 재생과 독립 사실 감사를 경기 종료 뒤 수행하며 다음 슬롯 진입 전에 실패를 전체 halt로 연결한다. 실행 완료 판정에32개 감사 receipt를 요구한다. 온라인 감사는 별도 프로세스 그룹에서 실행하며 정리 기한60초 전에 제한한다. 제한 시 부분 자료를 보존하고 자원 정리 후 별도 출력으로 오프라인 감사를 완료한다.

## EX-044 직접 본실험 연결

EX-044는 EX-043의 교정 선봉·입력 감사 실행기를 재사용하고 별도 study/clock binding을 가진다. D-065에 한정해 preflight skipped_by_user receipt를 허용한다. 감사 subprocess는 POKECHAMP_ROOT cwd에서 실행하며 이전 중단 자료를 변경하지 않는다.

## 플레이어별 관측 tracker 진단

`diagnostics/observation_run.py`는 기존 worker/recorder/격리 서버로 Abyssal 관측을 수집하고
메시지 순회의 결정 직전 행 위치를 별도로 기록한다. `observation_compare.py`는 각 actor의 동일
prefix를 현재 parser와 고정 공식 headless client에 재생하고 B2 관측 투영·원문·최초 차이를 연결한다.
`observation_client.cjs`는 기존 고정 서버의 공개 Dex와 공식 client TS를 별도 build로 사용하며 서버
자동 갱신이나 운영 입력 교체를 수행하지 않는다. 실제 과거 B2 전송 관측도 대조하지만 계산·전송·
행동 선택은 진단 범위 밖이다. [명령·출력 의미](../integration/pokechamp/diagnostics/observation-comparison.md)와
[EP-055 결과·지원 한계](exec-plans/evidence/ep055/report.md)를 참조한다.


## 공식 관측의 B/B2 운영 경로

D-066/C-043의 `observation/`은 EP-055 어댑터에서 분리한 운영 모듈이다. 고정 client TS와
공개 Dex 빌드·설치 의존성·서버 dist를 검증한 후 actor별 Node를 만들고 battle별 증분 상태를 둔다.
`observability.player`가 원문을 기록한 뒤 기존 parser의 실제 행 순회에 cursor를 연결한다.
`FixedPlayer`는 해당 event/행 경계에서만 공식 상태를 얻고 동일 관측으로 prior·계산·모델 입력을 만든다.
자기 request/세트와 상대 공개 상태·종 추론·미확인을 구분하며 소비/기간/억제/지연 이력만 같은
원문에서 출처를 명시하여 보완한다. legacy Battle 객체 상태를 병합하지 않는다.

공식 choice와 요청 조건으로 검증한 후보는 숫자 슬롯 그대로 제출한다. 선봉 정책과 RNG는 유지한다.
`observation_snapshot`에 원문 경계·공식 상태·계산 전 정규화를 남기고 `input_snapshot`·
`llm_call`·`wire_action`에서 계산·실제 system/user·제출을 연결한다. 최근10결정 창의 첫 프레임을
자르면 `line_offset`이 원래 행 번호를 보존한다. 증분/전체 재생은 별도 검증 경로에서 대조한다.
Node 오류·기한 초과·경계/빌드 불일치·미지원 상태는 입력 중단이며 자동 legacy 대체는 없다.

새 B/B2 prepare는 `official-client-v1`과 빌드 identity를 명시적으로 봉인한다. 필드 부재는
legacy, 과거 EX 지정은 당시 소스이며 upstream/Abyssal/C는 전환하지 않는다. 관측·전달 버전과
계산 의미 버전은 독립이다. [운영 안내](../integration/pokechamp/observation/README.md)·
[EP-056 검증과 viewer](exec-plans/evidence/ep056/report.md).

## EX-045 공식 관측 분산 비교

분산 실행기가 EX-045에만 공식 backend/build·v1.4.0/b2-official-v1을 준비·등록·worker·요청에 연결한다.
`diagnostics.official_cutoff`는 actor별 기록 행까지 공식 증분/전체 재생 후 정규화·계산·실제 입력·
원장/응답·숫자 슬롯을 대조한다. 자기 request와 공개 원문 사실·미확인 보존도 독립 검사한다.
coordinator는 official-cutoff-v1 receipt 통과 전 해당 자리에 다음 경기를 제출하지 않는다.
`diagnostics.official_lead`는 동일 coordinator의 fake 전용 첫4 제한과 경기당600초 상한으로
본 일정의 첫 공급자별 대응쌍을 검사한다. 과거 EX-043/044의 public-cutoff-v1은 보존한다.

EX-045에서 시간 제한 후 비동기 queue 처리와 wrapper 즉시 소비 검사의 불일치가 드러났다.
[D-068](decisions/D-068-official-async.md)/EP-058 연결부는 headless scene의 NaN interruption counter를
정상 초기값1로 두고 공식 atqueueend와 queue 위치를 함께 기다린다. 자기 request 앞·마지막 행의
종료 경계를 보장하며 Node 명령 직렬화·타이머 예외 실패 폐쇄·요청 전체30초를 적용한다.
upstream/build·schema·계산 의미는 유지한다. [EP-058 검증·보고](exec-plans/evidence/ep058/report.md)를 완료했으며 과거 수집
source와 중단 판정은 [EP-057 최종 보고](exec-plans/evidence/ep057/final-report.md)에 보존한다.
별도 fake 전용 ep058-local-eight 진단은 후속 공급자별4경기씩 동시에 실행하고 본 gate를 만들지 않는다.

## JEV provider 재시도 (D-084)

새 JevClient/Session/StudySession 기본은 jev-provider-retry-v1(최초+3회)이다.
Session이 각 시도를 예약·기록하고 단일 전송 client를 사용한다. 동일 payload/모델/endpoint와
기한/취소/누적 상한을 유지한다. 감사는 논리 결정과 물리 시도를 구분하며 과거0회 해석도 유지한다.
EX-053 등 고정 과거 유료 실행은 legacy를 명시한다. 새 수집 등록/receipt를 대신하지 않는다.

EX-054는 별도 실험 선택과 receipt에서 EX-053 일정/처치·EX-052 기준선·재시도3회를 결합한다.
물리 HTTP 시도와 논리 요청·회복/소진을 분리 집계하고 새 뷰어의 기술 기록에 시도별 원문을 포함한다.

## D-088 EX-056 직접 본실험

jev_study의 명시 EX-056은 EX-054 봉인 일정을 직접 읽고 별도 entry-record.json으로 사전 검사 생략과 실행 identity를 보존한다. 기존 receipt 경로와 구분하며 첫4 gate 없이 순차 수집·경기별 감사를 수행한다.

## D-089 EX-057 모델 고정 본실험

jev_study의 EX-057은 EX-056 봉인 일정과 jev-1.13.0 설정을 결합한다. jev_comparison은 EX-057에 한해 요청 모델명 고정을 명시적으로 허용하고 전후 요청/반환 모델을 기록한다.

## D-094 EX-058 개선 입력 연결

별도 [D-130](decisions/D-130-jev27b-ex058-reproduction.md)의 `integration/jev27b/`는 기존
v4 입력·명령·계산기를 재사용하고 공개 JEV-27B를 loopback Choice 서버에 연결한다.
공식 bare formatter·BF16 backbone/병합 어댑터·FP32 head/보정값을 사용하며, 로딩 I/O는
호스트 상한을 위해 Transformers의 순차 safetensors pread로 처리한다. 설치 환경과 가중치
내용은 바꾸지 않는다. SQLite 요청 원장이 동일 ID/본문의 중복 추론을 막고, 실험 전용
Session은600초 통신 감지·경과시간 상한 null·경기 실패 격리·전수 감사를 제공한다.
진입 gate·자원·중단/비교 원문은 [EX-082](experiments/EX-082-jev27b-ex058-reproduction.md)다.

jev_v4.Adapter는 EP-093 생성기를 그대로 호출하고 state.version만 jev-choice-v4로 바꾼다.
Session이 계산기·역할 DB·추천 세트 캐시를 소유하고 입력 생성은 asyncio.to_thread에서 처리한다.
JevPlayer는 자기 제출 팀 문자열만 전달한다. 계산/로그 감사는 input-audits의 별도 gzip 파일과
입력 이벤트의 hash로 연결한다. 감사기는 actor cutoff를 재생하고 같은 자기 팀으로 재산출한다.
실험 전용 EX-058은4사례 receipt 후1요청 probe를 수행하며 최초 wall/monotonic 시계를 본수집에
계승한다. 주 비교는 EX-057이고 기본 v3 경로·과거 실험은 유지한다.

## D-095 EX-059 자기 벤치 축약 연결

jev_v5는 v4의 비동기 어댑터·계산기/자료 캐시·probe를 재사용하고 compact=True와 별도 버전을
고정한다. 실행/재생 감사는 버전에 따라 상세/축약을 명시 선택하며 세션 중 처치 변경은 거부한다.
EX-059는 EX-058 봉인 일정과 팀을 연결하고 비교기는 v4/v5·축약 여부·고정 자료/지시문 일치를 검사한다.

## D-097 EX-060 한 경기 분기 수집

`integration/pokechamp/branch_rollouts`는 EX-058의 원관측·명령을 읽어 pinned local
simulator에서 원경기를 재현하고 결정별 simulator/actor snapshot을 별도 보존한다.
normal decision은 양측 제출 전, 턴 중간 교체는 이미 확정된 choice와 queue를 유지한다.
원경기 각 suffix 재생 검증을 통과한 root만 후속 분기의 출발점이 된다.

Node simulator는 `pokemon-showdown/dist/sim`을 사용하며 public/actor 채널을 분리한다.
오프라인 Python Actor는 기존 Abyssal의 관측·정책·Python/NumPy RNG를 독립 보존한다.
분기마다 미래 simulator/actor RNG를 교체하고 자기 후보를 강제한 다음 양측 Abyssal로
진행한다. 신규 JEV/API 호출은 없다. parent 원장은 시도·누적 시계·4 worker 제출을 소유한다.

원자료·private snapshot·후보/반복별 trace와 학습용 export는 저장 경계를 구분한다.
`training.jsonl`은 당시 실전 관측·행동·조건부 통계만 전달하고 비공개 상태와 미래 난수를
포함하지 않는다. 보고/뷰어는 후보별 분모·검열·오류·미실행·대체 기록을 보존한다.
구체적인 조건과 결과는 [EX-060](experiments/EX-060-single-battle-branch-rollouts.md)을 따른다.


## D-098 EX-061 후보별 행동가치 학습

EVE 독립 worktree의 `rlcd/pokemon_data.py`는 EX-060 봉인 통계/anchors/rollouts를
읽기 전용 대조하고 `inputs.jsonl`과167개 soft target `records.jsonl`을 분리한다.
`rlcd/pokemon_value.py`는 Qwen 비사고 chat template으로 무절단 토큰을 준비하고,
공식 text-only backbone 마지막 hidden에서 A/B 두 LM head 행만 읽는다.
기존 EVE 정수 answer loader·bandit training은 변경하지 않는다.
LoRA gradient를 후보 평균·관측별 update로 계산하고 baseline/epoch/reload 예측을 별도 보존한다.
EX-061 학습 자체에는 실제 배틀이 없었으며 실시간 연결은 아래 D-099 경로가 담당한다. 독립 배틀 성능은 미평가다.
[코드 안내](../.tools/eve-rlcd/worktrees/pokemon-training/docs/POKEMON_ACTION_VALUE.md) ·
[동결 protocol](experiments/EX-061-qwen-action-value.md).

## D-099 EX-062 실시간 후보별 행동가치

`integration/pokechamp/qwen_server.py`는 EVE 가상환경에서 EX-061의 InputExample/render/ValuePolicy를
재사용하고 GPU1의 고정 base+LoRA를 한 번 로딩한다. 표준 HTTP 서버의 loopback8765에서
health와 후보별 evaluate를 제공한다. GPU lock·무절단 입력·eval/no_grad·전후 fingerprint를 유지한다.
`qwen_player.py`는 기존 JEV 플레이어의 공식 관측·cursor·actor 경계를 상속하고 JEV v4 전문을
HTTP 입력으로 전송한다. 후보별 q 최댓값과 원순서 동률로 선택하며 새 rqid를 lock 앞에서 감지한다.
`qwen_battle.py`는 고정 Metamon2팀/seed의 진영교환2경기를 순차 실행하고 Qwen/Abyssal actor를
각각 독립 프로세스로 분리한다. 소유8109 worktree·타이머 off·재시도0·전체 시간 상한 없음을 적용한다.
`scripts/pokechamp-qwen`은 start/status/stop/probe/battle을 제공한다. 전수 감사는 `qwen_audit.py`,
오프라인 후보별 q+리플레이 내보내기는 `qwen_viewer.py`가 담당한다.
조건·완료/중단과 해석 원문은 [EX-062](experiments/EX-062-qwen-local-battle.md), runtime은
[C-049](CONTRACTS.md#c-049-qwen-local)이다. 기존 JEV 프로필·봉인·Blocked 실험은 보존한다.

D-102의 명시 입력 `qwen-candidate-state-v1`은 `qwen_temporal.Adapter`가 기존 JEV v4
생성기와 계산기를 재사용하고 결정별 instructions, 공개 교체 맥락, 동일 세트별 후보 전이를
추가한다. `diagnostics/candidate_state.py`가 정수 HP·능력치·테라·지원되는 진입 효과를
시간순으로 적용하고 미지원 전이는 사유와 unknown으로 남긴다. 큰 후보 결과는
`state.candidate_evaluations`에 한 번 두고 action ID로 참조한다. 공통 열과 수치 행 및 원문
설명 참조는 무손실 투영이며 원 구조·정수 roll·세트 가정은 외부 계산 감사에 보존한다.
`decision_instructions.compose`는 해당 결정 절차＋새 공통 규칙＋원 instructions 전문을
결합한다. 기존 q renderer와 A/B readout은 변경하지 않는다.

서버는 `--candidate-state`에서만 새 버전을 허용하고 `--diagnostics`에서만 별도
`/diagnose`를 제공한다. `qwen_diagnostics.py`의 짧은 JSON 예측은 같은 base＋LoRA의
별도 생성 결과이며 q 입력·선택·전송으로 되먹이지 않는다. `qwen_state_study.py`는
EX-063 actor cutoff의 원입력·지침만 변경·입력도 보완한 세 조건을 무전송 재생하고,
`qwen_state_run.py`가 동결 파일 검사·소유 서버·누적 기한·진단 전후 q 대조·정리·봉인을
관리한다. 계산 지원·진단 정확성·후보 순위·비용의 실행 원문은
[EX-064](experiments/EX-064-qwen-candidate-state.md), 계약은
[C-050](CONTRACTS.md#c-050-qwen-candidate-state)이다.

## D-100 EX-063 학습 원대진 실전 진단

Qwen runner는 EX별 schedule/probe/출력 원장을 선택한다. EX-063은 봉인된 원 battle-19와
공개 preview를 대조하여 원 team6/team2의 성별만 완성하고 원seed/진영으로 한 경기를 실행한다.
서빙·JEV v4·감사/뷰어 경로는 C-049를 재사용하며 기존 EX-062 source snapshot은 유지한다.

## D-101 결정 이름 표시

Qwen/JEV viewer builder는 공통 `viewer_assets/action-labels.js`를 HTML 안에 포함한다.
후보의 move_ref와 해당 결정 self_team/current_move_slots에서 기술명을, 후보 설명에서
교체/선봉 대상명을 해석하고 테라 여부를 표시한다. 원 JSON/ID/명령/q와 실행 의미는 유지한다.
EX-063 현재 링크는 새 표시이며 이전 봉인 내보내기는 ex063-v1에 연결한다.

## D-103 EX-065 공동 q 데이터 경로

`integration/pokechamp/joint_q/`는 reviewed108의 고정20상대·p2 고정 팀/80seed manifest,
공식 관측 root·별도 관측 추적 후속 actor, 원경기 전체/모든 root 다음 경계 재현을 제공한다.
프로세스 재사용·불변 root 캐시·내용 해시 정적 blob·RNG 결정 경계 checkpoint와 SQLite WAL
원장은 논리 rollout과 기술 시도를 구분한다. `serializer.JointInput`만 렌더링하고 `data.TrainingRecord`의
타깃은 분리한다. 입력/타깃/후보별 export·CPU tokenizer·감사/파일럿 gate는 동일 EX 루트에 보존한다.
계약은 [C-051](CONTRACTS.md#c-051-joint-q), 실제 검증·수집 상태는 EP-107/EX-065를 따른다.

## D-104 EX-066 Base 공동 q 학습 경로

`integration/pokechamp/joint_q/learning/`은 EX-065 공개 로더와 JointInput을 재사용하는 별도
학습·오프라인 평가 경로다. 새 renderer는 공식 Base chat template 뒤 후보별 ACTION_ID/Q_VALUE=
위치를 추가하고 명시 token position을 ID에 연결한다. `JointValuePolicy`는 공식 text backbone의
한 forward 결과에서 모든 후보 hidden state를 읽어 공유 FP32 head의 독립 sigmoid q를 반환한다.
text LoRA/head와 frozen BF16 base를 분리하며 기존 A/B 서빙 모델과 수집 코드는 유지한다.

`scripts/pokechamp-joint-q`는 EVE Python/물리 GPU1에서 prepare/preflight/train/evaluate/verify를 제공한다.
GPU2 사용 중 유휴 GPU 대체라는 D-106 지시에 따라 실행 자원을 고정했다.
준비 토큰/소스·데이터·Base/tokenizer 해시, 완전 optimizer/RNG/cursor checkpoint, validation
선택·새 프로세스 재로딩, test 잠금/모델별1회 예약과 저장 예측 분석을 연결한다.
조건·분모·복구·해석은 EX-066, runtime은 C-052, 실제 검증·실행 상태는 EP-108이 소유한다.

### D-129 EX081 공동 q 체크포인트 배틀 경로

`joint_q/battle_eval/`은 원 epoch3·학습 renderer를 읽기 전용으로 재사용한다. EVE GPU0 서버는
관측당 공동 q를 직렬 평가하며 독립 health endpoint로 모델/프로세스/소스 식별자를 제공한다.
두 별도 프로세스의 전체 validation 재현 후 마지막 프로세스를 유지하여 native CPU player와
loopback으로 연결한다. 원 test20 manifest·공식 JointInput 생성·전송 직전 rqid/합법성 검증을
재사용하고 별도 admission/누적 시계·모든 raw I/O·독립 감사/뷰어를 새 실험에 보존한다.
조건 원문은 EX081, runtime은 C-062, 진행은 EP-133이다. 기존 learning/Kev 경로는 유지한다.
`outputs.correct_baseline`은 원 보고/입력 감사의 해시를 보존한 상태에서 같은 역사 실험 계보의
version-sealed capture 링크를 읽어 비교만 정정한다. 뷰어는 선택한 final receipt에 원자료를
결합하고, 이동 후 DOM 준비를 기다려 모든 입력/q/전송을 오프라인 검증한다.

## D-108 Kev r1 실시간 연결

`kev_player.InputGenerator`가 기존 `joint_q.serializer.generate`와 원 Dex/Smogon/RoleDB를
공유하여 validation/live 입력을 생성한다. `kev_value`는 payload_json 문자열과 학습 문구의
후보별 noul 질문을 loopback `/v1/systemone`에 전달한다. 플레이어는 모든 후보 확률을 검증한
후 원순서 최대값을 고르고 rqid/합법 목록을 재검증한다. 단일 후보도 호출하며 대체 선택은 없다.

`kev_acceptance`는 validation3관측의 bytes와 저장 development 예측을 순차 gate로 확인한다.
`kev_control`은 서버를 시작하지 않고 로컬 checkpoint/head·Base 캐시·프로세스/GPU3와 준비
receipt를 대조한다. `kev_battle`은 EX-065 자기 packed 팀을 그대로 제출하는 Kev-p2와
새 reviewed108 상대의 Abyssal-p1을 별도 CPU 프로세스/소유 Showdown에서 한 번 실행한다.
모델 생성기에는 원 own.text만 전달하며 제출 형식과 구분한다. 원문 전송 기록의 전수 감사와
휴대 가능한 열람본은 `kev_audit`/`kev_viewer`가 담당한다. 수락 검사의 실제 완료 여부는
[EP-111](exec-plans/completed/EP-111-kev-battle.md), 조건은 EX-068, runtime은 C-054를 따른다.
재진입 명령·서버 승인 경계는 [Kev 안내](../integration/pokechamp/KEV.md)에 있다.

D-110의 `kev_main`은 이 worker·입력/선택/감사 경로를 재사용하여 EX-065의 원 test20 대진을
순차 실행한다. 양 packed 팀·simulator/actor seed·원순서를 동결하고 각 경기의 별도 Session과
전역 admission·시간 상한·판단 오류 경기 격리를 관리한다. 추가 사전검사는 사용자 지시로
생략하며 실제 진입의 동일성 확인과 경기별 원자료 감사/봉인은 유지한다. 전체 결과와
역사 기준선 분석·20경기 열람본은 [EP-112](exec-plans/completed/EP-112-kev-test-battles.md)와
[EX-069](experiments/EX-069-kev-test-battles.md)를 따른다.

D-111의 `kev_continuation`은 EX-069 첫 대진만 가져오는 전용1회 실행기다. 명시적
`kev-continuation-noul-v1`을 설정→기존 worker→Session→HTTP 생성/검증에 전달한다.
state/후보/명령과 기존 프로필 기본값은 유지하며 독립 감사·뷰어는 선언별 질문을 대조한다.
CPU receipt·소스/질문/모델 동결 후 감독 프로세스가 GPU3 소유 서버·수집 자식과 누적 시계/
정리 여유를 관리한다. 전역 시작/경기 admission으로 출력 경로를 바꾼 반복을 차단한다.
조건과 해석은 [EX-070](experiments/EX-070-kev-continuation-question.md)을 따른다.

## D-107 EX-067 Abyssal Tera 보완 수집

`abyssal_tera.py`의 관측 전용 정책은 기존 선택1회 뒤 고정 공격·방어 규칙으로 주문을 바꾼다.
`joint_q.Actor`는 opt-in policy ID/config와 공개 기술 추적을 원경기·후속·snapshot·재개에 유지한다.
과거 metadata 없는 actor는 기존 Abyssal이다. 강제 첫 후보의 p2 정책 호출은0이다.
`tera_config.py`는 별도 seed namespace를 제공하고 `tera.py` CPU 실행기는 단계별 gate를 강제한다.
판단 사유/원자료와 JointInput을 분리하며 기존 EX-066 봉인 소스/로더/환경은 보존한다.
`tera_inputs.py`는 공개 prefix의 팀별 Tera 소모를 현재 개체 표시와 구분하여 입력에 보존한다.
`tera_recovery.py`는 첫 파일럿 입력 결함의 원자료·소스·최초 시계를 보존하고,
정책/seed 불변과 독립 검증 receipt를 확인한 `public-tera-v2`만 준비한다.
감사·뷰어/복사 경로는 `tera_verify.py`·`tera_outputs.py`, 상세 실행은 [전용 안내](../integration/pokechamp/joint_q/TERA.md)를 따른다.

## D-113 EX-071 리플레이 모방 학습 경로

`integration/pokechamp/imitation/`은 기존 q 학습·서빙과 독립된 Choice 정책 경로다.
`dataset`이 원본·역사 평가팀 제외·연결 그룹 분할·보완 통계·새 대진을 동결하고,
`metamon_bridge`가 별도 Python3.11 CPU 환경의 pinned parser와 JSONL로 통신한다.
`impute`는 공개된 원래 세트와 일치하는 합법 corpus 세트를 결정적으로 보완한다.
`replay`의 결정 직전 prefix와 공식 실배틀 관측은 같은 `schema.from_snapshot`을 거쳐
`pokemon-imitation-input-v1`이 된다. 정답·승패·이름·출처는 감사 영역에만 보존한다.

`model`은 고정 Kev Choice readout과 새 LoRA/head의 unmerged 정밀도를 공유하며,
`learning`은 최초 시계·업데이트 예산·부분 경사를 포함한 재개·validation 선택·test 잠금을
담당한다. `serving`과 `player`는 저장 확률의 HTTP 대조, 안정된 행동 ID와 실제 명령 슬롯,
전송 직전 rqid/합법 후보 확인으로 이어진다. `battle`이 소유 Showdown/actor/서버의
고정40 slot을 관리하고 `reporting`·`viewer`가 전체 분모와 행동 선택 확률을 표시한다.
`verification`은 CPU 의존성과 실제 validator/Dex 소스·검사 증거를 GPU gate에 묶는다.
진입점은 `scripts/pokechamp-imitation`이며 구현/운영 안내는
[imitation README](../integration/pokechamp/imitation/README.md), 실제 검증·실행 상태는
[EP-115](exec-plans/completed/EP-115-qwen-replay-imitation.md)를 따른다. 첫 학습·잠긴 test·
40경기와 오프라인 뷰어까지 완료했으며 실행 소스와 실제 산출물은 해당 완료 기록에 연결한다.

## D-114 EX-072 자기대국·확률 보정 경로

`integration/pokechamp/selfplay/`은 EX-071의 입력·후보/명령 경계와 BF16/FP32 정밀도를
재사용하는 별도 학습 경로다. `prepare`가 제외 구성·새 팀 split·BC와 전체 대진/seed를 동결한다.
`model`의 한 backbone forward가 행동 정책과 W/D/L head를 계산하며 `serving`은 동결 snapshot을
순차 교환하여 temperature1 categorical 선택과 원 분포를 반환한다. `player`/`battle`은
소유 Showdown·두 actor의 전송 증거와 정상 종료를 독립 감사하고 지정 learner의 결정만 연결한다.

`trainer`는 라운드별 새 rollout의 PPO/WDL과 EX-071 train BC를 별도 평균한다. 정책 선택 뒤에는
동결한 표현으로 WDL head만 보정한다. `runner`는 후보 dev·head 채택·잠긴 test까지의 상태를,
`execution`은 UUID 고정 GPU·최초 시계·원자적 완료 step checkpoint·SIGTERM 재개와 정리를 관리한다.
`reporting`은 경기/상대 가중 확률 지표와 팀쌍 bootstrap을 계산하고 `finalize`/`viewer`는
원자료·필수 검증·이동 후 오프라인 재생 gate를 통과한 산출물을 봉인한다.
진입점은 `scripts/pokechamp-selfplay`, 운영 안내는 [selfplay README](../integration/pokechamp/selfplay/README.md)다.
조건은 [EX-072](experiments/EX-072-selfplay-rlcd.md), runtime은 [C-056](CONTRACTS.md#c-056-selfplay),
실제 진행과 검증은 [EP-116](exec-plans/completed/EP-116-selfplay-rlcd.md)이 소유한다.

EX-072의 동결 최종화에서 브라우저 의존성 누락과 JavaScript 큰 정수 직렬화 문제가 발견되어,
[EP-117](exec-plans/completed/EP-117-selfplay-finalization-recovery.md)의 별도 CPU 정정 경로를 사용한다.
`scripts/pokechamp-selfplay-finalization-v3.py`는 원 봉인·시계·통계와 실제 검증 증거를 확인하고,
`scripts/selfplay_viewer_exact_json.py`는 새 export의 원문 패널·복사·다운로드만 정확한 Python JSON
문자열로 교정한다. 원 검증기는 그대로 사용하고 원 자료·source freeze·실패한 최종본은 보존한다.
정정 산출물의 상태는 `corrections/latest.json`이 연결하며 원 `completed.json`의 당시 판정을 덮어쓰지 않는다.

## D-116 EX-073 Abyssal 전용 동기 4GPU 경로

`integration/pokechamp/abyssal_rl/`은 EX-072 원본을 보존한 별도 실행기다. prepare가
EX-071/072 및 원 replay 구성을 제외한 split·가능 슬롯·원 BC를 동결한다. rank별 직렬 HTTP
서빙과2동시 배틀을 동기 수집하고, 전역 RL16/BC4의 FP32 gradient SUM·공동 KL로 학습한다.
입력/모델/원자료 감사는 검증된 selfplay/imitation 기능을 재사용한다. checkpoint는 rank별
난수·완료 cursor·optimizer·동결 buffer·최초 시계를 보존한다. 정책/head 잠금 뒤 대응 test만
허용하며 독립 재집계·정확한 JSON/C-047 뷰어 검증은 별도 CPU 경로다.
진입점은 `scripts/pokechamp-abyssal-rl`, 조건 원문은 [EX-073](experiments/EX-073-abyssal-rl.md),
검증·현재 실행 상태는 [EP-119](exec-plans/active/EP-119-abyssal-rl.md)를 따른다.


## D-117 EX-074 계승 경로

승인된 새 경로는 `integration/pokechamp/abyssal_rl_continue/`이며 EX-073 실행기·동결
artifact를 보존한다. CPU 준비에서 부모 checkpoint 출처·가중치/optimizer/RNG와 새 split·
슬롯을 연결하고 실행기가 새 시계·추가 라운드·단계 receipt를 소유한다. 독립 감지기는
모델을 호출하지 않고 receipt/프로세스 상태와 영속 전달 원장을 사용한다.
별도 최종화는 모든 정상 경기 export와 단계별 표본 브라우저 확인을 담당한다.
이 경로의 실행·검증·최종화는 완료했으며 기존 동결 실행은 재개하지 않는다. 확정 조건은
[EX-074](experiments/EX-074-abyssal-rl-continue.md), runtime은
[C-058](CONTRACTS.md#c-058-abyssal-rl-continue), 구현·검증 상태는
[EP-121](exec-plans/completed/EP-121-abyssal-rl-continue.md)이 소유한다.


## D-118 EX-075 계승 경로

새 `integration/pokechamp/abyssal_rl_next/`는 EX-074 local25/전체82의 학습 checkpoint를
CPU 출처 검증 후 별도 실행으로 가져온다. 가중치/optimizer/RNG와 train 순환을 이어받고
새 test·경기 seed·슬롯·시계를 동결한다. 추가 update와 기존 누적 이력은 별도 기록한다.
prepare/verify/run/status/finalize와 EX-075 내부 재개, 영속 단계 알람과 전 경기 export/
표본 브라우저 확인을 구현하고 CPU 통합 검증을 통과했다. GPU 검증과 실제 실행은 별도 receipt로 판단한다. 단일12시간 주기 뒤
후속 실행을 자동 시작하지 않는다. 조건은 [EX-075](experiments/EX-075-abyssal-rl-next.md),
runtime은 [C-059](CONTRACTS.md#c-059-abyssal-rl-next), 구현·검증 증거는
[EP-122](exec-plans/completed/EP-122-abyssal-rl-next.md)를 따른다.


### Life Orb 공개 입력 교정

[EP-123](exec-plans/completed/EP-123-life-orb-input.md): 공유 imitation replay/live serializer는
Life Orb의 `-damage ... [from] item: Life Orb`도 도구 공개로 기록한다. 공개 여부는 이력
window와 독립적으로 유지하고 현재 도구 값·제거·재획득은 기존 parser를 따른다.
기존 동결 실행 source와 저장 입력은 당시 형태를 보존한다.
