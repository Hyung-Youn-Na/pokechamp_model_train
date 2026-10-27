# EP-XXX — 제목

- 상태: Draft | Active | Blocked | Completed | Abandoned
- 생성일: YYYY-MM-DD
- 책임자: TBD
- 승인 근거·범위: 현재 명시적 사용자 지시 또는 유효한 plan/Decision 참조
- 관련 contract / decision / experiment: 해당 원문 링크
- 기준 연구선: `research/model-training` 또는 `research/l1-l5-port`
- 실제 작업 branch·시작 commit·미커밋 변경: TBD
- 작업 checkout·사용할 interpreter/launcher: TBD (문서/설계만이면 해당 없음)
- 새 산출물·검증 출력 위치: TBD
- 참조 원자료·보존본·manifest: TBD (새 쓰기 위치와 구분)

브랜치별 진입·환경·출력은 [연구 매뉴얼](../RESEARCH_MANUAL.md), 보존 시점은
[공통 안내](../RESEARCH_WORKFLOW.md#preservation)를 따른다. 기존 ID·기록은 재사용/재작성하지 않는다.

## 목표와 맥락

완료할 하나의 outcome과 근거를 적는다. Fact와 assumption을 구분하고 과거 경과는 링크한다.

## 범위와 불변 조건

- 포함 / 제외 범위, 허용 file/system: TBD
- 외부·유료·파괴적 행동의 승인 범위·한도: 해당하는 경우 원문 참조
- 보존할 Charter·계약·Accepted Decision 및 task-local invariant: 원문과 적용 범위

실험 조건·예산·gate·재시도·분모는 해당 EX의 동결 protocol을 명시 참조하고 전문을 복사하지
않는다. 새 protocol은 실행 전에 관련 domain authority와 승인에 연결해 등록한다.
기본 IO의 설명 검토 여부는 [연구 설계 §8.1](../RESEARCH_DESIGN.md#io-explanation-review)을
따르며 별도 요청이 있으면 근거·범위를 기록한다.

## 완료 기준

- [ ] 승인된 outcome에 대한 관찰 가능한 기준. 실험 기준은 원문 참조.
- [ ] 정상 종료 배틀 실험은 [C-047](../CONTRACTS.md#c-047-viewer-export)에 따라
  exports/battle_viewers에 뷰어·목록·출처를 제공하고 오프라인 열람을 검증한다. 비배틀 작업은 해당 없음.
- [ ] 적용 대상 신규 배틀은 EX의 UI 규격·생성기 판본·소스·확장 선언을 연결하고
  [매뉴얼](../RESEARCH_MANUAL.md#battle-viewer-workflow)에 따라 실행 전 지원을 확인한다.
  미지원 항목은 선행 구현 EP와 검증 근거를 연결한다.
- [ ] 실제 내보내기의 UI 확인표·개별 EX 필수 검증 결과 및
  [변경일지](../shared/viewers/CHANGELOG.md) 항목을 연결한다.
  문서 규격 확정과 생성기 지원/내보내기 완료를 구분한다. 비배틀 작업은 해당 없음.

## 검증

| 변경 영향 / 보존할 의미 | 검사 방법·범위 | 기준 evidence / 새 evidence | 결과·한계 |
|---|---|---|---|
| TBD | TBD | TBD | Not run |

관련 변경·실패·미해결 우려로 범위를 정하고 기존 검증을 참조할 때 적용 source/config와 차이를
기록한다. 재사용은 새 source 전체 검증이나 미실행 gate 통과를 뜻하지 않는다. 필수 검증을
완화하지 않으며 반복·범위 확대 판단은 [INDEX](../INDEX.md#workflow)를 따른다.
문서 정리는 diff·링크·상태/규칙/판정·증거 연결을 대조하고 runtime 검사는 관련 변경이 있을 때 판단한다.

## 진행

- YYYY-MM-DD — 승인·등록, 구현 전.

## 차단·중단

[INDEX 공통 기준](../INDEX.md#workflow)과 해당 domain/개별 작업의 명시 조건을 따른다.
미승인 행동은 준비된 결과·영향을 제시하고 필요한 결정만 확인한다.

- 비실험 작업: 복구·재수집·실험 시계는 해당 없음과 사유 한 줄.
- 새 실험: [공통 복구](../RESEARCH_DESIGN.md#defect-recovery)·[C-018](../CONTRACTS.md#c-018-recovery)의
  적용 및 예외 사유·범위, 재수집 허용/단위/한도, 승인·최초 시계·누적 상한,
  실행기 지원과 독립 검증·원본/정정 연결 기록은 해당 EX 절을 참조한다.
- 새 실험의 공급자 판단 오류: [RD §11.2](../RESEARCH_DESIGN.md#provider-judgment-errors)·
  [C-046](../CONTRACTS.md#c-046-provider-judgment)의 진단/경기 실패 격리 및 실행기 지원을 확인한다.
  포괄적인 첫 오류 전체 중단을 상속하지 않는다.
- Task별 추가 blocker: 해당할 때 기록.
- Blocked 기록의 현재 처리 필요·후속 해결·명시적 종료가 확인되면 catalog/blocked.json에
  관리 분류와 근거 ID를 등록한다. 불명확하면 확인 필요로 두며 원래 상태·판정을 변경하지 않는다.

## 결과 및 증거

종결 시 outcome·미충족 기준·검증/최종 보고서 링크를 기록한다. 중단 처리와 실험 목표 달성을
구분하고, 현재 그림이 바뀔 때만 색인·STATUS를 갱신한다. 상세 로그·검사 수치를 복제하지 않는다.

복사 위치는 주제의 `plans/`이며 이 template의 `../` 문서 링크는 `../../`로 조정한다.

## 등록·탐색 정보

원문을 승인된 기본 주제의 decisions/plans/experiments에 두고 catalog/records.json에 등록한다.
ID·path·topic·methods(학습/추론/평가)·models·datasets·relations를 기록하며
제목·상태·결과는 이 원문에서만 관리한다. 새 기록의 legacy_paths는 빈 배열이다.
상태 변경으로 파일을 이동하지 않는다. 생성 색인은 context-catalog build/check로 갱신한다.
