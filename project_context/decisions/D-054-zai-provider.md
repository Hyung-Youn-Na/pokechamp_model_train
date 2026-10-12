# D-054 — Z.ai 배틀 공급자 선택

- 상태: Accepted
- 날짜: 2026-09-14
- 승인: 현재 사용자의 Z.ai 연결 구현 계획
- 부분 대체: [D-007](D-007-adopt-pokechamp-dotenv-credential.md)의 Ollama 단일 공급자·환경 로더 범위 및 [D-013](D-013-remove-client-output-cap.md)의 전송 필드 표현. 과거 실행에는 소급하지 않는다.

## 결정·근거

공통 배틀 backend가 Ollama와 Z.ai를 명시 선택한다. 구체적 runtime 원문은
[C-034](../CONTRACTS.md#c-034-provider)다. 프로세스 환경 우선, 로컬 .env 기본 zai,
모델 glm-5.3-flash 유지와 주소·키 사용자 입력은 명시적 사용자 지시에 따른다.
공식 [Chat Completions 계약](https://docs.z.ai/api-reference/llm/chat-completion)의
Bearer 인증·thinking·reasoning_effort·response_format과 응답 변환을 구현한다.
Z.ai 공식 요청 필드에 seed가 없으므로 전송하지 않고 미적용을 기록한다.
요청 실패에서 재시도·공급자/모델 대체를 추가하지 않는다.

## 대안·영향

단일 Ollama 고정은 승인된 Z.ai 연결을 충족하지 않는다. SDK를 추가하지 않고 기존 httpx를 사용한다.
기존 backend 인터페이스와 검증/viewer를 유지하며 새 준비 자료는 비밀 없는 공급자 설정을 봉인한다.
과거 미기재 자료는 Ollama로 해석한다. 실제 API 호출·계정 모델 지원 확인은 이번 범위 밖이다.
모델명 변경·연구 조건/평가 변경·기존 중단 실험 재개는 승인하지 않는다.
[EP-042](../exec-plans/completed/EP-042-zai-provider.md)에서 로컬 검증한다.

2026-09-21: [D-070](D-070-jev-client.md)이 독립 JEV 호출의 환경 로더·비밀 관리 범위를 확장한다. 배틀 계약은 유지한다.
