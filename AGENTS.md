# 리포지토리 에이전트 라우팅

실질적인 작업 전 [project_context/INDEX.md](project_context/INDEX.md)와
[CHARTER.md](project_context/CHARTER.md)를 읽고,
[작업별 읽기 경로](project_context/INDEX.md#reading-paths)로 관련 계약·설계·결정 원문을 확인한다.

- 구현·실험 전 [exec-plan 색인](project_context/exec-plans/INDEX.md)과 범위가 겹치는 모든
  `active/` plan을 확인한다. 실행 중/중단 보존 표시는 읽기·승인 요건을 면제하지 않는다.
- 승인·질문·중단·완료는 [INDEX 공통 기준](project_context/INDEX.md#workflow)을 따른다.
  active 밖의 TODO·roadmap·plan은 legacy evidence이며 현재 작업으로 상속하지 않는다.
- 연구 방법·hypothesis·평가 기준·treatment·해석 규칙 변경 전
  [RESEARCH_DESIGN.md](project_context/RESEARCH_DESIGN.md)를 읽는다.
- 문서의 원문 소유·갱신 범위·한국어 규범은 INDEX를 따른다. 현재 상태가 바뀌면 관련
  개별 plan·색인·STATUS를 필요한 범위에서 갱신한다. 이 라우터에 이력·정책값을 복제하지 않는다.

하위 디렉터리의 구체적 지시도 적용한다. Python agent subtree는
[AgenticSTS/AGENTS.md](AgenticSTS/AGENTS.md)의 coding·testing·safety 및 `Agent Usage`를 따르되,
날짜별 status·roadmap은 현재 계획으로 상속하지 않는다. Architecture·project history는
`project_context/`에서 관리한다.

## Astra의 서브에이전트 활용

- 주 에이전트가 Astra(`gpt-6-astra`)로 실행 중이고 작업량이 많으면, 독립적인 조사·분리 가능한
  구현·검토를 서브에이전트(`subagent`)에 위임해 병렬로 진행한다. 예상 시간 절감이나 검증 품질
  향상이 생성·조율 비용보다 클 때 활용한다.
- 작은 단일 수정이나 선행 결과에 강하게 의존하는 작업은 직접 처리한다. 위임 도구가 없으면
  가능한 작업을 직접 이어간다.
- 위임할 때 목표, 담당 범위·파일, 관련 AGENTS·plan·계약, 기대 산출물·검증 기준을 명시한다.
  같은 파일의 동시 수정을 피하고 공유 파일 수정과 통합은 주 에이전트가 조율한다.
- 필요한 수의 서브에이전트만 생성하고 환경의 동시 실행 한도를 따른다. 별도 지시가 없으면
  현재 모델과 추론 설정을 상속한다.
- 주 에이전트는 중복 작업을 피하며 독립 작업을 계속하고, 반환 결과·변경분을 검토하여
  통합·필수 검증·완료 보고까지 책임진다.
- 이 지침은 위 조건에서 위임을 활용하는 근거다. 사용자·상위 지시·개별 plan의 명시적 위임
  제한을 우선하며, 승인·중단·완료 판단은 위 INDEX 공통 기준을 따른다.
