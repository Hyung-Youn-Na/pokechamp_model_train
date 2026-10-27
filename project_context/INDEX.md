# 프로젝트 컨텍스트 색인

현재 연구선은 `research/model-training`이다. 연구 목적별 원문과 공통 규범을 함께 읽는다.
한국어가 규범 언어이며 코드/API·식별자·원문 인용과 표준 상태값은 원형을 유지한다.

## 탐색

| 필요한 정보 | 시작점 |
|---|---|
| 목표·기본 원칙 | [CHARTER](CHARTER.md) |
| 현재 작업·제약·다음 단계 | [STATUS](STATUS.md) |
| 연구 질문별 흐름·원문 | [연구 목록](research/INDEX.md) |
| 공통 데이터·환경·뷰어·문서 운영 | [공통 기반](shared/INDEX.md) |
| 공통 연구·평가·해석 | [RESEARCH_DESIGN](RESEARCH_DESIGN.md) |
| 공통 runtime·출처·검증 | [CONTRACTS](CONTRACTS.md) |
| 전체 구성과 주제별 연결 | [ARCHITECTURE](ARCHITECTURE.md) |
| 시작·등록·완료 순서 | [연구 매뉴얼](RESEARCH_MANUAL.md) |
| 연구선·외부 자산·복원 | [작업 안내](RESEARCH_WORKFLOW.md) |
| D·EP·EX 전체·상태·방법·모델 | [탐색 등록부](catalog/INDEX.md) |
| 실행 중·중단 보존 계획 | [계획 색인](catalog/plans.md) |
| Blocked의 처리 필요·후속 종결 근거 | [Blocked 분류](catalog/blocked.md) |
| 최종 보고서·manifest·정정 근거 | 해당 EX/EP → [증거 안내](exec-plans/evidence/INDEX.md) |

<a id="reading-paths"></a>

## 작업별 읽기 경로

공통으로 INDEX와 CHARTER를 읽는다. 목차·적용 버전으로 범위를 좁힌 뒤 관련 원문을 확인한다.

| 작업 | 이어서 읽을 원문 |
|---|---|
| 작업 시작 | RESEARCH_MANUAL → STATUS → 계획 색인과 겹치는 계획 |
| 문서·링크·색인 정리 | 대상 주제 INDEX와 원문 권한, 관련 계획. 조건·판정은 RD/C/EX까지 대조 |
| 구현·버그 수정 | 주제 ARCHITECTURE/CONTRACTS, 공통 CONTRACTS, 관련 D·EP |
| 실험 준비·실행 | 공통·주제 DESIGN/CONTRACTS, 승인 D·EP 및 EX 동결 protocol |
| 방법·평가·해석 변경 | 공통 RESEARCH_DESIGN과 주제 DESIGN, 적용 EX·ADR |
| 과거 결과 감사 | EX → 최종 보고서 → manifest → 필요한 원자료/정정 분석 |

기본 IO 설명 검토는 RD §8.1, 도구 결함 복구는 RD §11.1/C-018,
공급자 판단 오류는 RD §11.2/C-046, 배틀 viewer 완료 요건은 C-047을 따른다.
상속 구현 사실 조사에는 AgenticSTS README/reference를 사용하되 날짜별 TODO를 현재 작업으로 삼지 않는다.

## 원문·누적 정책

- D-170에 따라 D·EP·EX 원문을 연구 목적의 decisions/plans/experiments에 둔다.
  기록 ID와 파일명은 유지하고 하나의 원문만 등록한다. 상태 변경으로 파일을 이동하지 않는다.
- 여러 목적·방법에 속하면 기본 소속 하나를 정하고 색인·관계로 연결한다.
  전용 실험 작업은 해당 목적에, 범용 데이터·환경·뷰어·운영은 shared에 둔다.
- 현재 규범은 공통 문서와 명시된 주제 문서의 현재 값을 갱신한다.
  과거 범위의 조건·Current 표시는 적용 당시 범위를 함께 읽으며 현재 실행 지시로 승계하지 않는다.
