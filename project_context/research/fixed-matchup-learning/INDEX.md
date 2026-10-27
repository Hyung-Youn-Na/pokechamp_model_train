# 고정 대진 공개 상태 학습

## 연구 질문·역할

고정 공개 상태에서 탐색과 자기대국이 탐색 없는 정책을 개선하는가?

공통 규칙과 본 주제의 적용 범위를 함께 읽는다. 같은 폴더에 속한다는 사실만으로 실험의 직접 비교 가능성이나 효능 개선을 주장하지 않는다.

## 읽기 경로

[DESIGN.md](DESIGN.md) · [CONTRACTS.md](CONTRACTS.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

[개별 기록과 원문 상태](RECORDS.md) · [전체 계획 상태](../../catalog/plans.md) · [방법별 탐색](../../catalog/by-method.md) · [기록 관계](../../catalog/relations.md)

## 연구 흐름과 해석 경계

### 공개 상태의 진단 범위

[EX-076](experiments/EX-076-fixed-matchup-mcts.md) → [EX-077](experiments/EX-077-fixed-matchup-day.md)

고정 두 팀·공개 상태 연구를 일반 비공개 Gen9 OU 성능으로 확대하지 않는다.

### 첫 라운드·종료조건·행렬 탐색

[EX-078](experiments/EX-078-fixed-matchup-first-round.md) → [EX-079](experiments/EX-079-fixed-matchup-stopping.md) → [EX-080](experiments/EX-080-qwen-matrix-selfplay.md)

예산·중단·복구·모델 초기화와 탐색 방식 변경을 구분한다. 과거 미완료 실행을 자동 재개하지 않는다.

## 갱신

새 D·EP·EX는 이 폴더의 decisions/plans/experiments에 등록한다. 상태 변경으로 경로를 옮기지 않는다. 원문을 갱신한 뒤 등록부와 생성 색인을 갱신한다.
