# D-001 — Persistent project-context control plane 수립

- 상태 (Status): 채택 (Accepted)
- 날짜 (Date): 2026-09-04

## 맥락 (Context)

사용자가 사람과 coding agent가 공유하는 장기 design, implementation, experiment 작업용
persistent context를 repository에 추가하라고 명시적으로 지시했다.

## 결정 (Decision)

[`../INDEX.md`](../INDEX.md)가 안내하는 authority hierarchy와 work/experiment lifecycle을 갖춘
`project_context/`를 사용한다. Root [`AGENTS.md`](../../AGENTS.md)는 간결하게 유지하고
substantive work를 이곳으로 routing한다.

## 거절한 대안 (Rejected Alternatives)

기록 없음. Directory 구조와 hierarchy는 사용자가 명시적으로 지시했다.

## 근거 (Rationale)

현재 context는 README, 날짜가 있는 reference document, archived plan, source, experiment
artifact에 분산되어 있다. 작은 authority-aware layer를 두면 그 evidence를 재작성하지 않고도
충돌과 active work를 드러낼 수 있다.

## 영향 (Consequences)

미래의 substantive work는 이 directory를 먼저 확인하고, lower-level work에 맞추려고
higher-authority context를 변경하지 않으며, bounded exec plan과 evidence가 연결된 experiment
record를 사용한다.

## 증거 (Evidence)

2026-09-04 초기화 task의 명시적 사용자 지시와 그 task에서 추가한 파일.
