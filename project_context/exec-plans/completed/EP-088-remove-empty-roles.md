# EP-088 — 빈 근거 역할 두 개 제거

- 상태: Completed
- 생성일: 2026-09-22
- 승인: 사용자의 두 역할 제외 계획 구현 지시.
- 원문: [INDEX](../../INDEX.md#workflow), [CHARTER](../../CHARTER.md).

## 범위·완료 기준

열람본 `export/docs/gen9ou_team_pool_role_db.json`에서 Zamazenta speed_control,
Heatran defensive_check를 제거하고 관련 세트3개의 roles 참조만 삭제한다.
세트 자체·공통 역할 사전·기능·나머지 데이터는 보존하고 같은 폴더의 설명서를 갱신한다.
기존 active plan과 중첩 없음. 원본 DB·runtime·연구 설계 변경 없음.

- [x] 포켓몬44종, 역할261→259, 빈 근거 역할0, 잘못된 세트 참조0 확인.
- [x] 허용 변경 외 전체 객체 동일, JSON 파싱·두 자리 표시 및 문서 링크 확인.

## 진행·중단

승인·등록. 비실험 열람본 편집으로 외부 호출·복구·재수집·시계·뷰어 해당 없음.
[INDEX 공통 기준](../../INDEX.md#workflow)을 따른다.

## 결과 및 증거

[열람본](../../../export/docs/gen9ou_team_pool_role_db.json)에서 두 역할과 세트3개의 참조를 제거하고
[설명서](../../../export/docs/gen9ou-team-pool-role-db-field-guide.md)를 갱신했다.
44종·역할259개·빈 근거 역할0·잘못된 참조0, 나머지 객체 전체 동일성을 확인했다.
세트 자체와 공통 사전·기능·통계 보존, JSON 재파싱·두 자리 표시·문서 링크를 검증했다.
운영 상태 변화 없어 STATUS 갱신 없음.
