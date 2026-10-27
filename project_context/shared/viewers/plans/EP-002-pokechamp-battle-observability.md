# EP-002 — PokéChamp battle observability logging 및 정적 viewer

- 상태 (Status): Completed
- 생성일 (Created): 2026-09-04
- 완료일 (Completed): 2026-09-04
- 책임자 (Owner): Codex
- 관련 contract (Related contracts): [`C-008`, `C-009`](../../../CONTRACTS.md)
- 관련 decision (Related decisions): [`D-010`](../decisions/D-010-adopt-pokechamp-battle-observability.md)
- 관련 experiment (Related experiments): 없음 — 관찰 도구 구현이며 efficacy experiment가 아님

## 목표 (Objective)

명시적으로 research-tagged PokéChamp battle의 LLM wire input/output, 실제 action과 이후 Showdown
전개를 무결성 검증 가능한 bundle로 기록하고, 원 evidence에서 사람이 읽는 정적 HTML 및 검색 가능한
experiment catalog를 재생성할 수 있게 한다.

## 맥락 (Context)

EP-001 qualification은 prompt/response 원문을 보존하지 않도록 설계되어 end-to-end 실행 가능성은
검증하지만 battle decision을 사후 분석할 수 없다. 사용자가 승인한 설계와
[`D-010`](../decisions/D-010-adopt-pokechamp-battle-observability.md)은 qualification과 분리된
opt-in full-fidelity 기록 경계를 정의한다. 현재 연구 hypothesis와 efficacy protocol은 여전히
TBD이므로 이 plan은 수집·열람 capability만 구현한다.

## 범위 (Scope)

- 포함 범위 (In scope):
  - `POKECHAMP_DATA_ROOT/experiments/<experiment_id>/battles/<battle_id>/` source bundle writer
  - schema v1 event/manifest, append ordering, SHA-256 sealing과 verification
  - parent-owned LLM/backend 및 player/transport trace hook
  - decision/LLM call/wire action correlation, battle state snapshot과 raw protocol capture
  - escaped CSP-protected `report.html`, optional Showdown animation `replay.html`, local
    `showdown.log`
  - experiment `catalog.sqlite`와 searchable static `index.html` rebuild
  - research run/rebuild/verify CLI 및 usage documentation
  - partial/tampered/failure cases와 qualification 비노출 regression test
- 허용된 file/system (Allowed files/systems): `integration/pokechamp/`, `scripts/pokechamp-env`, root
  `.gitignore`, 관련 `project_context/` 문서, test-created temporary data roots, 명시적으로 설정한
  `POKECHAMP_DATA_ROOT`; runtime 검증 시 기존 loopback Showdown과 사용자가 설정한 Ollama Cloud
  boundary.

## 비목표 (Non-goals)

- L4/L5 automatic retrieval, learning 또는 memory write
- RQ/hypothesis, baseline/treatment, metric, denominator, efficacy evaluation 또는 성능 claim
- Public ladder 개인정보·공개 정책
- Showdown animation과 LLM card의 자동 시간 동기화
- External `pokechamp` 또는 `pokemon-showdown` submodule 변경

## 불변 조건 (Invariants)

- Recorder가 없는 qualification path에는 prompt, response, reasoning 또는 credential이 저장되지
  않는다.
- Full-fidelity logging은 명시적인 research tag와 writable data root가 있을 때만 시작한다.
- 완료된 source evidence는 overwrite/delete하지 않으며 derived rebuild는 source 세 파일을 수정하지
  않는다.
- 진행 중 recorder failure는 evidence completeness를 낮추고 경고하되 gameplay action을 바꾸지
  않는다.
- 모든 HTML에 untrusted text escaping과 CSP를 적용한다.
- Canonical 두 submodule은 지정 SHA에서 clean 상태를 유지한다.

## 완료 기준 (Acceptance Criteria)

- [x] Team preview, 강제 교체, 동일 turn 복수 decision과 복수/실패 LLM call이 각 ID에 연결된다.
- [x] Effective wire prompt, reasoning, raw/parsed output, validation과 실제 wire action을 보존한다.
- [x] 승리·패배·무승부·중단·provider failure·logging failure manifest/completeness를 표현한다.
- [x] Seal 검증, tamper 탐지, partial rendering과 catalog rebuild가 동작한다.
- [x] Report/index/replay가 untrusted text를 실행하지 않고 offline static timeline을 제공한다.
- [x] 기존 qualification artifact 및 call metadata에 full-fidelity content가 추가되지 않는다.
- [x] Controlled-local deterministic fixture가 timeline, report와 replay export를 end-to-end 검증한다.
- [x] 관련 unit/integration, syntax, documentation 및 canonical submodule cleanliness 검사가 통과한다.

## 검증 (Verification)

