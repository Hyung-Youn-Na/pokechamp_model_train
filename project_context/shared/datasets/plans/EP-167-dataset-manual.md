# EP-167 — 보관 데이터셋 매뉴얼 안내

- 상태: Completed
- 생성일: 2026-10-19 (KST)
- 책임자: Codex
- 승인: 사용자의 두 데이터셋 정보·위치를 매뉴얼에 반영하라는 지시.
- 기준/실제 연구선: `research/model-training`, `/workspace`, 시작 commit `a4659bf298c7935714f9fbd25246db2d831c5926`; 기존 미커밋 변경 보존.
- 실행 환경: 문서 편집·정적 검사만 수행, 연구 실행기 해당 없음.
- 관련 원문: [INDEX](../../../INDEX.md#workflow), [연구 매뉴얼](../../../RESEARCH_MANUAL.md), [EP-165](EP-165-showdown-sft-archive.md), [EP-166](EP-166-pokechamp-dataset-archive.md).

## 범위·완료 기준

연구 매뉴얼 6절에 두 보관본의 위치·특징·schema·분할·revision·검증 범위·원문/manifest 연결을
추가하고 INDEX와 STATUS에서 안내한다. active plan 색인을 확인했으며 데이터셋 안내와
직접 겹치는 실행 작업은 없다. 기존 보관 데이터·manifest·완료 기록·연구 방법은 변경하지 않는다.

- [x] 매뉴얼의 안내와 보관 README·manifest·EP 수치/구조 대조.
- [x] 새 링크·앵커·문서 변경분 검사 및 완료 기록.

## 진행·중단

- 2026-10-19 — 사용자 승인 범위 등록. 문서 작업이므로 배틀/학습·EX·뷰어·실험 시계는 해당 없음.
- INDEX 공통 기준을 따르며 원문과의 충돌은 임의로 해소하지 않는다.

## 결과·검증

[매뉴얼 6.1절](../../../RESEARCH_MANUAL.md#archived-datasets)에 안내를 추가하고 INDEX·STATUS에서 연결했다.
보관 README·EP의 schema/설명 및 manifest의 revision·파일 수·용량·행 수를 대조했다.
추가한 로컬 링크·앵커 검사가 통과했다. 문서만 변경하여 runtime 검사는 해당 없다.
