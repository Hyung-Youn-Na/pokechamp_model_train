# D-070 — JEV 환경 설정과 독립 호출 기반

- 상태: Accepted
- 날짜: 2026-09-21
- 승인: 현재 사용자 계획 구현 지시
- 부분 확장: [D-007](D-007-adopt-pokechamp-dotenv-credential.md), [D-054](D-054-zai-provider.md)의 환경 로더·비밀 관리 범위. 배틀 계약은 유지한다.

## 맥락·결정

사용자는 JEV의 환경 설정·독립 호출 기반을 선택했다. JEV는 Chat Completions와 다른
상태/질문 기반 API다. 기존 httpx로 별도 클라이언트를 제공하며 runtime 원문은
[C-044](../CONTRACTS.md#c-044-jev)에 둔다. 공식 변수명 TYPESAFE_API_KEY를 사용한다.

## 대안·근거

변수만 추가하는 방식은 선택된 호출 기반 범위를 충족하지 않는다. 배틀 통합은 별도 범위다.
추가 SDK 없이 기존 환경을 활용하고 공식 HTTP 계약을 모의 전송으로 검증한다.

## 영향·증거

JEV 키도 공통 비밀 제거와 자식 환경 제외에 포함한다. 배틀 공급자·연구 조건·과거 봉인은
변경하지 않는다. 실제 API 호출은 이번 범위 밖이며 계정 연결은 미검증이다.
[공식 API](https://docs.typesafe.ai/api), [EP-061](../plans/EP-061-jev-client.md).
