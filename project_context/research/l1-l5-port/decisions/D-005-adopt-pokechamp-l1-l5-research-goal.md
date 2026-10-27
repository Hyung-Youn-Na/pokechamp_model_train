# D-005 — `pokechamp` 대상 L1-L5 적용 연구 목표 채택

- 상태 (Status): 채택 (Accepted)
- 날짜 (Date): 2026-09-04

## 맥락 (Context)

[`D-002`](../../../shared/governance/decisions/D-002-reset-research-direction.md)는 상속된 연구 방향을 reset하고, 사용자가 새 목표를
명시할 때까지 project goal을 `TBD`로 두었다. 사용자는 현재 프로젝트의 최상위 연구 목표를
AgenticSTS의 L1-L5 메모리 구조를 `pokechamp`에 적용하여 성능 개선을 시도하는 것으로
명시했다.

## 결정 (Decision)

AgenticSTS의 L1-L5 계층형 메모리/컨텍스트 구조를 `pokechamp`에 적용하고 그 적용을 통한 성능
개선을 시도하는 것을 최상위 연구 목표로 채택한다. AgenticSTS는 이전할 구조의 reference이며,
`pokechamp`는 적용 및 성능 평가 대상이다.

이 결정은 layer별 대응, code 재사용 범위, baseline, performance metric, hypothesis, 성공 기준
또는 evaluation protocol을 확정하지 않는다. 이 항목들은 구현이나 실험 전에
[`../RESEARCH_DESIGN.md`](../../../RESEARCH_DESIGN.md)와 bounded exec plan에서 별도로 정의한다.

## 거절한 대안 (Rejected Alternatives)

기록 없음 (None recorded). 목표는 사용자가 명시적으로 지정했다.

## 근거 (Rationale)

상위 목표를 target system, 적용할 구조와 의도한 outcome 방향으로 명확히 구분하면 이후 설계와
구현이 legacy AgenticSTS roadmap을 자동 승계하지 않으면서도 동일한 연구 목적을 따를 수 있다.
성능 개선을 검증된 사실이 아닌 평가할 목표로 기록하면 evidence 없이 efficacy를 주장하는 것도
방지한다.

## 영향 (Consequences)

[`D-002`](../../../shared/governance/decisions/D-002-reset-research-direction.md)의 legacy plan 제외 결정은 계속 유효하지만, 새 연구
목표가 `TBD`였던 조건은 해소된다. [`../CHARTER.md`](../../../CHARTER.md),
[`../RESEARCH_DESIGN.md`](../../../RESEARCH_DESIGN.md), [`../STATUS.md`](../../../STATUS.md)는 이 목표와
정합해야 한다. 구체적인 구현 또는 실험은 아직 승인된 active work가 아니며 별도 설계와 exec
plan이 필요하다.

## 증거 (Evidence)

2026-09-04의 명시적 사용자 지시.
