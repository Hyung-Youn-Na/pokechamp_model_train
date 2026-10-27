# D-014 — Cloud 요청 timeout 300초

- 상태: Accepted
- 날짜: 2026-09-07
- 근거: 사용자가 요청 timeout을 120초에서 300초로 늘리도록 명시적으로 지시했다.

새 Ollama Cloud client의 timeout을 300초로 변경한다. Benchmark의 이미 진행 중인 응답
보존 대기도 요청 timeout + 5초로 계산하고, 부모 강제 종료 여유는 요청 timeout + 60초로
계산한다. 이전 125초/180초 값이 300초 요청을 먼저 끊지 않게 한다.
경기 자체 watchdog 1200초, 출력 131072, 모델 및 fail-closed 정책은 유지한다.
CLI manifest와 새 benchmark plan/actor metadata는 실제 요청 timeout을 기록한다.

D-013/C-008의 요청 timeout만 대체한다. 과거 실험 설정·결과는 변경하지 않는다.
새 pilot/main을 실행하는 변경이 아니며 회귀 테스트로 client 설정과 종료 경로를 검증한다.

검증: client factory에 timeout=300.0 전달 및 새 plan metadata의 300초 기록을 확인했다.
종료·peer cancellation 경로를 포함한 전체 76 tests와 changed-file Ruff 통과.
