# 고정 대진 공개 상태 학습 — 기록 목록

<!-- generated: scripts/context-catalog build -->

원문은 한 곳에 두며 다른 주제의 관련 기록은 색인과 원문 링크로 연결한다.

| ID | 제목 | 상태 |
|---|---|---|
| [D-119](decisions/D-119-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 정책 학습 | Accepted |
| [D-120](decisions/D-120-fixed-matchup-run.md) | 고정 대진 GPU 학습·실험 실행 | Accepted |
| [D-121](decisions/D-121-fixed-matchup-fnt-recovery.md) | 기절 상태 교정 후 원 예산 재개 | Accepted |
| [D-122](decisions/D-122-fixed-matchup-day.md) | 하루 내 예상 시 고정 대진 실행 | Accepted |
| [D-123](decisions/D-123-fixed-matchup-first-round.md) | 첫1라운드 체크포인트 진단 | Accepted |
| [D-124](decisions/D-124-fixed-matchup-no-time-limit.md) | 현재1라운드 실험의 경과시간 상한 해제 | Accepted |
| [D-125](decisions/D-125-first-round-single-retry.md) | 실패1경기 재수집·첫라운드 재개 | Accepted |
| [D-126](decisions/D-126-fixed-matchup-stopping.md) | 성능·정체·학습량 종료조건을 갖춘 추가 학습 | Accepted |
| [D-127](decisions/D-127-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Accepted |
| [D-128](decisions/D-128-qwen-fixed-shape-serving.md) | EX-080 고정 shape 서빙과 G3·G4 게이트 재정의 | Accepted |
| [EP-124](plans/EP-124-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 구현 | Completed — 구현·CPU 개발 검증 완료, 실험 미실행 |
| [EP-125](plans/EP-125-fixed-matchup-run.md) | 고정 A/B 공개 상태 GPU 실험 | Blocked — 교정 후 기술 검증 통과, 평가 예산 gate 초과로 학습/test 보류 |
| [EP-126](plans/EP-126-fixed-matchup-day.md) | 하루 내 고정 대진 실험 | Paused — 사용자 요청 중지; 학습·test 미시작 |
| [EP-127](plans/EP-127-fixed-matchup-first-round.md) | 첫1라운드 학습 | Blocked — 원실행1경기 시간초과·학습0; 시간 규범 변경 완료 후 재개 미실행 |
| [EP-128](plans/EP-128-fixed-matchup-no-time-limit.md) | EX-078 경과시간 상한 해제 | Completed |
| [EP-129](plans/EP-129-first-round-single-retry.md) | 실패1경기 재수집·1라운드 재개 | Completed |
| [EP-130](plans/EP-130-first-round-model-comparison.md) | 첫라운드 전후 동일 관측 비교 | Completed |
| [EP-131](plans/EP-131-fixed-matchup-stopping.md) | 종료조건 기반 추가 학습·독립 평가 | Completed |
| [EP-132](plans/EP-132-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 자기대국 학습 실행 | Completed |
| [EX-076](experiments/EX-076-fixed-matchup-mcts.md) | 고정 A/B 공개 상태 MCTS 정책 학습 | Incomplete — 교정 후 기술 검증/측정 통과, 평가 예산 gate 초과로 학습/test 보류 |
| [EX-077](experiments/EX-077-fixed-matchup-day.md) | 하루 내 고정 대진 공개 상태 학습 | Incomplete — 사용자 요청 중지; 학습/test 미시작 |
| [EX-078](experiments/EX-078-fixed-matchup-first-round.md) | 첫1라운드 학습 체크포인트 | Completed — D-125 복구·첫라운드 진단 완료; 원실행 Incomplete 보존 |
| [EX-079](experiments/EX-079-fixed-matchup-stopping.md) | 종료조건 기반 고정 대진 추가 학습 | Completed — 추가학습·시험·감사/뷰어·정리 완료; 주효능 기준 미달 |
| [EX-080](experiments/EX-080-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Completed — 시도 3 학습(round40 둔화 종료)·선택(round36)·잠긴 test·감사/뷰어/봉인·정리 완료; 주효능 미입증 (시도 1·2는 도구 결함으로 학습 전 중단·보존) |
