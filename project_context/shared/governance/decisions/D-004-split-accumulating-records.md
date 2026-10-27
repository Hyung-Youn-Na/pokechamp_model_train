# D-004 — 누적형 기록을 index와 개별 문서로 분리

- 상태 (Status): 채택 (Accepted)
- 날짜 (Date): 2026-09-04

## 맥락 (Context)

Decision, experiment record, completed exec plan은 시간이 지나면서 계속 누적된다. 사용자는
장기 운영을 위해 이런 기록을 하나의 대형 문서에 계속 append하지 않고 index와 개별 항목
문서로 분리하라고 명시적으로 지시했다. 동시에 현재 authoritative state를 정의하는 문서의
역할과 authority hierarchy는 유지해야 한다.

## 결정 (Decision)

- [`../DECISIONS.md`](../../../DECISIONS.md)는 decision registry로 유지하고 각 결정의 전체 본문은
  `decisions/D-XXX-short-title.md`에 둔다.
- [`../exec-plans/INDEX.md`](../../../exec-plans/INDEX.md)는 active 및 completed plan의 registry와
  lifecycle을 제공한다. 각 plan의 본문은 `active/` 또는 `completed/`의 개별 파일에 둔다.
- [`../experiments/INDEX.md`](../../../experiments/INDEX.md)는 experiment registry와 기록 규칙을
  제공한다. 각 experiment의 본문은 개별 `EX-XXX-*` record에 둔다.
- [`../CHARTER.md`](../../../CHARTER.md), [`../ARCHITECTURE.md`](../../../ARCHITECTURE.md),
  [`../CONTRACTS.md`](../../../CONTRACTS.md), [`../STATUS.md`](../../../STATUS.md)는 현재 authoritative state를
  설명하는 단일 문서로 유지한다. `STATUS.md`에는 과거 진행 로그를 축적하지 않는다.
- Index는 navigation과 요약만 제공하며 개별 record의 의미나 기존 authority hierarchy를
  대체하지 않는다.

## 거절한 대안 (Rejected Alternatives)

Decision 본문을 `DECISIONS.md` 하나에 계속 누적하는 방식과 현재 상태 문서까지 historical
fragment로 분해하는 방식은 채택하지 않았다.

## 근거 (Rationale)

누적 항목의 상세 본문을 분리하면 index가 탐색 가능한 크기로 유지되고 각 항목의 identity,
status, provenance를 독립적으로 추적할 수 있다. 반면 현재 상태 문서를 단일 source로 유지하면
독자가 여러 history fragment를 조합해 현재 규칙을 추론하지 않아도 된다.

## 영향 (Consequences)

새 decision, experiment, completed plan은 개별 파일과 해당 index row를 함께 추가해야 한다.
Accepted decision을 대체하거나 record status가 바뀌면 개별 문서를 먼저 갱신하고 index summary를
동기화한다. Index와 record가 충돌하면 임의로 해석하지 않고 불일치로 보고한다.

## 증거 (Evidence)

2026-09-04의 명시적 사용자 재구성 지시.
