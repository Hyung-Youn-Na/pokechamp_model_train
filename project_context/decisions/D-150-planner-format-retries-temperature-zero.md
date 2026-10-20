# D-150 — GLM 응답 형식 재시도·기본 temperature0

- 상태: Accepted
- 날짜: 2026-10-15
- 승인: 사용자 “통신오류가 아닌 응답 형식오류에 해당하면 GLM 모델은 재시도”,
  “그냥 기본 설정을 temperature 0으로 설정해서 실험해 앞으로도 그렇게 하고”

새 GLM planner 기본 temperature를0으로 바꾸며 재시도에도 같은0을 사용한다. JEV 공식 calibration
온도는 변경하지 않는다. 새 planner.retry_scope=response_format은 JSON 구문/중복키/비유한값·
계획 스키마·빈/잘린 응답·잘못된 성공HTTP envelope를 최대5회 추가 재생성한다.
기존 json_retries 상한을 한 번만 적용하며 오류 종류별로 예산을 중첩하지 않는다.
메시지/관측/다른 옵션은 동일하고 원문·usage/오류/생성차수·모든 물리HTTP를 보존한다.
통신 재시도는 기존 정책, 전략적으로 나쁜 유효 계획은 재생성하지 않는다.
과거 동결 설정은 온도/범위를 보존한다(retry_scope 부재는json_syntax).
EX-096 실패를 보존하고 [EX-097](../experiments/EX-097-planner-format-temperature-zero.md)의
새 GPU0 단일적재·8사전추론·같은 서버1경기로 실행한다. 반복 확률은 D-149의 진단 정책을 유지한다.
진행은 [EP-156](../exec-plans/completed/EP-156-planner-format-temperature-zero.md)다.
