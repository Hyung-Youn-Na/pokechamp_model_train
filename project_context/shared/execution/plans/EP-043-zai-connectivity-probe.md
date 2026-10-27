# EP-043 — Z.ai 단일 연결 확인

- 상태: Completed
- 생성일: 2026-09-14
- 승인: 사용자가 주소·키 입력 후 간략한 호출 테스트를 명시적으로 요청했다.
- 계약: [C-034](../CONTRACTS.md#c-034-provider), [D-054](../decisions/D-054-zai-provider.md)

## 범위·완료 기준

기존 CLI probe로 짧은 status_ok JSON 요청을 최대1회 보낸다. 모델·전송 옵션은 C-034 유지.
재시도·배틀·중단 실험 재개·키 출력은 없다. 성공 또는 실패 metadata와 artifact를 확인해 보고한다.
연결 자격 확인이며 연구 실험·효능 검증이 아니므로 실험 복구·재수집·시계는 해당 없다.
기존 active 중단 plan의 실행·자료는 변경하지 않는다.

## 진행·검증

2026-09-14: 승인·등록. 실제 요청 전.

## 결과

단일 실제 Z.ai 요청 성공, status_ok JSON 검증 통과. HTTP 200, 모델 glm-5.3-flash, 1713ms.
입력 95 / 출력 15 tokens. 재시도·배틀0.
[호출 artifact](../../../../.artifacts/pokechamp/probe/20260914T234619.921098Z/manifest.json)에 비밀 없는 metadata를 보존했다. 실제 배틀 기능·효능은 미검증이다.
