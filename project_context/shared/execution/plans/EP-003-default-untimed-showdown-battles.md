# EP-003 — PokéChamp Showdown battle timer 기본 비활성화

- 상태 (Status): Completed
- 생성일 (Created): 2026-09-04
- 완료일 (Completed): 2026-09-04
- 책임자 (Owner): Codex
- 관련 contract (Related contracts): [`C-008`](../../../CONTRACTS.md)
- 관련 decision (Related decisions): [`D-011`](../decisions/D-011-default-untimed-showdown-battles.md)
- 관련 experiment (Related experiments): 없음 — runtime policy 검증이며 efficacy experiment가 아님

## 목표 (Objective)

명시적 timed-run 요청이 없는 repository-managed PokéChamp battle에서 Showdown inactivity timer를
비활성화하고, 매뉴얼·runtime·evidence metadata가 동일한 기본 정책을 표현하게 한다.

## 맥락 (Context)

Pinned Showdown은 `forcetimer=true`이고 `observability-demo/demo-001`에서 countdown protocol이
관찰됐다. 사용자가 채택한 untimed 기본값과 기존 parent launcher 사이의 불일치를 D-011에 따라
해소한다.

## 범위 (Scope)

- 포함 범위 (In scope): parent launcher의 process-local timer override, qualification/research
  metadata, integration 매뉴얼, 관련 current-state 문서와 회귀 검증
- 허용된 file/system (Allowed files/systems): `integration/pokechamp/`, 관련 `project_context/` 문서,
  test/runtime artifact 및 temporary Showdown worktree

## 비목표 (Non-goals)

- Provider request 또는 orchestration safety timeout 제거
- Timed experiment용 새 CLI 설계
- 기존 source bundle 수정 또는 efficacy experiment 실행
- External submodule 수정

## 불변 조건 (Invariants)

- Loopback-only bind, pinned SHA, deterministic seed, credential 비노출과 source bundle contract를
  유지한다.
- Timer opt-in은 기존 Showdown/player interface로 계속 가능하다.
- 기존 timed artifact를 소급 수정하지 않는다.

## 완료 기준 (Acceptance Criteria)

- [x] Launcher가 pinned `forcetimer=true`를 process-local `false`로 바꾸고 server를 시작한다.
- [x] 기본 controlled battle protocol에 `|inactive|` countdown이 없음을 검증한다.
- [x] 매뉴얼이 untimed 기본값, timed opt-in과 safety timeout의 차이를 명시한다.
- [x] Artifact/research metadata가 default timer policy를 기록한다.
- [x] Canonical submodule은 clean이고 port 8000은 검증 뒤 종료된다.

## 검증 (Verification)

| 검사 (Check) | Command 또는 방법 | 기대 evidence | 결과 (Result) |
|---|---|---|---|
| Unit/integration | `pytest integration/pokechamp/tests -q`; Ruff/compileall/Node syntax | launcher policy와 metadata 회귀 통과 | Pass — 47 tests |
| Runtime | loopback server + deterministic local battle protocol | countdown event 없음 | Pass — 72 turns, countdown 0 |
| Hygiene | links, credential, diff, submodule, port 검사 | 문서 정상, secret 없음, submodule clean, port 종료 | Pass — 236 links |

## 진행 상황 (Progress)

- 2026-09-04 — D-011과 함께 plan 등록. Implementation은 아직 시작하지 않음.
- 2026-09-04 — Launcher가 server config module의 `forcetimer`를 process-local `false`로 바꾸도록
  구현하고 qualification/research metadata와 한국어 매뉴얼을 갱신.
- 2026-09-04 — 47 tests와 static hygiene 통과. 실제 deterministic local battle 72턴에서
  countdown 0을 확인하고 server를 종료해 plan 완료.

## 차단 및 중단 조건 (Blockers / Stop Conditions)

- Higher-authority context와 충돌하면 중단하고 보고한다.
- Default timer 비활성화에 external submodule 수정이 필요하면 중단한다.
- Safety timeout까지 제거해야 하는 경우 현재 범위를 확장하지 않고 별도 결정을 요청한다.

## 결과 및 증거 (Outcome and Evidence)

Pinned source의 `forcetimer=true`를 수정하지 않고 parent launcher에서만 timer-off 기본값을
적용했다. Qualification manifest와 새 research bundle metadata는 forced/default request 상태를
기록한다. 실제 loopback battle protocol에 `|inactive|` 또는 `Time left:` event가 없었으며 기존
provider/orchestration timeout은 infrastructure safety 경계로 유지했다. Canonical submodule과 기존
timed evidence는 수정하지 않았다.
