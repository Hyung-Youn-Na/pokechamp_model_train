# D-104 — EX-065 기반 Base 공동 q 학습

- 상태: Accepted
- 날짜: 2026-09-30
- 승인: 현재 사용자가 제공한 학습 계획의 구현·GPU 실행·검증 지시

## 결정과 근거

EX-065 검증 복사본의 팀 단위 분할을 유지하고 Qwen3.5-4B-Base 고정 revision에서
새 LoRA와 공유 sigmoid value head를 학습한다. 관측당 한 backbone forward에서 후보별
독립 q를 읽고 전체 타깃 MSE/Brier를 관측 동일가중으로 최적화한다. 표본 보상 bandit RLCD와
구분하며 기존 EX-061의 instruct 모델·A/B readout·개발 분모를 승계하지 않는다.

현재 지시는 GPU1의 A6000 한 장, 최대3epoch·시간 상한 없음과 독립 test 오프라인 평가를
승인한다. D-103의 수집 전용 범위와 과거 실험의 봉인은 보존한다. 신규 배틀·세 환경 비교는
이번 범위 밖이다. 개선 여부와 관계없이 필수 검증·평가·보존을 완료해야 한다.

처치·지표·분모·중단/복구의 동결 원문은 [EX-066](../experiments/EX-066-joint-q-training.md),
진행은 [EP-108](../exec-plans/active/EP-108-joint-q-training.md), 입력/모델 경계는 C-052가 소유한다.
