# 전략 계획과 행동 실행

## 연구 질문·역할

전략 계획·갱신 정책·수행 지시를 결합했을 때 어떤 행동이 관찰되는가?

공통 규칙과 본 주제의 적용 범위를 함께 읽는다. 같은 폴더에 속한다는 사실만으로 실험의 직접 비교 가능성이나 효능 개선을 주장하지 않는다.

## 읽기 경로

[DESIGN.md](DESIGN.md) · [CONTRACTS.md](CONTRACTS.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

[개별 기록과 원문 상태](RECORDS.md) · [전체 계획 상태](../../catalog/plans.md) · [방법별 탐색](../../catalog/by-method.md) · [기록 관계](../../catalog/relations.md)

## 연구 흐름과 해석 경계

### 설정 환경과 첫 샘플

[EP-145](plans/EP-145-jev-planner-environment.md) → [EP-146](plans/EP-146-planner-role-resource-guide.md) → [EX-092](experiments/EX-092-planner-first-battle-sample.md) → [EX-093](experiments/EX-093-planner-goal-completion-sample.md)

전략 계획과 최종 행동 수행의 역할을 분리하고 지시문·표시명·호출 조건을 확인한다.

### 복구·모델·추론 강도

[EX-094](experiments/EX-094-planner-json-retry-sample.md) → [EX-097](experiments/EX-097-planner-format-temperature-zero.md) → [EX-098](experiments/EX-098-planner-high-effort-sample.md) → [EX-099](experiments/EX-099-planner-unlimited-time-max-output.md) → [EX-100](experiments/EX-100-glm53-low-sample.md)

단일 샘플과 결합 처치가 포함된다. 연속 ID를 동일 조건의 성능 순위로 읽지 않는다.

### 사건 호출과 수행 모델

[EX-101](experiments/EX-101-matchup-events.md) → [EX-102](experiments/EX-102-matchup-events-high.md) → [EX-103](experiments/EX-103-jev-omni-low.md) → [EX-104](experiments/EX-104-tacit-thinking-low.md) → [EX-105](experiments/EX-105-tacit-vllm-low.md)

계획 갱신 사건·추론 강도·수행 모델/backend 차이를 구분하고 실패 표본도 연결한다.

## 갱신

새 D·EP·EX는 이 폴더의 decisions/plans/experiments에 등록한다. 상태 변경으로 경로를 옮기지 않는다. 원문을 갱신한 뒤 등록부와 생성 색인을 갱신한다.
