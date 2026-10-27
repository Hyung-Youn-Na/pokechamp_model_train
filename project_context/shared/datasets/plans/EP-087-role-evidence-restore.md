# EP-087 — 노력치 외 판단 조건 복원

- 상태: Completed
- 생성일: 2026-09-22
- 승인: 사용자의 노력치 외 조건 복원 계획 구현 지시.
- 원문: [INDEX](../../../INDEX.md#workflow), [CHARTER](../../../CHARTER.md).

## 범위·불변 조건

`export/docs/gen9ou_team_pool_role_db.json`의 역할/세트 evidence를 원본에서 다시 추출한다.
노력치와 관련 스피드 프로필만 제외하며 all_of의 남은 조건이 하나면 단일 조건으로 만든다.
출처·notes·status 및 노력치 관련 설명은 계속 제외한다. 원본의 전체 조건과 같다는 뜻이 아닌
열람용 생략임을 같은 폴더의 필드 설명서에 명시한다. 원본 DB·runtime·연구 설계 변경 없음.
기존 active plan 중 범위 중첩 없음.

## 완료 기준·검증

- [x] 원본과 ID 대응, 44종·역할/세트 목록·evidence 외 데이터 보존.
- [x] 빈 근거 역할31→2, 세트16→1 및 Great Tusk choicescarf 복원.
- [x] 금지 필드/노력치 부재, JSON 파싱·비율 표시·문서 일치 검증.

## 진행·중단

승인·등록. 비실험 열람본 편집으로 외부 호출·복구·재수집·시계·뷰어 해당 없음.
[INDEX 공통 기준](../../../INDEX.md#workflow)을 따른다.

## 결과 및 증거

[열람본](../../../../export/docs/gen9ou_team_pool_role_db.json)과 [설명서](../../../../export/docs/gen9ou-team-pool-role-db-field-guide.md) 수정 완료.
역할 근거45개·세트 근거15개 신호 복원. 빈 근거 역할31→2·세트16→1 확인.
Great Tusk의 revenge_killer에 choicescarf 단일 조건 복원 확인.
evidence만 바뀌었음을 전체 객체 대조로 검증했으며 원본 DB bytes 불변, JSON 재파싱,
금지 필드/노력치 부재, all_of 최소2조건, 두 자리 비율 표시·문서 링크를 확인했다.
설명서의 반대 근거 현황을1개로 정정하고 남은 조건이 원본 전체 조건과 같지 않음을 명시했다.
운영 상태 변경 없어 STATUS 갱신 없음.
