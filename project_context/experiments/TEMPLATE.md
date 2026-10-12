# EX-XXX — 제목 (Title)

- 상태 (Status): Planned | Running | Completed | Stopped | Invalid
- 생성일 (Created): YYYY-MM-DD
- 책임자 (Owner): TBD
- 관련 exec plan (Related exec plan): TBD
- 관련 decision (Related decision): TBD

## 질문 및 목적 (Question and Purpose)

이 experiment가 답할 수 있는 질문과 그 답이 중요한 이유를 적는다.

## 가설 또는 qualification 목표 (Hypothesis or Qualification Target)

TBD. Exploratory work는 명시적으로 표시한다. Directional guess는 result가 아니다.

## 조건 및 변수 (Conditions and Variables)

이 record의 사전 protocol은 해당 실행 조건의 동결 원문이다. 적용하는 RD·계약 절과 승인 ADR을
연결하고, 공통 규칙을 반복하지 말고 이 실행의 조건·차이·예외를 기록한다. EP·색인에는 이 원문을
참조한다. 실행 후 원조건을 고쳐 과거 결과의 의미를 바꾸지 않는다.

| Condition | 통제 입력 (Controlled inputs) | 변경 입력 (Changed input) | 예상 artifact 위치 |
|---|---|---|---|
| TBD | TBD | TBD | TBD |

- Population/sample: TBD
- Denominator: TBD
- 중단 규칙 (Stopping rule): TBD
- Run-order/randomization policy: TBD

## 환경 및 출처 (Environment and Provenance)

- Code commit: TBD
- Data/store SHA 또는 clean-start 선언: TBD
- Game version: TBD
- Mod/protocol version: TBD
- Data schema version: TBD
- Model/provider 및 tier setting: TBD
- Configuration/feature flag: TBD
- 해당하는 경우 character/difficulty/seed: TBD
- 비교에 영향을 주는 machine/runtime fact: TBD

Credential, private endpoint 또는 개인 machine identifier를 이 record에 기록하지 않는다.

## 격리 및 오염 통제 (Isolation and Contamination Controls)

- Experiment tag: TBD
- Writable-store 위치: TBD
- Shared-state exception: TBD
- Resume behavior: TBD
- Prior-data inclusion rule: TBD

## 절차 (Procedure)

1. TBD

## 승인·무효화·중단 조건 (Acceptance, Invalidation, and Stop Conditions)

- Acceptance/qualification: TBD
- Invalid attempt: TBD
- Safety/cost/time stop: TBD

## 테스트·평가 도구 결함 복구

[공통 절차](../RESEARCH_DESIGN.md#defect-recovery)와 [C-018](../CONTRACTS.md#c-018-recovery)는
D-029 채택 후 새로 승인·등록하는 실험의 기본값이다. 기존 실험에는 소급 적용하지 않는다.

- 별도 전체 중단 규칙의 사유·범위: TBD (없으면 공통 절차).
- 재수집 허용 여부·한도(금지이면 0): TBD.
- 대응 조건 쌍/block·연쇄 메모리와 후속 결과를 보존하는 복구 단위: TBD.
- 같은 승인 안의 복구 범위·예산·시간·호출 상한, 최초 시계·누적 사용량 연결: TBD.
- 실행기 지원 경로·지원되지 않는 복구와 필요한 선행 검증: TBD.
- 결함 기록 위치: TBD. 발견 단계·시점/결과 확인 여부, 원자료 기반 재현, 영향받는 입력·조건·
  결과/공유 의존성, 수정 전후 source·기준/해시, 독립 검증·재현/회귀 검사, 재평가·재실행 범위를 남긴다.
- 원본 evidence·보고서 보존 및 수정 분석/새 실행의 별도 버전·identity 연결: TBD.

공통 절차의 비소급·원본 보존·분모·rubric·재시도·상한·halt 경계를 위 원문 참조로 적용한다.
기본 IO의 설명 검토는 [§8.1](../RESEARCH_DESIGN.md#io-explanation-review)에 따라 적용 여부와
명시 요청 근거를 기록한다. 미평가와 오류0을 구분한다.

## 증거 (Evidence)

| Artifact / 원본·정정 관계 | Path 또는 durable link | Checksum/query | 상태 (Status) |
|---|---|---|---|
| TBD | TBD | TBD | Not produced |

보고서 → manifest → 원자료·source/config·판정 근거의 경로를 연결한다. 집계 hash만 적지 말고
그 hash의 대상 manifest 위치를 기록한다. 중간 산출물은 최종 결과와 구분해 필요한 경우에만 읽도록
연결하되 실패/무효 및 정정 근거를 삭제하지 않는다.

## 결과 (Results)

실행하지 않음 (Not run). Evidence에 근거한 observation이 있을 때만 교체하며, uncertainty와
선언한 모든 denominator를 포함한다.

## 분석 및 한계 (Analysis and Limitations)

TBD. Measured observation, derived statistic, interpretation을 구분한다.

## 결론 및 후속 작업 (Conclusion and Follow-ups)

TBD. Hypothesis/qualification이 supported, unsupported, unresolved 중 무엇인지 명시한다.
Experiment result 자체는 higher-authority document를 변경하지 않는다.
