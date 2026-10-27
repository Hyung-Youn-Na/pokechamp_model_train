# D-010 — PokéChamp battle full-fidelity observability 경계 채택

- 상태 (Status): 채택 (Accepted)
- 날짜 (Date): 2026-09-04
- 관련 결정 (Related decisions): [`D-007`](../../execution/decisions/D-007-adopt-pokechamp-dotenv-credential.md), [`D-009`](../../execution/decisions/D-009-adapt-always-on-reasoning-output.md)

## 맥락 (Context)

현재 qualification artifact는 source와 실행 가능성을 증명하기 위해 prompt, response와 reasoning
원문을 의도적으로 저장하지 않는다. 이 경계는 secret/content 최소화에는 적합하지만, 사람이
battle별 LLM 입력·출력, 실제 전송 action과 이후 Showdown 전개를 함께 검토하기에는 부족하다.

사용자는 자동 L4/L5 학습이나 efficacy 평가가 아니라 controlled local battle의 수동 분석을 위한
full-fidelity observability viewer를 요청했다. 이 기능은 새 persistent schema와 write authority를
만들며, qualification artifact의 비노출 계약을 약화하지 않아야 한다.

## 결정 (Decision)

1. Full-fidelity 기록은 명시적인 `experiment_id`가 있는 research run에서만 활성화한다. 저장소는
   필수 `POKECHAMP_DATA_ROOT` 아래
   `experiments/<experiment_id>/battles/<battle_id>/`이며 qualification `.artifacts/`와 분리한다.
2. Source evidence는 schema version 1의 `manifest.json`, append-only `events.jsonl`과 seal 시점의
   `checksums.sha256`다. 완료된 source bundle은 자동 삭제하거나 덮어쓰지 않으며 ID 충돌은
   실패한다. Correction은 `replacement_for`를 가진 새 bundle identity를 사용한다.
3. Event는 battle 단위 `event_seq`, 판단 단위 `decision_seq`, 호출 단위 `llm_call_seq`를 가진다.
   `showdown_turn`은 표시 정보이며 decision identity로 사용하지 않는다. 고정 event type은
   `battle_start`, `protocol_in`, `decision_start`, `llm_call`, `decision_result`, `wire_action`,
   `battle_end`, `logging_error`다.
4. Research `llm_call`은 실제 provider에 전송한 system/user prompt, provider reasoning과 raw
   content, canonical parsed output, validation, model/token/latency/stop metadata를 보존한다.
   Parent-owned hook이 inbound Showdown protocol과 실제 outbound action을 기록한다.
5. `showdown.log`, `replay.html`, `report.html`, experiment별 `catalog.sqlite`와 `index.html`은 source
   evidence에서 재생성하는 derived output이다. 재생성은 source 세 파일을 수정하지 않는다.
6. Research logging을 시작할 때 data root와 bundle source file을 열 수 없으면 battle을 시작하지
   않는다. 진행 중 logging failure는 gameplay 결정을 바꾸지 않고 가능한 경우 `logging_error`와
   `evidence_complete=false`를 남기며 사용자에게 경고한다.
7. Qualification 경로는 recorder를 연결하지 않는다. 기존 qualification manifest에는 prompt,
   response, reasoning 또는 credential을 추가하지 않는다. 어느 경로에서도 credential 값은
   evidence에 기록하지 않는다.
8. HTML은 untrusted prompt, output, username과 protocol text를 escape하고 CSP를 적용한다.
   Showdown animation이 network asset을 사용하지 못해도 `report.html`의 정적 turn timeline은
   완전히 local에서 읽을 수 있어야 한다.
9. 이 artifact는 `research_observability`, `efficacy_evidence=false`로 분류한다. 현재 미정인
   hypothesis, treatment, metric, denominator 또는 interpretation rule을 정하거나 자동 L4/L5
   write를 수행하지 않는다.

## 거절한 대안 (Rejected Alternatives)

- Qualification manifest에 원문을 추가: `C-008`의 content 최소화 및 기존 검증 경계를 깨므로
  채택하지 않았다.
- Upstream `pokechamp` 또는 `pokemon-showdown` 수정: pinned clean reference와 parent-owned
  integration 경계를 흐리므로 채택하지 않았다.
- HTML이나 SQLite를 primary evidence로 사용: renderer 변경으로 원 evidence가 달라질 수 있으므로
  source JSON/JSONL과 seal만 primary로 둔다.
- 모든 battle을 기본 기록: prompt/reasoning 원문의 민감도와 storage 비용 때문에 명시적 research
  tag가 없는 경로에는 활성화하지 않는다.

## 근거 (Rationale)

Qualification과 research logging을 별도 root, activation gate와 schema로 분리하면 기존 secret
최소화 경계를 보존하면서 사람이 decision provenance를 검토할 수 있다. Append-only event와 source
seal은 derived viewer를 언제든 재생성하고 tamper를 탐지할 수 있게 한다. Turn과 decision identity를
분리하면 team preview, 강제 교체와 같은 turn 내 복수 판단도 손실 없이 표현한다.

## 영향 (Consequences)

- [`EP-002`](../plans/EP-002-pokechamp-battle-observability.md)가 parent integration,
  renderer, catalog, CLI와 검증을 구현한다.
- Full-fidelity bundle에는 prompt, model output, reasoning, username과 battle protocol이 포함될 수
  있으므로 local research data로 취급하고 source control에 넣지 않는다.
- Viewer schema 확장은 backward-compatible reader 또는 새 schema/decision으로 수행한다.
- Public ladder 수집의 개인정보·공개 정책과 animation-panel 자동 동기화는 별도 결정 전까지 범위
  밖이다.

## 증거 (Evidence)

- 2026-09-04 사용자 승인 구현 계획: PokéChamp Battle Observability Logging 설계.
- [`C-008`, `C-009`](../../../CONTRACTS.md)
- [`EP-002`](../plans/EP-002-pokechamp-battle-observability.md)
