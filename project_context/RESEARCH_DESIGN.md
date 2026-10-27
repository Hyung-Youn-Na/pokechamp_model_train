# 공통 연구 설계

현재 연구선의 목적은 포켓몬 모델 학습·정책 개선·독립 평가다. [CHARTER](CHARTER.md)와 [현재 상태](STATUS.md)를 함께 읽는다.
D-170에 따라 이 파일은 공통 원문과 주제별 원문 연결을 담당한다. 이전 절은 아래 링크의 주제 문서가 편집 원문이며 적용 범위를 자동 확대하지 않는다.
L1–L5를 명시한 설계·미정 항목은 별도 연구선의 보존 범위다. 과거 실험의 Current·현재·이번 표시는 그 당시 범위이며 실행 지시가 아니다.


<a id="current-rules"></a>

<a id="적용-범위와-읽기-경로"></a>
## 적용 범위와 읽기 경로

[연구 질문별 목록](research/INDEX.md)에서 주제 원문을 찾는다. 새 설계에는 아래 공통 평가·복구·
해석 규칙과 해당 주제의 명시된 적용 범위를 함께 사용한다.

<a id="1-연구-목적-research-objective"></a>
## 1. 연구 목적 (Research Objective)

<a id="current-objective"></a>

현재 목표는 포켓몬 모델 학습·정책 개선·독립 평가이며 최상위 원문은 [CHARTER](CHARTER.md)다.
구체적 질문·처치·평가·자원은 승인된 개별 D·EP·EX에서 정한다.
현재 실행과 중단 보존은 [STATUS](STATUS.md) 및 [계획 색인](catalog/plans.md)에서 확인한다.

<a id="4-실험-단위와-처리-조건-experimental-units--treatments"></a>
## 4. 실험 단위와 처리 조건 (Experimental Units / Treatments)

<a id="연구선별-적용-범위와-보존된-pilot-조건"></a>
### 연구선별 적용 범위와 보존된 pilot 조건

학습 연구선의 기존 처치·분할·평가는 해당 EX의 동결 조건을 따른다. 후속 실행 조건은
새 범위에서 정한다. 아래 pilot 조건과 L1-L5의 미정 항목은 그 지정 범위에만 적용한다.

- Experimental unit: Pilot은 경기 slot; 팀/seed와 진영 교환을 shared block으로 묶는다.
- Baseline/control: Pilot은 pinned minimax/IO/Abyssal/OneStep/Random inventory.
- Treatment: L1-L5 효능 treatment는 **TBD**.
- Unit independence 또는 grouping rule: 같은 team/seed를 공유하는 대진은 하나의 block으로 분석한다.

효능 비교의 treatment는 미정이다. Pilot 방법은 minimax, IO, Abyssal, OneStep, Random으로
승인됐다. 다음 표는 재사용 가능성을 평가할 때
참조할 **Observed, Excluded legacy** condition inventory이며 current treatment matrix가 아니다.
정확한 code-level setting은 [`run_ablation.py`](../AgenticSTS/scripts/run_ablation.py)와 관련
[tests](../AgenticSTS/tests/test_run_ablation.py)에서 확인된다.

| Legacy kind | Code에서 관찰된 configuration | 한 condition에 결합된 변화 | Current status |
|---|---|---|---|
| `baseline-strict` | `prompt_variant=baseline`; skills/L4/evolution/postrun/STM/combat conversation/boss HP off; hint filter와 strict knowledge on | Prompt family, context content, state exposure, conversation behavior를 동시에 변경 | Excluded legacy; 단일-factor baseline으로 채택되지 않음 |
| `prompt-only` | Full prompts; skills/L4/evolution/postrun/STM off; combat conversation과 boss HP on | `baseline-strict` 대비 prompt 및 여러 gate가 함께 달라짐 | Excluded legacy |
| `mode-a` | Full prompts와 expert L5 seeds; L4/evolution/postrun/STM off | `prompt-only` 대비 skill retrieval과 authored seed content가 함께 활성화 | Excluded legacy |
| `self-evolve` | Full prompts; L4/L5/evolution/STM/postrun on; expert seeds off; Mode B stubs 및 stub fill on; per-experiment writable store | Memory, skill source, learning, postrun, sequential store growth를 결합 | Excluded legacy; isolation이 필요한 복합 treatment |
| `full` | Code와 tests에서는 full prompts, L4/L5/evolution/STM on, expert seeds 사용, `postrun=False`, shared data root | 여러 layer와 이미 존재하는 store content를 결합 | Excluded legacy; 정의 drift가 있어 현재 treatment로 사용 불가 |

Legacy paper label `mode-b-frozen`과 `full-frozen`은 각각 특정 released artifact에서
code-level `self-evolve`, `full`에 대응한다. 이 mapping은
[`CONTRACTS.md` C-006](CONTRACTS.md)의
legacy reproduction 범위에만 적용하며 새 run 이름을 추측으로 join하지 않는다.

`full`의 postrun setting은 명백히 일치하지 않는다. Reference ABLATION table은 postrun을
`on`으로 설명하지만 `Condition.postrun` default, matrix construction, tests는 `False`와
`--no-postrun`을 확인한다. 이 차이는 **Unresolved treatment-definition conflict**다.

<a id="8-평가-절차-evaluation-protocol"></a>
## 8. 평가 절차 (Evaluation Protocol)

L1-L5 baseline-vs-treatment efficacy comparison procedure는 미정이다. 기준선 pilot의
unit/count/sampling/order/retry/stopping은 D-012와 EX-002에 승인되어 있다.

새 efficacy protocol은 적어도 다음을 실행 전에 명시해야 한다. 이는 현재
[`CHARTER.md`](CHARTER.md), [`CONTRACTS.md` C-006](CONTRACTS.md),
[`experiments/TEMPLATE.md`](experiments/TEMPLATE.md)의 제약을 정리한 것이며 구체적 숫자를 새로
정한 것이 아니다.

1. RQ와 hypothesis, baseline/treatment의 정확한 차이, experimental unit과 population.
2. Primary/secondary outcome, numerator/denominator, aggregation, uncertainty 및 claim threshold.
3. Sample size 또는 stopping rule, order/randomization, incomplete-run 및 retry policy.
4. Model/provider/effort, prompt family, environment version, data snapshot과 mutable-store isolation.
5. Stable `experiment_tag`, condition identity, invalidation criterion, 모든 attempt의 audit trail.
6. Code/harness 변경이 필요하면 별도 active exec plan, 실제 run마다 개별 experiment record와
   durable evidence link.