- STATUS는 현재 목표·작업·제약·다음 단계만 유지한다. 완료 일지는 원문과 생성 색인에서 찾는다.
- 등록부는 위치·분류·관계만 소유한다. 제목·상태는 원문에서 읽어 색인을 생성한다.
  조건·결과·분모를 색인에 중복 관리하지 않는다.
- D-171에 따라 Blocked의 관리 분류는 catalog/blocked.json에 별도 기록한다.
  후속 해결·진행 종료를 원래 실험의 Completed 전환이나 재개 승인으로 해석하지 않는다.
  미분류는 확인 필요로 표시하며, scope가 겹치는 원문 확인 의무는 유지한다.
- 승인된 문서 재배치와 링크 교정은 허용한다. 기존 실행 패키지의 동결 protocol 사본·source·
  보고서·원자료·봉인은 변경하지 않는다. 연구 조건·결과·판정 변경은 별도 근거와 승인을 따른다.
- 이전 경로의 `context-redirect` 파일은 탐색용이다. 원문 조회·동결은 등록 ID를 사용한다.
- 새 기록 또는 상태·분류 변경 후 `scripts/context-catalog build`와 `check`를 실행한다.
  숫자만 갱신하기 위해 여러 요약을 편집하지 않는다.

## Authority model

CHARTER는 목표와 기본 invariant의 최상위 원문이다. 그 아래 domain authority는 다음과 같다.

| Domain | 공통 편집 원문 | 주제별 편집 원문 |
|---|---|---|
| 연구 질문·처치·평가·해석 | RESEARCH_DESIGN.md | research/shared 각 주제의 DESIGN.md |
| schema·runtime·검증·provenance | CONTRACTS.md | 각 주제 CONTRACTS.md |
| 구성·data/control flow | ARCHITECTURE.md | 각 주제 ARCHITECTURE.md |
| 현재 운영 상태 | STATUS.md | 진행·검증 원문은 개별 EP, 실행 결과는 EX |

주제 원문은 명시된 subsystem·실험·버전 범위에서만 authoritative하다.
공통 규칙을 조용히 덮어쓰지 않으며 예외는 승인 근거와 적용 범위를 명시한다.
주제 INDEX·RECORDS·catalog는 탐색/근거 연결이며 새로운 authority가 아니다.
Accepted ADR은 근거를 제공하지만 current-state 원문을 자동 대체하지 않는다.
구현·EX·계획은 상위 목적이나 공통 방법을 조용히 변경하지 않는다.
규범 충돌은 한쪽을 맞춰 숨기지 않고 기록·보고한다.

<a id="workflow"></a>

## 승인·확인 질문·중단·완료

이 절은 agent 작업 절차의 공통 기준이다. Root/subtree AGENTS와 exec-plan template는 이
기준을 참조한다. Charter, domain authority 및 개별 작업의 명시적인 승인·중단 요건을
면제하지 않으며 기존 exec plan 등록 요건을 유지한다. 근거는
[`D-025`](shared/governance/decisions/D-025-agent-instruction-boundaries.md)에 기록한다.

1. **승인 근거를 재사용한다.** 현재 대화의 명시적 사용자 지시와 유효한 plan·Decision을
   함께 확인한다. 대상·범위·예산·조건이 같고 승인이 철회·만료되지 않았으며 별도 재승인
   요건이 없으면 같은 행동을 다시 승인받지 않는다. 후속 지시가 아직 plan에 없다는 이유만으로
   다시 묻지 말고 필요한 기록을 갱신한다. Authority 변경이 필요하면 해당 명시적 변경과
   Decision 기록을 먼저 반영한다. 포괄적인 완료 요청은 추가 비용·권한·실험 재개의 승인이 아니다.
2. **현재 작업에 필요한 정보만 질문한다.** 요청과 접근 가능한 자료를 먼저 확인하고 이미
   제공된 내용은 다시 묻지 않는다. 승인된 범위의 일상적인 구현 선택은 판단하여 진행한다.
   누락 정보가 결과의 정확성·범위·쓰기 대상·비용·권한에 실질적인 차이를 만들고 근거 또는
   합리적인 가정으로 해결할 수 없을 때만 질문한다. 가정으로 승인이나 연구 사실을 만들지 않는다.
