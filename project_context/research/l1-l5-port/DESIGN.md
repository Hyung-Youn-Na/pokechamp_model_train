# L1–L5 이식 연구의 보존 맥락 — 연구 설계

D-170에 따라 중앙 문서의 관련 절을 이전한 편집 원문이다. 연구 설계·계약·구성의 domain authority와 각 절의 적용 버전·조건은 유지한다.
과거 날짜·실험·D별 절의 “현재”, “이번”, “Current”는 해당 당시 범위다. 현재 실행 여부와 승인은 개별 계획 및 전체 상태 색인에서 확인한다.
다른 주제의 기록을 인용하더라도 해당 원문의 소유권·범위를 이전하지 않는다.


<a id="2-연구-질문-research-questions"></a>
## 2. 연구 질문 (Research Questions)

기존 Qwen 입력 개선의 [D-102](../action-value/decisions/D-102-qwen-candidate-state.md)는 제공 정보의
결정별 행동 순서·상태 변화 연결을 개발 가설로 둔다. [EX-064](../action-value/experiments/EX-064-qwen-candidate-state.md)의
저장 관측 3조건과 별도 진단은 조건부 상태 정확성·후보 순위·비용을 분리해 비교한다.
고정 모델의 학습 입력 분포 변화가 포함되며 q의 Abyssal 후속 조건 의미를 유지한다.
정확한 진단 출력은 q가 해당 예측을 사용했다는 증거가 아니며 개발 장면 개선을 독립 승률
개선으로 해석하지 않는다. 새 배틀·재학습·독립 성능 평가는 이 처치 범위 밖이다.

<a id="현재-연구-질문"></a>
### 현재 연구 질문

| ID | Status | Current formulation | 확정에 필요한 것 |
|---|---|---|---|
| **RQ1** | **Preserved — research/l1-l5-port, operationalization TBD** | AgenticSTS의 L1-L5 계층형 메모리/컨텍스트 구조를 `pokechamp`에 적용하면 `pokechamp`의 성능이 개선되는가? | Layer별 대응, 대상 population/version, baseline/treatment, performance metric과 claim criterion 승인 |
| **RQ2** | **Current — 학습 입력 참고, 새 비교 TBD** | 제공하는 정보의 종류와 표현이 행동 선택·배틀 성능·비용에 어떤 영향을 미치는가? | 정보 내용과 표현의 비교 범위, 통제 조건, 행동 변화·성능·비용의 측정 및 완료 기준 |
| **RQ3** | **Current — 학습 입력 참고, 새 비교 TBD** | 제공하는 이력의 범위와 요약 방식이 정보 보존·행동 선택·배틀 성능·비용에 어떤 영향을 미치는가? | 이력 범위·요약 조건, 정보 보존·손실 평가와 비교 protocol |
| **RQ4** | **Current — 주 목표, 후속 실행 설계 TBD** | 세 RLCD 환경을 활용한 포켓몬 전용 학습이 기준선 대비 행동 선택·배틀 성능에 어떤 변화를 만드는가? | 초기 모델·데이터/분할·학습 처치·통제 조건·평가 지표/분모·예산 및 claim criterion |

