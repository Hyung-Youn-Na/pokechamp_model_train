# D-009 — Always-on reasoning model의 compact action output 경계 채택

- 상태 (Status): 채택 (Accepted)
- 날짜 (Date): 2026-09-04
- 대체하는 결정 (Supersedes): [`D-008`](D-008-fail-closed-cloud-json-actions.md)
- 관련 결정 (Related decisions): [`D-007`](D-007-adopt-pokechamp-dotenv-credential.md)

2026-09-07 [D-013](D-013-remove-client-output-cap.md)이 출력/context 상한을 대체했다.
아래 512/8192는 당시 결정과 실험의 역사적 경계이며 새 호출에 적용하지 않는다.

## 맥락 (Context)

D-008은 첫 cloud battle의 387-call amplification을 막기 위해 JSON action call에서
`think=false`와 output-contract fail-closed를 채택했다. 수정 후 probe는 성공했지만 battle
`smoke-cloud/20260904T054418.824101Z`의 첫 provider response가 다시 300 completion tokens를 모두
사용해 `done_reason=length`, invalid JSON으로 끝났다. Fail-closed는 의도대로 provider 호출을
1회로 제한하고 battle을 실패 처리했다.

[공식 `glm-5.3-flash` 모델 문서](https://ollama.com/library/glm-5.3-flash)는 이 model의 reasoning이
항상 켜져 있고 request별 effort를 `low`, `high`, `max`로 조절한다고 명시한다. 따라서 일반적인
boolean `think=false` 안내는 이 model에 적용되지 않았다. 또한
[Ollama structured outputs 문서](https://docs.ollama.com/capabilities/structured-outputs)는 현재
Cloud가 structured outputs를 지원하지 않는다고 명시하므로 `format=json`만으로 compact action을
보장할 수 없다.

## 결정 (Decision)

1. `glm-5.3-flash` JSON qualification call의 `think` 값은 지원되는 최저 effort인 `low`로 고정한다.
2. Battle action call은 C-008의 기존 output 상한 512 tokens를 전부 사용한다. Endpoint, model,
   context 8192 및 512 상한 자체는 변경하지 않는다.
3. Upstream IO prompt 끝에 parent adapter가 compact JSON object만 반환하고 reasoning, explanation,
   Markdown을 `message.content`에 포함하지 말라는 호환성 지시를 추가한다. `format=json`은 hint로
   유지하되 Cloud의 schema enforcement로 간주하지 않는다.
4. D-008의 fail-closed 검증을 유지한다. JSON parse 실패 또는 현재 battle에서 실행 불가능한
   action은 첫 provider response에서 `output_contract` terminal failure와 battle 취소가 된다.
5. Artifact schema version은 3으로 올리고 `thinking_effort=low`, 실제 requested/completion token,
   종료 이유와 content 비노출 validation metadata를 기록한다.
6. D-008 적용 run의 원 artifact와 실패 해석을 보존하며 성공으로 재분류하지 않는다.

## 거절한 대안 (Rejected Alternatives)

- `think=false` 유지: 실제 response와 model 문서가 비활성화를 지원하지 않음을 보여준다.
- Output 상한을 512보다 높임: 먼저 기존 sealed resource/cost boundary를 바꾸게 되므로 채택하지
  않았다.
- Model/provider 변경: D-007의 고정 경계를 바꾸고 비교 변수를 추가하므로 채택하지 않았다.
- Cloud structured-output schema에 의존: 현재 Cloud에서 지원되지 않는다는 공식 문서와 충돌한다.
- Invalid output retry/local move fallback: failure amplification과 거짓 qualification success를
  다시 허용하므로 채택하지 않았다.

## 근거 (Rationale)

Model이 제공하는 최저 reasoning effort와 이미 승인된 최대 output budget을 함께 사용하면 모델
identity와 비용 상한을 유지하면서 final JSON을 생성할 가장 작은 여유를 제공한다. Prompt-level
compact-output 지시는 Cloud에서 schema enforcement를 사용할 수 없는 제약을 보완한다. 첫-response
fail-closed가 남아 있으므로 호환되지 않을 경우 추가 비용과 fallback gameplay 없이 즉시 드러난다.

## 영향 (Consequences)

- [`EP-001`](../exec-plans/completed/EP-001-pokechamp-reproducible-environment.md)은 이 설정으로 cloud
  one-battle을 한 번만 재검증한다.
- 첫 response가 다시 invalid이면 한 번의 provider call과 failure artifact로 종료하고, model 또는
  output 상한 변경은 사용자 판단이 필요한 별도 작업으로 남긴다.
- 이 qualification 설정은 이후 L1-L5 efficacy treatment의 reasoning effort를 자동으로 정하지
  않는다.

## 증거 (Evidence)

- D-008 probe artifact: `.artifacts/pokechamp/probe/20260904T054348.759187Z/manifest.json`
- D-008 cloud battle artifact:
  `.artifacts/pokechamp/smoke-cloud/20260904T054418.824101Z/manifest.json`
- D-009 validation probe: `.artifacts/pokechamp/probe/20260904T054729.900005Z/manifest.json`
- D-009 final cloud battle:
  `.artifacts/pokechamp/smoke-cloud/20260904T054859.499907Z/manifest.json`
- [`C-008`](../CONTRACTS.md)
- [Ollama `glm-5.3-flash`](https://ollama.com/library/glm-5.3-flash)
- [Ollama Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)
