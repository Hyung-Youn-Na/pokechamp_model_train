# 방법별 탐색

<!-- generated: scripts/context-catalog build -->

탐색 분류는 처치의 동일성·실제 실행·직접 비교 가능성을 보증하지 않는다. 관련 모델·자료에는 기준선과 참조도 포함하며 실제 조건은 원문을 확인한다.

| 분류 | 기록 수 |
|---|---|
| [추론 / Choice](#추론--choice) | 25 |
| [추론 / MCTS](#추론--mcts) | 5 |
| [추론 / laya](#추론--laya) | 22 |
| [추론 / vLLM LoRA 선택지 판독](#추론--vllm-lora-선택지-판독) | 3 |
| [추론 / 요약](#추론--요약) | 97 |
| [추론 / 입력 표현](#추론--입력-표현) | 8 |
| [추론 / 전략 planner](#추론--전략-planner) | 30 |
| [추론 / 행렬 탐색](#추론--행렬-탐색) | 1 |
| [평가 / System1](#평가--system1) | 3 |
| [평가 / 고정 대진](#평가--고정-대진) | 94 |
| [평가 / 고정대진32경기](#평가--고정대진32경기) | 2 |
| [평가 / 독립 선택형](#평가--독립-선택형) | 29 |
| [평가 / 배틀](#평가--배틀) | 30 |
| [평가 / 배틀32](#평가--배틀32) | 1 |
| [평가 / 서빙 기술 검증](#평가--서빙-기술-검증) | 1 |
| [평가 / 오프라인 QA](#평가--오프라인-qa) | 5 |
| [평가 / 정보 제거](#평가--정보-제거) | 9 |
| [학습 / LoRA](#학습--lora) | 20 |
| [학습 / RLCD](#학습--rlcd) | 7 |
| [학습 / SFT](#학습--sft) | 1 |
| [학습 / System1](#학습--system1) | 3 |
| [학습 / laya](#학습--laya) | 26 |
| [학습 / soft-CE](#학습--soft-ce) | 26 |
| [학습 / 공동 q](#학습--공동-q) | 1 |
| [학습 / 규칙 데이터 생성](#학습--규칙-데이터-생성) | 3 |
| [학습 / 리플레이 결과 지도](#학습--리플레이-결과-지도) | 2 |
| [학습 / 모방](#학습--모방) | 26 |
| [학습 / 모방 학습](#학습--모방-학습) | 7 |
| [학습 / 본문 근거 역할 주석](#학습--본문-근거-역할-주석) | 2 |
| [학습 / 분류 데이터 생성](#학습--분류-데이터-생성) | 1 |
| [학습 / 선택지 교차엔트로피](#학습--선택지-교차엔트로피) | 13 |
| [학습 / 자기대국](#학습--자기대국) | 18 |
| [학습 / 정책 강화학습](#학습--정책-강화학습) | 3 |
| [학습 / 조건부 KO 판정](#학습--조건부-ko-판정) | 2 |
| [학습 / 학습 데이터 생성](#학습--학습-데이터-생성) | 2 |
| [학습 / 합성 규칙 자료](#학습--합성-규칙-자료) | 2 |
| [학습 / 행동가치](#학습--행동가치) | 10 |

## 추론 / Choice

| ID | 제목 | 상태 |
|---|---|---|
| [D-028](../research/input-and-memory/decisions/D-028-summary-max-diagnostic.md) | 요약 thinking low/max 독립 진단 | Accepted |
| [D-071](../research/model-evaluation/decisions/D-071-jev-battle.md) | JEV Choice 배틀 연결 | Accepted |
| [D-113](../research/policy-learning/decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [D-134](../research/model-evaluation/decisions/D-134-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32경기 | Accepted |
| [D-160](../research/model-evaluation/decisions/D-160-strategist-first-battle.md) | Strategist 첫 배틀 탐색 평가 | Accepted |
| [EP-011](../research/input-and-memory/plans/EP-011-improved-io.md) | IO 개선 및 병렬 3조건 비교 | Blocked |
| [EP-062](../research/model-evaluation/plans/EP-062-jev-battle.md) | JEV 전용 배틀 입력과 2경기 테스트 | Blocked |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-139](../research/model-evaluation/plans/EP-139-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32 평가 | Completed |
| [EP-149](../research/planner-executor/plans/EP-149-executor-goal-completion.md) | JEV 계획 목표 충족 확인 지시 | Completed |
| [EP-179](../research/model-evaluation/plans/EP-179-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Blocked |
| [EX-024](../research/input-and-memory/experiments/EX-024-low-summary-prompt-reexperiment.md) | low 요약 지시 개선 후 IO 재실험 | Blocked |
| [EX-047](../research/model-evaluation/experiments/EX-047-jev-battle.md) | JEV Choice 소규모 배틀 진단 | Incomplete |
| [EX-051](../research/input-and-memory/experiments/EX-051-jev-v2-battle.md) | JEV 교정 입력 v2 동일 조건2경기 | Completed |
| [EX-071](../research/policy-learning/experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EX-082](../research/model-evaluation/experiments/EX-082-jev27b-ex058-reproduction.md) | JEV-27B로 EX-058 개선 입력 동일32 평가 | Blocked |
| [EX-083](../research/model-evaluation/experiments/EX-083-jev27b-four-gpu-continuation.md) | JEV-27B 4GPU 잔여9경기 계승 평가 | Completed |
| [EX-084](../research/model-evaluation/experiments/EX-084-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책의 EX-083 동일32경기 평가 | Completed |
| [EX-085](../research/model-evaluation/experiments/EX-085-jev9b-single-choice.md) | JEV-9B의 EX-083 설정 기반 동일32경기 평가 | Completed |
| [EX-086](../research/input-and-memory/experiments/EX-086-jev27b-public-memory-v6.md) | JEV-27B 공개 정보 v6 신규32경기 | Blocked |
| [EX-087](../research/input-and-memory/experiments/EX-087-jev9b-public-memory-v6.md) | JEV-9B 공개 정보 v6 신규32경기 | Blocked |
| [EX-088](../research/input-and-memory/experiments/EX-088-jev27b-v6-corrected.md) | 교정 v6 JEV-27B 신규32경기 | Completed |
| [EX-090](../research/input-and-memory/experiments/EX-090-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 신규32경기 | Completed |
| [EX-091](../research/model-evaluation/experiments/EX-091-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 신규32경기 | Completed |
| [EX-095](../research/planner-executor/experiments/EX-095-jev35b-nvfp4-sample.md) | JEV-35B-NVFP4 EX-094 동일 대진 샘플 | Blocked |

## 추론 / MCTS

| ID | 제목 | 상태 |
|---|---|---|
| [D-119](../research/fixed-matchup-learning/decisions/D-119-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 정책 학습 | Accepted |
| [EP-124](../research/fixed-matchup-learning/plans/EP-124-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 구현 | Completed — 구현·CPU 개발 검증 완료, 실험 미실행 |
| [EP-130](../research/fixed-matchup-learning/plans/EP-130-first-round-model-comparison.md) | 첫라운드 전후 동일 관측 비교 | Completed |
| [EX-076](../research/fixed-matchup-learning/experiments/EX-076-fixed-matchup-mcts.md) | 고정 A/B 공개 상태 MCTS 정책 학습 | Incomplete — 교정 후 기술 검증/측정 통과, 평가 예산 gate 초과로 학습/test 보류 |
| [EX-079](../research/fixed-matchup-learning/experiments/EX-079-fixed-matchup-stopping.md) | 종료조건 기반 고정 대진 추가 학습 | Completed — 추가학습·시험·감사/뷰어·정리 완료; 주효능 기준 미달 |

## 추론 / laya

| ID | 제목 | 상태 |
|---|---|---|
| [D-184](../research/policy-learning/decisions/D-184-laya-team-generalization.md) | laya 모방 모델의 새 팀 일반화 평가 | Accepted |
| [D-194](../research/policy-learning/decisions/D-194-laya-head-to-head-evaluation.md) | laya 직접 대결 평가(GPU2, EX-120 일정) | Accepted |
| [D-196](../research/policy-learning/decisions/D-196-laya-v2t-corrected-input-battle.md) | laya v2+테라(EX-124)를 재학습 없이 D-195 보정 입력으로 배틀(GPU1) | Accepted |
| [D-197](../research/policy-learning/decisions/D-197-laya-v2t-tera-decision-defence.md) | laya v2+테라(EX-124) fix 입력에서 테라 합산 결정과 테라 방어 문구 배틀(재학습 없음, GPU1) | Accepted |
| [EP-209](../research/policy-learning/plans/EP-209-laya-team-generalization.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EP-217](../research/policy-learning/plans/EP-217-laya-head-to-head-evaluation.md) | laya 직접 대결 평가 하네스와 벤치마크(GPU2) | Active |
| [EP-219](../research/policy-learning/plans/EP-219-laya-v2t-corrected-input-battle.md) | laya v2+테라 보정 입력 배틀(재학습 없음, GPU1) | Completed |
| [EP-220](../research/policy-learning/plans/EP-220-laya-v2t-tera-decision-defence.md) | laya v2+테라 fix 입력 테라 합산 결정·테라 방어 문구 배틀(재학습 없음, GPU1) | Active |
| [EX-119](../research/policy-learning/experiments/EX-119-laya-compact-imitation-battle32.md) | laya 압축 입력 모방 모델 EX-089 표준 32경기 | Completed |
| [EX-120](../research/policy-learning/experiments/EX-120-laya-team-generalization128.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EX-122](../research/policy-learning/experiments/EX-122-laya-v1-v2-battle256.md) | laya v1·v2 같은 실행 256경기 비교 (EX-120 일정) | Completed |
| [EX-125](../research/policy-learning/experiments/EX-125-laya-v2-tera-battle256.md) | laya v2와 v2+테라 지식 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-127](../research/policy-learning/experiments/EX-127-laya-v2t-v2te-battle256.md) | laya v2+테라와 v2+테라+효과 지식 같은 실행 256경기(GPU2, EX-120 일정) | Completed |
| [EX-129](../research/policy-learning/experiments/EX-129-laya-v2t-v3t-battle256.md) | laya v2+테라와 v3+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-131](../research/policy-learning/experiments/EX-131-laya-v2t-v4t-battle256.md) | laya v2+테라와 v4+테라 같은 실행 256경기(GPU1, EX-120 일정) | Planned |
| [EX-133](../research/policy-learning/experiments/EX-133-laya-v2t-v2tw-battle256.md) | laya v2+테라와 v2+테라 승패 가중 모방 같은 실행 256경기(GPU0, EX-120 일정) | Planned |
| [EX-134](../research/policy-learning/experiments/EX-134-laya-head-to-head512.md) | laya v2+테라 대 v2·v1·v2+테라+효과·v3+테라 직접 대결 512경기(GPU2, EX-120 일정) | Running |
| [EX-135](../research/policy-learning/experiments/EX-135-laya-head-to-head-v2tw-v4t.md) | laya v2+테라 대 승패 가중·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Planned |
| [EX-137](../research/policy-learning/experiments/EX-137-laya-v4t-v5t-battle256.md) | laya v4+테라와 v5+테라 같은 실행 256경기(GPU0, EX-120 일정) | Planned |
| [EX-138](../research/policy-learning/experiments/EX-138-laya-head-to-head-v5t.md) | laya v5+테라 대 v2+테라·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Planned |
| [EX-139](../research/policy-learning/experiments/EX-139-laya-v2t-corrected-input-battle256.md) | laya v2+테라(EX-124) 보정 입력 fix·info 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-140](../research/policy-learning/experiments/EX-140-laya-v2t-tera-decision-defence384.md) | laya v2+테라(EX-124) fix 입력 테라 합산 결정(k=1·3)과 테라 방어 문구 384경기(GPU1, EX-120 일정) | Running |

## 추론 / vLLM LoRA 선택지 판독

| ID | 제목 | 상태 |
|---|---|---|
| [EP-190](../research/rule-learning/plans/EP-190-jevk5-vllm-serving-check.md) | JevK5 추가 LoRA vLLM 서빙 확인 | Completed |
| [EP-191](../research/rule-learning/plans/EP-191-jevk5-ruleqa-battle32.md) | 학습 JevK5 LoRA 실전32 실행 | Completed |
| [EX-114](../research/rule-learning/experiments/EX-114-jevk5-ruleqa-battle32.md) | 학습 JevK5 선택형 LoRA 실전32 | Completed |

## 추론 / 요약

| ID | 제목 | 상태 |
|---|---|---|
| [D-004](../shared/governance/decisions/D-004-split-accumulating-records.md) | 누적형 기록을 index와 개별 문서로 분리 | 채택 (Accepted) |
| [D-019](../research/input-and-memory/decisions/D-019-improved-io.md) | IO 관측·계산·고정 정책 및 배틀 내 요약 비교 | Accepted |
| [D-022](../research/input-and-memory/decisions/D-022-resume-io-experiment.md) | EX-017 재실험 및 발생 오류 중심 패치 | Accepted |
| [D-023](../research/input-and-memory/decisions/D-023-summary-harness-diagnostics.md) | 요약 오류의 harness 기여도 진단 | Accepted |
| [D-024](../research/input-and-memory/decisions/D-024-state-summary-thinking.md) | 상태 처리 정비와 요약 thinking 비교 | Accepted |
| [D-025](../shared/governance/decisions/D-025-agent-instruction-boundaries.md) | 승인 근거와 작업 중단·완료 범위 명료화 | 채택 (Accepted) |
| [D-026](../research/input-and-memory/decisions/D-026-continue-io-experiment.md) | EX-017 계열 IO 실험의 사용자 승인 재개 | Accepted |
| [D-027](../research/input-and-memory/decisions/D-027-low-summary-prompt-reexperiment.md) | low 요약 지시 개선과 IO 재실험 | Accepted |
| [D-028](../research/input-and-memory/decisions/D-028-summary-max-diagnostic.md) | 요약 thinking low/max 독립 진단 | Accepted |
| [D-030](../research/input-and-memory/decisions/D-030-io-battle-only.md) | 요약을 제외한 improved_io A/B 비교 | Accepted |
| [D-031](../research/input-and-memory/decisions/D-031-battle-field-guide.md) | B 행동 입력 필드 설명서 | Accepted |
| [D-032](../research/input-and-memory/decisions/D-032-battle-guide-live.md) | 필드 설명서 v1.1.0 실제 Cloud 병렬 배틀 | Accepted |
| [D-033](../research/input-and-memory/decisions/D-033-battle-guide-direct32.md) | 사전 검증 생략 32판과 오류 턴 표시 | Accepted |
| [D-034](../research/input-and-memory/decisions/D-034-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Accepted |
| [D-036](../research/input-and-memory/decisions/D-036-calculator-inputfix32.md) | 교정 입력·계산기 동일32판 | Accepted |
| [D-038](../research/input-and-memory/decisions/D-038-battle-guide-movefix32.md) | 수정 완료본 A/B32판 새 실행 | Accepted |
| [D-039](../research/input-and-memory/decisions/D-039-external-memory-repeat32.md) | 외부 메모리 장애 기록 및 동일 조건 재실험 | Accepted |
| [D-041](../research/input-and-memory/decisions/D-041-a-diagnostic64.md) | Smogon 원본 A64 진단 실행 | Accepted |
| [D-042](../research/input-and-memory/decisions/D-042-ab-head-to-head32.md) | 원본 A 대 변경 구성 B 직접 대결32경기 | Accepted |
| [D-044](../research/input-and-memory/decisions/D-044-ab-head-to-head32-protectfix.md) | Protect 수정본 직접32 연속 실행 | Accepted |
| [D-047](../research/input-and-memory/decisions/D-047-ab-head-to-head32-b2.md) | B2 직접대결32 실행 | Accepted |
| [D-063](../research/input-and-memory/decisions/D-063-intermediate-research-objectives.md) | 입력 정보·이력·요약의 중간 연구 목표 채택 | Accepted |
| [D-071](../research/model-evaluation/decisions/D-071-jev-battle.md) | JEV Choice 배틀 연결 | Accepted |
| [D-094](../research/input-and-memory/decisions/D-094-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Accepted |
| [D-096](../research/policy-learning/decisions/D-096-pokemon-training-objective.md) | 세 RLCD 환경을 활용한 포켓몬 전용 학습 당면 목표 채택 | Accepted |
| [D-167](../research/input-and-memory/decisions/D-167-candidate-matchup-summary.md) | 후보별 현재 상대 적용결과 보강 | Accepted |
| [D-168](../research/input-and-memory/decisions/D-168-openai-candidate-matchup-battle.md) | 후보별 상성 요약 OpenAI 동일32경기 | Accepted |
| [EP-011](../research/input-and-memory/plans/EP-011-improved-io.md) | IO 개선 및 병렬 3조건 비교 | Blocked |
| [EP-012](../research/input-and-memory/plans/EP-012-summary-harness-diagnostics.md) | 요약 harness 기여도 진단 | Blocked |
| [EP-013](../research/input-and-memory/plans/EP-013-state-summary-thinking.md) | 상태 처리 정비와 요약 thinking 비교 | Blocked |
| [EP-014](../shared/governance/plans/EP-014-agent-instruction-maintenance.md) | 승인·중단 지시와 현재 상태 정합화 | Completed |
| [EP-015](../research/input-and-memory/plans/EP-015-summary-max-diagnostic.md) | 요약 thinking low/max 진단 | Blocked — 입력·평가 기준 불일치로 전체 무효, 진단 미완료 |
| [EP-016](../research/input-and-memory/plans/EP-016-input-summary-documentation.md) | 현재 입력·요약 구조 문서화 | Completed |
| [EP-017](../shared/governance/plans/EP-017-experiment-defect-recovery.md) | 테스트·평가 결함 복구 절차 문서화 | Completed |
| [EP-018](../research/input-and-memory/plans/EP-018-io-battle-only.md) | 요약 없는 improved_io A/B 비교 | Blocked — 구현·검증·중단 보고 완료, Cloud gate 미충족으로 비교 미완료 |
| [EP-019](../research/input-and-memory/plans/EP-019-battle-field-guide.md) | B 행동 입력 필드 설명서 | Completed |
| [EP-020](../research/input-and-memory/plans/EP-020-battle-guide-live.md) | 필드 설명서 실제 Cloud 병렬 배틀 | Blocked — 구현·로컬 검증·중단 보고 완료, Cloud 기술 gate 실패로 실제 비교 미완료 |
| [EP-021](../research/input-and-memory/plans/EP-021-battle-guide-direct32.md) | 사전 검증 생략 32판과 오류 턴 표시 | Completed |
| [EP-022](../research/input-and-memory/plans/EP-022-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Completed — 사용자 중단 대안 포함 완료; 성능 비교 미완료 |
| [EP-024](../research/input-and-memory/plans/EP-024-calculator-inputfix32.md) | 교정 입력·계산기 동일 조건 A/B32판 | Completed |
| [EP-026](../research/input-and-memory/plans/EP-026-battle-guide-movefix32.md) | 수정 완료본 A/B32판 본 실험 | Completed — 승인된 중단 포함 작업 완료, 성능 비교 미완료 |
| [EP-027](../research/input-and-memory/plans/EP-027-external-memory-repeat32.md) | 외부 메모리 장애 후 동일 조건32판 재실험 | Completed |
| [EP-028](../research/input-and-memory/plans/EP-028-smogon-diagnostic-design.md) | Smogon 기반 원본 A 진단 평가 준비 | Completed — 평가 준비 구현·로컬 검증 완료, 대전 미실행 |
| [EP-029](../research/input-and-memory/plans/EP-029-a-diagnostic64.md) | Smogon 원본 A64 진단 실행 | Completed |
| [EP-030](../research/input-and-memory/plans/EP-030-ab-head-to-head32.md) | 원본 A 대 변경 구성 B 직접 대결32경기 | Blocked — 계산 결함 중단, 직접비교 미완료 |
| [EP-032](../research/input-and-memory/plans/EP-032-ab-head-to-head32-protectfix.md) | Protect 수정본 A/B 직접대결32 | Blocked |
| [EP-034](../research/input-and-memory/plans/EP-034-b-prompt-optimization.md) | B 판단 정보 보존형 프롬프트 최적화 | Completed |
| [EP-035](../research/input-and-memory/plans/EP-035-ab-head-to-head32-b2.md) | B2 적용 A/B 직접대결32 | Blocked |
| [EP-038](../shared/governance/plans/EP-038-io-explanation-review-opt-in.md) | 기본 IO 테스트 설명 오류 기입 명시 선택 | Completed |
| [EP-052](../research/input-and-memory/plans/EP-052-intermediate-research-objectives.md) | 입력 정보·메모리 설계 중간 연구 목표 문서화 | Completed |
| [EP-058](../research/input-and-memory/plans/EP-058-official-async.md) | 공식 관측 비동기 처리 교정 | Completed |
| [EP-069](../shared/viewers/plans/EP-069-researcher-viewer.md) | 실험자용 JEV 뷰어 가독성 | Completed |
| [EP-072](../shared/viewers/plans/EP-072-viewer-navigation-hp.md) | 뷰어 단축키·상대 HP 비율 표시 | Completed |
| [EP-105](../shared/viewers/plans/EP-105-viewer-action-names.md) | 뷰어 결정의 실제 기술·포켓몬 이름 표시 | Completed |
| [EP-140](../research/input-and-memory/plans/EP-140-jev-public-memory-v6.md) | 공개 정보 v6·턴 로그 뷰어·JEV 27B/9B 재평가 | Blocked |
| [EP-141](../research/input-and-memory/plans/EP-141-jev-v6-corrected-evaluation.md) | 교정 v6의27B/9B 신규64평가 | Completed |
| [EP-142](../shared/viewers/plans/EP-142-jev-damage-viewer.md) | EX-088·089 Damage-calc 시나리오 탭 | Completed |
| [EP-169](../research/rule-learning/plans/EP-169-showdown-ruleqa.md) | Showdown 규칙 Q&A·State 데이터셋 v1 | Completed |
| [EP-182](../research/input-and-memory/plans/EP-182-candidate-matchup-summary.md) | 후보별 현재 대면 상성·효과 요약 | Completed |
| [EP-183](../research/input-and-memory/plans/EP-183-openai-candidate-matchup-battle.md) | 후보별 상성 요약 OpenAI 32경기 | Blocked |
| [EX-017](../research/input-and-memory/experiments/EX-017-improved-io-offline.md) | 개선 IO 오프라인 검증 | Stopped |
| [EX-020](../research/input-and-memory/experiments/EX-020-resume-io.md) | 개선 IO 재실험 | Blocked |
| [EX-021](../research/input-and-memory/experiments/EX-021-summary-harness-diagnostics.md) | 요약 오류의 harness 기여도 비교 | Blocked (invalidated / 진단 미완료) |
| [EX-022](../research/input-and-memory/experiments/EX-022-state-summary-thinking.md) | 상태 처리 정비 후 요약 thinking 비교 | Blocked / invalidated / 진단 미완료 |
| [EX-023](../research/input-and-memory/experiments/EX-023-continue-io.md) | 상태 교정 후 개선 IO 실험 재개 | Blocked |
| [EX-024](../research/input-and-memory/experiments/EX-024-low-summary-prompt-reexperiment.md) | low 요약 지시 개선 후 IO 재실험 | Blocked |
| [EX-025](../research/input-and-memory/experiments/EX-025-summary-max-diagnostic.md) | 요약 thinking low/max 진단 | Invalidated — 전체 중단·진단 미완료 |
| [EX-026](../research/input-and-memory/experiments/EX-026-io-battle-only.md) | 요약 없는 improved_io A/B 비교 | Blocked — Cloud 출력·의미 gate 실패, A/B 비교 미완료 |
| [EX-027](../research/input-and-memory/experiments/EX-027-battle-guide-live.md) | 필드 설명서 v1.1.0 실제 Cloud 병렬 배틀 | Stopped — Cloud 출력 계약 실패, 실제 비교 미완료 |
| [EX-028](../research/input-and-memory/experiments/EX-028-battle-guide-direct32.md) | 사전 검증 생략 32판 비교 | Completed — 32 slot 처리 완료, 16쌍 비교 미완료 |
| [EX-029](../research/input-and-memory/experiments/EX-029-calculator-entry-calcfix32.md) | 계산기 교정 동일 조건 A/B32판 | Completed — 승인된 중단 포함 작업 완료; 32판 성능 비교 미완료 |
| [EX-031](../research/input-and-memory/experiments/EX-031-calculator-inputfix32.md) | 교정 입력·계산기 동일 조건 A/B32판 | Completed — 중단 포함 작업 완료, 성능 비교 미완료 |
| [EX-032](../research/input-and-memory/experiments/EX-032-battle-guide-movefix32.md) | 수정 완료본 A/B32판 | Completed — 승인된 중단 포함 작업 완료, 성능 비교 미완료 |
| [EX-033](../research/input-and-memory/experiments/EX-033-external-memory-repeat32.md) | 외부 메모리 장애 후 동일 조건32판 | Completed |
| [EX-034](../research/input-and-memory/experiments/EX-034-smogon-diagnostic-design.md) | Smogon 기반 원본 A 운용 한계 진단 설계 | Prepared — 팀·대진·검토·자원 명세 검증 완료, 대전 미실행 |
| [EX-035](../research/input-and-memory/experiments/EX-035-a-diagnostic64.md) | Smogon 원본 A64 진단 실험 | Completed — 유효64/64·A50승14패·1902결정 전수검토·보고·보존/정리 완료 |
| [EX-036](../research/input-and-memory/experiments/EX-036-ab-head-to-head32.md) | 원본 A 대 변경 구성 B 직접 대결32경기 | Stopped — 계산 결함 중단, 직접비교 미완료 |
| [EX-037](../research/input-and-memory/experiments/EX-037-ab-head-to-head32-protectfix.md) | Protect 수정본 A/B 직접대결32 | Blocked / 비교 미완료 |
| [EX-038](../research/input-and-memory/experiments/EX-038-ab-head-to-head32-b2.md) | 원본 A 대 B2 직접대결32 | Blocked |
| [EX-039](../research/lead-policy/experiments/EX-039-b2-lead-proposal.md) | B2 seeded_random 대 llm_lead 선봉 정책 대응 비교 | Stopped / 비교 미완료 — 사용자 지시로 실행·감시 종료, 미실행12경기 보존 |
| [EX-040](../research/lead-policy/experiments/EX-040-b2-lead-zai.md) | Z.ai B2 seeded_random 대 llm_lead32 | Stopped / 첫 HTTP429 중단·비교 미완료 |
| [EX-041](../research/lead-policy/experiments/EX-041-b2-lead-zai4.md) | Z.ai B2 seeded_random 대 llm_lead32 | Incomplete / 수집·보고·보존·정리 완료, 비교 미완료 |
| [EX-042](../research/lead-policy/experiments/EX-042-distributed-lead.md) | Ollama Cloud·Z.ai 분산 B2 선봉 정책 비교 | Incomplete |
| [EX-043](../research/lead-policy/experiments/EX-043-corrected-lead.md) | 교정된 B2 개선 선봉 대 무작위 선봉 | Incomplete |
| [EX-045](../research/lead-policy/experiments/EX-045-official-lead.md) | 공식 관측 B2 기반 LLM 선봉 정책 본실험 | Incomplete |
| [EX-047](../research/model-evaluation/experiments/EX-047-jev-battle.md) | JEV Choice 소규모 배틀 진단 | Incomplete |
| [EX-051](../research/input-and-memory/experiments/EX-051-jev-v2-battle.md) | JEV 교정 입력 v2 동일 조건2경기 | Completed |
| [EX-052](../research/model-evaluation/experiments/EX-052-jev-abyssal32.md) | JEV 대 Abyssal 32경기 | Completed |
| [EX-053](../research/input-and-memory/experiments/EX-053-jev-v3-abyssal32.md) | JEV 대 Abyssal 32경기 | Incomplete |
| [EX-054](../research/input-and-memory/experiments/EX-054-jev-v3-retry32.md) | 재시도3회 적용 JEV v3 동일32경기 | Incomplete |
| [EX-058](../research/input-and-memory/experiments/EX-058-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EX-059](../research/input-and-memory/experiments/EX-059-jev-compact32.md) | 자기 벤치 축약 JEV 입력 동일32경기 | Completed |
| [EX-060](../research/action-value/experiments/EX-060-single-battle-branch-rollouts.md) | EX-058 battle-19 분기 데이터 추출 | Completed |
| [EX-086](../research/input-and-memory/experiments/EX-086-jev27b-public-memory-v6.md) | JEV-27B 공개 정보 v6 신규32경기 | Blocked |
| [EX-109](../research/model-evaluation/experiments/EX-109-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Stopped |
| [EX-111](../research/model-evaluation/experiments/EX-111-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Completed |
| [EX-112](../research/input-and-memory/experiments/EX-112-openai-candidate-matchup-battle.md) | 후보별 현재 대면 요약 gpt-6-luna 32경기 | Stopped |

## 추론 / 입력 표현

| ID | 제목 | 상태 |
|---|---|---|
| [D-179](../research/input-and-memory/decisions/D-179-candidate-action-v7.md) | 후보 중심 v7와 응답 복구 탐색 실험 | Accepted |
| [D-181](../research/input-and-memory/decisions/D-181-v7-survival-switch-cost.md) | v7 생존 판단과 교체 기회비용 지침 | Accepted |
| [D-182](../research/input-and-memory/decisions/D-182-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Accepted |
| [EP-202](../research/input-and-memory/plans/EP-202-candidate-action-v7.md) | 후보 중심 v7와 GPT-6 Luna 32경기 | Completed |
| [EP-205](../research/input-and-memory/plans/EP-205-v7-survival-switch-cost.md) | v7 생존 판단과 교체 비용 지시문 개정 | Completed |
| [EP-206](../research/input-and-memory/plans/EP-206-v7-survival-battle32.md) | 개정 v7 GPT-6 Luna 32경기 시작·수집 | Blocked |
| [EX-115](../research/input-and-memory/experiments/EX-115-candidate-action-v7.md) | 후보 중심 v7 GPT-6 Luna 32경기 | Completed |
| [EX-117](../research/input-and-memory/experiments/EX-117-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Stopped |

## 추론 / 전략 planner

| ID | 제목 | 상태 |
|---|---|---|
| [D-139](../research/planner-executor/decisions/D-139-jev-planner-environment.md) | GLM planner–JEV 수행 모델 실험 환경 | Accepted |
| [D-140](../research/planner-executor/decisions/D-140-planner-role-resource-guide.md) | Planner 역할·승리 경로·자원 관리 안내 | Accepted |
| [D-142](../research/planner-executor/decisions/D-142-planner-first-battle-sample.md) | EX-088 첫 대진의 planner–JEV 샘플 실행 | Accepted |
| [D-143](../research/planner-executor/decisions/D-143-executor-goal-completion.md) | JEV의 계획 목표 충족 여부 확인 | Accepted |
| [D-145](../research/planner-executor/decisions/D-145-goal-completion-sample.md) | 바뀐 수행 프롬프트의 실제 샘플1경기 | Accepted |
| [D-146](../research/planner-executor/decisions/D-146-planner-json-retries.md) | GLM JSON 구문 오류 최대5회 재시도·새 샘플 | Accepted |
| [D-147](../research/planner-executor/decisions/D-147-planner-unlimited-disk.md) | GLM·JEV 향후 실행의 디스크 용량 상한 해제 | Accepted |
| [D-150](../research/planner-executor/decisions/D-150-planner-format-retries-temperature-zero.md) | GLM 응답 형식 재시도·기본 temperature0 | Accepted |
| [D-151](../research/planner-executor/decisions/D-151-planner-high-effort-sample.md) | GLM high 추론 강도 동일 대진 샘플 | Accepted |
| [D-152](../research/planner-executor/decisions/D-152-planner-unlimited-time-max-output.md) | 경기/전체 시간 상한 해제·GLM 최대 출력 새1경기 | Accepted |
| [D-153](../research/planner-executor/decisions/D-153-glm53-low-sample.md) | GLM-5.3 low 동일 대진 새1경기 | Accepted |
| [D-155](../research/planner-executor/decisions/D-155-matchup-events-high.md) | 매치업 사건 GLM high 동일 대진 | Accepted |
| [EP-145](../research/planner-executor/plans/EP-145-jev-planner-environment.md) | GLM planner–JEV 실험 설정 환경 | Completed |
| [EP-146](../research/planner-executor/plans/EP-146-planner-role-resource-guide.md) | Planner 역할·승리 경로·자원 안내 | Completed |
| [EP-148](../research/planner-executor/plans/EP-148-planner-first-battle-sample.md) | GLM planner–JEV 첫 실제 샘플 | Completed |
| [EP-149](../research/planner-executor/plans/EP-149-executor-goal-completion.md) | JEV 계획 목표 충족 확인 지시 | Completed |
| [EP-151](../research/planner-executor/plans/EP-151-planner-goal-completion-sample.md) | 변경 수행 프롬프트 샘플1경기 | Blocked |
| [EP-152](../research/planner-executor/plans/EP-152-planner-json-retry-sample.md) | GLM JSON 구문 재시도·샘플1경기 | Completed |
| [EP-153](../research/planner-executor/plans/EP-153-planner-unlimited-disk.md) | GLM·JEV 디스크 상한 해제 | Completed |
| [EP-156](../research/planner-executor/plans/EP-156-planner-format-temperature-zero.md) | GLM 형식 재시도·temperature0 실제1경기 | Completed |
| [EP-157](../research/planner-executor/plans/EP-157-planner-high-effort-sample.md) | GLM high 추론 강도 실제1경기 | Blocked |
| [EP-158](../research/planner-executor/plans/EP-158-planner-unlimited-time-max-output.md) | 시간 상한 없는 GLM 최대 출력 실제1경기 | Completed |
| [EX-092](../research/planner-executor/experiments/EX-092-planner-first-battle-sample.md) | EX-088 첫 대진의 GLM planner–JEV 샘플 | Completed |
| [EX-093](../research/planner-executor/experiments/EX-093-planner-goal-completion-sample.md) | 목표 충족 확인 지시문 적용 샘플1경기 | Blocked |
| [EX-094](../research/planner-executor/experiments/EX-094-planner-json-retry-sample.md) | GLM JSON 구문 재시도 적용 샘플 | Completed |
| [EX-097](../research/planner-executor/experiments/EX-097-planner-format-temperature-zero.md) | GLM 형식 재시도·temperature0 NVFP4 샘플1경기 | Completed |
| [EX-098](../research/planner-executor/experiments/EX-098-planner-high-effort-sample.md) | GLM high 추론 강도 NVFP4 동일 대진1경기 | Blocked |
| [EX-099](../research/planner-executor/experiments/EX-099-planner-unlimited-time-max-output.md) | 시간 상한 없는 GLM 최대 출력 NVFP4 샘플1경기 | Completed |
| [EX-100](../research/planner-executor/experiments/EX-100-glm53-low-sample.md) | GLM-5.3 low 동일 대진 NVFP4 샘플1경기 | Completed |
| [EX-102](../research/planner-executor/experiments/EX-102-matchup-events-high.md) | 매치업 사건 기반 GLM high 동일 대진 | Completed |

## 추론 / 행렬 탐색

| ID | 제목 | 상태 |
|---|---|---|
| [EX-080](../research/fixed-matchup-learning/experiments/EX-080-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Completed — 시도 3 학습(round40 둔화 종료)·선택(round36)·잠긴 test·감사/뷰어/봉인·정리 완료; 주효능 미입증 (시도 1·2는 도구 결함으로 학습 전 중단·보존) |

## 평가 / System1

| ID | 제목 | 상태 |
|---|---|---|
| [D-186](../research/rule-learning/decisions/D-186-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Accepted |
| [EP-211](../research/rule-learning/plans/EP-211-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |
| [EX-123](../research/rule-learning/experiments/EX-123-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |

## 평가 / 고정 대진

| ID | 제목 | 상태 |
|---|---|---|
| [D-034](../research/input-and-memory/decisions/D-034-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Accepted |
| [D-036](../research/input-and-memory/decisions/D-036-calculator-inputfix32.md) | 교정 입력·계산기 동일32판 | Accepted |
| [D-083](../research/input-and-memory/decisions/D-083-jev-v3-abyssal32.md) | JEV v3 동일32경기와 v2 전후 비교 | Accepted |
| [D-088](../research/input-and-memory/decisions/D-088-jev-direct32.md) | EX-056 사전 검증 생략 동일32경기 | Accepted |
| [D-094](../research/input-and-memory/decisions/D-094-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Accepted |
| [D-095](../research/input-and-memory/decisions/D-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Accepted |
| [D-110](../research/model-evaluation/decisions/D-110-kev-test-battles.md) | 기존 test 대진의 Kev 본 배틀 | Accepted |
| [D-115](../research/policy-learning/decisions/D-115-abyssal-first-objective.md) | Abyssal 상대 효율적 승리를 당면 단기 목표로 채택 | Accepted |
| [D-119](../research/fixed-matchup-learning/decisions/D-119-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 정책 학습 | Accepted |
| [D-120](../research/fixed-matchup-learning/decisions/D-120-fixed-matchup-run.md) | 고정 대진 GPU 학습·실험 실행 | Accepted |
| [D-122](../research/fixed-matchup-learning/decisions/D-122-fixed-matchup-day.md) | 하루 내 예상 시 고정 대진 실행 | Accepted |
| [D-127](../research/fixed-matchup-learning/decisions/D-127-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Accepted |
| [D-130](../research/model-evaluation/decisions/D-130-jev27b-ex058-reproduction.md) | JEV-27B 공개 가중치로 개선 입력 동일32 평가 | Accepted |
| [D-133](../research/model-evaluation/decisions/D-133-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책 동일32경기 | Accepted |
| [D-134](../research/model-evaluation/decisions/D-134-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32경기 | Accepted |
| [D-137](../research/input-and-memory/decisions/D-137-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 평가 | Accepted |
| [D-138](../research/model-evaluation/decisions/D-138-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 평가 | Accepted |
| [D-168](../research/input-and-memory/decisions/D-168-openai-candidate-matchup-battle.md) | 후보별 상성 요약 OpenAI 동일32경기 | Accepted |
| [D-184](../research/policy-learning/decisions/D-184-laya-team-generalization.md) | laya 모방 모델의 새 팀 일반화 평가 | Accepted |
| [D-185](../research/policy-learning/decisions/D-185-laya-modular-renderer-v2.md) | laya 모듈형 렌더러 v2(기술 변형·속도·교체·피해량) | Accepted |
| [D-187](../research/policy-learning/decisions/D-187-laya-tera-knowledge.md) | laya v2에 테라 기본 지식 데이터 추가(GPU1) | Accepted |
| [D-188](../research/policy-learning/decisions/D-188-laya-effect-knowledge.md) | laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2) | Accepted |
| [D-189](../research/policy-learning/decisions/D-189-laya-renderer-v3-opponent-sets.md) | laya 렌더러 v3(상대 세트 추론)와 래더 대비 학습(GPU0) | Accepted |
| [D-190](../research/policy-learning/decisions/D-190-laya-ex129-gate-override.md) | EX-128 진행 조건 미충족에도 EX-129 배틀 실행(사용자 결정) | Accepted |
| [D-191](../research/policy-learning/decisions/D-191-no-offline-battle-gate.md) | 오프라인 test 평가로 배틀 평가를 거르지 않는다 | Accepted |
| [D-192](../research/policy-learning/decisions/D-192-laya-renderer-v4-fail-out.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해)와 GPU1 학습·배틀 | Accepted |
| [D-193](../research/policy-learning/decisions/D-193-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방(GPU0 학습·배틀) | Accepted |
| [D-194](../research/policy-learning/decisions/D-194-laya-head-to-head-evaluation.md) | laya 직접 대결 평가(GPU2, EX-120 일정) | Accepted |
| [D-195](../research/policy-learning/decisions/D-195-laya-item-state-renderer-v5.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터)와 학습·배틀 | Accepted |
| [D-196](../research/policy-learning/decisions/D-196-laya-v2t-corrected-input-battle.md) | laya v2+테라(EX-124)를 재학습 없이 D-195 보정 입력으로 배틀(GPU1) | Accepted |
| [D-197](../research/policy-learning/decisions/D-197-laya-v2t-tera-decision-defence.md) | laya v2+테라(EX-124) fix 입력에서 테라 합산 결정과 테라 방어 문구 배틀(재학습 없음, GPU1) | Accepted |
| [EP-022](../research/input-and-memory/plans/EP-022-calculator-entry-calcfix32.md) | 계산기 등장 특성 교정 및 동일32판 | Completed — 사용자 중단 대안 포함 완료; 성능 비교 미완료 |
| [EP-027](../research/input-and-memory/plans/EP-027-external-memory-repeat32.md) | 외부 메모리 장애 후 동일 조건32판 재실험 | Completed |
| [EP-075](../research/input-and-memory/plans/EP-075-jev-v3-abyssal32.md) | JEV v3 동일32경기와 v2 전후 비교 | Blocked |
| [EP-077](../research/input-and-memory/plans/EP-077-jev-v3-retry32.md) | EX-054 재시도3회 동일32경기 | Blocked |
| [EP-080](../research/input-and-memory/plans/EP-080-jev-direct32.md) | EX-056 사전 검증 생략 동일32경기 | Blocked |
| [EP-094](../research/input-and-memory/plans/EP-094-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EP-095](../research/input-and-memory/plans/EP-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Completed |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-124](../research/fixed-matchup-learning/plans/EP-124-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 구현 | Completed — 구현·CPU 개발 검증 완료, 실험 미실행 |
| [EP-126](../research/fixed-matchup-learning/plans/EP-126-fixed-matchup-day.md) | 하루 내 고정 대진 실험 | Paused — 사용자 요청 중지; 학습·test 미시작 |
| [EP-130](../research/fixed-matchup-learning/plans/EP-130-first-round-model-comparison.md) | 첫라운드 전후 동일 관측 비교 | Completed |
| [EP-131](../research/fixed-matchup-learning/plans/EP-131-fixed-matchup-stopping.md) | 종료조건 기반 추가 학습·독립 평가 | Completed |
| [EP-132](../research/fixed-matchup-learning/plans/EP-132-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 자기대국 학습 실행 | Completed |
| [EP-134](../research/model-evaluation/plans/EP-134-jev27b-ex058-reproduction.md) | JEV-27B 개선 입력 동일32 재현 | Blocked |
| [EP-136](../shared/governance/plans/EP-136-branch-research-manuals.md) | 분리된 연구선의 매뉴얼 정비 | Completed |
| [EP-138](../research/model-evaluation/plans/EP-138-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책 동일32 평가 | Completed |
| [EP-139](../research/model-evaluation/plans/EP-139-jev9b-single-choice.md) | JEV-9B 단일 Choice 동일32 평가 | Completed |
| [EP-209](../research/policy-learning/plans/EP-209-laya-team-generalization.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Active |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Active |
| [EP-217](../research/policy-learning/plans/EP-217-laya-head-to-head-evaluation.md) | laya 직접 대결 평가 하네스와 벤치마크(GPU2) | Active |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Active |
| [EP-219](../research/policy-learning/plans/EP-219-laya-v2t-corrected-input-battle.md) | laya v2+테라 보정 입력 배틀(재학습 없음, GPU1) | Completed |
| [EP-220](../research/policy-learning/plans/EP-220-laya-v2t-tera-decision-defence.md) | laya v2+테라 fix 입력 테라 합산 결정·테라 방어 문구 배틀(재학습 없음, GPU1) | Active |
| [EX-033](../research/input-and-memory/experiments/EX-033-external-memory-repeat32.md) | 외부 메모리 장애 후 동일 조건32판 | Completed |
| [EX-046](../research/lead-policy/experiments/EX-046-async-official-lead.md) | 비동기 교정본 공식 관측 B2 선봉 본실험 | Completed |
| [EX-054](../research/input-and-memory/experiments/EX-054-jev-v3-retry32.md) | 재시도3회 적용 JEV v3 동일32경기 | Incomplete |
| [EX-056](../research/input-and-memory/experiments/EX-056-jev-direct32.md) | 사전 검증 없이 동일 조건32경기 재실험 | Incomplete |
| [EX-058](../research/input-and-memory/experiments/EX-058-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EX-059](../research/input-and-memory/experiments/EX-059-jev-compact32.md) | 자기 벤치 축약 JEV 입력 동일32경기 | Completed |
| [EX-069](../research/model-evaluation/experiments/EX-069-kev-test-battles.md) | EX-065 test20 고정 대진의 Kev 본 테스트 | Completed |
| [EX-077](../research/fixed-matchup-learning/experiments/EX-077-fixed-matchup-day.md) | 하루 내 고정 대진 공개 상태 학습 | Incomplete — 사용자 요청 중지; 학습/test 미시작 |
| [EX-079](../research/fixed-matchup-learning/experiments/EX-079-fixed-matchup-stopping.md) | 종료조건 기반 고정 대진 추가 학습 | Completed — 추가학습·시험·감사/뷰어·정리 완료; 주효능 기준 미달 |
| [EX-080](../research/fixed-matchup-learning/experiments/EX-080-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Completed — 시도 3 학습(round40 둔화 종료)·선택(round36)·잠긴 test·감사/뷰어/봉인·정리 완료; 주효능 미입증 (시도 1·2는 도구 결함으로 학습 전 중단·보존) |
| [EX-082](../research/model-evaluation/experiments/EX-082-jev27b-ex058-reproduction.md) | JEV-27B로 EX-058 개선 입력 동일32 평가 | Blocked |
| [EX-083](../research/model-evaluation/experiments/EX-083-jev27b-four-gpu-continuation.md) | JEV-27B 4GPU 잔여9경기 계승 평가 | Completed |
| [EX-084](../research/model-evaluation/experiments/EX-084-quyet-medium-two-stage.md) | Quyet-Medium 2단계 정책의 EX-083 동일32경기 평가 | Completed |
| [EX-085](../research/model-evaluation/experiments/EX-085-jev9b-single-choice.md) | JEV-9B의 EX-083 설정 기반 동일32경기 평가 | Completed |
| [EX-086](../research/input-and-memory/experiments/EX-086-jev27b-public-memory-v6.md) | JEV-27B 공개 정보 v6 신규32경기 | Blocked |
| [EX-088](../research/input-and-memory/experiments/EX-088-jev27b-v6-corrected.md) | 교정 v6 JEV-27B 신규32경기 | Completed |
| [EX-089](../research/input-and-memory/experiments/EX-089-jev9b-v6-corrected.md) | 교정 v6 JEV-9B 신규32경기 | Completed |
| [EX-090](../research/input-and-memory/experiments/EX-090-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 신규32경기 | Completed |
| [EX-091](../research/model-evaluation/experiments/EX-091-minicpm5-2b-jev.md) | MiniCPM5-2B-Jev 계산기 포함 신규32경기 | Completed |
| [EX-109](../research/model-evaluation/experiments/EX-109-openai-decisions-v6-battle32.md) | OpenAI Decisions v6 상세32경기 | Stopped |
| [EX-110](../research/model-evaluation/experiments/EX-110-openai-decisions-retry32.md) | OpenAI Decisions 통신 재시도 새32경기 | Completed |
| [EX-111](../research/model-evaluation/experiments/EX-111-jevk5-v6-battle32.md) | JevK5-9B v6 상세32경기 | Completed |
| [EX-120](../research/policy-learning/experiments/EX-120-laya-team-generalization128.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EX-122](../research/policy-learning/experiments/EX-122-laya-v1-v2-battle256.md) | laya v1·v2 같은 실행 256경기 비교 (EX-120 일정) | Completed |
| [EX-125](../research/policy-learning/experiments/EX-125-laya-v2-tera-battle256.md) | laya v2와 v2+테라 지식 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-127](../research/policy-learning/experiments/EX-127-laya-v2t-v2te-battle256.md) | laya v2+테라와 v2+테라+효과 지식 같은 실행 256경기(GPU2, EX-120 일정) | Completed |
| [EX-129](../research/policy-learning/experiments/EX-129-laya-v2t-v3t-battle256.md) | laya v2+테라와 v3+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-131](../research/policy-learning/experiments/EX-131-laya-v2t-v4t-battle256.md) | laya v2+테라와 v4+테라 같은 실행 256경기(GPU1, EX-120 일정) | Planned |
| [EX-133](../research/policy-learning/experiments/EX-133-laya-v2t-v2tw-battle256.md) | laya v2+테라와 v2+테라 승패 가중 모방 같은 실행 256경기(GPU0, EX-120 일정) | Planned |
| [EX-134](../research/policy-learning/experiments/EX-134-laya-head-to-head512.md) | laya v2+테라 대 v2·v1·v2+테라+효과·v3+테라 직접 대결 512경기(GPU2, EX-120 일정) | Running |
| [EX-135](../research/policy-learning/experiments/EX-135-laya-head-to-head-v2tw-v4t.md) | laya v2+테라 대 승패 가중·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Planned |
| [EX-137](../research/policy-learning/experiments/EX-137-laya-v4t-v5t-battle256.md) | laya v4+테라와 v5+테라 같은 실행 256경기(GPU0, EX-120 일정) | Planned |
| [EX-138](../research/policy-learning/experiments/EX-138-laya-head-to-head-v5t.md) | laya v5+테라 대 v2+테라·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Planned |
| [EX-139](../research/policy-learning/experiments/EX-139-laya-v2t-corrected-input-battle256.md) | laya v2+테라(EX-124) 보정 입력 fix·info 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-140](../research/policy-learning/experiments/EX-140-laya-v2t-tera-decision-defence384.md) | laya v2+테라(EX-124) fix 입력 테라 합산 결정(k=1·3)과 테라 방어 문구 384경기(GPU1, EX-120 일정) | Running |

## 평가 / 고정대진32경기

| ID | 제목 | 상태 |
|---|---|---|
| [EP-191](../research/rule-learning/plans/EP-191-jevk5-ruleqa-battle32.md) | 학습 JevK5 LoRA 실전32 실행 | Completed |
| [EX-114](../research/rule-learning/experiments/EX-114-jevk5-ruleqa-battle32.md) | 학습 JevK5 선택형 LoRA 실전32 | Completed |

## 평가 / 독립 선택형

| ID | 제목 | 상태 |
|---|---|---|
| [D-180](../research/rule-learning/decisions/D-180-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Accepted |
| [D-183](../research/policy-learning/decisions/D-183-laya-compact-imitation.md) | laya 압축 입력 모방 학습과 표준 배틀 평가 | Accepted |
| [D-185](../research/policy-learning/decisions/D-185-laya-modular-renderer-v2.md) | laya 모듈형 렌더러 v2(기술 변형·속도·교체·피해량) | Accepted |
| [D-187](../research/policy-learning/decisions/D-187-laya-tera-knowledge.md) | laya v2에 테라 기본 지식 데이터 추가(GPU1) | Accepted |
| [D-188](../research/policy-learning/decisions/D-188-laya-effect-knowledge.md) | laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2) | Accepted |
| [D-189](../research/policy-learning/decisions/D-189-laya-renderer-v3-opponent-sets.md) | laya 렌더러 v3(상대 세트 추론)와 래더 대비 학습(GPU0) | Accepted |
| [D-190](../research/policy-learning/decisions/D-190-laya-ex129-gate-override.md) | EX-128 진행 조건 미충족에도 EX-129 배틀 실행(사용자 결정) | Accepted |
| [D-191](../research/policy-learning/decisions/D-191-no-offline-battle-gate.md) | 오프라인 test 평가로 배틀 평가를 거르지 않는다 | Accepted |
| [D-192](../research/policy-learning/decisions/D-192-laya-renderer-v4-fail-out.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해)와 GPU1 학습·배틀 | Accepted |
| [D-193](../research/policy-learning/decisions/D-193-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방(GPU0 학습·배틀) | Accepted |
| [D-195](../research/policy-learning/decisions/D-195-laya-item-state-renderer-v5.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터)와 학습·배틀 | Accepted |
| [EP-203](../research/rule-learning/plans/EP-203-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Active |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Active |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Active |
| [EX-116](../research/rule-learning/experiments/EX-116-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Running |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Running |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Planned |

## 평가 / 배틀

| ID | 제목 | 상태 |
|---|---|---|
| [D-179](../research/input-and-memory/decisions/D-179-candidate-action-v7.md) | 후보 중심 v7와 응답 복구 탐색 실험 | Accepted |
| [D-182](../research/input-and-memory/decisions/D-182-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Accepted |
| [D-184](../research/policy-learning/decisions/D-184-laya-team-generalization.md) | laya 모방 모델의 새 팀 일반화 평가 | Accepted |
| [D-186](../research/rule-learning/decisions/D-186-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Accepted |
| [D-194](../research/policy-learning/decisions/D-194-laya-head-to-head-evaluation.md) | laya 직접 대결 평가(GPU2, EX-120 일정) | Accepted |
| [D-196](../research/policy-learning/decisions/D-196-laya-v2t-corrected-input-battle.md) | laya v2+테라(EX-124)를 재학습 없이 D-195 보정 입력으로 배틀(GPU1) | Accepted |
| [D-197](../research/policy-learning/decisions/D-197-laya-v2t-tera-decision-defence.md) | laya v2+테라(EX-124) fix 입력에서 테라 합산 결정과 테라 방어 문구 배틀(재학습 없음, GPU1) | Accepted |
| [EP-202](../research/input-and-memory/plans/EP-202-candidate-action-v7.md) | 후보 중심 v7와 GPT-6 Luna 32경기 | Completed |
| [EP-206](../research/input-and-memory/plans/EP-206-v7-survival-battle32.md) | 개정 v7 GPT-6 Luna 32경기 시작·수집 | Blocked |
| [EP-209](../research/policy-learning/plans/EP-209-laya-team-generalization.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EP-211](../research/rule-learning/plans/EP-211-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |
| [EP-217](../research/policy-learning/plans/EP-217-laya-head-to-head-evaluation.md) | laya 직접 대결 평가 하네스와 벤치마크(GPU2) | Active |
| [EP-219](../research/policy-learning/plans/EP-219-laya-v2t-corrected-input-battle.md) | laya v2+테라 보정 입력 배틀(재학습 없음, GPU1) | Completed |
| [EP-220](../research/policy-learning/plans/EP-220-laya-v2t-tera-decision-defence.md) | laya v2+테라 fix 입력 테라 합산 결정·테라 방어 문구 배틀(재학습 없음, GPU1) | Active |
| [EX-115](../research/input-and-memory/experiments/EX-115-candidate-action-v7.md) | 후보 중심 v7 GPT-6 Luna 32경기 | Completed |
| [EX-117](../research/input-and-memory/experiments/EX-117-v7-survival-battle32.md) | 생존·교체 비용 v7 GPT-6 Luna 32경기 | Stopped |
| [EX-120](../research/policy-learning/experiments/EX-120-laya-team-generalization128.md) | laya 모방 모델 새 팀 128경기 일반화 평가 | Completed |
| [EX-122](../research/policy-learning/experiments/EX-122-laya-v1-v2-battle256.md) | laya v1·v2 같은 실행 256경기 비교 (EX-120 일정) | Completed |
| [EX-123](../research/rule-learning/experiments/EX-123-jevk5-system1-battle32.md) | System One JevK5 선택 어댑터 실전32 | Completed |
| [EX-125](../research/policy-learning/experiments/EX-125-laya-v2-tera-battle256.md) | laya v2와 v2+테라 지식 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-127](../research/policy-learning/experiments/EX-127-laya-v2t-v2te-battle256.md) | laya v2+테라와 v2+테라+효과 지식 같은 실행 256경기(GPU2, EX-120 일정) | Completed |
| [EX-129](../research/policy-learning/experiments/EX-129-laya-v2t-v3t-battle256.md) | laya v2+테라와 v3+테라 같은 실행 256경기(GPU0, EX-120 일정) | Completed |
| [EX-131](../research/policy-learning/experiments/EX-131-laya-v2t-v4t-battle256.md) | laya v2+테라와 v4+테라 같은 실행 256경기(GPU1, EX-120 일정) | Planned |
| [EX-133](../research/policy-learning/experiments/EX-133-laya-v2t-v2tw-battle256.md) | laya v2+테라와 v2+테라 승패 가중 모방 같은 실행 256경기(GPU0, EX-120 일정) | Planned |
| [EX-134](../research/policy-learning/experiments/EX-134-laya-head-to-head512.md) | laya v2+테라 대 v2·v1·v2+테라+효과·v3+테라 직접 대결 512경기(GPU2, EX-120 일정) | Running |
| [EX-135](../research/policy-learning/experiments/EX-135-laya-head-to-head-v2tw-v4t.md) | laya v2+테라 대 승패 가중·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Planned |
| [EX-137](../research/policy-learning/experiments/EX-137-laya-v4t-v5t-battle256.md) | laya v4+테라와 v5+테라 같은 실행 256경기(GPU0, EX-120 일정) | Planned |
| [EX-138](../research/policy-learning/experiments/EX-138-laya-head-to-head-v5t.md) | laya v5+테라 대 v2+테라·v4+테라 직접 대결 256경기(GPU2, EX-120 일정) | Planned |
| [EX-139](../research/policy-learning/experiments/EX-139-laya-v2t-corrected-input-battle256.md) | laya v2+테라(EX-124) 보정 입력 fix·info 같은 실행 256경기(GPU1, EX-120 일정) | Completed |
| [EX-140](../research/policy-learning/experiments/EX-140-laya-v2t-tera-decision-defence384.md) | laya v2+테라(EX-124) fix 입력 테라 합산 결정(k=1·3)과 테라 방어 문구 384경기(GPU1, EX-120 일정) | Running |

## 평가 / 배틀32

| ID | 제목 | 상태 |
|---|---|---|
| [EX-119](../research/policy-learning/experiments/EX-119-laya-compact-imitation-battle32.md) | laya 압축 입력 모방 모델 EX-089 표준 32경기 | Completed |

## 평가 / 서빙 기술 검증

| ID | 제목 | 상태 |
|---|---|---|
| [EP-190](../research/rule-learning/plans/EP-190-jevk5-vllm-serving-check.md) | JevK5 추가 LoRA vLLM 서빙 확인 | Completed |

## 평가 / 오프라인 QA

| ID | 제목 | 상태 |
|---|---|---|
| [D-159](../research/rule-learning/decisions/D-159-showdown-ruleqa.md) | Showdown 규칙 Q&A 데이터셋 v1 | Accepted |
| [D-161](../research/rule-learning/decisions/D-161-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA 1회 | Accepted |
| [EP-169](../research/rule-learning/plans/EP-169-showdown-ruleqa.md) | Showdown 규칙 Q&A·State 데이터셋 v1 | Completed |
| [EP-173](../research/rule-learning/plans/EP-173-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA | Completed |
| [EX-107](../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md) | Tacit-9B 규칙 Q&A LoRA | Completed |

## 평가 / 정보 제거

| ID | 제목 | 상태 |
|---|---|---|
| [D-092](../research/input-and-memory/decisions/D-092-jev-offline-input.md) | JEV 오프라인 입력 표현 개선 | Accepted |
| [D-095](../research/input-and-memory/decisions/D-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Accepted |
| [D-137](../research/input-and-memory/decisions/D-137-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 평가 | Accepted |
| [EP-093](../research/input-and-memory/plans/EP-093-jev-offline-input.md) | JEV 입력 표현 개선·오프라인 검증 | Completed |
| [EP-095](../research/input-and-memory/plans/EP-095-jev-compact32.md) | 자기 벤치 축약 동일32경기 | Completed |
| [EP-143](../research/input-and-memory/plans/EP-143-jev9b-no-damage.md) | JEV-9B 피해 예측 제거와 EX-089 비교 | Completed |
| [EX-058](../research/input-and-memory/experiments/EX-058-jev-improved32.md) | 개선 JEV 입력 동일32경기 | Completed |
| [EX-059](../research/input-and-memory/experiments/EX-059-jev-compact32.md) | 자기 벤치 축약 JEV 입력 동일32경기 | Completed |
| [EX-090](../research/input-and-memory/experiments/EX-090-jev9b-no-damage.md) | JEV-9B 피해 예측 제거 신규32경기 | Completed |

## 학습 / LoRA

| ID | 제목 | 상태 |
|---|---|---|
| [D-098](../research/action-value/decisions/D-098-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 행동가치 학습 | Accepted |
| [D-127](../research/fixed-matchup-learning/decisions/D-127-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Accepted |
| [D-161](../research/rule-learning/decisions/D-161-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA 1회 | Accepted |
| [D-169](../research/rule-learning/decisions/D-169-jevk5-ruleqa-lora.md) | JevK5 규칙 선택형 추가 LoRA | Accepted |
| [D-180](../research/rule-learning/decisions/D-180-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Accepted |
| [EP-102](../research/action-value/plans/EP-102-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 학습 검증 | Completed |
| [EP-108](../research/action-value/plans/EP-108-joint-q-training.md) | EX-065 기반 Base 공동 q 학습 | Blocked |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-116](../research/policy-learning/plans/EP-116-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정 | Completed |
| [EP-132](../research/fixed-matchup-learning/plans/EP-132-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 자기대국 학습 실행 | Completed |
| [EP-133](../research/action-value/plans/EP-133-joint-q-battle.md) | EX066 epoch3의 GPU0 실제 배틀 평가 | Completed |
| [EP-173](../research/rule-learning/plans/EP-173-tacit-ruleqa-lora.md) | Tacit 규칙 Q&A LoRA | Completed |
| [EP-184](../research/rule-learning/plans/EP-184-jevk5-ruleqa-lora.md) | JevK5 규칙 선택형 추가 LoRA | Completed |
| [EP-203](../research/rule-learning/plans/EP-203-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EX-061](../research/action-value/experiments/EX-061-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 행동가치 개발 실험 | Completed |
| [EX-066](../research/action-value/experiments/EX-066-joint-q-training.md) | Qwen3.5-4B-Base 공동 q 학습·독립 평가 | Blocked — 새 프로세스 재로딩 gate 실패 |
| [EX-071](../research/policy-learning/experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EX-107](../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md) | Tacit-9B 규칙 Q&A LoRA | Completed |
| [EX-113](../research/rule-learning/experiments/EX-113-jevk5-ruleqa-lora.md) | JevK5-9B 규칙 선택형 추가 LoRA | Completed |
| [EX-116](../research/rule-learning/experiments/EX-116-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |

## 학습 / RLCD

| ID | 제목 | 상태 |
|---|---|---|
| [D-096](../research/policy-learning/decisions/D-096-pokemon-training-objective.md) | 세 RLCD 환경을 활용한 포켓몬 전용 학습 당면 목표 채택 | Accepted |
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-114](../research/policy-learning/decisions/D-114-selfplay-rlcd.md) | 단일 GPU 자기대국과 선택 행동 확률 보정 | Accepted |
| [EP-099](../research/policy-learning/plans/EP-099-pokemon-training-objective.md) | 포켓몬 전용 모델 학습 당면 목표 문서화 | Completed |
| [EP-102](../research/action-value/plans/EP-102-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 학습 검증 | Completed |
| [EP-116](../research/policy-learning/plans/EP-116-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정 | Completed |
| [EX-072](../research/policy-learning/experiments/EX-072-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정: 단일 GPU 24시간 | Completed — 실험 완료, 성능 개선 미입증 |

## 학습 / SFT

| ID | 제목 | 상태 |
|---|---|---|
| [EX-107](../research/rule-learning/experiments/EX-107-tacit-ruleqa-lora.md) | Tacit-9B 규칙 Q&A LoRA | Completed |

## 학습 / System1

| ID | 제목 | 상태 |
|---|---|---|
| [D-180](../research/rule-learning/decisions/D-180-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Accepted |
| [EP-203](../research/rule-learning/plans/EP-203-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |
| [EX-116](../research/rule-learning/experiments/EX-116-jevk5-system1-full-training.md) | JevK5 전체 System One 학습 | Completed |

## 학습 / laya

| ID | 제목 | 상태 |
|---|---|---|
| [D-183](../research/policy-learning/decisions/D-183-laya-compact-imitation.md) | laya 압축 입력 모방 학습과 표준 배틀 평가 | Accepted |
| [D-185](../research/policy-learning/decisions/D-185-laya-modular-renderer-v2.md) | laya 모듈형 렌더러 v2(기술 변형·속도·교체·피해량) | Accepted |
| [D-187](../research/policy-learning/decisions/D-187-laya-tera-knowledge.md) | laya v2에 테라 기본 지식 데이터 추가(GPU1) | Accepted |
| [D-188](../research/policy-learning/decisions/D-188-laya-effect-knowledge.md) | laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2) | Accepted |
| [D-189](../research/policy-learning/decisions/D-189-laya-renderer-v3-opponent-sets.md) | laya 렌더러 v3(상대 세트 추론)와 래더 대비 학습(GPU0) | Accepted |
| [D-190](../research/policy-learning/decisions/D-190-laya-ex129-gate-override.md) | EX-128 진행 조건 미충족에도 EX-129 배틀 실행(사용자 결정) | Accepted |
| [D-191](../research/policy-learning/decisions/D-191-no-offline-battle-gate.md) | 오프라인 test 평가로 배틀 평가를 거르지 않는다 | Accepted |
| [D-192](../research/policy-learning/decisions/D-192-laya-renderer-v4-fail-out.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해)와 GPU1 학습·배틀 | Accepted |
| [D-193](../research/policy-learning/decisions/D-193-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방(GPU0 학습·배틀) | Accepted |
| [D-195](../research/policy-learning/decisions/D-195-laya-item-state-renderer-v5.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터)와 학습·배틀 | Accepted |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Active |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Active |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Active |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Running |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Running |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Planned |

## 학습 / soft-CE

| ID | 제목 | 상태 |
|---|---|---|
| [D-183](../research/policy-learning/decisions/D-183-laya-compact-imitation.md) | laya 압축 입력 모방 학습과 표준 배틀 평가 | Accepted |
| [D-185](../research/policy-learning/decisions/D-185-laya-modular-renderer-v2.md) | laya 모듈형 렌더러 v2(기술 변형·속도·교체·피해량) | Accepted |
| [D-187](../research/policy-learning/decisions/D-187-laya-tera-knowledge.md) | laya v2에 테라 기본 지식 데이터 추가(GPU1) | Accepted |
| [D-188](../research/policy-learning/decisions/D-188-laya-effect-knowledge.md) | laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2) | Accepted |
| [D-189](../research/policy-learning/decisions/D-189-laya-renderer-v3-opponent-sets.md) | laya 렌더러 v3(상대 세트 추론)와 래더 대비 학습(GPU0) | Accepted |
| [D-190](../research/policy-learning/decisions/D-190-laya-ex129-gate-override.md) | EX-128 진행 조건 미충족에도 EX-129 배틀 실행(사용자 결정) | Accepted |
| [D-191](../research/policy-learning/decisions/D-191-no-offline-battle-gate.md) | 오프라인 test 평가로 배틀 평가를 거르지 않는다 | Accepted |
| [D-192](../research/policy-learning/decisions/D-192-laya-renderer-v4-fail-out.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해)와 GPU1 학습·배틀 | Accepted |
| [D-193](../research/policy-learning/decisions/D-193-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방(GPU0 학습·배틀) | Accepted |
| [D-195](../research/policy-learning/decisions/D-195-laya-item-state-renderer-v5.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터)와 학습·배틀 | Accepted |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Active |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Active |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Active |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Running |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Running |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Planned |

## 학습 / 공동 q

| ID | 제목 | 상태 |
|---|---|---|
| [EX-066](../research/action-value/experiments/EX-066-joint-q-training.md) | Qwen3.5-4B-Base 공동 q 학습·독립 평가 | Blocked — 새 프로세스 재로딩 gate 실패 |

## 학습 / 규칙 데이터 생성

| ID | 제목 | 상태 |
|---|---|---|
| [EP-195](../research/rule-learning/plans/EP-195-gen9-status-system1-data.md) | Gen9 상태이상 System 1 학습자료 | Completed |
| [EP-196](../research/rule-learning/plans/EP-196-gen9-priority-system1-data.md) | Gen9 행동 우선도 System 1 자료 | Completed |
| [EP-197](../research/rule-learning/plans/EP-197-gen9-weather-terrain-system1-data.md) | Gen9 날씨·영역 System 1 자료 | Completed |

## 학습 / 리플레이 결과 지도

| ID | 제목 | 상태 |
|---|---|---|
| [D-175](../research/rule-learning/decisions/D-175-replay-ko-system1-data.md) | 실제 리플레이의 관측 KO 결과 학습자료 | Accepted |
| [EP-198](../research/rule-learning/plans/EP-198-replay-ko-system1-data.md) | 실제 리플레이 KO 결과 예측 System 1 자료 | Completed |

## 학습 / 모방

| ID | 제목 | 상태 |
|---|---|---|
| [D-183](../research/policy-learning/decisions/D-183-laya-compact-imitation.md) | laya 압축 입력 모방 학습과 표준 배틀 평가 | Accepted |
| [D-185](../research/policy-learning/decisions/D-185-laya-modular-renderer-v2.md) | laya 모듈형 렌더러 v2(기술 변형·속도·교체·피해량) | Accepted |
| [D-187](../research/policy-learning/decisions/D-187-laya-tera-knowledge.md) | laya v2에 테라 기본 지식 데이터 추가(GPU1) | Accepted |
| [D-188](../research/policy-learning/decisions/D-188-laya-effect-knowledge.md) | laya v2+테라에 기술·도구·특성 효과 지식 데이터 추가(GPU2) | Accepted |
| [D-189](../research/policy-learning/decisions/D-189-laya-renderer-v3-opponent-sets.md) | laya 렌더러 v3(상대 세트 추론)와 래더 대비 학습(GPU0) | Accepted |
| [D-190](../research/policy-learning/decisions/D-190-laya-ex129-gate-override.md) | EX-128 진행 조건 미충족에도 EX-129 배틀 실행(사용자 결정) | Accepted |
| [D-191](../research/policy-learning/decisions/D-191-no-offline-battle-gate.md) | 오프라인 test 평가로 배틀 평가를 거르지 않는다 | Accepted |
| [D-192](../research/policy-learning/decisions/D-192-laya-renderer-v4-fail-out.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해)와 GPU1 학습·배틀 | Accepted |
| [D-193](../research/policy-learning/decisions/D-193-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방(GPU0 학습·배틀) | Accepted |
| [D-195](../research/policy-learning/decisions/D-195-laya-item-state-renderer-v5.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터)와 학습·배틀 | Accepted |
| [EP-208](../research/policy-learning/plans/EP-208-laya-compact-imitation.md) | laya 압축 입력 모방 학습·배틀 에이전트 | Completed |
| [EP-210](../research/policy-learning/plans/EP-210-laya-renderer-v2.md) | laya 모듈형 렌더러 v2 학습과 v1·v2 비교 | Completed |
| [EP-212](../research/policy-learning/plans/EP-212-laya-tera-knowledge.md) | laya v2 테라 지식 데이터 학습과 배틀 비교(GPU1) | Completed |
| [EP-213](../research/policy-learning/plans/EP-213-laya-effect-knowledge.md) | laya v2+테라+효과 지식 데이터 학습과 배틀 비교(GPU2) | Completed |
| [EP-214](../research/policy-learning/plans/EP-214-laya-renderer-v3.md) | laya 렌더러 v3(상대 세트 추론) 학습과 배틀 비교(GPU0) | Completed |
| [EP-215](../research/policy-learning/plans/EP-215-laya-renderer-v4.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) 학습과 배틀 비교(GPU1) | Active |
| [EP-216](../research/policy-learning/plans/EP-216-laya-outcome-weighted-imitation.md) | laya v2+테라 승패 가중 모방 학습과 배틀 비교(GPU0) | Active |
| [EP-218](../research/policy-learning/plans/EP-218-laya-renderer-v5-item-state.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) 학습과 배틀 비교(GPU0·GPU2) | Active |
| [EX-118](../research/policy-learning/experiments/EX-118-laya-compact-imitation-training.md) | laya 압축 입력 리플레이 모방 학습 | Completed |
| [EX-121](../research/policy-learning/experiments/EX-121-laya-v2-all-training.md) | laya 모듈형 렌더러 v2(4종 전부) 학습과 v1 쌍비교 | Completed |
| [EX-124](../research/policy-learning/experiments/EX-124-laya-v2-tera-knowledge-training.md) | laya v2 + 테라 기본 지식 데이터 학습(GPU1) | Completed |
| [EX-126](../research/policy-learning/experiments/EX-126-laya-v2-tera-effect-training.md) | laya v2 + 테라 + 효과 지식 데이터 학습(GPU2) | Completed |
| [EX-128](../research/policy-learning/experiments/EX-128-laya-v3-tera-training.md) | laya 렌더러 v3(상대 세트 추론) + 테라 지식 학습(GPU0) | Completed |
| [EX-130](../research/policy-learning/experiments/EX-130-laya-v4-tera-training.md) | laya 렌더러 v4(확정 실패 표시·교체 후보 공격 피해) + 테라 지식 학습(GPU1) | Running |
| [EX-132](../research/policy-learning/experiments/EX-132-laya-v2t-outcome-weighted-training.md) | laya v2+테라 승패 가중 모방 학습(GPU0) | Running |
| [EX-136](../research/policy-learning/experiments/EX-136-laya-v5-tera-training.md) | laya 렌더러 v5(상대 아이템 상태·상태 카운터) + 테라 지식 학습(GPU0) | Planned |

## 학습 / 모방 학습

| ID | 제목 | 상태 |
|---|---|---|
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-113](../research/policy-learning/decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [D-115](../research/policy-learning/decisions/D-115-abyssal-first-objective.md) | Abyssal 상대 효율적 승리를 당면 단기 목표로 채택 | Accepted |
| [EP-114](../research/policy-learning/plans/EP-114-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 구체화 | Completed |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-116](../research/policy-learning/plans/EP-116-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정 | Completed |
| [EX-071](../research/policy-learning/experiments/EX-071-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |

## 학습 / 본문 근거 역할 주석

| ID | 제목 | 상태 |
|---|---|---|
| [D-177](../research/rule-learning/decisions/D-177-smogon-role-system1-data.md) | Smogon 분석의 역할 근거 학습 | Accepted |
| [EP-200](../research/rule-learning/plans/EP-200-smogon-role-system1-data.md) | Smogon 전략 기반 역할 System 1 자료 | Completed |

## 학습 / 분류 데이터 생성

| ID | 제목 | 상태 |
|---|---|---|
| [EP-193](../research/rule-learning/plans/EP-193-gen9-type-system1-data.md) | Gen9 타입 System 1 판별 학습자료 | Completed |

## 학습 / 선택지 교차엔트로피

| ID | 제목 | 상태 |
|---|---|---|
| [D-175](../research/rule-learning/decisions/D-175-replay-ko-system1-data.md) | 실제 리플레이의 관측 KO 결과 학습자료 | Accepted |
| [D-176](../research/rule-learning/decisions/D-176-conditional-ko-system1-data.md) | 조건부 KO와 관측 KO의 분리 | Accepted |
| [D-177](../research/rule-learning/decisions/D-177-smogon-role-system1-data.md) | Smogon 분석의 역할 근거 학습 | Accepted |
| [D-178](../research/rule-learning/decisions/D-178-gen9-mechanics-system1-data.md) | 우선순위별 규칙 적용과 정보 충분성 자료 | Accepted |
| [EP-193](../research/rule-learning/plans/EP-193-gen9-type-system1-data.md) | Gen9 타입 System 1 판별 학습자료 | Completed |
| [EP-195](../research/rule-learning/plans/EP-195-gen9-status-system1-data.md) | Gen9 상태이상 System 1 학습자료 | Completed |
| [EP-196](../research/rule-learning/plans/EP-196-gen9-priority-system1-data.md) | Gen9 행동 우선도 System 1 자료 | Completed |
| [EP-197](../research/rule-learning/plans/EP-197-gen9-weather-terrain-system1-data.md) | Gen9 날씨·영역 System 1 자료 | Completed |
| [EP-198](../research/rule-learning/plans/EP-198-replay-ko-system1-data.md) | 실제 리플레이 KO 결과 예측 System 1 자료 | Completed |
| [EP-199](../research/rule-learning/plans/EP-199-conditional-ko-system1-data.md) | 조건부 확정 KO 판정 자료 | Completed |
| [EP-200](../research/rule-learning/plans/EP-200-smogon-role-system1-data.md) | Smogon 전략 기반 역할 System 1 자료 | Completed |
| [EP-201](../research/rule-learning/plans/EP-201-gen9-mechanics-system1-data.md) | 우선순위별 Gen9 규칙 적용 System 1 자료 | Completed |
| [EX-113](../research/rule-learning/experiments/EX-113-jevk5-ruleqa-lora.md) | JevK5-9B 규칙 선택형 추가 LoRA | Completed |

## 학습 / 자기대국

| ID | 제목 | 상태 |
|---|---|---|
| [D-112](../research/policy-learning/decisions/D-112-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 채택 | Accepted |
| [D-113](../research/policy-learning/decisions/D-113-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Accepted |
| [D-114](../research/policy-learning/decisions/D-114-selfplay-rlcd.md) | 단일 GPU 자기대국과 선택 행동 확률 보정 | Accepted |
| [D-115](../research/policy-learning/decisions/D-115-abyssal-first-objective.md) | Abyssal 상대 효율적 승리를 당면 단기 목표로 채택 | Accepted |
| [D-119](../research/fixed-matchup-learning/decisions/D-119-fixed-matchup-mcts.md) | 고정 대진 공개 상태 MCTS 정책 학습 | Accepted |
| [D-127](../research/fixed-matchup-learning/decisions/D-127-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Accepted |
| [EP-114](../research/policy-learning/plans/EP-114-imitation-self-play-objectives.md) | Qwen 모방 학습·자기대국 단기 목표 구체화 | Completed |
| [EP-115](../research/policy-learning/plans/EP-115-qwen-replay-imitation.md) | Qwen 4B 리플레이 모방 학습과 첫 배틀 평가 | Completed |
| [EP-116](../research/policy-learning/plans/EP-116-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정 | Completed |
| [EP-118](../research/policy-learning/plans/EP-118-abyssal-first-objective.md) | Abyssal 우선 단기 목표 정비 | Completed |
| [EP-127](../research/fixed-matchup-learning/plans/EP-127-fixed-matchup-first-round.md) | 첫1라운드 학습 | Blocked — 원실행1경기 시간초과·학습0; 시간 규범 변경 완료 후 재개 미실행 |
| [EP-132](../research/fixed-matchup-learning/plans/EP-132-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 자기대국 학습 실행 | Completed |
| [EX-072](../research/policy-learning/experiments/EX-072-selfplay-rlcd.md) | 자기대국과 RLCD 확률 보정: 단일 GPU 24시간 | Completed — 실험 완료, 성능 개선 미입증 |
| [EX-076](../research/fixed-matchup-learning/experiments/EX-076-fixed-matchup-mcts.md) | 고정 A/B 공개 상태 MCTS 정책 학습 | Incomplete — 교정 후 기술 검증/측정 통과, 평가 예산 gate 초과로 학습/test 보류 |
| [EX-077](../research/fixed-matchup-learning/experiments/EX-077-fixed-matchup-day.md) | 하루 내 고정 대진 공개 상태 학습 | Incomplete — 사용자 요청 중지; 학습/test 미시작 |
| [EX-078](../research/fixed-matchup-learning/experiments/EX-078-fixed-matchup-first-round.md) | 첫1라운드 학습 체크포인트 | Completed — D-125 복구·첫라운드 진단 완료; 원실행 Incomplete 보존 |
| [EX-079](../research/fixed-matchup-learning/experiments/EX-079-fixed-matchup-stopping.md) | 종료조건 기반 고정 대진 추가 학습 | Completed — 추가학습·시험·감사/뷰어·정리 완료; 주효능 기준 미달 |
| [EX-080](../research/fixed-matchup-learning/experiments/EX-080-qwen-matrix-selfplay.md) | Qwen3.5-0.8B 행렬 탐색 고정 대진 자기대국 학습 | Completed — 시도 3 학습(round40 둔화 종료)·선택(round36)·잠긴 test·감사/뷰어/봉인·정리 완료; 주효능 미입증 (시도 1·2는 도구 결함으로 학습 전 중단·보존) |

## 학습 / 정책 강화학습

| ID | 제목 | 상태 |
|---|---|---|
| [EX-073](../research/policy-learning/experiments/EX-073-abyssal-rl.md) | Abyssal 우선 정책 학습: 4GPU·24시간 | Incomplete — 학습·test·독립 감사 완료, 최종 뷰어 검증 시간 초과 |
| [EX-074](../research/policy-learning/experiments/EX-074-abyssal-rl-continue.md) | 57라운드 계승·동일 설정 추가12시간 학습 | Completed — 실험 완료·57라운드 출발 대비 통계적 개선·성능 목표 미달 |
| [EX-075](../research/policy-learning/experiments/EX-075-abyssal-rl-next.md) | 82라운드 계승·동일 설정 추가12시간 1회 | Completed — 필수 검증·평가·뷰어·봉인·정리 완료; 개선 미입증·목표 미달 |

## 학습 / 조건부 KO 판정

| ID | 제목 | 상태 |
|---|---|---|
| [D-176](../research/rule-learning/decisions/D-176-conditional-ko-system1-data.md) | 조건부 KO와 관측 KO의 분리 | Accepted |
| [EP-199](../research/rule-learning/plans/EP-199-conditional-ko-system1-data.md) | 조건부 확정 KO 판정 자료 | Completed |

## 학습 / 학습 데이터 생성

| ID | 제목 | 상태 |
|---|---|---|
| [D-174](../research/rule-learning/decisions/D-174-gen9-type-matchup-dataset.md) | Gen9 타입 상성 전수 자료 | Accepted |
| [EP-192](../research/rule-learning/plans/EP-192-gen9-type-matchup-dataset.md) | Gen9 타입 상성 전수 학습 데이터 | Completed |

## 학습 / 합성 규칙 자료

| ID | 제목 | 상태 |
|---|---|---|
| [D-178](../research/rule-learning/decisions/D-178-gen9-mechanics-system1-data.md) | 우선순위별 규칙 적용과 정보 충분성 자료 | Accepted |
| [EP-201](../research/rule-learning/plans/EP-201-gen9-mechanics-system1-data.md) | 우선순위별 Gen9 규칙 적용 System 1 자료 | Completed |

## 학습 / 행동가치

| ID | 제목 | 상태 |
|---|---|---|
| [D-098](../research/action-value/decisions/D-098-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 첫 행동가치 학습 | Accepted |
| [D-099](../research/action-value/decisions/D-099-qwen-local-battle.md) | Qwen 행동가치 로컬 서빙·배틀 연결 | Accepted |
| [D-103](../research/action-value/decisions/D-103-joint-q-data.md) | 다경기 공동 q 데이터 | Accepted |
| [D-104](../research/action-value/decisions/D-104-joint-q-training.md) | EX-065 기반 Base 공동 q 학습 | Accepted |
| [D-105](../research/action-value/decisions/D-105-joint-q-gpu2.md) | 공동 q 학습의 GPU2 지정 | Accepted |
| [D-106](../research/action-value/decisions/D-106-joint-q-idle-gpu.md) | 공동 q 학습의 유휴 GPU 대체 | Accepted |
| [EP-107](../research/action-value/plans/EP-107-joint-q-data.md) | Abyssal 80경기 공동 q 데이터 | Completed |
| [EP-108](../research/action-value/plans/EP-108-joint-q-training.md) | EX-065 기반 Base 공동 q 학습 | Blocked |
| [EP-110](../research/action-value/plans/EP-110-abyssal-tera-joint-q.md) | Abyssal Tera 정책과 보완 공동 q 데이터 | Completed |
| [EX-061](../research/action-value/experiments/EX-061-qwen-action-value.md) | EX-060 기반 Qwen3.5-4B 행동가치 개발 실험 | Completed |
