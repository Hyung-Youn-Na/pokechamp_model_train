# EP-089 — EX-057 제출 팀 역할 대조

- 상태: Completed
- 생성일: 2026-09-22
- 승인: 사용자의 EX-057 DB 조건 일치 역할 부여 계획 구현 지시.
- 근거: [INDEX](../../../INDEX.md#workflow), [CHARTER](../../../CHARTER.md), [RD 해석](../../../research/rule-learning/DESIGN.md#12-해석-규칙-interpretation-rules), [EX-057](../../../research/input-and-memory/experiments/EX-057-jev-pinned32.md).

## 범위·판정

봉인 manifest의 팀1/2/6/12 총24슬롯과 현재 열람 DB를 대조한다.
아이템·특성·기술·기본 타입·제출 테라 타입만 사용한다. 노력치·성격·사용률 제외.
strong/supporting 하나 이상 일치, 반대 일치 없음이면 부여한다. 양쪽 일치는 mixed로 별도 표시.
all_of는 전조건 일치, prior는 참고값이다. 모든 후보의 판정과 원본 해시를 증거로 보존한다.
양쪽 제출문을 아는 사후 기술적 대조이며 당시 모델의 관측·역할 판단 또는 효능 증거가 아니다.
기존 active 실험을 재개하지 않고 원본·운영·연구 방법은 변경하지 않는다.

## 완료 기준

- [x] 제출문 해시·4팀×6슬롯·DB 대응 검증.
- [x] 판정별 일치 근거·분모 보존 및 출력.
- [x] 수정 금지 원본 해시 불변, 노력치/제외 역할 미사용 확인.

## 진행·중단

등록 후 표준 라이브러리 오프라인 대조. API·배틀·비용0.
기존 active plan과 실행 범위 중첩 없음. 복구·재수집·시계·뷰어 해당 없음.
[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다.

## 결과 및 증거

[전체 구성·역할 표](../../../exec-plans/evidence/ep089/report.md), [전수 판정 JSON](../../../exec-plans/evidence/ep089/result.json),
[재현 스크립트](../../../exec-plans/evidence/ep089/assess.py).
4팀·24슬롯·21종, 후보149개 중 부여96·미일치53·충돌0·반대 단독0.
제출문4개 해시 검증, 조건 원자 집합을 사용하는 독립 대조로149개 판정 전수 검증,
입력3파일 해시 불변 확인. 노력치 생략 때문에 일부 근거가 넓어진 열람용 판정임을 보고했다.
원본 실험·DB·운영 상태 변경 없음. STATUS 갱신 없음.
