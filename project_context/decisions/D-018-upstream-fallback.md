# D-018 — 원본 행동 생성과 출력 fallback 조건

- Status: Accepted
- 날짜: 2026-09-07
- 근거: 사용자가 전달한 원본 fallback 병렬32판 구현·실행 지시.

## 결정

별도 봉인 조건 `action_policy="upstream"`에서 원본 IO 프롬프트, Ollama 접미사와 추출,
행동 변환, 일반10회/검색 내부2회 재시도와 fallback을 복원한다. 출력 오류만 회복 대상이다.
Provider·인증·모델·환경·무결성 오류는 terminal이다. 필드 부재는 기존 strict 정책이다.
닉네임 식별·parser 전달·격리·원자료 기록과 Cloud 모델/effort/temperature/예산/context/timeout,
팀/seed/진영/대진을 유지한다. Pinned source와 depth/상대 fallback 자기 팀 참조는 수정하지 않는다.

EX-016 core-repeat32를 배틀10/요청10, retry_transient=0으로 실행한다. D-017의144회 및8판
gate는 이 조건에 적용하지 않는다. 고정 fixture·RNG 동등성·기존 회귀·팀6/12 양진영 fake
provider 로컬2판 검증을 먼저 통과한다. Cloud 시작부터4시간,3시간45분 신규 중지/15분 정리다.

역할별 출력 파싱/연결 실패, IO ID/시도/회복, 단계별 fallback 진입과 실제 전송 출처를 기록한다.
검색 후보와 상대 예측을 실제 자기 전송에서 분리한다. 전송 판단은 중첩 fallback에도1회만 센다.
전체 시도/유효 완료 각각 IO/minimax별 분모·비율을 보고하며 실패 비용도 보존한다.
Fallback 정상 종료는 유효 결과다. 과거 결과는 불변이며 오류 없는 minimax 성능이나 최대 처리량
검증으로 해석하지 않는다.
