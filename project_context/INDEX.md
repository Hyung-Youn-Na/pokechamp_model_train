# 프로젝트 컨텍스트 색인 (Project Context Index)

이 디렉터리는 연구자와 coding agent가 함께 사용하는 영속적 engineering control plane이다.
권위 있는 맥락으로 작업을 안내하며, 세부 subsystem 문서나 raw experiment artifact를 대체하지
않는다.

## 문서 언어 정책 (Language Policy)

한국어가 규범 언어이며 영어는 보조 언어다. 목표·결정·계약·상태·계획·해석은 한국어로 작성하고
동일 본문을 영문으로 복제하지 않는다. 충돌 시 한국어가 우선하되 코드/API·파일명·명령·
machine-readable 값·원문 인용은 원형을 유지한다. `Active`, `Accepted`, `TBD` 등 표준 상태값은
검색 가능하도록 영문을 유지하거나 병기한다.

## 탐색 안내 (Navigation)

| 필요한 정보 | 원문 |
|---|---|
| 장기 목적·범위·상위 invariant | [CHARTER](CHARTER.md) |
| 현재 연구선의 질문·범위·미정 설계 | [연구 목표](RESEARCH_DESIGN.md#branch-research-objective) |
| 학습 연구선의 방향·기존 단계 | [학습 설계](RESEARCH_DESIGN.md#pokemon-training-objective) · [기존 단계](RESEARCH_DESIGN.md#pokemon-imitation-self-play) |
| 연구 질문·처치·평가·해석과 규칙 적용 범위 | [RESEARCH_DESIGN](RESEARCH_DESIGN.md#current-rules) |
| schema·runtime·검증·provenance 계약과 버전별 범위 | [CONTRACTS](CONTRACTS.md#current-rules) |
| 결정 목록 / 승인·대체 근거 | [DECISIONS](DECISIONS.md) / 해당 개별 ADR |
| 현재 구성·data/control flow | [ARCHITECTURE](ARCHITECTURE.md) |
| 현재 연구선의 작업 시작·환경·등록 순서 | [연구 매뉴얼](RESEARCH_MANUAL.md) |
| 보관 데이터셋의 특징·구조·위치 | [데이터셋 안내](RESEARCH_MANUAL.md#archived-datasets) |
| 보관 Strategist 모델의 구조·위치 | [모델 안내](RESEARCH_MANUAL.md#archived-strategist-model) |
| 연구선·외부 보존본·새 출력·복원 | [작업 안내](RESEARCH_WORKFLOW.md) · [보존 manifest 연결](preservation/pre-split.json) |
| 현재 목표·작업·기능 제한 | [STATUS](STATUS.md) |
| 실행 중·중단 보존·완료 작업 | [exec-plan 색인](exec-plans/INDEX.md) |
| 실행별 조건·결과·유효성·분모 | [실험 색인](experiments/INDEX.md) → 해당 EX |
| 원자료·최종 검증·정정 분석의 연결 | [증거 탐색](exec-plans/evidence/INDEX.md) 및 각 EP/EX의 최종 보고서 |
| 실제 입력·요약 시점 / prompt 원문 | [입력·요약 구조](../docs/pokechamp-input-summary.md) / [원문 부록](../docs/pokechamp-prompt-originals.md) |
| B 필드 설명·버전 / 전달 표현·정보 보존 | [필드 설명서](../docs/pokechamp-battle-field-guide.md) / [B 표현](../docs/pokechamp-b-prompt-optimization.md) |

<a id="reading-paths"></a>

## 작업별 읽기 경로

공통으로 이 INDEX와 CHARTER를 확인한다. 다음 표는 관련 문서를 찾는 경로이며 권한·승인·
중단 요건을 면제하지 않는다. 목차·scope·적용 버전으로 범위를 좁힌 뒤 관련 본문을 읽는다.
구현·실험 전 plan 등록과 겹치는 모든 active plan 확인은 [아래 절](#active-work)을 따른다.

| 작업 | 이어서 확인할 범위 |
|---|---|
| 분리된 환경에서 작업 시작 | 현재 checkout의 [연구 매뉴얼](RESEARCH_MANUAL.md) → STATUS와 관련 plan. 보존/복원은 [공통 안내](RESEARCH_WORKFLOW.md) |
| 문서·링크·색인 정리 | STATUS, 대상 문서의 authority·참조 원문, 관련 plan. 조건/판정 문구를 줄이면 해당 RD/C/EX 근거까지 대조 |
| 구현·버그 수정 | STATUS → plan 색인과 겹치는 plan → 해당 ARCHITECTURE·CONTRACTS 절 및 ADR |
| 기본 IO 테스트·viewer | 위 구현 경로와 [설명 검토 적용 규칙](RESEARCH_DESIGN.md#io-explanation-review), [실행기 경계](CONTRACTS.md#c-032-io-explanation-review) |
| 실험 준비·실행 | 해당 연구 설계·계약·승인 ADR·plan·EX의 동결 protocol, [복구](RESEARCH_DESIGN.md#defect-recovery)와 [운영 지원 범위](../integration/pokechamp/README.md#defect-recovery) |
| 연구 방법·평가·해석 변경 | RESEARCH_DESIGN의 해당 공통 규칙과 실험별 원문, 관련 CONTRACTS 및 ADR. 기존 승인·중단 조건 확인 |
| 과거 결과 감사 | 해당 EX → 최종 보고서·manifest → 원자료/정정 분석. 과거 실행을 재개하지 않음 |

상속 구현의 사실 조사에만 [agent README](../AgenticSTS/README.md)와
[reference documentation](../AgenticSTS/docs/reference/)를 사용한다. 날짜별 TODO·roadmap은
현재 작업으로 상속하지 않는다. 대형 로그·JSON·replay는 보고서·manifest로 대상을 좁힌 뒤 읽는다.

## 문서 구조와 누적 정책

- CHARTER·RESEARCH_DESIGN·CONTRACTS·ARCHITECTURE·STATUS는 각 domain의 현재 원문이다.
  현재 값을 갱신하고 obsolete state를 덧붙이지 않는다. 변경 근거는 Git history와 ADR로 추적한다.
- ADR·EP·EX는 `색인 + 개별 기록`으로 관리한다. 색인은 ID·상태·날짜·짧은 설명·링크만 담고
  상세 조건·검증 수치·경과를 복제하지 않는다. 새 항목은 표 안에 추가한다.
- STATUS는 목표·현재 작업·현재 제한·다음 단계·검증 참조만 유지한다. 완료 일지는 개별 EP로
  연결하고 상세 실행 결과·분모·무효/정정은 EX와 최종 보고서에 둔다.
- 규칙의 편집 원문과 적용 범위를 명시하고 안내표·plan에는 참조를 사용한다. 공통 방법은 RD,
  runtime 계약은 CONTRACTS, 승인 근거는 ADR, 작업 진행은 EP, 실행 조건·결과는 EX가 담당한다.
  실험별 원문 참조는 현재 domain authority 안에서 명시하며 authority를 조용히 이전하지 않는다.
- 기존 동결 protocol·원자료·당시 판정은 정리 목적으로 수정·삭제·이동하지 않는다. 정정은
  별도 근거를 연결한다. 새 기록부터 조건 전문을 여러 문서에 복사하지 않는다.
- 진행·검증은 해당 EP에서 갱신한다. 색인은 status/경로/요약이 바뀔 때, STATUS는 현재
  operational picture가 바뀔 때만 동기화한다. 숫자 갱신을 위해 여러 요약을 함께 고치지 않는다.

## Authority model

[`CHARTER.md`](CHARTER.md)는 project goal과 fundamental invariant에 대해 최상위 authority다.
그 아래 current-state authority는 하나의 total ordering이 아니라 다음과 같이 domain별로
나뉜다.

| 문서 | Authority domain |
|---|---|
| [`RESEARCH_DESIGN.md`](RESEARCH_DESIGN.md) | Research question, hypothesis, treatment와 comparison methodology, evaluation protocol, interpretation rule |
| [`CONTRACTS.md`](CONTRACTS.md) | Schema, runtime semantics, validation boundary, authority/provenance contract |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 현재 system composition과 data/control flow의 사실적 설명 |
| [`STATUS.md`](STATUS.md) | 현재 objective, 진행 상태, blocker와 verification summary |

`Accepted` 개별 ADR은 current-state 문서가 현재 형태가 된 rationale와 provenance를 제공하지만
그 문서를 자동으로 대체하지 않는다. Active exec plan은 승인된 current-state 문서의 범위 안에서
작업을 한정하고, implementation은 실제 동작의 evidence이지만 research design이나 contract를
조용히 재정의하지 않는다. Experiment record는 개별 run의 configuration, result와 evidence를
보존하며 current methodology 자체를 변경하지 않는다. Registry와 index는 navigation용이다.

하위 작업을 통과시키기 위해 적용되는 상위 또는 domain-authoritative 문서를 임의로 수정해서는
안 된다. 서로 다른 authoritative 문서, implementation 또는 evidence 사이에 conflict가 있으면
한쪽을 조용히 맞추지 말고 기록하고 보고한다. 새로운 evidence로 current-state 변경이 필요하면
관련 ADR에 근거를 남기고 해당 문서를 명시적으로 변경한다.

<a id="workflow"></a>

## 승인·확인 질문·중단·완료

이 절은 agent 작업 절차의 공통 기준이다. Root/subtree AGENTS와 exec-plan template는 이
기준을 참조한다. Charter, domain authority 및 개별 작업의 명시적인 승인·중단 요건을
면제하지 않으며 기존 exec plan 등록 요건을 유지한다. 근거는
[`D-025`](decisions/D-025-agent-instruction-boundaries.md)에 기록한다.

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

이 control plane보다 먼저 존재한 모든 TODO, roadmap, future-work 목록, 미완료 checklist,
날짜가 있는 plan, handoff note, experiment resume plan은 현재 planning에서 제외한다. 여기에는
`AgenticSTS/docs/`, `AgenticSTS/CLAUDE.md`, `AgenticSTS/AGENTS.md`, root README의 Future Work가
포함된다.

이 파일들은 provenance를 위해 보존한다. 상속받은 시스템을 사실적으로 조사할 때 evidence로
사용할 수 있지만, 현재 작업이나 후보 작업은 아니다. 새로운 명시적 사용자 지시 없이
`active/`로 옮기거나 이어서 수행해서는 안 된다. `exec-plans/active/`에 명시적으로 승인된
plan만 현재 실행 작업을 나타낸다.

기존 README, archived decision, 완료된 experiment report도 보조 evidence다. 사실 설명이
충돌하면 구현 편의나 파일 날짜만으로 승자를 정하지 말고, 새로 승인된 작업에 영향을 줄 때
충돌을 드러낸다.

<a id="active-work"></a>

## Active work 찾기

Active plan은 [`exec-plans/INDEX.md`](exec-plans/INDEX.md)의 Active plan 목록(실행 중/중단 보존)에 등록되고
[`exec-plans/active/`](exec-plans/active/)에 본문이 있는 `EP-XXX-short-title.md` 파일이다.
`.gitkeep`은 무시한다. [`STATUS.md`](STATUS.md)의 요약을 확인한 뒤 제안 작업과 scope가 겹치는
모든 active plan을 읽는다. `Blocked`는 실행 가능 여부와 구분해 표시하지만 이 확인 대상에서
자동 제외하거나 재개하지 않는다. 일치하는 plan이 없다면 Charter의 bounded active exec plan 요건에
따라 구현·실험을 시작하기 전에 [`exec-plans/TEMPLATE.md`](exec-plans/TEMPLATE.md)로 새 plan을
만들고 index에 등록한다. Plan의 분량은 작업 규모에 맞추되 짧은 구현이라는 이유로 등록을
면제하지 않는다. 현재 대화에서 이미 승인된 같은 목표를 plan 등록 때문에 다시 승인받지는 않는다.

`active/`가 비어 있다는 것은 이 control plane에 등록된 active execution unit이 없다는
뜻이다. 다른 곳에 비공식 작업이 전혀 없다는 증거는 아니다.
