# D-XXX — 제목 (Title)

- 상태 (Status): 제안 (Proposed) | 채택 (Accepted) | D-YYY로 대체됨 (Superseded) | 거절 (Rejected)
- 날짜 (Date): YYYY-MM-DD

## 맥락 (Context)

결정이 필요한 상황과 확인된 evidence를 적는다. Fact와 assumption을 구분한다.

## 결정 (Decision)

채택하거나 검토할 선택을 명확하게 적는다.

## 거절한 대안 (Rejected Alternatives)

검토한 대안과 채택하지 않은 이유를 적는다. 기록이 없으면 `기록 없음 (None recorded)`이라고
쓴다.

## 근거 (Rationale)

이 선택이 맥락과 상위 authority를 어떻게 충족하는지 적는다.

## 영향 (Consequences)

후속 작업, 제약, migration 또는 알려진 trade-off를 적는다.

## 증거 (Evidence)

승인 지시, 관련 contract, source, experiment 또는 exec plan을 link한다.

---

Stable하고 단조 증가하는 ID를 사용하며 ID를 재사용하지 않는다. Accepted decision을 이후 선택에
맞춰 다시 쓰지 않는다. 선택이 바뀌면 새 decision으로 대체하고 두 문서와
[`../DECISIONS.md`](../DECISIONS.md)의 관계를 함께 갱신한다.

## 등록·탐색 정보

원문을 승인된 기본 주제의 decisions/plans/experiments에 두고 catalog/records.json에 등록한다.
ID·path·topic·methods(학습/추론/평가)·models·datasets·relations를 기록하며
제목·상태·결과는 이 원문에서만 관리한다. 새 기록의 legacy_paths는 빈 배열이다.
상태 변경으로 파일을 이동하지 않는다. 생성 색인은 context-catalog build/check로 갱신한다.