3. **중단 범위를 밝힌다.** 충돌은 임의로 해결하지 않고 기록·보고한다. 그 해결이나 누락된
   의존성을 전제로 하는 작업은 중단하고, 영향을 받지 않으며 이미 승인된 작업은 계속한다.
   개별 contract·실험 규칙이 전체 중단을 명시하면 그 전체 범위를 그대로 중단한다. 중단 후
   필요한 증거 보존·자원 정리·무효/미완료 보고도 해당 규칙 안에서 수행하며, 이를 재개 허가로
   해석하지 않는다.
   D-029 채택 후 새로 승인·등록하는 실험의 도구 결함에는
   [공통 복구 절차](RESEARCH_DESIGN.md#defect-recovery)를 기본으로 적용한다. 등록 시 전체 중단
   예외의 사유·범위, 재수집 허용 여부·단위·한도, 최초 시계·누적 상한 및 실행기 지원 여부를
   확인한다. 같은 승인·상한 안의 허용 복구는 재승인하지 않는다. 기존 실험의 전체 중단·무효·
   `Blocked`는 보존하며 provider 재시도를 확대하지 않는다.
   새 실험의 공급자 판단 오류는 [RD §11.2](RESEARCH_DESIGN.md#provider-judgment-errors)에 따라
   전체 중단에서 제외한다. 합법 선택은 진단을 기록하고 계속하며, 실행 불가능한 응답은
   해당 경기로 격리한다. 실행기 지원을 확인하고 기술적 오류와 구분한다.
4. **추가 승인은 구체적인 결과를 대상으로 받는다.** 이미 승인된 조사·초안·검증 등 가능한
   준비를 완료하고 변경 내용, 대상, 비용·영향을 제시한 뒤 미승인 행동만 승인받는다. 질문·승인이
   필요하면 적용한 파일·조항과 필요한 결정을 밝힌다. 실제 권한 제한을 우회하지 않는다.
5. **요청한 결과까지 수행한다.** 구현 요청은 계획 작성에서 끝내지 않고 승인된 구현·필수
   검증·상태 갱신까지 수행한다. 필수 검사가 통과한 뒤 새 변경·실패·미해결 우려가 없으면 같은
   검사를 반복하거나 범위를 계속 넓히지 않는다. 정상 종료 배틀 실험은
   [C-047](CONTRACTS.md#c-047-viewer-export)의 뷰어 내보내기·링크 제공을 완료 절차에 포함한다.
   충족하지 못한 완료 기준과 차단 사유는 사실대로
   보고한다. 중단 처리의 완료는 실험 목표 달성이나 미완료 plan의 `Completed` 전환을 뜻하지 않는다.

## Legacy planning 제외 규칙

D-002 이전 및 이 control plane 밖의 TODO·roadmap·날짜별 계획은 legacy evidence다.
현재 명시적 승인과 등록 없이 실행하거나 미완료 연구를 재개하지 않는다.
과거 Completed는 효능 개선을, Blocked/Paused의 보고 종결은 연구 완료를 뜻하지 않는다.

<a id="active-work"></a>

## 실행 작업 찾기와 등록

[계획 색인](catalog/plans.md)의 진행·중단 보존을 확인하고 scope가 겹치는 모든 원문을 읽는다.
Blocked/Paused도 확인 대상이며 자동 재개하지 않는다.
실행 권한은 폴더명이 아니라 등록된 EP의 상태·현재 승인·범위와 관련 규범으로 판단한다.
구현·실험 전 새 [계획](templates/plan.md)을 주제 plans/에 만들고 catalog/records.json에 등록한다.
새 ID는 유형별 최댓값 다음 번호를 사용하며 재사용하지 않는다. 등록 때문에 같은 승인을 다시 묻지 않는다.
실험은 [실험 템플릿](templates/experiment.md), 지속 규범 변경은 [결정 템플릿](templates/decision.md)을 쓴다.
세부 등록·색인 명령과 호환 경계는 [catalog 안내](catalog/INDEX.md)를 따른다.
