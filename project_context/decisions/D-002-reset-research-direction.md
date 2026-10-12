# D-002 — 연구 방향 reset 및 legacy plan 제외

- 상태 (Status): 채택 (Accepted)
- 날짜 (Date): 2026-09-04

## 맥락 (Context)

현재 사용자는 자신의 목표가 원저자의 목표와 다르며, 이후 작업을 별도 연구 프로그램으로
취급하고 기존 TODO plan을 모두 제외하라고 지시했다.

## 결정 (Decision)

기존 TODO, roadmap, Future Work 항목, unchecked checklist, 날짜가 있는 plan, handoff,
experiment-resume plan을 현재 또는 candidate work로 상속하지 않는다. 상속된 AgenticSTS
repository는 기술적 baseline으로만 취급한다. 사용자가 명시적으로 정의할 때까지 새 연구
목표와 target architecture를 `TBD`로 둔다. 새로 승인되어 `exec-plans/active/`에 놓인 파일만
active execution work를 나타낼 수 있다.

## 거절한 대안 (Rejected Alternatives)

이전에 제안된 matched accumulating-context 후속 실험을 포함하여 원래 roadmap을 이어가는
방안은 채택하지 않는다. Historical file은 삭제하지 않고 provenance를 위해 유지한다.

## 근거 (Rationale)

Repository의 계보와 원저자의 TODO는 현재 소유자의 연구 의도를 성립시키지 않는다. Legacy
evidence를 보존하되 planning authority를 끊으면 다른 연구 agenda를 실수로 이어가는 일을
방지할 수 있다.

## 영향 (Consequences)

[`../CHARTER.md`](../CHARTER.md)는 bounded-memory 연구나 원래 benchmark roadmap을 새 project
goal로 채택하지 않는다. 현재 runtime contract는 새 목표가 의도적으로 변경하기 전까지 상속
implementation의 설명으로 남는다. [`../STATUS.md`](../STATUS.md)에는 legacy backlog나 legacy
follow-up 제안이 없다.

## 증거 (Evidence)

Control-plane 초기화 직후인 2026-09-04의 명시적 사용자 지시.