7. [§11.1](#defect-recovery)의 복구 규칙 적용 여부, 별도 전체 중단 사유·범위,
   재수집 허용 여부·단위·한도, 동일 승인·예산·시계 연결 및 실행기의 지원 여부.

<a id="io-explanation-review"></a>

<a id="81-기본-io-테스트의-설명-오류-검토-기본값"></a>
### 8.1 기본 IO 테스트의 설명 오류 검토 기본값

[D-050](shared/governance/decisions/D-050-io-explanation-review-opt-in.md)에 따라 2026-09-14 이후 새로 계획하는
**기본 IO 알고리즘 테스트에서는 별도 사용자 지시가 없으면 설명 오류 검토·기입을 수행하지 않는다.**
일반 IO 실행·입출력 동작·성능 확인 및 그 viewer 생성 요청에 설명 평가를 자동 추가하지 않는다.
원본 IO 또는 개선 IO를 시험한다는 이유만으로 과거 실험의 설명 전수 검토를 상속하지 않는다.

- 기본 제외: LLM 설명/reasoning의 사실·진영·시점·계산 주장에 대한 사후 오류 탐색,
  수동/모델 전수 검토, 설명 오류 annotation 추가와 설명 오류율 집계.
- 명시 요청 시 수행: 사용자가 설명 오류 검토·기입 또는 설명 정확성 평가를 요청한 범위를
  해당 plan에 기록한다. 기본값 적용 여부를 매번 확인 질문하지 않는다.
- 계속 수행: 승인된 IO 형식·합법 행동·입력/계산/실제 전달·실행 실패·무결성 검사,
  성능/비용 보고와 원문 응답·provider reasoning 기록/표시. 기술 결함은 기존 규칙대로 처리한다.
- 설명 평가를 하지 않은 새 기본 테스트는 보고서에 `미평가(기본 제외)`로 밝힌다.
  검토 부재만으로 테스트를 미완료 처리하지 않으며 오류0·정상 설명·의미 검증 통과로 주장하지 않는다.

기존 실험의 평가·오류 기록·annotation·미검토·Blocked는 보존한다. 이 기본값은 과거 결과를
소급 재평가하거나 재개하는 지시가 아니다. 별도로 승인된 설명/요약 의미 진단과 그 고정 gate는
해당 명시 범위를 따른다. 아래 실험별 전수 검토 규칙을 새 기본 테스트의 필수 요건으로 자동
복사하지 않는다. 계약 및 실행기 적용 경계는 [C-032](CONTRACTS.md#c-032-io-explanation-review)를 따른다.

<a id="9-무작위성과-재현성-randomness-and-reproducibility"></a>
## 9. 무작위성과 재현성 (Randomness and Reproducibility)

| Source of variation | Observed state | Reproducibility status |
|---|---|---|
| Game/simulator RNG | Upstream run payload에는 `seed`가 있으나 `RunRecord` schema에는 별도 seed field가 없음 | Run-level exact replay 근거가 불완전함; pin/record policy TBD |
| Model sampling | Default temperature는 0이나 provider와 thinking mode가 parameter를 변경/제거할 수 있고 remote service는 비결정적일 수 있음 | Configured model/effort는 profile에 기록되지만 exact decoding/service identity seal은 없음 |
| Provider routing/fallback | Configured provider/model과 일부 per-call telemetry가 존재 | Fallback이 발생하면 run-level profile만으로 actual route를 완전히 설명하지 못함 |
| Local Python randomness | Skill ranking tie-break와 일부 fallback action이 unseeded `random`을 사용 | Seed 또는 RNG-state record를 확인하지 못함 |
| Run ordering | Legacy orchestrator는 deterministic condition-major loop이고 timestamp를 기록 | Randomized/block order가 아님; time/provider drift와 결합 가능 |
| Sequential learning | Writable `self-evolve` store는 앞선 run의 결과가 뒤 run treatment state를 바꿈 | Run이 independent replicate가 아닐 수 있으며 order를 treatment history로 기록해야 함 |
| Environment/data version | History line에 game/mod/schema version을 append하고 `data_repo_sha`/`machine_id`를 기록할 수 있음 | 값이 비어 있거나 `unknown`일 수 있으며 current acceptance rule은 TBD |
| Analysis resampling | Legacy bootstrap helper는 seed `42`를 사용 | Legacy reproduction에 한정해 pinned됨; current analysis method는 미채택 |

Pilot은 C-010의 sealed plan, 경기별 actual seed와 actor source bundle을 사용한다. Remote
model decoding의 완전한 재현성은 보장하지 않으며 model response identity와 UTC를 기록한다.

<a id="10-교란-요인과-타당도-위협-confounders-and-threats-to-validity"></a>
## 10. 교란 요인과 타당도 위협 (Confounders and Threats to Validity)

아래 위험은 상속 stack을 새 연구에 재사용할 때 직접 관련되는 항목이다.

| Category | Current risk |
|---|---|
| Treatment coupling | `baseline-strict`와 `self-evolve`는 여러 prompt, memory, conversation, learning flag를 함께 바꾸므로 차이를 한 component에 귀속할 수 없다. |
| Treatment-definition drift | `full`의 postrun 상태가 reference doc과 executable code/tests에서 다르다. |
| Provenance/classification | `RunRecord`에 explicit `experiment_condition_id`와 Mode B flags가 없고 report가 `model_profile`에서 condition을 추론한다. 다른 설정이 같은 label로 합쳐질 수 있다. |
| Store contamination | `self-evolve`에는 isolation path가 있지만 `full`은 shared inherited store를 읽는다. Snapshot/clean-start identity가 없으면 treatment가 달라진다. |
| Sequential dependence | Learning condition에서는 later run이 earlier run과 동일한 treatment state를 공유하지 않는다. Ordinary independent-run CI 해석이 부적절할 수 있다. |
| Denominator drift | Live orchestrator, generic `ablation_report`, paper reproduction이 incomplete/aborted outcome을 동일하게 filter하지 않는다. |
| Model/provider confounding | Tier routing, thinking effort, fallback, postrun model이 condition 또는 시간에 따라 달라질 수 있다. `self-evolve`는 model만 strategic tier에 맞추고 effort는 동기화하지 않는다. |
| Environment drift | Game/mod/data version과 provider service가 batch 사이에 바뀔 수 있다. 기록값이 없는 run은 matched comparison을 약화한다. |
| Unrecorded randomness | Game seed와 local RNG state가 run evidence에 완전하게 보존되지 않는다. |
| Outcome ambiguity | Stored `score`, `fitness`, reproduction derived score가 별개인데 이름만으로 같은 measure로 합칠 위험이 있다. |
| Evidence availability | Run-level archive는 존재하지만 full per-decision trajectory 일부는 이 checkout에 없다고 data README가 명시한다. 세부 correctness/cost audit이 제한될 수 있다. |
| Sample size | Current design에는 N이나 power/precision target이 없다. Legacy N=5/N=10 result를 새 claim의 충분한 evidence로 간주할 수 없다. |

<a id="11-무효화-및-즉시-중단-기준-invalidation--hard-stop-criteria"></a>
## 11. 무효화 및 즉시 중단 기준 (Invalidation / Hard-stop Criteria)

| Situation | Classification | Required handling |
|---|---|---|
| RQ, hypothesis, treatment contrast, primary outcome, denominator 또는 stopping rule 미정 | Design incomplete | Efficacy experiment와 efficacy claim을 시작하지 않는다. |
| Required experiment record, stable tag/condition identity 또는 provenance 누락 | Missing evidence | 결과를 efficacy evidence로 인정하지 않는다. 원 evidence를 사후 추측으로 채우지 않는다. |
| [`CONTRACTS.md`](CONTRACTS.md)의 state/action/schema/validation boundary 위반 | Technical qualification failure | Attempt를 invalid로 기록하고 research outcome과 분리한다. |
| Model/provider/effort, prompt, environment 또는 data snapshot이 declared condition과 불일치 | Configuration drift | 영향이 사전 규칙으로 허용되지 않았다면 matched comparison에서 제외하고 audit trail을 남긴다. |
| Writable-store leakage 또는 treatment 간 state 공유 | Invalid treatment isolation | 오염된 comparison을 efficacy evidence로 사용하지 않는다. |
| Malformed/missing required raw evidence | Evidence integrity failure | 분석을 중단한다. Runtime loader가 skip한 line도 분모에서 조용히 사라지게 두지 않는다. |
| `agent_abort`, `mcp_error`, `interrupt`, timeout/provider outage | Infrastructure/runtime failure | Research failure나 defeat로 자동 변환하지 않는다. Attempt를 보존하고 predeclared retry/exclusion rule을 적용한다. |
| `max_steps` 또는 그 밖의 non-terminal stop | Censored/incomplete run | 현재 처리 규칙은 Unresolved다. Policy가 정해지기 전에는 efficacy denominator에 포함하지 않는다. |
| Natural `victory`/`defeat` | Potential efficacy unit | Declared population, condition, qualification을 충족할 때만 분석 대상이 된다. |

정확한 qualification suite와 threshold는 **TBD**다. Unit test 또는 smoke success는 기술적
실행 가능성을 보일 수 있지만 hypothesis efficacy를 support하지 않는다.

<a id="defect-recovery"></a>

<a id="111-테스트평가-도구-결함의-공통-복구-절차"></a>
### 11.1 테스트·평가 도구 결함의 공통 복구 절차

[D-029](shared/governance/decisions/D-029-experiment-defect-recovery.md) 채택(2026-09-09) 후 **새로 승인·등록하는
실험부터** 아래 절차를 기본으로 적용한다. 기존 실험과 이 문서의 D-019~D-028 등 실험별 절에
기록된 전체 중단·재시도·재개 규칙은 당시 실험에 유지한다. 기존 실험의 증거·무효 판정·
`Blocked`를 소급 복구하지 않는다. 새 실험에서 별도 전체 중단 규칙이 필요하면 사유와 범위를
등록한다. §11의 무효화 원칙을 유지하면서 결함의 중지·복구 범위를 아래처럼 판단한다.

1. **발견·보존:** 발견 단계와 증상을 기록하고 당시 source, 입력, 평가 기준, 응답과 보고서를
   보존한다. 모델의 잘못된 답변 자체는 도구 결함과 구별하여 실험별 측정·gate 규칙을 따른다.
   새 실험의 모델 판단 오류는 [§11.2](#provider-judgment-errors)를 따른다.
   도구 결함과 모델 오류가 함께 있으면 둘을 구분해 기록한다.
2. **영향받는 작업 일시 중지:** 의존하는 단계 진입·신규 수집·분석·claim을 필요한 범위에서
   보류한다. 잠재 영향 범위가 불명확하면 공유 의존성을 포함하여 먼저 넓게 중지한다.
   이미 진행 중인 작업의 증거 보존·정리는 해당 실행기와 중단 규칙 안에서 수행한다.
3. **원인·영향 확인:** 원자료에 근거한 재현으로 테스트/평가 구현/기준/실제 수집의 어느
   경계가 잘못됐는지 판별한다. 같은 source·변환·rubric·store를 쓰는 조건 및 후속 결과까지
   추적한다. 영향이 없다는 입증 없이 표본을 유지하지 않는다.
4. **수정·독립 검증:** 중지된 범위의 구현 또는 기준을 별도 버전으로 교정한다. 원자료·별도
   계산·독립 사례로 검증하며 수정 구현의 기대값을 그대로 복제한 검사는 독립 검증이 아니다.
   결함 재현 검사와 관련 회귀 검사가 통과하고 영향 범위·복구 단위를 확정해야 의존 작업을
   재개할 수 있다. 실행 중인 수집의 source·기준을 바꾸지 않는다.
5. **재평가·재실행 및 보고:** 아래 판단표와 등록된 승인·상한·실행기 지원 범위 안에서만
   수행하고, 변경 전후 결과·분모·미완료 및 해석 한계를 함께 기록한다.

| 결함 유형 | 기본 처리 |
|---|---|
| 단위 테스트·fixture·경로만 잘못됨 | 의존하는 단계 진입을 보류하고 수정·재검증한다. 실제 실험의 입력·처치·수집·평가에 영향이 없다는 근거가 있으면 결과를 유지한다. |
| 평가 코드가 사전 기준을 잘못 구현함 | 관련 분석을 보류한다. 사전 기준은 유지하고 구현 수정 후 영향을 받는 모든 조건·응답을 동일하게 재평가한다. 수집이 온전하면 재호출은 필요하지 않다. |
| 정답·rubric 자체가 잘못됨 | 관련 분석을 보류하고 원문 근거로 교정 사유를 기록한다. 결과 확인 후 기준 변경임을 공개하고 기존 평가와 구분된 수정 분석으로 보고한다. 모든 영향 조건·응답에 같은 수정 기준을 적용한다. |
| 실제 입력·처치·수집이 잘못됨 | 영향을 받은 실행과 의존 결과를 무효 처리한다. 수정된 조건에서 비교 구조를 보존하는 필요한 단위를 재수집한다. 기존 응답의 재채점만으로 입력 오류를 해소하지 않는다. |
| 영향 범위가 불명확하거나 증거 무결성이 깨짐 | 공유 의존성을 포함한 잠재 영향 범위를 중지한다. 원자료·source·의존성으로 범위를 입증할 수 없으면 해당 비교 전체를 중단·무효 처리한다. |

정답·rubric 교정인지 입력 설계 오류인지 판단할 때는 사전 목적·원문과 **실제로 전달된 입력에서
요구 사실을 알 수 있는지**를 함께 대조한다. 필요한 입력을 누락한 수집 오류를 rubric 완화로
바꾸어 처리하지 않는다. 두 결함이 함께 있으면 각각 기록하고 입력 오류의 무효화도 적용한다.
검토 중 발견한 모델 오답이나 gate 실패를 테스트 오류로 재분류하여 통과시키지 않는다.

결함 기록은 개별 plan/experiment에 연결하며 다음을 남긴다.

- 발견 단계·시점·결과 확인 여부, 증상과 원자료에 근거한 재현 자료.
- 영향받는 입력·조건·실행·응답·분석, 공유 의존성과 후속 전파, 비영향 판단 근거.
- 수정 전후 source·평가 기준의 버전/해시·차이·교정 사유 및 원문 근거.
- 독립 검증의 방법·결과·근거와 결함 재현 검사·관련 회귀 검사 결과.
- 유지/무효/수정 분석/재수집의 범위·단위, 기존·새 identity 연결, 사용한 승인과 남은 상한.

재실행 단위는 사전 비교 구조를 보존한다. 대응 비교는 필요한 조건 쌍·block을 함께 다루고,
연쇄 메모리 오류는 최초 오염부터 후속 요약·행동·배틀 및 공유 store의 의존 결과까지 포함한다.
검증된 오염 전 경계 또는 clean state에서 다시 시작한다. 재수집할 표본은 결함·의존성으로
정하며 결과가 좋은 표본만 선택해 보존하거나 실패 분모를 삭제하지 않는다. 예정/시도/응답/
실패/무효/미실행/미확정/대응 누락과 복구 시도를 구별하고 반복을 독립 표본으로 늘려 세지 않는다.

기존 원자료·봉인·보고서는 보존한다. 수정 분석과 새 실행은 별도 버전·identity로 원본에
연결하고 전후 source·기준·cohort를 구분한다. 평가 기준 완화로 기존 실험을 통과시킨 것으로
보고하지 않는다. 새 실행도 검증·평가 완료 전에는 유효 결과로 인정하지 않는다.

같은 승인·예산·시간·호출 상한 안의 **허용된 복구**는 재승인을 요구하지 않는다.
상한은 수정·검증·재수집·새 identity로 초기화하지 않으며 최초 시계와 누적 사용량을 연결한다.
새 실험 등록 시 재수집 허용 여부와 한도(금지이면 0), 조건 쌍/연쇄 단위와 정리 여유를 명시한다.
상한 소진·재수집 미승인·필수 정보 부재이면 그 행동을 보류하고 가능한 보존·검증·미완료 보고를
수행한다. 추가 범위는 [INDEX](INDEX.md)의 승인 절차를 따른다. Provider 재시도 정책은 확대하지 않는다.

[C-018](CONTRACTS.md#c-018-recovery)과 [운영 매뉴얼](../integration/pokechamp/README.md#defect-recovery)의
실행기 지원 한계도 적용한다. 이 절차는 halt 삭제·기존 실행 덮어쓰기·시계 초기화의 허가가 아니며
현재 실행기가 지원하지 않는 복구를 명령이나 파일 편집으로 우회하지 않는다.

<a id="provider-judgment-errors"></a>

<a id="112-공급자-판단-오류는-전체-실험-중단-사유가-아니다"></a>
### 11.2 공급자 판단 오류는 전체 실험 중단 사유가 아니다

[D-074](shared/execution/decisions/D-074-provider-judgment-policy.md)의 사용자 지시에 따라 새 실험은 공급자·모델의
판단 오류를 측정 대상으로 기록하며 전체 중단 gate로 사용하지 않는다. 이 절은 §11.1의 도구
결함과 구분한다. 과거 동결 실험의 당시 규칙·판정·Blocked는 보존한다.

| 유형 | 처리 |
|---|---|
| 전략적으로 나쁜 합법 선택, 설명의 오답·모순·지시 미준수 | 원문과 진단을 남기고 해당 선택으로 경기를 계속한다. 실패·패배도 평가에 포함한다. |
| 확률 합계/반올림, 선택과 최댓값 불일치, 보조 확률·confidence의 누락·범위·키 이상 | 실행할 선택이 명확하고 합법이면 진단으로만 기록한다. 재정규화·최댓값 강제 선택·재질의로 모델 판단을 바꾸지 않는다. |
| 선택 누락·파싱 불가·후보 밖 선택 등 실행 불가능한 응답 | 사전 등록된 출력 복구/fallback이 있으면 그 범위만 적용한다. 없거나 소진되면 해당 경기만 실패로 종료하고 남은 독립 경기를 계속한다. |
| 실제 입력·관측·후보 생성 오류, 전송/수집 결함, 증거 무결성 훼손 | 판단 오류로 완화하지 않고 §11.1 및 기술 계약에 따라 영향 범위를 중지·복구한다. |

판단 오류 빈도나 설명 품질만으로 후속 독립 경기를 막거나 전체 실험을 Blocked로 만들지 않는다.
경기 실패·미완료·대응 누락을 보존하고 예정/시도/완료/실패 분모를 함께 보고한다. 미완료를
승패로 임의 변환하거나 실패를 빼고 성공 표본만 비교하지 않는다. 모든 경기 시도가 끝나도
사전 유효완료·대응쌍 기준 미달이면 비교 미완료로 보고한다.

인증·연결·timeout·429 등 통신 오류는 판단 오류가 아니며 기존 transport/예산/중단 계약을
따른다. 재시도·보충 경기·비용·시간 상한을 이 규칙으로 늘리지 않는다. 입력/관측·요청ID·
실행 후보의 합법성 검증은 유지한다. 전체 중단은 기술적 공유 영향·무결성·승인 상한 등
구체적인 별도 근거와 범위를 기록하며, 새 protocol에 포괄적인 “첫 오류 전체 중단”을 복사하지 않는다.

새 실행 등록 시 이 분류·경기 격리·실행기 지원을 확인한다. 구현 경계와 버전은
[C-046](CONTRACTS.md#c-046-provider-judgment)을 따른다. 문서 개정이 기존 실행기의 동작을
자동 변경하거나 중단 실험을 재개하는 것은 아니다.

<a id="13-증거-연결-evidence-mapping"></a>
## 13. 증거 연결 (Evidence Mapping)

| Research item | Required evidence | Current source | Status |
|---|---|---|---|
| 학습 연구선 / RQ4 | 명시적 사용자 지시, 학습·평가 설계 및 재현 증거 | [학습 목표와 보존 근거](research/policy-learning/DESIGN.md#pokemon-training-objective), [D-096](research/policy-learning/decisions/D-096-pokemon-training-objective.md), [D-131](shared/governance/decisions/D-131-research-branch-preservation.md), 개별 EX | **실행별 완료·중단·성능 판정은 해당 EX를 따름; 후속 실행 설계 TBD** |
| L1-L5 이식 연구선 / RQ1 | 명시적 사용자 승인과 Charter-compatible formulation | [`CHARTER.md`](CHARTER.md), [`D-005`](research/l1-l5-port/decisions/D-005-adopt-pokechamp-l1-l5-research-goal.md), [`STATUS.md`](STATUS.md) | **Objective와 broad RQ 승인; operationalization Unresolved** |
| 중간 연구 목표 / RQ2·RQ3 | 명시적 사용자 승인, 단계별 산출물·완료 기준 및 최종 목표와의 연결 | [이 문서 §2](research/input-and-memory/DESIGN.md#intermediate-objectives), [D-063](research/input-and-memory/decisions/D-063-intermediate-research-objectives.md) | **목표와 broad RQ 승인; 새 실험별 operationalization TBD, 목표 달성은 미평가** |
| H1 | Claim, direction, contrast, support/reject/inconclusive rule | 이 문서 §3 | **Missing / Unresolved** |
| L1-L5 전체 효능 baseline/treatments | Exact configuration manifest와 isolation rule | 이 문서 §4; legacy `run_ablation.py`는 참고 가능 | **Missing** — 별도 운영 조건의 부재를 뜻하지 않음 |
| Runtime contract qualification | API/state/action/parser evidence와 declared qualification result | [`CONTRACTS.md`](CONTRACTS.md), [`test_upstream_api_contract.py`](../AgenticSTS/tests/test_upstream_api_contract.py), [`test_upstream_state_parser.py`](../AgenticSTS/tests/test_upstream_state_parser.py) | 운영 검증 상태는 해당 EP/EX record 참조; L1-L5 이전본의 qualification은 미정 |
| Legacy condition behavior | Executable matrix와 regression tests | [`run_ablation.py`](../AgenticSTS/scripts/run_ablation.py), [`test_run_ablation_conditions.py`](../AgenticSTS/tests/test_run_ablation_conditions.py) | **Observed legacy**, definition conflict 있음 |
| Legacy run outcome | Run identity, outcome, floor, config/profile fields | [`AgenticSTS-Data/runs/history.jsonl`](../AgenticSTS-Data/runs/history.jsonl) | Available inherited evidence; current study에는 미등록 |
| Legacy paper aggregation | Cell tags, completed filter, score/CI code | [`scripts/reproduce/`](../AgenticSTS/scripts/reproduce) | Available inherited method; current protocol로 미채택 |
| 운영 experiment configuration/result | 개별 `EX-XXX` record와 linked raw evidence | [`experiments/INDEX.md`](experiments/INDEX.md), [`STATUS.md`](STATUS.md) | **등록됨** — 유효성·중단·미완료는 개별 record를 따르며 L1-L5 전체 효능 evidence로 승격하지 않음 |
| PokéChamp technical environment | Pinned source/toolchain, loopback server, secret-safe cloud route와 smoke artifact | [`EP-001`](shared/execution/plans/EP-001-pokechamp-reproducible-environment.md), [`C-008`](CONTRACTS.md), local `.artifacts/pokechamp/` | **Complete — local 및 real Cloud qualification 통과; efficacy evidence 아님** |
| Randomness/reproducibility seal | Game seed, decoding/service identity, order, code/data/environment snapshot | PokéChamp schema 및 개별 EX record의 manifest·receipt·source seal | 운영 seal과 한계는 개별 record 참조; L1-L5 전체 효능용 evidence는 미등록 |
| Per-call correctness/efficiency | Full state/decision/action/LLM telemetry와 aggregation definition | [`C-009`](CONTRACTS.md), [`PokéChamp observability schema`](../integration/pokechamp/observability/SCHEMA.md), 개별 EX record | 운영 호출·비용·오류 evidence는 등록됨; L1-L5 전체 효능용 집계와 근거는 미정 |

## 주제별 원문과 이전 앵커

<a id="현재-연구-설계-research-design"></a>
- [분리 전 안내](shared/governance/DESIGN.md#현재-연구-설계-research-design)
<a id="jev-planner-environment"></a><a id="glm-plannerjev-설정-환경"></a>
- [GLM planner–JEV 설정 환경](research/planner-executor/DESIGN.md#jev-planner-environment)
<a id="0-d-012-기준선-pilot의-현재-설계"></a>
- [0. D-012 기준선 pilot의 현재 설계](shared/execution/DESIGN.md#0-d-012-기준선-pilot의-현재-설계)
<a id="01-d-016-운영-동시성-측정"></a>
- [0.1 D-016 운영 동시성 측정](shared/execution/DESIGN.md#01-d-016-운영-동시성-측정)
<a id="branch-research-objective"></a><a id="current-state"></a>
- [Current state](shared/governance/DESIGN.md#branch-research-objective)
<a id="pokemon-training-objective"></a><a id="주-연구-목표--포켓몬-전용-모델-학습정책-개선독립-평가"></a>
- [주 연구 목표 — 포켓몬 전용 모델 학습·정책 개선·독립 평가](research/policy-learning/DESIGN.md#pokemon-training-objective)
<a id="pokemon-imitation-self-play"></a><a id="fixed-matchup-objective"></a><a id="단기-목표--고정-대진-공개-상태-정책-개선"></a>
- [단기 목표 — 고정 대진 공개 상태 정책 개선](research/fixed-matchup-learning/DESIGN.md#pokemon-imitation-self-play)
<a id="abyssal-first-objective"></a><a id="이전-단기-단계--qwen-모방-학습-이후-abyssal-상대-정책-개선"></a>
- [이전 단기 단계 — Qwen 모방 학습 이후 Abyssal 상대 정책 개선](research/policy-learning/DESIGN.md#abyssal-first-objective)
<a id="qwen-action-value-first-run"></a><a id="첫-학습--ex-060-후보별-조건부-행동가치"></a>
- [첫 학습 — EX-060 후보별 조건부 행동가치](research/action-value/DESIGN.md#qwen-action-value-first-run)
<a id="qwen-local-battle"></a><a id="qwen-실시간-연결--ex-062"></a>
- [Qwen 실시간 연결 — EX-062](research/action-value/DESIGN.md#qwen-local-battle)
<a id="qwen-training-matchup"></a><a id="qwen-학습-원대진--ex-063"></a>
- [Qwen 학습 원대진 — EX-063](research/action-value/DESIGN.md#qwen-training-matchup)
<a id="2-연구-질문-research-questions"></a>
- [2. 연구 질문 (Research Questions)](research/l1-l5-port/DESIGN.md#2-연구-질문-research-questions)
<a id="intermediate-objectives"></a><a id="중간-연구-목표와-최종-목표의-연결"></a>
- [중간 연구 목표와 최종 목표의 연결](research/input-and-memory/DESIGN.md#intermediate-objectives)
<a id="현재-연구-질문"></a>
- [현재 연구 질문](research/l1-l5-port/DESIGN.md#현재-연구-질문)
<a id="3-가설-hypotheses"></a>
- [3. 가설 (Hypotheses)](research/l1-l5-port/DESIGN.md#3-가설-hypotheses)
<a id="h1--tbd"></a>
- [H1 — TBD](research/l1-l5-port/DESIGN.md#h1--tbd)
<a id="5-독립-변수-independent-variables"></a>
- [5. 독립 변수 (Independent Variables)](research/l1-l5-port/DESIGN.md#5-독립-변수-independent-variables)
<a id="6-통제-변수-controlled-variables"></a>
- [6. 통제 변수 (Controlled Variables)](research/l1-l5-port/DESIGN.md#6-통제-변수-controlled-variables)
<a id="7-결과-측정치-outcome-measures"></a>
- [7. 결과 측정치 (Outcome Measures)](research/l1-l5-port/DESIGN.md#7-결과-측정치-outcome-measures)
<a id="current-outcomes--l1-l5-전체-효능-비교"></a>
- [Current outcomes — L1-L5 전체 효능 비교](research/l1-l5-port/DESIGN.md#current-outcomes--l1-l5-전체-효능-비교)
<a id="observed-legacy-procedure--not-adopted"></a>
- [Observed legacy procedure — not adopted](research/l1-l5-port/DESIGN.md#observed-legacy-procedure--not-adopted)
<a id="12-해석-규칙-interpretation-rules"></a>
- [12. 해석 규칙 (Interpretation Rules)](research/rule-learning/DESIGN.md#12-해석-규칙-interpretation-rules)
<a id="kev-battle-connection"></a><a id="d-108-kev-r1-연결-검증"></a>
- [D-108 Kev r1 연결 검증](research/model-evaluation/DESIGN.md#kev-battle-connection)
<a id="14-미해결-연구-질문-open-research-questions"></a>
- [14. 미해결 연구 질문 (Open Research Questions)](research/l1-l5-port/DESIGN.md#14-미해결-연구-질문-open-research-questions)
<a id="15-현재-연구-단계-current-research-stage"></a>
- [15. 현재 연구 단계 (Current Research Stage)](research/l1-l5-port/DESIGN.md#15-현재-연구-단계-current-research-stage)
<a id="보존된-운영-검증의-범위"></a>
- [보존된 운영 검증의 범위](shared/execution/DESIGN.md#보존된-운영-검증의-범위)
<a id="d-017-요청-조건-변경과-운영-검증"></a>
- [D-017 요청 조건 변경과 운영 검증](shared/execution/DESIGN.md#d-017-요청-조건-변경과-운영-검증)
<a id="d-018-원본-fallback-운영-조건"></a>
- [D-018 원본 fallback 운영 조건](shared/execution/DESIGN.md#d-018-원본-fallback-운영-조건)
<a id="d-019-io-3조건-탐색적-비교-current"></a>
- [D-019 IO 3조건 탐색적 비교 (Current)](research/input-and-memory/DESIGN.md#d-019-io-3조건-탐색적-비교-current)
<a id="d-021-특수-기술-오프라인-진단-current"></a>
- [D-021 특수 기술 오프라인 진단 (Current)](research/input-and-memory/DESIGN.md#d-021-특수-기술-오프라인-진단-current)
<a id="d-022-재실험-current"></a>
- [D-022 재실험 (Current)](research/input-and-memory/DESIGN.md#d-022-재실험-current)
<a id="d-023-요약-harness-진단-current"></a>
- [D-023 요약 harness 진단 (Current)](research/input-and-memory/DESIGN.md#d-023-요약-harness-진단-current)
<a id="d-024-상태-정비-후-요약-thinking-진단-current"></a>
- [D-024 상태 정비 후 요약 thinking 진단 (Current)](research/input-and-memory/DESIGN.md#d-024-상태-정비-후-요약-thinking-진단-current)
<a id="d-027-low-요약-지시-개선-io-재실험-current"></a>
- [D-027 low 요약 지시 개선 IO 재실험 (Current)](research/input-and-memory/DESIGN.md#d-027-low-요약-지시-개선-io-재실험-current)
<a id="d-028-고정-이전-메모리-요약-lowmax-진단-current"></a>
- [D-028 고정 이전 메모리 요약 low/max 진단 (Current)](research/input-and-memory/DESIGN.md#d-028-고정-이전-메모리-요약-lowmax-진단-current)
<a id="d-030-요약-없는-improved_io-ab-탐색-비교-current"></a>
- [D-030 요약 없는 improved_io A/B 탐색 비교 (Current)](research/input-and-memory/DESIGN.md#d-030-요약-없는-improved_io-ab-탐색-비교-current)
<a id="d-031-행동-필드-설명서-구현-범위"></a>
- [D-031 행동 필드 설명서 구현 범위](research/input-and-memory/DESIGN.md#d-031-행동-필드-설명서-구현-범위)
<a id="d-032-필드-설명서-실제-cloud-탐색-비교"></a>
- [D-032 필드 설명서 실제 Cloud 탐색 비교](research/input-and-memory/DESIGN.md#d-032-필드-설명서-실제-cloud-탐색-비교)
<a id="d-033-사전-검증-생략-직접32판-탐색-비교"></a>
- [D-033 사전 검증 생략 직접32판 탐색 비교](research/input-and-memory/DESIGN.md#d-033-사전-검증-생략-직접32판-탐색-비교)
<a id="d-034-계산기-교정-동일32판"></a>
- [D-034 계산기 교정 동일32판](research/input-and-memory/DESIGN.md#d-034-계산기-교정-동일32판)
<a id="d-035-계산기-입력-정확성-로컬-진단"></a>
- [D-035 계산기 입력 정확성 로컬 진단](research/input-and-memory/DESIGN.md#d-035-계산기-입력-정확성-로컬-진단)
<a id="d-036-교정-입력계산기-동일32판"></a>
- [D-036 교정 입력·계산기 동일32판](research/input-and-memory/DESIGN.md#d-036-교정-입력계산기-동일32판)
<a id="d-038-수정-완료본-ab32판"></a>
- [D-038 수정 완료본 A/B32판](research/input-and-memory/DESIGN.md#d-038-수정-완료본-ab32판)
<a id="d-039-외부-메모리-장애-후-동일-조건-반복"></a>
- [D-039 외부 메모리 장애 후 동일 조건 반복](research/input-and-memory/DESIGN.md#d-039-외부-메모리-장애-후-동일-조건-반복)
<a id="d-040-smogon-기반-원본-a-진단-평가-준비"></a>
- [D-040 Smogon 기반 원본 A 진단 평가 준비](research/input-and-memory/DESIGN.md#d-040-smogon-기반-원본-a-진단-평가-준비)
<a id="d-041-원본-a64-진단-실행"></a>
- [D-041 원본 A64 진단 실행](research/input-and-memory/DESIGN.md#d-041-원본-a64-진단-실행)
<a id="d-042-원본-ab-직접-대결32"></a>
- [D-042 원본 A/B 직접 대결32](research/input-and-memory/DESIGN.md#d-042-원본-ab-직접-대결32)
<a id="d-044-protect-수정본-ab-직접32"></a>
- [D-044 Protect 수정본 A/B 직접32](research/input-and-memory/DESIGN.md#d-044-protect-수정본-ab-직접32)
<a id="d-045-전체-cloud-기본-동시성8"></a>
- [D-045 전체 Cloud 기본 동시성8](shared/execution/DESIGN.md#d-045-전체-cloud-기본-동시성8)
<a id="d-046-b-프롬프트-오프라인-최적화"></a>
- [D-046 B 프롬프트 오프라인 최적화](research/input-and-memory/DESIGN.md#d-046-b-프롬프트-오프라인-최적화)
<a id="d-047-b2-직접대결32"></a>
- [D-047 B2 직접대결32](research/input-and-memory/DESIGN.md#d-047-b2-직접대결32)
<a id="d-052-b2-선봉-정책-구현과-후속-비교-준비"></a>
- [D-052 B2 선봉 정책 구현과 후속 비교 준비](research/lead-policy/DESIGN.md#d-052-b2-선봉-정책-구현과-후속-비교-준비)
<a id="d-053-ex-039-선봉-정책-대응-비교-실행"></a>
- [D-053 EX-039 선봉 정책 대응 비교 실행](research/lead-policy/DESIGN.md#d-053-ex-039-선봉-정책-대응-비교-실행)
<a id="d-055-ex-040-zai-선봉-정책-비교"></a>
- [D-055 EX-040 Z.ai 선봉 정책 비교](research/lead-policy/DESIGN.md#d-055-ex-040-zai-선봉-정책-비교)
<a id="d-056-zai-기본4ex-041-재실험"></a>
- [D-056 Z.ai 기본4·EX-041 재실험](research/lead-policy/DESIGN.md#d-056-zai-기본4ex-041-재실험)
<a id="d-057-배틀선봉-상세-효과-사전"></a>
- [D-057 배틀·선봉 상세 효과 사전](research/input-and-memory/DESIGN.md#d-057-배틀선봉-상세-효과-사전)
<a id="d-058-새-응답-대기연결-재시도-기본값"></a>
- [D-058 새 응답 대기·연결 재시도 기본값](shared/execution/DESIGN.md#d-058-새-응답-대기연결-재시도-기본값)
<a id="d-059-공급자44-분산-선봉-비교"></a>
- [D-059 공급자4+4 분산 선봉 비교](research/lead-policy/DESIGN.md#d-059-공급자44-분산-선봉-비교)
<a id="d-060-새-공급자-오류-재시도"></a>
- [D-060 새 공급자 오류 재시도](shared/execution/DESIGN.md#d-060-새-공급자-오류-재시도)
<a id="d-061-선봉-전략규칙-입력-개선"></a>
- [D-061 선봉 전략·규칙 입력 개선](research/lead-policy/DESIGN.md#d-061-선봉-전략규칙-입력-개선)
<a id="d-064-교정-b2-개선-선봉-비교"></a>
- [D-064 교정 B2 개선 선봉 비교](research/lead-policy/DESIGN.md#d-064-교정-b2-개선-선봉-비교)
<a id="ex-044-직접-본실험"></a>
- [EX-044 직접 본실험](research/lead-policy/DESIGN.md#ex-044-직접-본실험)
<a id="d-066-공식-관측-소스-전환"></a>
- [D-066 공식 관측 소스 전환](research/input-and-memory/DESIGN.md#d-066-공식-관측-소스-전환)
<a id="d-067-공식-관측-b2-선봉-정책-비교"></a>
- [D-067 공식 관측 B2 선봉 정책 비교](research/lead-policy/DESIGN.md#d-067-공식-관측-b2-선봉-정책-비교)
<a id="d-069-비동기-교정본-공식-관측-본실험"></a>
- [D-069 비동기 교정본 공식 관측 본실험](research/lead-policy/DESIGN.md#d-069-비동기-교정본-공식-관측-본실험)
<a id="d-071-jev-choice-기술-진단"></a>
- [D-071 JEV Choice 기술 진단](research/model-evaluation/DESIGN.md#d-071-jev-choice-기술-진단)
<a id="d-072-jev-수치-표현-호환성-교정"></a>
- [D-072 JEV 수치 표현 호환성 교정](research/model-evaluation/DESIGN.md#d-072-jev-수치-표현-호환성-교정)
<a id="d-073-jev-수정본-재실행"></a>
- [D-073 JEV 수정본 재실행](research/model-evaluation/DESIGN.md#d-073-jev-수정본-재실행)
<a id="d-081-jev-대-abyssal32-탐색-측정"></a>
- [D-081 JEV 대 Abyssal32 탐색 측정](research/model-evaluation/DESIGN.md#d-081-jev-대-abyssal32-탐색-측정)
<a id="d-082-jev-v3-일반-게임-지식-추가"></a>
- [D-082 JEV v3 일반 게임 지식 추가](research/input-and-memory/DESIGN.md#d-082-jev-v3-일반-게임-지식-추가)
<a id="d-083-jev-v3-동일32-전후-비교"></a>
- [D-083 JEV v3 동일32 전후 비교](research/input-and-memory/DESIGN.md#d-083-jev-v3-동일32-전후-비교)
<a id="d-084-provider-재시도3회"></a>
- [D-084 provider 재시도3회](shared/execution/DESIGN.md#d-084-provider-재시도3회)
<a id="d-085-ex-054-동일-조건-재실험"></a>
- [D-085 EX-054 동일 조건 재실험](research/input-and-memory/DESIGN.md#d-085-ex-054-동일-조건-재실험)
<a id="d-088-ex-056-직접-본실험"></a>
- [D-088 EX-056 직접 본실험](research/input-and-memory/DESIGN.md#d-088-ex-056-직접-본실험)
<a id="d-089-ex-057-모델-고정-본실험"></a>
- [D-089 EX-057 모델 고정 본실험](research/input-and-memory/DESIGN.md#d-089-ex-057-모델-고정-본실험)
<a id="role-corpus-expansion"></a><a id="d-090-팀-데이터-기반-열람-역할-db"></a>
- [D-090 팀 데이터 기반 열람 역할 DB](shared/datasets/DESIGN.md#role-corpus-expansion)
<a id="d-091-현재-팀-후보-제한"></a>
- [D-091 현재 팀 후보 제한](shared/datasets/DESIGN.md#d-091-현재-팀-후보-제한)
<a id="d-092-jev-오프라인-표현정보-생략-비교"></a>
- [D-092 JEV 오프라인 표현·정보 생략 비교](research/input-and-memory/DESIGN.md#d-092-jev-오프라인-표현정보-생략-비교)
<a id="d-094--개선-입력-전체-처치-탐색-비교"></a>
- [D-094 — 개선 입력 전체 처치 탐색 비교](research/input-and-memory/DESIGN.md#d-094--개선-입력-전체-처치-탐색-비교)
<a id="d-095--자기-벤치-축약-탐색-비교"></a>
- [D-095 — 자기 벤치 축약 탐색 비교](research/input-and-memory/DESIGN.md#d-095--자기-벤치-축약-탐색-비교)
<a id="d-097--한-경기-조건부-행동-가치-데이터"></a>
- [D-097 — 한 경기 조건부 행동 가치 데이터](research/action-value/DESIGN.md#d-097--한-경기-조건부-행동-가치-데이터)
<a id="d-103--공동-q-학습-데이터"></a>
- [D-103 — 공동 q 학습 데이터](research/action-value/DESIGN.md#d-103--공동-q-학습-데이터)
<a id="d-107--자발적-tera-보완-공동-q-데이터"></a>
- [D-107 — 자발적 Tera 보완 공동 q 데이터](research/action-value/DESIGN.md#d-107--자발적-tera-보완-공동-q-데이터)
<a id="showdown-ruleqa"></a><a id="d-159--신규-showdown-규칙-데이터-v1"></a>
- [D-159 — 신규 Showdown 규칙 데이터 v1](research/rule-learning/DESIGN.md#showdown-ruleqa)
<a id="strategist-첫-배틀-탐색-평가"></a>
- [Strategist 첫 배틀 탐색 평가](research/model-evaluation/DESIGN.md#strategist-첫-배틀-탐색-평가)
<a id="tacit-규칙-qa-lora"></a>
- [Tacit 규칙 Q&A LoRA](research/rule-learning/DESIGN.md#tacit-규칙-qa-lora)
<a id="학습-tacit-실전32"></a>
- [학습 Tacit 실전32](research/rule-learning/DESIGN.md#학습-tacit-실전32)
<a id="openai-decisions-v6-상세-고정-대진-탐색"></a>
- [OpenAI Decisions v6 상세 고정 대진 탐색](research/model-evaluation/DESIGN.md#openai-decisions-v6-상세-고정-대진-탐색)
<a id="openai-통신-재시도-새32경기"></a>
- [OpenAI 통신 재시도 새32경기](research/model-evaluation/DESIGN.md#openai-통신-재시도-새32경기)
<a id="jevk5-9b-v6-상세32경기"></a>
- [JevK5-9B v6 상세32경기](research/model-evaluation/DESIGN.md#jevk5-9b-v6-상세32경기)
<a id="후보별-현재-대면-상성효과-요약"></a>
- [후보별 현재 대면 상성·효과 요약](research/input-and-memory/DESIGN.md#후보별-현재-대면-상성효과-요약)
<a id="후보별-요약-openai-동일32-탐색-비교"></a>
- [후보별 요약 OpenAI 동일32 탐색 비교](research/input-and-memory/DESIGN.md#후보별-요약-openai-동일32-탐색-비교)
<a id="jevk5-규칙-선택형-lora"></a>
- [JevK5 규칙 선택형 LoRA](research/rule-learning/DESIGN.md#jevk5-규칙-선택형-lora)
