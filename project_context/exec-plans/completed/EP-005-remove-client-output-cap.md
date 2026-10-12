# EP-005 — Cloud 출력 상한 최대화

- 상태: Completed
- 완료일: 2026-09-07
- 생성일: 2026-09-07
- 근거: 사용자 출력 한도 최대화 지시 및 [D-013](../../decisions/D-013-remove-client-output-cap.md)

## 목표와 범위

새 호출의 512-token 상한과 8192-context override를 제거한다. Parent adapter, benchmark
metadata, 테스트와 현재 문서만 수정한다. 외부 submodule 및 과거 실험 artifact는 보존한다.

## 완료 기준

- [x] 실제 요청에서 num_predict=131072, num_ctx 생략; 작은 upstream 인자가 제한을 복구하지 않음
- [x] Cloud/benchmark metadata 일치 및 과거 sealed plan 분석 호환
- [x] 요청 회귀 테스트와 512 tokens 초과 단일 JSON 기술 probe 검증
- [x] 현재 contract/설계/상태 문서 갱신; 새 pilot/main 미실행

## 진행

구현 전 등록. Source/model/credential 경계를 유지하며 key를 기록하지 않는다.

일반 Ollama의 -1은 실제 Cloud에서 거부되어, D-013에 근거를 남기고 모델 공식 최대 128K로 변경했다.

## 결과

출력 예산 131072와 provider 기본 context를 적용했다. 작은 upstream budget이 재적용되지
않고 CLI/benchmark 설정·call metadata가 실제 요청과 일치한다. 새 plan은 LLM 설정을 명시한다.
76 tests 및 Ruff 통과. 실제 685-token JSON probe가 stop/complete로 끝났으며 D-013에
artifact를 기록했다. -1 실패와 큰 budget의 짧은 진단 요청도 구분 보존했다.
과거 40 match/80 actor와 지표 불변, submodule clean 및 credential 검사를 통과했다.
새 pilot/main은 실행하지 않았다. 요청 120초 및 경기 watchdog은 유지한다.
