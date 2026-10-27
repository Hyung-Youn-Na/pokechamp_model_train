# 문서·연구선 운영 — 연구 설계

이 문서는 **개편 전 중앙 문서의 서문·연구선 안내를 당시 범위로 보존**한다.
아래 본문의 “이 문서”, “현재”, “원문 소유권”은 이전 시점의 문서를 가리킨다.
현재 권한 배치·작업 절차는 [루트 INDEX](../../INDEX.md), 현재 목표는 [CHARTER](../../CHARTER.md),
진행 상태는 [STATUS](../../STATUS.md)가 소유한다. 이전 실험의 규범 참조·해석 범위는 보존한다.


D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.

<a id="현재-연구-설계-research-design"></a>
# 현재 연구 설계 (Research Design)

D-149의 사용자 재승인으로 [EX-096](../../research/planner-executor/experiments/EX-096-nvfp4-battle-probability-diagnostics.md)은
반복 확률 차이를 진단으로 유지하며 새1경기에 진입한다. EX-095의 기준/Blocked는 보존한다.

D-148의 EX-095를 JEV-35B-NVFP4 단일GPU 동일 대진 샘플 규범으로 편입한다.
조건·검증·한도·실패 분모·해석 원문은 [EX-095](../../research/planner-executor/experiments/EX-095-jev35b-nvfp4-sample.md)다.
이 문서의 현재 연구선은 `research/model-training`이며 최상위 목적은 **모델 학습·정책 개선·독립 평가**다.
[D-131](decisions/D-131-research-branch-preservation.md)에 따라 두 목적의 현재 작업을 분리한다. 기존 실험의 조건·평가·해석과
Blocked/Paused 판정은 보존한다. EX-084의 Quyet-Medium 2단계 동일 대진 평가를 완료했으며
EX-085의 공식 JEV-9B 단일 Choice 동일32경기와 EX-088/089의 교정v6 신규64경기 평가도
완료했다. D-137/EX-090의 피해 예측 제거 신규32경기 비교도 승인 범위에서 종결했다.
D-138/EX-091의 MiniCPM5-2B-Jev 계산기 포함 신규32경기 비교도 승인 범위에서 완료했다.
EX-095는 반복성 gate 실패로 본경기 미실행1·Blocked를 보존한다. 실행 상태와 후속 범위는 STATUS/EP-154를 따른다.
분리 기반 구성은 [EP-135](plans/EP-135-research-branch-preservation.md), 경로·외부 자산·복원은 [연구선 작업·출력·복원 안내](../../RESEARCH_WORKFLOW.md)를 따른다.

- 상태 (Status): Current — 모델 학습·정책 개선·독립 평가; EX-091 완료
- 편집 기준일 (As of): 2026-10-14 — D-138 MiniCPM5-2B-Jev 비교 종결
- Authority domain: research question, hypothesis, treatment definition, comparison methodology,
  evaluation protocol, interpretation rule

이 문서는 현재 이 프로젝트가 무엇을 어떤 비교와 evidence로 검증하려 하는지에 대한 source of
truth다. 현재 값이 `TBD`라는 사실도 authoritative state의 일부다. 과거 run의 configuration과
result는 [`experiments/`](../../experiments)에, 설계 변경의 rationale은
[`decisions/`](../../decisions)에 둔다.

이 문서는 [`CHARTER.md`](../../CHARTER.md)의 project goal과 fundamental invariant를 변경하지 않으며,
[`CONTRACTS.md`](../../CONTRACTS.md)의 runtime semantics를 재정의하지 않는다. 상속된 code나 paper
artifact를 설명할 때는 현재 연구 설계로 채택했다는 의미가 없도록 아래 status를 사용한다.
현재 system composition과 data/control flow는 [`ARCHITECTURE.md`](../../ARCHITECTURE.md), 실제 수행
단위는 [`exec-plans/INDEX.md`](../../exec-plans/INDEX.md), 현재 진행 상태는 [`STATUS.md`](../../STATUS.md)가
각각 담당한다. Implementation에서 관찰한 동작은 이 문서의 methodology를 자동으로 바꾸지 않는다.

일반 절에서 L1-L5를 명시한 미정 항목은 그 연구선의 전체 효능 비교 설계와 확증 evidence에
한정한다. 개별 학습·pilot·운영 비교·요약 진단의 조건과 평가는 해당 D-XXX 절과 EX를 따른다.
브랜치의 현재 목적은 [§1](#branch-research-objective), 학습 연구선의 방향·미정 설계는
[포켓몬 전용 학습 절](../../research/policy-learning/DESIGN.md#pokemon-training-objective)에 구분한다.
운영 실험·진단이 등록되지 않았다는 뜻으로 해석하지 않는다. 개별 실행·중단·검증 상태는
[`STATUS.md`](../../STATUS.md)와 [`experiments/INDEX.md`](../../experiments/INDEX.md)가 연결하는 record를
확인한다. 설계의 채택 자체는 중단된 실행의 재개 승인이 아니다.

| 표시 | 의미 |
|---|---|
| **Current** | 이 브랜치에서 채택한 연구 목적·설계. 실행 중이라는 뜻은 아니다. |
| **Preserved** | 다른 연구선 또는 과거 승인 범위의 설계·근거를 보존한다. 당시 조건·판정을 변경하지 않는다. |
| **Observed** | Source, test 또는 artifact에서 확인한 구현·기록 사실. 그 자체로 연구 의도는 아니다. |
| **Excluded legacy** | 원저자 연구의 evidence이지만 Decision D-002에 따라 현재 설계로 승계하지 않은 항목 |
| **Provisional** | 검토 가능한 후보이나 명시적 승인 전에는 experiment를 구속하지 않는 항목 |
| **Unresolved / TBD** | 현재 evidence만으로 정할 수 없는 항목 |
| **Missing** | 요구되는 evidence 또는 record가 현재 존재하지 않는 상태 |

<a id="current-state"></a>
### Current state

<a id="branch-research-objective"></a>

이 브랜치의 최상위 연구 목적은 **포켓몬 전용 모델 학습·정책 개선·독립 평가**다.
[D-131](decisions/D-131-research-branch-preservation.md)과 [CHARTER](../../CHARTER.md)에 따라 RQ4를 중심으로 학습 효과와 정책의 성능을
구분하여 검증한다. 모델 선택에 사용하지 않은 평가 자료와 사전 지표·분모·불확실성 기준으로
개선 여부를 판단하며, 기존 평가 자료를 학습에 자동 편입하지 않는다.

L1-L5 구조 이식의 broad RQ1과 미정 설계는 `research/l1-l5-port`의 목적·보존 근거다.
이 문서에도 관련 규범·참조를 유지하지만 학습 연구의 상위 목표나 자동 후속 작업으로 두지 않는다.
두 연구선의 결합 방식은 미정이다. 기존 입력·JEV·AgenticSTS·학습 구현을 공통 기준선에 유지한다.

개별 EX에 채택된 학습·운영 비교와 아직 미정인 L1-L5 전체 효능 비교를 구분한다.
새 실험의 objective·질문·처치·평가·예산은 관련 authority와 bounded plan/EX에서 정한다.
상속 artifact의 hypothesis·benchmark·결과와 과거 미완료 계획을 자동 채택하지 않는다.
분리 범위는 EP-135의 기반 구성·보존에 한정한다. 현재 새 학습·GPU·외부 API·실제 배틀 실행은 없다.
