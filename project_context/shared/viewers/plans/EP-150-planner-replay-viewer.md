# EP-150 — GLM·JEV 탭·리플레이 통합 뷰어

- 상태: Completed
- 생성일: 2026-10-15
- 책임자: Codex
- 승인: 현재 사용자 제공 계획의 구현·검증 지시
- 관련: [D-144](../decisions/D-144-planner-replay-viewer.md), [C-070](../../../research/planner-executor/CONTRACTS.md#c-070-jev-planner), [C-047](../../../CONTRACTS.md#c-047-viewer-export)
- 연구선/실제 branch: `research/model-training`, 시작 commit `a4659bf`; checkout `/workspace`
- 기존 미커밋 구현·문서 다수 보존. 작업 대상은 `integration/jev_planner/` 및 관련 현재 문서다.
- interpreter: `/workspace/pokechamp/.venv/bin/python`, 브라우저 `/tmp/ep037/tools/bin/python`
- 검증 출력: `/tmp/ep150-*`, 보고 `project_context/exec-plans/evidence/ep150/`
- 읽기 전용 참조: EX-092 보고→봉인 manifest→결정 원자료. 기존 EX-088·092 출력은 변경하지 않는다.

## 목표·범위

향후 export의 경기 화면에서 GLM 계획 기본 탭과 JEV/상태/로그/피해/기술 탭을 리플레이와 함께 제공한다.
턴·결정 선택만 재생을 정지하고 턴 시작으로 이동하며, 탭·리플레이 조작은 정보 선택과 독립이다.
원문·피해 시나리오는 결정별 로컬 스크립트로 지연 적재한다. API/GPU/새 배틀·정책 변경0.
INDEX·CHARTER·매뉴얼·STATUS·plan 색인, 겹치는 보존 EP-062/064/075/077/080/134/140과
완료 EP-141/143/144의 경계를 확인한다. 기존 평가 재개·뷰어 재내보내기는 하지 않는다.
설명 정확성 평가는 RD8.1/C-032에 따라 미평가(기본 제외)다.

## 완료 기준

- [x] 7탭·반응형 동시 표시·원문 복사/다운로드·재사용 생성 결정 연결
- [x] actor 공개 로그/정확한 결정 cutoff·결정 없는 턴·iframe 최신 선택 및 양방향 독립성
- [x] observation 감사 해시·표시명/계획 추가 전 입력 identity와 저장 피해 연결·필터/상세
- [x] 최초/재사용/새계획/자동/실패/다중결정 CPU검사 및 EX-092 임시 export 원문 대조
- [x] 이동 후 file://·외부차단·키보드·모바일·연속선택 브라우저 검증·문서/상태 동기화

## 검증·진행

- 2026-10-15 — 승인 범위 등록. 기존 변경 보존, 구현 전.

## 중단·경계

INDEX 공통 절차 적용. 비실험 구현으로 복구·재수집·실험 시계는 해당 없음.
현재 실험·입력·모델·프롬프트·호출 정책을 변경하지 않는다.


## 결과·증거

새 export의 기본 통합 화면과 모든 완료 기준을 구현·검증했다. CPU202통과/5skip,
별도 Playwright2통과, EX-092 전체68결정/피해 원문 전수 일치와4대표 이동후 오프라인·공식
실제 animation pause/seek를 확인했다. 새 모델/배틀·피해 재계산0이며 기존 출력은 보존했다.
[완료 보고](../../../exec-plans/evidence/ep150/report.md) · [전수 검증](../../../exec-plans/evidence/ep150/verification.json).
