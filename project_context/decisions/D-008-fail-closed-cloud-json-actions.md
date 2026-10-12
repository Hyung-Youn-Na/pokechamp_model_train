# D-008 — Ollama Cloud JSON action의 thinking 비활성화와 fail-closed 검증

- 상태 (Status): [`D-009`](D-009-adapt-always-on-reasoning-output.md)로 대체됨 (Superseded)
- 날짜 (Date): 2026-09-04
- 관련 결정 (Related decisions): [`D-007`](D-007-adopt-pokechamp-dotenv-credential.md)

`think=false`가 `glm-5.3-flash`의 always-on reasoning을 끌 수 있다는 전제가 실제 재검증과 모델
문서로 반증되었다. Fail-closed action 검증을 유지하면서 model-specific effort/output 정책을
정정한 [`D-009`](D-009-adapt-always-on-reasoning-output.md)가 이 결정을 전체 대체한다.

## 맥락 (Context)

실제 Ollama Cloud probe는 성공했지만 첫 PokéChamp IO-vs-Abyssal smoke
`smoke-cloud/20260904T053841.545854Z`에서는 provider call 387회 중 JSON-valid 응답이 2회뿐이었다.
385회는 invalid였고 386회가 PokéChamp 요청 상한 300 completion tokens에서
`done_reason=length`로 끝났다. Upstream IO loop는 decision마다 최대 10회 재호출한 뒤
`choose_max_damage_move`로 fallback하므로 battle은 35턴 `player_lost`로 종료되고 기존 구현은
이를 success로 기록했다. 이 결과는 transport evidence지만 실제 IO action-path qualification은
아니다.

[Ollama thinking 문서](https://docs.ollama.com/capabilities/thinking)는 thinking-capable model에서
reasoning trace가 `message.thinking`에, 최종 답이 `message.content`에 분리되며 대부분의 model은
`think=false`를 지원한다고 설명한다. 관찰된 300-token length 종료와 거의 비어 있는 content는
제한된 output budget이 final JSON 전에 thinking에 소진됐다는 해석과 일치한다.

## 결정 (Decision)

1. EP-001의 JSON qualification call은 `think=false`로 고정한다. Endpoint
   `https://ollama.com`, model `glm-5.3-flash`, context 8192와 output token 상한 512는 유지한다.
2. JSON response가 parse되지 않으면 `output_contract` terminal failure로 처리한다. Battle call은
   추가로 `move`, `dynamax`, `terastallize`, `switch` 중 정확히 하나의 non-empty string action을
   포함하고 현재 `available_moves` 또는 `available_switches`에 일치해야 한다.
3. Output-contract failure는 failure event를 설정해 battle을 취소한다. Upstream의 10회 provider
   재호출과 max-damage fallback을 qualification success로 허용하지 않는다.
4. Artifact에는 thinking 설정, `json_valid`, `battle_action_valid`, `output_contract_valid`, token과
   종료 metadata만 기록하고 response/action content는 기록하지 않는다.
5. 첫 smoke artifact의 원문은 변경하지 않되, program-level `status=success`와 관계없이
   qualification failure로 해석한다.

## 거절한 대안 (Rejected Alternatives)

- Output 상한을 512보다 높임: C-008의 sealed resource boundary와 비용 범위를 먼저 바꾸게 되므로
  채택하지 않았다.
- Invalid response를 계속 재시도: 첫 run에서 387회 호출과 385회 invalid가 발생했으므로 비용과
  failure amplification을 허용하지 않는다.
- Battle 종료와 provider transport success만으로 통과: 실제 action이 local fallback에서
  나왔으므로 IO runtime qualification이라고 볼 수 없다.
- Prompt/response 원문 저장: 진단에 필요하지 않고 기존 secret/content 최소화 경계를 넓히므로
  채택하지 않았다.

## 근거 (Rationale)

Qualification의 목적은 model이 PokéChamp가 실행할 수 있는 action을 공급하는 end-to-end 경로를
검증하는 것이다. Thinking trace 대신 작은 final JSON이 필요한 호출에서 thinking을 끄면 기존
output 상한을 유지할 수 있다. 첫 invalid output에서 종료하면 provider/model fallback 없이 실패를
드러내고 반복 호출 비용을 제한한다.

## 영향 (Consequences)

- [`EP-001`](../exec-plans/completed/EP-001-pokechamp-reproducible-environment.md)은 변경 후 real cloud
  battle을 한 번 다시 검증해야 한다.
- 재검증에서 첫 response가 invalid이면 network call 한 번 뒤 battle이 취소되고 failure artifact가
  남는다.
- 이 설정은 technical qualification boundary이며 L1-L5 treatment의 reasoning effort나 efficacy
  protocol을 자동으로 결정하지 않는다.
- Thinking mode 또는 output-validation policy를 바꾸려면 별도 decision과 evidence가 필요하다.

## 증거 (Evidence)

- Probe artifact: `.artifacts/pokechamp/probe/20260904T052318.926468Z/manifest.json`
- 첫 cloud battle artifact:
  `.artifacts/pokechamp/smoke-cloud/20260904T053841.545854Z/manifest.json`
- [`C-008`](../CONTRACTS.md)
- [Ollama Thinking](https://docs.ollama.com/capabilities/thinking)
