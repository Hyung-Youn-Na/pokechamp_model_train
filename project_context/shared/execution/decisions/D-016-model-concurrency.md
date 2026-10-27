# D-016 — 계정·모델 요청 제한과 병렬 운영 측정

- Status: Accepted
- 날짜: 2026-09-07
- 근거: 사용자가 모델별 동시성 측정과 병렬 배틀 실행 계획 전체 구현·검증을 지시했다.

## 결정

기존 8/32/40판 일정과 과거 evidence를 보존하면서 execution-config를 plan에 seal한다.
기존 실행 설정 부재는 순차다. Qualification은 8000을 유지하고 benchmark 전용 서버는
8100–8109, 127.0.0.1 bind, localhost client, 경기별 process/worktree/seed/log를 쓴다.
전역 benchmark lock을 유지하며 coordinator의 Unix socket broker가 계정·모델 permit을
원자적으로 부여한다. Credential/prompt는 broker에 보내지 않는다. 연결 유실은 요청 timeout까지
permit을 보류하고 broker 실패는 fail-closed한다. 429는 Retry-After 또는 30초 공통 대기다.

Max 공식 계정 한도 10은 https://ollama.com/pricing 에서 2026-09-07 확인했다.
https://ollama.com/library/glm-5.3-flash 에 별도 모델 한도는 없으므로 unknown으로 기록한다.
실측 운용 상한은 계정·모델·요청 조건·evidence에만 적용하며 다른 모델을 활성화하지 않는다.

실측은 총 4시간, 3시간45분 신규 작업 중지·취소, 마지막 15분 정리다. 구현/로컬 테스트는 제외한다.
EX-003 성공 호출에서 IO action/minimax action/opponent/tool/score 각각 고정 4개,
총 20개를 deterministic source 순서로 선택하여 hash와 조건을 호출 전에 seal한다.
1–10 동시성, 3반복, 첫 반복 오름차순, 다음 반복 seed 20260907의 고정 shuffle 순서다.
30분 한도이며 실패 보충 호출은 없다. 전송 오류 수준 이상 탐색 중단, hard error 전체 중단.
3반복 전송 오류 없음, p95가 순차 2배 이하인 후보 중 최고 중앙 JSON 처리량의 95% 이상을
내는 최소 동시성 C*를 선택한다. 서버 내부 병렬 처리 보장은 주장하지 않는다.

C*>=2이면 같은 source·8판 일정의 순차(1/1)·병렬(min(C*,8)/C*)을 새 ID로 비교한다.
실행 순서는 seed 20260907로 사전 고정한다. 병렬 integrity/격리 정상, 429/timeout 없음,
유효 완료가 순차 이상이고 batch 경과 시간이 짧을 때만 32판을 고려한다.
대진별 관측 시간을 32판 일정의 빈 실행 자리에 배정한 예상 ×1.5가 남은 신규 작업 예산에
들어갈 때 C* 배틀/C* 요청으로 시작한다. 미실행·실패 slot을 분모에 보존한다.
Minimax depth/알고리즘/모델/출력/context/경기 watchdog은 변경하지 않는다.
이 기준은 소표본 운영 기준이며 효능·완료율 차이의 통계적 확증이 아니다.
