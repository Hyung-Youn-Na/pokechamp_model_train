# D-024 — 상태 처리 정비와 요약 thinking 비교

- Status: Accepted
- 날짜: 2026-09-08
- 근거: 사용자가 전달한 EX-022 구현·검증·72호출 실행 계획.

## 결정과 근거

EX-021의 weather 의미/평가 턴 오류와 Future Sight 경과 counter의 시작 턴 오해를
출발점으로 protocol/request→parser→정규화→계산/요약 경계의 전달 필드 전체를 검토한다.
원본 근거로 재현한 필수 범위 오류를 고치고 parent 공통 protocol 의미 해석을 사용한다.
실제 사건 턴은 행 순서로 정하며 설치 턴·마지막 갱신·경과 counter·겹 수를 구별한다.
미지원 상태를 정상0으로 채우거나 계산기 전체 지원 범위를 확대하지 않는다.
FixedBackend summary_thinking_effort=low|high는 summary/summary_rollup에만 적용하며
기본 및 행동 역할은 low를 유지한다. 전송값과 기록값은 요청마다 한 번 결정한다.
정비된 운영 요약 입력에서 장면당 입력 하나를 만들고 반복 request 원본을 보존한다.
EX-021의 동일12장면·io actor·첫10행동 이후·이전 요약 없는 첫 경계를 사용한다.
low/high의 system/user prompt는 바이트 단위로 동일하다. 모델 glm-5.3-flash,
temperature0, seed100, 출력131072, provider 기본 context, 기존 summary system prompt와
전략을 고정한다. 유일한 요청 조건 차이는 summary thinking low/high다.
12장면×2조건×3반복=72호출; 순서 seed20260908로 장면을 섞고 선행 조건을 균형 교대한다.
요청/모델 permit10/10, retry_transient=0, 호출마다 독립 backend/context다.
추가 유료 probe·Cloud 채점·실제 배틀·다른 모델 비교·운영 기본 변경은 제외한다.
EX-022 첫 Cloud 제출부터1시간,45분 신규 제출 중지,60분까지 응답 보존·정리하며
재시작으로 시계를 초기화하지 않는다. 모델 요약 사실/형식 오류만 측정하며 수집을 계속한다.
Provider·환경·무결성·입력·평가 기준 오류에는 전체 중단한다. 보충·재질문·실행 중 수정은 없다.

평가 사실은 운영 변환을 사용하지 않고 원본 행에서 독립 작성·검증·봉인한다.
조건/thinking을 가린 응답을 검토한다. 주지표는 중요 사실 오류·필수 사실 누락·형식 위반
중 하나 이상인 요약 비율이다. 장면별3반복을 먼저 집계하여 low/high를 대응 비교한다.
누락·필수 사실 보존율·사실 주장 오류·모순·실제 token·HTTP 지연을 함께 보고한다.
EX-020 기존4/EX-021 추가8을 따로 보고 모두 이미 사용한 개발 자료임을 명시한다.
이전 무효 low 응답은 분모에서 제외한다.72응답과 근거 연결 검토 완료가 진단 완료다.
중단 시 미완료 분모를 보존한다. 운영 적용/EX-020 재개는 결과로 자동 승인하지 않는다.

## 영향과 증거

C-016과 RESEARCH_DESIGN에 명시적으로 새 범위를 채택한다. D-023의 과거 실행은
대체·복구하지 않는다. EX-020/021의 halt·receipt·clock·봉인 자료와 EP-011/012 Blocked를 보존한다.
[공식 모델 설명](https://ollama.com/library/glm-5.3-flash)은 low/high/max 지원을 명시한다
(2026-09-08 확인). high의 오류 감소는 이번 대응 비교의 미확정 질문이다.
[EP-013](../plans/EP-013-state-summary-thinking.md),
[EX-022](../experiments/EX-022-state-summary-thinking.md).

## 실행 근거와 한계

EX-022는72응답 수집 후 공개 Supreme Overlord 발동과 정규화 특성의 불일치로 중단됐다.
이는 C-016 위반이며 사전 입력 검증의 누락이다. 중단 규칙·기준·분모를 바꾸지 않고 전체
효과 추정을 무효화했다. halt 이후 로컬 특성 전달·독립 검사·새 profile 중단 보고의 교정은
기존 입력/응답에 소급하지 않는다. 운영 기본 변경이나 추가 Cloud 호출을 승인하지 않는다.
