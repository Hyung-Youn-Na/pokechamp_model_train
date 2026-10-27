# D-163 — 독립 OpenAI Decisions API 환경

- 상태: Accepted
- 날짜: 2026-10-20
- 승인: 사용자의 API 환경 구성 요청. API 키는 사용자가 `.env`에 입력한다.

## 맥락·결정

`gpt-6-luna`의 공식 Decisions endpoint를 독립 `httpx` 클라이언트와 전용 가상환경으로 제공한다.
루트 `.env`의 OPENAI_API_KEY, 프로세스 환경 우선(빈 값 포함), 파일600·Git 제외를 적용한다.
[D-007](D-007-adopt-pokechamp-dotenv-credential.md)의 원래 배틀 공급자 경로는 변경하지 않는다.
독립 경로에서 `python-dotenv`를 변수 확장 없이 사용하며 파일을 shell로 실행하지 않는다.

## 대안·근거

기존 배틀 환경의 SDK 업그레이드 대신 별도 HTTP 환경을 사용해 기존 의존성에 영향을 주지 않는다.
공식 HTTP API로 요청하므로 SDK의 Decisions 리소스 지원 여부에 의존하지 않는다.

## 영향·증거

실제 유료 호출·배틀 통합·연구 방법 변경은 이번 환경 준비의 범위 밖이다.
고정 endpoint·모델, timeout60초·재시도0·redirect 금지와 오류 비밀 비출력은
[C-078](../CONTRACTS.md#c-078-openai-decisions)에 둔다.
[공식 문서](https://developers.openai.com/api/docs/guides/decisions),
[EP-178](../plans/EP-178-openai-decisions-environment.md).
