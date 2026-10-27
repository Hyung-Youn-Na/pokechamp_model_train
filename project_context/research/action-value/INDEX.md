# 후보 행동가치 추정

## 연구 질문·역할

후보별 조건부 가치와 공동 q를 학습하고 실제 선택에 사용할 수 있는가?

공통 규칙과 본 주제의 적용 범위를 함께 읽는다. 같은 폴더에 속한다는 사실만으로 실험의 직접 비교 가능성이나 효능 개선을 주장하지 않는다.

## 읽기 경로

[DESIGN.md](DESIGN.md) · [CONTRACTS.md](CONTRACTS.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

[개별 기록과 원문 상태](RECORDS.md) · [전체 계획 상태](../../catalog/plans.md) · [방법별 탐색](../../catalog/by-method.md) · [기록 관계](../../catalog/relations.md)

## 연구 흐름과 해석 경계

### 한 경기 후보별 가치

[EX-060](experiments/EX-060-single-battle-branch-rollouts.md) → [EX-061](experiments/EX-061-qwen-action-value.md) → [EX-062](experiments/EX-062-qwen-local-battle.md) → [EX-063](experiments/EX-063-qwen-training-matchup.md) → [EX-064](experiments/EX-064-qwen-candidate-state.md)

특정 숨은 상태·후속 정책에 조건부인 q와 실제 행동 선택 확률을 구분한다. 개발 대진 적합은 독립 성능 개선이 아니다.

### 다경기 공동 q와 평가

[EX-065](experiments/EX-065-joint-q-data.md) → [EX-066](experiments/EX-066-joint-q-training.md) → [EX-067](experiments/EX-067-abyssal-tera-joint-q.md) → [EX-081](experiments/EX-081-joint-q-battle.md)

자료 분할·Tera 보완·재로딩 실패와 후속 배틀 평가의 출처를 각각 보존한다.

## 갱신

새 D·EP·EX는 이 폴더의 decisions/plans/experiments에 등록한다. 상태 변경으로 경로를 옮기지 않는다. 원문을 갱신한 뒤 등록부와 생성 색인을 갱신한다.
