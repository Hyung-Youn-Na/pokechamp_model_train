# 프로젝트 헌장 (Project Charter)

현재 당면 우선순위는 [D-119](decisions/D-119-fixed-matchup-mcts.md)의 **고정 A/B 공개 상태
자기대국·MCTS 정책 개선 검증**이다. 사용자의 첫1라운드 요청 [D-123](decisions/D-123-fixed-matchup-first-round.md)에
따라 [EX-078](experiments/EX-078-fixed-matchup-first-round.md)의 체크포인트 진단을
[EP-127](exec-plans/active/EP-127-fixed-matchup-first-round.md)에서 수행했으나 시간초과로 학습 전 중단했다.
후속 실행에는 [D-124](decisions/D-124-fixed-matchup-no-time-limit.md)의 시간 상한 해제를 적용한다.
현재 [D-125](decisions/D-125-first-round-single-retry.md)/[EP-129](exec-plans/completed/EP-129-first-round-single-retry.md)으로
정상31을 계승하고 실패1만 재수집해 첫라운드 학습·체크포인트 진단을 완료했다.
후속 [D-126](decisions/D-126-fixed-matchup-stopping.md)/[EX-079](experiments/EX-079-fixed-matchup-stopping.md)는
정기 평가·목표/정체/라운드 종료조건과 최고 모델 독립 시험을 완료했다.
EX079의 초기모델 상대 우세와 Abyssal 주평가 개선 미입증을 구분한다.
EX-076 예산 중단·EX-077 사용자 중지와 기존 Qwen 자료/판정·L1-L5 장기 목표를 보존한다.

**Authority:** 가장 높은 수준의 프로젝트 의도다. 현재 사용자가 연구 방향을 명시적으로
재설정했으므로, 상속받은 repository는 새 연구의 목표가 아니라 활용 가능한 출발 artifact다.

## 프로젝트 목표 (Project Goal)

AgenticSTS의 **L1-L5 계층형 메모리/컨텍스트 구조를 `pokechamp`에 적용하여 성능 개선을
시도하는 것**이 이 프로젝트의 최상위 연구 목표다.

이 목표는 성능 향상을 사전에 보장하거나 이미 달성된 사실로 전제하지 않는다. 개선 여부는
명시적으로 정의한 baseline, outcome measure, evaluation protocol과 보존된 evidence로 판단한다.
L1-L5의 정확한 `pokechamp` 대응 관계, 구현 범위와 평가 기준은
[`RESEARCH_DESIGN.md`](RESEARCH_DESIGN.md), 관련 Decision 및 bounded exec plan에서 구체화한다.

기존 AgenticSTS code, mod, data, documentation은 L1-L5 구조를 이해하고 이전할 때 참고하거나
선택적으로 재사용할 수 있는 기술적 baseline/evidence다. 원 프로젝트의 hypothesis, benchmark,
metric 또는 결과를 새 목표에 자동 승계하지 않는다.

<a id="immediate-objective"></a>

### 당면 목표

현재 우선 목표는 **구성한 LAYA-RLCD·EVE-RLCD·RLCD-Lite 세 학습 환경을 활용하여
포켓몬 배틀에 특화된 모델을 학습하고, 행동 선택·배틀 성능의 개선 여부를 평가하는 것**이다.
2026-09-28 사용자 지시와 [D-096](decisions/D-096-pokemon-training-objective.md)에 따라 채택한다.
2026-10-01 사용자 지시와 [D-112](decisions/D-112-imitation-self-play-objectives.md)에 따라,
Qwen 기반 구조화 행동 선택 모델(Kev 포함)의 **기존 리플레이 모방 학습 → 자기대국을 통한
정책 개선**을 단기 학습 방향으로 채택했다. D-115의 Abyssal 우선 단계를 거쳐,
2026-10-07 [D-119](decisions/D-119-fixed-matchup-mcts.md)에 따라 **고정 A/B 공개 상태에서
작은 전용 모델의 자기대국·MCTS 정책 개선 검증**을 먼저 추진한다. 단계별 산출물·평가와 미정 설계는
[단기 학습 목표](RESEARCH_DESIGN.md#pokemon-imitation-self-play)를 따른다.
L1-L5 적용은 장기 목표로 유지하며, 학습 모델과 메모리 구조의 결합 방식은 미정이다.
학습·평가의 구체적 설계와 해석은 [연구 설계](RESEARCH_DESIGN.md#pokemon-training-objective)를 따른다.

## 범위 (Scope)

- 적용 대상 시스템과 연구 domain: `pokechamp`.
- 당면 intervention: 세 RLCD 환경을 활용한 포켓몬 배틀 전용 모델 학습.
- 장기 intervention: AgenticSTS에서 L1-L5로 구분하는 계층형 메모리/컨텍스트 구조의 적용.
- 의도한 outcome: `pokechamp`의 성능 개선 시도와 그 효과에 대한 evidence 기반 평가.
- Layer별 대응, 재사용할 AgenticSTS component, deliverable, baseline, 성능 지표, 성공 기준과
  evaluation protocol의 구체적 정의: **TBD**.
- 구체적인 구현과 실험은 위 미정 항목을 관련 authority 문서와 bounded exec plan에서 정한 뒤
  수행한다.

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
