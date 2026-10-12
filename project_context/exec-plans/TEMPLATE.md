# EP-XXX — 제목

- 상태: Draft | Active | Blocked | Completed | Abandoned
- 생성일: YYYY-MM-DD
- 책임자: TBD
- 승인 근거·범위: 현재 명시적 사용자 지시 또는 유효한 plan/Decision 참조
- 관련 contract / decision / experiment: 해당 원문 링크

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

## 결과 및 증거

종결 시 outcome·미충족 기준·검증/최종 보고서 링크를 기록한다. 중단 처리와 실험 목표 달성을
구분하고, 현재 그림이 바뀔 때만 색인·STATUS를 갱신한다. 상세 로그·검사 수치를 복제하지 않는다.

복사 위치는 `active/`이며 이 template의 `../` 문서 링크는 `../../`로 조정한다.
