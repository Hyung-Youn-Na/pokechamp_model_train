# D-068 — 공식 관측 비동기 완료 경계 교정

- 상태: Accepted
- 날짜: 2026-09-17
- 승인: 현재 사용자 계획 구현 지시

공식 클라이언트가 정상 타이머로 처리를 양보하는 경우 queue와 종료 처리가 완료된 후
request 정규화·snapshot을 반환한다. 시계 조작·고정 대기·검사 삭제로 대체하지 않는다.
Node 명령 직렬화와 실패 부분 상태 폐기, Python 요청 전체30초 제한을 적용한다.
공식 upstream/build·schema·prompt·계산 의미와 EX-045 중단/원자료/수집 source를 보존한다.
[EP-058](../plans/EP-058-official-async.md)의 오프라인 및 별도 무유료8경기 검증을
승인하며 유료 호출·재수집·과거 실험 재개는 포함하지 않는다. C-043의 입력 경계를 교정한다.


## 구현 근거·검증

공식 headless scene의 NaN interruption counter가 타이머 재개를 무조건 취소하는 추가 원인을
실제 지연으로 확인했다. 연결부에서 정상 scene 초기값1로 설정하며 공식 시계/build는 유지한다.
[EP-058 최종 보고](../../../exec-plans/evidence/ep058/report.md)에 재현·회귀·보존 재생·별도 로컬 검증과
새 source 봉인을 연결한다. 수정 완료가 EX-045 비교 완료·재개를 뜻하지 않는다.
