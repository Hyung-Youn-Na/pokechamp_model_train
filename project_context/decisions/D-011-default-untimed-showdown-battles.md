# D-011 — PokéChamp 실험의 Showdown battle timer 기본 비활성화

- 상태 (Status): 채택 (Accepted)
- 날짜 (Date): 2026-09-04
- 관련 결정 (Related decisions): [`D-007`](D-007-adopt-pokechamp-dotenv-credential.md),
  [`D-010`](D-010-adopt-pokechamp-battle-observability.md)

## 맥락 (Context)

Pinned `pokemon-showdown/config/config.js`는 `forcetimer=true`이며, operational demo
`observability-demo/demo-001`의 protocol에도 turn별 150초·battle 전체 600초 countdown이
관찰됐다. LLM 응답 시간이나 실행 부하가 이 clock과 결합하면 의도하지 않은 timeout loss와
treatment-dependent pressure를 만들 수 있다.

사용자는 별도 명령이 없는 실험은 시간 제한 없이 실행하도록 매뉴얼에 명시할 것을 요청했다.
문서만 바꾸고 현재 강제 timer를 유지하면 실제 동작과 규범이 충돌하므로 parent-owned runtime
경계도 함께 맞춰야 한다.

## 결정 (Decision)

1. Repository가 관리하는 PokéChamp qualification 및 research battle은 기본적으로 Pokémon
   Showdown inactivity timer를 사용하지 않는다.
2. Parent-owned launcher는 pinned server module을 초기화하기 전에 process-local
   `Config.forcetimer=false`를 설정한다. Canonical `pokemon-showdown` submodule은 수정하지 않는다.
3. Timed battle은 실행 전 명시적으로 승인·기록된 경우에만 `/timer on` 또는 player의
   `start_timer_on_battle_start=True`와 같은 opt-in으로 활성화한다. Timed와 untimed run을 같은
   condition으로 조용히 합치지 않는다.
4. Provider request timeout, orchestration watchdog, socket shutdown timeout은 hung process와
   infrastructure failure를 통제하는 안전 경계로 유지한다. 이들은 Showdown의 turn/battle
   decision clock이 아니며 승패로 자동 해석하지 않는다.
5. 기존 timed artifact는 원형을 보존하고 소급 변경하지 않는다. 이후 comparison에 사용할 때는
   timer 차이를 configuration drift로 명시한다.

## 거절한 대안 (Rejected Alternatives)

- 매뉴얼만 수정: 현재 `forcetimer=true` 동작과 충돌해 사용자가 기대한 기본값을 보장하지 못한다.
- Canonical submodule의 `config/config.js` 직접 수정: pinned clean-source 경계를 깨므로 채택하지
  않았다.
- 모든 종류의 timeout 제거: provider 장애나 hung process를 무한 대기로 바꾸며 요청한 Showdown
  battle clock 범위를 넘어가므로 채택하지 않았다.

## 근거 (Rationale)

Untimed 기본값은 느린 LLM call이 게임 규칙상 패배로 변환되는 것을 막고, latency가 다른 condition
사이의 불필요한 교란을 줄인다. Process-local override는 upstream provenance와 canonical
cleanliness를 유지하면서 실제 server 동작을 매뉴얼과 일치시킨다.

## 영향 (Consequences)

- [`EP-003`](../exec-plans/completed/EP-003-default-untimed-showdown-battles.md)이 launcher, evidence
  metadata, 매뉴얼과 검증을 갱신한다.
- Timed condition은 timer activation과 설정을 experiment record에 포함해야 한다.
- 기존 EP-001 qualification과 `demo-001`은 당시 timer-on 환경의 historical evidence로 남는다.

## 증거 (Evidence)

- 2026-09-04 사용자 지시: 별도 명령이 없는 experiment는 무제한으로 실행.
- [`pokemon-showdown/config/config.js`](../../pokemon-showdown/config/config.js)
- [`C-008`](../CONTRACTS.md)
- [`RESEARCH_DESIGN.md`](../RESEARCH_DESIGN.md)
