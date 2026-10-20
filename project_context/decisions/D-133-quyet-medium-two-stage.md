# D-133 — Quyet-Medium 2단계 정책 동일32경기

- Status: Accepted
- Date: 2026-10-13
- 승인: 현재 사용자가 제공한 계획의 구현·검증·새32경기 실행 지시

EX-083의 고유32슬롯을 Quyet-1.0-Medium으로 모두 새로 평가한다. 기존 경기 성적은 계승하지
않는다. 사용자가 선택한4GPU·기술/교체2단계·무절단 긴 입력을 별도 처치로 채택한다.
공식 모델/revision·코드 pin·prompt v1·보정값은 유지하고 상태/전체 prompt 한도만32768로
명시 확장한다. 모델 가중치만의 효과나 일반적 성능 우위로 해석하지 않는다.

조건·자원·GPU 최대9회 검증·분모·중단·비교 원문은
[EX-084](../experiments/EX-084-quyet-medium-two-stage.md), runtime은
[C-065](../CONTRACTS.md#c-065-quyet-two-stage), 진행은
[EP-138](../exec-plans/completed/EP-138-quyet-medium-two-stage.md)이다.
기존 EX-082/083·Blocked/Paused·환경·원자료·봉인은 보존한다.
