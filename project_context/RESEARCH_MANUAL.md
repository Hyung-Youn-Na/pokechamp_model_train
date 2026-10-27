# 모델 학습 연구 매뉴얼

이 매뉴얼은 `research/model-training`에서 모델 학습·정책 개선·독립 평가를 준비하는
작업 순서를 안내한다. 현재 연구 주제·조건은 [CHARTER](CHARTER.md)와
[연구 설계](RESEARCH_DESIGN.md#current-objective), 진행 중인 작업은
[STATUS](STATUS.md#active-work)에서 확인한다. 매뉴얼의 명령 예시는 새 실험 실행 지시가 아니다.
승인·중단·완료 기준의 원문은 [INDEX](INDEX.md#workflow)와 개별 EP/EX에 유지한다.

<a id="start"></a>

## 1. 작업 위치 확인

현재 연구 주기의 주 개발 checkout과 기존 실행 환경은 `/workspace`다.
먼저 실제 checkout·브랜치·변경분·submodule pin을 확인한다.

```bash
cd /workspace
GIT_OPTIONAL_LOCKS=0 git rev-parse --show-toplevel
GIT_OPTIONAL_LOCKS=0 git branch --show-current
GIT_OPTIONAL_LOCKS=0 git status --short --branch
GIT_OPTIONAL_LOCKS=0 git submodule status
```

기준 연구선은 `research/model-training`이다. 작업 브랜치가 따로 있으면 그 이름과 기준 연구선을
함께 기록한다. 현재 학습 원격은 `model-train`이며, 원격 역할과 L1–L5 checkout은
[Git·작업 위치 안내](RESEARCH_WORKFLOW.md#remotes)를 따른다.
Git clone에는 코드·문서·작은 고정 입력이 포함된다. 외부 모델·자료·환경은
[보존/복원 안내](RESEARCH_WORKFLOW.md#preservation)에서 연결하므로 다른 머신의 clone을
현재 연구 주기의 실행 환경과 같은 상태로 간주하지 않는다.

## 2. 연구 질문과 작업 등록

1. [현재 목표](CHARTER.md)와 [학습 설계](research/policy-learning/DESIGN.md#pokemon-training-objective),
   관련 EX의 최종 결과·한계를 읽어 이번 질문이 무엇인지 정한다.
2. [계획 색인](catalog/plans.md)의 현재 실행 작업과 범위가 겹치는 중단 보존 plan을 확인한다.
   기존 사용자 승인과 동일 범위이면 [INDEX 절차](INDEX.md#workflow)에 따라 재사용한다.
3. [EP 템플릿](templates/plan.md)으로 작업 범위·변경 대상·검증·완료 기준을 기록한다.
   지속되는 설계·계약 변경이 있을 때는 [Decision 템플릿](templates/decision.md)을 사용한다.
4. 실제 실험은 [EX 템플릿](templates/experiment.md)에 질문·모델/revision·데이터/분할·처치·
   기준선·독립 평가·자원/예산·중단/복구 조건과 출력 위치를 기록한다. 세부 원문을 EP에 중복하지 않는다.
5. 등록된 조건과 해당 실행기의 실제 동작이 맞는지 확인한 뒤 승인된 단계를 수행한다.

새 기록에는 연구선, 실제 branch/commit·미커밋 변경, checkout, interpreter/launcher,
새 출력 경로와 원자료/보존본을 구분해 적는다. 기존 ID는 재사용하지 않는다. 주제 폴더의 원문과 catalog/records.json을 등록하고
`scripts/context-catalog build` 및 `check`를 실행한다. 상태 변경으로 경로를 이동하지 않는다.
다른 연구선의 자료는 ID와 함께 branch·commit·EX/manifest를 인용해 출처를 식별한다.
이 문서는 기존 연구 질문·평가 기준·예산을 새로 정하지 않는다.

## 3. 환경·실행기·명령 경계

[실행 환경과 출력·명령 경계](shared/execution/ENVIRONMENT.md)를 확인한다.
확인용 명령 이름만으로 부작용을 판단하지 않으며 해당 wrapper의 인자 처리부터 읽는다.

<a id="battle-viewer-workflow"></a>

## 4. 배틀 viewer 규격·지원 확인·변경 기록

새 배틀 실험은 [공통 UI 규격](shared/viewers/CONTRACTS.md#battle-viewer-ui-v1)과
[판본 규칙](shared/viewers/CONTRACTS.md#viewer-versioning)을 따른다.
기본 화면·탭 순서·탐색·리플레이 동작의 규범 원문은 위 계약에만 둔다.
[기준 화면](exec-plans/evidence/ep177/viewer.png)은 배치 참조이며 전체 규격의 구현 인증은 아니다.
현재 생성기의 차이는 [지원 현황](shared/viewers/ARCHITECTURE.md#viewer-ui-support),
변경 경위는 [변경일지](shared/viewers/CHANGELOG.md)에서 확인한다.

1. **등록:** EX 템플릿에 적용 UI 규격·생성기 식별자/판본·소스 참조·확장 탭과 순서·출력
   위치를 기록한다. 소스 참조는 미커밋 변경도 식별할 수 있어야 한다. EP에는 해당 EX와
   지원 확인·검증 근거를 연결한다. 비배틀 작업은 해당 없음으로 적는다.
2. **실행 전:** 선언한 생성기의 지원을 규격과 대조한다. 미지원 기능은 해당 실험의
   선행 구현 EP에 연결하고 검증 후 실행한다. 임의의 별도 UI로 대체하거나 문서 등록을
   지원 완료로 간주하지 않는다. 공통 렌더러 구현은 별도 작업이며 자동 실행하지 않는다.
3. **내보내기·완료:** 고정한 규격/생성기로 내보내고 아래 확인표와 C-047·개별 EX의
   필수 검증을 수행한다. 확인 결과·미지원/미실행 항목·판본·변경일지 링크를 EP의
   완료 근거에 남기고 최종 보고에 열람 링크를 제공한다. 미충족 기준은 완료로 표시하지 않는다.
4. **변경:** 구조·동작 변경은 새 Decision/규격 버전, 허용된 확장·표시 교정은 렌더러
   판본과 변경일지로 추적한다. 상세 이유·적용 EX·검증 근거를 연결하고 기존 판본을 보존한다.
   실행 중 판본을 조용히 교체하지 않으며 승인 판단은 INDEX를 따른다.

### 뷰어 확인표

실행 전에는 선택한 생성기의 지원 근거를, 완료 시에는 실제 내보내기와 대응 증거를 확인한다.
같은 소스·설정의 검증을 참조할 때는 적용 범위와 차이를 적는다. 실제 자료에 없는 사례는
합성 검증으로 구분하며 실험 성적에 포함하지 않는다.

| 확인 영역 | 확인할 사례·결과 |
|---|---|
| 구조·탐색 | 고정 기본 탭·첫 화면·선언한 확장 순서, 목록/경기 복귀, 결정·턴 선택과 키보드/폼 조작 |
| 결정 상태 | 선봉·일반 행동·강제 교체·같은 턴 복수 결정·자동 선택·실패·결정 없는 턴, 미호출/자료 없음 구별 |
| 리플레이 | 선택 턴 시작으로 일시정지·이동, 같은 턴 결정 위치 일치, 탭/영상 조작의 선택 독립성 |
| 연속 선택 | 로딩 전·빠른 연속 선택의 마지막 선택 유지, 다른 경기/actor/결정 자료 혼입 없음 |
| 원문·경계 | 요청/응답/선택 원값, 복원 출처·공개 정보/cutoff, 전체 턴 로그의 결정 이후 결과 표시, 복사·다운로드 |
| 이동·오프라인 | 폴더 이동 후 file://, 외부 자산 차단 시 공개 로그와 입력·응답 열람, 외부 애니메이션 의존 안내 |
| 반응형 | 데스크톱의 동시 표시와 고정 리플레이, 좁은 화면의 상단 리플레이·탐색·원문 접근 |

이 표는 UI 확인 절차이며 기존 EX의 원자료 무결성·전수 대조·봉인 검증을 대체하거나
표본 검사로 완화하지 않는다. 적용 이전의 실행·동결 실험·Blocked/Paused에는 소급하지 않는다.

## 6. 자료·평가·종결

기존 실행의 보고서 → manifest → 원자료 순으로 읽는다. `.pokechamp-data/experiments`,
`export/teams`, `exports/pokemon-role-data`, replay corpus에는 학습 입력뿐 아니라 평가/참조
자료도 있으므로 새 데이터 포함 범위는 [학습 설계](research/policy-learning/DESIGN.md#pokemon-training-objective)와
해당 EX의 분할·오염 통제에 맞춘다. 학습 손실이나 같은 학습 자료의 재평가만으로 독립 성능
개선을 주장하지 않는다.

<a id="no-offline-battle-gate"></a>

오프라인 test 평가(NLL·일치율·지식 정답률 등)의 결과로 배틀 평가를 생략하거나 미루는
사전 진행 조건(gate)을 두지 않는다. 학습 실험에 대응하는 배틀 평가가 있으면 오프라인 판정과
관계없이 실행하고, 두 판정은 각각 보고한다. 오프라인 평가는 학습 결함 확인(재로딩·parity·
자료 무결성)과 보고 지표로만 쓴다. 근거는 [D-191](research/policy-learning/decisions/D-191-no-offline-battle-gate.md)이다.
이미 동결된 실험의 판정 원문은 고치지 않는다.

결과는 해당 EX에 실제 분모·실패/중단·불확실성과 함께 기록하고 EP의 완료 기준을 대조한다.
보고·봉인·소유 자원 정리와 [C-047](CONTRACTS.md#c-047-viewer-export)의 배틀 viewer 요건은
해당 실행에 적용한다. 새 run 출력 경로와 `/workspace/exports/battle_viewers/`는 역할이 다르다.
기존 snapshot·봉인·Blocked/Paused를 새 작업 결과로 덮어쓰지 않는다.

## 6.1 자료 안내

[보관 데이터셋·규칙 자료·모델 안내](shared/datasets/MANUAL.md)에서 출처·구조·manifest를 찾는다.

## 7. 다른 연구선과 보존본

L1–L5 이식의 source·설계는 별도 checkout의 매뉴얼을 따른다. 그 worktree의 evidence·exports와
일부 `.tools/.../docs`는 보존본으로 연결된 읽기용 링크다. 연구선 간 코드를 옮길 때는 변경 범위와
출처 commit을 확인하고 필요한 변경을 명시적으로 반영한다. 작업 전체나 legacy TODO를 자동 계승하지 않는다.

복원 절차와 EP-135 기준 기록은 [보존 안내](RESEARCH_WORKFLOW.md#preservation) 및
[복원 절차](RESEARCH_WORKFLOW.md#restore)를 따른다. `snapshot/pre-split`과 당시 bundle/receipt는
분리 완료 시점의 기록이며 이후 README·매뉴얼 커밋을 가리키도록 갱신하지 않는다.

현재 `integration/qwen_mcts/prepare.py`의 EP132 active/completed 경로 불일치는
[알려진 한계](RESEARCH_WORKFLOW.md#limitations)에 남아 있다. 준비 명령을 확인용으로 실행하거나
문서 경로 오류를 이유로 봉인 검사를 우회하지 않는다.

## 이전 세부 안내 위치

<a id="environment"></a>

[environment](shared/execution/ENVIRONMENT.md#environment)

<a id="outputs"></a>

[outputs](shared/execution/ENVIRONMENT.md#outputs)

<a id="command-boundaries"></a>

[command-boundaries](shared/execution/ENVIRONMENT.md#command-boundaries)

<a id="archived-datasets"></a>

[archived-datasets](shared/datasets/MANUAL.md#archived-datasets)

<a id="pretrain-dataset"></a>

[pretrain-dataset](shared/datasets/MANUAL.md#pretrain-dataset)

<a id="pokemon-training-dataset"></a>

[pokemon-training-dataset](shared/datasets/MANUAL.md#pokemon-training-dataset)

<a id="generated-ruleqa"></a>

[generated-ruleqa](shared/datasets/MANUAL.md#generated-ruleqa)

<a id="archived-strategist-model"></a>

[archived-strategist-model](shared/datasets/MANUAL.md#archived-strategist-model)
