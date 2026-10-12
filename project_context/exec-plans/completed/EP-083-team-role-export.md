# EP-083 — 팀 풀 44종 역할 DB 내보내기

- 상태: Completed
- 생성일: 2026-09-22
- 승인 근거·범위: 사용자의 44종 JSON 저장 계획 구현 지시.
- 관련 원문: [INDEX](../../INDEX.md#workflow), [CHARTER](../../CHARTER.md).

## 목표와 범위

13개 gen9ou 팀 파일의 44종·폼을 원본 role DB와 ID로 대조하여
`export/docs/gen9ou_team_pool_role_db.json`에 전체 항목과 분류 사전·출처를 저장한다.
원본 metadata는 전체 DB 통계로 구분하고 추출 범위·출처 해시를 별도로 기록한다.
원본 DB·팀·runtime·기존 실험은 변경하지 않는다. 색인의 active plan 중 이 내보내기와
범위가 겹치는 작업은 없다. 비실험 문서/데이터 작업으로 복구·재수집·시계·뷰어는 해당 없다.

## 완료 기준과 검증

- [x] UTF-8 들여쓰기 JSON 저장 및 재파싱 성공.
- [x] 13팀·78슬롯·44종, 누락/중복0 및 추출 항목 원본 일치.
- [x] 사전·출처·원본 metadata 보존, 원본 파일 해시 불변 확인.

## 진행

- 2026-09-22 — 사용자 승인에 따라 등록·추출·검증 완료.

## 차단·중단

[INDEX 공통 기준](../../INDEX.md#workflow)을 따른다. 외부 호출·비용 없음.

## 결과 및 증거

[추출 JSON](../../../export/docs/gen9ou_team_pool_role_db.json) 저장 완료(3,594,618 bytes).
Python 표준 라이브러리로 저장 후 재파싱하고 13팀·78슬롯·44종, 누락/중복0,
모든 추출 항목과 사전·출처의 원본 동일성, 원본 DB·팀 파일 해시 불변을 확인했다.
원본 291종 통계는 `source_metadata`, 추출 범위와 팀별 ID·해시는 `export_metadata`에 구분했다.
연구 방법·운영 상태는 변경되지 않아 STATUS 갱신은 필요 없다.
