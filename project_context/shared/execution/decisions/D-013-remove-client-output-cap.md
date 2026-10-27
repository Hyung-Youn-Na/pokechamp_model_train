# D-013 — 사용자 지시에 따른 LLM 출력 상한 최대화

- 상태: Accepted
- 날짜: 2026-09-07
- 근거: 사용자가 응답 잘림을 막기 위해 출력 한도를 최대로 늘리도록 명시적으로 지시했다.
- 대체 범위: D-009/C-008의 512 output / 8192 context 경계만 대체한다.

새 Cloud 호출은 모델 공식 최대 출력 128K에 맞춘 `num_predict=131072`를 사용한다.
Upstream의 20/64/100/500 등 작은 max_tokens 인자로 다시 제한하지 않는다. `num_ctx`를
생략하여 Cloud의 최대 context 기본값을 사용하며 metadata의 context_window=null과
context_window_policy=provider_default는 provider 기본값 사용을 뜻한다.

근거: [모델 개발사 문서](https://docs.z.ai/guides/vlm/glm-5.3-flash)는 최대 출력 128K,
context 1M을 명시한다. [Ollama context 문서](https://docs.ollama.com/context-length)는 Cloud가
기본적으로 최대 context를 사용한다고 명시한다. Model은 glm-5.3-flash 그대로다.
Think low, compact JSON 지시, 첫 오류 fail-closed, 요청 timeout 120초와 경기 watchdog은 유지한다.

## 실제 Cloud 호환성 확인

[일반 Ollama parameter 문서](https://docs.ollama.com/modelfile)의 num_predict=-1은 이 Cloud
endpoint에서 HTTP 400 (`max_tokens must be positive`)으로 거부됐다. 이 설정은 채택하지 않는다.
실패 probe를 `probe-output-cap/20260906T233828.405659Z`에 보존했다. 추가 진단 요청에서도
동일한 HTTP 400을 확인했다. 1048576 양수 budget의 짧은 요청은 accepted/stop이었지만,
그만큼 실제 출력할 수 있다는 증거가 아니므로 모델 공식 출력 한도 128K를 기준으로 선택한다.
이 경계 probe는 `probe-output-boundary/20260906T233902.629882Z`에 보존했다.

검증은 최종 설정의 요청·metadata 회귀 검사와 512 tokens를 넘는 JSON 기술 probe다.
새 pilot 또는 본 실험은 실행하지 않는다. 과거 EX-001/EX-002 source, 설정, 결과와 파생
보고서는 변경하지 않는다. 새 조건의 결과/비용을 이전 pilot과 혼합하지 않는다.
서비스 자체 제한과 timeout 때문에 모든 응답의 완결을 보장하지 않으며, 잘린 응답을 성공으로
숨기거나 자동 재시도하지 않는다.

## 최종 검증

최종 131072 budget probe는 `.artifacts/pokechamp/probe-output-cap/20260906T233945.481389Z/manifest.json`에
보존했다. 요청한 1..300 정수 배열을 완전하게 반환했고 입력 62/출력 685 tokens,
done_reason=stop, JSON valid, 3585ms였다. 이전 512 상한 초과 응답의 완결을 확인했다.
전체 76 tests와 changed-file Ruff 통과. EX-002의 40 match/80 actor source와 기존 지표가
불변임을 검증했다. 외부 submodule clean 및 probe credential 비노출을 확인했다.

2026-09-07 후속 [D-014](D-014-increase-cloud-request-timeout.md)이 새 요청 timeout을 300초로 변경했다.
위 120초는 D-013 검증 당시 설정이다.

2026-09-14: [D-054](D-054-zai-provider.md)이 새 배틀의 공급자 선택·환경 로더·전송 표현을 부분 대체한다. 당시 실행·검증은 보존한다.
