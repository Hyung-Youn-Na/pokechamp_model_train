# D-060 — 공급자 오류 재시도 확대·정상 경기 viewer

- 상태: Accepted
- 날짜: 2026-09-16
- 승인: 현재 사용자 계획 구현 지시 및 오류 범위/429 소진 후 전체 중단 선택

새 전송 기본값 provider-retry-v2를 채택한다. 연결 오류·연결/읽기/쓰기/pool timeout·HTTP5xx·429에
1초/2초/4초 최대3재시도(총4시도)를 적용한다. 최종 실패429는 전체 신규 수집 중단이다.
Retry-After는 기록만 하고 고정 backoff를 바꾸지 않는다. 기존 timeout과 admission/permit 경계는 유지한다.
과거 connect-retry-v1/legacy·EX-042 첫429 중단 및 봉인은 소급 변경하지 않는다.
EX-042 정상 완료26경기와 기존52 actor viewer를 새 목록으로 연결한다.
구현·무외부호출 검증은 [EP-049](../exec-plans/completed/EP-049-provider-retry-viewer.md)에서 완료했다.
