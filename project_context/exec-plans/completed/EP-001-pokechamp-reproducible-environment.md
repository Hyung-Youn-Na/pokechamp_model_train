# EP-001 — PokéChamp 재현 가능 연구 환경 구성

- 상태 (Status): Completed
- 생성일 (Created): 2026-09-04
- 완료일 (Completed): 2026-09-04
- 책임자 (Owner): Codex
- 관련 contract (Related contracts): [`C-007`, `C-008`](../../CONTRACTS.md)
- 관련 decision (Related decisions): [`D-005`](../../decisions/D-005-adopt-pokechamp-l1-l5-research-goal.md), [`D-007`](../../decisions/D-007-adopt-pokechamp-dotenv-credential.md), [`D-009`](../../decisions/D-009-adapt-always-on-reasoning-output.md)
- 관련 experiment (Related experiments): 없음 — technical qualification이며 efficacy experiment가 아님

## 목표 (Objective)

Pin된 PokéChamp 및 Pokémon Showdown source, 격리된 Python/Node dependency, loopback battle server,
direct Ollama Cloud adapter와 provenance artifact를 하나의 repository-owned CLI로 bootstrap하고
검증하여 이후 L1-L5 적용 작업의 재현 가능한 technical baseline을 만든다.

## 맥락 (Context)

[`D-005`](../../decisions/D-005-adopt-pokechamp-l1-l5-research-goal.md)가 상위 목표를 채택했지만
현재 repository에는 PokéChamp source, Showdown runtime, cloud adapter 또는 qualification record가
없다. 조사 시 host에는 Python 3.11.11, Node 24.18.0/npm 11.16.0과 NVIDIA RTX A6000이 있으나
`uv`, Docker, `pnpm`은 없었고 disk 여유는 약 349 GiB였다. Ollama Cloud credential 값은 아직
process environment나 ignored root `.env`에서 확인되지 않았다. 이 host 관찰값은 pin이 아니며
bootstrap preflight가 실행 시 다시 측정한다.

이 plan은 [`RESEARCH_DESIGN.md`](../../RESEARCH_DESIGN.md)의 efficacy hard-stop을 유지한다.
Battle 결과는 runtime qualification evidence일 뿐, 승률이나 성능 개선 evidence가 아니다.

## 범위 (Scope)

- 포함 범위 (In scope):
  - `pokechamp/`와 `pokemon-showdown/`의 pinned Git submodule 등록
  - repository-local `uv 0.12.9`, Python 3.11.11 기반 `uv sync --locked`
  - Showdown `npm ci`, `127.0.0.1:8000`, `--no-security --ai-tournament` server lifecycle
  - parent-owned Ollama Cloud backend와 fail-closed configuration validation
  - process 우선, ignored root `.env` fallback인 persistent credential resolution
  - `bootstrap`, `preflight`, `server start|status|stop`, `probe`, `smoke` CLI
  - gen9ou, seed 100, bundled team ID 1/2의 local one-battle 및 PokéChamp IO one-battle smoke
  - source/tool/model/config/outcome metadata를 포함하는 `.artifacts/pokechamp/` artifact
  - unit/integration test와 project-context 현재 상태 갱신
- 허용된 file/system (Allowed files/systems): root `.gitmodules`, `.gitignore`, `.env.example`, ignored
  local `.env`, 두 submodule path,
  `integration/pokechamp/`, `scripts/pokechamp-env`, 관련 test, `.tools/uv/`,
  `.artifacts/pokechamp/`, `project_context/`의 관련 authority/plan/status 문서, localhost process와
  사용자가 제공한 Ollama Cloud API.

## 비목표 (Non-goals)

- L1-L5 layer mapping 또는 implementation
- Baseline/treatment, hypothesis, primary outcome, efficacy protocol 또는 성능 개선 claim
- Minimax evaluation, 대규모 battle/data 수집, model comparison
- Docker, local Ollama daemon, local GPU inference
- Upstream submodule source 수정 또는 dependency upgrade
- 기존 Hugging Face/cache 삭제, repository-wide Python 환경 통합

## 불변 조건 (Invariants)

- [`CHARTER.md`](../../CHARTER.md)의 상위 연구 목표와
  [`RESEARCH_DESIGN.md`](../../RESEARCH_DESIGN.md)의 pre-experiment 상태를 보존한다.
- Upstream submodule은 지정 commit에서 clean 상태를 유지한다.
- Credential 값은 승인된 ignored root `.env` 외의 file, command output, process argument, test
  fixture 또는 artifact에 쓰지 않는다.
