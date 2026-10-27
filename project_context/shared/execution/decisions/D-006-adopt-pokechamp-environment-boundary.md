# D-006 — PokéChamp 연구 환경 및 외부 경계 채택

- 상태 (Status): [`D-007`](D-007-adopt-pokechamp-dotenv-credential.md)로 대체됨 (Superseded)
- 날짜 (Date): 2026-09-04

이 결정의 source/toolchain/server/cloud/qualification/license 경계를 포함한 전체 결정은
`OLLAMA_API_KEY`의 영속 저장 정책을 변경한 [`D-007`](D-007-adopt-pokechamp-dotenv-credential.md)로
대체되었다. 이 문서는 이전 선택의 provenance로 보존한다.

## 맥락 (Context)

[`D-005`](../../../research/l1-l5-port/decisions/D-005-adopt-pokechamp-l1-l5-research-goal.md)는 AgenticSTS의 L1-L5 구조를
`pokechamp`에 적용하는 상위 연구 목표를 채택했지만, 대상 source와 실행 환경의 identity,
외부 service 경계 및 credential 취급은 정하지 않았다. 구현이나 efficacy 실험보다 먼저
동일한 source와 설정으로 baseline runtime을 재구성하고, 실패를 연구 결과와 분리해 기록할 수
있는 technical qualification 경계가 필요하다.

확인한 upstream source는 `sethkarten/pokechamp`와 그 README가 local battle용으로 지시하는
`jakegrigsby/pokemon-showdown` fork다. `pokechamp`의 `LICENSE`는 MIT 문구와 함께 일본에서의
사용·배포·판매를 금지하는 추가 문구를 포함하므로 표준 MIT license로 축약해 표현할 수 없다.

## 결정 (Decision)

1. 외부 source는 다음 Git submodule과 commit으로 pin한다.
   - `pokechamp/`: `https://github.com/sethkarten/pokechamp.git`,
     `0f84c460319ebe733f8c3028e58a2a5452c60d85`
   - `pokemon-showdown/`: `https://github.com/jakegrigsby/pokemon-showdown.git`,
     `e64915c0eab066db1d3e732b1280386468dd7415`
2. Upstream submodule은 수정하지 않는다. 이 repository가 소유하는 cloud adapter, launcher,
   configuration template, test와 artifact writer는 submodule 밖에 둔다.
3. PokéChamp Python 환경은 repository-local `uv 0.12.9`, Python `3.11.11` 및 upstream
   `uv.lock`으로 격리한다. 기존 AgenticSTS Python 3.12+ 환경과 결합하지 않는다. Showdown은
   pinned source의 `package-lock.json`에 대해 `npm ci`로 설치한다.
4. Showdown server는 `127.0.0.1:8000`에만 bind하고 `--no-security --ai-tournament`로 실행한다.
5. 초기 cloud provider 경계는 direct Ollama Cloud API `https://ollama.com`이며 model은
   `glm-5.3-flash`로 고정한다. Credential은 IDE/process environment의 `OLLAMA_API_KEY`에서만
   읽고 file이나 log/artifact에 기록하지 않는다. 다른 model/provider 또는 local Ollama
   daemon으로 조용히 fallback하지 않는다.
6. Cloud request 기본 경계는 request timeout 120초, output token 상한 512, context 8192다.
   실제 provider identity와 응답 metadata 중 비밀이 아닌 provenance를 qualification artifact에
   기록한다.
7. Qualification은 deterministic local one-battle smoke와 real API probe 및 PokéChamp IO
   one-battle smoke를 구분해 기록한다. 성공은 interface와 runtime의 실행 가능성만 뜻하며
   L1-L5 treatment의 efficacy evidence나 성능 개선 claim이 아니다.
8. `pokechamp/LICENSE` 원문과 provenance를 보존한다. 재배포 또는 release 전에 비표준 일본
   제한 문구를 포함한 실제 license 조건을 별도로 검토하며, 이 dependency를 단순히 “MIT”로
   표시하지 않는다.

## 거절한 대안 (Rejected Alternatives)

- Source vendoring: upstream history와 local change 경계가 흐려지므로 채택하지 않았다.
- Workspace 밖의 임시 clone만 사용: 재현할 source identity를 repository가 보존하지 못하므로
  채택하지 않았다.
- Upstream PokéChamp fork를 즉시 수정: 첫 단계의 baseline qualification과 이후 L1-L5 변경을
  분리하기 위해 채택하지 않았다.
- Local Ollama daemon 또는 GPU inference: 사용자가 초기 범위를 Ollama Cloud로 지정했으며
  별도 model/runtime 변수를 추가하므로 채택하지 않았다.
- Provider/model fallback: qualification failure를 숨기고 provenance를 바꾸므로 채택하지 않았다.

## 근거 (Rationale)

Source, dependency resolver, Python/Node runtime, server address, model, credential와 artifact 경계를
먼저 고정하면 이후의 L1-L5 적용 변경을 환경 drift와 구분할 수 있다. Parent-owned adapter는
upstream snapshot을 clean reference로 유지하면서 direct cloud endpoint와 fail-closed credential
policy를 명시적으로 구현한다. Local smoke와 cloud smoke를 분리하면 infrastructure failure를
연구 결과로 오해하지 않게 한다.

## 영향 (Consequences)

- [`EP-001`](../plans/EP-001-pokechamp-reproducible-environment.md)이 이 결정을
  구현하고 검증한다.
- 환경 bootstrap에는 network access와 상당한 disk 사용이 필요하다. 기존 cache를 삭제하지
  않으며 최소 여유 공간 gate를 둔다.
- `OLLAMA_API_KEY`가 없거나 auth/model/rate-limit/transport 오류가 발생하면 cloud qualification은
  실패 또는 blocked로 기록한다. local path 성공으로 대체하지 않는다.
- 향후 source commit, provider, model, endpoint, credential policy 또는 bind exposure를 바꾸려면
  이 decision을 대체하는 새 decision과 bounded exec plan이 필요하다.
- 이 결정은 L1-L5 mapping, baseline/treatment, metric, hypothesis 또는 efficacy protocol을
  채택하지 않는다.

## 증거 (Evidence)

- 2026-09-04 사용자 승인: Git submodule, official upstream, parent adapter, Ollama Cloud,
  `glm-5.3-flash`, API probe와 IO one-battle validation.
- [`D-005`](../../../research/l1-l5-port/decisions/D-005-adopt-pokechamp-l1-l5-research-goal.md)
- [`RESEARCH_DESIGN.md`](../../../RESEARCH_DESIGN.md)의 qualification/efficacy 분리 규칙
- [`EP-001`](../plans/EP-001-pokechamp-reproducible-environment.md)