| 검사 (Check) | Command 또는 방법 | 기대 evidence | 결과 (Result) |
|---|---|---|---|
| Unit/integration | `pytest integration/pokechamp/tests -q` | schema, hook, render, catalog, regression 통과 | Pass — 45 tests |
| Lint/syntax | Ruff `E/F/I/W`, `python -m compileall integration/pokechamp` | parent integration lint/compile 성공 | Pass |
| CLI | `scripts/pokechamp-env research --help`; repository CLI fixture `rebuild`/`verify` | run/rebuild/verify interface와 sealed fixture | Pass |
| Viewer safety | malicious prompt/model/username/protocol fixture, CSP hash 확인 | markup/script 미실행, local timeline | Pass |
| Source integrity | source byte snapshot, checksum tamper/partial/logging-fault fixture | derived rebuild source 불변, 상태 구분 | Pass |
| Hygiene | actual credential value, Markdown link/trailing whitespace, port와 `git submodule status` 검사 | secret 없음, links 정상, port 종료, submodule clean | Pass |
| Operational demo | `observability-demo/demo-001` actual Cloud battle 및 `research verify` | sealed full-fidelity bundle과 viewer 생성 | Pass — 28 turns, 261 events, 35 decisions, 34 calls |

## 진행 상황 (Progress)

- 2026-09-04 — 사용자 승인 설계를 D-010/C-009와 함께 Active plan으로 등록. Implementation 시작.
- 2026-09-04 — Schema v1 recorder, exclusive bundle creation, append event sequencing, checksum seal과
  correction identity를 구현. Mid-battle write failure를 gameplay에서 격리하고 completeness를 낮춤.
- 2026-09-04 — Parent-owned traced player가 raw inbound protocol, decision state/result와 exact outbound
  wire payload를 기록하고 Ollama backend가 recorder가 있을 때만 effective prompt, reasoning,
  raw/parsed output 및 validation/token/latency metadata를 전달하도록 연결.
- 2026-09-04 — Escaped CSP report/replay, offline protocol timeline, SQLite catalog와 date/experiment/
  model/result/format/completeness filter index 및 rebuild/verify CLI 구현.
- 2026-09-04 — Qualification content-minimization, credential redaction, outcome/completeness,
  team-preview/forced-switch/same-turn/multi-call, tamper/partial/catalog와 repository CLI fixture를 포함한
  45 tests 및 최종 hygiene가 통과해 plan 완료.
- 2026-09-04 — 완료 후 operational demo `observability-demo/demo-001`을 실제 Ollama Cloud로 실행.
  `player_won` 28턴, source checksum PASS, `evidence_complete=true`, logging error 0을 확인하고 server를
  종료했다. 단일 승패는 efficacy evidence로 해석하지 않는다.

## 차단 및 중단 조건 (Blockers / Stop Conditions)

- Higher-authority context와 충돌하면 중단하고 보고한다.
- `POKECHAMP_DATA_ROOT`를 battle 전에 생성·열 수 없으면 research battle을 시작하지 않는다.
- 기존 bundle ID가 존재하면 overwrite하지 않고 실패한다.
- Upstream 수정이나 efficacy methodology 변경이 필요해지면 현재 구현을 확장하지 않고 별도 결정을
  요청한다.

## 결과 및 증거 (Outcome and Evidence)

2026-09-06 사용자 요청으로 report에 스크롤 중 유지되는 sandbox replay 패널을 추가했다.
Desktop은 오른쪽, 좁은 화면은 상단에 고정한다. `observability-demo`의 derived HTML을 재생성하고
source 세 파일의 해시 불변을 확인했다. Renderer 회귀 2건과 Ruff 통과, Chromium의
1600/900/390px 화면에서 스크롤 후 위치 유지와 animation control 로딩을 검증했다.

`integration/pokechamp/observability/`에 source recorder, parent player hook, static renderer/catalog와
schema 문서를 구현했고 `scripts/pokechamp-env research run|rebuild|verify`로 노출했다. Full-fidelity
source는 명시적 absolute `POKECHAMP_DATA_ROOT`와 experiment tag가 있을 때만 생성되며 qualification
artifact는 기존 content-minimized 동작을 유지한다.

Controlled fixture는 source 세 파일의 byte가 derived rebuild 전후 동일함, valid/invalid checksum,
partial rendering, HTML injection 방지, decision/LLM/action correlation과 repository CLI 경로를
검증했다. Plan 완료 뒤 actual Cloud operational demo 1회를 추가로 검증했지만 efficacy experiment는
실행하지 않았으며 `project_context/experiments/`에도 experiment를 등록하지 않았다. Canonical
`pokechamp`와 `pokemon-showdown` submodule은 각각 pinned SHA에서 clean이고 port 8000은 종료 상태다.