- Cloud failure는 local success나 다른 provider/model로 fallback하지 않는다.
- Server는 loopback에만 bind하며 PID ownership을 검증한 process만 중지한다.
- 모든 smoke attempt는 성공/실패와 provenance를 남기고 efficacy result로 분류하지 않는다.
- PokéChamp license의 비표준 추가 제한을 보존하고 표준 MIT로 축약하지 않는다.

## 완료 기준 (Acceptance Criteria)

- [x] 두 Git submodule이 지정 URL/commit으로 pin되고 clean 상태다.
- [x] `scripts/pokechamp-env bootstrap`이 fresh checkout 전제에서 필요한 dependency와 config를
      만들고 재실행해도 안전하다.
- [x] `preflight`가 source SHA, Python/uv/Node/npm, disk, imports, loopback server와 credential
      준비 상태를 비밀 노출 없이 판정한다.
- [x] Showdown이 오직 `127.0.0.1:8000`에서 시작되고 status/stop lifecycle이 검증된다.
- [x] Missing `OLLAMA_API_KEY`가 network call 전에 명시적으로 실패한다.
- [x] Process environment를 우선하고 protected root `.env`를 fallback으로 쓰는 loader와 Git
      ignore/example 구성이 검증된다.
- [x] Fake client unit test가 `https://ollama.com`, `glm-5.3-flash`, timeout 120초, output 512,
      context 8192, `think=low`, compact action 지시, action-contract fail-closed와 무 fallback 동작을
      검증한다.
- [x] Local deterministic random-vs-max-power gen9ou one-battle smoke가 완료되고 artifact를 남긴다.
- [x] Real Ollama Cloud probe와 PokéChamp IO-vs-Abyssal gen9ou one-battle smoke가 각각 완료되고
      artifact를 남긴다.
- [x] Artifact가 source/tool/model/config/outcome metadata와 qualification 분류를 포함하며 secret을
      포함하지 않는다.
- [x] 관련 test, documentation link/format 및 submodule cleanliness 검사가 통과한다.

## 검증 (Verification)

| 검사 (Check) | Command 또는 방법 | 기대 evidence | 결과 (Result) |
|---|---|---|---|
| Source pin | `git submodule status`와 각 remote/status 확인 | 지정 SHA/URL, clean | Pass — 두 canonical submodule clean |
| Bootstrap | `scripts/pokechamp-env bootstrap` 2회 | locked sync 성공, idempotent | Pass — 성공 artifact `044157`, `044759` UTC |
| Unit/import | parent integration test와 upstream import | backend contract 및 import 성공 | Pass — 21 tests, pinned import 성공 |
| Credential gate | key가 없는 격리 env에서 `probe` | network 전에 nonzero와 분류 artifact | Pass — exit 3, `probe/20260904T044215.433619Z` |
| Persistent credential | dotenv unit/integration test, permission/ignore/child-env 검사 | process 우선, `.env` fallback, 비실행 parser, child 격리, `0600`, Git 제외 | Pass — 6 tests, ignored `.env` preflight와 artifact secret scan 통과 |
| Server lifecycle | `server start`, socket bind 확인, `status`, `stop` | loopback-only 및 owned PID | Pass — start 재실행 및 stop 재실행 포함 |
| Local smoke | `smoke --local-only` 독립 server 재시작 2회 | 동일 gen9ou 1 battle artifact | Pass — 둘 다 `player_lost`, 118 turns |
| Cloud probe | `probe` | model 응답 검증 및 artifact | Pass — D-009 `probe/20260904T054729.900005Z`, 1/1 valid |
| Cloud battle | `smoke --cloud-only` | IO vs Abyssal 1 battle, 20분 이내 | Pass — D-009 `smoke-cloud/20260904T054859.499907Z`, 24턴 `player_won`, 29/29 action-valid |
| Hygiene | Markdown link/whitespace, secret scan, submodule status | 오류/secret/dirty 없음 | Pass — 23 Markdown, 58 manifest, exact SHA/clean 및 port 종료 확인 |

## 진행 상황 (Progress)

- 2026-09-04 — 사용자 승인에 따라 plan을 Active로 등록. Implementation 시작.
- 2026-09-04 — 두 external source를 지정 SHA의 Git submodule로 등록하고 exact license를 확인.
- 2026-09-04 — Locked Python/Node bootstrap 완료. Upstream direct `llm_player` import의 순환
  import는 source 수정 없이 안전한 import order로 처리.
