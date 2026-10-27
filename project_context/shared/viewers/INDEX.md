# 공통 관측·뷰어

## 연구 질문·역할

기록된 판단·행동·리플레이와 감사 근거를 어떻게 열람하는가?

공통 규칙과 본 주제의 적용 범위를 함께 읽는다. 같은 폴더에 속한다는 사실만으로 실험의 직접 비교 가능성이나 효능 개선을 주장하지 않는다.

## 읽기 경로

[CONTRACTS.md](CONTRACTS.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

[공통 UI 규격](CONTRACTS.md#battle-viewer-ui-v1) ·
[실험 매뉴얼의 등록·확인 절차](../../RESEARCH_MANUAL.md#battle-viewer-workflow) ·
[생성기 지원 차이](ARCHITECTURE.md#viewer-ui-support) · [UI 변경일지](CHANGELOG.md)

[개별 기록과 원문 상태](RECORDS.md) · [전체 계획 상태](../../catalog/plans.md) · [방법별 탐색](../../catalog/by-method.md) · [기록 관계](../../catalog/relations.md)

## 연구 흐름과 해석 경계

### 관측과 연구자 열람

[EP-002](plans/EP-002-pokechamp-battle-observability.md) → [EP-037](plans/EP-037-viewer-turn-tabs.md) → [EP-067](plans/EP-067-viewer-export-location.md) → [EP-068](plans/EP-068-jev-replay-viewer.md) → [EP-069](plans/EP-069-researcher-viewer.md)

수집 원문·리플레이·판단 표시를 연결하며 viewer 판본과 실험 결과를 구분한다.

### 최근 표시 개선

[EP-142](plans/EP-142-jev-damage-viewer.md) → [EP-150](plans/EP-150-planner-replay-viewer.md) → [EP-177](plans/EP-177-ex108-viewer-layout.md)

재내보내기·표시 교정은 과거 원자료나 수집 당시 봉인을 덮어쓰지 않는다.

### 공통 규격과 변경 기록

[D-172](decisions/D-172-battle-viewer-ui-standard.md) →
[EP-187](plans/EP-187-battle-viewer-ui-standard.md)는 신규 실험의 UI 규격과 운영 절차를 고정한다.
문서 확정과 생성기 구현·검증 완료를 구분한다. 과거 실험을 자동 재내보내지 않는다.

## 갱신

새 D·EP·EX는 이 폴더의 decisions/plans/experiments에 등록한다. 상태 변경으로 경로를 옮기지 않는다. 원문을 갱신한 뒤 등록부와 생성 색인을 갱신한다.
