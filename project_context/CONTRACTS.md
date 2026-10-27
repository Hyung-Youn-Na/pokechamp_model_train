# 공통 실행 계약

현재 연구선의 목적은 포켓몬 모델 학습·정책 개선·독립 평가다. [CHARTER](CHARTER.md)와 [현재 상태](STATUS.md)를 함께 읽는다.
D-170에 따라 이 파일은 공통 원문과 주제별 원문 연결을 담당한다. 이전 절은 아래 링크의 주제 문서가 편집 원문이며 적용 범위를 자동 확대하지 않는다.
L1–L5를 명시한 설계·미정 항목은 별도 연구선의 보존 범위다. 과거 실험의 Current·현재·이번 표시는 그 당시 범위이며 실행 지시가 아니다.


<a id="current-rules"></a>

<a id="적용-범위와-읽기-경로"></a>
## 적용 범위와 읽기 경로

계약은 해당 schema·runtime 경로·정책 identity에 적용한다. 실험명·버전이 붙은 계약은
그 범위의 기술적 의미를 보존하며 새 작업에 당시 실행 계획 전체를 자동 추가하지 않는다.
새 실험의 공통 복구 경계는 [C-018](#c-018-recovery), 새 Cloud 기본값의 적용·호환 범위는
[C-029](shared/execution/CONTRACTS.md#c-029--새-cloud-기본-동시성8), 새 기본 IO 설명 검토의 적용 경계는
[C-032](#c-032-io-explanation-review)에서 확인한다. EX-040 식별자·중단 경계는 [C-035](research/lead-policy/CONTRACTS.md#c-035-ex040)를 따른다. 새 구조 설명·효과 사전 전송은 [C-037](research/input-and-memory/CONTRACTS.md#c-037-effect-reference), 선봉 독립 구성요소는 [C-040](research/lead-policy/CONTRACTS.md#c-040-lead-components)을 따른다. 구체 값을 이 안내에 복제하지 않는다.

중복 참조는 EP-039의 2026-09-14 대조 시점에 지정한 원문 범위만 이 계약에 명시적으로 편입한다. 이 문서의 domain authority나
원문 소유권을 이전하지 않고 참조 문서의 이후 변경을 자동 채택하지 않는다. 과거 실행 승인·
중단·실패 판정은 유지하며 여기의 과거 명령·승인 기록을 현재 실행 또는 재개 지시로 읽지 않는다.

<a id="c-006--experiment-identity-isolation-및-denominator"></a>
## C-006 — Experiment identity, isolation 및 denominator

- 아래 condition name과 corpus rule은 상속된 AgenticSTS artifact를 재현하거나 비교할 때만
  적용한다. 새 연구 프로그램의 default requirement, baseline 또는 candidate work가 아니다.
- Experiment run은 비어 있지 않은 stable `experiment_tag`를 사용한다. 비교는 condition도
  식별한다. Resume logic은 기록된 tag/condition evidence를 key로 사용한다.
- Writable condition은 L4/L5/evolution state를 격리해야 한다. 현재 `self-evolve` condition은
  aggregation을 위한 shared run-history routing을 유지하면서 experiment별 data root를 쓴다.
- 현재 code-level condition name은 `baseline-strict`, `prompt-only`, `mode-a`, `self-evolve`,
  `full`이다. 공개된 frozen label은 `self-evolve`를 `mode-b-frozen`에, `full`을
  `full-frozen`에 대응시킨다. 분석은 이 이름들을 추측으로 join하면 안 된다.
- 모든 experiment record는 denominator와 stopping rule을 명시해야 한다. 공개 paper corpus에서
  completed game은 `victory` 또는 `defeat`이며, `max_steps`와 infrastructure outcome은 298-game
  completed corpus에 포함되지 않는다. Live ablation orchestrator는 현재 `max_steps`를 채워진
  non-victory slot으로 취급하지만 paper reproduction filter는 제외한다. Decision으로 조정할
  때까지 이 차이를 명시적으로 유지해야 한다.
- Evidence가 존재한 뒤에만 result를 기록한다. Interface, version, routing 또는 cadence가 다른
  operational comparison은 해당 caveat를 유지해야 하며 controlled single-variable ablation으로
  다시 label하면 안 된다.
- 새 연구 experiment는 `project_context/experiments/` 아래의 새 record에서 시작하며 legacy
  hypothesis, condition, metric 또는 stopping rule을 암묵적으로 상속하지 않는다.

현재 experiment 상세 내용: [`ABLATION.md`](../AgenticSTS/docs/reference/ABLATION.md),
[`run_ablation.py`](../AgenticSTS/scripts/run_ablation.py),
[`scripts/reproduce/`](../AgenticSTS/scripts/reproduce).

<a id="c-007--distribution-및-provenance-경계"></a>
<a id="c-007-distribution-및-provenance-경계"></a>
## C-007 — Distribution 및 provenance 경계

최상위 component는 별도 license를 유지한다. Python agent는 Apache-2.0, mod fork는 AGPL-3.0,
data artifact는 CC-BY-4.0이다. Agent license는 mod나 data를 포괄하지 않는다. Repository의
ignore/export rule에 나열된 generated upstream 또는 proprietary game-knowledge file은 local에서
재생성하며, Apache-2.0으로 조용히 commit하거나 재배포하지 않는다.
[`release_exclusions.md`](../AgenticSTS/docs/release/release_exclusions.md)와
[`data/knowledge/README.md`](../AgenticSTS/data/knowledge/README.md)를 참조한다.

외부 submodule도 자체 license와 provenance를 유지한다. `pokemon-showdown/LICENSE`는 MIT다.
`pokechamp/pyproject.toml`과 classifier는 MIT라고 표시하지만 `pokechamp/LICENSE` 원문은 일본에서의
사용·배포·판매를 금지하는 추가 문구를 포함한다. 따라서 PokéChamp를 표준 MIT component로
축약하거나 현재 repository의 다른 license가 포괄한다고 해석하지 않는다. 재배포 또는 release
전에 원문 조건과 적용 가능성을 별도로 검토한다.

<a id="failure-behavior-요약"></a>
## Failure behavior 요약

| 경계 | 관찰된 동작 |
|---|---|
| Mod가 `ok: false`를 보고하거나 HTTP/connection failure 발생 | Python client가 error를 raise한다. Action error는 server의 `retryable` flag를 보존한다. |
| Wait 중 SSE를 사용할 수 없거나 실패 | Polling으로 fallback한다. Timeout은 계속 raise된다. |
| Strict state validation 실패 | `parse_state`가 raise한다. 명시적인 safe path만 `None`을 반환한다. |
| Default sibling data root 부재 | Path resolution이 `FileNotFoundError`를 raise하며 replacement store를 조용히 만들지 않는다. |
| Runtime run-history load에서 malformed line 발견 | Warning 후 해당 line을 건너뛴다. 계속 실행하기 위한 fail-open 동작이다. |
| Paper reproduction load에서 malformed JSONL 발견 | File과 line number를 포함해 raise한다. 분석을 위한 fail-closed 동작이다. |
| Monitor event emit 실패 | Monitoring error는 gameplay와 격리되며 agent를 crash하지 않는다. |
| PokéChamp source/tool/server preflight 실패 | Battle 또는 cloud call을 시작하지 않고 nonzero와 qualification artifact를 남긴다. |
| Cloud credential/configuration 부재 또는 불일치 | Client/network call 전에 fail-closed한다. |
| Cloud auth/model/rate-limit/timeout/transport 실패 | 분류한 failure를 기록하고 다른 endpoint, model 또는 local backend로 fallback하지 않는다. |
| Research data root/bundle initial open 실패 또는 ID 충돌 | Player/challenge를 만들기 전에 fail-closed하며 기존 bundle을 수정하지 않는다. |
| Battle 진행 중 research recorder write 실패 | Gameplay를 변경하지 않고 warning을 내며 가능한 경우 incomplete manifest와 `logging_error`를 남긴다. |
| Research checksum 불일치 또는 partial source | Renderer/catalog가 integrity/partial 상태를 표시하며 complete evidence로 분류하지 않는다. |

이 차이는 의도에 대한 주장이 아니라 관찰된 사실이다. 새 code에서 fail-open 또는 fail-closed를
일반적으로 선호하라는 지시가 아니다. 새 boundary는 자체 policy를 명시해야 한다.

<a id="c-018-recovery"></a>

<a id="c-018--새-실험의-테스트평가-결함-복구-경계"></a>
## C-018 — 새 실험의 테스트·평가 결함 복구 경계

[D-029](shared/governance/decisions/D-029-experiment-defect-recovery.md) 채택(2026-09-09) 후 새로 승인·등록하는
실험은 [RESEARCH_DESIGN §11.1](RESEARCH_DESIGN.md#defect-recovery)을 기본으로 적용한다.
별도 전체 중단 규칙은 해당 새 실험에 사유와 범위를 명시한다. 기존 실험의 C-014~C-017 등
개별 계약·중단·무효·halt/clock은 계속 유효하며 소급 수정하지 않는다.

- 결함 발견 시 영향받는 작업과 의존 단계 진입을 보류하고 원인·공유 의존성·전파 범위를
  입증한다. 불명확한 범위는 잠재 영향 전체를 중지하고, 입증할 수 없으면 해당 비교 전체를
  중단·무효 처리한다. 새 실험의 모델 판단 오류는 [C-046](#c-046-provider-judgment)을 따른다.
  Provider 재시도는 확대하지 않는다.
- 테스트만 잘못됐고 실제 실험이 온전하면 근거를 남겨 결과를 유지할 수 있다. 평가 구현
  오류는 사전 기준대로 모든 영향 조건·응답을 동일 재평가한다. 정답·rubric 교정은 원문 근거와
  결과 확인 후 변경 사실을 공개한 별도 수정 분석이다. 실제 입력·처치·수집 오류는 영향 실행과
  의존 결과를 무효 처리하고 필요한 비교 단위를 재수집한다.
- 수정 전후 source·기준, 재현·독립 검증, 영향받는 입력·조건·결과, 재평가/재실행 단위를
  plan/experiment에 기록한다. 독립 검증은 수정 구현의 기대값 복제가 아닌 원자료·별도 계산·
  독립 사례를 사용한다. 재현 검사와 관련 회귀 통과 전 의존 작업을 재개하지 않는다.
- 대응 조건 쌍·block 및 연쇄 메모리 후속 결과를 포함한 복구 단위를 등록한다. 좋은 표본
  선택 보존·실패 분모 삭제는 금지하며 무효·미확정·미실행·복구 시도를 계속 보고한다.
- 기존 원자료·봉인·보고서·halt는 보존한다. 수정 분석/새 실행은 별도 버전·identity로 원본에
  연결한다. 새 identity는 새 예산이 아니다. 최초 시계·누적 사용량 및 전후 source/기준을
  연결하고, 평가 기준 완화로 기존 실험을 통과시킨 것으로 보고하지 않는다.
- 새 실험은 실행 전에 재수집 허용 여부·단위·한도와 승인·예산·시간·호출 상한을 등록한다.
  같은 승인·상한 안의 허용 복구는 재승인을 요구하지 않는다. 상한 소진·미승인 복구는
  추가 실행 없이 보존·미완료 보고하고 INDEX의 절차를 따른다. 시계·상한을 초기화하지 않는다.
- 이 계약은 연구 운영 절차다. 현재 API·CLI·파일 schema·실행기와 source seal 검사는 불변이며,
  halt 후 제출/정상 비교 복구 차단을 유지한다. 선택적 재수집·수정 분석 등 지원되지 않는
  경로는 [매뉴얼](../integration/pokechamp/README.md#recovery-runtime-limits)에 명시한다.
  지원 부재를 halt 삭제·기존 실행 덮어쓰기·새 디렉터리의 시계 초기화로 우회하지 않는다.
  필요한 도구 구현은 별도 bounded plan과 해당 승인 범위에서 검증한 후에만 사용한다.


<a id="c-032-io-explanation-review"></a>

<a id="c-032--기본-io-테스트의-설명-오류-기입-명시-선택"></a>
## C-032 — 기본 IO 테스트의 설명 오류 기입 명시 선택

[D-050](shared/governance/decisions/D-050-io-explanation-review-opt-in.md)과
[연구 설계 §8.1](RESEARCH_DESIGN.md#io-explanation-review)에 따라 새 기본 IO 알고리즘 테스트는
설명 오류 사후 검토·annotation 신규 기입을 기본 제외한다. 사용자가 명시적으로 요청한 경우에만
해당 범위의 검토 자료를 작성·연결한다. 단순 IO 테스트·비교·viewer 생성 요청으로 확대하지 않는다.

- 새 plan에는 기본 제외 또는 명시 요청의 근거·범위를 기록한다. 설명 오류율·검토 완전성을
  별도 요청 없는 기본 테스트의 gate/완료 조건으로 추가하지 않는다.
- 원문/reasoning 기록·표시, 기술적 입력/출력/합법 행동/계산/실제 전달/실행 실패/무결성 검증은 유지한다.
- 검토하지 않은 설명은 미평가이며 정상이나 오류0으로 재분류하지 않는다. 기존 viewer의
  `unreviewed`는 검토 기록 부재를 나타내며 새 기본 테스트의 추가 작업 지시가 아니다.
- 기존 review/annotation의 읽기·표시는 유지한다. 기존 원자료·봉인·viewer·오류 집계·실험
  완료/미완료 판정과 Blocked는 변경하지 않는다.
- C-019/C-020/C-021 등 과거 명시적 설명/의미 gate와 정책 hash·전용 실행기는 보존한다.
  이 지침을 근거로 과거 receipt를 다시 봉인하거나 gate를 통과한 것으로 만들지 않는다.
  새 일반 IO 테스트 계획은 과거 실험의 설명 검토 요건을 자동 상속하지 않으며, 사용할 실행
  경로와 승인 범위가 맞는지 등록 시 확인한다.

<a id="c-046-provider-judgment"></a>

<a id="c-046--새-실험의-공급자-판단-오류-처리-경계"></a>
## C-046 — 새 실험의 공급자 판단 오류 처리 경계

D-074 / [RD §11.2](RESEARCH_DESIGN.md#provider-judgment-errors)의 runtime 요구사항이다.
새 실행기는 판단 진단과 실행 불가능한 응답, 입력/통신/무결성 오류를 구분해야 한다.
실행 가능한 합법 선택은 보조 점수·설명 불일치에도 그대로 전송하고 원문·진단을 보존한다.
실행 불가능한 응답은 등록된 복구 범위 소진 후 해당 경기만 실패 처리하며 독립 경기의
admission이나 공유 halt를 변경하지 않는다. 기술적 공유 결함과 승인 상한은 기존 계약대로 처리한다.
경기별 실패 이유·시도/완료/실패·전송 여부와 대응 누락을 기록한다.

**지원 상태:** D-075/EP-066의 JEV `choice-action-v3`는 합법 choice를 실행하고 보조 확률/
confidence 이상을 진단으로 남긴다. 실행 불가능 응답은 경기별 실패로 격리하며 통신·입력·
전송·무결성 오류는 EX-049/050의 기술 중단 경계를 따른다. 검증 근거는 EP-066 receipt다.
C-045의 v1/v2와 EX-047/048 감사는 당시 기준을 유지한다. 기존 버전명을 재사용하거나
봉인된 실행 중 source를 바꾸지 않는다. 다른 실행기의 지원을 자동으로 주장하지 않는다.

<a id="c-047-viewer-export"></a>

<a id="c-047--정상-종료-배틀-실험의-뷰어-내보내기"></a>
## C-047 — 정상 종료 배틀 실험의 뷰어 내보내기

[D-172](shared/viewers/decisions/D-172-battle-viewer-ui-standard.md) 채택 이후 이 연구선에
신규 등록하는 배틀 실험은 아래 내보내기 요건과 함께
[공통 UI 규격](shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)을 적용한다.
규격·생성기 판본·확장 탭 고정과 변경 기록은 해당 원문,
등록·지원 확인·완료 검증은 [매뉴얼](RESEARCH_MANUAL.md#battle-viewer-workflow)을 따른다.
기존 실행·동결 protocol·과거 뷰어에는 소급하지 않으며 생성기 지원은 별도 확인한다.

D-076부터 정상 종료한 새 배틀 실험은 완료 보고 전에
`/workspace/exports/battle_viewers/<실험ID 소문자>/index.html`에 열람용 뷰어를 제공한다.
현재 EX-050에도 적용한다. 상위 `battle_viewers/index.html`에서 각 실험으로 연결한다.
D-077부터 경기별 리플레이와 입력·응답을 함께 볼 수 있는 화면을 포함한다. 저장된 배틀
protocol로 생성하고 경기 구분·턴·승패를 원자료와 대조한다. 재생 자료가 없으면 그 한계를 명시한다.
필요한 로컬 자산은 실험 폴더 안에 두고 상대경로를 사용해 폴더 이동 후에도 열리게 한다.
외부 애니메이션 자산이 필요한 경우 명시하되 입력·응답·선택/결과는 오프라인에서 열람할 수 있어야 한다.
출처 실험·원본 위치·원본/복사본 해시·정상완료 분모를 함께 기록한다.
봉인된 원본을 이동·수정하거나 내보내기 복사본으로 대체하지 않는다. 기존 경로가 있으면
내용을 확인하고 다른 실험/버전을 덮어쓰지 않는다. 원본 봉인·링크·오프라인 열람을 확인하고
최종 보고에 내보내기 링크를 제공한다. 이는 완료 절차이며 모든 실행기의 자동 export 구현을 뜻하지 않는다.

D-078의 실험자용 화면은 입력 요청·응답·실제 선택을 우선 배치하고 관측/전송 기술 기록은
별도 영역에 둔다. JSON은 들여쓰기·구문 강조 및 복사/다운로드를 제공한다. 요청을 원자료로
복원하면 출처와 한계를 명시하며 필드값을 바꾸지 않는다. 자동 선택의 미호출을 실제 요청이나
모델 응답처럼 표시하지 않는다. 현재 JEV 내보내기는 jev_viewer.py/jev-researcher-v2가 담당한다.
EP-072의 뷰어 표시에서 좌우 방향키는 이전/다음 결정을 탐색하며 폼·탭 조작은 유지한다.
상대 HP 요약은 공개 비율(%)·미확인을 구분하고 자기 HP와 원래 요청/응답 JSON 값은 보존한다.
[D-101](shared/viewers/decisions/D-101-viewer-action-names.md)의 현재/향후 Qwen·JEV 표시에서는 결정 당시
후보 설명·move_ref/현재 기술 슬롯으로 실제 기술명·교체/선봉 대상·테라 여부를 표시한다.
정보 부재는 미확인이며 원 ID·명령·입력/응답·q는 보존한다. 표시 갱신은 이전 봉인 버전을 보존하고 provenance로 연결한다.

## 주제별 원문과 이전 앵커

<a id="계약-contracts"></a>
- [분리 전 안내](shared/governance/CONTRACTS.md#계약-contracts)
<a id="c-073-planner-viewer"></a><a id="c-073--향후-glmjev-통합-뷰어"></a>
- [C-073 — 향후 GLM·JEV 통합 뷰어](shared/viewers/CONTRACTS.md#c-073-planner-viewer)
<a id="c-072-candidate-display-names"></a><a id="c-072--후보-display_name과-실행-식별자"></a>
- [C-072 — 후보 display_name과 실행 식별자](research/input-and-memory/CONTRACTS.md#c-072-candidate-display-names)
<a id="c-071-planner-role-guide"></a><a id="c-071--planner-역할자원-guide의-선택과-동결"></a>
- [C-071 — Planner 역할·자원 guide의 선택과 동결](research/planner-executor/CONTRACTS.md#c-071-planner-role-guide)
<a id="c-070-jev-planner"></a><a id="c-070--전략-plannerjev-실행-경계"></a>
- [C-070 — 전략 planner–JEV 실행 경계](research/planner-executor/CONTRACTS.md#c-070-jev-planner)
<a id="c-069-minicpm5-2b-jev"></a><a id="c-069--minicpm5-2b-jev-손실-없는-choice-평가"></a>
- [C-069 — MiniCPM5-2B-Jev 손실 없는 Choice 평가](research/model-evaluation/CONTRACTS.md#c-069-minicpm5-2b-jev)
<a id="c-068-jev-no-damage"></a><a id="c-068--jev-피해-예측-제거-입력과-단독-평가"></a>
- [C-068 — JEV 피해 예측 제거 입력과 단독 평가](research/input-and-memory/CONTRACTS.md#c-068-jev-no-damage)
<a id="c-067-jev-public-memory-v6"></a><a id="c-067--상대-공개-정보-v6와-턴-로그"></a>
- [C-067 — 상대 공개 정보 v6와 턴 로그](research/input-and-memory/CONTRACTS.md#c-067-jev-public-memory-v6)
<a id="c-066-jev9b-single-choice"></a><a id="c-066--jev-9b-단일-choice-실행-경계"></a>
- [C-066 — JEV-9B 단일 Choice 실행 경계](research/model-evaluation/CONTRACTS.md#c-066-jev9b-single-choice)
<a id="c-065-quyet-two-stage"></a><a id="c-065--quyet-2단계-choice-실행-경계"></a>
- [C-065 — Quyet 2단계 Choice 실행 경계](research/model-evaluation/CONTRACTS.md#c-065-quyet-two-stage)
<a id="c-064-jev27b-continuation"></a><a id="c-064--ex-083-4gpu-계승-실행-경계"></a>
- [C-064 — EX-083 4GPU 계승 실행 경계](research/model-evaluation/CONTRACTS.md#c-064-jev27b-continuation)
<a id="c-063-jev27b-local"></a><a id="c-063--jev-27b-로컬-choice-재현-경계"></a>
- [C-063 — JEV-27B 로컬 Choice 재현 경계](research/model-evaluation/CONTRACTS.md#c-063-jev27b-local)
<a id="c-061-qwen-matrix"></a><a id="c-061--qwen-고정-대진-행렬-탐색-경계"></a>
- [C-061 — Qwen 고정 대진 행렬 탐색 경계](research/fixed-matchup-learning/CONTRACTS.md#c-061-qwen-matrix)
<a id="c-060-fixed-matchup"></a><a id="c-060--고정-대진-공개-상태-탐색-경계"></a>
- [C-060 — 고정 대진 공개 상태 탐색 경계](research/fixed-matchup-learning/CONTRACTS.md#c-060-fixed-matchup)
<a id="c-059-abyssal-rl-next"></a><a id="c-059--82라운드-계승단일-추가-주기"></a>
- [C-059 — 82라운드 계승·단일 추가 주기](research/policy-learning/CONTRACTS.md#c-059-abyssal-rl-next)
<a id="c-058-abyssal-rl-continue"></a><a id="c-058--마지막-학습-상태-계승별도-실험과-단계-알람"></a>
- [C-058 — 마지막 학습 상태 계승·별도 실험과 단계 알람](research/policy-learning/CONTRACTS.md#c-058-abyssal-rl-continue)
<a id="c-057-abyssal-rl"></a><a id="c-057--abyssal-전용-동기-4gpu-정책-학습"></a>
- [C-057 — Abyssal 전용 동기 4GPU 정책 학습](research/policy-learning/CONTRACTS.md#c-057-abyssal-rl)
<a id="c-056-selfplay"></a><a id="c-056--자기대국-정책선택-행동-승무패-확률"></a>
- [C-056 — 자기대국 정책·선택 행동 승무패 확률](research/policy-learning/CONTRACTS.md#c-056-selfplay)
<a id="c-055-imitation"></a><a id="c-055--리플레이-모방-학습-입력choice-정책"></a>
- [C-055 — 리플레이 모방 학습 입력·Choice 정책](research/policy-learning/CONTRACTS.md#c-055-imitation)
<a id="c-001--상속된-agenticsts-context와-layer-write-authority"></a>
- [C-001 — 상속된 AgenticSTS context와 layer write authority](research/l1-l5-port/CONTRACTS.md#c-001--상속된-agenticsts-context와-layer-write-authority)
<a id="c-002--game-mod-transport"></a>
- [C-002 — Game-mod transport](research/l1-l5-port/CONTRACTS.md#c-002--game-mod-transport)
<a id="c-003--state-및-index-표현"></a>
- [C-003 — State 및 index 표현](research/l1-l5-port/CONTRACTS.md#c-003--state-및-index-표현)
<a id="c-004--llm-decision-boundary"></a>
- [C-004 — LLM decision boundary](research/l1-l5-port/CONTRACTS.md#c-004--llm-decision-boundary)
<a id="c-005--persistent-state-및-provenance"></a>
- [C-005 — Persistent state 및 provenance](research/l1-l5-port/CONTRACTS.md#c-005--persistent-state-및-provenance)
<a id="c-008--pokéchamp-qualification-environment"></a>
- [C-008 — PokéChamp qualification environment](shared/execution/CONTRACTS.md#c-008--pokéchamp-qualification-environment)
<a id="c-009--pokéchamp-research-battle-observability"></a>
- [C-009 — PokéChamp research battle observability](shared/viewers/CONTRACTS.md#c-009--pokéchamp-research-battle-observability)
<a id="c-010--benchmark-pilot-control-record"></a>
- [C-010 — Benchmark pilot control record](shared/execution/CONTRACTS.md#c-010--benchmark-pilot-control-record)
<a id="c-011--benchmark-병렬-실행과-요청-admission"></a>
- [C-011 — Benchmark 병렬 실행과 요청 admission](shared/execution/CONTRACTS.md#c-011--benchmark-병렬-실행과-요청-admission)
<a id="c-012--benchmark-식별-및-요청별-후보"></a>
- [C-012 — Benchmark 식별 및 요청별 후보](shared/execution/CONTRACTS.md#c-012--benchmark-식별-및-요청별-후보)
<a id="c-013--원본-행동-생성-별도-benchmark-조건"></a>
- [C-013 — 원본 행동 생성 별도 benchmark 조건](shared/execution/CONTRACTS.md#c-013--원본-행동-생성-별도-benchmark-조건)
<a id="c-014--개선-io-조건의-입력출력실행-경계"></a>
- [C-014 — 개선 IO 조건의 입력·출력·실행 경계](research/input-and-memory/CONTRACTS.md#c-014--개선-io-조건의-입력출력실행-경계)
<a id="c-015--독립-요약-harness-진단"></a>
- [C-015 — 독립 요약 harness 진단](research/input-and-memory/CONTRACTS.md#c-015--독립-요약-harness-진단)
<a id="c-016--상태-의미와-요약-thinking-진단"></a>
- [C-016 — 상태 의미와 요약 thinking 진단](research/input-and-memory/CONTRACTS.md#c-016--상태-의미와-요약-thinking-진단)
<a id="c-017--고정-이전-메모리-lowmax-요약-진단"></a>
- [C-017 — 고정 이전 메모리 low/max 요약 진단](research/input-and-memory/CONTRACTS.md#c-017--고정-이전-메모리-lowmax-요약-진단)
<a id="c-019--요약-없는-ab-profile-및-복구-실행-경계"></a>
- [C-019 — 요약 없는 A/B profile 및 복구 실행 경계](research/input-and-memory/CONTRACTS.md#c-019--요약-없는-ab-profile-및-복구-실행-경계)
<a id="c-020--명시적-battle-guide-live-v1-실험-정책"></a>
- [C-020 — 명시적 battle-guide-live-v1 실험 정책](research/input-and-memory/CONTRACTS.md#c-020--명시적-battle-guide-live-v1-실험-정책)
<a id="c-021--battle-guide-direct32-v1-실행출력-복구-경계"></a>
- [C-021 — battle-guide-direct32-v1 실행·출력 복구 경계](research/input-and-memory/CONTRACTS.md#c-021--battle-guide-direct32-v1-실행출력-복구-경계)
<a id="c-022--battle-guide-calcfix32-v1-계산기-교정-및-실행-경계"></a>
- [C-022 — battle-guide-calcfix32-v1 계산기 교정 및 실행 경계](research/input-and-memory/CONTRACTS.md#c-022--battle-guide-calcfix32-v1-계산기-교정-및-실행-경계)
<a id="c-023--계산기-입력-로컬-조사수정-경계"></a>
- [C-023 — 계산기 입력 로컬 조사·수정 경계](research/input-and-memory/CONTRACTS.md#c-023--계산기-입력-로컬-조사수정-경계)
<a id="c-024--battle-guide-inputfix32-v1-교정-입력-실행-경계"></a>
- [C-024 — battle-guide-inputfix32-v1 교정 입력 실행 경계](research/input-and-memory/CONTRACTS.md#c-024--battle-guide-inputfix32-v1-교정-입력-실행-경계)
<a id="c-025--battle-guide-movefix32-v1-수정-완료본-실행-경계"></a>
- [C-025 — battle-guide-movefix32-v1 수정 완료본 실행 경계](research/input-and-memory/CONTRACTS.md#c-025--battle-guide-movefix32-v1-수정-완료본-실행-경계)
<a id="c-026--외부-환경-장애-후-동일-조건-새-반복"></a>
- [C-026 — 외부 환경 장애 후 동일 조건 새 반복](research/input-and-memory/CONTRACTS.md#c-026--외부-환경-장애-후-동일-조건-새-반복)
<a id="d-041-원본-a64-진단-실행"></a>
- [D-041 원본 A64 진단 실행](research/input-and-memory/CONTRACTS.md#d-041-원본-a64-진단-실행)
<a id="c-027--ab-head-to-head32-v1-실행-경계"></a>
- [C-027 — ab-head-to-head32-v1 실행 경계](research/input-and-memory/CONTRACTS.md#c-027--ab-head-to-head32-v1-실행-경계)
<a id="c-028--ab-head-to-head32-protectfix-v1-실행-경계"></a>
- [C-028 — ab-head-to-head32-protectfix-v1 실행 경계](research/input-and-memory/CONTRACTS.md#c-028--ab-head-to-head32-protectfix-v1-실행-경계)
<a id="c-029--새-cloud-기본-동시성8"></a>
- [C-029 — 새 Cloud 기본 동시성8](shared/execution/CONTRACTS.md#c-029--새-cloud-기본-동시성8)
<a id="c-030--b-오프라인-전달-표현"></a>
- [C-030 — B 오프라인 전달 표현](research/input-and-memory/CONTRACTS.md#c-030--b-오프라인-전달-표현)
<a id="c-031--ex-038-b2-실제-전달-경계"></a>
- [C-031 — EX-038 B2 실제 전달 경계](research/input-and-memory/CONTRACTS.md#c-031--ex-038-b2-실제-전달-경계)
<a id="c-033-llm-lead"></a><a id="c-033--b2-선봉-선택의-별도-경계"></a>
- [C-033 — B2 선봉 선택의 별도 경계](research/lead-policy/CONTRACTS.md#c-033-llm-lead)
<a id="c-034-provider"></a><a id="c-034--새-배틀-공급자-설정과-호환"></a>
- [C-034 — 새 배틀 공급자 설정과 호환](shared/execution/CONTRACTS.md#c-034-provider)
<a id="c-035-ex040"></a><a id="c-035--ex-040-실행-식별자와-첫429-중단"></a>
- [C-035 — EX-040 실행 식별자와 첫429 중단](research/lead-policy/CONTRACTS.md#c-035-ex040)
<a id="c-036-zai4"></a><a id="c-036--zai-기본4-및-ex-041-식별자"></a>
- [C-036 — Z.ai 기본4 및 EX-041 식별자](research/lead-policy/CONTRACTS.md#c-036-zai4)
<a id="c-037-effect-reference"></a><a id="c-037--새-배틀선봉-효과-사전-전송"></a>
- [C-037 — 새 배틀·선봉 효과 사전 전송](research/input-and-memory/CONTRACTS.md#c-037-effect-reference)
<a id="c-038-transport-retry"></a><a id="c-038--새-전송-정책"></a>
- [C-038 — 새 전송 정책](shared/execution/CONTRACTS.md#c-038-transport-retry)
<a id="c-039-distributed-lead"></a><a id="c-039--ex-042-분산-실행-경계"></a>
- [C-039 — EX-042 분산 실행 경계](research/lead-policy/CONTRACTS.md#c-039-distributed-lead)
<a id="c-040-lead-components"></a><a id="c-040--선봉-전략규칙-독립-구성요소"></a>
- [C-040 — 선봉 전략·규칙 독립 구성요소](research/lead-policy/CONTRACTS.md#c-040-lead-components)
<a id="c-041--ex-043-교정-선봉-분산-실행"></a>
- [C-041 — EX-043 교정 선봉 분산 실행](research/lead-policy/CONTRACTS.md#c-041--ex-043-교정-선봉-분산-실행)
<a id="c-042--ex-044-직접-진입"></a>
- [C-042 — EX-044 직접 진입](research/lead-policy/CONTRACTS.md#c-042--ex-044-직접-진입)
<a id="c-043-official-observation"></a><a id="c-043--새-bb2-공식-관측-경계"></a>
- [C-043 — 새 B/B2 공식 관측 경계](research/input-and-memory/CONTRACTS.md#c-043-official-observation)
<a id="c-044-official-lead"></a><a id="c-044--ex-045-공식-관측-분산-실행"></a>
- [C-044 — EX-045 공식 관측 분산 실행](research/lead-policy/CONTRACTS.md#c-044-official-lead)
<a id="c-044-jev"></a><a id="c-044--독립-jev-클라이언트"></a>
- [C-044 — 독립 JEV 클라이언트](shared/execution/CONTRACTS.md#c-044-jev)
<a id="c-045-jev-battle"></a><a id="c-045--jev-choice-배틀-프로필"></a>
- [C-045 — JEV Choice 배틀 프로필](research/model-evaluation/CONTRACTS.md#c-045-jev-battle)
<a id="d-081--ex-052-jev-일정-실행-확장"></a>
- [D-081 / EX-052 JEV 일정 실행 확장](research/model-evaluation/CONTRACTS.md#d-081--ex-052-jev-일정-실행-확장)
<a id="d-083--ex-053-v3-일정-실행"></a>
- [D-083 / EX-053 v3 일정 실행](research/input-and-memory/CONTRACTS.md#d-083--ex-053-v3-일정-실행)
<a id="d-084--새-jev-provider-재시도3회"></a>
- [D-084 — 새 JEV provider 재시도3회](shared/execution/CONTRACTS.md#d-084--새-jev-provider-재시도3회)
<a id="d-085-ex-054-실행-경계"></a>
- [D-085 EX-054 실행 경계](research/input-and-memory/CONTRACTS.md#d-085-ex-054-실행-경계)
<a id="d-087--새-jev-재시도-대기-확대"></a>
- [D-087 — 새 JEV 재시도 대기 확대](shared/execution/CONTRACTS.md#d-087--새-jev-재시도-대기-확대)
<a id="d-088-ex-056-직접-본실험"></a>
- [D-088 EX-056 직접 본실험](research/input-and-memory/CONTRACTS.md#d-088-ex-056-직접-본실험)
<a id="d-089-ex-057-모델-고정-본실험"></a>
- [D-089 EX-057 모델 고정 본실험](research/input-and-memory/CONTRACTS.md#d-089-ex-057-모델-고정-본실험)
<a id="d-092--별도-jev-오프라인-입력"></a>
- [D-092 — 별도 JEV 오프라인 입력](research/input-and-memory/CONTRACTS.md#d-092--별도-jev-오프라인-입력)
<a id="d-094--ex-058-개선-입력-실행-경계"></a>
- [D-094 — EX-058 개선 입력 실행 경계](research/input-and-memory/CONTRACTS.md#d-094--ex-058-개선-입력-실행-경계)
<a id="d-095--ex-059-자기-벤치-축약-실행-경계"></a>
- [D-095 — EX-059 자기 벤치 축약 실행 경계](research/input-and-memory/CONTRACTS.md#d-095--ex-059-자기-벤치-축약-실행-경계)
<a id="c-048--ex-060-독립-분기-실행-경계"></a>
- [C-048 — EX-060 독립 분기 실행 경계](research/action-value/CONTRACTS.md#c-048--ex-060-독립-분기-실행-경계)
<a id="c-048-action-value-training"></a><a id="c-048--포켓몬-후보별-soft-target-학습-경계"></a>
- [C-048 — 포켓몬 후보별 soft target 학습 경계](research/action-value/CONTRACTS.md#c-048-action-value-training)
<a id="c-049-qwen-local"></a><a id="c-049--qwen-로컬-행동가치-서빙"></a>
- [C-049 — Qwen 로컬 행동가치 서빙](research/action-value/CONTRACTS.md#c-049-qwen-local)
<a id="c-050-qwen-candidate-state"></a><a id="c-050--qwen-후보-상태-입력과-개발-진단"></a>
- [C-050 — Qwen 후보 상태 입력과 개발 진단](research/action-value/CONTRACTS.md#c-050-qwen-candidate-state)
<a id="c-051-joint-q"></a><a id="c-051--ex-065-공동-q-데이터"></a>
- [C-051 — EX-065 공동 q 데이터](research/action-value/CONTRACTS.md#c-051-joint-q)
<a id="c-054-kev-battle"></a><a id="c-054--kev-pokechamp-r1-배틀-연결"></a>
- [C-054 — Kev pokechamp r1 배틀 연결](research/model-evaluation/CONTRACTS.md#c-054-kev-battle)
<a id="c-052-joint-q-training"></a><a id="c-052--base-공동-q-모델학습-경계"></a>
- [C-052 — Base 공동 q 모델·학습 경계](research/action-value/CONTRACTS.md#c-052-joint-q-training)
<a id="c-053-abyssal-tera"></a><a id="c-053--abyssal-tera-정책보완-수집"></a>
- [C-053 — Abyssal Tera 정책·보완 수집](research/action-value/CONTRACTS.md#c-053-abyssal-tera)
<a id="c-062-joint-q-battle"></a><a id="c-062--ex066-공동-q-체크포인트-실제-배틀-경계"></a>
- [C-062 — EX066 공동 q 체크포인트 실제 배틀 경계](research/action-value/CONTRACTS.md#c-062-joint-q-battle)
<a id="c-074-ruleqa"></a><a id="c-074--데이터-전용-규칙-qa-state"></a>
- [C-074 — 데이터 전용 규칙 Q&A State](research/rule-learning/CONTRACTS.md#c-074-ruleqa)
<a id="c-075--strategist-텍스트-행동-경계"></a>
- [C-075 — Strategist 텍스트 행동 경계](research/model-evaluation/CONTRACTS.md#c-075--strategist-텍스트-행동-경계)
<a id="c-076--규칙-qa-학습-경계"></a>
- [C-076 — 규칙 Q&A 학습 경계](research/rule-learning/CONTRACTS.md#c-076--규칙-qa-학습-경계)
<a id="c-077--학습-tacit-배틀-경계"></a>
- [C-077 — 학습 Tacit 배틀 경계](research/rule-learning/CONTRACTS.md#c-077--학습-tacit-배틀-경계)
<a id="c-078-openai-decisions"></a><a id="c-078--독립-openai-decisions-api-호출"></a>
- [C-078 — 독립 OpenAI Decisions API 호출](shared/execution/CONTRACTS.md#c-078-openai-decisions)
<a id="c-079-openai-decisions-battle"></a><a id="c-079--openai-decisions-v6-배틀-경계"></a>
- [C-079 — OpenAI Decisions v6 배틀 경계](research/model-evaluation/CONTRACTS.md#c-079-openai-decisions-battle)
<a id="c-080-openai-decisions-retry"></a><a id="c-080--openai-통신-지속-재시도"></a>
- [C-080 — OpenAI 통신 지속 재시도](research/model-evaluation/CONTRACTS.md#c-080-openai-decisions-retry)
<a id="c-080--jevk5-외부-vllm-선택지-판독"></a>
- [C-080 — JevK5 외부 vLLM 선택지 판독](research/model-evaluation/CONTRACTS.md#c-080--jevk5-외부-vllm-선택지-판독)
<a id="c-081-candidate-matchup"></a><a id="c-081--후보별-현재-대면-요약"></a>
- [C-081 — 후보별 현재 대면 요약](research/input-and-memory/CONTRACTS.md#c-081-candidate-matchup)
<a id="c-082--요약-프로필-배틀감사-연결"></a>
- [C-082 — 요약 프로필 배틀·감사 연결](research/input-and-memory/CONTRACTS.md#c-082--요약-프로필-배틀감사-연결)
<a id="c-083--jevk5-규칙-선택형-학습"></a>
- [C-083 — JevK5 규칙 선택형 학습](research/rule-learning/CONTRACTS.md#c-083--jevk5-규칙-선택형-학습)