- 2026-09-04 — Canonical Showdown이 runtime season JSON을 수정하는 것을 관찰. 두 generated
  change를 HEAD로 복구하고 marker-protected temporary Git worktree 실행으로 격리.
- 2026-09-04 — Node worker preload로 Showdown RNG까지 seal. 독립 재시작 local smoke 두 번이
  동일한 outcome/118 turns를 기록.
- 2026-09-04 — Local acceptance 완료. Process environment에 `OLLAMA_API_KEY`가 없어 status를
  Blocked로 변경하고 real Cloud checks만 보류.
- 2026-09-04 — Final syntax/unit/link/artifact/secret/submodule/port hygiene 통과. 미완료 항목은
  credential-dependent real Cloud probe와 battle뿐임을 확인.
- 2026-09-04 — 사용자 승인으로 D-006을 D-007로 대체하고 ignored root `.env` credential
  fallback을 구현. Process environment 우선순위, non-executing parser, permission/child-process
  gate와 6개 test를 추가했으나 실제 key 값은 아직 입력되지 않음.
- 2026-09-04 — 실제 `.env` key로 all-scope preflight와 Ollama Cloud probe 성공. 첫 cloud battle은
  35턴 `player_lost`와 program-level success를 기록했지만 387 calls 중 385 invalid, 386
  `done_reason=length` 및 반복 max-damage fallback이 확인되어 acceptance를 거절.
- 2026-09-04 — D-008로 JSON call의 `think=false`, available-action 검증 및 첫 invalid response
  terminal failure를 채택·구현. Unit suite 21건 통과.
- 2026-09-04 — D-008 적용 probe는 통과했으나 battle 첫 call이 다시 300-token length/invalid로
  종료. Fail-closed가 provider call을 1회로 제한하고 exit 4 failure artifact를 남김. 공식 model
  문서에서 `glm-5.3-flash` reasoning이 always-on임을 확인해 D-008을 D-009로 대체하고
  `think=low`, battle 512-token cap과 compact JSON-only compatibility instruction을 구현.
- 2026-09-04 — D-009 real probe가 1/1 valid, 7 completion tokens와 `done_reason=stop`으로 통과.
  최종 cloud battle은 24턴 `player_won`, provider call 29/29의 JSON/action/output contract valid,
  29/29 `done_reason=stop`, prompt 57,817 및 completion 2,027 tokens로 통과. Server stop과
  credential/artifact hygiene 확인 후 모든 acceptance criterion을 완료.

## 차단 및 중단 조건 (Blockers / Stop Conditions)

- Higher-authority context와 충돌하면 중단하고 보고한다.
- 이 plan에서 승인하지 않은 destructive, external, costly 또는 scope-expanding action 전에
  중단한다.
- Disk 여유가 30 GiB 미만이면 dependency install을 시작하지 않는다. 기존 cache를 삭제하지 않는다.
- Pinned lock/source가 요구 runtime과 호환되지 않으면 임의 upgrade하지 않고 evidence를 기록한다.
- Cloud key 부재 또는 auth/model/rate-limit/transport failure는 cloud criterion을 미완료로 남긴다.
- 20분을 넘긴 cloud battle은 infrastructure timeout으로 기록하며 defeat나 efficacy result로
  바꾸지 않는다.

## 결과 및 증거 (Outcome and Evidence)

Pinned source/toolchain, deterministic local battle, protected persistent credential, direct Ollama
Cloud probe 및 valid model-action 기반 IO one-battle 경로가 모두 구현·검증됐다. 최종 artifact는
`.artifacts/pokechamp/probe/20260904T054729.900005Z`와
`.artifacts/pokechamp/smoke-cloud/20260904T054859.499907Z`다. Cloud battle의 승리는 runtime
qualification outcome일 뿐 efficacy evidence가 아니며 성능 개선 claim에 사용할 수 없다.

앞선 두 cloud battle attempt도 변경하지 않고 보존한다. 첫 run은 387-call amplification과 local
fallback을 success로 잘못 분류했고, D-008 run은 fail-closed를 검증하면서 model-specific
`think=false` 비호환을 드러냈다. D-009가 두 문제를 해결했다. 남은 별도 limitation은 pinned
Showdown lock의 2026-09-04 npm audit summary 31건(critical 4 포함)이며, 외부 exposure 또는
production 사용 전에 별도 검토가 필요하다.
