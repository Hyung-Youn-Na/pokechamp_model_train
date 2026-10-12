# D-007 — PokéChamp `.env` credential 정책을 포함한 연구 환경 경계 채택

- 상태 (Status): 채택 (Accepted)
- 날짜 (Date): 2026-09-04
- 대체하는 결정 (Supersedes): [`D-006`](D-006-adopt-pokechamp-environment-boundary.md)

## 맥락 (Context)

[`D-006`](D-006-adopt-pokechamp-environment-boundary.md)은 `OLLAMA_API_KEY`를 IDE 또는 invoking
process environment에서만 받도록 정했다. 이 방식은 terminal session이 종료되면 키를 다시
설정해야 하므로 개인 연구 환경의 반복 실행에 불편이 있었다. 사용자는 이 프로젝트가 개인 연구
용도임을 근거로, Git에서 제외되는 repository-local `.env`에 키를 영구 저장하는 방식을 명시적으로
승인했다.

Credential 저장 위치는 변경되지만 endpoint/model pin, fallback 금지, secret 비노출, Showdown
격리와 qualification/efficacy 구분은 계속 유지해야 한다. 따라서 D-006을 부분 편집하지 않고 현재
환경 경계 전체를 이 결정으로 대체한다.

## 결정 (Decision)

1. 외부 source는 다음 Git submodule과 commit으로 pin한다.
   - `pokechamp/`: `https://github.com/sethkarten/pokechamp.git`,
     `0f84c460319ebe733f8c3028e58a2a5452c60d85`
   - `pokemon-showdown/`: `https://github.com/jakegrigsby/pokemon-showdown.git`,
     `e64915c0eab066db1d3e732b1280386468dd7415`
2. Upstream submodule은 수정하지 않는다. 이 repository가 소유하는 cloud adapter, launcher,
   configuration template, test와 artifact writer는 submodule 밖에 둔다.
3. PokéChamp Python 환경은 repository-local `uv 0.12.9`, Python `3.11.11` 및 upstream
   `uv.lock`으로 격리한다. Showdown은 pinned `package-lock.json`에 대해 `npm ci`로 설치한다.
4. Showdown server는 `127.0.0.1:8000`에만 bind하고 `--no-security --ai-tournament`로 실행한다.
5. Cloud provider는 direct Ollama Cloud API `https://ollama.com`, model은 `glm-5.3-flash`로
   고정한다. 다른 model/provider 또는 local Ollama daemon으로 fallback하지 않는다.
6. Cloud command의 `OLLAMA_API_KEY` resolution은 다음 순서를 사용한다.
   1. 비어 있지 않은 invoking process environment 값
   2. Git에서 제외된 repository root `.env`의 `OLLAMA_API_KEY`

   Process environment가 항상 우선한다. CLI는 `.env`를 shell로 실행하거나 source하지 않고
   `KEY=VALUE` assignment로만 해석하며, root `.env`에서 `OLLAMA_API_KEY`만 process에 주입한다.
   `.env`는 regular file이고 group/other access가 없는 permission이어야 한다. 추적되는
   `.env.example`에는 빈 값만 둔다.
7. Key 값은 tracked source/config, command argument/output, log, test fixture 또는 qualification
   artifact에 기록하지 않는다. Root `.env`는 유일하게 승인된 영속 secret file이며 재현성
   evidence가 아니다. Cloud client를 포함하는 현재 Python process 외의 spawned child process에는
   key를 전달하지 않는다.
8. Cloud request timeout은 120초, output token 상한은 512, context는 8192다. 실제 provider
   identity와 비밀이 아닌 response metadata만 qualification artifact에 기록한다.
9. Qualification은 deterministic local one-battle smoke, real API probe와 PokéChamp IO
   one-battle smoke를 구분한다. 성공은 interface/runtime 실행 가능성만 뜻하며 efficacy evidence나
   성능 개선 claim이 아니다.
10. `pokechamp/LICENSE` 원문과 provenance를 보존하고, 재배포 전에 비표준 일본 제한 문구를
    포함한 실제 조건을 별도로 검토한다.

## 거절한 대안 (Rejected Alternatives)

- Process environment만 사용: terminal 또는 IDE session마다 재입력해야 하므로 사용자의 영속
  설정 요구를 충족하지 않는다.
- `.env`를 Git에 추적: 실제 secret의 repository/history 유입 위험 때문에 채택하지 않았다.
- `.env`를 shell로 source: credential 파일의 shell syntax를 실행할 필요가 없으므로 채택하지
  않았다.
- Local Ollama 또는 provider/model fallback: qualification provenance를 바꾸고 failure를 숨길 수
  있으므로 채택하지 않았다.

## 근거 (Rationale)

Ignored root `.env`는 개인 연구 환경에서 terminal lifecycle과 독립적인 credential persistence를
제공한다. Process override를 유지하면 CI나 일회성 실행이 local file을 수정하지 않고 명시적으로
값을 교체할 수 있다. Narrow parser, file permission gate, child-process 제거 및 artifact redaction은
영속 저장으로 늘어난 노출 범위를 제한한다.

## 영향 (Consequences)

- [`EP-001`](../exec-plans/completed/EP-001-pokechamp-reproducible-environment.md)은 root `.env` loader,
  `.env.example`, ignore rule과 검증을 유지한다.
- 실제 key는 각 local checkout의 `.env`에 별도로 입력해야 하며 checkout/repository evidence로
  복제되지 않는다.
- `.env`가 group/other에 공개되어 있거나 malformed이면 cloud command는 network call 전에
  실패한다. Key 부재와 auth/model/rate-limit/timeout/transport failure도 fallback 없이 실패한다.
- 향후 source commit, provider, model, endpoint, credential resolution/storage policy 또는 bind
  exposure를 바꾸려면 이 결정을 대체하는 새 decision과 bounded exec plan이 필요하다.
- 이 결정은 L1-L5 mapping, baseline/treatment, metric, hypothesis 또는 efficacy protocol을
  채택하지 않는다.

## 증거 (Evidence)

- 2026-09-04 사용자 지시: 개인 연구 프로젝트에서 `.env` 영구 저장과 Git 예외 처리를 승인.
- [`D-005`](D-005-adopt-pokechamp-l1-l5-research-goal.md)
- [`D-006`](D-006-adopt-pokechamp-environment-boundary.md)
- [`C-008`](../CONTRACTS.md)
- [`EP-001`](../exec-plans/completed/EP-001-pokechamp-reproducible-environment.md)

2026-09-14: [D-054](D-054-zai-provider.md)이 새 배틀의 공급자 선택·환경 로더·전송 표현을 부분 대체한다. 당시 실행·검증은 보존한다.

2026-09-21: [D-070](D-070-jev-client.md)이 독립 JEV 호출의 환경 로더·비밀 관리 범위를 확장한다. 배틀 계약은 유지한다.
