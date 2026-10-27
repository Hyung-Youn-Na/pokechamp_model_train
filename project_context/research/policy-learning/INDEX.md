# 배틀 정책 학습·개선

## 연구 질문·역할

모방 학습과 후속 정책 학습이 행동 선택 및 독립 평가를 개선하는가?

공통 규칙과 본 주제의 적용 범위를 함께 읽는다. 같은 폴더에 속한다는 사실만으로 실험의 직접 비교 가능성이나 효능 개선을 주장하지 않는다.

## 읽기 경로

[DESIGN.md](DESIGN.md) · [CONTRACTS.md](CONTRACTS.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

[개별 기록과 원문 상태](RECORDS.md) · [전체 계획 상태](../../catalog/plans.md) · [방법별 탐색](../../catalog/by-method.md) · [기록 관계](../../catalog/relations.md)

## 연구 흐름과 해석 경계

### 모방 학습에서 정책 개선으로

[EX-071](experiments/EX-071-qwen-replay-imitation.md) → [EX-072](experiments/EX-072-selfplay-rlcd.md)

리플레이 선택 행동의 모방과 자기대국의 후속 정책 개선을 구분한다.

### Abyssal 상대 학습과 계승

[EX-073](experiments/EX-073-abyssal-rl.md) → [EX-074](experiments/EX-074-abyssal-rl-continue.md) → [EX-075](experiments/EX-075-abyssal-rl-next.md)

계승 체크포인트·누적 학습·독립 평가·완료 기준은 각 EX에서 확인한다. 중단 처리 완료와 효능 개선은 별도다.

### laya 압축 입력 모방

[D-183](decisions/D-183-laya-compact-imitation.md) → [EX-118](experiments/EX-118-laya-compact-imitation-training.md) → [EX-119](experiments/EX-119-laya-compact-imitation-battle32.md) → [D-184](decisions/D-184-laya-team-generalization.md) → [EX-120](experiments/EX-120-laya-team-generalization128.md)(새 팀 32개 128경기 일반화) → [D-185](decisions/D-185-laya-modular-renderer-v2.md) → [EX-121](experiments/EX-121-laya-v2-all-training.md)(렌더러 v2 학습) → [EX-122](experiments/EX-122-laya-v1-v2-battle256.md)(v1·v2 256경기) → [D-187](decisions/D-187-laya-tera-knowledge.md) → [EX-124](experiments/EX-124-laya-v2-tera-knowledge-training.md) → [EX-125](experiments/EX-125-laya-v2-tera-battle256.md)(테라 지식)

EX-071 자료·입력 경계를 압축 텍스트로 바꾼 소형 판정 모델의 모방 학습과 표준 대진 평가다. EX-071 Qwen 결과와의 비교는 모델·입력·학습량이 함께 다른 전체 구성 차이다.

## 갱신

새 D·EP·EX는 이 폴더의 decisions/plans/experiments에 등록한다. 상태 변경으로 경로를 옮기지 않는다. 원문을 갱신한 뒤 등록부와 생성 색인을 갱신한다.
