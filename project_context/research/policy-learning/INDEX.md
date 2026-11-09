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

### laya 입력 확장(v3~v10)과 래더 자료

[EX-128](experiments/EX-128-laya-v3-tera-training.md)·[EX-129](experiments/EX-129-laya-v2t-v3t-battle256.md)(v3) → [EX-130](experiments/EX-130-laya-v4-tera-training.md)·[EX-131](experiments/EX-131-laya-v2t-v4t-battle256.md)(v4) → [EX-136](experiments/EX-136-laya-v5-tera-training.md)·[EX-137](experiments/EX-137-laya-v4t-v5t-battle256.md)(v5) → [EX-141](experiments/EX-141-laya-v6s-streaks-training.md)·[EX-142](experiments/EX-142-laya-v6h-long-history-training.md)(v6) → [EX-149](experiments/EX-149-laya-v7-opponent-sets-training.md)·[EX-150](experiments/EX-150-laya-v6st-v7t-battle256.md)(v7) → [EX-152](experiments/EX-152-laya-v8-engine-fails-training.md)·[EX-155](experiments/EX-155-laya-v8l-likely-fails-training.md)(v8·v8l) → [EX-157](experiments/EX-157-laya-v9-opponent-threat-training.md)·[EX-158](experiments/EX-158-laya-v7t-v9t-battle256.md)(v9) → [D-204](decisions/D-204-laya-renderer-v10-all-info.md) → [EX-161](experiments/EX-161-laya-v10-all-info-training.md)·[EX-162](experiments/EX-162-laya-v7t-v10t-battle256.md)(v10) → [D-208](decisions/D-208-laya-ladder-r1500-v10.md) → [EX-166](experiments/EX-166-laya-ladder-r1500-data.md)·[EX-167](experiments/EX-167-laya-v10-ladder-training.md)·[EX-168](experiments/EX-168-laya-v10t-v10rt-battle256.md)(v10 + 래더)

판본마다 앞 판본의 입력에 정보를 더하고, 같은 EX-120 일정에서 앞 모델과 Abyssal 256경기로 비교한다. 잠긴 test의 사람 선택 재현은 v10(EX-161)과 래더 자료(EX-167)에서 구간이 0 아래로 나아졌다. 하지만 Abyssal 점수는 v7t 0.875, v9t 0.859, v10t 0.867, v10rt 0.859로 모여 서로 구별되지 않는다(포화). 사람 팀 일정([EX-159](experiments/EX-159-laya-human-teams-v7t-v8t-v9t.md)·[EX-160](experiments/EX-160-laya-human-teams-v8lt.md))도 같다. 이 계열의 판별은 사람 대전, 직접 대결([EX-134](experiments/EX-134-laya-head-to-head512.md) 하네스), 읽기 상대([EX-163](experiments/EX-163-laya-v8lt-vs-switch-reader.md)~[EX-165](experiments/EX-165-laya-opponent-prediction-scenes.md))로 보충한다.

## 갱신

새 D·EP·EX는 이 폴더의 decisions/plans/experiments에 등록한다. 상태 변경으로 경로를 옮기지 않는다. 원문을 갱신한 뒤 등록부와 생성 색인을 갱신한다.