학습 연구선 RQ4의 기존 비교 설계는 [모방 학습·정책 개선·고정 대진 연구](../fixed-matchup-learning/DESIGN.md#pokemon-imitation-self-play)에 보존한다.
모방 학습 전후와 자기대국 전후의 효과를 구분하고, 구체적인 평가 조건은 실행 전에 정한다.

RQ2·RQ3은 RQ1의 메모리 내용·관리 방식 설계를 위한 중간 연구 질문이다. 구체적인 처치·지표·
표본 수·예산·중단 규칙은 새 실험별로 실행 전에 정한다. 행동 선택의 변화 자체를 품질 개선으로
해석하지 않는다. L1-L5 전체 효능 비교에서 무엇을 성능으로 측정할지와 correctness,
reliability, efficiency를 secondary outcome으로 다룰지는 **TBD**다.

상속 repository에는 bounded typed context와 accumulating transcript의 비교, L1-L5 layer의
기여 분해, self-evolution, cross-backbone behavior, cost/latency에 관한 원저자 질문이 나타난다.
근거는 [root README](../../../README.md),
[`AgenticSTS/docs/reference/ABLATION.md`](../../../AgenticSTS/docs/reference/ABLATION.md), 과거
competitor report에 있다. 이들은 모두 **Excluded legacy**이며 현재 RQ 번호를 부여하지 않는다.

<a id="3-가설-hypotheses"></a>
## 3. 가설 (Hypotheses)

L1-L5 전체 효능 비교의 H1은 아직 미정이다. 개별 학습·운영 실험에 채택된 질문·가설·판정은
각 D별 절과 동결 EX를 따르며, H1의 미정 상태로 그 설계나 결과를 부정하지 않는다.

<a id="h1--tbd"></a>
### H1 — TBD

- Status: **Unresolved**
- Claim: **TBD**
- Expected direction: **TBD**
- Comparison: **TBD**
- Supporting evidence rule: **TBD**
- Rejection rule: **TBD**
- Inconclusive rule: **TBD**

상속된 README와 reproduction material의 directional claim 또는 과거 point estimate를 H1으로
승격하지 않는다. `Provisional` hypothesis를 추가할 때도 claim, direction, comparison,
support/reject/inconclusive criterion을 실행 전에 함께 승인해야 한다.

<a id="5-독립-변수-independent-variables"></a>
## 5. 독립 변수 (Independent Variables)

L1-L5 전체 효능 비교의 independent variable과 estimand는 **TBD**다. 상속 stack에는 다음 configurable
factor가 관찰되지만, configuration switch라는 이유만으로 연구 변수가 되지는 않는다.

| Observed factor | 구현 surface | 현재 연구 변수 여부 |
|---|---|---|
| Prompt family 및 visibility gate | `STS2_PROMPT_VARIANT`, `STS2_PROMPT_HINT_FILTER`, `STS2_KNOWLEDGE_STRICT`, `STS2_INCLUDE_BOSS_HP` | 미채택 (TBD) |
| Context/memory layer | `STS2_MEMORY_ENABLED`, `STS2_SKILLS_ENABLED`, `STS2_STM_ENABLED`, `STS2_COMBAT_CONVERSATION_ENABLED` | 미채택 (TBD) |
| Skill source와 writable learning | expert seeds, Mode B stubs, postrun/evolution flags, data-root policy | 미채택 (TBD) |
| Model/provider/effort routing | model family, tier별 model/provider/effort | 미채택. Treatment가 아니면 control 또는 stratification 대상일 수 있음 |
| Character, ascension, run progression | `--character`, `--ascension` | 미채택. Population/difficulty definition 후보일 뿐임 |

새 variable은 변경되는 한 요소, 고정되는 요소, 측정하려는 causal contrast를 함께 명시해야
한다. 여러 switch를 묶으면 component별 기여가 아니라 그 bundle의 효과만 해석할 수 있다.

<a id="6-통제-변수-controlled-variables"></a>
## 6. 통제 변수 (Controlled Variables)

Pilot은 D-012의 model/environment/team/seed/source snapshot을 고정한다. 아래 표는 상속 stack이 제공하는
control/recording capability와 아직 필요한 결정을 구분한다.

| Factor | Observed control 또는 record | Current design status |
|---|---|---|
| Task/population | Legacy harness는 STS2 run을 단위로 받고 character와 ascension을 CLI로 지정 | Target domain은 `pokechamp`; 대상 version, task/population, experimental unit과 difficulty는 TBD |
| Model/provider | `model_profile`에 configured tier model, family, provider, effort와 profile hash를 기록 | 사용할 identity와 fallback 허용 여부 TBD. 실제 per-call route 검증 필요 |
| Sampling parameter | Default `LLM_TEMPERATURE=0`; provider/thinking mode에 따라 temperature가 생략되거나 다른 값이 강제될 수 있음 | Sealing rule TBD |
| Prompt/context family | Ablation env override와 일부 `model_profile` field로 기록 | 어떤 field를 고정할지 TBD |
| Mode B flags | Orchestrator가 env를 명시적으로 override | `model_profile`/`RunRecord`에는 세 Mode B flag가 없어 provenance가 불완전함 |
| Environment version | History append가 `game_version`, `mod_version`, `data_schema_version`을 JSONL에 추가 | 허용 version과 drift policy TBD |
| Data/store state | `data_repo_sha` 기록 가능; `self-evolve`는 writable store를 분리 | Clean/frozen start, snapshot identity, shared-state exception TBD |
| Legal action/runtime contract | Mod state/action API, local parser와 validation boundary는 [`CONTRACTS.md`](../../CONTRACTS.md)에 정의 | Efficacy control이 아니라 먼저 통과해야 할 technical qualification |
| Run ordering | Legacy orchestrator는 matrix order대로 condition별 run을 연속 실행 | Randomization/blocking/order policy TBD |
| Qualification | State/API tests와 smoke tooling은 존재 | L1-L5 전체 효능 비교용 suite와 threshold는 TBD; 운영 qualification evidence는 해당 EP/EX record 참조 |
| PokéChamp environment qualification | EP-001이 source/tool/server/cloud-adapter contract와 local/cloud smoke를 정의 | Completed — local deterministic smoke, real Cloud probe 및 29/29 valid-action one-battle 통과. Efficacy protocol은 아님 |
| PokéChamp decision observability | D-010/EP-002 bundle이 source SHA, seed, state/protocol, LLM wire call과 sent action을 기록 | Recording/viewer capability는 완료. 운영 run은 개별 EX record에 등록되며 L1-L5 전체 효능 protocol은 아님 |
| Showdown battle timer | Pinned server는 `forcetimer=true`지만 D-011 parent launcher가 process-local `false`로 override한다 | **Current:** 별도 timed-run 지시가 없으면 inactivity timer를 끈다. Timed run은 activation/configuration을 사전 선언·기록하고 untimed run과 같은 condition으로 합치지 않는다. |

<a id="7-결과-측정치-outcome-measures"></a>
## 7. 결과 측정치 (Outcome Measures)

학습·정책 개선 연구의 지표·분모·판정은 개별 EX가 소유한다. 후속 독립 평가는 학습·모델
선택 자료와 분리하고 사전 기준을 명시한다. 아래 TBD는 L1-L5 전체 효능 비교에 한정한다.

<a id="current-outcomes--l1-l5-전체-효능-비교"></a>
### Current outcomes — L1-L5 전체 효능 비교

- Primary outcome: **TBD**
- Secondary outcomes: **TBD**
- Unit of analysis 및 aggregation: **TBD**
- Uncertainty/statistical procedure: **TBD**

다음은 상속 artifact에서 계산 가능한 **Observed measures**다. 새 연구의 outcome으로 채택된 것은
아니다.

| Available measure | 측정 단위와 관찰된 aggregation | Data source | 제한 |
|---|---|---|---|
| `victory` / `outcome` | Run별 terminal outcome; legacy paper는 `victory`/`defeat`만 denominator로 한 win rate와 Wilson 95% CI 사용 | [`runs/history.jsonl`](../../../AgenticSTS-Data/runs/history.jsonl), [`reproduce_table_2.py`](../../../AgenticSTS/scripts/reproduce/reproduce_table_2.py) | 새 연구 denominator와 primary status는 TBD |
| Derived paper score | Run별 `100` if victory, else `floor + (52/3) * bosses`; legacy table은 mean과 percentile-bootstrap 95% CI | [`scripts/reproduce/_lib.py`](../../../AgenticSTS/scripts/reproduce/_lib.py) | Stored `score`/`fitness`와 동일하다고 가정하면 안 됨 |
| `final_floor` | Run별 도달 floor; legacy report에서 mean 사용 | [`src/runs/history.py`](../../../AgenticSTS/src/runs/history.py) | Difficulty/termination이 맞지 않으면 비교 불가 |
| `combats_won` / `combats_total` | Run을 합쳐 combat win fraction 계산 가능 | `history.jsonl`, [`ablation_report.py`](../../../AgenticSTS/scripts/ablation_report.py) | Combat mix와 run length에 민감하며 current metric 아님 |
| `duration_seconds`, `llm_calls`, `total_actions` | Run별 runtime 및 call/action count | `history.jsonl` | 직접적인 latency, token 또는 monetary cost와 같지 않음 |
| Per-call latency/token/cache fields | LLM call별 latency, prompt/completion/cache token | [`session_logger.py`](../../../AgenticSTS/src/log/session_logger.py), [`PokéChamp observability schema`](../../../integration/pokechamp/observability/SCHEMA.md) | 두 recording capability가 있으나 현재 연구 bundle과 승인된 aggregation은 없음 |
| Action result status | Action별 `ok`, `soft_fail`, `hard_fail`와 error | `session_logger.py` | Illegal-action/contract-violation rate의 canonical numerator·denominator는 미정 |
| LLM-as-judge quality | Legacy script의 action/reasoning/conciseness rubric | [`eval_decision_quality.py`](../../../AgenticSTS/scripts/eval_decision_quality.py) | Judge model, rubric validity, sampling protocol이 current design으로 승인되지 않음 |

<a id="observed-legacy-procedure--not-adopted"></a>
### Observed legacy procedure — not adopted

`run_ablation.py`는 default로 model별 5개 condition, condition당 10 run, `Silent`,
`--ascension auto`, 최대 5000 step을 condition-major order로 실행한다. `agent_abort`와
`mcp_error`를 slot당 최대 3회 retry하고, `interrupt`는 보존하며, `max_steps`는 non-victory
filled slot으로 센다. 반면 paper reproduction의 `filter_cell`은 `max_steps`까지 제외하고
start time 기준 첫 completed run을 고른다. 이 절차와 숫자는 **Excluded legacy**이며 서로 다른
denominator 규칙은 새 protocol을 정하기 전 해소해야 한다.

<a id="14-미해결-연구-질문-open-research-questions"></a>
## 14. 미해결 연구 질문 (Open Research Questions)

이 목록은 L1-L5 전체 이식·효능 설계의 미해결 질문이며 implementation TODO가 아니다.
해당 research design에서 정할 결정과 필요한 evidence를 나타낸다. 학습 후속 실행의
미정 조건은 [학습 목표 절](../policy-learning/DESIGN.md#pokemon-training-objective)과 개별 새 plan/EX에서 관리한다.

| ID | Question | Why it matters | Resolution evidence/decision |
|---|---|---|---|
| OQ-001 | `pokechamp`의 performance를 어떤 primary outcome과 성공 기준으로 operationalize하며 intended contribution을 어디까지 주장할 것인가? | Broad RQ를 검증 가능한 hypothesis와 claim으로 바꾸는 선행 조건이다. | Metric, denominator, uncertainty 및 claim criterion 승인 |
| OQ-002 | `pokechamp`의 어떤 component에 L1-L5를 어떻게 대응시키고 AgenticSTS의 code/data/contract 중 무엇을 이전 또는 재구현할 것인가? | Treatment identity, implementation scope와 external validity가 달라진다. | Target architecture 및 reuse-boundary decision |
| OQ-003 | 어떤 baseline과 treatment contrast가 핵심 estimand를 식별하는가? | Coupled legacy cells를 그대로 쓰면 component 기여를 분리할 수 없다. | Exact treatment manifest와 rationale |
| OQ-004 | Primary outcome, secondary outcome, success/rejection 기준은 무엇인가? | 결과 선택과 사후 해석 편향을 막는다. | Metric definition, denominator, uncertainty/claim rule 승인 |
| OQ-005 | Unit 수, stopping rule, ordering/randomization, incomplete-run과 retry policy는 무엇인가? | Selection bias, time drift, precision을 결정한다. | Pre-run protocol 및 experiment record |
| OQ-006 | Model/provider/effort와 fallback을 고정할지 연구 변수로 둘지 어떻게 정할 것인가? | Model effect와 treatment effect가 섞이는 것을 막는다. | Routing manifest와 provider-identity policy |
| OQ-007 | Game seed, local RNG, environment/data snapshot을 어느 수준까지 pin 또는 record할 것인가? | Exact replay와 stochastic comparison의 수준을 결정한다. | Reproducibility manifest와 qualification evidence |
| OQ-008 | 298-game legacy corpus와 과거 experiment를 새 RQ의 evidence로 사용할 수 있는가? | 재사용은 비용을 줄이지만 다른 목표·protocol의 selection bias를 가져올 수 있다. | Eligibility/exclusion rule과 provenance review |
| OQ-009 | `full` postrun drift와 outcome denominator 차이를 어떤 canonical definition으로 해소할 것인가? | Treatment identity와 sample inclusion이 불명확하면 비교가 재현되지 않는다. | 별도 accepted decision과 current-state/code 정합화 evidence |

<a id="15-현재-연구-단계-current-research-stage"></a>
## 15. 현재 연구 단계 (Current Research Stage)

**모델 학습·정책 개선·독립 평가를 주 개발 연구선으로 관리한다.**
분리 기반의 보존·Git 기준선·문서·worktree·검증과 완료 근거는 [EP-135](../../shared/governance/plans/EP-135-research-branch-preservation.md)가 소유한다.
학습·평가 실험은 실행 중이지 않으며 후속 방법·초기 모델·데이터·독립 평가·자원 조건을
새 범위에서 정한다. 기존 EX-079·EX-080의 종료·시험 결과와 주효능 미입증을 보존한다.
기존 Qwen·Kev·Abyssal·JEV 결과 및 중단 판정도 해당 EX의 조건·분모·한계 안에서 해석한다.

L1-L5 전체 효능 설계의 미정 상태는 별도 `research/l1-l5-port`에 유지한다.
기존 구현·환경의 존재나 과거 완료 이력은 새 실행 권한이 아니다.
운영 현황은 [STATUS](../../STATUS.md), 작업·보존본·출력·복원은 [연구선 작업·출력·복원 안내](../../RESEARCH_WORKFLOW.md)를 따른다.
