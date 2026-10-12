# 프로젝트 헌장 — 모델 학습 연구선 (Project Charter)

이 브랜치 `research/model-training`의 최상위 목표는 **포켓몬 배틀 전용 모델의 학습·정책 개선과
독립 평가**다. [D-131](decisions/D-131-research-branch-preservation.md)의 사용자 지시에 따라 `/workspace`를 주 개발 checkout과 기존 실행
환경으로 유지한다. L1–L5 구조 이식 연구는 별도 `research/l1-l5-port`에서 보존·후속 설계한다.
공통 기준선·외부 자산·출력·복원 절차는 [연구선 작업·출력·복원 안내](RESEARCH_WORKFLOW.md)를 따른다.

**Authority:** 이 브랜치의 프로젝트 목적과 기본 invariant에 대한 최상위 원문이다.
연구선 분리는 기존 ADR·EX·동결 protocol·봉인·Blocked/Paused 판정을 바꾸지 않는다.
분리 기반 구성의 범위·검증은 [EP-135](exec-plans/active/EP-135-research-branch-preservation.md)에서 관리한다. 실행 중인 학습·평가 실험은 없다.

## 프로젝트 목표 (Project Goal)

`pokechamp`의 관측과 합법 행동 후보에 맞는 모델을 학습하고 정책을 개선하며,
학습·모델 선택과 분리한 평가로 행동 선택 및 배틀 성능의 변화·불확실성을 판단한다.
학습 손실 감소나 초기모델 상대 우세만으로 독립 배틀 성능 개선을 주장하지 않는다.
구체적 학습 방법·처치·평가 기준·분모·예산·중단 조건은
[`RESEARCH_DESIGN.md`](RESEARCH_DESIGN.md), 관련 Decision과 개별 EX에서 정한다.

LAYA-RLCD·EVE-RLCD·RLCD-Lite의 기존 환경과 Qwen·Kev·고정 대진 탐색 구현은 활용 가능한
기반이다. 환경 준비나 기존 구현의 존재가 새 실행 또는 모든 환경의 동시 학습을 승인하지 않는다.
프롬프트·JEV·AgenticSTS 구성과 과거 실험 자산을 공통 기준선에 유지한다.
기존 AgenticSTS의 연구 목표·benchmark·metric·결과는 자동 승계하지 않는다.

<a id="immediate-objective"></a>

### 당면 목표

이번 분리 단계의 범위는 Git 기준선·공통 보존 태그·브랜치별 목적 문서·worktree·대형 자산
복사와 검증이며 진행·완료 근거는 [EP-135](exec-plans/active/EP-135-research-branch-preservation.md)에 연결한다. 새 학습·GPU 실행·외부 모델 호출·
실제 배틀은 분리 범위에 포함하지 않는다.
기존 [D-096](decisions/D-096-pokemon-training-objective.md)의 학습 목표와
[D-112](decisions/D-112-imitation-self-play-objectives.md)의 모방 학습·정책 개선 방향,
[D-119](decisions/D-119-fixed-matchup-mcts.md) 이후 고정 공개 상태 연구는 후속 설계의 근거다.
EX-079·EX-080의 완료 결과와 기존 중단 결과를 각각의 조건·해석 범위에서 유지하며
어떤 과거 실행도 이 분리 작업으로 재개하지 않는다.

## 범위 (Scope)

- 대상: `pokechamp`의 모델 학습·정책 개선·독립 평가와 이를 뒷받침하는 입력·데이터·검증 기반.
- 작업 위치: `/workspace`, 브랜치 `research/model-training`; 기존 interpreter·환경·캐시 경로 유지.
- 이번 작업: 공통 소스 기준선, 목적 문서 분리, 외부 보존·검증·복원 연결.
- 후속 학습의 모델·데이터·방법·평가·자원 조건: 새 bounded plan/EX에서 구체화한다.
- L1–L5 이식은 별도 연구선의 목적이며 학습 모델과의 결합은 미정이다.

## 비목표 (Non-goals)

- Repository에 존재한다는 이유만으로 원저자의 TODO, roadmap, paper follow-up, release work,
  Future Work를 계속 수행하는 것.
- L1-L5 적용 목표를 이유로 원 AgenticSTS의 bounded-memory hypothesis, *Slay the Spire 2*
  benchmark, 기존 metric 또는 과거 result를 현재 연구 설계로 자동 채택하는 것.
- 사전에 정한 비교와 evidence 없이 `pokechamp`의 성능 개선이 달성되었다고 주장하는 것.
- Reset 이전 plan을 자동으로 되살리거나 완료하는 것.
- Game, game binary, 제외된 proprietary/upstream-derived artifact를 재배포하는 것.

## 기본 invariant (Fundamental Invariants)

1. **실질적 작업 전 명시적 목표가 필요하다.** Legacy plan이나 추정한 원저자 의도는 사용자가
   승인한 research objective와 bounded active exec plan을 대신할 수 없다.
2. **Legacy와 현재 의도를 분리한다.** 기존 code, paper, result, TODO, plan은 상속받은 artifact를
   설명할 뿐 새 연구 프로그램에 대한 authority를 갖지 않는다.
3. **Claim은 evidence와 provenance의 제약을 받는다.** Result에는 condition, 관련 version과
   configuration, denominator, evidence 위치가 있어야 한다. Evidence가 없으면 result가 아니다.
4. **Authority 충돌을 숨기지 않는다.** 하위 작업은 상위 context를 조용히 다시 쓰지 않는다.
   현재 contract나 architecture의 변경 제안은 Decision을 통해 추적 가능해야 한다.
5. **License, security, provenance 경계를 유지한다.** 상속받은 Python agent, mod fork, data,
   generated game knowledge를 재사용할 때 각각의 의무를 보존한다.

## 실험 가정과 제약 (Experimental Assumptions and Constraints)

- Legacy experiment의 hypothesis, benchmark, population, condition matrix, metric, baseline,
  stopping rule은 새 연구에 승계하지 않는다.
- 새 experiment는 실행 전에 question, population, condition, metric, denominator, stopping rule,
  configuration, provenance, contamination control을 선언한다.
- 기존 result는 관련성이 있을 때 inherited evidence로 인용할 수 있지만 기본 baseline은 아니다.

## 변경 권한 (Change Authority)

> 에이전트는 구현이나 실험을 성공시키기 위해 `CHARTER.md`를 임의로 수정해서는 안 된다. 프로젝트 목표 또는 기본 invariant의 변경에는 명시적인 사용자 지시가 필요하다.

보조 영문 원문:

> `CHARTER.md` must not be modified by an agent merely to make an implementation or experiment succeed. Changes to project goals or fundamental invariants require explicit user direction.

Repository에는 독립적인 Charter 변경 권한을 가진 상시 개인이나 조직이 지정되어 있지 않다.
해당 governance는 **TBD**다. 그 전까지 의미가 바뀌는 Charter 수정에는 명시적 사용자 지시와
추적 가능한 [`Decision`](DECISIONS.md) entry가 필요하다. 의미를 바꾸지 않는 편집·링크 수정은 일반 review로
처리할 수 있다.
