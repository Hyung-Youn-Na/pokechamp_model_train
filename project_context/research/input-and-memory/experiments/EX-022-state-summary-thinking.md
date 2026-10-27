# EX-022 — 상태 처리 정비 후 요약 thinking 비교

- Status: Blocked / invalidated / 진단 미완료
- 생성일: 2026-09-08
- 관련: [D-024](../decisions/D-024-state-summary-thinking.md),
  [EP-013](../plans/EP-013-state-summary-thinking.md)

## 질문 및 사전 protocol

정비된 동일 입력에서 요약 thinking high가 low보다 사실/누락/형식 오류를 줄이는가?
방향을 확정하지 않는 탐색적 대응 비교다.
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

## 검증과 출처

Cloud 전에 기존244+추가회귀, Ruff/Python compile/관련 Node,15장면 의미·구조와
사후3건 계산 대조, fake72 lifecycle을 통과한다. source/원본/입력/기준/일정/검증 receipt를
`.pokechamp-data/summary-diagnostics/ex022/`에 봉인한다. 모델 응답을 본 후 기준을 바꾸지 않는다.

## 결과

사전289회귀·Ruff·compileall·Node11·15장면 구조/의미·사후3건과 fake72 lifecycle을 통과했다.
72/72호출을 제출·수집했고 배치110.21초, Provider 실패·미실행·미확정0이었다.
조건/thinking/token을 숨긴 검토 중 scene1 원본 event58 line5의
`|-activate|p1a: Kingambit|ability: Supreme Overlord`가 정규화 입력에서는
`ability=null`, `ability_known=false`인 모순을 발견했다. 원본 발생은 turn7이며 뒤의
turn8 마커와 구별한다. 일부 응답은 `ability_known false`를 그대로 기술했다.

사전 입력 검증은 모든 자기 request 필드와 주석 행을 대조했지만, 공개 발동과 상대 특성
필드의 일치를 직접 검사하지 않았다. C-016과 실제 입력의 충돌을 기록하고 전체 비교를
중단·무효화했다. 사전289통과 receipt는 당시 사실로 보존하되 현재 자격을 철회했다.
유효 검토0/72, 무효 초안6/72 보존, 나머지66/72 검토 중단이다. 기존0/4·추가0/8의
유효 대응이며 low/high 오류·누락·보존율·형식·주장 오류·모순 차이는 미확정이다.
해당 입력의 노출은 low3/high3이지만 모델 오류 재현율이 아니다. 나머지 장면만 골라
사후 비교하지 않았고, 이전 무효 low 응답을 분모에 넣지 않았다.

첫 collection 상태 조회에 일부 원래 blind_id와 조건이 출력됐다. 응답 내용을 읽기 전에
별도의 비결정적 무작위 alias로 다시 봉인했고 검토 중 그 매핑을 열지 않았다.
설계를 아는 단일 검토자이며 독립 이중맹검이 아니다. 전체 검토 초안과 재명명 근거를 보존한다.

중단을 먼저 봉인한 뒤 로컬 공개 특성 전달과 독립 검사를 수정했다. Supreme Overlord,
Quark Drive, Protosynthesis의 holder 발동 행을 반영하며, 임시 특성을 원래 특성으로
확정하지 않는다. 이 수정은 기존72입력/응답에 소급하지 않으며 재호출·보충·Cloud 채점은0이다.
중단 보고는 입력 hash와 실패 근거를 검증하여 계속 읽을 수 있지만 실행·검토 복구는 차단한다.
EX-020/021의 자료와 중단 상태, 운영 기본 low는 유지한다.

중단 후 최종296회귀(기존244+추가52), Ruff·compileall·Node11,15장면 구조/의미·사후3건,
fake72의 중단 보고/복구 거부 검사가 통과했다. 이 결과는 로컬 교정의 검증이며 EX-022
비교의 유효성이나 운영 Cloud 자격을 회복하지 않는다.

|실측 자원|low 36호출|high 36호출|
|---|---:|---:|
|prompt tokens|1,101,810|1,101,810|
|completion tokens|40,090|63,527|
|평균 HTTP 지연|11.793초|15.372초|

모든 응답의 token metadata를 확보했다. 전체2,307,237 tokens이며 금전 청구액은 측정하지
않았다. 잘못된 입력을 포함한 수집 비용이다. 오류 감소당 효율이나 유효 treatment 비용
효과로 해석하지 않는다.

- [검증 receipt](../../../../.pokechamp-data/summary-diagnostics/ex022/verification.json)
- [입력·일정 봉인](../../../../.pokechamp-data/summary-diagnostics/ex022/manifest.json)
- [상태 전달 감사](../../../experiments/ex022-state-audit.md)
- [입력 오류 근거](../../../../.pokechamp-data/summary-diagnostics/ex022/input-transform-failure.json)
- [중단 봉인](../../../../.pokechamp-data/summary-diagnostics/ex022/halt.json)
- [중단 보고서와 실측 비용](../../../../.pokechamp-data/summary-diagnostics/ex022/report.md)
- [중단 후 로컬 검증](../../../../.pokechamp-data/summary-diagnostics/ex022/poststop-verification.json)
